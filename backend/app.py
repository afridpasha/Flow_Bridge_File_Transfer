"""
FlowBridge v3.0 — Hybrid File Transfer System
Main application entry point with all security middleware.
"""

import os
import sys
import logging
import secrets
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from config import Config

# ========== Logging ==========
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== App Init ==========
app = Flask(
    __name__,
    template_folder=os.path.join(current_dir, '..', 'frontend', 'templates'),
    static_folder=os.path.join(current_dir, '..', 'frontend', 'static'),
)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

# ========== Middleware ==========

# CORS - Allow all origins for deployed version
CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"],
    "supports_credentials": True,
    "expose_headers": ["Content-Type", "Authorization"]
}})

# GZip/Brotli Compression (Feature #5)
# Exclude socket.io paths — compression breaks WebSocket upgrade handshake
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/javascript',
    'application/json', 'application/javascript'
]
app.config['COMPRESS_EXCLUDE_PATHS'] = ['/socket.io']
Compress(app)

# Rate Limiting (Feature #1)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[Config.RATE_LIMIT_DEFAULT],
    storage_uri="memory://",
)

# SocketIO
async_mode = 'threading'
for mode in ['eventlet', 'gevent']:
    try:
        __import__(mode)
        async_mode = mode
        break
    except ImportError:
        pass

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode=async_mode,
    max_http_buffer_size=10 * 1024 * 1024,
    ping_timeout=60,
    ping_interval=25,
    logger=True,
    engineio_logger=True,
    **({"allow_unsafe_werkzeug": True} if async_mode == "threading" else {})
)

# ========== Request Latency Tracking (feeds CF Worker adaptive weights) ==========

@app.before_request
def _before():
    try:
        from flask import g
        import time
        g._start_time = time.time()
    except RuntimeError:
        # Ignore if called outside request context (during eventlet monkey patching)
        pass

@app.after_request
def set_security_headers(response):
    # Record latency for CF Worker adaptive weight metrics
    try:
        import time
        from flask import g
        if hasattr(g, '_start_time'):
            latency_ms = (time.time() - g._start_time) * 1000
            from routes.scaling_routes import record_request_latency
            record_request_latency(latency_ms, response.status_code >= 500)
    except (RuntimeError, AttributeError):
        # Ignore if called outside request context
        pass
    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    # CSP — allow inline scripts + CDN resources
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' ws: wss: https:; "
        "frame-src 'self'"
    )
    return response

# ========== Database Init ==========
Config.init_app()

from database import Database
try:
    Database.initialize()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Database init failed: {e}")

# ========== Storage + Cache Init ==========
from services.storage_service import get_storage_service
from services.redis_cache_service import get_cache_service
try:
    storage = get_storage_service()
    if storage.is_available():
        logger.info("✅ Storage service initialized")
    else:
        logger.warning("⚠️ No storage backend configured — uploads will fail")
except Exception as e:
    logger.error(f"Storage init failed: {e}")

try:
    cache = get_cache_service()
    logger.info(f"✅ Cache service initialized — upstash={cache.is_upstash_connected}")
except Exception as e:
    logger.warning(f"Cache init failed: {e}")

# ========== Register Blueprints ==========
from routes.auth_routes import auth_bp
from routes.file_routes import file_bp
from routes.share_routes import share_bp
from routes.tcp_routes import tcp_bp
from routes.user_file_routes import user_file_bp
from routes.transfer_routes import transfer_bp
from routes.totp_routes import totp_bp
from routes.zip_routes import zip_bp
from routes.activity_routes import activity_bp
from routes.api_docs_routes import api_docs_bp
from routes.codeshare_routes import codeshare_bp
from routes.scaling_routes import scaling_bp
from routes.advanced_routes import advanced_bp

for bp in [auth_bp, file_bp, share_bp, tcp_bp, user_file_bp,
           transfer_bp, totp_bp, zip_bp, activity_bp, api_docs_bp, codeshare_bp, scaling_bp, advanced_bp]:
    app.register_blueprint(bp)

# Make limiter accessible to blueprints
app.limiter = limiter

# ========== WebSocket ==========
from websocket_transfer import register_websocket_events
register_websocket_events(socketio)

# ========== Create Storage Dirs ==========
for folder in [Config.STORAGE_DIR, Config.UPLOAD_FOLDER,
               Config.DOWNLOAD_FOLDER, Config.SHARED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ========== TCP Receiver ==========
# Only start TCP receiver if not on Render (Render doesn't support TCP)
if not os.environ.get('RENDER'):
    from tcp_receiver import TCPReceiver
    tcp_receiver = TCPReceiver(socketio)
    tcp_receiver.start()
    logger.info(f"TCP Receiver started on port {Config.TCP_PORT}")
else:
    logger.info("TCP Receiver disabled (running on Render)")

# ========== Page Routes (Keep for backward compatibility) ==========

@app.route('/')
def index():
    """Redirect to React frontend or serve API info."""
    if request.accept_mimetypes.best_match(['text/html', 'application/json']) == 'application/json':
        return jsonify({
            'name': 'FlowBridge API',
            'version': '3.0.0',
            'frontend': 'https://flowbridge.pages.dev',
            'docs': '/api/docs',
            'health': '/health'
        })
    return render_template('login.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/transfer-mode')
def transfer_mode():
    return render_template('transfer-mode.html')

@app.route('/receive')
def receive_page():
    return render_template('receive.html')

@app.route('/activity')
def activity_page():
    return render_template('activity.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

@app.route('/socketio-test')
def socketio_test():
    return render_template('socketio_test.html')

@app.route('/monitor')
def monitor_page():
    return render_template('monitor.html')

@app.route('/webrtc')
def webrtc_page():
    return render_template('webrtc_transfer.html')

# ========== Health Check ==========

@app.route('/health')
def health_check():
    """Rich health check — read by Cloudflare Worker every 30s."""
    import psutil, time
    try:
        db = Database.get_db()
        db.command('ping')
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    proc = psutil.Process(os.getpid())
    cpu   = psutil.cpu_percent(interval=0.1)
    mem   = psutil.virtual_memory()
    uptime = int(time.time() - proc.create_time())

    # Determine health: degraded if DB down OR cpu/mem critical
    healthy = db_status == "connected" and cpu < 90 and mem.percent < 90

    from services.storage_service import get_storage_service
    from services.redis_cache_service import get_cache_service
    storage = get_storage_service()
    cache   = get_cache_service()

    return jsonify({
        'status':   'healthy' if healthy else 'degraded',
        'database': db_status,
        'version':  '3.0.0',
        'instance': os.environ.get('INSTANCE_ID', 'primary'),
        'uptime_seconds': uptime,
        'metrics': {
            'cpu_percent':    round(cpu, 1),
            'memory_percent': round(mem.percent, 1),
            'memory_free_mb': round(mem.available / 1024 / 1024, 1),
        },
        'storage': {
            'r2':    bool(storage.r2),
            'b2':    bool(storage.b2),
            'minio': bool(storage.minio),
        },
        'cache': {
            'upstash': cache.is_upstash_connected,
        },
    }), 200 if healthy else 503


@app.route('/api/public-url', methods=['GET'])
def get_public_url():
    """Get current public URL and refresh if needed."""
    # Refresh the public URL
    Config.PUBLIC_URL = Config.get_public_url()
    
    is_localhost = 'localhost' in Config.PUBLIC_URL or '127.0.0.1' in Config.PUBLIC_URL
    
    return jsonify({
        'success': True,
        'public_url': Config.PUBLIC_URL,
        'is_localhost': is_localhost,
        'warning': 'Share links will only work on this computer. Start ngrok or set PUBLIC_URL in .env' if is_localhost else None,
        'tips': [
            'Start ngrok: ngrok http 5000',
            'Or set PUBLIC_URL in .env file',
            'Or deploy to Render for permanent URL'
        ] if is_localhost else []
    })

# ========== Error Handlers ==========

@app.errorhandler(404)
def not_found(e):
    if _wants_json():
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return render_template('error.html', error_code=404,
                           error_message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    if _wants_json():
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return render_template('error.html', error_code=500,
                           error_message="Internal server error"), 500

@app.errorhandler(429)
def rate_limit_error(e):
    return jsonify({
        'success': False,
        'error': 'Too many requests. Please slow down.',
        'retry_after': e.description
    }), 429

def _wants_json():
    from flask import request
    return (request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json'
            or request.path.startswith('/api/'))

# ========== SocketIO Events ==========
# Note: disconnect is handled in websocket_transfer.py for room cleanup

@socketio.on('connect')
def handle_connect():
    logger.debug('Client connected')

# ========== Server Start ==========

def start_server():
    """Start the FlowBridge server."""
    port = int(os.environ.get('PORT', Config.HTTP_PORT))
    
    # Check storage status
    from services.storage_service import get_storage_service
    from services.redis_cache_service import get_cache_service
    storage = get_storage_service()
    cache   = get_cache_service()
    r2_ok    = "✅" if storage.r2    else "❌"
    b2_ok    = "✅" if storage.b2    else "❌"
    minio_ok = "✅" if storage.minio else "❌"
    redis_ok = "✅ Upstash" if cache.is_upstash_connected else "⚠️ InMemory"
    
    print("=" * 60)
    print(" FlowBridge Hybrid File Transfer System v3.0")
    print("=" * 60)
    print(f" Public URL : {Config.PUBLIC_URL}")
    print(f" HTTP Port  : {port}")
    if not os.environ.get('RENDER'):
        print(f" TCP Port   : {Config.TCP_PORT}")
    print(f" R2 Primary : {r2_ok}")
    print(f" B2 Replica : {b2_ok}  (EU Central)")
    print(f" MinIO Local: {minio_ok} (localhost:9000)")
    print(f" Cache      : {redis_ok}")
    print(f" Async Mode : {async_mode}")
    print("=" * 60)

    run_kwargs = dict(host=Config.HOST, port=port, debug=False)
    if async_mode == 'threading':
        run_kwargs['allow_unsafe_werkzeug'] = True
    socketio.run(app, **run_kwargs)


if __name__ == '__main__':
    start_server()

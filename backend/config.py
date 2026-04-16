import os
import secrets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration - all secrets from environment variables."""

    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_hex(32)
    JWT_ACCESS_EXPIRY_MINUTES = 30
    JWT_REFRESH_EXPIRY_DAYS = 7

    # MongoDB Settings
    MONGO_URI = os.environ.get('MONGO_URI', '')
    MONGO_DB_NAME = "flowbridge_db"

    # Server Settings
    HTTP_PORT = int(os.environ.get('PORT', os.environ.get('HTTP_PORT', 5000)))
    TCP_PORT = int(os.environ.get('TCP_PORT', 5555))
    HOST = '0.0.0.0'

    # Public URL
    @staticmethod
    def get_public_url():
        """Auto-detect public URL from multiple sources."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Priority 1: Environment variable (for production/Render)
        env_url = os.environ.get('PUBLIC_URL')
        if env_url and env_url.strip():
            url = env_url.rstrip('/')
            logger.info(f"✅ Using PUBLIC_URL from environment: {url}")
            return url
        
        # Priority 2: Render.com auto-detection
        render_external_url = os.environ.get('RENDER_EXTERNAL_URL')
        if render_external_url:
            url = render_external_url.rstrip('/')
            logger.info(f"✅ Detected Render.com URL: {url}")
            return url
        
        # Priority 3: ngrok API (for local development)
        try:
            import requests as req
            response = req.get('http://localhost:4040/api/tunnels', timeout=2)
            if response.status_code == 200:
                tunnels = response.json().get('tunnels', [])
                # Prefer HTTPS tunnel
                for tunnel in tunnels:
                    if tunnel.get('proto') == 'https':
                        url = tunnel['public_url']
                        logger.info(f"✅ Detected ngrok HTTPS URL: {url}")
                        return url
                # Fallback to any tunnel
                if tunnels:
                    url = tunnels[0]['public_url']
                    logger.info(f"✅ Detected ngrok URL: {url}")
                    return url
        except Exception as e:
            logger.debug(f"ngrok not detected: {e}")
        
        # Priority 4: Try to get public IP (for LAN access)
        try:
            import requests as req
            response = req.get('https://api.ipify.org?format=json', timeout=3)
            if response.status_code == 200:
                public_ip = response.json().get('ip')
                if public_ip:
                    # Use PORT env variable if available (for Render)
                    port = int(os.environ.get('PORT', Config.HTTP_PORT))
                    url = f'http://{public_ip}:{port}'
                    logger.warning(f"⚠️ Using public IP (may not work if behind NAT): {url}")
                    return url
        except Exception as e:
            logger.debug(f"Could not get public IP: {e}")
        
        # Priority 5: Localhost fallback (only works on same machine)
        port = int(os.environ.get('PORT', Config.HTTP_PORT))
        url = f'http://localhost:{port}'
        logger.warning(f"⚠️ FALLBACK: Using localhost URL (share links won't work externally!): {url}")
        logger.warning("💡 TIP: Start ngrok with 'ngrok http 5000' or deploy to Render.com")
        return url

    PUBLIC_URL = None  # Set during app init

    # Storage Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STORAGE_DIR = os.path.join(BASE_DIR, 'storage')
    UPLOAD_FOLDER = os.path.join(STORAGE_DIR, 'uploads')
    DOWNLOAD_FOLDER = os.path.join(STORAGE_DIR, 'downloads')
    SHARED_FOLDER = os.path.join(STORAGE_DIR, 'shared')

    # File Settings
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_FILE_SIZE_MB', 2048)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg',
        'mp4', 'avi', 'mkv', 'mov', 'webm',
        'mp3', 'wav', 'ogg', 'flac',
        'zip', 'rar', '7z', 'tar', 'gz',
        'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'csv',
        'py', 'js', 'html', 'css', 'json', 'xml', 'md',
        'apk', 'exe', 'dmg', 'iso'
    }

    PREVIEWABLE_IMAGES = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}
    PREVIEWABLE_TEXT = {'txt', 'py', 'js', 'html', 'css', 'json', 'xml', 'md', 'csv'}
    PREVIEWABLE_VIDEO = {'mp4', 'webm'}
    PREVIEWABLE_AUDIO = {'mp3', 'wav', 'ogg'}

    # TCP Settings
    BUFFER_SIZE = 65536
    FILENAME_SIZE = 256
    FILESIZE_SIZE = 20

    # Transfer Settings
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming
    MAX_CONCURRENT_TRANSFERS = 5

    # Rate Limiting
    RATE_LIMIT_DEFAULT = "200 per minute"
    RATE_LIMIT_LOGIN = "5 per minute"
    RATE_LIMIT_SIGNUP = "3 per minute"
    RATE_LIMIT_API = "100 per minute"
    RATE_LIMIT_UPLOAD = "20 per minute"
    RATE_LIMIT_SHARE = "30 per minute"

    # OTP Settings
    OTP_MAX_ATTEMPTS = 3
    OTP_LOCKOUT_MINUTES = 15
    SHARE_DEFAULT_EXPIRY_HOURS = 24

    # Password Policy
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_DIGIT = True

    # Email (SMTP)
    EMAIL_USER = os.environ.get('EMAIL_USER', '')
    EMAIL_PASS = os.environ.get('EMAIL_PASS', '')
    EMAIL_SMTP_HOST = os.environ.get('EMAIL_SMTP_HOST', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.environ.get('EMAIL_SMTP_PORT', 587))
    EMAIL_ENABLED = bool(os.environ.get('EMAIL_USER'))

    # ── Cloudflare R2 — PRIMARY binary storage ──────────────────────────────
    R2_ACCOUNT_ID          = os.environ.get('R2_ACCOUNT_ID', '')
    R2_ACCESS_KEY_ID       = os.environ.get('R2_ACCESS_KEY_ID', '')
    R2_SECRET_ACCESS_KEY   = os.environ.get('R2_SECRET_ACCESS_KEY', '')
    R2_BUCKET_FILES        = os.environ.get('R2_BUCKET_FILES', 'flowbridge-files')
    R2_BUCKET_THUMBS       = os.environ.get('R2_BUCKET_THUMBS', 'flowbridge-thumbs')
    R2_BUCKET_ZIPS         = os.environ.get('R2_BUCKET_ZIPS', 'flowbridge-zips')
    R2_ENABLED             = bool(os.environ.get('R2_ACCOUNT_ID'))

    # ── Backblaze B2 — GLOBAL REPLICA (EU Central) ───────────────────────────
    B2_ENDPOINT_URL        = os.environ.get('B2_ENDPOINT_URL', '')
    B2_ACCESS_KEY_ID       = os.environ.get('B2_ACCESS_KEY_ID', '')
    B2_SECRET_ACCESS_KEY   = os.environ.get('B2_SECRET_ACCESS_KEY', '')
    B2_BUCKET_FILES        = os.environ.get('B2_BUCKET_FILES', 'flowbridge-files-replica')
    B2_BUCKET_THUMBS       = os.environ.get('B2_BUCKET_THUMBS', 'flowbridge-thumbs-replica')
    B2_BUCKET_ZIPS         = os.environ.get('B2_BUCKET_ZIPS', 'flowbridge-zips-replica')
    B2_ENABLED             = bool(os.environ.get('B2_ENDPOINT_URL') and os.environ.get('B2_ACCESS_KEY_ID'))

    # ── MinIO — LOCAL REPLICA + LAN transfer server ───────────────────────────
    MINIO_ACCESS_KEY       = os.environ.get('MINIO_ACCESS_KEY', '')
    MINIO_SECRET_KEY       = os.environ.get('MINIO_SECRET_KEY', '')
    MINIO_ENDPOINT_URL     = os.environ.get('MINIO_ENDPOINT_URL', 'http://localhost:9000')
    MINIO_PUBLIC_ENDPOINT_URL = os.environ.get('MINIO_PUBLIC_ENDPOINT_URL', 'http://localhost:9000')
    MINIO_BUCKET_FILES     = os.environ.get('MINIO_BUCKET_FILES', 'flowbridge-files')
    MINIO_BUCKET_THUMBS    = os.environ.get('MINIO_BUCKET_THUMBS', 'flowbridge-thumbs')
    MINIO_BUCKET_ZIPS      = os.environ.get('MINIO_BUCKET_ZIPS', 'flowbridge-zips')
    MINIO_ENABLED          = bool(os.environ.get('MINIO_ACCESS_KEY') and os.environ.get('MINIO_SECRET_KEY'))

    # ── Upstash Redis — Application cache ────────────────────────────────────
    UPSTASH_REDIS_REST_URL   = os.environ.get('UPSTASH_REDIS_REST_URL', '')
    UPSTASH_REDIS_REST_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', '')
    REDIS_ENABLED            = bool(os.environ.get('UPSTASH_REDIS_REST_URL'))

    # Logging
    LOG_FILE = os.path.join(BASE_DIR, 'flowbridge.log')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

    @classmethod
    def init_app(cls):
        """Initialize runtime configuration."""
        cls.PUBLIC_URL = cls.get_public_url()
        if not cls.MONGO_URI:
            raise ValueError("MONGO_URI environment variable is required. Create a .env file.")
        return cls

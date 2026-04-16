from .file_routes import file_bp
from .transfer_routes import transfer_bp
from .auth_routes import auth_bp
from .user_file_routes import user_file_bp
from .share_routes import share_bp
from .tcp_routes import tcp_bp
from .totp_routes import totp_bp
from .zip_routes import zip_bp
from .activity_routes import activity_bp
from .api_docs_routes import api_docs_bp
from .scaling_routes import scaling_bp
from .advanced_routes import advanced_bp

__all__ = [
    'file_bp', 'transfer_bp', 'auth_bp', 'user_file_bp',
    'share_bp', 'tcp_bp', 'totp_bp', 'zip_bp',
    'activity_bp', 'api_docs_bp', 'scaling_bp', 'advanced_bp',
]

import logging
from functools import wraps
from flask import request, jsonify
import jwt
from config import Config
from models import User

logger = logging.getLogger(__name__)


def token_required(f):
    """JWT authentication decorator with proper error handling."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')

        if not token:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        try:
            if token.startswith('Bearer '):
                token = token[7:]

            data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            current_user = User.find_by_id(data['user_id'])

            if not current_user:
                return jsonify({'success': False, 'error': 'User not found'}), 401

            if User.is_locked(current_user):
                return jsonify({'success': False, 'error': 'Account is temporarily locked'}), 403

        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token expired. Please login again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Invalid token. Please login again.'}), 401
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return jsonify({'success': False, 'error': 'Authentication error'}), 401

        return f(current_user, *args, **kwargs)

    return decorated

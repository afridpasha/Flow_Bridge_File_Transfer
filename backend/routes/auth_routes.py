import logging
from flask import Blueprint, request, jsonify, current_app
import jwt
from datetime import datetime, timedelta, timezone

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import Config
from models import User, utcnow

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _get_limiter():
    """Get rate limiter from app context."""
    return getattr(current_app, 'limiter', None)


@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    """User registration with password policy enforcement."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400

    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'success': False, 'error': 'All fields are required'}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({'success': False, 'error': 'Username must be 3-30 characters'}), 400

    try:
        user, error = User.create(username, email, password)
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return jsonify({'success': False, 'error': 'Service temporarily unavailable. Please try again later.'}), 503

    if error:
        return jsonify({'success': False, 'error': error}), 400

    logger.info(f"New user registered: {username}")
    return jsonify({
        'success': True,
        'message': 'Account created successfully',
        'username': username
    })


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """User login with account lockout protection."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request body'}), 400

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400

    # Find user
    user = User.find_by_username(username)

    if not user:
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

    # Check account lock
    if User.is_locked(user):
        return jsonify({
            'success': False,
            'error': 'Account temporarily locked due to too many failed attempts. Try again later.'
        }), 403

    # Verify password
    if not User.verify_password(user['password'], password):
        attempts = User.increment_failed_login(username)
        if attempts >= 5:
            User.lock_account(username, minutes=15)
            logger.warning(f"Account locked: {username} (too many failed attempts)")
            return jsonify({
                'success': False,
                'error': 'Account locked for 15 minutes due to too many failed attempts'
            }), 403
        remaining = 5 - attempts
        return jsonify({
            'success': False,
            'error': f'Invalid credentials. {remaining} attempts remaining.'
        }), 401

    # Successful login
    User.reset_failed_login(username)

    # Log activity
    try:
        from routes.activity_routes import log_activity
        log_activity(str(user['_id']), 'login', {'ip': request.remote_addr})
    except Exception:
        pass

    # Feature #4: Check if 2FA is enabled
    if user.get('totp_enabled'):
        logger.info(f"2FA challenge issued for: {username}")
        return jsonify({
            'success': True,
            'needs_2fa': True,
            'user_id': str(user['_id']),
            'message': 'Enter your 2FA code from authenticator app.'
        })

    # Generate access token
    access_token = jwt.encode({
        'user_id': str(user['_id']),
        'username': user['username'],
        'type': 'access',
        'exp': utcnow() + timedelta(minutes=Config.JWT_ACCESS_EXPIRY_MINUTES)
    }, Config.JWT_SECRET_KEY, algorithm="HS256")

    # Generate refresh token
    refresh_token = jwt.encode({
        'user_id': str(user['_id']),
        'type': 'refresh',
        'exp': utcnow() + timedelta(days=Config.JWT_REFRESH_EXPIRY_DAYS)
    }, Config.JWT_SECRET_KEY, algorithm="HS256")

    logger.info(f"User logged in: {username}")

    return jsonify({
        'success': True,
        'token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': str(user['_id']),
            'username': user['username'],
            'email': user['email'],
            'storage_used': user.get('storage_used', 0),
            'storage_quota': user.get('storage_quota', 500 * 1024 * 1024),
        }
    })


@auth_bp.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    token = data.get('refresh_token')
    if not token:
        return jsonify({'success': False, 'error': 'Refresh token required'}), 400

    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get('type') != 'refresh':
            return jsonify({'success': False, 'error': 'Invalid token type'}), 401

        user = User.find_by_id(payload['user_id'])
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 401

        # Generate new access token
        new_access_token = jwt.encode({
            'user_id': str(user['_id']),
            'username': user['username'],
            'type': 'access',
            'exp': utcnow() + timedelta(minutes=Config.JWT_ACCESS_EXPIRY_MINUTES)
        }, Config.JWT_SECRET_KEY, algorithm="HS256")

        return jsonify({
            'success': True,
            'token': new_access_token
        })

    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Refresh token expired. Please login again.'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid refresh token'}), 401


@auth_bp.route('/api/auth/verify', methods=['GET'])
def verify_token():
    """Verify JWT token validity."""
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'success': False, 'error': 'Token missing'}), 401

    try:
        if token.startswith('Bearer '):
            token = token[7:]

        data = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        user = User.find_by_id(data['user_id'])

        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 401

        return jsonify({
            'success': True,
            'user': {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user['email'],
                'storage_used': user.get('storage_used', 0),
                'storage_quota': user.get('storage_quota', 500 * 1024 * 1024),
            }
        })
    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'success': False, 'error': 'Invalid token'}), 401


@auth_bp.route('/api/auth/change-password', methods=['POST'])
def change_password():
    """Change user password."""
    from middleware.auth_middleware import token_required as _tr
    # Inline auth check
    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'success': False, 'error': 'Auth required'}), 401
    try:
        if token.startswith('Bearer '):
            token = token[7:]
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        user = User.find_by_id(payload['user_id'])
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 401
    except Exception:
        return jsonify({'success': False, 'error': 'Auth failed'}), 401

    data = request.get_json()
    current_pw = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not User.verify_password(user['password'], current_pw):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400

    from models import validate_password
    import bcrypt as _bc
    is_valid, error = validate_password(new_pw)
    if not is_valid:
        return jsonify({'success': False, 'error': error}), 400

    from database import Database
    db = Database.get_db()
    hashed = _bc.hashpw(new_pw.encode('utf-8'), _bc.gensalt(rounds=12))
    db.users.update_one(
        {"_id": user['_id']},
        {"$set": {"password": hashed}}
    )

    return jsonify({'success': True, 'message': 'Password changed successfully'})

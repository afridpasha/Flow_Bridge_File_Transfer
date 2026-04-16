"""2FA/TOTP Authentication Routes for FlowBridge."""

import logging
import pyotp
import qrcode
import io
import base64
from flask import Blueprint, request, jsonify

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from database import Database
from bson import ObjectId

logger = logging.getLogger(__name__)
totp_bp = Blueprint('totp', __name__)


@totp_bp.route('/api/auth/2fa/setup', methods=['POST'])
@token_required
def setup_2fa(current_user):
    """Generate TOTP secret and QR code for 2FA setup."""
    if current_user.get('totp_enabled'):
        return jsonify({'success': False, 'error': '2FA is already enabled'}), 400

    # Generate secret
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)

    # Generate provisioning URI for QR code
    uri = totp.provisioning_uri(
        name=current_user['username'],
        issuer_name='FlowBridge'
    )

    # Generate QR code as base64
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    # Store secret (not yet enabled — user must verify first)
    db = Database.get_db()
    db.users.update_one(
        {'_id': current_user['_id']},
        {'$set': {'totp_secret': secret}}
    )

    return jsonify({
        'success': True,
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_base64}',
        'message': 'Scan the QR code with your authenticator app, then verify.'
    })


@totp_bp.route('/api/auth/2fa/verify-setup', methods=['POST'])
@token_required
def verify_2fa_setup(current_user):
    """Verify TOTP code to complete 2FA setup."""
    data = request.get_json()
    code = data.get('code', '').strip()

    if not code or len(code) != 6:
        return jsonify({'success': False, 'error': 'Enter a 6-digit code'}), 400

    secret = current_user.get('totp_secret')
    if not secret:
        return jsonify({'success': False, 'error': 'Run setup first'}), 400

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({'success': False, 'error': 'Invalid code. Try again.'}), 401

    # Enable 2FA
    db = Database.get_db()
    db.users.update_one(
        {'_id': current_user['_id']},
        {'$set': {'totp_enabled': True}}
    )

    logger.info(f"2FA enabled for user: {current_user['username']}")
    return jsonify({
        'success': True,
        'message': '2FA has been enabled! You will need your authenticator app to log in.'
    })


@totp_bp.route('/api/auth/2fa/validate', methods=['POST'])
def validate_2fa():
    """Validate TOTP code during login (called after password is verified)."""
    data = request.get_json()
    user_id = data.get('user_id')
    code = data.get('code', '').strip()

    if not user_id or not code:
        return jsonify({'success': False, 'error': 'User ID and code required'}), 400

    db = Database.get_db()
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        return jsonify({'success': False, 'error': 'Invalid user'}), 400

    if not user or not user.get('totp_enabled'):
        return jsonify({'success': False, 'error': '2FA not enabled'}), 400

    totp = pyotp.TOTP(user['totp_secret'])
    if not totp.verify(code, valid_window=1):
        return jsonify({'success': False, 'error': 'Invalid 2FA code'}), 401

    # Generate JWT (same as login)
    import jwt
    from datetime import datetime, timezone, timedelta
    from config import Config

    access_token = jwt.encode({
        'user_id': str(user['_id']),
        'username': user['username'],
        'exp': datetime.now(timezone.utc) + timedelta(minutes=Config.JWT_ACCESS_EXPIRY_MINUTES),
        'type': 'access'
    }, Config.JWT_SECRET_KEY, algorithm='HS256')

    refresh_token = jwt.encode({
        'user_id': str(user['_id']),
        'exp': datetime.now(timezone.utc) + timedelta(days=Config.JWT_REFRESH_EXPIRY_DAYS),
        'type': 'refresh'
    }, Config.JWT_SECRET_KEY, algorithm='HS256')

    logger.info(f"2FA validated, login complete: {user['username']}")
    return jsonify({
        'success': True,
        'token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': str(user['_id']),
            'username': user['username'],
            'email': user.get('email', ''),
        }
    })


@totp_bp.route('/api/auth/2fa/disable', methods=['POST'])
@token_required
def disable_2fa(current_user):
    """Disable 2FA for the current user."""
    data = request.get_json()
    code = data.get('code', '').strip()

    if not current_user.get('totp_enabled'):
        return jsonify({'success': False, 'error': '2FA is not enabled'}), 400

    # Require valid TOTP code to disable
    totp = pyotp.TOTP(current_user['totp_secret'])
    if not totp.verify(code, valid_window=1):
        return jsonify({'success': False, 'error': 'Invalid 2FA code'}), 401

    db = Database.get_db()
    db.users.update_one(
        {'_id': current_user['_id']},
        {'$set': {'totp_enabled': False, 'totp_secret': None}}
    )

    logger.info(f"2FA disabled for user: {current_user['username']}")
    return jsonify({'success': True, 'message': '2FA has been disabled.'})


@totp_bp.route('/api/auth/2fa/status', methods=['GET'])
@token_required
def get_2fa_status(current_user):
    """Check if 2FA is enabled for current user."""
    return jsonify({
        'success': True,
        'enabled': current_user.get('totp_enabled', False),
    })

import logging
import secrets
import random
import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file, render_template

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from models import UserFile, utcnow, format_size
from database import Database
from config import Config

logger = logging.getLogger(__name__)
share_bp = Blueprint('share', __name__)


def _get_share_collection():
    """Get the share_tokens MongoDB collection."""
    return Database.get_db().share_tokens


@share_bp.route('/api/share/generate', methods=['POST'])
@token_required
def generate_share_link(current_user):
    """Generate public shareable link with OTP, QR, expiry, downloads, message, email, schedule."""
    data = request.get_json()
    file_id = data.get('file_id')
    expiry_hours = data.get('expiry_hours', Config.SHARE_DEFAULT_EXPIRY_HOURS)
    max_downloads = data.get('max_downloads', 10)
    password = data.get('password')  # Optional password protection
    message = data.get('message', '')  # Feature #12: custom message
    notify_email = data.get('notify_email', '')  # Feature #21: email notification
    available_after = data.get('available_after')  # Feature #18: scheduled availability

    if not file_id:
        return jsonify({'success': False, 'error': 'File ID required'}), 400

    # Verify file belongs to user (IDOR protection)
    file_meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    filename = file_meta['filename']
    file_size = file_meta['size']

    # Generate unique share token
    share_token = secrets.token_urlsafe(24)

    # Generate 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Hash password if provided
    password_hash = None
    if password:
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Parse scheduled availability
    available_after_dt = None
    if available_after:
        try:
            # Simple ISO format parsing without external dependency
            from datetime import datetime
            available_after_dt = datetime.fromisoformat(available_after.replace('Z', '+00:00'))
        except Exception:
            available_after_dt = None

    # Store in MongoDB (not in-memory!)
    share_doc = {
        'token': share_token,
        'file_id': file_id,
        'user_id': str(current_user['_id']),
        'filename': filename,
        'file_size': file_size,
        'otp': otp,
        'otp_verified': False,
        'otp_attempts': 0,
        'otp_locked_until': None,
        'password_hash': password_hash,
        'message': message,  # Feature #12
        'available_after': available_after_dt,  # Feature #18
        'created_at': utcnow(),
        'expires_at': utcnow() + timedelta(hours=expiry_hours),
        'max_downloads': max_downloads,
        'download_count': 0,
        'sender_username': current_user['username'],
        'downloads': [],  # Track who downloaded when
    }

    _get_share_collection().insert_one(share_doc)

    # Create shareable link
    share_link = f"{Config.PUBLIC_URL}/share/{share_token}"
    
    # Check if using localhost (warn user)
    is_localhost = 'localhost' in Config.PUBLIC_URL or '127.0.0.1' in Config.PUBLIC_URL
    warning_message = None
    if is_localhost:
        warning_message = "⚠️ WARNING: Share link uses localhost and won't work for external users. Start ngrok or set PUBLIC_URL in .env"

    # Generate QR Code
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(share_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
        qr_code_data = f"data:image/png;base64,{qr_base64}"
    except ImportError:
        qr_code_data = None

    logger.info(f"Share link created: {filename} by {current_user['username']} (expires in {expiry_hours}h)")

    # Feature #21: Send email notification
    if notify_email:
        try:
            from services.email_service import EmailService
            EmailService.send_share_notification(
                to_email=notify_email,
                share_link=share_link,
                otp=otp,
                filename=filename,
                sender_name=current_user['username'],
                message=message,
                expires_at=str(utcnow() + timedelta(hours=expiry_hours)),
            )
        except Exception as e:
            logger.error(f"Email notification failed: {e}")

    # Log activity
    try:
        from routes.activity_routes import log_activity
        log_activity(str(current_user['_id']), 'share', {
            'filename': filename, 'token': share_token[:8],
            'email': notify_email or None,
        })
    except Exception:
        pass

    return jsonify({
        'success': True,
        'share_link': share_link,
        'share_token': share_token,
        'otp': otp,
        'qr_code': qr_code_data,
        'filename': filename,
        'file_size': file_size,
        'file_size_formatted': format_size(file_size),
        'expires_at': share_doc['expires_at'].strftime('%Y-%m-%d %H:%M:%S'),
        'max_downloads': max_downloads,
        'has_password': password_hash is not None,
        'is_localhost': is_localhost,
        'warning': warning_message,
        'message': 'Share this link and OTP with the receiver'
    })


@share_bp.route('/share/<share_token>', methods=['GET'])
def share_page(share_token):
    """Display OTP verification page."""
    share_info = _get_share_collection().find_one({'token': share_token})

    if not share_info:
        return render_template('share_error.html', error='Invalid or expired share link')

    # Check if expired
    expires_at = share_info['expires_at']
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utcnow() > expires_at:
        return render_template('share_error.html', error='This share link has expired')

    # Check download limit
    if share_info['download_count'] >= share_info['max_downloads']:
        return render_template('share_error.html', error='Download limit reached for this link')

    return render_template('share_verify.html',
                           share_token=share_token,
                           filename=share_info['filename'],
                           file_size=format_size(share_info['file_size']),
                           sender=share_info['sender_username'],
                           has_password=share_info.get('password_hash') is not None)


@share_bp.route('/api/share/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP with brute-force protection."""
    data = request.get_json()
    share_token = data.get('share_token')
    otp_entered = data.get('otp')
    password_entered = data.get('password')

    share_info = _get_share_collection().find_one({'token': share_token})

    if not share_info:
        return jsonify({'success': False, 'error': 'Invalid or expired link'}), 404

    # Check expiry
    expires_at = share_info['expires_at']
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utcnow() > expires_at:
        return jsonify({'success': False, 'error': 'Link has expired'}), 410

    # Check download limit
    if share_info['download_count'] >= share_info['max_downloads']:
        return jsonify({'success': False, 'error': 'Download limit reached'}), 410

    # Check OTP lockout
    locked_until = share_info.get('otp_locked_until')
    if locked_until:
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if utcnow() < locked_until:
            remaining = int((locked_until - utcnow()).total_seconds() / 60) + 1
            return jsonify({
                'success': False,
                'error': f'Too many attempts. Try again in {remaining} minutes.'
            }), 429

    # Check OTP attempts
    attempts = share_info.get('otp_attempts', 0)
    if attempts >= Config.OTP_MAX_ATTEMPTS:
        # Lock out
        _get_share_collection().update_one(
            {'token': share_token},
            {'$set': {
                'otp_locked_until': utcnow() + timedelta(minutes=Config.OTP_LOCKOUT_MINUTES),
                'otp_attempts': 0
            }}
        )
        return jsonify({
            'success': False,
            'error': f'Too many failed attempts. Locked for {Config.OTP_LOCKOUT_MINUTES} minutes.'
        }), 429

    # Verify OTP
    if share_info['otp'] != otp_entered:
        _get_share_collection().update_one(
            {'token': share_token},
            {'$inc': {'otp_attempts': 1}}
        )
        remaining = Config.OTP_MAX_ATTEMPTS - attempts - 1
        return jsonify({
            'success': False,
            'error': f'Invalid OTP. {remaining} attempts remaining.'
        }), 401

    # Verify password if required
    if share_info.get('password_hash'):
        if not password_entered:
            return jsonify({'success': False, 'error': 'Password required', 'needs_password': True}), 401

        import bcrypt
        if not bcrypt.checkpw(password_entered.encode('utf-8'), share_info['password_hash'].encode('utf-8')):
            return jsonify({'success': False, 'error': 'Invalid password'}), 401

    # Success — mark as verified and reset attempts
    _get_share_collection().update_one(
        {'token': share_token},
        {'$set': {'otp_verified': True, 'otp_attempts': 0}}
    )

    return jsonify({
        'success': True,
        'message': 'Verified! Download will start...',
        'download_url': f"/share/{share_token}/download"
    })


@share_bp.route('/share/<share_token>/download', methods=['GET'])
def download_shared_file(share_token):
    """Download file after OTP verification with download counting."""
    share_info = _get_share_collection().find_one({'token': share_token})

    if not share_info:
        return jsonify({'success': False, 'error': 'Invalid or expired link'}), 404

    # Check OTP verification
    if not share_info.get('otp_verified'):
        return jsonify({'success': False, 'error': 'OTP verification required'}), 403

    # Check expiry
    expires_at = share_info['expires_at']
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if utcnow() > expires_at:
        return jsonify({'success': False, 'error': 'Link has expired'}), 410

    # Check download limit
    if share_info['download_count'] >= share_info['max_downloads']:
        return jsonify({'success': False, 'error': 'Download limit reached'}), 410

    file_id = share_info['file_id']

    try:
        # Resolve file metadata to support both MinIO and GridFS backends
        from database import Database
        from bson import ObjectId
        file_meta = Database.get_db().user_files.find_one({'_id': ObjectId(file_id)})

        if not file_meta:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        file_stream = UserFile.get_file_stream(file_meta)

        # Increment download count and reset OTP verification
        _get_share_collection().update_one(
            {'token': share_token},
            {
                '$inc': {'download_count': 1},
                '$push': {'downloads': {
                    'timestamp': utcnow(),
                    'ip': request.remote_addr,
                }},
                '$set': {'otp_verified': False}
            }
        )

        logger.info(f"File downloaded via share: {share_info['filename']} (token: {share_token[:8]}...)")

        if file_stream['type'] == 'presigned_url':
            from flask import redirect
            return redirect(file_stream['url'])

        return jsonify({'success': False, 'error': 'File not available'}), 404
    except Exception as e:
        logger.error(f"Share download error: {e}")
        return jsonify({'success': False, 'error': 'File not found or unavailable'}), 404


@share_bp.route('/api/share/revoke/<share_token>', methods=['DELETE'])
@token_required
def revoke_share_link(current_user, share_token):
    """Revoke a share link."""
    result = _get_share_collection().delete_one({
        'token': share_token,
        'user_id': str(current_user['_id'])
    })

    if result.deleted_count > 0:
        logger.info(f"Share link revoked: {share_token[:8]}... by {current_user['username']}")
        return jsonify({'success': True, 'message': 'Link revoked'})

    return jsonify({'success': False, 'error': 'Link not found'}), 404


@share_bp.route('/api/share/active', methods=['GET'])
@token_required
def get_active_shares(current_user):
    """Get all active share links for current user."""
    shares = list(_get_share_collection().find({
        'user_id': str(current_user['_id']),
        'expires_at': {'$gt': utcnow()}
    }).sort('created_at', -1))

    result = []
    for s in shares:
        result.append({
            'token': s['token'],
            'filename': s['filename'],
            'file_size_formatted': format_size(s['file_size']),
            'otp': s['otp'],
            'link': f"{Config.PUBLIC_URL}/share/{s['token']}",
            'created_at': s['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'expires_at': s['expires_at'].strftime('%Y-%m-%d %H:%M:%S'),
            'download_count': s['download_count'],
            'max_downloads': s['max_downloads'],
            'has_password': s.get('password_hash') is not None,
            'message': s.get('message', ''),
        })

    return jsonify({
        'success': True,
        'shares': result,
        'count': len(result)
    })


# Feature #14: Share Analytics
@share_bp.route('/api/share/analytics/<share_token>', methods=['GET'])
@token_required
def share_analytics(current_user, share_token):
    """Get detailed download analytics for a share link."""
    share = _get_share_collection().find_one({
        'token': share_token,
        'user_id': str(current_user['_id'])
    })

    if not share:
        return jsonify({'success': False, 'error': 'Share not found'}), 404

    downloads = share.get('downloads', [])
    for d in downloads:
        if 'timestamp' in d and hasattr(d['timestamp'], 'isoformat'):
            d['timestamp'] = d['timestamp'].isoformat()

    return jsonify({
        'success': True,
        'token': share_token,
        'filename': share['filename'],
        'download_count': share['download_count'],
        'max_downloads': share['max_downloads'],
        'created_at': share['created_at'].isoformat(),
        'expires_at': share['expires_at'].isoformat(),
        'message': share.get('message', ''),
        'downloads': downloads,
    })

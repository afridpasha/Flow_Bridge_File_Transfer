"""
CodeShare Routes - Real-time collaborative code sharing API
"""

import logging
import base64
from io import BytesIO
from flask import Blueprint, request, jsonify, render_template
from config import Config

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from models_codeshare import CodeShare
from middleware.auth_middleware import token_required

logger = logging.getLogger(__name__)
codeshare_bp = Blueprint('codeshare', __name__)


# ===== Public Routes (No Auth Required) =====

@codeshare_bp.route('/api/codeshare/create', methods=['POST'])
def create_codeshare():
    """Create a new code share session (public or authenticated)."""
    data = request.get_json() or {}
    
    code = data.get('code', '')
    language = data.get('language', 'python')
    title = data.get('title', 'Untitled')
    custom_slug = data.get('custom_slug')
    expiry_hours = data.get('expiry_hours')
    allow_edit = data.get('allow_edit', True)
    
    # Get creator info (if authenticated)
    creator_id = None
    creator_name = data.get('creator_name', 'Anonymous')
    
    # Check if user is authenticated
    token = request.headers.get('Authorization')
    if token:
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            import jwt
            from models import User
            payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
            user = User.find_by_id(payload['user_id'])
            if user:
                creator_id = str(user['_id'])
                creator_name = user['username']
        except Exception:
            pass  # Continue as anonymous

    try:
        doc = CodeShare.create(
            code=code,
            language=language,
            title=title,
            custom_slug=custom_slug,
            creator_id=creator_id,
            creator_name=creator_name,
            expiry_hours=expiry_hours,
            allow_edit=allow_edit
        )
        
        share_url = f"{Config.PUBLIC_URL}/code/{doc['slug']}"
        
        # Generate QR code
        qr_code_data = None
        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(share_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_buffer = BytesIO()
            qr_img.save(qr_buffer, format='PNG')
            qr_buffer.seek(0)
            qr_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
            qr_code_data = f"data:image/png;base64,{qr_base64}"
        except Exception as e:
            logger.warning(f"QR code generation failed: {e}")
        
        return jsonify({
            'success': True,
            'slug': doc['slug'],
            'share_url': share_url,
            'qr_code': qr_code_data,
            'title': doc['title'],
            'language': doc['language'],
            'allow_edit': doc['allow_edit'],
            'expires_at': doc['expires_at'].isoformat() if doc.get('expires_at') else None,
            'message': 'Code share created! Anyone with the link can view and edit.'
        })
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"CodeShare creation error: {e}")
        return jsonify({'success': False, 'error': 'Failed to create code share'}), 500


@codeshare_bp.route('/api/codeshare/<slug>', methods=['GET'])
def get_codeshare(slug):
    """Get code share by slug (public access)."""
    try:
        doc = CodeShare.get_by_slug(slug)
        
        if not doc:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
        
        # Check if expired
        if doc.get('expires_at'):
            from models_codeshare import utcnow
            from datetime import timezone
            expires_at = doc['expires_at']
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if utcnow() > expires_at:
                return jsonify({'success': False, 'error': 'This code share has expired'}), 410
        
        return jsonify({
            'success': True,
            'slug': doc['slug'],
            'title': doc['title'],
            'code': doc['code'],
            'language': doc['language'],
            'creator_name': doc['creator_name'],
            'allow_edit': doc.get('allow_edit', True),
            'is_public': doc.get('is_public', True),
            'created_at': doc['created_at'].isoformat() if doc.get('created_at') else None,
            'updated_at': doc['updated_at'].isoformat() if doc.get('updated_at') else None,
            'expires_at': doc['expires_at'].isoformat() if doc.get('expires_at') else None,
            'view_count': doc.get('view_count', 0),
            'edit_count': doc.get('edit_count', 0),
            'active_users': doc.get('active_users', []),
            'collaborators': doc.get('collaborators', []),
        })
    
    except Exception as e:
        logger.error(f"Get codeshare error: {e}")
        return jsonify({'success': False, 'error': 'Failed to load code share'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/update', methods=['POST'])
def update_codeshare(slug):
    """Update code content (public access if editing allowed)."""
    data = request.get_json() or {}
    
    code = data.get('code', '')
    editor_name = data.get('editor_name', 'Anonymous')
    save_version = data.get('save_version', False)
    
    try:
        success = CodeShare.update_code(slug, code, editor_name, save_version)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Code updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
    
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Update codeshare error: {e}")
        return jsonify({'success': False, 'error': 'Failed to update code'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/settings', methods=['PUT'])
def update_settings(slug):
    """Update code share settings."""
    data = request.get_json() or {}
    
    try:
        success = CodeShare.update_settings(
            slug=slug,
            title=data.get('title'),
            language=data.get('language'),
            allow_edit=data.get('allow_edit'),
            expiry_hours=data.get('expiry_hours')
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Settings updated'})
        else:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
    
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        return jsonify({'success': False, 'error': 'Failed to update settings'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/history', methods=['GET'])
def get_history(slug):
    """Get version history."""
    try:
        history = CodeShare.get_version_history(slug)
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        logger.error(f"Get history error: {e}")
        return jsonify({'success': False, 'error': 'Failed to load history'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/stats', methods=['GET'])
def get_stats(slug):
    """Get statistics."""
    try:
        stats = CodeShare.get_stats(slug)
        if not stats:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return jsonify({'success': False, 'error': 'Failed to load stats'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/download', methods=['GET'])
def download_code(slug):
    """Download code as file."""
    try:
        doc = CodeShare.get_by_slug(slug)
        if not doc:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
        
        code = doc['code']
        language = doc['language']
        title = doc['title']
        
        # Determine file extension
        ext_map = {
            'python': 'py', 'javascript': 'js', 'typescript': 'ts',
            'java': 'java', 'cpp': 'cpp', 'c': 'c', 'csharp': 'cs',
            'go': 'go', 'rust': 'rs', 'php': 'php', 'ruby': 'rb',
            'swift': 'swift', 'kotlin': 'kt', 'html': 'html',
            'css': 'css', 'sql': 'sql', 'bash': 'sh', 'json': 'json',
            'xml': 'xml', 'yaml': 'yaml', 'markdown': 'md'
        }
        ext = ext_map.get(language, 'txt')
        filename = f"{title.replace(' ', '_')}.{ext}"
        
        from flask import Response
        return Response(
            code,
            mimetype='text/plain',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({'success': False, 'error': 'Failed to download'}), 500


@codeshare_bp.route('/api/codeshare/<slug>/delete', methods=['DELETE'])
def delete_codeshare(slug):
    """Delete code share (requires creator authentication or admin)."""
    # TODO: Add authentication check for creator
    try:
        success = CodeShare.delete(slug)
        if success:
            return jsonify({'success': True, 'message': 'Code share deleted'})
        else:
            return jsonify({'success': False, 'error': 'Code share not found'}), 404
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'success': False, 'error': 'Failed to delete'}), 500


# ===== Authenticated Routes =====

@codeshare_bp.route('/api/codeshare/my-shares', methods=['GET'])
@token_required
def get_my_shares(current_user):
    """Get all code shares created by current user."""
    try:
        shares = CodeShare.get_user_codeshares(str(current_user['_id']))
        return jsonify({
            'success': True,
            'shares': shares,
            'count': len(shares)
        })
    except Exception as e:
        logger.error(f"Get my shares error: {e}")
        return jsonify({'success': False, 'error': 'Failed to load shares'}), 500


# ===== Cleanup Task =====

@codeshare_bp.route('/api/codeshare/cleanup', methods=['POST'])
def cleanup_expired():
    """Cleanup expired code shares (admin only or cron job)."""
    # TODO: Add admin authentication
    try:
        count = CodeShare.cleanup_expired()
        return jsonify({
            'success': True,
            'deleted_count': count,
            'message': f'Cleaned up {count} expired code shares'
        })
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
        return jsonify({'success': False, 'error': 'Cleanup failed'}), 500


# ===== Page Routes =====

@codeshare_bp.route('/code/<slug>')
def codeshare_page(slug):
    """Render code share page."""
    return render_template('codeshare.html', slug=slug)


@codeshare_bp.route('/codeshare')
def codeshare_home():
    """Render code share home/create page."""
    return render_template('codeshare_create.html')

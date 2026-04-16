import logging
from flask import Blueprint, request, jsonify
from io import BytesIO

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from models import UserFile, Folder, format_size, compute_checksum, get_file_extension
from config import Config
from database import Database

logger = logging.getLogger(__name__)
user_file_bp = Blueprint('user_files', __name__)


@user_file_bp.route('/api/user/files', methods=['GET'])
@token_required
def get_user_files(current_user):
    """Get all files for logged-in user with search, sort, and folder support."""
    folder_id = request.args.get('folder_id')
    search = request.args.get('search')
    sort_by = request.args.get('sort_by', 'uploaded_at')
    sort_order = int(request.args.get('sort_order', -1))

    files = UserFile.get_user_files(
        current_user['_id'],
        folder_id=folder_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )

    folders = Folder.get_folders(str(current_user['_id']), parent_id=folder_id)

    return jsonify({
        'success': True,
        'files': files,
        'folders': folders,
        'count': len(files),
        'folder_count': len(folders),
        'storage_used': current_user.get('storage_used', 0),
        'storage_quota': current_user.get('storage_quota', 500 * 1024 * 1024),
        'storage_used_formatted': format_size(current_user.get('storage_used', 0)),
        'storage_quota_formatted': format_size(current_user.get('storage_quota', 500 * 1024 * 1024)),
    })


@user_file_bp.route('/api/user/upload', methods=['POST'])
@token_required
def upload_user_file(current_user):
    """Upload file(s) with validation, checksum, and duplicate detection."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    uploaded_files = request.files.getlist('file')
    results = []
    errors = []

    for file in uploaded_files:
        if not file.filename or file.filename == '':
            continue

        try:
            file_data = file.read()
            file_size = len(file_data)

            if file_size == 0:
                errors.append(f"{file.filename}: File is empty")
                continue

            # Check for duplicates
            checksum = compute_checksum(file_data)
            duplicate = UserFile.check_duplicate(str(current_user['_id']), checksum)
            if duplicate:
                errors.append(f"{file.filename}: Duplicate of '{duplicate['filename']}' (same content)")
                continue

            # Store in MongoDB
            folder_id = request.form.get('folder_id')
            file_id = UserFile.create(
                current_user['_id'],
                file.filename,
                file_data,
                file_size,
                file.content_type or 'application/octet-stream'
            )

            # Move to folder if specified
            if folder_id:
                from database import Database
                db = Database.get_db()
                from bson import ObjectId as OID
                db.user_files.update_one(
                    {"_id": OID(file_id)},
                    {"$set": {"folder_id": folder_id}}
                )

            results.append({
                'file_id': file_id,
                'filename': file.filename,
                'size': file_size,
                'size_formatted': format_size(file_size),
                'checksum': checksum,
            })

        except ValueError as e:
            errors.append(f"{file.filename}: {str(e)}")
        except Exception as e:
            logger.error(f"Upload error for {file.filename}: {e}")
            errors.append(f"{file.filename}: Upload failed")

    return jsonify({
        'success': len(results) > 0,
        'uploaded': results,
        'errors': errors,
        'count': len(results),
    })


@user_file_bp.route('/api/user/download/<file_id>', methods=['GET'])
@token_required
def download_user_file(current_user, file_id):
    """Download file with ownership verification - supports R2 presigned URLs."""
    try:
        # Verify ownership (prevents IDOR)
        file_meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
        if not file_meta:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Get file stream (R2 presigned URL or GridFS stream)
        file_stream = UserFile.get_file_stream(file_meta)
        
        if file_stream['type'] == 'presigned_url':
            from flask import redirect
            return redirect(file_stream['url'])

        return jsonify({'success': False, 'error': 'File not available'}), 404
    except Exception as e:
        logger.error(f"Download error for file {file_id}: {e}")
        return jsonify({'success': False, 'error': 'File not found or unavailable'}), 404


@user_file_bp.route('/api/user/preview/<file_id>', methods=['GET'])
def preview_file_public(file_id):
    """Preview file content (images, text, etc.) - supports token in query param for img/video tags."""
    # Try to get token from Authorization header first, then from query param
    token = request.headers.get('Authorization')
    if token and token.startswith('Bearer '):
        token = token[7:]
    else:
        token = request.args.get('token')
    
    if not token:
        return jsonify({'success': False, 'error': 'Unauthorized - No token provided'}), 401
    
    # Verify token
    try:
        import jwt
        from models import User
        from config import Config
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        user = User.find_by_id(payload['user_id'])
        if not user:
            return jsonify({'success': False, 'error': 'Invalid token - User not found'}), 401
        current_user = user
    except jwt.ExpiredSignatureError:
        return jsonify({'success': False, 'error': 'Token expired'}), 401
    except jwt.InvalidTokenError as e:
        logger.error(f"Token verification failed: {e}")
        return jsonify({'success': False, 'error': 'Invalid token'}), 401
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return jsonify({'success': False, 'error': 'Authentication failed'}), 401
    
    try:
        # Try to get file metadata - the file_id parameter could be either _id or file_id
        # First try as _id (document ID)
        from bson import ObjectId as OID
        from bson.errors import InvalidId
        
        file_meta = None
        try:
            file_meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
        except InvalidId:
            pass
        
        if not file_meta:
            return jsonify({'success': False, 'error': 'File not found or access denied'}), 404

        ext = get_file_extension(file_meta['filename'])
        storage_backend = file_meta.get('storage_backend', 'r2')

        # Handle text files
        if ext in Config.PREVIEWABLE_TEXT:
            file_bytes = UserFile.get_file_bytes(file_meta)
            if not file_bytes:
                return jsonify({'success': False, 'error': 'File not found in storage'}), 404
            content = file_bytes.decode('utf-8', errors='replace')[:50000]
            return jsonify({
                'success': True, 'type': 'text',
                'content': content, 'filename': file_meta['filename']
            })

        # Handle images, videos, audio, PDFs
        if ext in Config.PREVIEWABLE_IMAGES or ext in Config.PREVIEWABLE_VIDEO \
                or ext in Config.PREVIEWABLE_AUDIO or ext == 'pdf':
            from flask import send_file
            file_bytes = UserFile.get_file_bytes(file_meta)
            if not file_bytes:
                return jsonify({'success': False, 'error': 'File not found in storage'}), 404
            return send_file(
                BytesIO(file_bytes),
                mimetype=file_meta.get('content_type', 'application/octet-stream'),
                download_name=file_meta['filename']
            )

        return jsonify({'success': False, 'error': f'Preview not available for .{ext} files'}), 400

    except Exception as e:
        logger.error(f"Preview error for file {file_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'Preview failed: {str(e)}'}), 500


@user_file_bp.route('/api/user/delete/<file_id>', methods=['DELETE'])
@token_required
def delete_user_file(current_user, file_id):
    """Soft-delete file (move to trash) with ownership check."""
    permanent = request.args.get('permanent', 'false').lower() == 'true'
    success = UserFile.delete_file(file_id, str(current_user['_id']), soft=not permanent)

    if success:
        return jsonify({'success': True, 'message': 'File moved to trash' if not permanent else 'File permanently deleted'})
    return jsonify({'success': False, 'error': 'File not found'}), 404


@user_file_bp.route('/api/user/restore/<file_id>', methods=['POST'])
@token_required
def restore_file(current_user, file_id):
    """Restore file from trash."""
    success = UserFile.restore_file(file_id, str(current_user['_id']))
    if success:
        return jsonify({'success': True, 'message': 'File restored'})
    return jsonify({'success': False, 'error': 'File not found in trash'}), 404


@user_file_bp.route('/api/user/trash', methods=['GET'])
@token_required
def get_trash(current_user):
    """Get trashed files."""
    files = UserFile.get_trash(str(current_user['_id']))
    return jsonify({'success': True, 'files': files, 'count': len(files)})


@user_file_bp.route('/api/user/file/<file_id>/info', methods=['GET'])
@token_required
def get_file_info(current_user, file_id):
    """Get file info with ownership verification."""
    file_meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    return jsonify({
        'success': True,
        'filename': file_meta['filename'],
        'size': file_meta['size'],
        'size_formatted': format_size(file_meta['size']),
        'file_id': str(file_meta['_id']),
        'content_type': file_meta.get('content_type', ''),
        'checksum': file_meta.get('checksum', ''),
        'uploaded_at': file_meta['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(file_meta.get('uploaded_at', ''), 'strftime') else str(file_meta.get('uploaded_at', '')),
        'tags': file_meta.get('tags', []),
    })


@user_file_bp.route('/api/user/file/<file_id>/tags', methods=['POST'])
@token_required
def update_tags(current_user, file_id):
    """Add tags to a file."""
    data = request.get_json()
    tags = data.get('tags', [])
    if not tags:
        return jsonify({'success': False, 'error': 'Tags required'}), 400

    success = UserFile.add_tags(file_id, str(current_user['_id']), tags)
    if success:
        return jsonify({'success': True, 'message': 'Tags added'})
    return jsonify({'success': False, 'error': 'File not found'}), 404


@user_file_bp.route('/api/user/file/<file_id>/tags/<tag>', methods=['DELETE'])
@token_required
def remove_tag(current_user, file_id, tag):
    """Remove a tag from a file."""
    success = UserFile.remove_tag(file_id, str(current_user['_id']), tag)
    if success:
        return jsonify({'success': True, 'message': 'Tag removed'})
    return jsonify({'success': False, 'error': 'File or tag not found'}), 404


@user_file_bp.route('/api/user/folders', methods=['POST'])
@token_required
def create_folder(current_user):
    """Create a new folder."""
    data = request.get_json()
    name = (data.get('name') or '').strip()
    parent_id = data.get('parent_id')

    if not name:
        return jsonify({'success': False, 'error': 'Folder name required'}), 400

    folder_id = Folder.create(str(current_user['_id']), name, parent_id)
    return jsonify({'success': True, 'folder_id': folder_id, 'message': 'Folder created'})


@user_file_bp.route('/api/user/folders/<folder_id>', methods=['DELETE'])
@token_required
def delete_folder(current_user, folder_id):
    """Delete a folder."""
    success = Folder.delete(folder_id, str(current_user['_id']))
    if success:
        return jsonify({'success': True, 'message': 'Folder deleted'})
    return jsonify({'success': False, 'error': 'Folder not found'}), 404


@user_file_bp.route('/api/user/folders/<folder_id>/rename', methods=['PUT'])
@token_required
def rename_folder(current_user, folder_id):
    """Rename a folder."""
    data = request.get_json()
    new_name = (data.get('name') or '').strip()
    if not new_name:
        return jsonify({'success': False, 'error': 'New name required'}), 400

    success = Folder.rename(folder_id, str(current_user['_id']), new_name)
    if success:
        return jsonify({'success': True, 'message': 'Folder renamed'})
    return jsonify({'success': False, 'error': 'Folder not found'}), 404





@user_file_bp.route('/api/user/bulk-delete', methods=['POST'])
@token_required
def bulk_delete(current_user):
    """Bulk delete multiple files."""
    data = request.get_json()
    file_ids = data.get('file_ids', [])
    if not file_ids:
        return jsonify({'success': False, 'error': 'No files specified'}), 400

    deleted = 0
    for fid in file_ids:
        if UserFile.delete_file(fid, str(current_user['_id']), soft=True):
            deleted += 1

    return jsonify({
        'success': True,
        'message': f'{deleted} files moved to trash',
        'deleted': deleted
    })


# ===== Feature #23: File Rename =====
@user_file_bp.route('/api/user/files/<file_id>/rename', methods=['PATCH'])
@token_required
def rename_file(current_user, file_id):
    """Rename a file."""
    data = request.get_json()
    new_name = data.get('new_name', '').strip()

    if not new_name:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    from database import Database
    from bson import ObjectId as OID
    db = Database.get_db()

    result = db.user_files.update_one(
        {"_id": OID(file_id), "user_id": str(current_user['_id'])},
        {"$set": {"filename": new_name}}
    )

    if result.modified_count > 0:
        _log_activity(current_user, 'rename', {'file_id': file_id, 'new_name': new_name})
        return jsonify({'success': True, 'message': f'Renamed to {new_name}'})
    return jsonify({'success': False, 'error': 'File not found'}), 404


# ===== Feature #24: Move File =====
@user_file_bp.route('/api/user/file/<file_id>/move', methods=['PUT', 'PATCH'])
@token_required
def move_file(current_user, file_id):
    """Move file to a different folder."""
    data = request.get_json()
    folder_id = data.get('folder_id')  # None = root

    from database import Database
    from bson import ObjectId as OID
    db = Database.get_db()
    result = db.user_files.update_one(
        {"_id": OID(file_id), "user_id": str(current_user['_id'])},
        {"$set": {"folder_id": folder_id}}
    )

    if result.modified_count > 0:
        _log_activity(current_user, 'move', {'file_id': file_id, 'folder_id': folder_id})
        return jsonify({'success': True, 'message': 'File moved'})
    return jsonify({'success': False, 'error': 'File not found'}), 404


# ===== Feature #19: File Comments =====
@user_file_bp.route('/api/user/files/<file_id>/comments', methods=['POST'])
@token_required
def add_comment(current_user, file_id):
    """Add a comment to a file."""
    data = request.get_json()
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'success': False, 'error': 'Comment text required'}), 400

    if len(text) > 1000:
        return jsonify({'success': False, 'error': 'Comment too long (max 1000 chars)'}), 400

    from database import Database
    from bson import ObjectId as OID
    from datetime import datetime, timezone
    db = Database.get_db()

    # Verify file ownership
    file_meta = db.user_files.find_one({
        "_id": OID(file_id),
        "user_id": str(current_user['_id'])
    })
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    comment = {
        'user': current_user['username'],
        'text': text,
        'timestamp': datetime.now(timezone.utc),
    }

    db.user_files.update_one(
        {"_id": OID(file_id)},
        {"$push": {"comments": comment}}
    )

    _log_activity(current_user, 'comment', {'file_id': file_id})
    return jsonify({'success': True, 'message': 'Comment added'})


@user_file_bp.route('/api/user/files/<file_id>/comments', methods=['GET'])
@token_required
def get_comments(current_user, file_id):
    """Get all comments for a file."""
    from database import Database
    from bson import ObjectId as OID
    db = Database.get_db()

    file_meta = db.user_files.find_one({
        "_id": OID(file_id),
        "user_id": str(current_user['_id'])
    })
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    comments = file_meta.get('comments', [])
    for c in comments:
        if 'timestamp' in c:
            c['timestamp'] = c['timestamp'].isoformat()

    return jsonify({'success': True, 'comments': comments})


# ===== Feature #11: Version History =====
@user_file_bp.route('/api/user/versions/<file_id>', methods=['GET'])
@token_required
def get_versions(current_user, file_id):
    """Get version history for a file."""
    from database import Database
    from bson import ObjectId as OID
    db = Database.get_db()

    file_meta = db.user_files.find_one({
        "_id": OID(file_id),
        "user_id": str(current_user['_id'])
    })
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    # Find all versions (same filename, same user)
    versions = list(db.user_files.find(
        {
            "filename": file_meta['filename'],
            "user_id": str(current_user['_id']),
        },
        sort=[("uploaded_at", -1)]
    ))

    result = []
    for v in versions:
        result.append({
            'file_id': str(v['_id']),
            'filename': v['filename'],
            'size_formatted': format_size(v.get('size', 0)),
            'uploaded_at': v.get('uploaded_at', '').isoformat() if hasattr(v.get('uploaded_at', ''), 'isoformat') else str(v.get('uploaded_at', '')),
            'version': v.get('version', 1),
            'checksum': v.get('checksum', ''),
        })

    return jsonify({'success': True, 'versions': result, 'count': len(result)})



# ===== Helper: Activity Logging =====
def _log_activity(user, action, details=None):
    """Log activity for the user."""
    try:
        from routes.activity_routes import log_activity
        log_activity(str(user['_id']), action, details)
    except Exception:
        pass

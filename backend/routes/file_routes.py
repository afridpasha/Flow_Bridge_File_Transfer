import logging
from flask import Blueprint, jsonify, send_file, request
import os, sys
from werkzeug.utils import secure_filename

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import Config
from services.file_service import FileService
from middleware.auth_middleware import token_required

logger = logging.getLogger(__name__)
file_bp = Blueprint('files', __name__)


@file_bp.route('/api/files', methods=['GET'])
@token_required
def get_files(current_user):
    """Get list of local files (requires authentication)."""
    folder = request.args.get('folder', 'shared')

    folder_map = {
        'shared': Config.SHARED_FOLDER,
        'uploads': Config.UPLOAD_FOLDER,
        'downloads': Config.DOWNLOAD_FOLDER
    }

    folder_path = folder_map.get(folder, Config.SHARED_FOLDER)
    files = FileService.get_file_list(folder_path)

    return jsonify({
        'success': True,
        'folder': folder,
        'files': files,
        'count': len(files)
    })


@file_bp.route('/api/download/<folder>/<filename>', methods=['GET'])
@token_required
def download_file(current_user, folder, filename):
    """Download a specific local file (requires authentication)."""
    folder_map = {
        'shared': Config.SHARED_FOLDER,
        'uploads': Config.UPLOAD_FOLDER,
        'downloads': Config.DOWNLOAD_FOLDER
    }

    folder_path = folder_map.get(folder, Config.SHARED_FOLDER)
    safe_filename = secure_filename(filename)
    filepath = os.path.join(folder_path, safe_filename)

    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    # Prevent path traversal
    real_path = os.path.realpath(filepath)
    real_folder = os.path.realpath(folder_path)
    if not real_path.startswith(real_folder):
        logger.warning(f"Path traversal attempt: {filename}")
        return jsonify({'success': False, 'error': 'Invalid file path'}), 400

    return send_file(filepath, as_attachment=True, download_name=safe_filename)


@file_bp.route('/api/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    """Upload file(s) to local storage (requires authentication)."""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400

    files = request.files.getlist('files')
    uploaded = []

    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
            file.save(filepath)
            uploaded.append(filename)
            logger.info(f"Local file uploaded: {filename}")

    return jsonify({
        'success': True,
        'uploaded': uploaded,
        'count': len(uploaded)
    })


@file_bp.route('/api/delete/<folder>/<filename>', methods=['DELETE'])
@token_required
def delete_file(current_user, folder, filename):
    """Delete a local file (requires authentication)."""
    folder_map = {
        'shared': Config.SHARED_FOLDER,
        'uploads': Config.UPLOAD_FOLDER,
        'downloads': Config.DOWNLOAD_FOLDER
    }

    folder_path = folder_map.get(folder, Config.SHARED_FOLDER)
    safe_filename = secure_filename(filename)
    filepath = os.path.join(folder_path, safe_filename)

    # Path traversal protection
    real_path = os.path.realpath(filepath)
    real_folder = os.path.realpath(folder_path)
    if not real_path.startswith(real_folder):
        return jsonify({'success': False, 'error': 'Invalid file path'}), 400

    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    try:
        os.remove(filepath)
        logger.info(f"Local file deleted: {filename}")
        return jsonify({'success': True, 'message': 'File deleted'})
    except OSError as e:
        logger.error(f"File delete error: {e}")
        return jsonify({'success': False, 'error': 'Could not delete file'}), 500


@file_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Get storage statistics."""
    stats = FileService.get_storage_stats()
    return jsonify({
        'success': True,
        'stats': stats
    })

"""ZIP download routes for FlowBridge — batch download multiple files."""

import logging
import zipfile
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from models import UserFile

logger = logging.getLogger(__name__)
zip_bp = Blueprint('zip', __name__)


@zip_bp.route('/api/user/download-zip', methods=['POST'])
@token_required
def download_as_zip(current_user):
    """Download multiple files as a single ZIP archive."""
    data = request.get_json()
    file_ids = data.get('file_ids', [])

    if not file_ids:
        return jsonify({'success': False, 'error': 'No files selected'}), 400

    if len(file_ids) > 50:
        return jsonify({'success': False, 'error': 'Maximum 50 files per ZIP'}), 400

    try:
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_id in file_ids:
                meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
                if not meta:
                    continue

                file_bytes = UserFile.get_file_bytes(meta)
                if file_bytes:
                    zf.writestr(meta['filename'], file_bytes)

        zip_buffer.seek(0)

        logger.info(f"ZIP download: {len(file_ids)} files for user {current_user['username']}")

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'flowbridge_{len(file_ids)}_files.zip'
        )

    except Exception as e:
        logger.error(f"ZIP download error: {e}")
        return jsonify({'success': False, 'error': 'Failed to create ZIP'}), 500

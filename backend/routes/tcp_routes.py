import logging
import threading
from flask import Blueprint, request, jsonify

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from models import UserFile
from tcp_sender import TCPSender

logger = logging.getLogger(__name__)
tcp_bp = Blueprint('tcp', __name__)


@tcp_bp.route('/api/tcp/send', methods=['POST'])
@token_required
def send_file_tcp(current_user):
    """Send file via TCP to a receiver with ownership verification."""
    data = request.get_json()
    file_id = data.get('file_id')
    receiver_ip = data.get('receiver_ip')
    receiver_port = data.get('receiver_port', 5555)

    if not file_id:
        return jsonify({'success': False, 'error': 'File ID required'}), 400
    if not receiver_ip:
        return jsonify({'success': False, 'error': 'Receiver IP required'}), 400

    # Validate IP format (basic)
    parts = receiver_ip.split('.')
    if len(parts) != 4:
        return jsonify({'success': False, 'error': 'Invalid IP address format'}), 400

    # Verify file ownership (IDOR protection)
    file_meta = UserFile.get_file_meta(file_id, str(current_user['_id']))
    if not file_meta:
        return jsonify({'success': False, 'error': 'File not found'}), 404

    try:
        file_bytes = UserFile.get_file_bytes(file_meta)
        if not file_bytes:
            return jsonify({'success': False, 'error': 'File data unavailable'}), 404
        filename = file_meta['filename']

        sender = TCPSender(receiver_ip, receiver_port)

        def do_send():
            result = sender.send_file(filename, file_bytes)
            if result['success']:
                logger.info(f"TCP send complete: {filename} to {receiver_ip}")
            else:
                logger.error(f"TCP send failed: {filename} to {receiver_ip}: {result.get('error')}")

        threading.Thread(target=do_send, daemon=True).start()

        return jsonify({
            'success': True,
            'message': f'Transfer started: {filename} → {receiver_ip}:{receiver_port}',
            'filename': filename,
        })

    except Exception as e:
        logger.error(f"TCP send setup error: {e}")
        return jsonify({'success': False, 'error': 'Failed to start transfer'}), 500

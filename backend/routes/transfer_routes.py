import logging
from flask import Blueprint, jsonify
import os, sys, socket

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from services.transfer_service import TransferService
from config import Config

logger = logging.getLogger(__name__)
transfer_bp = Blueprint('transfers', __name__)


@transfer_bp.route('/api/transfers/active', methods=['GET'])
def get_active_transfers():
    """Get all active transfers."""
    transfers = TransferService.get_active_transfers()
    return jsonify({
        'success': True,
        'transfers': transfers,
        'count': len(transfers)
    })


@transfer_bp.route('/api/transfers/history', methods=['GET'])
def get_transfer_history():
    """Get transfer history from database."""
    history = TransferService.get_transfer_history(limit=20)
    return jsonify({
        'success': True,
        'history': history,
        'count': len(history)
    })


@transfer_bp.route('/api/network', methods=['GET'])
def get_network_info():
    """Get network information."""
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        local_ip = '127.0.0.1'

    return jsonify({
        'success': True,
        'hostname': hostname,
        'local_ip': local_ip,
        'http_port': Config.HTTP_PORT,
        'tcp_port': Config.TCP_PORT,
        'public_url': Config.PUBLIC_URL or '',
    })

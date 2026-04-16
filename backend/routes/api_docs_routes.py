"""API Documentation route for FlowBridge."""

import logging
from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)
api_docs_bp = Blueprint('api_docs', __name__)


@api_docs_bp.route('/api/docs', methods=['GET'])
def api_documentation():
    """Return complete API documentation."""
    return jsonify({
        'name': 'FlowBridge API',
        'version': '3.0.0',
        'description': 'Hybrid file transfer system with E2E encryption, 2FA, and room-based transfers.',
        'base_url': '/api',
        'authentication': 'Bearer token in Authorization header',
        'endpoints': {
            'auth': {
                'POST /api/auth/signup': {
                    'desc': 'Create new account',
                    'body': {'username': 'str', 'email': 'str', 'password': 'str'},
                    'rate_limit': '3/min',
                },
                'POST /api/auth/login': {
                    'desc': 'Login (returns JWT or 2FA challenge)',
                    'body': {'username': 'str', 'password': 'str'},
                    'rate_limit': '5/min',
                },
                'POST /api/auth/refresh': {
                    'desc': 'Refresh access token',
                    'body': {'refresh_token': 'str'},
                },
                'GET /api/auth/verify': {
                    'desc': 'Verify current token is valid',
                    'auth': True,
                },
            },
            '2fa': {
                'POST /api/auth/2fa/setup': {
                    'desc': 'Generate TOTP secret + QR code',
                    'auth': True,
                },
                'POST /api/auth/2fa/verify-setup': {
                    'desc': 'Verify code to enable 2FA',
                    'auth': True,
                    'body': {'code': '6-digit TOTP'},
                },
                'POST /api/auth/2fa/validate': {
                    'desc': 'Validate 2FA during login',
                    'body': {'user_id': 'str', 'code': '6-digit TOTP'},
                },
                'POST /api/auth/2fa/disable': {
                    'desc': 'Disable 2FA',
                    'auth': True,
                    'body': {'code': '6-digit TOTP'},
                },
                'GET /api/auth/2fa/status': {
                    'desc': 'Check if 2FA is enabled',
                    'auth': True,
                },
            },
            'files': {
                'GET /api/user/files': {
                    'desc': 'List files with search, sort, folder filter',
                    'auth': True,
                    'params': {'search': 'str', 'sort_by': 'filename|size|uploaded_at', 'sort_order': '1|-1', 'folder_id': 'str'},
                },
                'POST /api/user/upload': {
                    'desc': 'Upload file(s)',
                    'auth': True,
                    'body': 'multipart/form-data with file field',
                    'rate_limit': '20/min',
                },
                'GET /api/user/download/<file_id>': {
                    'desc': 'Download a file',
                    'auth': True,
                },
                'DELETE /api/user/delete/<file_id>': {
                    'desc': 'Soft-delete file (moves to trash)',
                    'auth': True,
                },
                'PATCH /api/user/files/<file_id>/rename': {
                    'desc': 'Rename a file',
                    'auth': True,
                    'body': {'new_name': 'str'},
                },
                'PATCH /api/user/files/<file_id>/move': {
                    'desc': 'Move file to folder',
                    'auth': True,
                    'body': {'folder_id': 'str or null'},
                },
                'GET /api/user/versions/<file_id>': {
                    'desc': 'Get version history',
                    'auth': True,
                },
                'POST /api/user/download-zip': {
                    'desc': 'Download multiple files as ZIP',
                    'auth': True,
                    'body': {'file_ids': ['str']},
                },
                'POST /api/user/bulk-delete': {
                    'desc': 'Bulk delete files',
                    'auth': True,
                    'body': {'file_ids': ['str']},
                },
                'GET /api/user/preview/<file_id>': {
                    'desc': 'Preview file (images, text, video, audio, PDF)',
                    'auth': True,
                },
                'POST /api/user/files/<file_id>/comments': {
                    'desc': 'Add comment to file',
                    'auth': True,
                    'body': {'text': 'str'},
                },
                'GET /api/user/files/<file_id>/comments': {
                    'desc': 'Get file comments',
                    'auth': True,
                },
            },
            'folders': {
                'POST /api/user/folders': {
                    'desc': 'Create folder',
                    'auth': True,
                    'body': {'name': 'str', 'parent_id': 'str or null'},
                },
            },
            'sharing': {
                'POST /api/share/generate': {
                    'desc': 'Generate share link with OTP',
                    'auth': True,
                    'body': {
                        'file_id': 'str',
                        'expiry_hours': 'int',
                        'max_downloads': 'int',
                        'password': 'str (optional)',
                        'message': 'str (optional)',
                        'notify_email': 'str (optional)',
                        'available_after': 'ISO datetime (optional)',
                    },
                    'rate_limit': '30/min',
                },
                'GET /api/share/active': {
                    'desc': 'Get active share links',
                    'auth': True,
                },
                'DELETE /api/share/revoke/<token>': {
                    'desc': 'Revoke a share link',
                    'auth': True,
                },
                'POST /share/<token>/verify': {
                    'desc': 'Verify OTP/password for share link',
                    'body': {'otp': 'str', 'password': 'str (if required)'},
                },
                'GET /share/<token>/download': {
                    'desc': 'Download shared file (after verification)',
                },
            },
            'activity': {
                'GET /api/user/activity': {
                    'desc': 'Get activity feed',
                    'auth': True,
                    'params': {'page': 'int', 'per_page': 'int'},
                },
            },
            'transfers': {
                'GET /api/transfers/history': {
                    'desc': 'Get transfer history',
                },
            },
            'system': {
                'GET /health': {
                    'desc': 'Health check with feature flags',
                },
                'GET /api/docs': {
                    'desc': 'This API documentation',
                },
            },
        },
        'websocket_events': {
            'create_room': 'Receiver creates a transfer room, gets 6-char code',
            'join_transfer_room': 'Sender joins room with code',
            'send_file_chunk': 'Send file chunk to room',
            'file_transfer_start': 'Notify receiver of incoming file',
            'file_transfer_complete': 'Signal transfer completion',
            'cancel_transfer': 'Cancel ongoing transfer',
        },
    })

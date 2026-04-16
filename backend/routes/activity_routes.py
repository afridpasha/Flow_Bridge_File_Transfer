"""Activity feed routes for FlowBridge — track all user actions."""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone

import sys, os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from middleware.auth_middleware import token_required
from database import Database
from models import format_size

logger = logging.getLogger(__name__)
activity_bp = Blueprint('activity', __name__)


def log_activity(user_id: str, action: str, details: dict = None):
    """Log a user activity event."""
    try:
        db = Database.get_db()
        db.activity_log.insert_one({
            'user_id': user_id,
            'action': action,
            'details': details or {},
            'timestamp': datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.error(f"Activity log error: {e}")


@activity_bp.route('/api/user/activity', methods=['GET'])
@token_required
def get_activity(current_user):
    """Get paginated activity feed for the current user."""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 30))
    skip = (page - 1) * per_page

    db = Database.get_db()
    user_id = str(current_user['_id'])

    activities = list(db.activity_log.find(
        {'user_id': user_id},
        sort=[('timestamp', -1)],
    ).skip(skip).limit(per_page))

    total = db.activity_log.count_documents({'user_id': user_id})

    # Format for frontend
    items = []
    action_icons = {
        'upload': '📤', 'download': '⬇️', 'delete': '🗑️',
        'share': '🔗', 'login': '🔐', '2fa_enable': '🛡️',
        'folder_create': '📁', 'rename': '✏️', 'move': '📂',
        'restore': '♻️', 'tag': '🏷️', 'comment': '💬',
    }

    for a in activities:
        items.append({
            'id': str(a['_id']),
            'action': a['action'],
            'icon': action_icons.get(a['action'], '📌'),
            'details': a.get('details', {}),
            'timestamp': a['timestamp'].isoformat(),
            'time_ago': _time_ago(a['timestamp']),
        })

    return jsonify({
        'success': True,
        'activities': items,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page,
    })


def _time_ago(dt):
    """Human-readable time ago string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        m = seconds // 60
        return f'{m}m ago'
    elif seconds < 86400:
        h = seconds // 3600
        return f'{h}h ago'
    elif seconds < 604800:
        d = seconds // 86400
        return f'{d}d ago'
    else:
        return dt.strftime('%b %d, %Y')

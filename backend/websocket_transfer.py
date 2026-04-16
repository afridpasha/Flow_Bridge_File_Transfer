import logging
import random
import string
import time
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request

logger = logging.getLogger(__name__)

# Active rooms: room_code -> {sender_sid, receiver_sid, status, created_at, ...}
active_rooms = {}


def _generate_room_code():
    """Generate a unique 6-character room code (readable, no ambiguous chars)."""
    chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'  # No 0/O/1/I confusion
    while True:
        code = ''.join(random.choices(chars, k=6))
        if code not in active_rooms:
            return code


def _cleanup_stale_rooms():
    """Remove rooms older than 30 minutes."""
    now = time.time()
    stale = [code for code, room in active_rooms.items()
             if now - room.get('created_at', 0) > 1800]
    for code in stale:
        del active_rooms[code]


def register_websocket_events(socketio: SocketIO):
    """Register WebSocket event handlers for room-based file transfers."""

    # ===== RECEIVER creates a room and waits =====
    @socketio.on('create_room')
    def handle_create_room(data):
        """Receiver creates a room and gets a code to share with the sender."""
        _cleanup_stale_rooms()

        code = _generate_room_code()
        sid = request.sid
        room_name = f'transfer_{code}'

        join_room(room_name)

        active_rooms[code] = {
            'room': room_name,
            'receiver_sid': sid,
            'sender_sid': None,
            'status': 'waiting',
            'created_at': time.time(),
            'username': data.get('username', 'Anonymous'),
        }

        emit('room_created', {
            'room_code': code,
            'message': f'Room created! Share code: {code}'
        })
        logger.info(f"Room created: {code} by {data.get('username', '?')}")

    # ===== SENDER joins a room by code =====
    @socketio.on('join_transfer_room')
    def handle_join_room(data):
        """Sender joins a receiver's room using the 6-digit code."""
        code = (data.get('room_code') or '').upper().strip()

        if code not in active_rooms:
            emit('room_error', {'error': 'Invalid room code. Check and try again.'})
            return

        room_info = active_rooms[code]
        if room_info['status'] != 'waiting':
            emit('room_error', {'error': 'Room is busy with another transfer.'})
            return

        sid = request.sid
        room_name = room_info['room']
        join_room(room_name)

        room_info['sender_sid'] = sid
        room_info['status'] = 'connected'

        # Notify both parties
        emit('room_joined', {
            'room_code': code,
            'room': room_name,
            'message': f'Connected! You can now send files.',
            'receiver': room_info['username'],
        })

        # Tell the receiver that sender connected
        emit('sender_connected', {
            'room_code': code,
            'sender': data.get('username', 'Anonymous'),
            'message': 'Sender connected! Waiting for file...'
        }, room=room_name)

        logger.info(f"Sender joined room {code}")

    # ===== Get list of active rooms (for UI) =====
    @socketio.on('list_rooms')
    def handle_list_rooms(data):
        """List active rooms (for admin/debug)."""
        _cleanup_stale_rooms()
        rooms = [{
            'code': code,
            'status': info['status'],
            'receiver': info['username'],
            'age_seconds': int(time.time() - info['created_at']),
        } for code, info in active_rooms.items()]
        emit('room_list', {'rooms': rooms})

    # ===== File transfer: sender → server → receiver =====
    @socketio.on('send_file_chunk')
    def handle_send_file_chunk(data):
        """Forward file chunk from sender to receiver via room."""
        room = data.get('room')
        if not room:
            return

        emit('receive_file_chunk', {
            'chunk': data.get('chunk'),
            'chunk_index': data.get('chunk_index', 0),
            'total_chunks': data.get('total_chunks', 1),
            'filename': data.get('filename', 'unknown'),
            'file_size': data.get('file_size', 0),
        }, room=room, include_self=False)

        # Progress notification to both parties
        progress = round((data.get('chunk_index', 0) + 1) / max(data.get('total_chunks', 1), 1) * 100, 1)
        emit('transfer_progress', {
            'filename': data.get('filename'),
            'progress': progress,
            'chunk_index': data.get('chunk_index'),
            'total_chunks': data.get('total_chunks'),
        }, room=room)

    # ===== Transfer metadata (sent before chunks) =====
    @socketio.on('file_transfer_start')
    def handle_transfer_start(data):
        """Notify receiver that a file transfer is about to begin."""
        room = data.get('room')
        if room:
            emit('incoming_file', {
                'filename': data.get('filename'),
                'file_size': data.get('file_size'),
                'total_chunks': data.get('total_chunks'),
            }, room=room, include_self=False)
        logger.info(f"Transfer starting: {data.get('filename')}")

    # ===== Transfer complete =====
    @socketio.on('file_transfer_complete')
    def handle_transfer_complete(data):
        """Handle transfer completion."""
        room = data.get('room')
        if room:
            emit('transfer_complete', {
                'filename': data.get('filename'),
                'success': data.get('success', True),
                'checksum': data.get('checksum'),
            }, room=room)

        # Update room status
        for code, info in active_rooms.items():
            if info['room'] == room:
                info['status'] = 'waiting'  # Ready for next file
                break

        logger.info(f"Transfer complete: {data.get('filename')}")

    # ===== Cancel transfer =====
    @socketio.on('cancel_transfer')
    def handle_cancel_transfer(data):
        """Handle transfer cancellation."""
        room = data.get('room')
        if room:
            emit('transfer_cancelled', {
                'message': 'Transfer cancelled'
            }, room=room)

    # ===== Leave/close room =====
    @socketio.on('leave_transfer_room')
    def handle_leave_room(data):
        """Leave and optionally close a transfer room."""
        code = (data.get('room_code') or '').upper().strip()
        if code in active_rooms:
            room_name = active_rooms[code]['room']
            leave_room(room_name)
            emit('peer_disconnected', {
                'message': 'Peer disconnected'
            }, room=room_name)
            del active_rooms[code]
            logger.info(f"Room closed: {code}")

    # ===== Handle disconnect =====
    @socketio.on('disconnect')
    def handle_disconnect():
        """Clean up when a client disconnects."""
        sid = request.sid
        to_remove = []
        for code, info in active_rooms.items():
            if info.get('receiver_sid') == sid or info.get('sender_sid') == sid:
                room_name = info['room']
                emit('peer_disconnected', {
                    'message': 'Peer disconnected'
                }, room=room_name)
                to_remove.append(code)

        for code in to_remove:
            del active_rooms[code]

    # ========== CODESHARE: Real-time Collaborative Editing ==========
    
    @socketio.on('codeshare_join')
    def handle_codeshare_join(data):
        """User joins a code share session."""
        slug = data.get('slug')
        user_id = data.get('user_id', request.sid)
        user_name = data.get('user_name', 'Anonymous')
        
        if not slug:
            emit('codeshare_error', {'error': 'Slug required'})
            return
        
        # Join room
        room = f'codeshare_{slug}'
        join_room(room)
        
        # Add to active users
        from models_codeshare import CodeShare
        CodeShare.add_active_user(slug, user_id, user_name)
        
        # Notify others
        emit('codeshare_user_joined', {
            'user_id': user_id,
            'user_name': user_name,
            'message': f'{user_name} joined'
        }, room=room, include_self=False)
        
        # Send current active users to new user
        doc = CodeShare.get_by_slug(slug)
        if doc:
            # Convert datetime objects to strings for JSON serialization
            active_users = doc.get('active_users', [])
            serializable_users = []
            for user in active_users:
                user_copy = user.copy()
                if 'joined_at' in user_copy and hasattr(user_copy['joined_at'], 'isoformat'):
                    user_copy['joined_at'] = user_copy['joined_at'].isoformat()
                serializable_users.append(user_copy)
            
            emit('codeshare_active_users', {
                'active_users': serializable_users
            })
        
        logger.info(f"User {user_name} joined codeshare: {slug}")
    
    @socketio.on('codeshare_leave')
    def handle_codeshare_leave(data):
        """User leaves a code share session."""
        slug = data.get('slug')
        user_id = data.get('user_id', request.sid)
        user_name = data.get('user_name', 'Anonymous')
        
        if not slug:
            return
        
        room = f'codeshare_{slug}'
        leave_room(room)
        
        # Remove from active users
        from models_codeshare import CodeShare
        CodeShare.remove_active_user(slug, user_id)
        
        # Notify others
        emit('codeshare_user_left', {
            'user_id': user_id,
            'user_name': user_name,
            'message': f'{user_name} left'
        }, room=room)
        
        logger.info(f"User {user_name} left codeshare: {slug}")
    
    @socketio.on('codeshare_edit')
    def handle_codeshare_edit(data):
        """Real-time code edit broadcast."""
        slug = data.get('slug')
        code = data.get('code', '')
        user_id = data.get('user_id', request.sid)
        user_name = data.get('user_name', 'Anonymous')
        cursor = data.get('cursor', {'line': 0, 'column': 0})
        
        if not slug:
            return
        
        room = f'codeshare_{slug}'
        
        # Update cursor position
        from models_codeshare import CodeShare
        CodeShare.update_cursor(slug, user_id, cursor.get('line', 0), cursor.get('column', 0))
        
        # Broadcast to others (not to sender)
        emit('codeshare_code_update', {
            'code': code,
            'user_id': user_id,
            'user_name': user_name,
            'cursor': cursor
        }, room=room, include_self=False)
    
    @socketio.on('codeshare_cursor')
    def handle_codeshare_cursor(data):
        """Update and broadcast cursor position."""
        slug = data.get('slug')
        user_id = data.get('user_id', request.sid)
        user_name = data.get('user_name', 'Anonymous')
        cursor = data.get('cursor', {'line': 0, 'column': 0})
        
        if not slug:
            return
        
        room = f'codeshare_{slug}'
        
        # Update in database
        from models_codeshare import CodeShare
        CodeShare.update_cursor(slug, user_id, cursor.get('line', 0), cursor.get('column', 0))
        
        # Broadcast to others
        emit('codeshare_cursor_update', {
            'user_id': user_id,
            'user_name': user_name,
            'cursor': cursor
        }, room=room, include_self=False)
    
    @socketio.on('codeshare_save')
    def handle_codeshare_save(data):
        """Save code to database."""
        slug = data.get('slug')
        code = data.get('code', '')
        user_name = data.get('user_name', 'Anonymous')
        save_version = data.get('save_version', False)
        
        if not slug:
            emit('codeshare_error', {'error': 'Slug required'})
            return
        
        try:
            from models_codeshare import CodeShare
            success = CodeShare.update_code(slug, code, user_name, save_version)
            
            if success:
                emit('codeshare_saved', {
                    'success': True,
                    'message': 'Code saved successfully'
                })
                
                # Notify others
                room = f'codeshare_{slug}'
                emit('codeshare_notification', {
                    'message': f'{user_name} saved the code',
                    'type': 'save'
                }, room=room, include_self=False)
            else:
                emit('codeshare_error', {'error': 'Failed to save'})
        
        except Exception as e:
            logger.error(f"CodeShare save error: {e}")
            emit('codeshare_error', {'error': str(e)})

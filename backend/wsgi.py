"""
WSGI entry point for Gunicorn with eventlet worker.
This file ensures eventlet.monkey_patch() runs BEFORE any other imports.
"""

# CRITICAL: monkey_patch MUST be first, before ANY other imports
import eventlet
eventlet.monkey_patch()

# Now safe to import Flask app
from app import app, socketio

# For gunicorn with eventlet worker
application = socketio if socketio else app

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000)

"""
CodeShare Models - Real-time collaborative code sharing
Similar to codeshare.io functionality
"""

import logging
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from database import Database
from bson import ObjectId
from services.redis_cache_service import get_cache_service

logger = logging.getLogger(__name__)

# ── InMemory: active users + cursors per slug ──────────────────────────────
# Structure: { slug: { user_id: { user_name, cursor, joined_at } } }
# Lost on restart — acceptable (ephemeral real-time state)
_active_users: dict = {}
_active_lock = __import__('threading').Lock()


def utcnow() -> datetime:
    """Get current UTC time."""
    return datetime.now(timezone.utc)


class CodeShare:
    """Model for collaborative code sharing sessions."""

    @staticmethod
    def generate_slug(length: int = 8) -> str:
        """Generate a random URL-safe slug."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def create(
        code: str = "",
        language: str = "python",
        title: str = "Untitled",
        custom_slug: Optional[str] = None,
        creator_id: Optional[str] = None,
        creator_name: str = "Anonymous",
        expiry_hours: Optional[int] = None,
        is_public: bool = True,
        allow_edit: bool = True
    ) -> Dict:
        """Create a new code share session."""
        db = Database.get_db()

        # Generate or validate slug
        if custom_slug:
            # Validate custom slug
            custom_slug = custom_slug.lower().strip()
            if not custom_slug or len(custom_slug) < 3:
                raise ValueError("Custom URL must be at least 3 characters")
            if not all(c in string.ascii_lowercase + string.digits + '-_' for c in custom_slug):
                raise ValueError("Custom URL can only contain letters, numbers, hyphens, and underscores")
            
            # Check if slug already exists
            existing = db.codeshares.find_one({"slug": custom_slug})
            if existing:
                raise ValueError(f"URL '{custom_slug}' is already taken. Try another one.")
            
            slug = custom_slug
        else:
            # Generate unique random slug
            while True:
                slug = CodeShare.generate_slug()
                if not db.codeshares.find_one({"slug": slug}):
                    break

        # Calculate expiry
        expires_at = None
        if expiry_hours:
            expires_at = utcnow() + timedelta(hours=expiry_hours)

        # Create document
        doc = {
            "slug": slug,
            "title": title,
            "code": code,
            "language": language,
            "creator_id": creator_id,
            "creator_name": creator_name,
            "is_public": is_public,
            "allow_edit": allow_edit,
            "created_at": utcnow(),
            "updated_at": utcnow(),
            "expires_at": expires_at,
            "view_count": 0,
            "edit_count": 0,
            "active_users": [],  # List of currently active users
            "version_history": [{
                "version": 1,
                "code": code,
                "edited_by": creator_name,
                "edited_at": utcnow(),
                "change_summary": "Initial version"
            }],
            "collaborators": [],  # List of users who have edited
        }

        result = db.codeshares.insert_one(doc)
        doc['_id'] = result.inserted_id

        logger.info(f"CodeShare created: {slug} by {creator_name}")
        return doc

    @staticmethod
    def get_by_slug(slug: str) -> Optional[Dict]:
        """Get code share by slug — Redis cache (30s) then MongoDB."""
        cache = get_cache_service()
        cached = cache.get_codeshare(slug)
        if cached is not None:
            # Attach live InMemory active users
            with _active_lock:
                cached['active_users'] = list(
                    _active_users.get(slug, {}).values()
                )
            return cached

        db = Database.get_db()
        doc = db.codeshares.find_one({"slug": slug})
        
        if doc:
            db.codeshares.update_one(
                {"slug": slug}, {"$inc": {"view_count": 1}}
            )
            # Cache in Redis (without active_users — those are InMemory only)
            doc_to_cache = {k: v for k, v in doc.items()
                            if k not in ('active_users', '_id')}
            doc_to_cache['_id'] = str(doc['_id'])
            cache.set_codeshare(slug, doc_to_cache)
            # Attach InMemory active users to response
            with _active_lock:
                doc['active_users'] = list(
                    _active_users.get(slug, {}).values()
                )
        return doc

    @staticmethod
    def update_code(
        slug: str,
        code: str,
        editor_name: str = "Anonymous",
        save_version: bool = False
    ) -> bool:
        """Update code content."""
        db = Database.get_db()
        
        doc = db.codeshares.find_one({"slug": slug})
        if not doc:
            return False

        # Check if editing is allowed
        if not doc.get('allow_edit', True):
            raise ValueError("Editing is disabled for this code share")

        # Check if expired
        if doc.get('expires_at'):
            expires_at = doc['expires_at']
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if utcnow() > expires_at:
                raise ValueError("This code share has expired")

        update_data = {
            "code": code,
            "updated_at": utcnow(),
            "$inc": {"edit_count": 1}
        }

        # Save version history
        if save_version:
            version_num = len(doc.get('version_history', [])) + 1
            version_entry = {
                "version": version_num,
                "code": code,
                "edited_by": editor_name,
                "edited_at": utcnow(),
                "change_summary": f"Edit by {editor_name}"
            }
            update_data["$push"] = {"version_history": version_entry}

        # Add to collaborators if not already there
        if editor_name not in doc.get('collaborators', []):
            if "$push" in update_data:
                update_data["$push"]["collaborators"] = editor_name
            else:
                update_data["$push"] = {"collaborators": editor_name}

        db.codeshares.update_one({"slug": slug}, update_data)
        # Invalidate Redis cache so next read gets fresh content
        get_cache_service().invalidate_codeshare(slug)
        return True

    @staticmethod
    def update_settings(
        slug: str,
        title: Optional[str] = None,
        language: Optional[str] = None,
        allow_edit: Optional[bool] = None,
        expiry_hours: Optional[int] = None
    ) -> bool:
        """Update code share settings."""
        db = Database.get_db()
        
        update_data = {"updated_at": utcnow()}
        
        if title is not None:
            update_data["title"] = title
        if language is not None:
            update_data["language"] = language
        if allow_edit is not None:
            update_data["allow_edit"] = allow_edit
        if expiry_hours is not None:
            if expiry_hours > 0:
                update_data["expires_at"] = utcnow() + timedelta(hours=expiry_hours)
            else:
                update_data["expires_at"] = None

        result = db.codeshares.update_one({"slug": slug}, {"$set": update_data})
        return result.modified_count > 0

    @staticmethod
    def add_active_user(slug: str, user_id: str, user_name: str) -> bool:
        """Add user to InMemory active users — zero DB writes."""
        with _active_lock:
            if slug not in _active_users:
                _active_users[slug] = {}
            _active_users[slug][user_id] = {
                'user_id':   user_id,
                'user_name': user_name,
                'joined_at': utcnow().isoformat(),
                'cursor_position': {'line': 0, 'column': 0},
            }
        return True

    @staticmethod
    def remove_active_user(slug: str, user_id: str) -> bool:
        """Remove user from InMemory active users."""
        with _active_lock:
            if slug in _active_users:
                _active_users[slug].pop(user_id, None)
                if not _active_users[slug]:
                    del _active_users[slug]
        return True

    @staticmethod
    def update_cursor(slug: str, user_id: str, line: int, column: int) -> bool:
        """Update cursor in InMemory — zero DB writes (10-100 updates/sec safe)."""
        with _active_lock:
            if slug in _active_users and user_id in _active_users[slug]:
                _active_users[slug][user_id]['cursor_position'] = {
                    'line': line, 'column': column
                }
        return True

    @staticmethod
    def get_version_history(slug: str) -> List[Dict]:
        """Get version history for a code share."""
        db = Database.get_db()
        
        doc = db.codeshares.find_one({"slug": slug})
        if not doc:
            return []
        
        history = doc.get('version_history', [])
        
        # Format timestamps
        for version in history:
            if isinstance(version.get('edited_at'), datetime):
                version['edited_at'] = version['edited_at'].isoformat()
        
        return history

    @staticmethod
    def delete(slug: str) -> bool:
        """Delete a code share."""
        db = Database.get_db()
        result = db.codeshares.delete_one({"slug": slug})
        return result.deleted_count > 0

    @staticmethod
    def get_user_codeshares(creator_id: str, limit: int = 20) -> List[Dict]:
        """Get all code shares created by a user."""
        db = Database.get_db()
        
        docs = list(db.codeshares.find(
            {"creator_id": creator_id}
        ).sort("created_at", -1).limit(limit))
        
        for doc in docs:
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('created_at'), datetime):
                doc['created_at'] = doc['created_at'].isoformat()
            if isinstance(doc.get('updated_at'), datetime):
                doc['updated_at'] = doc['updated_at'].isoformat()
            if isinstance(doc.get('expires_at'), datetime):
                doc['expires_at'] = doc['expires_at'].isoformat()
        
        return docs

    @staticmethod
    def cleanup_expired() -> int:
        """Delete expired code shares. Returns count of deleted documents."""
        db = Database.get_db()
        
        result = db.codeshares.delete_many({
            "expires_at": {"$lt": utcnow(), "$ne": None}
        })
        
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} expired code shares")
        
        return result.deleted_count

    @staticmethod
    def get_stats(slug: str) -> Dict:
        """Get statistics for a code share."""
        db = Database.get_db()
        
        doc = db.codeshares.find_one({"slug": slug})
        if not doc:
            return {}
        
        return {
            "view_count": doc.get('view_count', 0),
            "edit_count": doc.get('edit_count', 0),
            "collaborators_count": len(doc.get('collaborators', [])),
            "active_users_count": len(doc.get('active_users', [])),
            "version_count": len(doc.get('version_history', [])),
            "created_at": doc['created_at'].isoformat() if isinstance(doc.get('created_at'), datetime) else None,
            "updated_at": doc['updated_at'].isoformat() if isinstance(doc.get('updated_at'), datetime) else None,
        }

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import bcrypt
from bson import ObjectId
from database import Database
from config import Config
from services.storage_service import get_storage_service
from services.redis_cache_service import get_cache_service

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def format_size(size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def get_file_extension(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in Config.ALLOWED_EXTENSIONS


def compute_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_password(password: str) -> tuple:
    if len(password) < Config.PASSWORD_MIN_LENGTH:
        return False, f"Password must be at least {Config.PASSWORD_MIN_LENGTH} characters"
    if Config.PASSWORD_REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if Config.PASSWORD_REQUIRE_DIGIT and not re.search(r'[0-9]', password):
        return False, "Password must contain at least one digit"
    return True, ""


# ══════════════════════════════════════════════════════════════════════════
#  User
# ══════════════════════════════════════════════════════════════════════════

class User:

    @staticmethod
    def create(username: str, email: str, password: str) -> tuple:
        db = Database.get_db()
        is_valid, error = validate_password(password)
        if not is_valid:
            return None, error

        if db.users.find_one({"$or": [{"username": username}, {"email": email}]}):
            return None, "Username or email already exists"

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
        user = {
            "username": username,
            "email": email.lower().strip(),
            "password": hashed,
            "created_at": utcnow(),
            "storage_used": 0,
            "storage_quota": 500 * 1024 * 1024,
            "failed_login_attempts": 0,
            "locked_until": None,
            "totp_secret": None,
            "totp_enabled": False,
        }
        result = db.users.insert_one(user)
        user['_id'] = result.inserted_id
        return user, None

    @staticmethod
    def find_by_username(username: str) -> Optional[Dict]:
        return Database.get_db().users.find_one({"username": username})

    @staticmethod
    def find_by_id(user_id: str) -> Optional[Dict]:
        try:
            return Database.get_db().users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    @staticmethod
    def verify_password(stored: Any, provided: str) -> bool:
        if isinstance(stored, str):
            stored = stored.encode('utf-8')
        try:
            return bcrypt.checkpw(provided.encode('utf-8'), stored)
        except Exception:
            return False

    @staticmethod
    def update_storage(user_id: str, delta: int):
        Database.get_db().users.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"storage_used": delta}}
        )
        get_cache_service().invalidate_user_storage(user_id)

    @staticmethod
    def check_storage_quota(user_id: str, file_size: int) -> bool:
        user = User.find_by_id(user_id)
        if not user:
            return False
        used  = user.get('storage_used', 0)
        quota = user.get('storage_quota', 500 * 1024 * 1024)
        return (used + file_size) <= quota

    @staticmethod
    def increment_failed_login(username: str) -> int:
        result = Database.get_db().users.find_one_and_update(
            {"username": username},
            {"$inc": {"failed_login_attempts": 1}},
            return_document=True
        )
        return result.get('failed_login_attempts', 0) if result else 0

    @staticmethod
    def reset_failed_login(username: str):
        Database.get_db().users.update_one(
            {"username": username},
            {"$set": {"failed_login_attempts": 0, "locked_until": None}}
        )

    @staticmethod
    def lock_account(username: str, minutes: int = 15):
        from datetime import timedelta
        Database.get_db().users.update_one(
            {"username": username},
            {"$set": {"locked_until": utcnow() + timedelta(minutes=minutes)}}
        )

    @staticmethod
    def is_locked(user: Dict) -> bool:
        locked_until = user.get('locked_until')
        if not locked_until:
            return False
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        return utcnow() < locked_until


# ══════════════════════════════════════════════════════════════════════════
#  UserFile  — storage via R2 (primary) + B2 (global replica) + MinIO (local)
# ══════════════════════════════════════════════════════════════════════════

class UserFile:

    @staticmethod
    def create(user_id: str, filename: str, file_data: bytes,
               file_size: int, content_type: str) -> str:
        """
        Upload file to storage backends and save metadata to MongoDB.
        Write order: R2 (sync) → B2 (async) → MinIO (async)
        """
        db      = Database.get_db()
        storage = get_storage_service()
        cache   = get_cache_service()

        if not is_allowed_file(filename):
            raise ValueError(f"File type not allowed: {get_file_extension(filename)}")

        if not User.check_storage_quota(str(user_id), file_size):
            raise ValueError("Storage quota exceeded")

        # Upload to all backends
        result = storage.upload(file_data, filename, content_type)

        file_meta = {
            "user_id":        str(user_id),
            "filename":       filename,
            "size":           file_size,
            "content_type":   content_type,
            "checksum":       result['sha256'],

            # Storage keys — same content-addressable key on all backends
            "r2_key":         result['r2_key'],
            "b2_key":         result['b2_key'],
            "minio_key":      result['minio_key'],
            "storage_backend": "r2" if result['r2_key'] else (
                               "b2" if result['b2_key'] else "minio"),
            "b2_synced":      False,   # async — updated by background thread
            "minio_synced":   False,   # async — updated by background thread

            "uploaded_at":    utcnow(),
            "folder_id":      None,
            "tags":           [],
            "is_deleted":     False,
            "version":        1,
        }

        inserted = db.user_files.insert_one(file_meta)
        User.update_storage(str(user_id), file_size)

        # Invalidate file list cache so dashboard reflects new file
        cache.invalidate_file_list(str(user_id))

        logger.info(
            f"Uploaded: {filename} ({format_size(file_size)}) "
            f"r2={bool(result['r2_key'])} b2={bool(result['b2_key'])} "
            f"minio={bool(result['minio_key'])} dedup={result['deduplicated']}"
        )
        return str(inserted.inserted_id)

    @staticmethod
    def get_user_files(user_id: str, folder_id: Optional[str] = None,
                       search: Optional[str] = None,
                       sort_by: str = 'uploaded_at',
                       sort_order: int = -1) -> List[Dict]:
        """
        Get files for a user — Redis cache hit returns in ~10ms,
        cache miss queries MongoDB then caches result.
        Cache is only used for the default (no search, root folder) view.
        """
        cache     = get_cache_service()
        use_cache = not search and not folder_id

        if use_cache:
            cached = cache.get_file_list(user_id)
            if cached is not None:
                return cached

        db    = Database.get_db()
        query = {"user_id": str(user_id), "is_deleted": {"$ne": True}}

        if folder_id:
            query["folder_id"] = folder_id
        else:
            query["folder_id"] = None

        if search:
            query["filename"] = {"$regex": search, "$options": "i"}

        valid_sorts = {'uploaded_at', 'filename', 'size', 'content_type'}
        if sort_by not in valid_sorts:
            sort_by = 'uploaded_at'

        files = list(db.user_files.find(query).sort(sort_by, sort_order))

        for f in files:
            f['_id']            = str(f['_id'])
            # file_id for frontend compatibility — use _id as the identifier
            f['file_id']        = str(f['_id'])
            f['size_formatted'] = format_size(f.get('size', 0))
            f['extension']      = get_file_extension(f['filename'])
            f['is_previewable'] = f['extension'] in (
                Config.PREVIEWABLE_IMAGES | Config.PREVIEWABLE_TEXT |
                Config.PREVIEWABLE_VIDEO | Config.PREVIEWABLE_AUDIO
            )
            f['preview_type']   = UserFile._get_preview_type(f['extension'])
            if isinstance(f.get('uploaded_at'), datetime):
                f['uploaded_at'] = f['uploaded_at'].strftime('%Y-%m-%d %H:%M:%S')
            f['tags'] = f.get('tags', [])

        if use_cache:
            cache.set_file_list(user_id, files)

        return files

    @staticmethod
    def _get_preview_type(ext: str) -> str:
        if ext in Config.PREVIEWABLE_IMAGES: return 'image'
        if ext in Config.PREVIEWABLE_TEXT:   return 'text'
        if ext in Config.PREVIEWABLE_VIDEO:  return 'video'
        if ext in Config.PREVIEWABLE_AUDIO:  return 'audio'
        if ext == 'pdf':                     return 'pdf'
        return 'none'

    @staticmethod
    def get_file_meta(file_id: str, user_id: str) -> Optional[Dict]:
        """Get file metadata with ownership check."""
        db = Database.get_db()
        return db.user_files.find_one({
            "_id":        ObjectId(file_id),
            "user_id":    str(user_id),
            "is_deleted": {"$ne": True},
        })

    @staticmethod
    def get_file_stream(file_meta: Dict) -> Dict:
        """
        Get presigned download URL from best available backend.
        Returns {'type': 'presigned_url', 'url': str}
        """
        storage = get_storage_service()
        url = storage.get_download_url(
            r2_key    = file_meta.get('r2_key'),
            b2_key    = file_meta.get('b2_key'),
            minio_key = file_meta.get('minio_key'),
            filename  = file_meta.get('filename', 'file'),
        )
        if url:
            return {'type': 'presigned_url', 'url': url}
        raise RuntimeError(
            f"No storage backend available for file: {file_meta.get('filename')}"
        )

    @staticmethod
    def get_file_bytes(file_meta: Dict) -> Optional[bytes]:
        """Download raw bytes — used for ZIP creation and text preview."""
        storage = get_storage_service()
        key = (file_meta.get('r2_key')
               or file_meta.get('b2_key')
               or file_meta.get('minio_key'))
        if not key:
            return None
        return storage.download_bytes(key)

    @staticmethod
    def delete_file(file_id: str, user_id: str, soft: bool = True) -> bool:
        db      = Database.get_db()
        cache   = get_cache_service()
        storage = get_storage_service()

        file_meta = db.user_files.find_one({
            "_id":     ObjectId(file_id),
            "user_id": str(user_id),
        })
        if not file_meta:
            return False

        if soft:
            db.user_files.update_one(
                {"_id": ObjectId(file_id)},
                {"$set": {"is_deleted": True, "deleted_at": utcnow()}}
            )
            db.trash.insert_one({
                "original_file": {
                    "_id":      str(file_meta['_id']),
                    "filename": file_meta['filename'],
                    "size":     file_meta.get('size', 0),
                    "r2_key":   file_meta.get('r2_key'),
                    "b2_key":   file_meta.get('b2_key'),
                    "minio_key":file_meta.get('minio_key'),
                },
                "user_id":    str(user_id),
                "deleted_at": utcnow(),
            })
        else:
            # Hard delete — remove from all storage backends
            key = (file_meta.get('r2_key')
                   or file_meta.get('b2_key')
                   or file_meta.get('minio_key'))
            if key:
                storage.delete(key)
            db.user_files.delete_one({"_id": ObjectId(file_id)})

        User.update_storage(str(user_id), -file_meta.get('size', 0))
        cache.invalidate_file_list(str(user_id))

        logger.info(
            f"File {'trashed' if soft else 'deleted'}: "
            f"{file_meta['filename']} by {user_id}"
        )
        return True

    @staticmethod
    def restore_file(file_id: str, user_id: str) -> bool:
        db    = Database.get_db()
        cache = get_cache_service()

        result = db.user_files.update_one(
            {"_id": ObjectId(file_id), "user_id": str(user_id), "is_deleted": True},
            {"$set": {"is_deleted": False}, "$unset": {"deleted_at": ""}}
        )
        if result.modified_count > 0:
            db.trash.delete_one({"original_file._id": str(file_id)})
            file_meta = db.user_files.find_one({"_id": ObjectId(file_id)})
            if file_meta:
                User.update_storage(str(user_id), file_meta.get('size', 0))
            cache.invalidate_file_list(str(user_id))
            return True
        return False

    @staticmethod
    def get_trash(user_id: str) -> List[Dict]:
        db    = Database.get_db()
        files = list(db.user_files.find(
            {"user_id": str(user_id), "is_deleted": True}
        ).sort("deleted_at", -1))

        result = []
        for f in files:
            result.append({
                '_id':          str(f['_id']),
                'file_id':      str(f['_id']),   # safe — no GridFS ObjectId
                'filename':     f.get('filename', ''),
                'size':         f.get('size', 0),
                'size_formatted': format_size(f.get('size', 0)),
                'deleted_at':   (f['deleted_at'].strftime('%Y-%m-%d %H:%M:%S')
                                 if isinstance(f.get('deleted_at'), datetime)
                                 else str(f.get('deleted_at', ''))),
            })
        return result

    @staticmethod
    def search_files(user_id: str, query: str) -> List[Dict]:
        return UserFile.get_user_files(user_id, search=query)

    @staticmethod
    def add_tags(file_id: str, user_id: str, tags: List[str]) -> bool:
        result = Database.get_db().user_files.update_one(
            {"_id": ObjectId(file_id), "user_id": str(user_id)},
            {"$addToSet": {"tags": {"$each": tags}}}
        )
        if result.modified_count > 0:
            get_cache_service().invalidate_file_list(user_id)
        return result.modified_count > 0

    @staticmethod
    def remove_tag(file_id: str, user_id: str, tag: str) -> bool:
        result = Database.get_db().user_files.update_one(
            {"_id": ObjectId(file_id), "user_id": str(user_id)},
            {"$pull": {"tags": tag}}
        )
        if result.modified_count > 0:
            get_cache_service().invalidate_file_list(user_id)
        return result.modified_count > 0

    @staticmethod
    def check_duplicate(user_id: str, checksum: str) -> Optional[Dict]:
        return Database.get_db().user_files.find_one({
            "user_id":    str(user_id),
            "checksum":   checksum,
            "is_deleted": {"$ne": True},
        })


# ══════════════════════════════════════════════════════════════════════════
#  Folder
# ══════════════════════════════════════════════════════════════════════════

class Folder:

    @staticmethod
    def create(user_id: str, name: str, parent_id: Optional[str] = None) -> str:
        db = Database.get_db()
        result = db.folders.insert_one({
            "user_id":    str(user_id),
            "name":       name,
            "parent_id":  parent_id,
            "created_at": utcnow(),
        })
        return str(result.inserted_id)

    @staticmethod
    def get_folders(user_id: str, parent_id: Optional[str] = None) -> List[Dict]:
        db      = Database.get_db()
        folders = list(db.folders.find(
            {"user_id": str(user_id), "parent_id": parent_id}
        ).sort("name", 1))
        for f in folders:
            f['_id'] = str(f['_id'])
            if isinstance(f.get('created_at'), datetime):
                f['created_at'] = f['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return folders

    @staticmethod
    def delete(folder_id: str, user_id: str) -> bool:
        db = Database.get_db()
        db.user_files.update_many(
            {"folder_id": folder_id, "user_id": str(user_id)},
            {"$set": {"folder_id": None}}
        )
        db.folders.update_many(
            {"parent_id": folder_id, "user_id": str(user_id)},
            {"$set": {"parent_id": None}}
        )
        result = db.folders.delete_one(
            {"_id": ObjectId(folder_id), "user_id": str(user_id)}
        )
        if result.deleted_count > 0:
            get_cache_service().invalidate_file_list(user_id)
        return result.deleted_count > 0

    @staticmethod
    def rename(folder_id: str, user_id: str, new_name: str) -> bool:
        result = Database.get_db().folders.update_one(
            {"_id": ObjectId(folder_id), "user_id": str(user_id)},
            {"$set": {"name": new_name}}
        )
        return result.modified_count > 0

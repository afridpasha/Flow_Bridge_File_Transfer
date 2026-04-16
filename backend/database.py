import logging
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure
from config import Config

logger = logging.getLogger(__name__)


class Database:
    """MongoDB database manager — metadata only, no GridFS."""

    client = None
    db = None
    _initialized = False

    @staticmethod
    def initialize():
        if Database._initialized:
            return True

        try:
            uri = Config.MONGO_URI
            if not uri:
                raise ValueError("MONGO_URI not configured. Check your .env file.")

            Database.client = MongoClient(
                uri,
                tls=True,
                tlsAllowInvalidCertificates=True,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
                maxPoolSize=50,
                minPoolSize=5,
                retryWrites=True,
            )

            Database.client.admin.command('ping')
            Database.db = Database.client[Config.MONGO_DB_NAME]
            Database._initialized = True

            Database._create_indexes()
            logger.info("MongoDB connected successfully")
            return True

        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            raise

    @staticmethod
    def _create_indexes():
        db = Database.db
        try:
            # ── users ──────────────────────────────────────────────────
            db.users.create_index("username", unique=True)
            db.users.create_index("email", unique=True)

            # ── user_files ─────────────────────────────────────────────
            db.user_files.create_index(
                [("user_id", ASCENDING), ("uploaded_at", ASCENDING)]
            )
            db.user_files.create_index("checksum")
            # Replication status — quickly find un-synced files
            db.user_files.create_index("b2_synced")
            db.user_files.create_index("minio_synced")

            # ── share_tokens — TTL auto-delete on expiry ───────────────
            db.share_tokens.create_index("token", unique=True)
            db.share_tokens.create_index(
                "expires_at", expireAfterSeconds=0          # TTL ✅
            )
            db.share_tokens.create_index("user_id")

            # ── transfers — TTL 90 days ────────────────────────────────
            # Drop old index without TTL if it exists, then recreate with TTL
            try:
                db.transfers.drop_index("started_at_1")
            except Exception:
                pass
            db.transfers.create_index(
                "started_at", expireAfterSeconds=90 * 24 * 3600  # TTL ✅
            )
            db.transfers.create_index("user_id")

            # ── activity_log — TTL 30 days ─────────────────────────────
            db.activity_log.create_index(
                "timestamp", expireAfterSeconds=30 * 24 * 3600   # TTL ✅ NEW
            )
            db.activity_log.create_index("user_id")

            # ── folders ────────────────────────────────────────────────
            db.folders.create_index(
                [("user_id", ASCENDING), ("parent_id", ASCENDING)]
            )

            # ── trash — TTL 30 days ────────────────────────────────────
            db.trash.create_index(
                "deleted_at", expireAfterSeconds=30 * 24 * 3600  # TTL ✅
            )
            db.trash.create_index("user_id")

            # ── codeshares — TTL on expires_at ────────────────────────
            db.codeshares.create_index("slug", unique=True)
            db.codeshares.create_index(
                "expires_at", expireAfterSeconds=0,
                partialFilterExpression={"expires_at": {"$type": "date"}}  # TTL ✅
            )
            db.codeshares.create_index("creator_id")

            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    @staticmethod
    def get_db():
        if Database.db is None:
            Database.initialize()
        return Database.db

    @staticmethod
    def health_check():
        try:
            if Database.client is None:
                return False, "Not connected"
            Database.client.admin.command('ping')
            return True, "Connected"
        except Exception as e:
            return False, str(e)

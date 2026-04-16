import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


class TransferService:
    """Transfer tracking service with MongoDB persistence."""

    # In-memory cache for active transfers (real-time updates)
    _active_transfers = {}

    @classmethod
    def start_transfer(cls, transfer_id: str, filename: str, size: int,
                       source: str, user_id: str = None) -> Dict:
        """Register a new transfer."""
        transfer = {
            'id': transfer_id,
            'filename': filename,
            'size': size,
            'source': source,
            'user_id': user_id,
            'progress': 0,
            'bytes_transferred': 0,
            'status': 'active',
            'started_at': utcnow().strftime('%Y-%m-%d %H:%M:%S'),
        }
        cls._active_transfers[transfer_id] = transfer

        # Also persist to DB
        try:
            from database import Database
            db = Database.get_db()
            db.transfers.insert_one({
                **transfer,
                'started_at': utcnow(),
                'completed_at': None,
            })
        except Exception as e:
            logger.warning(f"Could not persist transfer to DB: {e}")

        return transfer

    @classmethod
    def update_progress(cls, transfer_id: str, bytes_transferred: int,
                        total_bytes: int) -> Optional[Dict]:
        """Update transfer progress."""
        if transfer_id in cls._active_transfers:
            progress = round((bytes_transferred / total_bytes * 100), 1) if total_bytes > 0 else 0
            cls._active_transfers[transfer_id]['progress'] = progress
            cls._active_transfers[transfer_id]['bytes_transferred'] = bytes_transferred
            return cls._active_transfers[transfer_id]
        return None

    @classmethod
    def complete_transfer(cls, transfer_id: str, success: bool = True) -> Optional[Dict]:
        """Mark transfer as complete and persist to database."""
        if transfer_id in cls._active_transfers:
            transfer = cls._active_transfers.pop(transfer_id)
            transfer['status'] = 'completed' if success else 'failed'
            transfer['completed_at'] = utcnow().strftime('%Y-%m-%d %H:%M:%S')

            # Update in DB
            try:
                from database import Database
                db = Database.get_db()
                db.transfers.update_one(
                    {'id': transfer_id},
                    {'$set': {
                        'status': transfer['status'],
                        'completed_at': utcnow(),
                        'progress': 100 if success else transfer.get('progress', 0),
                    }}
                )
            except Exception as e:
                logger.warning(f"Could not update transfer in DB: {e}")

            return transfer
        return None

    @classmethod
    def get_active_transfers(cls) -> List[Dict]:
        """Get all active transfers."""
        return list(cls._active_transfers.values())

    @classmethod
    def get_transfer_history(cls, limit: int = 20) -> List[Dict]:
        """Get recent transfer history from database."""
        try:
            from database import Database
            db = Database.get_db()
            transfers = list(db.transfers.find(
                {'status': {'$in': ['completed', 'failed']}},
                {'_id': 0}
            ).sort('started_at', -1).limit(limit))

            for t in transfers:
                if isinstance(t.get('started_at'), datetime):
                    t['started_at'] = t['started_at'].strftime('%Y-%m-%d %H:%M:%S')
                if isinstance(t.get('completed_at'), datetime):
                    t['completed_at'] = t['completed_at'].strftime('%Y-%m-%d %H:%M:%S')

            return transfers
        except Exception as e:
            logger.warning(f"Could not load transfer history: {e}")
            return []

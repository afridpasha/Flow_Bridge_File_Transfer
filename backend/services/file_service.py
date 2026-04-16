import logging
import os
from typing import List, Dict
from config import Config

logger = logging.getLogger(__name__)


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


class FileService:
    """Service for local filesystem file operations."""

    @staticmethod
    def get_file_list(folder_path: str) -> List[Dict]:
        """Get list of files in a local folder."""
        files = []
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            return files

        try:
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
                    files.append({
                        'filename': filename,
                        'size': stat.st_size,
                        'size_formatted': format_size(stat.st_size),
                        'extension': ext,
                        'modified': stat.st_mtime,
                    })
        except PermissionError as e:
            logger.error(f"Permission error reading {folder_path}: {e}")

        return sorted(files, key=lambda x: x['modified'], reverse=True)

    @staticmethod
    def get_storage_stats() -> Dict:
        """Get storage statistics across all local folders."""
        stats = {
            'uploads': 0,
            'downloads': 0,
            'shared': 0,
            'total_size': 0,
            'total_size_formatted': '0 B'
        }

        for folder_key, folder_path in [
            ('uploads', Config.UPLOAD_FOLDER),
            ('downloads', Config.DOWNLOAD_FOLDER),
            ('shared', Config.SHARED_FOLDER),
        ]:
            if os.path.exists(folder_path):
                count = 0
                size = 0
                for f in os.listdir(folder_path):
                    fp = os.path.join(folder_path, f)
                    if os.path.isfile(fp):
                        count += 1
                        size += os.path.getsize(fp)
                stats[folder_key] = count
                stats['total_size'] += size

        stats['total_size_formatted'] = format_size(stats['total_size'])
        return stats

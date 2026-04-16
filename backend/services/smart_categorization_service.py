"""
Smart Categorization Service — Auto-categorize files by type, content, and patterns.
"""
import re
from collections import defaultdict


CATEGORY_RULES = {
    "image": {
        "extensions": {"jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "ico", "tiff", "heic"},
        "mime_prefixes": ["image/"],
    },
    "video": {
        "extensions": {"mp4", "avi", "mov", "mkv", "webm", "flv", "wmv", "m4v", "3gp"},
        "mime_prefixes": ["video/"],
    },
    "audio": {
        "extensions": {"mp3", "wav", "flac", "aac", "ogg", "m4a", "wma", "opus"},
        "mime_prefixes": ["audio/"],
    },
    "document": {
        "extensions": {"pdf", "doc", "docx", "odt", "rtf", "txt", "md", "rst"},
        "mime_prefixes": ["application/pdf", "application/msword", "text/"],
    },
    "spreadsheet": {
        "extensions": {"xls", "xlsx", "csv", "ods", "tsv"},
        "mime_prefixes": ["application/vnd.ms-excel", "text/csv"],
    },
    "presentation": {
        "extensions": {"ppt", "pptx", "odp", "key"},
        "mime_prefixes": ["application/vnd.ms-powerpoint"],
    },
    "code": {
        "extensions": {"py", "js", "ts", "java", "c", "cpp", "cs", "go", "rb", "php",
                       "swift", "kt", "rs", "html", "css", "json", "xml", "yaml", "yml",
                       "sh", "bash", "sql", "r", "scala", "lua"},
        "mime_prefixes": ["text/x-", "application/x-"],
    },
    "archive": {
        "extensions": {"zip", "tar", "gz", "bz2", "7z", "rar", "xz", "tgz"},
        "mime_prefixes": ["application/zip", "application/x-tar"],
    },
    "executable": {
        "extensions": {"exe", "msi", "dmg", "deb", "rpm", "apk", "app"},
        "mime_prefixes": ["application/x-executable", "application/x-msdownload"],
    },
    "font": {
        "extensions": {"ttf", "otf", "woff", "woff2", "eot"},
        "mime_prefixes": ["font/"],
    },
}

TAGS_BY_CATEGORY = {
    "image": ["visual", "media", "photo"],
    "video": ["media", "video", "streaming"],
    "audio": ["media", "audio", "music"],
    "document": ["document", "text", "readable"],
    "spreadsheet": ["data", "tabular", "analysis"],
    "presentation": ["slides", "presentation", "visual"],
    "code": ["code", "programming", "development"],
    "archive": ["compressed", "bundle", "backup"],
    "executable": ["binary", "program", "executable"],
    "font": ["typography", "design", "font"],
}


class SmartCategorizationService:
    def __init__(self):
        self._stats = defaultdict(int)

    def categorize(self, filename, mime_type=None, size=None):
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        category = self._by_extension(ext) or self._by_mime(mime_type or "") or "other"
        tags = list(TAGS_BY_CATEGORY.get(category, ["uncategorized"]))
        tags += self._size_tags(size)
        self._stats[category] += 1
        return {
            "category": category,
            "tags": tags,
            "extension": ext,
            "confidence": "high" if self._by_extension(ext) else "medium",
        }

    def _by_extension(self, ext):
        for cat, rules in CATEGORY_RULES.items():
            if ext in rules["extensions"]:
                return cat
        return None

    def _by_mime(self, mime_type):
        for cat, rules in CATEGORY_RULES.items():
            for prefix in rules["mime_prefixes"]:
                if mime_type.startswith(prefix):
                    return cat
        return None

    def _size_tags(self, size):
        if size is None:
            return []
        if size < 1024 * 100:
            return ["small"]
        if size < 1024 * 1024 * 10:
            return ["medium"]
        return ["large"]

    def bulk_categorize(self, files):
        return [
            {"file": f.get("filename", ""), **self.categorize(f.get("filename", ""), f.get("content_type"), f.get("size"))}
            for f in files
        ]

    def stats(self):
        return {
            "categorized_files": sum(self._stats.values()),
            "by_category": dict(self._stats),
            "supported_categories": list(CATEGORY_RULES.keys()),
        }


_categorization_service = SmartCategorizationService()


def get_categorization_service():
    return _categorization_service

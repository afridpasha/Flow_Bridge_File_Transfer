"""
Differential Sync Service — Efficient document synchronization using diffs.
"""
import difflib
import hashlib
import time


class DocumentVersion:
    def __init__(self, content, version=0):
        self.content = content
        self.version = version
        self.timestamp = time.time()
        self.checksum = hashlib.md5(content.encode()).hexdigest()


class DifferentialSyncManager:
    def __init__(self):
        self.documents = {}  # doc_id -> DocumentVersion
        self.history = {}    # doc_id -> list of patches

    def create_document(self, doc_id, content=""):
        self.documents[doc_id] = DocumentVersion(content)
        self.history[doc_id] = []
        return {"doc_id": doc_id, "version": 0, "checksum": self.documents[doc_id].checksum}

    def get_document(self, doc_id):
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        return {"content": doc.content, "version": doc.version, "checksum": doc.checksum}

    def compute_diff(self, old_content, new_content):
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
        return "\n".join(diff)

    def apply_patch(self, doc_id, new_content, client_version):
        doc = self.documents.get(doc_id)
        if not doc:
            return {"success": False, "error": "Document not found"}

        if client_version != doc.version:
            # Return current state for client to reconcile
            return {
                "success": False,
                "conflict": True,
                "current_version": doc.version,
                "current_content": doc.content,
            }

        diff = self.compute_diff(doc.content, new_content)
        old_version = doc.version
        doc.content = new_content
        doc.version += 1
        doc.timestamp = time.time()
        doc.checksum = hashlib.md5(new_content.encode()).hexdigest()

        self.history[doc_id].append({
            "from_version": old_version,
            "to_version": doc.version,
            "diff": diff,
            "timestamp": doc.timestamp,
        })

        # Keep only last 50 patches
        if len(self.history[doc_id]) > 50:
            self.history[doc_id] = self.history[doc_id][-50:]

        return {"success": True, "version": doc.version, "checksum": doc.checksum}

    def get_diff(self, doc_id, from_version):
        doc = self.documents.get(doc_id)
        if not doc:
            return None
        patches = [p for p in self.history.get(doc_id, []) if p["from_version"] >= from_version]
        return {"patches": patches, "current_version": doc.version}

    def stats(self):
        return {
            "documents": len(self.documents),
            "total_patches": sum(len(h) for h in self.history.values()),
        }


_sync_manager = DifferentialSyncManager()


def get_sync_manager():
    return _sync_manager


# Alias used in advanced_routes
sync_manager = _sync_manager

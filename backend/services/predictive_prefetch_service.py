"""
Predictive Prefetch Service — Predict and prefetch files users are likely to access.
"""
import time
from collections import defaultdict, deque


class AccessPattern:
    def __init__(self, window=100):
        self.window = window
        self.history = deque(maxlen=window)
        self.transitions = defaultdict(lambda: defaultdict(int))

    def record(self, file_id):
        if self.history:
            prev = self.history[-1]
            self.transitions[prev][file_id] += 1
        self.history.append(file_id)

    def predict_next(self, file_id, top_n=3):
        candidates = self.transitions.get(file_id, {})
        if not candidates:
            return []
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [fid for fid, _ in sorted_candidates[:top_n]]


class PrefetchCache:
    def __init__(self, max_size=50):
        self.max_size = max_size
        self.cache = {}
        self.access_times = {}

    def put(self, file_id, metadata):
        if len(self.cache) >= self.max_size:
            # Evict LRU
            oldest = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest]
            del self.access_times[oldest]
        self.cache[file_id] = metadata
        self.access_times[file_id] = time.time()

    def get(self, file_id):
        if file_id in self.cache:
            self.access_times[file_id] = time.time()
            return self.cache[file_id]
        return None

    def is_cached(self, file_id):
        return file_id in self.cache

    def stats(self):
        return {
            "cached_files": len(self.cache),
            "max_size": self.max_size,
            "hit_rate": getattr(self, "_hits", 0) / max(getattr(self, "_requests", 1), 1),
        }


class PrefetchService:
    def __init__(self):
        self.patterns = defaultdict(AccessPattern)
        self.cache = PrefetchCache()
        self.prefetch_queue = []

    def record_access(self, user_id, file_id):
        self.patterns[user_id].record(file_id)
        predictions = self.patterns[user_id].predict_next(file_id)
        for predicted_id in predictions:
            if not self.cache.is_cached(predicted_id):
                self.prefetch_queue.append({"user_id": user_id, "file_id": predicted_id, "queued_at": time.time()})

    def get_predictions(self, user_id, file_id, top_n=3):
        return self.patterns[user_id].predict_next(file_id, top_n)

    def prefetch_metadata(self, file_id, metadata):
        self.cache.put(file_id, metadata)

    def get_cached(self, file_id):
        return self.cache.get(file_id)

    def get_queue(self):
        queue = self.prefetch_queue[:]
        self.prefetch_queue.clear()
        return queue

    def stats(self):
        return {
            "users_tracked": len(self.patterns),
            "cache": self.cache.stats(),
            "queue_size": len(self.prefetch_queue),
        }


_prefetch_service = PrefetchService()

# Alias used in advanced_routes
prefetch_service = _prefetch_service


def get_prefetch_service():
    return _prefetch_service

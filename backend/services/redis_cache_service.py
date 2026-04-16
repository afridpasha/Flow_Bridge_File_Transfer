"""
Cache Service — FlowBridge
───────────────────────────
Primary  : Upstash Redis REST API (Singapore ~60ms, free 10K cmd/day)
Fallback : InMemory (per-process, lost on restart — acceptable)

TTL strategy per key type:
  files:list:{uid}      5 min  — invalidated on upload/delete/rename
  user:storage:{uid}    5 min  — invalidated on upload/delete
  share:analytics:{tok} 2 min  — invalidated on each download
  codeshare:{slug}      30 sec — invalidated on each save
  user:profile:{uid}    10 min — invalidated on profile update
"""
import json
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── TTL constants (seconds) ────────────────────────────────────────────────
TTL_FILE_LIST      = 300    # 5 min
TTL_USER_STORAGE   = 300    # 5 min
TTL_SHARE_ANALYTICS= 120    # 2 min
TTL_CODESHARE      = 30     # 30 sec
TTL_USER_PROFILE   = 600    # 10 min


# ══════════════════════════════════════════════════════════════════════════
#  InMemory fallback
# ══════════════════════════════════════════════════════════════════════════

class _InMemoryCache:
    def __init__(self):
        self._store: dict = {}
        self._expiry: dict = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def set(self, key: str, value: Any, ttl: int = 300):
        with self._lock:
            self._store[key] = value
            self._expiry[key] = time.time() + ttl

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            exp = self._expiry.get(key)
            if exp and time.time() > exp:
                self._store.pop(key, None)
                self._expiry.pop(key, None)
                self._misses += 1
                return None
            if key in self._store:
                self._hits += 1
                return self._store[key]
            self._misses += 1
            return None

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)
            self._expiry.pop(key, None)

    def delete_pattern(self, prefix: str):
        """Delete all keys starting with prefix."""
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                self._store.pop(k, None)
                self._expiry.pop(k, None)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            'backend': 'memory',
            'keys': len(self._store),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': round(self._hits / total, 3) if total else 0,
        }


# ══════════════════════════════════════════════════════════════════════════
#  Upstash Redis REST client (no redis-py needed)
# ══════════════════════════════════════════════════════════════════════════

class _UpstashClient:
    """Thin wrapper around Upstash Redis REST API."""

    def __init__(self, url: str, token: str):
        self._url = url.rstrip('/')
        self._headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def _req(self, *args) -> Any:
        import urllib.request
        import urllib.error
        payload = json.dumps(list(args)).encode()
        req = urllib.request.Request(
            self._url,
            data=payload,
            headers=self._headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return json.loads(resp.read()).get('result')
        except urllib.error.URLError as e:
            raise ConnectionError(f"Upstash request failed: {e}")

    def set(self, key: str, value: str, ttl: int) -> bool:
        return self._req('SET', key, value, 'EX', ttl) == 'OK'

    def get(self, key: str) -> Optional[str]:
        return self._req('GET', key)

    def delete(self, key: str) -> int:
        return self._req('DEL', key)

    def keys(self, pattern: str) -> list:
        result = self._req('KEYS', pattern)
        return result if isinstance(result, list) else []

    def ping(self) -> bool:
        return self._req('PING') == 'PONG'


# ══════════════════════════════════════════════════════════════════════════
#  CacheService — public interface
# ══════════════════════════════════════════════════════════════════════════

class CacheService:
    def __init__(self):
        self._upstash: Optional[_UpstashClient] = None
        self._mem = _InMemoryCache()
        self._try_connect()

    def _try_connect(self):
        from config import Config
        url   = getattr(Config, 'UPSTASH_REDIS_REST_URL', '')
        token = getattr(Config, 'UPSTASH_REDIS_REST_TOKEN', '')
        if not url or not token:
            logger.info("Upstash Redis not configured — using InMemory cache")
            return
        try:
            client = _UpstashClient(url, token)
            client.ping()
            self._upstash = client
            logger.info("✅ Upstash Redis connected")
        except Exception as e:
            logger.warning(f"Upstash Redis unavailable: {e} — using InMemory fallback")

    # ── Core operations ────────────────────────────────────────────────────

    def set(self, key: str, value: Any, ttl: int = 300):
        serialized = json.dumps(value, default=str)
        if self._upstash:
            try:
                self._upstash.set(key, serialized, ttl)
                return
            except Exception as e:
                logger.warning(f"Upstash set failed: {e}")
        self._mem.set(key, value, ttl)

    def get(self, key: str) -> Optional[Any]:
        if self._upstash:
            try:
                raw = self._upstash.get(key)
                if raw is not None:
                    return json.loads(raw)
                return None
            except Exception as e:
                logger.warning(f"Upstash get failed: {e}")
        return self._mem.get(key)

    def delete(self, key: str):
        if self._upstash:
            try:
                self._upstash.delete(key)
            except Exception as e:
                logger.warning(f"Upstash delete failed: {e}")
        self._mem.delete(key)

    def delete_pattern(self, prefix: str):
        """Delete all keys matching prefix* — used for cache invalidation."""
        if self._upstash:
            try:
                keys = self._upstash.keys(f"{prefix}*")
                for k in keys:
                    self._upstash.delete(k)
            except Exception as e:
                logger.warning(f"Upstash delete_pattern failed: {e}")
        self._mem.delete_pattern(prefix)

    # ── Typed helpers (enforce correct TTLs) ──────────────────────────────

    def set_file_list(self, user_id: str, data: Any):
        self.set(f"files:list:{user_id}", data, TTL_FILE_LIST)

    def get_file_list(self, user_id: str) -> Optional[Any]:
        return self.get(f"files:list:{user_id}")

    def invalidate_file_list(self, user_id: str):
        self.delete(f"files:list:{user_id}")

    def set_user_storage(self, user_id: str, data: Any):
        self.set(f"user:storage:{user_id}", data, TTL_USER_STORAGE)

    def get_user_storage(self, user_id: str) -> Optional[Any]:
        return self.get(f"user:storage:{user_id}")

    def invalidate_user_storage(self, user_id: str):
        self.delete(f"user:storage:{user_id}")

    def set_share_analytics(self, token: str, data: Any):
        self.set(f"share:analytics:{token}", data, TTL_SHARE_ANALYTICS)

    def get_share_analytics(self, token: str) -> Optional[Any]:
        return self.get(f"share:analytics:{token}")

    def invalidate_share_analytics(self, token: str):
        self.delete(f"share:analytics:{token}")

    def set_codeshare(self, slug: str, data: Any):
        self.set(f"codeshare:{slug}", data, TTL_CODESHARE)

    def get_codeshare(self, slug: str) -> Optional[Any]:
        return self.get(f"codeshare:{slug}")

    def invalidate_codeshare(self, slug: str):
        self.delete(f"codeshare:{slug}")

    def set_user_profile(self, user_id: str, data: Any):
        self.set(f"user:profile:{user_id}", data, TTL_USER_PROFILE)

    def get_user_profile(self, user_id: str) -> Optional[Any]:
        return self.get(f"user:profile:{user_id}")

    def invalidate_user_profile(self, user_id: str):
        self.delete(f"user:profile:{user_id}")

    def stats(self) -> dict:
        if self._upstash:
            return {'backend': 'upstash_redis', 'status': 'connected'}
        return self._mem.stats()

    @property
    def is_upstash_connected(self) -> bool:
        return self._upstash is not None


# ── Singleton ──────────────────────────────────────────────────────────────

_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service

"""
Bloom Filter Service — Probabilistic duplicate detection.
"""
import hashlib
import math


class BloomFilter:
    def __init__(self, capacity=10000, error_rate=0.01):
        self.capacity = capacity
        self.error_rate = error_rate
        self.bit_count = self._optimal_bit_count(capacity, error_rate)
        self.hash_count = self._optimal_hash_count(self.bit_count, capacity)
        self.bit_array = bytearray(math.ceil(self.bit_count / 8))
        self.count = 0

    def _optimal_bit_count(self, n, p):
        return int(-n * math.log(p) / (math.log(2) ** 2))

    def _optimal_hash_count(self, m, n):
        return max(1, int((m / n) * math.log(2)))

    def _hashes(self, item):
        if isinstance(item, str):
            item = item.encode()
        h1 = int(hashlib.md5(item).hexdigest(), 16)
        h2 = int(hashlib.sha1(item).hexdigest(), 16)
        for i in range(self.hash_count):
            yield (h1 + i * h2) % self.bit_count

    def add(self, item):
        for bit in self._hashes(item):
            self.bit_array[bit // 8] |= (1 << (bit % 8))
        self.count += 1

    def contains(self, item):
        return all(
            self.bit_array[bit // 8] & (1 << (bit % 8))
            for bit in self._hashes(item)
        )

    def stats(self):
        return {
            "capacity": self.capacity,
            "count": self.count,
            "error_rate": self.error_rate,
            "bit_count": self.bit_count,
            "hash_count": self.hash_count,
            "fill_ratio": self.count / self.capacity if self.capacity else 0,
        }


# Global instance
_bloom_filter = BloomFilter()


def get_bloom_filter():
    return _bloom_filter

"""
HyperLogLog Service — Approximate cardinality estimation.
"""
import hashlib
import math


class HyperLogLog:
    def __init__(self, precision=14):
        self.precision = precision
        self.m = 1 << precision  # number of registers
        self.registers = [0] * self.m
        self.alpha = self._alpha(self.m)

    def _alpha(self, m):
        if m == 16:
            return 0.673
        if m == 32:
            return 0.697
        if m == 64:
            return 0.709
        return 0.7213 / (1 + 1.079 / m)

    def _hash(self, item):
        if isinstance(item, str):
            item = item.encode()
        return int(hashlib.sha256(item).hexdigest(), 16)

    def _leading_zeros(self, bits, max_bits):
        if bits == 0:
            return max_bits
        count = 0
        mask = 1 << (max_bits - 1)
        while mask and not (bits & mask):
            count += 1
            mask >>= 1
        return count + 1

    def add(self, item):
        h = self._hash(item)
        total_bits = 256
        register_bits = total_bits - self.precision
        j = h >> register_bits
        w = h & ((1 << register_bits) - 1)
        self.registers[j] = max(self.registers[j], self._leading_zeros(w, register_bits))

    def count(self):
        z = sum(2.0 ** (-r) for r in self.registers)
        estimate = self.alpha * self.m * self.m / z
        if estimate <= 2.5 * self.m:
            zeros = self.registers.count(0)
            if zeros:
                estimate = self.m * math.log(self.m / zeros)
        return int(estimate)

    def merge(self, other):
        if self.m != other.m:
            raise ValueError("Cannot merge HyperLogLog with different precision")
        for i in range(self.m):
            self.registers[i] = max(self.registers[i], other.registers[i])

    def stats(self):
        return {
            "precision": self.precision,
            "registers": self.m,
            "estimated_count": self.count(),
            "memory_bytes": self.m,
        }


class HyperLogLogManager:
    def __init__(self):
        self.counters = {}

    def get_counter(self, name, precision=14):
        if name not in self.counters:
            self.counters[name] = HyperLogLog(precision)
        return self.counters[name]

    def add(self, counter_name, item):
        self.get_counter(counter_name).add(item)

    def estimate(self, counter_name):
        counter = self.counters.get(counter_name)
        return counter.count() if counter else 0

    def stats(self):
        return {
            "counters": len(self.counters),
            "estimates": {name: c.count() for name, c in self.counters.items()},
        }


_hll_manager = HyperLogLogManager()


def get_hll_manager():
    return _hll_manager

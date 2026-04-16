"""
CRDT Service — Conflict-free Replicated Data Types for collaborative editing.
"""
import time
import uuid
from collections import defaultdict


class GCounter:
    """Grow-only counter CRDT."""
    def __init__(self, node_id=None):
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self.counts = defaultdict(int)

    def increment(self, amount=1):
        self.counts[self.node_id] += amount

    def value(self):
        return sum(self.counts.values())

    def merge(self, other):
        for node, count in other.counts.items():
            self.counts[node] = max(self.counts[node], count)

    def state(self):
        return dict(self.counts)


class LWWRegister:
    """Last-Write-Wins Register CRDT."""
    def __init__(self):
        self.value = None
        self.timestamp = 0
        self.node_id = str(uuid.uuid4())[:8]

    def write(self, value):
        self.timestamp = time.time()
        self.value = value

    def read(self):
        return self.value

    def merge(self, other_value, other_timestamp):
        if other_timestamp > self.timestamp:
            self.value = other_value
            self.timestamp = other_timestamp

    def state(self):
        return {"value": self.value, "timestamp": self.timestamp}


class ORSet:
    """Observed-Remove Set CRDT."""
    def __init__(self):
        self.added = {}    # element -> set of unique tags
        self.removed = {}  # element -> set of unique tags

    def add(self, element):
        tag = str(uuid.uuid4())
        if element not in self.added:
            self.added[element] = set()
        self.added[element].add(tag)

    def remove(self, element):
        if element in self.added:
            if element not in self.removed:
                self.removed[element] = set()
            self.removed[element].update(self.added[element])

    def contains(self, element):
        added_tags = self.added.get(element, set())
        removed_tags = self.removed.get(element, set())
        return bool(added_tags - removed_tags)

    def elements(self):
        return [e for e in self.added if self.contains(e)]

    def merge(self, other):
        for elem, tags in other.added.items():
            if elem not in self.added:
                self.added[elem] = set()
            self.added[elem].update(tags)
        for elem, tags in other.removed.items():
            if elem not in self.removed:
                self.removed[elem] = set()
            self.removed[elem].update(tags)


class CRDTManager:
    def __init__(self):
        self.counters = {}
        self.registers = {}
        self.sets = {}

    def get_counter(self, name):
        if name not in self.counters:
            self.counters[name] = GCounter()
        return self.counters[name]

    def get_register(self, name):
        if name not in self.registers:
            self.registers[name] = LWWRegister()
        return self.registers[name]

    def get_set(self, name):
        if name not in self.sets:
            self.sets[name] = ORSet()
        return self.sets[name]

    def stats(self):
        return {
            "counters": len(self.counters),
            "registers": len(self.registers),
            "sets": len(self.sets),
        }


_crdt_manager = CRDTManager()


def get_crdt_manager():
    return _crdt_manager

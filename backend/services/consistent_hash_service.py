"""
Consistent Hash Service — Distribute files across storage nodes.
"""
import hashlib
import bisect


class ConsistentHashRing:
    def __init__(self, replicas=150):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []

    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node):
        for i in range(self.replicas):
            vnode = f"{node}:{i}"
            h = self._hash(vnode)
            self.ring[h] = node
            bisect.insort(self.sorted_keys, h)

    def remove_node(self, node):
        for i in range(self.replicas):
            vnode = f"{node}:{i}"
            h = self._hash(vnode)
            if h in self.ring:
                del self.ring[h]
                idx = bisect.bisect_left(self.sorted_keys, h)
                if idx < len(self.sorted_keys) and self.sorted_keys[idx] == h:
                    self.sorted_keys.pop(idx)

    def get_node(self, key):
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self.sorted_keys, h) % len(self.sorted_keys)
        return self.ring[self.sorted_keys[idx]]

    def get_nodes(self):
        return list(set(self.ring.values()))

    def stats(self):
        nodes = self.get_nodes()
        distribution = {}
        for node in nodes:
            distribution[node] = sum(1 for v in self.ring.values() if v == node)
        return {
            "nodes": len(nodes),
            "virtual_nodes": len(self.ring),
            "replicas_per_node": self.replicas,
            "distribution": distribution,
        }


# Global instance
_ring = ConsistentHashRing()
_ring.add_node("storage-node-1")
_ring.add_node("storage-node-2")
_ring.add_node("storage-node-3")


def get_hash_ring():
    return _ring

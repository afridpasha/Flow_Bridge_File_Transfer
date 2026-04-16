"""
Merkle Tree Service — File integrity verification using hash trees.
"""
import hashlib
import math


def _sha256(data):
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


class MerkleNode:
    def __init__(self, left=None, right=None, data=None):
        self.left = left
        self.right = right
        self.hash = _sha256(data) if data else self._compute_hash()

    def _compute_hash(self):
        left_hash = self.left.hash if self.left else ""
        right_hash = self.right.hash if self.right else ""
        return _sha256(left_hash + right_hash)


class MerkleTree:
    def __init__(self, data_blocks):
        self.leaves = [MerkleNode(data=block) for block in data_blocks]
        self.root = self._build(self.leaves) if self.leaves else None

    def _build(self, nodes):
        if len(nodes) == 1:
            return nodes[0]
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])  # duplicate last node
        parents = []
        for i in range(0, len(nodes), 2):
            parents.append(MerkleNode(left=nodes[i], right=nodes[i + 1]))
        return self._build(parents)

    def get_root_hash(self):
        return self.root.hash if self.root else None

    def verify(self, data_blocks):
        new_tree = MerkleTree(data_blocks)
        return new_tree.get_root_hash() == self.get_root_hash()

    def get_proof(self, index):
        """Get Merkle proof for a leaf at given index."""
        if index >= len(self.leaves):
            return None
        proof = []
        nodes = self.leaves[:]
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        while len(nodes) > 1:
            sibling_idx = index ^ 1
            if sibling_idx < len(nodes):
                proof.append({"hash": nodes[sibling_idx].hash, "position": "right" if index % 2 == 0 else "left"})
            index //= 2
            parents = []
            for i in range(0, len(nodes), 2):
                parents.append(MerkleNode(left=nodes[i], right=nodes[i + 1] if i + 1 < len(nodes) else nodes[i]))
            nodes = parents
        return proof

    def stats(self):
        return {
            "leaves": len(self.leaves),
            "depth": math.ceil(math.log2(len(self.leaves))) if self.leaves else 0,
            "root_hash": self.get_root_hash(),
        }


class MerkleTreeManager:
    def __init__(self):
        self.trees = {}

    def create_tree(self, name, blocks):
        self.trees[name] = MerkleTree(blocks)
        return self.trees[name].get_root_hash()

    def verify_tree(self, name, blocks):
        tree = self.trees.get(name)
        if not tree:
            return False
        return tree.verify(blocks)

    def get_root(self, name):
        tree = self.trees.get(name)
        return tree.get_root_hash() if tree else None

    def stats(self):
        return {
            "trees": len(self.trees),
            "tree_stats": {name: t.stats() for name, t in self.trees.items()},
        }


_merkle_manager = MerkleTreeManager()


def get_merkle_manager():
    return _merkle_manager

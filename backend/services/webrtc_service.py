"""
WebRTC Signaling Service — Coordinate WebRTC peer connections.
"""
import time
import threading
from collections import defaultdict


class SignalingServer:
    def __init__(self, offer_ttl=60):
        self.offer_ttl = offer_ttl
        self._offers = {}   # (from, to) -> {offer, timestamp}
        self._answers = {}  # (from, to) -> {answer, timestamp}
        self._candidates = defaultdict(list)  # peer_id -> [candidates]
        self._rooms = {}    # room_id -> {peers: [], created_at}
        self._lock = threading.Lock()

    def _cleanup(self):
        now = time.time()
        with self._lock:
            expired_offers = [k for k, v in self._offers.items() if now - v["timestamp"] > self.offer_ttl]
            for k in expired_offers:
                del self._offers[k]
            expired_answers = [k for k, v in self._answers.items() if now - v["timestamp"] > self.offer_ttl]
            for k in expired_answers:
                del self._answers[k]

    def send_offer(self, from_peer, to_peer, offer):
        self._cleanup()
        with self._lock:
            self._offers[(from_peer, to_peer)] = {"offer": offer, "timestamp": time.time()}
        return True

    def get_offer(self, from_peer, to_peer):
        self._cleanup()
        entry = self._offers.get((from_peer, to_peer))
        return entry["offer"] if entry else None

    def send_answer(self, from_peer, to_peer, answer):
        self._cleanup()
        with self._lock:
            self._answers[(from_peer, to_peer)] = {"answer": answer, "timestamp": time.time()}
        return True

    def get_answer(self, from_peer, to_peer):
        self._cleanup()
        entry = self._answers.get((from_peer, to_peer))
        return entry["answer"] if entry else None

    def add_ice_candidate(self, peer_id, candidate):
        with self._lock:
            self._candidates[peer_id].append({"candidate": candidate, "timestamp": time.time()})

    def get_ice_candidates(self, peer_id):
        with self._lock:
            candidates = self._candidates.pop(peer_id, [])
        return [c["candidate"] for c in candidates]

    def create_room(self, room_id, peer_id):
        with self._lock:
            self._rooms[room_id] = {"peers": [peer_id], "created_at": time.time()}
        return True

    def join_room(self, room_id, peer_id):
        with self._lock:
            if room_id not in self._rooms:
                return False
            if peer_id not in self._rooms[room_id]["peers"]:
                self._rooms[room_id]["peers"].append(peer_id)
        return True

    def get_room_peers(self, room_id):
        room = self._rooms.get(room_id)
        return room["peers"] if room else []

    def leave_room(self, room_id, peer_id):
        with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id]["peers"] = [
                    p for p in self._rooms[room_id]["peers"] if p != peer_id
                ]
                if not self._rooms[room_id]["peers"]:
                    del self._rooms[room_id]

    def stats(self):
        return {
            "pending_offers": len(self._offers),
            "pending_answers": len(self._answers),
            "active_rooms": len(self._rooms),
            "peers_with_candidates": len(self._candidates),
        }


_signaling_server = SignalingServer()

# Alias used in advanced_routes
signaling_server = _signaling_server


def get_signaling_server():
    return _signaling_server

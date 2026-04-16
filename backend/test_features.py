"""
Feature-specific tests for FlowBridge advanced services.
Run from the backend directory: python test_features.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))


def test_bloom_filter():
    from services.bloom_filter_service import get_bloom_filter
    bf = get_bloom_filter()
    bf.add("file1.txt")
    bf.add("file2.txt")
    assert bf.contains("file1.txt"), "Should contain file1.txt"
    assert not bf.contains("file3.txt"), "Should not contain file3.txt"
    print("[PASS] Bloom Filter")


def test_consistent_hash():
    from services.consistent_hash_service import get_hash_ring
    ring = get_hash_ring()
    node = ring.get_node("my-file.txt")
    assert node is not None, "Should return a node"
    assert node in ring.get_nodes(), "Node should be in ring"
    print("[PASS] Consistent Hash")


def test_crdt():
    from services.crdt_service import get_crdt_manager
    mgr = get_crdt_manager()
    counter = mgr.get_counter("test")
    counter.increment(5)
    assert counter.value() == 5
    reg = mgr.get_register("test_reg")
    reg.write("hello")
    assert reg.read() == "hello"
    s = mgr.get_set("test_set")
    s.add("item1")
    assert s.contains("item1")
    s.remove("item1")
    assert not s.contains("item1")
    print("[PASS] CRDT")


def test_differential_sync():
    from services.differential_sync_service import get_sync_manager
    mgr = get_sync_manager()
    mgr.create_document("doc1", "Hello World")
    doc = mgr.get_document("doc1")
    assert doc["content"] == "Hello World"
    result = mgr.apply_patch("doc1", "Hello FlowBridge", 0)
    assert result["success"]
    assert result["version"] == 1
    print("[PASS] Differential Sync")


def test_hyperloglog():
    from services.hyperloglog_service import get_hll_manager
    mgr = get_hll_manager()
    for i in range(1000):
        mgr.add("unique_visitors", f"user_{i}")
    estimate = mgr.estimate("unique_visitors")
    assert 800 < estimate < 1200, f"Estimate {estimate} out of range"
    print("[PASS] HyperLogLog")


def test_merkle_tree():
    from services.merkle_tree_service import get_merkle_manager
    mgr = get_merkle_manager()
    blocks = ["block1", "block2", "block3", "block4"]
    root = mgr.create_tree("test_tree", blocks)
    assert root is not None
    assert mgr.verify_tree("test_tree", blocks)
    assert not mgr.verify_tree("test_tree", ["block1", "TAMPERED", "block3", "block4"])
    print("[PASS] Merkle Tree")


def test_predictive_prefetch():
    from services.predictive_prefetch_service import get_prefetch_service
    svc = get_prefetch_service()
    svc.record_access("user1", "file_a")
    svc.record_access("user1", "file_b")
    svc.record_access("user1", "file_a")
    svc.record_access("user1", "file_b")
    predictions = svc.get_predictions("user1", "file_a")
    assert "file_b" in predictions
    print("[PASS] Predictive Prefetch")


def test_redis_cache():
    from services.redis_cache_service import get_cache_service
    cache = get_cache_service()
    cache.set("test_key", {"value": 42}, ttl=60)
    result = cache.get("test_key")
    assert result == {"value": 42}
    cache.delete("test_key")
    assert cache.get("test_key") is None
    print("[PASS] Redis Cache (fallback)")


def test_smart_categorization():
    from services.smart_categorization_service import get_categorization_service
    svc = get_categorization_service()
    result = svc.categorize("photo.jpg", "image/jpeg", 1024 * 500)
    assert result["category"] == "image"
    assert "visual" in result["tags"]
    result2 = svc.categorize("script.py", "text/x-python", 2048)
    assert result2["category"] == "code"
    print("[PASS] Smart Categorization")


def test_wasm():
    from services.wasm_service import get_wasm_service
    svc = get_wasm_service()
    modules = svc.list_modules()
    assert len(modules) > 0
    result = svc.compute_checksum("test content")
    assert "sha256" in result
    print("[PASS] WASM Service")


def test_webrtc():
    from services.webrtc_service import get_signaling_server
    server = get_signaling_server()
    server.send_offer("peer_a", "peer_b", {"type": "offer", "sdp": "v=0..."})
    offer = server.get_offer("peer_a", "peer_b")
    assert offer is not None
    server.send_answer("peer_a", "peer_b", {"type": "answer", "sdp": "v=0..."})
    answer = server.get_answer("peer_a", "peer_b")
    assert answer is not None
    print("[PASS] WebRTC Signaling")


if __name__ == "__main__":
    print("FlowBridge — Feature Unit Tests\n" + "=" * 40)
    tests = [
        test_bloom_filter,
        test_consistent_hash,
        test_crdt,
        test_differential_sync,
        test_hyperloglog,
        test_merkle_tree,
        test_predictive_prefetch,
        test_redis_cache,
        test_smart_categorization,
        test_wasm,
        test_webrtc,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
    print(f"\n{'='*40}")
    print(f"Results: {passed}/{len(tests)} passed")

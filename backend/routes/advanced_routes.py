"""
Advanced Routes — Experimental and advanced feature endpoints.
"""
from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required as jwt_required
from services.wasm_service import wasm_service
from services.crdt_service import get_crdt_manager
from services.graphql_service import get_graphql_executor
from services.webrtc_service import signaling_server
from services.compression_service import CompressionService, CompressionAlgorithm
from services.differential_sync_service import sync_manager
from services.predictive_prefetch_service import prefetch_service

advanced_bp = Blueprint('advanced', __name__, url_prefix='/api/advanced')


# ========== WASM ==========

@advanced_bp.route('/wasm/modules', methods=['GET'])
@jwt_required
def list_wasm_modules(current_user):
    return jsonify({"success": True, "modules": wasm_service.list_modules()})


@advanced_bp.route('/wasm/module/<module_name>', methods=['GET'])
@jwt_required
def get_wasm_module(current_user, module_name):
    info = wasm_service.get_module_info(module_name)
    if not info:
        return jsonify({"success": False, "error": "Module not found"}), 404
    wat = wasm_service.get_module_wat(module_name)
    return jsonify({"success": True, "module": info, "wat": wat})


@advanced_bp.route('/wasm/checksum', methods=['POST'])
@jwt_required
def wasm_checksum(current_user):
    data = request.get_json() or {}
    content = data.get('content', '')
    result = wasm_service.compute_checksum(content)
    return jsonify({"success": True, "result": result})


@advanced_bp.route('/wasm/stats', methods=['GET'])
@jwt_required
def wasm_stats(current_user):
    return jsonify({"success": True, "stats": wasm_service.stats()})


# ========== CRDT ==========

@advanced_bp.route('/crdt/counter/<name>/increment', methods=['POST'])
@jwt_required
def crdt_increment(current_user, name):
    data = request.get_json() or {}
    amount = data.get('amount', 1)
    manager = get_crdt_manager()
    counter = manager.get_counter(name)
    counter.increment(amount)
    return jsonify({"success": True, "name": name, "value": counter.value()})


@advanced_bp.route('/crdt/counter/<name>', methods=['GET'])
@jwt_required
def crdt_get_counter(current_user, name):
    manager = get_crdt_manager()
    counter = manager.get_counter(name)
    return jsonify({"success": True, "name": name, "value": counter.value(), "state": counter.state()})


@advanced_bp.route('/crdt/register/<name>', methods=['POST'])
@jwt_required
def crdt_write_register(current_user, name):
    data = request.get_json() or {}
    value = data.get('value')
    manager = get_crdt_manager()
    reg = manager.get_register(name)
    reg.write(value)
    return jsonify({"success": True, "name": name, "state": reg.state()})


@advanced_bp.route('/crdt/register/<name>', methods=['GET'])
@jwt_required
def crdt_read_register(current_user, name):
    manager = get_crdt_manager()
    reg = manager.get_register(name)
    return jsonify({"success": True, "name": name, "value": reg.read(), "state": reg.state()})


@advanced_bp.route('/crdt/set/<name>/add', methods=['POST'])
@jwt_required
def crdt_set_add(current_user, name):
    data = request.get_json() or {}
    element = data.get('element')
    manager = get_crdt_manager()
    s = manager.get_set(name)
    s.add(element)
    return jsonify({"success": True, "name": name, "elements": s.elements()})


@advanced_bp.route('/crdt/set/<name>/remove', methods=['POST'])
@jwt_required
def crdt_set_remove(current_user, name):
    data = request.get_json() or {}
    element = data.get('element')
    manager = get_crdt_manager()
    s = manager.get_set(name)
    s.remove(element)
    return jsonify({"success": True, "name": name, "elements": s.elements()})


@advanced_bp.route('/crdt/set/<name>', methods=['GET'])
@jwt_required
def crdt_get_set(current_user, name):
    manager = get_crdt_manager()
    s = manager.get_set(name)
    return jsonify({"success": True, "name": name, "elements": s.elements()})


@advanced_bp.route('/crdt/stats', methods=['GET'])
@jwt_required
def crdt_stats(current_user):
    return jsonify({"success": True, "stats": get_crdt_manager().stats()})


# ========== GraphQL ==========

@advanced_bp.route('/graphql', methods=['POST'])
@jwt_required
def graphql_query(current_user):
    data = request.get_json() or {}
    query = data.get('query', '')
    variables = data.get('variables')
    if not query:
        return jsonify({"success": False, "error": "Query required"}), 400
    executor = get_graphql_executor()
    result = executor.execute(query, variables, context={"user": current_user})
    return jsonify({"success": True, **result})


@advanced_bp.route('/graphql/schema', methods=['GET'])
@jwt_required
def graphql_schema(current_user):
    try:
        from services.graphql_service import GraphQLSchema
        schema = GraphQLSchema()
    except Exception:
        pass
    executor = get_graphql_executor()
    return jsonify({"success": True, "schema": executor.get_schema_sdl()})


@advanced_bp.route('/graphql/stats', methods=['GET'])
@jwt_required
def graphql_stats(current_user):
    return jsonify({"success": True, "stats": get_graphql_executor().stats()})


# ========== WebRTC Signaling ==========

@advanced_bp.route('/webrtc/register', methods=['POST'])
def webrtc_register():
    """Register a peer with the signaling server (no auth required for WebRTC)."""
    data = request.get_json() or {}
    peer_id = data.get('peer_id', '')
    if not peer_id:
        return jsonify({"success": False, "error": "peer_id required"}), 400
    return jsonify({"success": True, "peer_id": peer_id})


@advanced_bp.route('/webrtc/offer', methods=['POST'])
def webrtc_send_offer():
    data = request.get_json() or {}
    from_peer = data.get('from', '')
    to_peer = data.get('to', '')
    offer = data.get('offer')
    if not all([from_peer, to_peer, offer]):
        return jsonify({"success": False, "error": "from, to, offer required"}), 400
    success = signaling_server.send_offer(from_peer, to_peer, offer)
    return jsonify({"success": success})


@advanced_bp.route('/webrtc/offer/<from_peer>/<to_peer>', methods=['GET'])
def webrtc_get_offer(from_peer, to_peer):
    offer = signaling_server.get_offer(from_peer, to_peer)
    return jsonify({"success": True, "offer": offer})


@advanced_bp.route('/webrtc/answer', methods=['POST'])
def webrtc_send_answer():
    data = request.get_json() or {}
    from_peer = data.get('from', '')
    to_peer = data.get('to', '')
    answer = data.get('answer')
    if not all([from_peer, to_peer, answer]):
        return jsonify({"success": False, "error": "from, to, answer required"}), 400
    success = signaling_server.send_answer(from_peer, to_peer, answer)
    return jsonify({"success": success})


@advanced_bp.route('/webrtc/answer/<from_peer>/<to_peer>', methods=['GET'])
def webrtc_get_answer(from_peer, to_peer):
    answer = signaling_server.get_answer(from_peer, to_peer)
    return jsonify({"success": True, "answer": answer})


@advanced_bp.route('/webrtc/ice', methods=['POST'])
@jwt_required
def webrtc_add_ice(current_user):
    data = request.get_json() or {}
    peer_id = data.get('peer_id', '')
    candidate = data.get('candidate')
    if not peer_id or not candidate:
        return jsonify({"success": False, "error": "peer_id and candidate required"}), 400
    signaling_server.add_ice_candidate(peer_id, candidate)
    return jsonify({"success": True})


# Alias used by webrtc-transfer.js
@advanced_bp.route('/webrtc/ice-candidate', methods=['POST'])
def webrtc_add_ice_candidate():
    data = request.get_json() or {}
    peer_id = data.get('peer_id', '')
    candidate = data.get('candidate')
    if not peer_id or not candidate:
        return jsonify({"success": False, "error": "peer_id and candidate required"}), 400
    signaling_server.add_ice_candidate(peer_id, candidate)
    return jsonify({"success": True})


@advanced_bp.route('/webrtc/ice/<peer_id>', methods=['GET'])
@jwt_required
def webrtc_get_ice(current_user, peer_id):
    candidates = signaling_server.get_ice_candidates(peer_id)
    return jsonify({"success": True, "candidates": candidates})


# Alias used by webrtc-transfer.js (polls /ice-candidates/<peer_id>)
@advanced_bp.route('/webrtc/ice-candidates/<peer_id>', methods=['GET'])
def webrtc_get_ice_candidates(peer_id):
    candidates = signaling_server.get_ice_candidates(peer_id)
    return jsonify({"success": True, "candidates": [{'candidate': c} for c in candidates]})


@advanced_bp.route('/webrtc/room', methods=['POST'])
@jwt_required
def webrtc_create_room(current_user):
    data = request.get_json() or {}
    room_id = data.get('room_id', '')
    peer_id = data.get('peer_id', str(current_user.get('_id', '')))
    if not room_id:
        return jsonify({"success": False, "error": "room_id required"}), 400
    signaling_server.create_room(room_id, peer_id)
    return jsonify({"success": True, "room_id": room_id})


@advanced_bp.route('/webrtc/room/<room_id>/join', methods=['POST'])
@jwt_required
def webrtc_join_room(current_user, room_id):
    data = request.get_json() or {}
    peer_id = data.get('peer_id', str(current_user.get('_id', '')))
    success = signaling_server.join_room(room_id, peer_id)
    peers = signaling_server.get_room_peers(room_id)
    return jsonify({"success": success, "peers": peers})


@advanced_bp.route('/webrtc/room/<room_id>/peers', methods=['GET'])
@jwt_required
def webrtc_room_peers(current_user, room_id):
    peers = signaling_server.get_room_peers(room_id)
    return jsonify({"success": True, "peers": peers})


@advanced_bp.route('/webrtc/stats', methods=['GET'])
@jwt_required
def webrtc_stats(current_user):
    return jsonify({"success": True, "stats": signaling_server.stats()})


# ========== Differential Sync ==========

@advanced_bp.route('/sync/document', methods=['POST'])
@jwt_required
def sync_create_document(current_user):
    data = request.get_json() or {}
    doc_id = data.get('doc_id', '')
    content = data.get('content', '')
    if not doc_id:
        return jsonify({"success": False, "error": "doc_id required"}), 400
    result = sync_manager.create_document(doc_id, content)
    return jsonify({"success": True, **result})


@advanced_bp.route('/sync/document/<doc_id>', methods=['GET'])
@jwt_required
def sync_get_document(current_user, doc_id):
    doc = sync_manager.get_document(doc_id)
    if not doc:
        return jsonify({"success": False, "error": "Document not found"}), 404
    return jsonify({"success": True, **doc})


@advanced_bp.route('/sync/document/<doc_id>/patch', methods=['POST'])
@jwt_required
def sync_patch_document(current_user, doc_id):
    data = request.get_json() or {}
    new_content = data.get('content', '')
    client_version = data.get('version', 0)
    result = sync_manager.apply_patch(doc_id, new_content, client_version)
    return jsonify(result)


@advanced_bp.route('/sync/document/<doc_id>/diff', methods=['GET'])
@jwt_required
def sync_get_diff(current_user, doc_id):
    from_version = int(request.args.get('from_version', 0))
    result = sync_manager.get_diff(doc_id, from_version)
    if not result:
        return jsonify({"success": False, "error": "Document not found"}), 404
    return jsonify({"success": True, **result})


@advanced_bp.route('/sync/stats', methods=['GET'])
@jwt_required
def sync_stats(current_user):
    return jsonify({"success": True, "stats": sync_manager.stats()})


# ========== Predictive Prefetch ==========

@advanced_bp.route('/prefetch/record', methods=['POST'])
@jwt_required
def prefetch_record(current_user):
    data = request.get_json() or {}
    file_id = data.get('file_id', '')
    user_id = str(current_user.get('_id', ''))
    if not file_id:
        return jsonify({"success": False, "error": "file_id required"}), 400
    prefetch_service.record_access(user_id, file_id)
    predictions = prefetch_service.get_predictions(user_id, file_id)
    return jsonify({"success": True, "predictions": predictions})


@advanced_bp.route('/prefetch/predict', methods=['POST'])
@jwt_required
def prefetch_predict(current_user):
    data = request.get_json() or {}
    file_id = data.get('file_id', '')
    user_id = str(current_user.get('_id', ''))
    predictions = prefetch_service.get_predictions(user_id, file_id)
    return jsonify({"success": True, "predictions": predictions})


@advanced_bp.route('/prefetch/queue', methods=['GET'])
@jwt_required
def prefetch_queue(current_user):
    queue = prefetch_service.get_queue()
    return jsonify({"success": True, "queue": queue})


@advanced_bp.route('/prefetch/stats', methods=['GET'])
@jwt_required
def prefetch_stats(current_user):
    return jsonify({"success": True, "stats": prefetch_service.stats()})


# ========== Compression ==========

@advanced_bp.route('/compression/compress', methods=['POST'])
@jwt_required
def compress_data(current_user):
    data = request.get_json() or {}
    content = data.get('content', '')
    algorithm = data.get('algorithm', 'gzip')
    if not content:
        return jsonify({"success": False, "error": "content required"}), 400
    try:
        algo = CompressionAlgorithm[algorithm.upper()]
        service = CompressionService()
        compressed = service.compress(content.encode(), algo)
        import base64
        return jsonify({
            "success": True,
            "original_size": len(content),
            "compressed_size": len(compressed),
            "ratio": round(len(compressed) / len(content), 3),
            "algorithm": algorithm,
            "data": base64.b64encode(compressed).decode(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@advanced_bp.route('/compression/algorithms', methods=['GET'])
@jwt_required
def list_algorithms(current_user):
    return jsonify({
        "success": True,
        "algorithms": [a.name.lower() for a in CompressionAlgorithm],
    })


# ========== Overview ==========

@advanced_bp.route('/status', methods=['GET'])
@jwt_required
def advanced_status(current_user):
    return jsonify({
        "success": True,
        "features": {
            "wasm": wasm_service.stats(),
            "crdt": get_crdt_manager().stats(),
            "graphql": get_graphql_executor().stats(),
            "webrtc": signaling_server.stats(),
            "differential_sync": sync_manager.stats(),
            "prefetch": prefetch_service.stats(),
        }
    })

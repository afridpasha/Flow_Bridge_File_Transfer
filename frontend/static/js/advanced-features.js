/**
 * FlowBridge Advanced Features — Client-side JS for advanced API endpoints.
 */

const AdvancedFeatures = (() => {
    const BASE = '/api/advanced';

    function getToken() {
        return localStorage.getItem('token') || '';
    }

    function headers() {
        return { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() };
    }

    async function request(method, path, body) {
        const opts = { method, headers: headers() };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(BASE + path, opts);
        return res.json();
    }

    // ===== WASM =====
    const wasm = {
        listModules: () => request('GET', '/wasm/modules'),
        getModule: (name) => request('GET', `/wasm/module/${name}`),
        checksum: (content) => request('POST', '/wasm/checksum', { content }),
        stats: () => request('GET', '/wasm/stats'),
    };

    // ===== CRDT =====
    const crdt = {
        increment: (name, amount = 1) => request('POST', `/crdt/counter/${name}/increment`, { amount }),
        getCounter: (name) => request('GET', `/crdt/counter/${name}`),
        writeRegister: (name, value) => request('POST', `/crdt/register/${name}`, { value }),
        readRegister: (name) => request('GET', `/crdt/register/${name}`),
        setAdd: (name, element) => request('POST', `/crdt/set/${name}/add`, { element }),
        setRemove: (name, element) => request('POST', `/crdt/set/${name}/remove`, { element }),
        getSet: (name) => request('GET', `/crdt/set/${name}`),
        stats: () => request('GET', '/crdt/stats'),
    };

    // ===== GraphQL =====
    const graphql = {
        query: (query, variables) => request('POST', '/graphql', { query, variables }),
        schema: () => request('GET', '/graphql/schema'),
        stats: () => request('GET', '/graphql/stats'),
    };

    // ===== WebRTC Signaling =====
    const webrtc = {
        sendOffer: (from, to, offer) => request('POST', '/webrtc/offer', { from, to, offer }),
        getOffer: (from, to) => request('GET', `/webrtc/offer/${from}/${to}`),
        sendAnswer: (from, to, answer) => request('POST', '/webrtc/answer', { from, to, answer }),
        getAnswer: (from, to) => request('GET', `/webrtc/answer/${from}/${to}`),
        addIce: (peer_id, candidate) => request('POST', '/webrtc/ice', { peer_id, candidate }),
        getIce: (peer_id) => request('GET', `/webrtc/ice/${peer_id}`),
        createRoom: (room_id, peer_id) => request('POST', '/webrtc/room', { room_id, peer_id }),
        joinRoom: (room_id, peer_id) => request('POST', `/webrtc/room/${room_id}/join`, { peer_id }),
        getRoomPeers: (room_id) => request('GET', `/webrtc/room/${room_id}/peers`),
        stats: () => request('GET', '/webrtc/stats'),
    };

    // ===== Differential Sync =====
    const sync = {
        createDocument: (doc_id, content = '') => request('POST', '/sync/document', { doc_id, content }),
        getDocument: (doc_id) => request('GET', `/sync/document/${doc_id}`),
        patch: (doc_id, content, version) => request('POST', `/sync/document/${doc_id}/patch`, { content, version }),
        getDiff: (doc_id, from_version = 0) => request('GET', `/sync/document/${doc_id}/diff?from_version=${from_version}`),
        stats: () => request('GET', '/sync/stats'),
    };

    // ===== Predictive Prefetch =====
    const prefetch = {
        record: (file_id) => request('POST', '/prefetch/record', { file_id }),
        predict: (file_id) => request('POST', '/prefetch/predict', { file_id }),
        queue: () => request('GET', '/prefetch/queue'),
        stats: () => request('GET', '/prefetch/stats'),
    };

    // ===== Compression =====
    const compression = {
        compress: (content, algorithm = 'gzip') => request('POST', '/compression/compress', { content, algorithm }),
        algorithms: () => request('GET', '/compression/algorithms'),
    };

    // ===== Status =====
    const status = () => request('GET', '/status');

    return { wasm, crdt, graphql, webrtc, sync, prefetch, compression, status };
})();

// Make globally available
window.AdvancedFeatures = AdvancedFeatures;

"""
Scaling Routes — Real metrics endpoint read by Cloudflare Worker
for adaptive weight decisions and auto-scaling signals.
"""
import os
import time
import threading
import psutil
from collections import deque
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from middleware.auth_middleware import token_required

scaling_bp = Blueprint('scaling', __name__, url_prefix='/api/scaling')

# ── Rolling latency window (last 100 requests) ────────────────────────────────
_latency_lock   = threading.Lock()
_latency_window = deque(maxlen=100)   # stores (timestamp, latency_ms) tuples
_request_count  = 0
_error_count    = 0
_start_time     = time.time()


def record_request_latency(latency_ms: float, is_error: bool = False):
    """Called by middleware on every request to build rolling stats."""
    global _request_count, _error_count
    with _latency_lock:
        _latency_window.append((time.time(), latency_ms))
        _request_count += 1
        if is_error:
            _error_count += 1


def _compute_percentile(samples, pct):
    if not samples:
        return 0
    s = sorted(samples)
    idx = max(0, int(len(s) * pct / 100) - 1)
    return round(s[idx], 1)


def _get_latency_stats():
    with _latency_lock:
        now = time.time()
        # Only last 60 seconds
        recent = [ms for ts, ms in _latency_window if now - ts <= 60]
    if not recent:
        return {"p50": 0, "p95": 0, "p99": 0, "count": 0}
    return {
        "p50":   _compute_percentile(recent, 50),
        "p95":   _compute_percentile(recent, 95),
        "p99":   _compute_percentile(recent, 99),
        "count": len(recent),
    }


# ── Public metrics endpoint — read by CF Worker ───────────────────────────────

@scaling_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Public metrics endpoint polled by Cloudflare Worker.
    Returns system load + latency percentiles for adaptive weight decisions.
    No auth required — CF Worker calls this from health checks.
    """
    cpu    = psutil.cpu_percent(interval=0.1)
    mem    = psutil.virtual_memory()
    uptime = int(time.time() - _start_time)
    lat    = _get_latency_stats()

    # Compute a 0-100 load score CF Worker uses for weight adjustment
    # Higher score = more loaded = lower weight
    load_score = round((cpu * 0.5) + (mem.percent * 0.3) + (
        min(lat["p95"] / 30, 20)  # p95 latency contributes up to 20 points
    ), 1)

    return jsonify({
        "instance":    os.environ.get("INSTANCE_ID", "unknown"),
        "uptime_s":    uptime,
        "cpu_percent": round(cpu, 1),
        "mem_percent": round(mem.percent, 1),
        "mem_free_mb": round(mem.available / 1024 / 1024, 1),
        "latency": lat,
        "requests": {
            "total":       _request_count,
            "errors":      _error_count,
            "error_rate":  round(_error_count / max(_request_count, 1) * 100, 2),
        },
        "load_score":  load_score,   # CF Worker reads this for weight decisions
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    })


@scaling_bp.route('/health', methods=['GET'])
def scaling_health():
    """
    Detailed health for CF Worker active health checks.
    Returns 503 if overloaded so CF removes this backend from pool.
    """
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory().percent
    lat = _get_latency_stats()

    # Mark degraded if: CPU > 85%, memory > 85%, or p95 > 3s
    degraded = cpu > 85 or mem > 85 or lat["p95"] > 3000

    status = 503 if degraded else 200
    return jsonify({
        "status":      "degraded" if degraded else "healthy",
        "cpu_percent": round(cpu, 1),
        "mem_percent": round(mem, 1),
        "p95_ms":      lat["p95"],
        "instance":    os.environ.get("INSTANCE_ID", "unknown"),
    }), status


@scaling_bp.route('/status', methods=['GET'])
@token_required
def scaling_status(current_user):
    """Full scaling status — authenticated, for dashboard."""
    cpu  = psutil.cpu_percent(interval=0.1)
    mem  = psutil.virtual_memory()
    lat  = _get_latency_stats()
    proc = psutil.Process(os.getpid())

    return jsonify({
        "success":  True,
        "instance": {
            "id":           os.environ.get("INSTANCE_ID", "unknown"),
            "pid":          os.getpid(),
            "uptime_s":     int(time.time() - proc.create_time()),
            "port":         int(os.environ.get("PORT", 5000)),
        },
        "system": {
            "cpu_percent":  round(cpu, 1),
            "mem_percent":  round(mem.percent, 1),
            "mem_free_mb":  round(mem.available / 1024 / 1024, 1),
            "cpu_count":    psutil.cpu_count(),
        },
        "latency":  lat,
        "requests": {
            "total":        _request_count,
            "errors":       _error_count,
            "error_rate":   round(_error_count / max(_request_count, 1) * 100, 2),
        },
    })

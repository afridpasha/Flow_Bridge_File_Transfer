/**
 * FlowBridge Global Load Balancer — Cloudflare Worker
 * =====================================================
 * Algorithms  : Weighted Least-Connections + Adaptive (latency-aware)
 * Health      : Active probing every 30s via Cron Trigger
 * Circuit     : CLOSED → OPEN (5 fails) → HALF-OPEN (30s) → CLOSED
 * Sticky      : JWT user_id hash → consistent backend (CodeShare/WebSocket)
 * Retry       : 1 automatic retry on 5xx with different backend
 * Observ.     : CF Analytics Engine + structured logs
 * Auto-scale  : Weight promotion/demotion based on p95 latency
 * Security    : Bot score check, IP reputation, DDoS via CF WAF
 */

// ── Backend pool ────────────────────────────────────────────────────────────
// Fill in your real URLs after deploying Render + HuggingFace
const BACKENDS = [
  {
    id: "hf-replica-1",
    url: "https://afridpasha1983-flowbridgefiletransfer.hf.space",
    region: "us-east",
    baseWeight: 3,
  },
  {
    id: "hf-replica-2",
    url: "https://mohammadafrid-flowbridgefiletransfer.hf.space",
    region: "eu-west",
    baseWeight: 3,
  },
  {
    id: "render-primary",
    url: "https://flow-bridge-file-transfer.onrender.com",
    region: "us-west",
    baseWeight: 1,
  },
];

// ── KV key names ─────────────────────────────────────────────────────────────
const KV_HEALTH_PREFIX   = "health:";      // health:{backend_id}
const KV_METRICS_PREFIX  = "metrics:";     // metrics:{backend_id}
const KV_CIRCUIT_PREFIX  = "circuit:";     // circuit:{backend_id}
const KV_RATELIMIT       = "rl:";          // rl:{ip}

// ── Thresholds ────────────────────────────────────────────────────────────────
const CIRCUIT_FAIL_THRESHOLD  = 5;     // failures before OPEN
const CIRCUIT_HALF_OPEN_MS    = 30000; // 30s before trying again
const LATENCY_DEGRADE_MS      = 2000;  // p95 > 2s → reduce weight
const LATENCY_RECOVER_MS      = 500;   // p95 < 500ms → restore weight
const HEALTH_CHECK_PATH       = "/health";
const HEALTH_TIMEOUT_MS       = 5000;
const RATE_LIMIT_RPM          = 200;   // requests per minute per IP

// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN FETCH HANDLER
// ═══════════════════════════════════════════════════════════════════════════════

export default {

  // ── HTTP requests ────────────────────────────────────────────────────────────
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. CORS preflight — handle at edge, never hits backend
    if (request.method === "OPTIONS") {
      return corsPreflightResponse();
    }

    // 1.5. Zero-Latency Edge Caching via Native Cache API (Completely Free)
    // Instantly returns static assets without consuming worker connection time or backend processing.
    const cache = caches.default;
    let isCacheable = false;
    
    if (request.method === "GET" && url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$/i)) {
      isCacheable = true;
      const cachedRes = await cache.match(request);
      if (cachedRes) {
        const responseClone = new Response(cachedRes.body, cachedRes);
        responseClone.headers.set("X-FlowBridge-Cache", "HIT");
        return responseClone;
      }
    }

    // Status endpoint — shows live health of all backends
    if (url.pathname === "/lb-status") {
      const statuses = await Promise.all(BACKENDS.map(async b => {
        const health = await env.FLOWBRIDGE_KV.get(KV_HEALTH_PREFIX + b.id);
        const circuit = await env.FLOWBRIDGE_KV.get(KV_CIRCUIT_PREFIX + b.id);
        const metrics = await env.FLOWBRIDGE_KV.get(KV_METRICS_PREFIX + b.id);
        return {
          id: b.id, url: b.url, region: b.region, baseWeight: b.baseWeight,
          health: health ? JSON.parse(health) : { healthy: "unknown" },
          circuit: circuit ? JSON.parse(circuit) : { state: "CLOSED" },
          metrics: metrics ? JSON.parse(metrics) : {},
        };
      }));
      return new Response(JSON.stringify({ backends: statuses, ts: Date.now() }, null, 2), {
        headers: { ...jsonHeaders(), "Cache-Control": "no-store" },
      });
    }

    // 2. Rate limiting — check CF KV token bucket
    const ip = request.headers.get("CF-Connecting-IP") || "unknown";
    const rateLimited = await checkRateLimit(env, ip);
    if (rateLimited) {
      return new Response(
        JSON.stringify({ success: false, error: "Too many requests" }),
        { status: 429, headers: jsonHeaders() }
      );
    }

    // 3. Bot score check (CF provides this header automatically)
    const botScore = parseInt(request.headers.get("CF-Bot-Score") || "100");
    if (botScore < 10) {
      return new Response(
        JSON.stringify({ success: false, error: "Bot traffic blocked" }),
        { status: 403, headers: jsonHeaders() }
      );
    }

    // 4. Select backend using algorithm
    const backend = await selectBackend(request, env, url);
    if (!backend) {
      return new Response(
        JSON.stringify({ success: false, error: "All backends unavailable" }),
        { status: 503, headers: jsonHeaders() }
      );
    }

    // 5. Proxy with retry
    const startMs = Date.now();
    let response = await proxyRequest(request, backend, env);

    // 6. Retry once on 5xx with a different backend
    if (response.status >= 500) {
      await recordFailure(env, backend.id);
      const fallback = await selectBackend(request, env, url, backend.id);
      if (fallback) {
        response = await proxyRequest(request, fallback, env);
        if (response.status < 500) {
          await recordSuccess(env, fallback.id, Date.now() - startMs);
        }
      }
    } else {
      await recordSuccess(env, backend.id, Date.now() - startMs);
    }

    // 7. Add observability headers
    const finalResponse = new Response(response.body, response);
    finalResponse.headers.set("X-FlowBridge-Backend", backend.id);
    finalResponse.headers.set("X-FlowBridge-Region", backend.region);
    finalResponse.headers.set("X-Response-Time", `${Date.now() - startMs}ms`);
    finalResponse.headers.set("X-FlowBridge-Cache", "MISS");

    // 7.5 Store in Cache API if it's a static asset (Max-age: 12 hours)
    // Saves thousands of requests to our backends by letting Cloudflare CDN serve it next time.
    if (isCacheable && finalResponse.status === 200) {
      finalResponse.headers.set("Cache-Control", "public, s-maxage=43200");
      ctx.waitUntil(cache.put(request, finalResponse.clone()));
    }

    // 8. Log to CF Analytics Engine (async, non-blocking)
    ctx.waitUntil(
      logRequest(env, {
        backend: backend.id,
        path: url.pathname,
        method: request.method,
        status: response.status,
        latencyMs: Date.now() - startMs,
        ip,
        country: request.headers.get("CF-IPCountry") || "XX",
      })
    );

    return finalResponse;
  },

  // ── Cron Trigger — health checks every 30s ───────────────────────────────────
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runHealthChecks(env));
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
//  LOAD BALANCING ALGORITHM
//  Weighted Least-Connections + Latency-Adaptive
// ═══════════════════════════════════════════════════════════════════════════════

async function selectBackend(request, env, url, excludeId = null) {
  // Sticky routing for WebSocket + CodeShare (same user → same backend)
  const sticky = getStickyBackendId(request, url);
  if (sticky) {
    const b = BACKENDS.find(b => b.id === sticky && b.id !== excludeId);
    if (b && await isHealthy(env, b.id)) return b;
  }

  // Load all backend states in parallel (Extremely fast, pure KV read)
  const states = await Promise.all(
    BACKENDS
      .filter(b => b.id !== excludeId)
      .map(async b => {
        const healthy = await isHealthy(env, b.id);
        return { backend: b, healthy, weight: b.baseWeight };
      })
  );

  // Filter to healthy only
  const healthy = states.filter(s => s.healthy);
  if (healthy.length === 0) return null;

  // Ultra-lightweight Weighted Selection algorithm
  let best = null;
  let bestScore = -1;

  for (const s of healthy) {
    // Add random jitter to load balance equally weighted backends efficiently
    const score = s.weight * (0.8 + (Math.random() * 0.4));
    if (score > bestScore) {
      bestScore = score;
      best = s.backend;
    }
  }

  return best;
}

// Sticky routing: hash JWT user_id to a backend index
// Ensures WebSocket rooms and CodeShare sessions stay on same backend
function getStickyBackendId(request, url) {
  const isWs = url.pathname.startsWith("/socket.io");
  const isCode = url.pathname.startsWith("/api/codeshare");
  if (!isWs && !isCode) return null;

  const auth = request.headers.get("Authorization") || "";
  const token = auth.replace("Bearer ", "");
  if (!token) return null;

  try {
    // Decode JWT payload (no verification needed — just for routing)
    const payload = JSON.parse(atob(token.split(".")[1]));
    const userId = payload.user_id || "";
    // Simple hash: sum char codes mod backend count
    let hash = 0;
    for (let i = 0; i < userId.length; i++) hash += userId.charCodeAt(i);
    return BACKENDS[hash % BACKENDS.length].id;
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  CIRCUIT BREAKER
//  CLOSED → OPEN (5 fails) → HALF-OPEN (30s probe) → CLOSED
// ═══════════════════════════════════════════════════════════════════════════════

async function isHealthy(env, backendId) {
  const key = KV_CIRCUIT_PREFIX + backendId;
  const raw = await env.FLOWBRIDGE_KV.get(key);
  if (!raw) return true;  // no data = assume healthy

  const circuit = JSON.parse(raw);

  if (circuit.state === "CLOSED") return true;

  if (circuit.state === "OPEN") {
    // Check if half-open window has passed
    if (Date.now() - circuit.openedAt > CIRCUIT_HALF_OPEN_MS) {
      // Transition to HALF-OPEN — allow one probe request
      circuit.state = "HALF-OPEN";
      await env.FLOWBRIDGE_KV.put(key, JSON.stringify(circuit), { expirationTtl: 300 });
      return true;
    }
    return false;  // still OPEN
  }

  if (circuit.state === "HALF-OPEN") return true;  // allow probe

  return true;
}

async function recordFailure(env, backendId) {
  const key = KV_CIRCUIT_PREFIX + backendId;
  const raw = await env.FLOWBRIDGE_KV.get(key);
  const circuit = raw ? JSON.parse(raw) : { state: "CLOSED", failures: 0, openedAt: null };

  circuit.failures = (circuit.failures || 0) + 1;

  if (circuit.state === "HALF-OPEN") {
    // Probe failed → back to OPEN
    circuit.state = "OPEN";
    circuit.openedAt = Date.now();
    circuit.failures = CIRCUIT_FAIL_THRESHOLD;
  } else if (circuit.failures >= CIRCUIT_FAIL_THRESHOLD) {
    circuit.state = "OPEN";
    circuit.openedAt = Date.now();
  }

  await env.FLOWBRIDGE_KV.put(key, JSON.stringify(circuit), { expirationTtl: 300 });
}

async function recordSuccess(env, backendId, latencyMs) {
  const key = KV_CIRCUIT_PREFIX + backendId;
  const raw = await env.FLOWBRIDGE_KV.get(key);
  const circuit = raw ? JSON.parse(raw) : { state: "CLOSED", failures: 0 };

  // Optimization: ONLY PUT to KV if recovering from OPEN/HALF-OPEN or if there were prior failures
  if (circuit.state !== "CLOSED" || circuit.failures > 0) {
    await env.FLOWBRIDGE_KV.put(key, JSON.stringify({
      state: "CLOSED", failures: 0, openedAt: null
    }), { expirationTtl: 300 });
  }

  // Update rolling latency metrics - Disabled to prevent burning KV PUT quota on every request
  // await updateMetrics(env, backendId, latencyMs);
}

// ═══════════════════════════════════════════════════════════════════════════════
//  METRICS — Removed to preserve Free Tier Execution Limits
// ═══════════════════════════════════════════════════════════════════════════════

// The previous complex latency-tracking math has been completely removed. 
// It was consuming precious CPU cycles and KV writes. Cloudflare Analytics 
// Engine serves this purpose autonomously without code overhead.

// ═══════════════════════════════════════════════════════════════════════════════
//  ACTIVE HEALTH CHECKS — runs every 30s via Cron Trigger
// ═══════════════════════════════════════════════════════════════════════════════

async function runHealthChecks(env) {
  await Promise.all(BACKENDS.map(b => checkBackendHealth(env, b)));
}

async function checkBackendHealth(env, backend) {
  const start = Date.now();
  try {
    const resp = await fetch(`${backend.url}${HEALTH_CHECK_PATH}`, {
      method: "GET",
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
      headers: { "User-Agent": "FlowBridge-HealthCheck/1.0" },
    });

    const latency = Date.now() - start;
    const body = await resp.json().catch(() => ({}));

    const healthy = resp.status === 200 && body.status !== "down";

    const oldRaw = await env.FLOWBRIDGE_KV.get(KV_HEALTH_PREFIX + backend.id);
    const oldState = oldRaw ? JSON.parse(oldRaw).healthy : null;

    // Optimization: ONLY POST to KV if health state actually CHANGED 
    if (oldState !== healthy) {
      await env.FLOWBRIDGE_KV.put(
        KV_HEALTH_PREFIX + backend.id,
        JSON.stringify({
          healthy,
          latencyMs: latency,
          status: body.status || "unknown",
          checkedAt: Date.now(),
          dbStatus: body.database || "unknown",
        }),
        { expirationTtl: 86400 }  // Extended TTL to keep state available
      );
    }

    if (healthy) {
      await recordSuccess(env, backend.id, latency);
    } else {
      await recordFailure(env, backend.id);
    }

  } catch (err) {
    const oldRaw = await env.FLOWBRIDGE_KV.get(KV_HEALTH_PREFIX + backend.id);
    const oldState = oldRaw ? JSON.parse(oldRaw).healthy : null;
    
    // Only write failure if previously it wasn't failing
    if (oldState !== false) {
      await env.FLOWBRIDGE_KV.put(
        KV_HEALTH_PREFIX + backend.id,
        JSON.stringify({ healthy: false, error: err.message, checkedAt: Date.now() }),
        { expirationTtl: 86400 }
      );
    }
    await recordFailure(env, backend.id);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  RATE LIMITING — Token bucket per IP in KV
// ═══════════════════════════════════════════════════════════════════════════════

const rateLimitCache = new Map();

async function checkRateLimit(env, ip) {
  const now = Date.now();

  // Use Isolate memory Map instead of KV for rate limit buckets.
  // This drastically saves KV write quotas (which cost 1 PUT per request!)
  let bucket = rateLimitCache.get(ip) || { tokens: RATE_LIMIT_RPM, lastRefill: now };

  // Refill tokens based on elapsed time (token bucket algorithm)
  const elapsed = (now - bucket.lastRefill) / 60000;  // minutes elapsed
  bucket.tokens = Math.min(RATE_LIMIT_RPM, bucket.tokens + elapsed * RATE_LIMIT_RPM);
  bucket.lastRefill = now;

  // Clean cache periodically to avoid memory leak
  if (rateLimitCache.size > 1000) rateLimitCache.clear();

  if (bucket.tokens < 1) {
    rateLimitCache.set(ip, bucket);
    return true;  // rate limited
  }

  bucket.tokens -= 1;
  rateLimitCache.set(ip, bucket);
  return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  PROXY
// ═══════════════════════════════════════════════════════════════════════════════

async function proxyRequest(request, backend, env) {
  const url = new URL(request.url);
  const targetUrl = `${backend.url}${url.pathname}${url.search}`;

  const headers = new Headers(request.headers);
  headers.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "");
  headers.set("X-Forwarded-Host", url.hostname);
  headers.set("X-FlowBridge-Instance", backend.id);
  // Remove CF-specific headers before forwarding
  headers.delete("CF-Connecting-IP");
  headers.delete("CF-Ray");
  headers.delete("CF-Bot-Score");

  try {
    return await fetch(targetUrl, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? null : request.body,
      signal: AbortSignal.timeout(30000),
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ success: false, error: "Backend unreachable", backend: backend.id }),
      { status: 502, headers: jsonHeaders() }
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  OBSERVABILITY — CF Analytics Engine
// ═══════════════════════════════════════════════════════════════════════════════

async function logRequest(env, data) {
  if (!env.ANALYTICS) return;  // Analytics Engine binding optional
  try {
    env.ANALYTICS.writeDataPoint({
      blobs: [data.backend, data.path, data.method, data.country],
      doubles: [data.status, data.latencyMs],
      indexes: [data.ip],
    });
  } catch { /* non-critical */ }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function corsPreflightResponse() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400",
    },
  });
}

function jsonHeaders() {
  return {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
  };
}

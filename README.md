# 🌉 FlowBridge — Hybrid File Transfer System

<div align="center">

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11-green.svg)
![Flask](https://img.shields.io/badge/flask-3.0.0-red.svg)
![MongoDB](https://img.shields.io/badge/mongodb-atlas-green.svg)
![Cloudflare](https://img.shields.io/badge/cloudflare-worker-orange.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)

**A production-grade, distributed, multi-protocol file transfer platform built on microservices architecture with global CDN distribution, enterprise-grade security, and real-time collaboration.**

*Built for Computer Networks Course — Vasavi College of Engineering, Hyderabad*

</div>

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Key Highlights](#-key-highlights)
3. [Complete Architecture](#-complete-architecture)
4. [System Design Concepts](#-system-design-concepts)
5. [Distributed Systems Concepts](#-distributed-systems-concepts)
6. [Cloud Computing Concepts](#-cloud-computing-concepts)
7. [Full Technology Stack](#-full-technology-stack)
8. [Project Structure](#-project-structure)
9. [All Features A–Z](#-all-features-az)
10. [API Reference](#-api-reference)
11. [WebSocket Events](#-websocket-events)
12. [Execution Flow](#-execution-flow)
13. [Security Architecture](#-security-architecture)
14. [Storage Architecture](#-storage-architecture)
15. [Load Balancer Deep Dive](#-load-balancer-deep-dive)
16. [Performance Metrics](#-performance-metrics)
17. [Data Models](#-data-models)
18. [Configuration Reference](#-configuration-reference)
19. [Deployment Guide](#-deployment-guide)
20. [Academic Context](#-academic-context)

---

## 🎯 Project Overview

**FlowBridge** is a full-stack, distributed file transfer system that combines three distinct transfer protocols under one unified platform:

| Transfer Mode | Protocol | Use Case | Speed |
|---|---|---|---|
| **Web Upload/Download** | HTTP/HTTPS via REST API | Any device, any network | CDN-accelerated |
| **TCP Direct Transfer** | Raw TCP Socket | LAN / same network | ~1 Gbps LAN speed |
| **WebSocket P2P** | WebSocket over Socket.IO | Cross-network, browser-to-browser | Real-time streaming |
| **WebRTC** | WebRTC DataChannel | True peer-to-peer, no server relay | Direct P2P |

Beyond file transfer, FlowBridge includes a full **CodeShare** platform (like codeshare.io), a complete **user management system** with 2FA, a **real-time activity feed**, and an **advanced features layer** implementing computer science concepts like CRDTs, Merkle Trees, Bloom Filters, HyperLogLog, and Consistent Hashing.

### What Makes This Different

- **No single point of failure** — 3 backend instances behind a Cloudflare Worker load balancer
- **3-tier storage** — Cloudflare R2 (primary) → Backblaze B2 (global replica) → MinIO (local replica)
- **Content-addressable storage** — SHA-256 keys mean identical files are stored exactly once across all users
- **Edge-first** — Cloudflare Worker runs at 310 PoPs worldwide, Mumbai PoP gives ~5ms latency from Hyderabad
- **Zero-cost egress** — R2 has no egress fees, B2 has free egress via Cloudflare

---

## ✨ Key Highlights

```
┌─────────────────────────────────────────────────────────────────┐
│  310 Cloudflare Edge Locations  →  ~5ms from Hyderabad          │
│  3 Backend Instances            →  Zero downtime deployments     │
│  3 Storage Backends             →  99.999% file durability       │
│  SHA-256 Deduplication          →  Zero duplicate storage        │
│  Circuit Breaker                →  Auto-failover in <30s         │
│  JWT + 2FA + OTP                →  Enterprise-grade security     │
│  4 Transfer Protocols           →  Any network, any device       │
│  Real-time Collaboration        →  CodeShare + WebSocket rooms   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Complete Architecture

### High-Level System Architecture

```
                        ┌─────────────────────────────────────┐
                        │         CLIENT LAYER                │
                        │  Browser / Mobile / Desktop App     │
                        │  React SPA  |  Legacy HTML Templates│
                        └──────────────┬──────────────────────┘
                                       │ HTTPS / WSS
                                       ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE EDGE LAYER                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Cloudflare Worker (worker.js)                  │    │
│  │                                                             │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │    │
│  │  │ Rate Limiter │  │ Bot Blocker  │  │  CORS Handler    │  │    │
│  │  │ Token Bucket │  │ CF-Bot-Score │  │  Edge Preflight  │  │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘  │    │
│  │                                                             │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │         Load Balancing Algorithm                     │  │    │
│  │  │   Weighted Least-Connections + Adaptive Latency      │  │    │
│  │  │   Sticky Routing (JWT hash) for WebSocket/CodeShare  │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  │                                                             │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │              Circuit Breaker (KV-backed)             │  │    │
│  │  │         CLOSED → OPEN (5 fails) → HALF-OPEN          │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  │                                                             │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │         CF Analytics Engine (Observability)          │    │    │
│  │  │    backend | path | latency | status | country       │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Cloudflare KV Store                         │   │
│  │  health:{id} | circuit:{id} | metrics:{id} | rl:{ip}        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                    │ weight=3        │ weight=3        │ weight=1
                    ▼                 ▼                 ▼
        ┌───────────────┐  ┌───────────────┐  ┌───────────────────┐
        │ HuggingFace   │  │ HuggingFace   │  │  Render.com       │
        │ Space #1      │  │ Space #2      │  │  Primary          │
        │ (Flask+gunicorn│  │ (Flask+gunicorn│  │  (Flask+gunicorn) │
        │  PORT=7860)   │  │  PORT=7860)   │  │  PORT=auto)       │
        └───────┬───────┘  └───────┬───────┘  └────────┬──────────┘
                │                  │                    │
                └──────────────────┴────────────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      BACKEND LAYER          │
                    │   Flask 3.0 + Socket.IO     │
                    │                             │
                    │  ┌─────────────────────┐    │
                    │  │   13 Blueprints     │    │
                    │  │  auth | files | share│   │
                    │  │  tcp | ws | codeshare│   │
                    │  │  scaling | advanced  │   │
                    │  └─────────────────────┘    │
                    │                             │
                    │  ┌─────────────────────┐    │
                    │  │  18 Services        │    │
                    │  │  storage | cache    │    │
                    │  │  email | compress   │    │
                    │  │  crdt | merkle      │    │
                    │  │  bloom | hll | etc  │    │
                    │  └─────────────────────┘    │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        ▼                        ▼
┌──────────────────┐   ┌───────────────────┐   ┌──────────────────────┐
│  STORAGE LAYER   │   │  DATABASE LAYER   │   │   CACHE LAYER        │
│                  │   │                   │   │                      │
│ Cloudflare R2    │   │  MongoDB Atlas    │   │  Upstash Redis       │
│ (Primary ~5ms)   │   │  (Metadata only)  │   │  (Singapore ~60ms)   │
│        ↓ async   │   │                   │   │  TTL-based caching   │
│ Backblaze B2     │   │  Collections:     │   │  InMemory fallback   │
│ (EU Central      │   │  users            │   │                      │
│  ~120ms replica) │   │  user_files       │   │  Keys:               │
│        ↓ async   │   │  share_tokens     │   │  files:list:{uid}    │
│ MinIO Docker     │   │  transfers        │   │  user:storage:{uid}  │
│ (Local ~0ms      │   │  activity_log     │   │  codeshare:{slug}    │
│  LAN replica)    │   │  folders          │   │  share:analytics:{}  │
│                  │   │  trash            │   │                      │
│ Key format:      │   │  codeshares       │   │                      │
│ files/{h[:2]}/   │   │                   │   │                      │
│       {h[2:]}    │   │  TTL indexes on:  │   │                      │
│ (SHA-256 CAS)    │   │  transfers (90d)  │   │                      │
│                  │   │  activity (30d)   │   │                      │
│                  │   │  trash (30d)      │   │                      │
└──────────────────┘   └───────────────────┘   └──────────────────────┘
```

### TCP Direct Transfer Architecture

```
  SENDER DEVICE (LAN)                    RECEIVER DEVICE (LAN)
  ┌─────────────────┐                    ┌─────────────────────┐
  │  Browser/App    │                    │  Browser/App        │
  │  POST /api/     │                    │  Opens /receive     │
  │  tcp/send       │                    │  page               │
  └────────┬────────┘                    └──────────┬──────────┘
           │                                        │
           ▼                                        ▼
  ┌─────────────────┐    TCP Socket       ┌─────────────────────┐
  │  TCPSender.py   │ ──────────────────► │  TCPReceiver.py     │
  │                 │  Protocol:          │                     │
  │  1. 4B filename │  [4B len][filename] │  1. Recv filename   │
  │     length      │  [8B filesize]      │  2. Recv filesize   │
  │  2. filename    │  [raw bytes...]     │  3. Recv chunks     │
  │  3. 8B filesize │                     │  4. Save to MinIO   │
  │  4. file bytes  │  Port: 5555         │     or disk         │
  │     in chunks   │                     │  5. Emit progress   │
  └─────────────────┘                    │     via SocketIO    │
                                          └─────────────────────┘
```

### WebSocket P2P Transfer Architecture

```
  SENDER BROWSER              FLASK SERVER              RECEIVER BROWSER
  ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
  │              │           │              │           │              │
  │ join_transfer│──────────►│ active_rooms │◄──────────│ create_room  │
  │ _room(code)  │           │ dict (RAM)   │           │ → gets code  │
  │              │           │              │           │              │
  │ send_file_   │──────────►│ forward to   │──────────►│ receive_file │
  │ chunk(data)  │           │ room via     │           │ _chunk       │
  │              │           │ Socket.IO    │           │              │
  │ file_transfer│──────────►│ emit to room │──────────►│ incoming_    │
  │ _complete    │           │              │           │ file done    │
  └──────────────┘           └──────────────┘           └──────────────┘
                              Room cleanup on
                              disconnect (30min TTL)
```

### Share Link Flow

```
  SENDER                    BACKEND                    RECEIVER
  ──────                    ───────                    ────────
  POST /api/share/generate
  {file_id, expiry, max_dl}
          │
          ▼
  ┌───────────────────┐
  │ Generate:         │
  │ • share_token     │     MongoDB
  │ • 6-digit OTP     │ ──► share_tokens collection
  │ • QR code (PNG)   │     TTL = expiry_hours
  │ • presigned URL   │
  └───────────────────┘
          │
          ▼
  share_link + OTP ──────────────────────────────► GET /share/{token}
  (sent via email                                         │
   or manually)                                          ▼
                                                  OTP verify page
                                                         │
                                              POST /api/share/verify-otp
                                              {token, otp, password?}
                                                         │
                                                         ▼
                                              GET /share/{token}/download
                                              → redirect to R2 presigned URL
                                              → download_count++
                                              → otp_verified = False (reset)
```

---

## 🧠 System Design Concepts

Every major system design concept taught in a distributed systems course is implemented and running in this project.

### 1. Content-Addressable Storage (CAS)

Files are stored using their SHA-256 hash as the key, not their filename.

```
Key format:  files/{sha256[:2]}/{sha256[2:]}
Example:     files/ab/cdef1234567890...

Benefits:
  ✅ Automatic global deduplication — same file uploaded by 1000 users = stored once
  ✅ Immutable keys — content never changes, key never changes
  ✅ Integrity verification — re-hash and compare to detect corruption
  ✅ Prefix distribution — first 2 chars spread objects across storage prefixes
```

Implementation: `backend/services/storage_service.py` → `storage_key(sha256)`

### 2. Multi-Tier Caching

```
Request → Upstash Redis (Singapore, ~60ms) → InMemory fallback → MongoDB

Cache TTL Strategy:
  files:list:{user_id}        →  5 minutes   (invalidated on upload/delete)
  user:storage:{user_id}      →  5 minutes   (invalidated on upload/delete)
  codeshare:{slug}            →  30 seconds  (invalidated on every save)
  share:analytics:{token}     →  2 minutes   (invalidated on download)
  user:profile:{user_id}      →  10 minutes  (invalidated on profile update)

Cache Invalidation: Write-through invalidation on every mutation
```

Implementation: `backend/services/redis_cache_service.py`

### 3. Asynchronous Replication

```
Upload Request
      │
      ▼
R2 Primary Upload (SYNCHRONOUS — must succeed, request blocks)
      │
      ├──► B2 EU Central (ASYNC — background thread, non-blocking)
      │
      └──► MinIO Local  (ASYNC — background thread, non-blocking)

Result returned to user immediately after R2 succeeds.
B2 and MinIO sync in background. b2_synced / minio_synced flags
updated in MongoDB when background threads complete.
```

Implementation: `backend/services/storage_service.py` → `upload()` method

### 4. Token Bucket Rate Limiting

Two layers of rate limiting:

**Layer 1 — Cloudflare Worker (Edge, per-IP):**
```
Bucket capacity: 200 tokens
Refill rate:     200 tokens/minute
Storage:         Cloudflare KV (global, consistent)
Enforcement:     Before request reaches any backend
```

**Layer 2 — Flask-Limiter (Per-endpoint):**
```
Default:   200/minute
Login:     5/minute    (brute-force protection)
Signup:    3/minute    (spam protection)
Upload:    20/minute   (abuse prevention)
Share:     30/minute   (link spam prevention)
```

### 5. Circuit Breaker Pattern

```
State Machine (stored in Cloudflare KV):

    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   CLOSED ──(5 failures)──► OPEN                    │
    │     ▲                        │                     │
    │     │                    (30 seconds)               │
    │     │                        │                     │
    │     └──(probe succeeds)── HALF-OPEN                │
    │                              │                     │
    │                         (probe fails)              │
    │                              │                     │
    │                           OPEN (reset timer)       │
    └─────────────────────────────────────────────────────┘

CLOSED:    All requests pass through normally
OPEN:      All requests rejected immediately (fast fail)
HALF-OPEN: One probe request allowed to test recovery
```

Implementation: `cloudflare-worker/worker.js` → `isHealthy()`, `recordFailure()`, `recordSuccess()`

### 6. Consistent Hashing

Used for distributing files across storage nodes with minimal redistribution when nodes are added/removed.

```
Ring with 150 virtual nodes per physical node:
  storage-node-1: 150 virtual positions on ring
  storage-node-2: 150 virtual positions on ring
  storage-node-3: 150 virtual positions on ring

File key → MD5 hash → position on ring → nearest node clockwise
Adding a node: only ~1/N keys need to move (not all keys)
```

Implementation: `backend/services/consistent_hash_service.py`

### 7. Bloom Filter (Probabilistic Duplicate Detection)

```
Capacity:    10,000 items
Error rate:  1% false positive rate
Bit array:   ~95,851 bits
Hash count:  7 hash functions (MD5 + SHA1 double hashing)

Use case: Quick "definitely not a duplicate" check before
          expensive SHA-256 full comparison in MongoDB.
          Saves DB round-trips for new files.
```

Implementation: `backend/services/bloom_filter_service.py`

### 8. HyperLogLog (Cardinality Estimation)

```
Precision: 14 bits → 16,384 registers
Memory:    ~16 KB per counter (vs millions of bytes for exact set)
Error:     ~0.81% standard error

Use case: Count unique file downloaders, unique visitors per share
          link, unique active users — without storing every user ID.
```

Implementation: `backend/services/hyperloglog_service.py`

### 9. Merkle Tree (File Integrity Verification)

```
File chunks → SHA-256 leaf nodes → binary tree → root hash

Verification: Re-compute tree from received chunks,
              compare root hash to sender's root hash.
              Any tampered chunk changes the root hash.

Proof generation: O(log N) proof path for any single chunk
                  without revealing other chunks.
```

Implementation: `backend/services/merkle_tree_service.py`

### 10. CRDT — Conflict-Free Replicated Data Types

Three CRDT types implemented for distributed state without coordination:

```
GCounter (Grow-only Counter):
  Each node has its own counter slot.
  Merge = take max of each slot.
  Value = sum of all slots.
  Use: Download counts, view counts across replicas.

LWW-Register (Last-Write-Wins Register):
  Each write tagged with timestamp.
  Merge = keep highest timestamp.
  Use: File metadata updates across replicas.

OR-Set (Observed-Remove Set):
  Each add tagged with unique UUID.
  Remove marks specific UUIDs as removed.
  Merge = union of adds, union of removes.
  Use: File tags, collaborator lists.
```

Implementation: `backend/services/crdt_service.py`

### 11. Differential Sync

```
Client sends: new_content + client_version
Server checks: client_version == server_version?
  YES → compute unified diff, apply, increment version
  NO  → conflict! return current server state for reconciliation

Patch history: last 50 patches kept per document
Use case: CodeShare real-time collaborative editing
```

Implementation: `backend/services/differential_sync_service.py`

### 12. Predictive Prefetch

```
Access pattern tracking: Markov chain (transition matrix)
  user_id → {file_id → {next_file_id → count}}

Prediction: After accessing file A, predict top-3 likely next files
            based on historical transition probabilities.

Prefetch queue: Pre-load predicted files into LRU cache (50 slots)
                before user requests them.
```

Implementation: `backend/services/predictive_prefetch_service.py`

---

## 🌐 Distributed Systems Concepts

### CAP Theorem Positioning

```
FlowBridge chooses CP (Consistency + Partition Tolerance):

  Storage (R2/B2/MinIO):
    → Eventual Consistency for replicas (B2, MinIO are async)
    → Strong Consistency for primary (R2 is synchronous)

  Database (MongoDB Atlas):
    → Strong Consistency for metadata (retryWrites=True)
    → Replica set with automatic failover

  Cache (Upstash Redis):
    → Eventual Consistency (TTL-based invalidation)
    → Falls back to InMemory on partition
```

### Replication Strategy

```
Write path (3-tier replication):
  ┌─────────────────────────────────────────────────────┐
  │  Tier 1: R2 (Synchronous)                           │
  │    → Must succeed before returning to user          │
  │    → Mumbai CF PoP → ~5ms from Hyderabad            │
  │    → Zero egress fees                               │
  ├─────────────────────────────────────────────────────┤
  │  Tier 2: B2 EU Central (Asynchronous)               │
  │    → Background thread, non-blocking                │
  │    → ~120ms replication lag                         │
  │    → Global geographic redundancy                   │
  ├─────────────────────────────────────────────────────┤
  │  Tier 3: MinIO Local (Asynchronous)                 │
  │    → Background thread, non-blocking                │
  │    → ~0ms (localhost Docker)                        │
  │    → LAN transfer source + local dev                │
  └─────────────────────────────────────────────────────┘

Read path (priority order):
  R2 presigned URL → B2 presigned URL → MinIO presigned URL
```

### Fault Tolerance

```
Component          Failure Mode              Recovery
─────────────────  ────────────────────────  ──────────────────────────
R2 Storage         Cloudflare outage         Serve from B2 (fallback)
B2 Storage         Backblaze outage          Serve from R2 or MinIO
MinIO              Docker container down     Serve from R2 or B2
MongoDB Atlas      Primary node failure      Atlas auto-failover (<30s)
Upstash Redis      Redis outage              InMemory cache fallback
HuggingFace #1     Instance crash            CF Worker routes to HF#2
HuggingFace #2     Instance crash            CF Worker routes to Render
Render             Cold start / crash        CF Worker routes to HF#1/#2
CF Worker          Edge PoP failure          CF auto-routes to next PoP
```

### Distributed Locking

```
CodeShare active users: threading.Lock() per process
  → _active_lock protects _active_users dict
  → Zero DB writes for cursor updates (100+ updates/sec safe)
  → Lost on restart (acceptable — ephemeral real-time state)

WebSocket rooms: active_rooms dict (in-memory per process)
  → Sticky routing via JWT hash ensures same user → same backend
  → Room cleanup on disconnect or 30-minute TTL
```

### Idempotency

```
File uploads: SHA-256 CAS keys are idempotent
  → Uploading same file twice = same key = no duplicate storage
  → _object_exists() check before put_object()

Share link generation: unique token per request (not idempotent)
  → Intentional — each share is a distinct authorization

OTP verification: otp_verified flag reset after each download
  → Prevents replay attacks on share links
```

---

## ☁️ Cloud Computing Concepts

### Serverless Edge Computing

```
Cloudflare Worker:
  → Runs at 310 edge locations worldwide
  → V8 isolate (not a container, not a VM)
  → Cold start: ~0ms (always warm at edge)
  → Memory: 128MB per isolate
  → CPU: 10ms per request (burst to 50ms)
  → No server to manage, no scaling to configure
  → Billed per request (free tier: 100K req/day)
```

### Infrastructure as Code

```
render.yaml       → Declarative Render.com deployment
Dockerfile        → Reproducible container for HuggingFace
docker-compose.yml → Local MinIO + bucket initialization
wrangler.toml     → Cloudflare Worker configuration
```

### Multi-Cloud Strategy

```
Provider          Service Used          Purpose
────────────────  ────────────────────  ──────────────────────────
Cloudflare        Worker + KV + R2      Edge compute + primary storage
Backblaze         B2 Object Storage     Geographic replica (EU Central)
MongoDB Atlas     Database              Managed NoSQL (free tier)
Upstash           Redis REST API        Managed cache (free tier)
Render.com        Web Service           Primary backend hosting
HuggingFace       Spaces (Docker)       Replica backend hosting (2x)
```

### Auto-Scaling Signals

```
AutoscalingManager (autoscaling_manager.py):
  → Monitors CPU + memory every 30 seconds
  → Logs SCALE_UP_SUGGESTED when CPU > 80%
  → Logs SCALE_DOWN_SUGGESTED when CPU < 20%
  → Writes to autoscaling.log for ops review

CF Worker adaptive weights (worker.js):
  → Reads /api/scaling/metrics from each backend
  → p95 latency > 2000ms → halve backend weight
  → p95 latency < 500ms  → restore full weight
  → load_score (0-100) computed from CPU + memory + p95
```

### Observability

```
Logging:
  → Python logging → flowbridge.log (file + stdout)
  → Log levels: DEBUG / INFO / WARNING / ERROR
  → Structured format: timestamp [LEVEL] module: message

Metrics (per backend instance):
  → Rolling latency window: last 100 requests (deque)
  → p50 / p95 / p99 latency percentiles
  → Request count + error count + error rate
  → CPU % + memory % + memory free MB
  → Exposed at GET /api/scaling/metrics (public, no auth)

Health Check (GET /health):
  → Database ping
  → CPU + memory thresholds
  → Storage backend availability (R2/B2/MinIO)
  → Cache connectivity (Upstash)
  → Returns 200 (healthy) or 503 (degraded)

CF Analytics Engine:
  → Per-request: backend, path, method, status, latency, country
  → Queryable via CF dashboard SQL interface
```

---

## 🛠️ Full Technology Stack

### Backend Core

| Technology | Version | Role |
|---|---|---|
| Python | 3.11 | Core language |
| Flask | 3.0.0 | HTTP API framework |
| Flask-SocketIO | 5.3.5 | WebSocket server |
| Flask-CORS | 4.0.0 | Cross-origin resource sharing |
| Flask-Compress | 1.14 | GZip/Brotli HTTP compression |
| Flask-Limiter | 3.5.0 | Rate limiting middleware |
| Gunicorn | 21.2.0 | WSGI production server |
| Eventlet | 0.35.2 | Async I/O for SocketIO |
| Gevent | 23.9.1 | Coroutine-based networking |

### Database & Storage

| Technology | Version | Role |
|---|---|---|
| PyMongo | 4.6.1 | MongoDB driver |
| MongoDB Atlas | Cloud | Metadata storage (NoSQL) |
| boto3 | 1.34.34 | S3-compatible client (R2/B2/MinIO) |
| Cloudflare R2 | — | Primary binary storage (S3-compatible) |
| Backblaze B2 | — | Global replica (EU Central) |
| MinIO | Docker latest | Local replica + LAN transfer server |

### Security

| Technology | Version | Role |
|---|---|---|
| PyJWT | 2.8.0 | JWT access + refresh tokens |
| bcrypt | 4.1.2 | Password hashing (12 rounds) |
| pyotp | 2.9.0 | TOTP 2FA (RFC 6238) |
| qrcode | 7.4.2 | QR code generation for 2FA + share links |
| Pillow | 10.2.0 | Image processing for QR codes |

### Caching & Messaging

| Technology | Version | Role |
|---|---|---|
| redis | 5.0.1 | Redis client library |
| Upstash Redis | REST API | Managed Redis (Singapore PoP) |
| InMemory Cache | Built-in | Fallback when Redis unavailable |

### Compression

| Technology | Version | Role |
|---|---|---|
| Brotli | 1.1.0 | Google's compression (20-30% better than gzip) |
| zstandard | 0.22.0 | Facebook's Zstd compression |
| gzip | stdlib | Standard HTTP compression |
| lzma | stdlib | Maximum compression ratio |

### Advanced Data Structures

| Technology | Role |
|---|---|
| bitarray | 2.8.1 | Bloom filter bit array |
| graphql-core | 3.2.3 | GraphQL query execution |
| difflib | stdlib | Differential sync (unified diff) |
| hashlib | stdlib | SHA-256, MD5 for Merkle/Bloom/HLL |

### Infrastructure & DevOps

| Technology | Role |
|---|---|
| Docker | MinIO containerization |
| docker-compose | Local dev orchestration |
| Cloudflare Worker | Global load balancer (310 PoPs) |
| Cloudflare KV | Distributed state for Worker |
| Cloudflare Analytics Engine | Request observability |
| Wrangler CLI | CF Worker deployment tool |
| Render.com | Primary backend hosting |
| HuggingFace Spaces | Replica backend hosting (2x) |
| psutil | 5.9.8 | System metrics (CPU/memory) |

### Frontend

| Technology | Role |
|---|---|
| HTML5 / CSS3 / JavaScript | Legacy template UI |
| Socket.IO Client | WebSocket connection |
| React 18 (planned) | Modern SPA frontend |
| Cloudflare Pages (planned) | Frontend hosting |

---

## 📁 Project Structure

```
FlowBridge-Flask/
│
├── backend/                          # Python Flask application
│   │
│   ├── app.py                        # Main entry point
│   │                                 # Flask init, middleware, blueprints,
│   │                                 # SocketIO, TCP receiver, health check
│   │
│   ├── config.py                     # All configuration from env vars
│   │                                 # Auto-detects PUBLIC_URL (Render/ngrok/IP)
│   │
│   ├── database.py                   # MongoDB connection + index creation
│   │                                 # TTL indexes on transfers/activity/trash
│   │
│   ├── models.py                     # Data models: User, UserFile, Folder
│   │                                 # Storage-agnostic (R2/B2/MinIO)
│   │
│   ├── models_codeshare.py           # CodeShare model
│   │                                 # InMemory active users + cursors
│   │                                 # Redis cache for code content
│   │
│   ├── tcp_receiver.py               # TCP server (port 5555)
│   │                                 # Receives files via raw socket
│   │                                 # Saves to MinIO or disk fallback
│   │
│   ├── tcp_sender.py                 # TCP client
│   │                                 # Binary protocol: len+name+size+data
│   │
│   ├── websocket_transfer.py         # Socket.IO event handlers
│   │                                 # Room-based P2P file transfer
│   │                                 # CodeShare real-time editing
│   │
│   ├── autoscaling_manager.py        # CPU/memory monitor (30s interval)
│   │                                 # Logs scale suggestions
│   │
│   ├── .env                          # Environment variables (not in git)
│   │
│   ├── routes/                       # Flask Blueprints (13 total)
│   │   ├── auth_routes.py            # /api/auth/* — signup, login, JWT, refresh
│   │   ├── totp_routes.py            # /api/auth/2fa/* — TOTP setup/verify/disable
│   │   ├── user_file_routes.py       # /api/user/* — upload, download, delete, tags
│   │   ├── file_routes.py            # /api/files/* — local filesystem operations
│   │   ├── share_routes.py           # /api/share/* + /share/* — OTP share links
│   │   ├── tcp_routes.py             # /api/tcp/* — trigger TCP transfers
│   │   ├── transfer_routes.py        # /api/transfers/* — history, network info
│   │   ├── zip_routes.py             # /api/user/download-zip — bulk ZIP download
│   │   ├── activity_routes.py        # /api/user/activity — paginated feed
│   │   ├── codeshare_routes.py       # /api/codeshare/* + /code/* — CodeShare API
│   │   ├── scaling_routes.py         # /api/scaling/* — metrics for CF Worker
│   │   ├── api_docs_routes.py        # /api/docs — self-documenting API
│   │   └── advanced_routes.py        # /api/advanced/* — WASM, CRDT, GraphQL,
│   │                                 #   WebRTC, DiffSync, Prefetch, Compression
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── auth_middleware.py        # JWT token_required decorator
│   │
│   └── services/                     # Business logic layer (18 services)
│       ├── storage_service.py        # Unified R2+B2+MinIO storage
│       ├── redis_cache_service.py    # Upstash Redis + InMemory fallback
│       ├── minio_service.py          # MinIO-specific operations
│       ├── r2_service.py             # Legacy R2 service (superseded)
│       ├── email_service.py          # SMTP email notifications
│       ├── file_service.py           # Local filesystem operations
│       ├── transfer_service.py       # Transfer tracking + history
│       ├── compression_service.py    # Brotli/Zstd/gzip/lzma
│       ├── bloom_filter_service.py   # Probabilistic duplicate detection
│       ├── consistent_hash_service.py# Consistent hash ring (150 vnodes)
│       ├── crdt_service.py           # GCounter, LWW-Register, OR-Set
│       ├── differential_sync_service.py # Unified diff sync
│       ├── graphql_service.py        # GraphQL query executor
│       ├── hyperloglog_service.py    # Cardinality estimation
│       ├── merkle_tree_service.py    # File integrity verification
│       ├── predictive_prefetch_service.py # Markov chain prefetch
│       ├── smart_categorization_service.py # Auto file categorization
│       ├── wasm_service.py           # WebAssembly module registry
│       └── webrtc_service.py         # WebRTC signaling server
│
├── cloudflare-worker/
│   ├── worker.js                     # Full load balancer implementation
│   │                                 # Weighted LeastConn + Circuit Breaker
│   │                                 # Sticky routing + Rate limiting
│   └── wrangler.toml                 # CF Worker deployment config
│
├── frontend/                         # Legacy HTML/CSS/JS templates
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/
│   │   │   ├── app.js                # Main frontend logic
│   │   │   ├── transfer.js           # WebSocket transfer UI
│   │   │   ├── advanced-features.js  # Advanced features UI
│   │   │   └── webrtc-transfer.js    # WebRTC transfer UI
│   │   ├── manifest.json             # PWA manifest
│   │   └── sw.js                     # Service Worker (offline support)
│   └── templates/                    # Jinja2 HTML templates (15 pages)
│       ├── login.html / signup.html
│       ├── dashboard.html
│       ├── transfer-mode.html
│       ├── receive.html
│       ├── share_verify.html
│       ├── codeshare.html / codeshare_create.html
│       ├── activity.html / settings.html / monitor.html
│       └── ...
│
├── storage/                          # Local file storage (git-ignored)
│   ├── uploads/
│   ├── downloads/
│   └── shared/
│
├── Dockerfile                        # HuggingFace Spaces deployment
│                                     # python:3.11-slim, PORT=7860
├── docker-compose.yml                # MinIO local dev setup
├── render.yaml                       # Render.com deployment config
├── requirements.txt                  # Python dependencies (root)
└── README.md                         # This file
```

---

## 🔤 All Features A–Z

### Authentication & Security
- **Account Lockout** — 5 failed login attempts → 15-minute lock
- **Activity Feed** — Paginated log of all user actions (upload, download, share, login, etc.)
- **bcrypt Password Hashing** — 12 rounds, industry standard
- **CORS** — Whitelist-based cross-origin policy
- **CSP Headers** — Content-Security-Policy on every response
- **JWT Tokens** — HS256, 30-minute access + 7-day refresh tokens
- **OTP Share Links** — 6-digit OTP required to download shared files
- **Password Policy** — Minimum 8 chars, uppercase required, digit required
- **Rate Limiting** — Token bucket per IP at edge + per-endpoint in Flask
- **Security Headers** — X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
- **TOTP 2FA** — RFC 6238 TOTP, 30-second window, QR code setup, Google Authenticator compatible

### File Management
- **Bulk Delete** — Delete multiple files in one request
- **Bulk ZIP Download** — Download up to 50 files as a single ZIP archive
- **Comments** — Add/view comments on files (max 1000 chars)
- **Content-Type Detection** — Auto-detect MIME type on upload
- **Duplicate Detection** — SHA-256 checksum prevents storing identical files
- **File Preview** — Images, text, video, audio, PDF preview in browser
- **File Rename** — Rename files without re-uploading
- **File Tags** — Add/remove custom tags on files
- **File Versioning** — Track multiple versions of same filename
- **Folder Organization** — Create nested folders, move files between folders
- **Move Files** — Move files to different folders
- **Search** — Full-text search by filename (case-insensitive regex)
- **Sort** — Sort by name, size, upload date (ascending/descending)
- **Storage Quota** — 500MB per user, enforced on upload
- **Trash / Recycle Bin** — Soft delete with 30-day auto-purge TTL
- **Restore from Trash** — Restore soft-deleted files

### File Transfer
- **HTTP Upload/Download** — Standard multipart form upload, presigned URL download
- **TCP Direct Transfer** — Raw socket transfer on LAN (port 5555)
- **WebSocket P2P** — Room-based file chunking via Socket.IO
- **WebRTC DataChannel** — True peer-to-peer via WebRTC (signaling server included)
- **Transfer History** — MongoDB-persisted transfer log with 90-day TTL

### Sharing
- **Download Limits** — Set maximum number of downloads per share link
- **Email Notifications** — Send share link + OTP via Gmail SMTP
- **Link Expiry** — 1h / 24h / 7d / 30d configurable expiry
- **Password Protection** — Optional bcrypt-hashed password on share links
- **QR Code Generation** — PNG QR code for every share link and CodeShare URL
- **Revoke Links** — Instantly invalidate any share link
- **Scheduled Availability** — Set a future datetime when link becomes active
- **Share Analytics** — Per-link download history with timestamps and IPs

### CodeShare (Real-time Collaboration)
- **Active User Tracking** — See who is currently editing (InMemory, zero DB writes)
- **Custom URL Slugs** — Choose your own URL (e.g., `/code/my-snippet`)
- **Download as File** — Download code with correct file extension
- **Expiry** — Set TTL on code shares (MongoDB TTL index auto-deletes)
- **Language Support** — 20+ languages with extension mapping
- **Live Cursor Tracking** — See other users' cursor positions in real-time
- **Public/Private Rooms** — Control who can view and edit
- **Real-time Editing** — Socket.IO broadcast, sub-100ms latency
- **Version History** — Save named versions, browse history
- **View/Edit Counts** — Track engagement metrics

### Advanced Features (Computer Science Concepts)
- **Bloom Filter** — Probabilistic duplicate detection (1% false positive rate)
- **Compression API** — Brotli / Zstd / gzip / lzma with ratio comparison
- **Consistent Hashing** — 150 virtual nodes per physical storage node
- **CRDT** — GCounter, LWW-Register, OR-Set for distributed state
- **Differential Sync** — Unified diff-based document synchronization
- **GraphQL** — Query interface for file metadata
- **HyperLogLog** — Approximate cardinality estimation (~0.81% error)
- **Merkle Tree** — File integrity verification with proof generation
- **Predictive Prefetch** — Markov chain access pattern prediction
- **Smart Categorization** — Auto-categorize files by extension + MIME type
- **WASM Registry** — WebAssembly module registry with WAT source

---

## 📡 API Reference

### Base URLs

```
Local development:  http://localhost:5000
Render primary:     https://flowbridge-api-primary.onrender.com
HuggingFace #1:     https://{username}-flowbridge-1.hf.space
HuggingFace #2:     https://{username}-flowbridge-2.hf.space
Via CF Worker:      https://api.yourdomain.com
```

### Authentication Header

```http
Authorization: Bearer <jwt_access_token>
```

---

### Auth Endpoints

#### POST /api/auth/signup
```json
Request:  { "username": "john", "email": "john@example.com", "password": "SecurePass1" }
Response: { "success": true, "message": "Account created successfully", "username": "john" }
```

#### POST /api/auth/login
```json
Request:  { "username": "john", "password": "SecurePass1" }
Response: { "success": true, "token": "<jwt>", "refresh_token": "<jwt>",
            "user": { "id": "...", "username": "john", "email": "...",
                      "storage_used": 0, "storage_quota": 524288000 } }
// If 2FA enabled:
Response: { "success": true, "needs_2fa": true, "user_id": "..." }
```

#### POST /api/auth/refresh
```json
Request:  { "refresh_token": "<jwt>" }
Response: { "success": true, "token": "<new_access_jwt>" }
```

#### GET /api/auth/verify
```
Headers: Authorization: Bearer <token>
Response: { "success": true, "user": { ... } }
```

#### POST /api/auth/change-password
```json
Request:  { "current_password": "old", "new_password": "NewPass1" }
Response: { "success": true, "message": "Password changed successfully" }
```

---

### 2FA Endpoints

#### POST /api/auth/2fa/setup  `[AUTH]`
```json
Response: { "success": true, "secret": "BASE32SECRET",
            "qr_code": "data:image/png;base64,..." }
```

#### POST /api/auth/2fa/verify-setup  `[AUTH]`
```json
Request:  { "code": "123456" }
Response: { "success": true, "message": "2FA has been enabled!" }
```

#### POST /api/auth/2fa/validate
```json
Request:  { "user_id": "...", "code": "123456" }
Response: { "success": true, "token": "<jwt>", "refresh_token": "<jwt>" }
```

#### POST /api/auth/2fa/disable  `[AUTH]`
```json
Request:  { "code": "123456" }
Response: { "success": true, "message": "2FA has been disabled." }
```

---

### File Endpoints

#### GET /api/user/files  `[AUTH]`
```
Query params: folder_id, search, sort_by, sort_order
Response: { "success": true, "files": [...], "folders": [...],
            "count": 5, "storage_used": 1048576, "storage_quota": 524288000 }
```

#### POST /api/user/upload  `[AUTH]`
```
Content-Type: multipart/form-data
Body: file=<binary>, folder_id=<optional>
Response: { "success": true, "uploaded": [{ "file_id": "...", "filename": "...",
            "size": 1024, "checksum": "sha256..." }], "errors": [] }
```

#### GET /api/user/download/\<file_id\>  `[AUTH]`
```
Response: 302 redirect to R2/B2/MinIO presigned URL (15-minute expiry)
```

#### DELETE /api/user/delete/\<file_id\>  `[AUTH]`
```
Query: ?permanent=true (hard delete) or omit (soft delete to trash)
Response: { "success": true, "message": "File moved to trash" }
```

#### PATCH /api/user/files/\<file_id\>/rename  `[AUTH]`
```json
Request:  { "new_name": "report_v2.pdf" }
Response: { "success": true, "message": "Renamed to report_v2.pdf" }
```

#### PUT /api/user/file/\<file_id\>/move  `[AUTH]`
```json
Request:  { "folder_id": "abc123" }  // null = move to root
Response: { "success": true, "message": "File moved" }
```

#### POST /api/user/download-zip  `[AUTH]`
```json
Request:  { "file_ids": ["id1", "id2", "id3"] }
Response: application/zip binary stream
```

#### POST /api/user/bulk-delete  `[AUTH]`
```json
Request:  { "file_ids": ["id1", "id2"] }
Response: { "success": true, "deleted": 2 }
```

#### GET /api/user/preview/\<file_id\>  `[AUTH via query ?token=]`
```
Response: For text → JSON with content
          For image/video/audio/PDF → binary stream with correct MIME type
```

#### POST /api/user/files/\<file_id\>/tags  `[AUTH]`
```json
Request:  { "tags": ["important", "work"] }
Response: { "success": true, "message": "Tags added" }
```

#### POST /api/user/files/\<file_id\>/comments  `[AUTH]`
```json
Request:  { "text": "Review this before Monday" }
Response: { "success": true, "message": "Comment added" }
```

---

### Share Endpoints

#### POST /api/share/generate  `[AUTH]`
```json
Request: {
  "file_id": "abc123",
  "expiry_hours": 24,
  "max_downloads": 10,
  "password": "optional",
  "message": "Here is the file you requested",
  "notify_email": "recipient@example.com",
  "available_after": "2025-01-01T00:00:00Z"
}
Response: {
  "success": true,
  "share_link": "https://api.yourdomain.com/share/xY9kL2...",
  "share_token": "xY9kL2mN4pQ6rS8t...",
  "otp": "847291",
  "qr_code": "data:image/png;base64,...",
  "expires_at": "2025-01-02 10:30:00",
  "has_password": false
}
```

#### POST /api/share/verify-otp
```json
Request:  { "share_token": "xY9kL2...", "otp": "847291", "password": "optional" }
Response: { "success": true, "download_url": "/share/xY9kL2.../download" }
```

#### GET /share/\<token\>/download
```
Response: 302 redirect to R2 presigned URL
          download_count incremented, otp_verified reset
```

#### GET /api/share/active  `[AUTH]`
```json
Response: { "success": true, "shares": [{ "token": "...", "filename": "...",
            "otp": "...", "link": "...", "download_count": 3, ... }] }
```

#### DELETE /api/share/revoke/\<token\>  `[AUTH]`
```json
Response: { "success": true, "message": "Link revoked" }
```

#### GET /api/share/analytics/\<token\>  `[AUTH]`
```json
Response: { "success": true, "download_count": 5,
            "downloads": [{ "timestamp": "...", "ip": "..." }] }
```

---

### TCP Transfer Endpoints

#### POST /api/tcp/send  `[AUTH]`
```json
Request:  { "file_id": "abc123", "receiver_ip": "192.168.1.100", "receiver_port": 5555 }
Response: { "success": true, "message": "Transfer started: file.zip → 192.168.1.100:5555" }
```

---

### CodeShare Endpoints

#### POST /api/codeshare/create
```json
Request: {
  "code": "print('hello')",
  "language": "python",
  "title": "My Snippet",
  "custom_slug": "my-snippet",
  "expiry_hours": 24,
  "allow_edit": true
}
Response: { "success": true, "slug": "my-snippet",
            "share_url": "https://api.yourdomain.com/code/my-snippet",
            "qr_code": "data:image/png;base64,..." }
```

#### GET /api/codeshare/\<slug\>
```json
Response: { "success": true, "slug": "...", "code": "...", "language": "python",
            "active_users": [...], "view_count": 42, "allow_edit": true }
```

#### POST /api/codeshare/\<slug\>/update
```json
Request:  { "code": "updated code", "editor_name": "Alice", "save_version": true }
Response: { "success": true, "message": "Code updated successfully" }
```

---

### Scaling / Health Endpoints

#### GET /health
```json
Response: {
  "status": "healthy",
  "database": "connected",
  "version": "3.0.0",
  "instance": "render-primary",
  "uptime_seconds": 3600,
  "metrics": { "cpu_percent": 12.3, "memory_percent": 45.1, "memory_free_mb": 512 },
  "storage": { "r2": true, "b2": true, "minio": false },
  "cache": { "upstash": true }
}
// 200 if healthy, 503 if degraded
```

#### GET /api/scaling/metrics  `[PUBLIC — read by CF Worker]`
```json
Response: {
  "instance": "render-primary",
  "cpu_percent": 12.3,
  "mem_percent": 45.1,
  "latency": { "p50": 45.2, "p95": 120.5, "p99": 350.1, "count": 87 },
  "requests": { "total": 1024, "errors": 3, "error_rate": 0.29 },
  "load_score": 28.4
}
```

#### GET /api/scaling/health
```json
Response: { "status": "healthy", "cpu_percent": 12.3, "mem_percent": 45.1,
            "p95_ms": 120.5, "instance": "render-primary" }
// 200 if healthy, 503 if overloaded (CF Worker removes from pool)
```

---

## 🔌 WebSocket Events

All WebSocket communication uses Socket.IO over the `/socket.io` path.

### File Transfer Events

| Event (Client → Server) | Payload | Description |
|---|---|---|
| `create_room` | `{ username }` | Receiver creates room, gets 6-char code |
| `join_transfer_room` | `{ room_code, username }` | Sender joins room with code |
| `file_transfer_start` | `{ room, filename, file_size, total_chunks }` | Announce incoming file |
| `send_file_chunk` | `{ room, chunk, chunk_index, total_chunks, filename, file_size }` | Send one chunk |
| `file_transfer_complete` | `{ room, filename, success, checksum }` | Signal completion |
| `cancel_transfer` | `{ room }` | Cancel ongoing transfer |
| `leave_transfer_room` | `{ room_code }` | Close room |

| Event (Server → Client) | Payload | Description |
|---|---|---|
| `room_created` | `{ room_code, message }` | Room ready, share this code |
| `room_joined` | `{ room_code, room, receiver }` | Sender confirmed in room |
| `sender_connected` | `{ room_code, sender }` | Receiver notified of sender |
| `receive_file_chunk` | `{ chunk, chunk_index, total_chunks, filename }` | Forwarded chunk |
| `incoming_file` | `{ filename, file_size, total_chunks }` | File about to arrive |
| `transfer_progress` | `{ filename, progress, chunk_index, total_chunks }` | Progress % |
| `transfer_complete` | `{ filename, success, checksum }` | Transfer done |
| `transfer_cancelled` | `{ message }` | Transfer cancelled |
| `peer_disconnected` | `{ message }` | Other party left |

### CodeShare Events

| Event (Client → Server) | Payload | Description |
|---|---|---|
| `codeshare_join` | `{ slug, user_id, user_name }` | Join editing session |
| `codeshare_leave` | `{ slug, user_id, user_name }` | Leave session |
| `codeshare_edit` | `{ slug, code, user_id, user_name, cursor }` | Broadcast code change |
| `codeshare_cursor` | `{ slug, user_id, user_name, cursor }` | Update cursor position |
| `codeshare_save` | `{ slug, code, user_name, save_version }` | Save to database |

| Event (Server → Client) | Payload | Description |
|---|---|---|
| `codeshare_user_joined` | `{ user_id, user_name }` | New user joined |
| `codeshare_user_left` | `{ user_id, user_name }` | User left |
| `codeshare_active_users` | `{ active_users: [...] }` | Current user list |
| `codeshare_code_update` | `{ code, user_id, user_name, cursor }` | Code changed by peer |
| `codeshare_cursor_update` | `{ user_id, user_name, cursor }` | Peer cursor moved |
| `codeshare_saved` | `{ success, message }` | Save confirmed |
| `codeshare_notification` | `{ message, type }` | System notification |
| `codeshare_error` | `{ error }` | Error message |

### TCP Transfer Events (Server → Client via SocketIO)

| Event | Payload | Description |
|---|---|---|
| `transfer_started` | `{ filename, size, source, transfer_id }` | TCP transfer began |
| `transfer_progress` | `{ transfer_id, filename, progress, received, total }` | Bytes received |
| `transfer_complete` | `{ filename, success, transfer_id }` | TCP transfer done |

---

## 🔄 Execution Flow

### 1. Application Startup Flow

```
python app.py
      │
      ├─ 1. Load .env (python-dotenv)
      ├─ 2. Config.init_app()
      │       ├─ Detect PUBLIC_URL (env → Render → ngrok → public IP → localhost)
      │       └─ Validate MONGO_URI present
      │
      ├─ 3. Flask app init
      │       ├─ CORS (all origins)
      │       ├─ Flask-Compress (exclude /socket.io)
      │       └─ Flask-Limiter (memory:// storage)
      │
      ├─ 4. SocketIO init
      │       └─ Detect async_mode: eventlet → gevent → threading
      │
      ├─ 5. Database.initialize()
      │       ├─ MongoClient connect (30s timeout)
      │       ├─ Ping admin
      │       └─ Create all indexes (TTL, unique, compound)
      │
      ├─ 6. StorageService init
      │       ├─ R2 boto3 client (if R2_ACCOUNT_ID set)
      │       ├─ B2 boto3 client (if B2_ENDPOINT_URL set)
      │       └─ MinIO boto3 client (if MINIO_ACCESS_KEY set)
      │
      ├─ 7. CacheService init
      │       ├─ Upstash PING test (8s timeout)
      │       └─ Fallback to InMemory if unavailable
      │
      ├─ 8. Register 13 Blueprints
      │
      ├─ 9. Register WebSocket events (websocket_transfer.py)
      │
      ├─ 10. Create storage directories (uploads/downloads/shared)
      │
      ├─ 11. Start TCPReceiver (background thread, port 5555)
      │        └─ Skipped if RENDER env var set
      │
      └─ 12. socketio.run(host=0.0.0.0, port=PORT)
```

### 2. File Upload Flow

```
Client: POST /api/user/upload
        Authorization: Bearer <token>
        Content-Type: multipart/form-data
              │
              ▼
        token_required decorator
              │ JWT decode → User.find_by_id()
              ▼
        Read file bytes from request
              │
              ▼
        compute_checksum(file_data) → SHA-256
              │
              ▼
        UserFile.check_duplicate(user_id, checksum)
              │ MongoDB: find_one({user_id, checksum, not deleted})
              │ If found → return 400 "Duplicate"
              ▼
        User.check_storage_quota(user_id, file_size)
              │ If exceeded → return 400 "Quota exceeded"
              ▼
        storage.upload(file_data, filename, content_type)
              │
              ├─ SHA-256 → storage key: files/{h[:2]}/{h[2:]}
              │
              ├─ R2: _object_exists() → if new: put_object() [SYNC]
              │       └─ Raises RuntimeError if R2 fails
              │
              ├─ B2: threading.Thread(_b2_replicate) [ASYNC]
              │       └─ put_object() in background
              │
              └─ MinIO: threading.Thread(_minio_replicate) [ASYNC]
                        └─ put_object() in background
              │
              ▼
        db.user_files.insert_one(file_meta)
              │ {user_id, filename, size, content_type, checksum,
              │  r2_key, b2_key, minio_key, storage_backend,
              │  b2_synced: False, minio_synced: False, uploaded_at, ...}
              │
              ▼
        User.update_storage(user_id, +file_size)
              │ MongoDB $inc storage_used
              │ Redis invalidate user:storage:{uid}
              │
              ▼
        cache.invalidate_file_list(user_id)
              │ Redis DEL files:list:{uid}
              │
              ▼
        Return 200: { file_id, filename, size, checksum }
```

### 3. File Download Flow

```
Client: GET /api/user/download/<file_id>
        Authorization: Bearer <token>
              │
              ▼
        token_required → current_user
              │
              ▼
        UserFile.get_file_meta(file_id, user_id)
              │ MongoDB: find_one({_id: ObjectId(file_id),
              │                    user_id: str, is_deleted: {$ne: true}})
              │ If not found → 404
              ▼
        UserFile.get_file_stream(file_meta)
              │
              └─ storage.get_download_url(r2_key, b2_key, minio_key)
                        │
                        ├─ Try R2: generate_presigned_url (15 min)
                        ├─ Try B2: generate_presigned_url (fallback)
                        └─ Try MinIO: generate_presigned_url (fallback)
              │
              ▼
        return redirect(presigned_url)  [302]
        Client downloads directly from R2/B2/MinIO
        (no bandwidth through Flask server)
```

### 4. Share Link Download Flow

```
Recipient: GET /share/<token>
                 │
                 ▼
           share_tokens.find_one({token})
           Check: expired? download_limit_reached?
                 │
                 ▼
           Render share_verify.html
           (shows filename, sender, OTP input)
                 │
                 ▼
           POST /api/share/verify-otp
           { share_token, otp, password? }
                 │
                 ├─ Check OTP lockout (3 attempts → 15 min lock)
                 ├─ Verify OTP matches
                 ├─ Verify password (bcrypt) if required
                 └─ Set otp_verified = True
                 │
                 ▼
           GET /share/<token>/download
                 │
                 ├─ Verify otp_verified = True
                 ├─ db.user_files.find_one({_id: ObjectId(file_id)})
                 ├─ UserFile.get_file_stream(file_meta)
                 ├─ $inc download_count
                 ├─ $push downloads [{timestamp, ip}]
                 ├─ $set otp_verified = False (reset for next download)
                 └─ redirect(presigned_url)
```

### 5. WebSocket P2P Transfer Flow

```
RECEIVER                    SERVER                      SENDER
   │                           │                           │
   │── emit('create_room') ───►│                           │
   │                           │ Generate 6-char code      │
   │                           │ active_rooms[code] = {...} │
   │◄── emit('room_created') ──│                           │
   │    { room_code: "AB3X7K" }│                           │
   │                           │                           │
   │  [share code with sender] │                           │
   │                           │                           │
   │                           │◄── emit('join_transfer_room', {code}) ──│
   │                           │ join_room(room_name)      │
   │                           │──── emit('room_joined') ─►│
   │◄── emit('sender_connected')│                          │
   │                           │                           │
   │                           │◄── emit('file_transfer_start') ────────│
   │◄── emit('incoming_file') ─│                           │
   │                           │                           │
   │                           │◄── emit('send_file_chunk', chunk_0) ───│
   │◄── emit('receive_file_chunk', chunk_0) ──────────────────────────  │
   │                           │◄── emit('send_file_chunk', chunk_1) ───│
   │◄── emit('receive_file_chunk', chunk_1) ──────────────────────────  │
   │         ...               │         ...               │
   │                           │◄── emit('file_transfer_complete') ─────│
   │◄── emit('transfer_complete')│                         │
   │  Reassemble chunks        │                           │
   │  Trigger download         │                           │
```

---

## 🔒 Security Architecture

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    JWT Token Lifecycle                          │
│                                                                 │
│  Login → Access Token (30 min, HS256)                          │
│       → Refresh Token (7 days, HS256)                          │
│                                                                 │
│  Access Token payload:                                          │
│    { user_id, username, type: "access", exp: <timestamp> }     │
│                                                                 │
│  Refresh Token payload:                                         │
│    { user_id, type: "refresh", exp: <timestamp> }              │
│                                                                 │
│  Rotation: POST /api/auth/refresh → new access token           │
│  Storage: Client-side only (localStorage / memory)             │
└─────────────────────────────────────────────────────────────────┘
```

### 2FA Flow

```
Setup:
  1. POST /api/auth/2fa/setup
     → pyotp.random_base32() → secret stored in DB (not yet enabled)
     → provisioning_uri → QR code PNG → base64 → client
  2. User scans QR with Google Authenticator / Authy
  3. POST /api/auth/2fa/verify-setup { code: "123456" }
     → pyotp.TOTP(secret).verify(code, valid_window=1)
     → totp_enabled = True in DB

Login with 2FA:
  1. POST /api/auth/login → { needs_2fa: true, user_id }
  2. POST /api/auth/2fa/validate { user_id, code }
     → verify TOTP → issue JWT
```

### OTP Share Link Security

```
Generation:
  → random.randint(100000, 999999) — 6-digit OTP
  → Stored in MongoDB share_tokens collection
  → TTL index auto-deletes on expiry

Brute-force protection:
  → 3 attempts max (OTP_MAX_ATTEMPTS)
  → After 3 failures: 15-minute lockout (OTP_LOCKOUT_MINUTES)
  → otp_locked_until stored in MongoDB

Replay protection:
  → otp_verified reset to False after each download
  → Recipient must re-enter OTP for each download
```

### Security Headers (every response)

```
X-Content-Type-Options:  nosniff
X-Frame-Options:         SAMEORIGIN
X-XSS-Protection:        1; mode=block
Referrer-Policy:         strict-origin-when-cross-origin
Permissions-Policy:      camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'
                         'unsafe-eval' https://cdn.socket.io ...
```

### IDOR Protection

Every file operation verifies ownership:
```python
# All queries include user_id check
db.user_files.find_one({
    "_id": ObjectId(file_id),
    "user_id": str(user_id),      # ← ownership check
    "is_deleted": {"$ne": True}
})
# Returns None if file belongs to different user → 404
```

---

## 💾 Storage Architecture

### Content-Addressable Key Design

```
File: "report.pdf" (SHA-256: abcdef1234567890...)

Storage key: files/ab/cdef1234567890...
                   ││  └─ remaining 62 chars
                   │└─ chars 2-3 (sub-prefix)
                   └─ chars 0-1 (prefix bucket)

Same key on ALL backends:
  R2:    flowbridge-files/files/ab/cdef1234...
  B2:    flowbridge-files-replica/files/ab/cdef1234...
  MinIO: flowbridge-files/files/ab/cdef1234...

Benefits:
  → Cross-backend deduplication (same key = same file)
  → Prefix distribution (256 possible top-level prefixes)
  → Immutable (content never changes, key never changes)
  → Integrity check (re-hash file → compare to key)
```

### Storage Backend Comparison

```
┌─────────────────┬──────────────┬──────────────┬──────────────┐
│ Property        │ R2 (Primary) │ B2 (Replica) │ MinIO (Local)│
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ Latency (HYD)   │ ~5ms         │ ~120ms       │ ~0ms         │
│ Egress cost     │ FREE         │ FREE via CF  │ FREE         │
│ Durability      │ 11 nines     │ 11 nines     │ Disk-based   │
│ Write mode      │ Synchronous  │ Async thread │ Async thread │
│ Addressing      │ Virtual-host │ Path-style   │ Path-style   │
│ Region          │ Mumbai PoP   │ EU Central   │ localhost    │
│ Use case        │ Primary read │ Geo replica  │ LAN transfer │
│ Presigned URLs  │ Yes (15 min) │ Yes (15 min) │ Yes (15 min) │
└─────────────────┴──────────────┴──────────────┴──────────────┘
```

### MongoDB Collections Schema

```javascript
// users
{
  _id: ObjectId,
  username: String (unique index),
  email: String (unique index),
  password: Binary (bcrypt hash),
  created_at: Date,
  storage_used: Number,
  storage_quota: Number (default: 524288000 = 500MB),
  failed_login_attempts: Number,
  locked_until: Date | null,
  totp_secret: String | null,
  totp_enabled: Boolean
}

// user_files
{
  _id: ObjectId,
  user_id: String,
  filename: String,
  size: Number,
  content_type: String,
  checksum: String (SHA-256),
  r2_key: String | null,
  b2_key: String | null,
  minio_key: String | null,
  storage_backend: "r2" | "b2" | "minio",
  b2_synced: Boolean,
  minio_synced: Boolean,
  uploaded_at: Date,
  folder_id: String | null,
  tags: [String],
  is_deleted: Boolean,
  deleted_at: Date | null,
  version: Number,
  comments: [{ user, text, timestamp }]
}
// Indexes: (user_id, uploaded_at), checksum, b2_synced, minio_synced

// share_tokens
{
  _id: ObjectId,
  token: String (unique index),
  file_id: String,
  user_id: String,
  filename: String,
  file_size: Number,
  otp: String,
  otp_verified: Boolean,
  otp_attempts: Number,
  otp_locked_until: Date | null,
  password_hash: String | null,
  message: String,
  available_after: Date | null,
  created_at: Date,
  expires_at: Date (TTL index → auto-delete),
  max_downloads: Number,
  download_count: Number,
  sender_username: String,
  downloads: [{ timestamp, ip }]
}

// transfers
{
  _id: ObjectId,
  id: String (transfer UUID),
  filename: String,
  size: Number,
  source: String,
  user_id: String | null,
  progress: Number,
  status: "active" | "completed" | "failed",
  started_at: Date (TTL index → 90-day auto-delete),
  completed_at: Date | null
}

// activity_log
{
  _id: ObjectId,
  user_id: String,
  action: String,
  details: Object,
  timestamp: Date (TTL index → 30-day auto-delete)
}

// folders
{
  _id: ObjectId,
  user_id: String,
  name: String,
  parent_id: String | null,
  created_at: Date
}
// Index: (user_id, parent_id)

// trash
{
  _id: ObjectId,
  original_file: { _id, filename, size, r2_key, b2_key, minio_key },
  user_id: String,
  deleted_at: Date (TTL index → 30-day auto-delete)
}

// codeshares
{
  _id: ObjectId,
  slug: String (unique index),
  title: String,
  code: String,
  language: String,
  creator_id: String | null,
  creator_name: String,
  is_public: Boolean,
  allow_edit: Boolean,
  created_at: Date,
  updated_at: Date,
  expires_at: Date | null (TTL index → auto-delete),
  view_count: Number,
  edit_count: Number,
  active_users: [],  // NOT stored in DB — InMemory only
  version_history: [{ version, code, edited_by, edited_at }],
  collaborators: [String]
}
```

---

## ⚖️ Load Balancer Deep Dive

### Weighted Least-Connections Algorithm

```javascript
// For each healthy backend, compute score:
score = adaptiveWeight / (activeConnections + 1)

// Backend with HIGHEST score wins

Example with 3 backends:
  HF-1:   weight=3, connections=2  → score = 3/3 = 1.00  ← WINNER
  HF-2:   weight=3, connections=5  → score = 3/6 = 0.50
  Render: weight=1, connections=0  → score = 1/1 = 1.00  (tie, HF-1 wins by order)

Traffic distribution (approximate):
  HF-1:   ~43% (weight 3)
  HF-2:   ~43% (weight 3)
  Render: ~14% (weight 1)
```

### Adaptive Weight Adjustment

```javascript
// CF Worker reads /api/scaling/metrics from each backend every minute
// Adjusts weights based on p95 latency:

if (p95 > 2000ms):  weight = max(1, floor(baseWeight / 2))  // degraded
if (p95 < 500ms):   weight = baseWeight                      // healthy
else:               weight = max(1, baseWeight - 1)          // slightly reduced

// load_score (0-100) from backend:
load_score = (cpu * 0.5) + (memory * 0.3) + (min(p95/30, 20))
// CF Worker uses this for weight decisions
```

### Sticky Routing (WebSocket + CodeShare)

```javascript
// Problem: WebSocket rooms are in-memory per process
//          If user switches backends mid-session → room not found

// Solution: Hash JWT user_id → consistent backend index
function getStickyBackendId(request, url) {
  if (!url.pathname.startsWith("/socket.io") &&
      !url.pathname.startsWith("/api/codeshare")) return null;

  const token = request.headers.get("Authorization").replace("Bearer ", "");
  const payload = JSON.parse(atob(token.split(".")[1]));
  const userId = payload.user_id;

  let hash = 0;
  for (let i = 0; i < userId.length; i++) hash += userId.charCodeAt(i);
  return BACKENDS[hash % BACKENDS.length].id;
}
// Same user_id → same hash → same backend → room found
```

### Circuit Breaker State Transitions

```
Trigger: 5 consecutive failures (HTTP 5xx or timeout)

CLOSED → OPEN:
  circuit.failures >= 5
  circuit.state = "OPEN"
  circuit.openedAt = Date.now()
  All requests to this backend → immediate 502

OPEN → HALF-OPEN:
  Date.now() - circuit.openedAt > 30000 (30 seconds)
  One probe request allowed through

HALF-OPEN → CLOSED (recovery):
  Probe request succeeds (HTTP 2xx/3xx/4xx)
  circuit.state = "CLOSED"
  circuit.failures = 0

HALF-OPEN → OPEN (still broken):
  Probe request fails
  circuit.state = "OPEN"
  circuit.openedAt = Date.now()  (reset timer)
```

### Rate Limiting (Token Bucket)

```
Per-IP token bucket stored in Cloudflare KV:

bucket = { tokens: 200, lastRefill: timestamp }

On each request:
  elapsed = (now - lastRefill) / 60000  // minutes
  tokens = min(200, tokens + elapsed * 200)  // refill
  if tokens < 1: return 429
  tokens -= 1
  save to KV

Result: 200 requests/minute per IP, burst allowed up to 200
        Smooth refill (not hard reset every minute)
```

---

## 📊 Performance Metrics

### Latency Targets

```
┌─────────────────────────────────────────────────────────────────┐
│  Operation                    Target      Actual (estimated)    │
├─────────────────────────────────────────────────────────────────┤
│  CF Worker routing            < 1ms       ~0.5ms               │
│  R2 file upload (1MB)         < 200ms     ~50-150ms            │
│  R2 presigned URL generation  < 50ms      ~10-30ms             │
│  MongoDB metadata write       < 50ms      ~20-40ms             │
│  Redis cache hit              < 10ms      ~5-8ms               │
│  Redis cache miss + DB query  < 100ms     ~40-80ms             │
│  JWT verification             < 1ms       ~0.1ms               │
│  bcrypt password verify       < 200ms     ~100-150ms           │
│  SHA-256 checksum (10MB file) < 50ms      ~20-30ms             │
│  QR code generation           < 100ms     ~50-80ms             │
│  TCP transfer (LAN, 100MB)    < 1s        ~0.8s (1Gbps LAN)   │
└─────────────────────────────────────────────────────────────────┘
```

### Throughput Capacity

```
Per backend instance (Render free tier / HuggingFace):
  → ~50-100 concurrent HTTP requests
  → ~200 concurrent WebSocket connections
  → ~20 concurrent file uploads (rate limited)

With 3 backends behind CF Worker:
  → ~150-300 concurrent HTTP requests
  → ~600 concurrent WebSocket connections

Storage throughput:
  → R2: No stated limit (Cloudflare infrastructure)
  → B2: 2500 download requests/day free tier
  → MinIO: Limited by local disk I/O (~500MB/s SSD)
```

### Cache Performance

```
Redis cache hit rate (typical):
  → File list: ~80% hit rate (5-min TTL, invalidated on change)
  → CodeShare: ~60% hit rate (30-sec TTL, frequent edits)
  → User storage: ~85% hit rate (5-min TTL)

Cache miss cost:
  → MongoDB query: ~20-40ms
  → Cache set: ~5ms
  → Total on miss: ~25-45ms

Cache hit cost:
  → Redis GET: ~5-8ms (Upstash Singapore)
  → Total on hit: ~5-8ms

Speedup: ~5-8x faster on cache hit
```

### Storage Efficiency

```
Deduplication savings (content-addressable storage):
  → 1000 users upload same 10MB file
  → Without CAS: 10GB stored
  → With CAS:    10MB stored (99.9% savings)

Compression ratios (typical):
  → Text/code files:  Brotli ~70-80% reduction
  → JSON/XML:         Zstd   ~60-75% reduction
  → Already-compressed (jpg/mp4/zip): ~0% (skipped)

MongoDB TTL auto-cleanup:
  → Transfers:    90-day TTL → prevents unbounded growth
  → Activity log: 30-day TTL → ~30 entries/user/day max
  → Trash:        30-day TTL → soft-deleted files auto-purged
  → Share tokens: expires_at TTL → expired links auto-deleted
```

### Scaling Thresholds

```
AutoscalingManager triggers:
  SCALE_UP_SUGGESTED:   CPU > 80%
  SCALE_DOWN_SUGGESTED: CPU < 20%
  Check interval:       30 seconds

CF Worker adaptive weight reduction:
  p95 > 2000ms → weight halved
  p95 < 500ms  → weight restored

Health check failure → circuit open:
  5 consecutive failures
  30-second recovery window
```

---

## ⚙️ Configuration Reference

### Environment Variables (backend/.env)

```env
# ── MongoDB Atlas ──────────────────────────────────────────────────
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/

# ── Security Keys (generate with: python -c "import secrets; print(secrets.token_hex(32))")
SECRET_KEY=your-64-char-hex-string
JWT_SECRET_KEY=your-other-64-char-hex-string

# ── Server ─────────────────────────────────────────────────────────
PORT=5000                          # Overridden by Render/HuggingFace
TCP_PORT=5555                      # TCP receiver port
MAX_FILE_SIZE_MB=2048              # Max upload size (2GB default)
LOG_LEVEL=INFO                     # DEBUG / INFO / WARNING / ERROR

# ── Cloudflare R2 (Primary Storage) ────────────────────────────────
R2_ACCOUNT_ID=your-cf-account-id
R2_ACCESS_KEY_ID=your-r2-key-id
R2_SECRET_ACCESS_KEY=your-r2-secret
R2_BUCKET_FILES=flowbridge-files
R2_BUCKET_THUMBS=flowbridge-thumbs
R2_BUCKET_ZIPS=flowbridge-zips

# ── Backblaze B2 (Global Replica) ──────────────────────────────────
B2_ENDPOINT_URL=https://s3.eu-central-003.backblazeb2.com
B2_ACCESS_KEY_ID=your-b2-key-id
B2_SECRET_ACCESS_KEY=your-b2-secret
B2_BUCKET_FILES=flowbridge-files-replica
B2_BUCKET_THUMBS=flowbridge-thumbs-replica
B2_BUCKET_ZIPS=flowbridge-zips-replica

# ── MinIO (Local Replica) ──────────────────────────────────────────
MINIO_ACCESS_KEY=flowbridge_admin
MINIO_SECRET_KEY=flowbridge_secret_change_me
MINIO_ENDPOINT_URL=http://localhost:9000
MINIO_PUBLIC_ENDPOINT_URL=http://localhost:9000
MINIO_BUCKET_FILES=flowbridge-files
MINIO_BUCKET_THUMBS=flowbridge-thumbs
MINIO_BUCKET_ZIPS=flowbridge-zips

# ── Upstash Redis (Cache) ──────────────────────────────────────────
UPSTASH_REDIS_REST_URL=https://your-instance.upstash.io
UPSTASH_REDIS_REST_TOKEN=your-upstash-token

# ── Email (Optional) ───────────────────────────────────────────────
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-gmail-app-password
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587

# ── Public URL (auto-detected if not set) ──────────────────────────
PUBLIC_URL=https://api.yourdomain.com
```

### All Config Values with Defaults

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | **required** | MongoDB Atlas connection string |
| `SECRET_KEY` | auto-generated | Flask session secret (random on restart if not set) |
| `JWT_SECRET_KEY` | auto-generated | JWT signing key (random on restart if not set) |
| `JWT_ACCESS_EXPIRY_MINUTES` | 30 | Access token lifetime |
| `JWT_REFRESH_EXPIRY_DAYS` | 7 | Refresh token lifetime |
| `PORT` / `HTTP_PORT` | 5000 | HTTP server port |
| `TCP_PORT` | 5555 | TCP receiver port |
| `MAX_FILE_SIZE_MB` | 2048 | Max upload size in MB |
| `LOG_LEVEL` | INFO | Logging verbosity |
| `RATE_LIMIT_DEFAULT` | 200/minute | Default rate limit |
| `RATE_LIMIT_LOGIN` | 5/minute | Login endpoint limit |
| `RATE_LIMIT_UPLOAD` | 20/minute | Upload endpoint limit |
| `OTP_MAX_ATTEMPTS` | 3 | OTP attempts before lockout |
| `OTP_LOCKOUT_MINUTES` | 15 | OTP lockout duration |
| `SHARE_DEFAULT_EXPIRY_HOURS` | 24 | Default share link expiry |
| `PASSWORD_MIN_LENGTH` | 8 | Minimum password length |
| `BUFFER_SIZE` | 65536 | TCP transfer buffer (64KB) |
| `CHUNK_SIZE` | 1048576 | Streaming chunk size (1MB) |

---

## 🚀 Deployment Guide

### Step 1 — Deploy Render.com (Primary Backend)

```bash
# 1. Push code to GitHub
git add .
git commit -m "Deploy FlowBridge v3.0"
git push origin main

# 2. Go to https://render.com → New → Web Service
# 3. Connect your GitHub repository
# 4. Render auto-reads render.yaml — no manual config needed

# 5. Add environment variables in Render dashboard:
#    MONGO_URI, SECRET_KEY, JWT_SECRET_KEY,
#    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
#    B2_ENDPOINT_URL, B2_ACCESS_KEY_ID, B2_SECRET_ACCESS_KEY,
#    UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN,
#    EMAIL_USER, EMAIL_PASS (optional)

# 6. Deploy → get URL: https://flowbridge-api-primary.onrender.com
```

### Step 2 — Deploy HuggingFace Spaces (2 Replicas)

```bash
# Create Space #1:
# 1. Go to https://huggingface.co/new-space
# 2. Space name: flowbridge-1
# 3. SDK: Docker
# 4. Push code:

git remote add hf1 https://huggingface.co/spaces/YOUR_USERNAME/flowbridge-1
git push hf1 main

# 5. Add secrets in HF Space settings (same env vars as Render)
# 6. Get URL: https://YOUR_USERNAME-flowbridge-1.hf.space

# Repeat for Space #2 (flowbridge-2)
# Get URL: https://YOUR_USERNAME-flowbridge-2.hf.space
```

### Step 3 — Deploy Cloudflare Worker (Load Balancer)

```bash
# 1. Install Wrangler
npm install -g wrangler
wrangler login

# 2. Create KV namespace
cd cloudflare-worker
wrangler kv:namespace create "FLOWBRIDGE_KV"
# Copy the id it prints

# 3. Update wrangler.toml:
#    - Replace REPLACE_WITH_YOUR_KV_NAMESPACE_ID with the id from step 2
#    - Replace api.yourdomain.com/* with your actual domain
#    - Replace REPLACE_WITH_YOUR_ZONE_ID with your CF Zone ID
#      (find in CF Dashboard → your domain → right sidebar)

# 4. Update worker.js BACKENDS array with real URLs:
#    url: "https://YOUR_USERNAME-flowbridge-1.hf.space"
#    url: "https://YOUR_USERNAME-flowbridge-2.hf.space"
#    url: "https://flowbridge-api-primary.onrender.com"

# 5. Deploy
wrangler deploy

# Worker is now live at https://api.yourdomain.com
# Routing traffic from 310 edge locations worldwide
```

### Step 4 — Start MinIO (Local Development)

```bash
# Requires Docker Desktop
docker-compose up -d minio createbuckets

# MinIO Console: http://localhost:9001
# Login: flowbridge_admin / flowbridge_secret_change_me

# Verify:
docker ps  # should show flowbridge-minio running
```

### Step 5 — Run Backend Locally

```bash
cd backend
pip install -r ../requirements.txt
python app.py

# Output:
# ============================================================
#  FlowBridge Hybrid File Transfer System v3.0
# ============================================================
#  Public URL : http://localhost:5000
#  HTTP Port  : 5000
#  TCP Port   : 5555
#  R2 Primary : ✅
#  B2 Replica : ✅  (EU Central)
#  MinIO Local: ✅ (localhost:9000)
#  Cache      : ✅ Upstash
#  Async Mode : eventlet
# ============================================================
```

### Deployment Architecture Summary

```
After all 4 steps:

User Request
     │
     ▼
Cloudflare Edge (310 PoPs)
     │ worker.js
     │ Rate limit → Bot check → Select backend
     ▼
┌────────────────────────────────────────┐
│  HF-1 (weight=3) ← ~43% traffic       │
│  HF-2 (weight=3) ← ~43% traffic       │
│  Render (weight=1) ← ~14% traffic     │
└────────────────────────────────────────┘
     │
     ▼
Flask Backend
     │
     ├─ MongoDB Atlas (metadata)
     ├─ Cloudflare R2 (files, primary)
     ├─ Backblaze B2 (files, replica)
     └─ Upstash Redis (cache)
```

---

## 🎓 Academic Context

This project was built for the **Computer Networks** course at **Vasavi College of Engineering, Hyderabad** (Semester 5). It demonstrates practical implementation of every major networking and distributed systems concept covered in the curriculum.

### Computer Networks Concepts Demonstrated

| Concept | Where Implemented |
|---|---|
| **TCP/IP Socket Programming** | `tcp_receiver.py`, `tcp_sender.py` — raw socket, bind, listen, accept, send/recv |
| **Application Layer Protocols** | HTTP/HTTPS REST API (Flask), WebSocket (Socket.IO), WebRTC |
| **Transport Layer** | TCP for file transfer (reliable, ordered), UDP-like for WebRTC |
| **Binary Protocol Design** | TCP protocol: `[4B len][filename][8B size][data]` — big-endian struct packing |
| **Client-Server Architecture** | Flask REST API serving browser clients |
| **Peer-to-Peer Architecture** | WebSocket room-based relay, WebRTC direct connection |
| **DNS & CDN** | Cloudflare Worker at edge, CF CDN for static assets |
| **Load Balancing** | Weighted Least-Connections algorithm in CF Worker |
| **HTTP Methods** | GET, POST, PUT, DELETE, PATCH, OPTIONS all used |
| **HTTP Status Codes** | 200, 201, 302, 400, 401, 403, 404, 410, 429, 500, 503 |
| **WebSocket Protocol** | Full-duplex, event-driven communication via Socket.IO |
| **TLS/HTTPS** | All production traffic over HTTPS (Cloudflare terminates TLS) |
| **CORS** | Cross-Origin Resource Sharing headers on all responses |
| **Rate Limiting** | Token bucket algorithm at edge and application layer |
| **Content Negotiation** | Accept header checking for JSON vs HTML responses |
| **Chunked Transfer** | File chunking for WebSocket P2P transfer |
| **Presigned URLs** | Time-limited authenticated URLs for direct S3 downloads |

### Distributed Systems Concepts Demonstrated

| Concept | Where Implemented |
|---|---|
| **Replication** | 3-tier storage (R2 → B2 → MinIO), async background threads |
| **Consistency** | Strong consistency on R2 write, eventual on B2/MinIO |
| **Fault Tolerance** | Circuit breaker, multi-backend failover, cache fallback |
| **CAP Theorem** | CP system — consistency + partition tolerance prioritized |
| **Content-Addressable Storage** | SHA-256 keys, global deduplication |
| **CRDT** | GCounter, LWW-Register, OR-Set for conflict-free state |
| **Consistent Hashing** | 150 virtual nodes, minimal key redistribution |
| **Bloom Filter** | Probabilistic set membership, O(1) duplicate check |
| **HyperLogLog** | Approximate cardinality, O(1) space |
| **Merkle Tree** | File integrity, O(log N) proof generation |
| **Differential Sync** | Unified diff, version vectors, conflict detection |
| **Predictive Prefetch** | Markov chain access patterns, LRU cache |
| **Circuit Breaker** | CLOSED/OPEN/HALF-OPEN state machine |
| **Sticky Sessions** | JWT hash → consistent backend for stateful connections |
| **TTL-based Expiry** | MongoDB TTL indexes for automatic data lifecycle |

### Cloud Computing Concepts Demonstrated

| Concept | Where Implemented |
|---|---|
| **Serverless** | Cloudflare Worker (V8 isolate, no server management) |
| **Object Storage** | Cloudflare R2, Backblaze B2, MinIO (S3-compatible API) |
| **Managed Database** | MongoDB Atlas (fully managed NoSQL) |
| **Managed Cache** | Upstash Redis (serverless Redis REST API) |
| **Container Deployment** | Docker + docker-compose for MinIO, Dockerfile for HuggingFace |
| **Infrastructure as Code** | render.yaml, wrangler.toml, docker-compose.yml |
| **Multi-Cloud** | Cloudflare + Backblaze + MongoDB Atlas + Upstash + Render + HuggingFace |
| **CDN** | Cloudflare global network (310 PoPs) |
| **Auto-scaling Signals** | CPU/memory monitoring, load_score for weight adjustment |
| **Health Checks** | /health endpoint, /api/scaling/health, active probing |
| **Observability** | Structured logging, p50/p95/p99 metrics, CF Analytics Engine |
| **Zero-downtime Deploy** | Multiple backends, CF Worker routes around deploying instance |
| **Edge Computing** | Rate limiting, bot blocking, CORS at edge (before backend) |

---

## 📝 License

MIT License — See LICENSE file for details.

---

## 👥 Contributors

Built by students at **Vasavi College of Engineering** for the Computer Networks course (Semester 5, 2024-25).

---

## 🆘 Troubleshooting

### Common Issues

**MongoDB connection fails on startup:**
```bash
# Check MONGO_URI is set correctly in .env
# Ensure IP whitelist in Atlas includes 0.0.0.0/0 for cloud deployments
```

**R2 upload fails:**
```bash
# Verify R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in .env
# Ensure bucket exists in Cloudflare dashboard (cannot be auto-created via API)
# Check bucket name matches R2_BUCKET_FILES
```

**WebSocket connections fail:**
```bash
# Ensure Flask-Compress excludes /socket.io (already configured in app.py)
# Check CORS allows your frontend origin
# Verify eventlet is installed: pip show eventlet
```

**TCP receiver not starting:**
```bash
# TCP receiver is disabled on Render (RENDER env var set)
# For local: ensure port 5555 is not in use
# Check firewall allows TCP on port 5555 for LAN transfers
```

**MinIO not available:**
```bash
docker-compose up -d minio createbuckets
docker ps  # verify flowbridge-minio is running
# Check http://localhost:9001 for MinIO console
```

**Upstash Redis timeout:**
```bash
# Timeout is set to 8 seconds (increased from 3s)
# If still failing, check UPSTASH_REDIS_REST_URL and token
# App falls back to InMemory cache automatically
```

**CF Worker KV namespace not found:**
```bash
wrangler kv:namespace list
# Copy the correct id into wrangler.toml
wrangler deploy
```

---

*FlowBridge v3.0.0 — Built with ❤️ for Computer Networks Course and Distributed Systems and Cloud Computing, Vasavi College of Engineering*

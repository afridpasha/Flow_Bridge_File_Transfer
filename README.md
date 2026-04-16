---
title: FlowBridge File Transfer
emoji: 🌉
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🌉 FlowBridge — Hybrid File Transfer System

A distributed file transfer platform that supports HTTP, TCP, WebSocket, and WebRTC protocols, allowing users to upload, download, and share files securely with JWT + 2FA authentication, OTP-protected share links, real-time collaborative code editing (CodeShare), and a 3-tier cloud storage backend (Cloudflare R2, Backblaze B2, MinIO).

## Features

- **Multi-Protocol Transfer**: HTTP/HTTPS, TCP Socket, WebSocket P2P, WebRTC DataChannel
- **Secure Sharing**: OTP-protected share links with expiry, password, download limits, QR codes
- **CodeShare**: Real-time collaborative code editor with live cursor tracking
- **Authentication**: JWT + bcrypt + TOTP 2FA (Google Authenticator compatible)
- **Advanced CS Concepts**: Bloom Filter, HyperLogLog, Merkle Tree, CRDT, Consistent Hashing

## Tech Stack

`Python 3.11` · `Flask 3.0` · `Socket.IO` · `MongoDB Atlas` · `Redis` · `Cloudflare Worker` · `Docker`

## Environment Variables Required

Set these in Space Settings → Variables:

```
MONGO_URI=mongodb+srv://...
SECRET_KEY=<64-char-hex>
JWT_SECRET_KEY=<64-char-hex>
R2_ACCOUNT_ID=<cloudflare-account-id>
R2_ACCESS_KEY_ID=<r2-access-key>
R2_SECRET_ACCESS_KEY=<r2-secret-key>
UPSTASH_REDIS_REST_URL=https://...
UPSTASH_REDIS_REST_TOKEN=<token>
INSTANCE_ID=huggingface-1
```

---

Built for Computer Networks Course — Vasavi College of Engineering, Hyderabad

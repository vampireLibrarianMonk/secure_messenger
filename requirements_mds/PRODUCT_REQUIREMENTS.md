# Secure Messenger Requirements (Signal × Slack)

## 1) Product Vision

Build a secure, real-time team messaging platform combining:

- **Signal-style privacy** (strong end-to-end encryption by default)
- **Slack-style collaboration** (workspaces, channels, DMs, groups, file/image sharing)

Primary goal: message and file content should be unreadable to the server and unauthorized parties.

---

## 2) Scope

### In Scope (MVP)

1. User authentication and session management
2. Device registration with client-side key generation
3. Workspaces, channels, direct messages, and group conversations
4. Real-time messaging over WebSockets
5. End-to-end encrypted text messages
6. End-to-end encrypted file/image sharing
7. Client-side message history decryption
8. Security controls:
   - Manual lock now
   - Inactivity auto-lock (user configurable)
   - Memory key wipe on lock/logout

### Out of Scope (initial MVP)

- Full mobile apps
- Enterprise SSO/SCIM
- Federated multi-server messaging
- Formal cryptographic audit (planned before production)

---

## 3) Recommended Technology Stack

### Frontend

- **Vue 3 + Vite + TypeScript**
- State management (Pinia)
- WebCrypto API for browser-side cryptography

### Backend

- **Django** (API/auth/admin)
- **Django Channels** (WebSocket messaging)
- ASGI server (Daphne/Uvicorn)

### Data & Messaging Infrastructure

- **PostgreSQL** for persistent data
- **Redis** for Channels layer and pub/sub fanout

### Background Jobs (Phase 2)

- **Celery** + Redis broker for async tasks:
  - file processing
  - malware scanning hooks
  - cleanup/retention jobs
  - notifications/retries

---

## 4) Security & Cryptography Requirements

## 4.1 Core Cryptographic Principles

1. Encrypt/decrypt only on client devices
2. Server stores ciphertext only for messages/files
3. Use authenticated encryption (AEAD)
4. Rotate session/message keys with ratcheting strategy
5. Ensure forward secrecy and post-compromise recovery strategy

## 4.2 Protocol Direction

- Signal-inspired model:
  - initial key agreement (X3DH-style)
  - per-conversation ratcheting (Double Ratchet-style)
- Message encryption:
  - AES-256-GCM or XChaCha20-Poly1305
- Attachment encryption:
  - unique random file key per attachment
  - encrypted file key sent inside E2EE message envelope

## 4.3 Key Management

- Per-device key pair generated client-side
- Public keys uploaded to server key directory
- Private keys never leave client in plaintext
- Local key protection at rest (browser secure storage strategy + passcode lock)
- Phase 2: optional hardware-backed key support where available

## 4.4 Verification & Trust

- Safety number / key fingerprint display
- Manual verification flow (QR or out-of-band string)
- Key change warnings for contacts/devices

## 4.5 Metadata Minimization

- Store minimal metadata required for routing
- Configurable retention windows
- Avoid logging plaintext payloads
- Restrict debugging logs in production

---

## 5) Functional Requirements

## 5.1 Identity & Access

1. Register/login/logout
2. Session refresh and revocation
3. Multi-device support (basic)
4. Role-based workspace membership (owner/admin/member)

## 5.2 Workspaces & Conversations

1. Create/join workspace
2. Create/list channels
3. Start DMs and group chats
4. Membership add/remove

## 5.3 Messaging

1. Send encrypted message
2. Receive encrypted message in real time
3. Store encrypted envelopes server-side
4. Load history and decrypt client-side
5. Basic message status (sent/delivered/read optional MVP)

## 5.4 File/Image Sharing

1. Encrypt file in browser before upload
2. Upload encrypted blob to backend storage
3. Share encrypted file metadata + wrapped key via message envelope
4. Decrypt and preview/download only on authorized clients

## 5.5 Presence & UX Security

1. User presence indicator (online/away)
2. **Inactivity auto-lock** with user-defined timeout
3. **Lock now** action
4. Key wipe from memory on lock/logout/session invalidation

## 5.6 Panic & Emergency Controls (MVP+ / Phase 2)

1. Panic button:
   - immediate UI lock
   - local cache clear
   - memory key wipe
   - token revocation
2. Optional global logout (all devices)
3. Optional decoy mode (future)

---

## 6) Non-Functional Requirements

## 6.1 Performance

- P95 message delivery latency target: near real-time under normal load
- Efficient websocket fanout for channel/group messaging
- Attachment upload resilience for moderate file sizes

## 6.2 Reliability

- Reconnect + message resync behavior
- Idempotent message handling on retries
- Graceful Redis/backend restart handling

## 6.3 Scalability

- Horizontal ASGI workers
- Redis-backed channel distribution
- Storage abstraction for attachments

## 6.4 Auditability & Compliance Readiness

- Security event logging (auth, key changes, lock events)
- No plaintext content in operational logs
- Defined retention/deletion strategy

---

## 7) Threat Model Baseline

### Protect Against

- Honest-but-curious server operators
- Database/storage compromise revealing ciphertext only
- Network interception (TLS + E2EE)
- Stolen session tokens (mitigated by short TTL, revocation, lock)

### Partially Mitigate

- Device theft (local lock, wipe, re-auth)
- Account takeover attempts (future MFA/passkeys)

### Not Fully Solved by Crypto Alone

- Fully compromised endpoints (malware, keylogger, screen capture)

---

## 8) System Architecture (High-Level)

1. **Vue Client**
   - UI/state
   - WebSocket client
   - WebCrypto key + encryption flows
2. **Django API**
   - auth, workspace/channel/member management
   - key directory endpoints
   - attachment upload endpoints
3. **Channels Consumers**
   - real-time publish/subscribe
   - room membership + event routing
4. **PostgreSQL**
   - users, devices, memberships, encrypted message envelopes metadata
5. **Redis**
   - channel layer pub/sub

---

## 9) Data Model (Initial)

- `User`
- `Device` (public keys, verification state)
- `Workspace`
- `WorkspaceMembership`
- `Channel`
- `Conversation` (DM/group)
- `ConversationMember`
- `MessageEnvelope` (ciphertext, nonce/iv, sender device ref, timestamps)
- `Attachment` (encrypted blob reference, mime, size, hash)
- `SessionEvent` (lock/logout/panic/revocation audit)

---

## 10) Delivery Plan

## Phase 1: MVP Foundation

1. Monorepo scaffold (`backend/`, `frontend/`)
2. Django + Channels + Redis plumbing
3. Vue app with auth and conversation UI skeleton
4. Basic E2EE envelope for text messages
5. Encrypted file upload/download pipeline
6. Inactivity lock + lock now

## Phase 2: Security Hardening

1. Key fingerprint verification UX
2. Panic button + remote revocation flows
3. Metadata minimization improvements
4. Stronger retention + secure deletion behavior
5. Background tasks (Celery) for file/security jobs

## Phase 3: Production Readiness

1. Monitoring, rate limits, abuse controls
2. Backup/restore strategy for encrypted blobs and metadata
3. Load/perf testing
4. Independent security review + crypto review

---

## 11) Acceptance Criteria (MVP)

1. Two users can exchange messages where server stores ciphertext only.
2. Two users can share encrypted image/file and decrypt client-side.
3. WebSocket real-time delivery works for channels and DMs.
4. Lock now + inactivity timeout immediately remove access and wipe in-memory keys.
5. Message history can be loaded and decrypted by authorized recipient devices.

---

## 12) Immediate Build Decision

Approved stack:

- **Frontend:** Vue 3 + TypeScript
- **Backend:** Django + Channels
- **Realtime:** Redis
- **DB:** PostgreSQL
- **E2EE:** Browser WebCrypto, Signal-inspired session model

This document is the baseline requirements spec for implementation.
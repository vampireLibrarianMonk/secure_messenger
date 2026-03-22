# Secure Messenger — End-to-End Encrypted Video Chat Implementation Plan

This document is a **handoff-ready engineering blueprint** for implementing a separate, fully encrypted video chat capability in this repository.

It is written so another LLM/engineer can pick it up and implement directly against the current codebase (`backend/` Django + Channels, `frontend/` Vue + Pinia + WebCrypto).

---

## 1) Objective and Constraints

### Objective
Add a **separate video chat capability** that supports:

- 1:1 encrypted calls first (MVP)
- optional group calls later (via SFU)
- strong participant authentication and key continuity checks

### Hard Security Requirements

1. Server must not decrypt media payloads.
2. Only authorized conversation members can join calls.
3. App-layer key material must be generated and consumed client-side.
4. Key lifecycle must support rotation and membership-change handling.
5. No plaintext media/key material in server logs.

### Scope Boundaries

- Keep existing secure messaging capability intact.
- Implement video as a **new module**; do not overload chat message pipeline.
- Preserve current auth stack (JWT + device model) and Channels infrastructure.

---

## 2) Current Repo Baseline (What Already Exists)

### Backend (already present)

- Django settings + DRF + Channels + JWT
- `messenger` app with:
  - user/device/workspace/conversation models
  - websocket chat consumer (`backend/messenger/consumers.py`)
  - routing (`backend/messenger/routing.py`)
  - REST endpoints via viewsets (`backend/messenger/views.py`)

### Frontend (already present)

- Vue 3 + Pinia + TypeScript
- API wrapper (`frontend/src/lib/api.ts`)
- Crypto helper (`frontend/src/lib/crypto.ts`)
- Stores for auth/security/chat
- Chat UI (`frontend/src/App.vue`)

### Architectural fit

Use existing auth + websocket infra for signaling, then add dedicated `video` components.

---

## 3) Target Architecture (Video)

### Components

1. **Video Signaling Channel (backend websocket)**
   - relays SDP/ICE/rekey/control events
   - enforces membership/authz

2. **WebRTC Media Plane (frontend)**
   - `RTCPeerConnection`
   - `getUserMedia`
   - STUN/TURN candidate negotiation

3. **App-layer E2EE Frame Crypto (frontend)**
   - Insertable Streams/SFrame-like frame encryption
   - keys derived from call session secret

4. **Key Directory + Verification (backend+frontend)**
   - uses `Device` keys + fingerprints
   - trust status and key change warnings

5. **Optional Group SFU (later phase)**
   - forwards encrypted frames only
   - no server decryption capability

---

## 4) Crypto Protocol Plan

## 4.1 Identity and Device Keys

- Continue per-device long-term identity keys.
- Prefer X25519 for key agreement where supported.
- Maintain fingerprint display + manual verification UX.

## 4.2 1:1 Call Key Agreement

Use a call-specific X3DH-like handshake:

1. Caller fetches recipient device bundle.
2. Caller generates ephemeral keypair and derives shared secret.
3. Caller sends encrypted call-init payload via signaling.
4. Recipient derives same secret using private prekey material.
5. Both derive call keys using HKDF:
   - master secret
   - send key / recv key
   - rekey seed

## 4.3 Media Encryption

- Keep DTLS-SRTP (WebRTC default) enabled.
- Add app-layer frame encryption (Insertable Streams):
  - encrypt encoded frames before outbound transport
  - decrypt on inbound frame pipeline

## 4.4 Rekey Strategy

Rekey triggers:

- participant join/leave
- timer (e.g., every 5–10 min)
- suspicious identity/key-change events

Rekey process must avoid server plaintext key exposure.

---

## 5) Backend Implementation Blueprint

## 5.1 New Django app (recommended)

Create `backend/video/` app (or `messenger/video/` submodule if preferred).

### New models

1. `VideoCallSession`
   - `id`
   - `conversation` (FK)
   - `created_by` (FK user)
   - `status` (`ringing`, `active`, `ended`, `failed`)
   - `created_at`, `started_at`, `ended_at`

2. `VideoCallParticipant`
   - `session` FK
   - `user` FK
   - `device` FK
   - `state` (`invited`, `joined`, `left`, `declined`)
   - timestamps

3. `VideoSignalEvent` (optional persistence, short TTL)
   - `session` FK
   - `sender_device` FK
   - `event_type` (`offer`, `answer`, `ice`, `rekey`, `hangup`)
   - `payload_ciphertext` (text/json blob)
   - `created_at`

4. `VideoAuditEvent`
   - `session` FK
   - `event_type`
   - `metadata` JSON
   - `created_at`

## 5.2 REST endpoints

Add routes under `/api/video/`:

- `POST /sessions/` create call session (authorized conversation member only)
- `POST /sessions/{id}/join`
- `POST /sessions/{id}/leave`
- `POST /sessions/{id}/end`
- `GET /sessions/{id}`
- `GET /sessions/{id}/participants`

### AuthZ rules

- user must be conversation member
- device must belong to user
- ended sessions reject join/signaling

## 5.3 Channels signaling consumer

Add `VideoSignalingConsumer`:

- route: `/ws/video/sessions/{session_id}/?token=...`
- validate JWT via existing middleware approach (`ws_auth.py` style)
- validate membership
- join group: `video_session_{id}`
- relay event envelope fields:
  - `type`
  - `sender_device_id`
  - `recipient_device_id` (optional)
  - `ciphertext_payload`
  - `nonce`
  - `timestamp`

### Event types to support

- `video.offer`
- `video.answer`
- `video.ice`
- `video.rekey`
- `video.hangup`
- `video.participant_state`

## 5.4 Files to create/update (backend)

- `backend/video/apps.py`
- `backend/video/models.py`
- `backend/video/serializers.py`
- `backend/video/views.py`
- `backend/video/urls.py`
- `backend/video/consumers.py`
- `backend/video/routing.py`
- `backend/video/migrations/*`
- update `backend/config/settings.py` (`INSTALLED_APPS`)
- update `backend/config/urls.py` (include video urls)
- update `backend/config/asgi.py` (merge routing)

---

## 6) Frontend Implementation Blueprint

## 6.1 New modules

Create:

- `frontend/src/video/types.ts`
- `frontend/src/video/signaling.ts`
- `frontend/src/video/webrtc.ts`
- `frontend/src/video/e2ee.ts`
- `frontend/src/stores/video.ts`
- `frontend/src/components/VideoCallPanel.vue`
- `frontend/src/components/IncomingCallModal.vue`

## 6.2 Store responsibilities (`video.ts`)

- call lifecycle state machine:
  - `idle` → `ringing` → `connecting` → `active` → `ended`
- track current session + participants
- create/join/leave/end session via REST
- establish signaling websocket
- pass SDP/ICE through signaling
- trigger rekey events

## 6.3 WebRTC engine (`webrtc.ts`)

- initialize local media tracks
- create `RTCPeerConnection` with ICE servers
- handle offer/answer setLocal/RemoteDescription
- handle ICE candidate generation and intake
- attach tracks to UI elements

## 6.4 E2EE frame pipeline (`e2ee.ts`)

- detect Insertable Streams support
- if strict-mode and unsupported: block call with clear UI error
- apply encrypt transform on outgoing encoded frames
- apply decrypt transform on incoming encoded frames
- key import/rotation API:
  - `setEpochKey(epoch, keyMaterial)`
  - `rotateKey(...)`

## 6.5 UI additions

In `App.vue`/chat header:

- “Start Video Call” action for DM/group (DM first)
- in-call panel with:
  - local/remote video
  - mute/cam toggles
  - end call
  - safety code + verification state
  - secure status badge (`E2EE Verified` / `E2EE Fallback`)

---

## 7) TURN/STUN + Deployment Plan

## 7.1 TURN server

Deploy coturn with:

- TLS enabled
- auth secret
- realm configured
- relay restrictions (no open relay)

Expose ICE config to frontend via secure endpoint:

- `GET /api/video/ice-config`
- returns temporary TURN credentials (time-limited)

## 7.2 Group calls (later)

Integrate SFU (LiveKit/mediasoup/Janus):

- SFU forwards encrypted streams
- implement sender keys + rekey on membership changes

---

## 8) Security and Compliance Controls

1. No plaintext signaling secrets in logs.
2. Replay protection for signaling events:
   - nonce + timestamp + short window
3. Rate limits:
   - call creation
   - signaling messages/sec
4. Call authz validation on every signaling message.
5. Key wipe on:
   - lock
   - logout
   - call end
6. Mandatory key-change warnings for device identity changes.

---

## 9) Detailed Task Breakdown (Implementation Order)

## Phase 1 — 1:1 Call Foundation (no frame E2EE yet)

1. Create backend video app + models + migrations.
2. Add REST session lifecycle endpoints.
3. Add signaling consumer + websocket routing.
4. Add frontend video store + basic call UI.
5. Implement WebRTC offer/answer/ICE for 1:1.
6. Validate call establishment across two browsers with TURN fallback.

## Phase 2 — App-layer Media E2EE

1. Add call key agreement scaffolding (using device keys).
2. Implement `e2ee.ts` frame encrypt/decrypt transforms.
3. Add strict-mode feature flag:
   - fail call if insertable streams unavailable.
4. Add rekey protocol messages.
5. Add safety code UI + verification persistence.

## Phase 3 — Hardening

1. Key rotation periodic timer + on membership changes.
2. Robust reconnect + ICE restart logic.
3. Abuse/rate limiting + audit events.
4. Security tests + protocol review.

## Phase 4 — Group Calls (Optional)

1. SFU selection + integration.
2. Sender key model.
3. Rekey on join/leave.
4. Load/performance testing.

---

## 10) Acceptance Criteria

## 10.1 1:1 MVP Secure Call

- Two authorized users can establish video call.
- Media works with TURN fallback when direct P2P fails.
- Signaling uses authenticated websocket.
- Participant can end call cleanly; state updates on both ends.

## 10.2 E2EE Criteria

- App-layer frame encryption active when supported.
- Server cannot decode media payloads.
- Key rotation events applied without call teardown.
- Key-change warnings shown when device identity changes.

## 10.3 Pre-Prototype Deployment Video Stream Connectivity Gate (Required)

Before any prototype deployment (internal demo, staging preview, or pilot), the team must pass a dedicated **Video Stream Connectivity Test Gate**.

### Gate Objective
Prove that video/audio streams can be established and sustained across expected network/browser conditions, and that failures are observable and diagnosable.

### Mandatory test matrix

1. **Browser matrix (minimum)**
   - Chromium-family latest stable (Chrome/Brave/Edge)
   - Firefox latest stable
   - Safari latest stable (macOS + iOS where supported)

2. **Network matrix**
   - same LAN
   - different home networks (NAT)
   - restrictive corporate-like/firewalled network
   - TURN-forced scenario (disable direct candidate success where possible)

3. **Call mode matrix**
   - 1:1 audio-only
   - 1:1 audio+video
   - mute/unmute + camera toggle mid-call
   - join/leave/rejoin path

### Required automated checks (CI or scripted preflight)

1. signaling channel auth + membership authorization tests
2. SDP/ICE exchange flow tests (offer/answer candidate handling)
3. TURN credential retrieval and expiration handling tests
4. call-state machine tests (`ringing -> connecting -> active -> ended`)
5. rekey trigger tests (at least timer + join/leave events)

### Required manual verification checklist

1. local preview camera/mic works and permission prompts are clear
2. remote stream appears within target setup budget (e.g., <= 5–8s in normal networks)
3. call survives 10-minute run without silent stream failure
4. reconnect behavior after temporary network drop (5–15s outage)
5. clear, user-facing errors when stream establishment fails

### Telemetry/observability required for gate pass

Capture and review for each test run:

- session id
- call setup duration
- ICE connection state transitions
- selected candidate pair type (host/srflx/relay)
- TURN usage indicator
- disconnect/reconnect events
- stream track ended/muted events

### Exit criteria (must all pass)

1. >= 95% success in planned 1:1 connectivity matrix runs
2. TURN fallback confirmed functional in environments where direct P2P fails
3. No unresolved critical defects in stream setup, authz, or call teardown
4. Incident triage artifacts stored (logs + reproduction notes) for any failed runs

### Blocking policy

If this gate is not passed, **prototype deployment is blocked**. Only exception is explicit documented approval with known-risk signoff.

### Implementation note for next LLM

Add a dedicated `docs/video_connectivity_test_gate.md` and a simple `make video-preflight` (or npm script) that executes scripted signaling/call checks and emits a pass/fail summary.

---

## 11) Risks / Non-Guarantees

1. Endpoint compromise (malware/screen capture) remains out-of-scope.
2. “Delete/nuke” cannot erase screenshots/offline copies on other devices.
3. Browser feature fragmentation may require strict-mode UX blocks.

---

## 12) Implementation Notes for Next LLM

1. Reuse existing auth and websocket patterns from `messenger/ws_auth.py` and chat consumer.
2. Keep video signaling payload schema versioned (`schema_version`).
3. Avoid coupling video state into `chat` store; separate `video` store.
4. Put all crypto operations in dedicated modules for testability.
5. Add verbose developer diagnostics behind a feature flag, not in production logs.

---

## 13) Immediate Next PR Recommendation

Create PR: `feat/video-phase1-signaling-and-1to1-calls`

Include:

- backend video app skeleton + migrations
- authenticated signaling consumer
- minimal REST lifecycle endpoints
- frontend store + basic call panel
- 1:1 offer/answer/ICE flow
- no group calls yet

Then PR2 adds app-layer media E2EE and verification UX.

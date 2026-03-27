# 02 — Audit: Video E2EE Verification Test (`documentation/02-video-e2ee-verification-test.md`)

## Audit Verdict
**Verdict: MOSTLY VERIFIED for synthetic classification behavior; app-layer media E2EE is not implemented as true frame-level E2EE in current code.**

## What the Document Claims
The document claims staged flow (`signal -> ice -> relay/direct -> dtls -> e2ee-check`) and allows distinction between `PASS — E2EE VERIFIED` and `PASS — TRANSPORT ONLY`.

## Code Evidence

### A) Scenario definition is accurate
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "video-e2ee"`
  - ordered steps exactly match document sequence.

### B) Synthetic execution and classification exist
- `frontend/src/components/AdminTestLabPanel.vue`
  - scenario run executes ordered steps and logs synthetic flow.
  - diagnostics expose `candidate_pair_type`, `turn_usage`, `transport_vs_app_layer`.
- `frontend/src/lib/resultModel.ts`
  - has explicit result class `PASS — TRANSPORT ONLY` for video when transport is protected but app-layer E2EE not confirmed.
  - in quick intensity, Admin Test Lab evidence logic can leave video at transport-only.

### C) Real video signaling and ICE behavior exist in app
- `frontend/src/stores/video.ts`
  - uses `RTCPeerConnection` + ICE candidates + offer/answer exchange.
  - signaling via websocket (`videoWebsocketUrl(...)`).
  - diagnostics collect RTT, bitrate, packet loss from `getStats()`.
- `backend/messenger/consumers.py` (`VideoSignalingConsumer`)
  - authenticates and enforces membership before join.
  - relays `ready/offer/answer/ice/hangup` events.

## Critical Security Finding
There is **no explicit custom app-layer frame encryption implementation** (e.g., insertable streams / SFrame-like logic) in current frontend video store.

Therefore:
- `PASS — TRANSPORT ONLY` is technically consistent with current concrete implementation.
- `PASS — E2EE VERIFIED` in synthetic mode is a simulated evidence outcome and should not be interpreted as proven app-layer frame cryptography from this codebase alone.

## Standards/Framework Traceability
- ICE terminology aligns with the documented network appendix and WebRTC model.
- WebRTC transport security assumptions (DTLS-SRTP equivalent) are standard stack behavior.
- No code evidence of ISO/NIST certification claims for video subsystem operations.

## Required Codebase Changes to Close Security Gaps
1. **Implement true app-layer media E2EE**
   - Add insertable streams (or equivalent) media frame encryption pipeline in `frontend/src/stores/video.ts`.
   - Introduce per-call/per-participant media key management and rotation instead of transport-only reliance.

2. **Separate transport-only and E2EE states with hard evidence**
   - Update `frontend/src/lib/resultModel.ts` and Admin Test Lab evidence generation so `PASS — E2EE VERIFIED` is only reachable when app-layer encryption instrumentation confirms active state.
   - Keep `PASS — TRANSPORT ONLY` as default for sessions without app-layer media crypto proof.

3. **Strengthen signaling and key exchange controls**
   - Extend `backend/messenger/consumers.py` signaling schema with strict payload validation and anti-replay metadata.
   - Add authenticated key exchange channel/messages for media E2EE key updates bound to participant membership.

4. **Add end-to-end video security tests**
   - Add automated tests for offer/answer/ICE authz failures, relay-only scenarios, and app-layer media encryption toggles.
   - Add diagnostics assertions that verify media E2EE enabled state in addition to WebRTC transport metrics.

## Implementation Progress Update (Current Phase)
### Completed in this phase
- Added **signaling anti-replay sequencing** enforcement in `backend/messenger/consumers.py`:
  - each signaling message now requires `client_id` and monotonic `sequence`.
  - replayed/out-of-order signaling messages are rejected.
- Added **server-issued signaling session binding**:
  - backend now emits a per-connection `session` message with `signaling_session_id`.
  - subsequent signaling messages must include matching `signaling_session_id`.
  - mismatched or missing session ids are rejected (`invalid_signaling_session`).
- Updated frontend signaling client (`frontend/src/stores/video.ts`) to send per-connection monotonic `sequence` on signaling events.
- Updated frontend signaling flow to wait for server session id before transmitting signaling payloads.
- Expanded backend unit tests to verify missing identity/sequence rejection and replayed sequence rejection in signaling validation.
- Added frontend **media-E2EE scaffold state** in `frontend/src/stores/video.ts`:
  - insertable-stream support detection (`mediaE2eeSupported`),
  - scaffold lifecycle flags (`mediaE2eeEnabled`, `mediaE2eeMode`),
  - ephemeral key fingerprint/rotation timestamp for observability.
- Added **runtime insertable-stream pipeline activation state** in `frontend/src/stores/video.ts`:
  - sender/receiver encoded-stream transform hooks are now attached when supported,
  - `mediaE2eeMode` can transition to `runtime_pipeline_active` when runtime pipeline attaches.
  - current transform is pass-through scaffold (no cryptographic frame transform yet).
- Added **experimental runtime frame obfuscation transform** in `frontend/src/stores/video.ts`:
  - insertable-stream hooks now apply reversible XOR-based byte obfuscation for sender/receiver frame data,
  - runtime diagnostics now expose transform class and attachment counts.
  - this is explicitly experimental and **not** standards-based media E2EE cryptography.
- Added diagnostics surfacing in `frontend/src/App.vue` for media-E2EE scaffold telemetry.
- Hardened result classification in `frontend/src/lib/resultModel.ts`:
  - video `PASS — E2EE VERIFIED` now requires `videoAppLayerEvidenceSource === "runtime_verified"`.
  - synthetic/unverified app-layer evidence is forced to `PASS — TRANSPORT ONLY` or `UNKNOWN / UNVERIFIED`.
- Extended evidence-source taxonomy in `frontend/src/lib/resultModel.ts`:
  - added `runtime_experimental_obfuscation` classification.
  - explicitly prevents experimental runtime obfuscation from qualifying as `PASS — E2EE VERIFIED`.
- Updated synthetic evidence generation in `frontend/src/components/AdminTestLabPanel.vue` to explicitly mark video app-layer evidence as `synthetic_or_unverified` until runtime cryptographic evidence exists.
- Updated synthetic evidence generation in `frontend/src/components/AdminTestLabPanel.vue` so exhaustive video runs may emit `runtime_experimental_obfuscation`, still mapped to non-E2EE-verified outcomes.

### Security impact
- Hardens signaling channel against stale/out-of-order replay attempts and malformed unauthenticated signaling envelopes.
- Improves integrity of call control flow even before full app-layer media E2EE is implemented.
- Prevents false-positive `PASS — E2EE VERIFIED` outcomes from synthetic-only video evidence paths.

### Remaining gaps
- Standards-aligned cryptographic media frame transform (insertable streams/SFrame-class/AES-GCM class design) is still not implemented.
- Current XOR obfuscation transform is not a recognized secure E2EE construction and must not be treated as cryptographic proof.
- “PASS — E2EE VERIFIED” remains stronger than what can be cryptographically proven from media path implementation.

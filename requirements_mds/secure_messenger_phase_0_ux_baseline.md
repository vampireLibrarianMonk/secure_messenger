# Secure Messenger — Phase 0 UX Baseline

This document completes **Phase 0** from `requirements_mds/secure_messenger_user_experience_phased_plan.md` by turning the requested enhancements into implementation-ready decisions, constraints, and MVP boundaries.

## Phase 0 Status

**Status:** Complete baseline definition

This phase does **not** implement the end-user features yet. It establishes the concrete product and engineering decisions required before feature coding begins.

---

## 1. Confirmed Feature Set

Phase 0 covers the following planned capabilities:

1. Authenticated user password change
2. Independent notification sounds for:
   - DM message
   - DM document/file event
   - video incoming ring
   - user-left-chat event
3. Video UI visibility toggles for:
   - local pane
   - remote pane
4. Conversation list refactor from button list to selection-box pattern
5. Configurable code-word emergency close capability
6. Secure image/document previewer window for common supported formats

---

## 2. Product Decisions Locked for Implementation

### 2.1 Password Change

**Decision:** password change will be an authenticated account-security feature requiring:

- current password
- new password
- confirmation of new password

**Decision:** backend password validation will continue to use Django password validators already configured in the project.

**Decision:** after a successful password change, the product should treat session continuity conservatively:

- current active session may remain valid for the immediate response cycle
- all other sessions/tokens should be considered candidates for invalidation in implementation review

**Implementation note:** final behavior should prefer explicit reauthentication after password change if straightforward within the current auth model.

---

### 2.2 Notification Sound Taxonomy

**Decision:** the following sound categories are independent and must each have their own stored preference:

- `dm_sound`
- `dm_document_sound`
- `video_ring_sound`
- `chat_leave_sound`

**Decision:** these categories must not implicitly share sound state.

**Decision:** the initial MVP sound source will be **bundled static frontend assets**, not user-uploaded sounds.

**Decision:** settings should support future extension for:

- enabled/disabled
- mute
- volume
- accessibility-oriented sound packs

**Implementation note:** preview playback must be user-initiated to avoid browser autoplay issues.

---

### 2.3 Code-Word Capability

**Decision:** code-word behavior is a **local-device safety feature** and must not rely on server-side speech processing.

**Decision:** initial delivery will use a staged rollout:

1. configuration gate
2. manual fallback / explicit emergency-close action
3. browser speech-recognition integration where supported

**Decision:** the user must complete code-word configuration before they can start or receive a DM **when the feature gate is enabled for the environment**.

**Decision:** the code word should not be stored in plaintext if avoidable. A derived local representation is preferred.

**Decision:** if speech recognition is unavailable, the UI must clearly indicate that fallback behavior is required.

**Decision:** emergency close means, at minimum:

- close the active DM/chat surface
- close related preview windows
- stop local notification playback for the active chat context
- locally terminate or hide visible video UI for that chat
- optionally trigger lock-now in a later hardening step

---

### 2.4 Video Visibility Controls

**Decision:** local and remote video visibility toggles are **presentation-layer controls only** for the initial implementation.

This means:

- hiding local video does not automatically stop camera transmission
- hiding remote video does not terminate the call
- media mute/transmit controls remain separate from visibility controls

**Decision:** the UI must make that distinction clear to avoid user confusion.

---

### 2.5 Conversation Selection UX

**Decision:** the conversation list should move from a stack of action buttons to a **single-selection listbox/selectable-row pattern**.

Required behavior:

- one active conversation at a time
- keyboard navigation support
- obvious selected state
- unread indicators preserved
- conversation actions remain available, but not as the primary selection mechanism

---

### 2.6 Secure Previewer

**Decision:** preview rendering is allowed only after the existing authorized client-side decrypt flow succeeds.

**Decision:** no server-side plaintext preview generation is allowed.

**Decision:** MVP preview support includes:

- PNG
- JPEG/JPG
- PDF

**Decision:** unsupported file types must fall back to download behavior.

**Decision:** preview lifecycle must be integrated with security cleanup events:

- lock
- logout
- emergency close
- conversation teardown where applicable

**Implementation note:** object URLs must be revoked on preview close and on cleanup transitions.

---

## 3. Storage and State Decisions

### 3.1 Backend-stored user preferences

The following should be stored in backend user settings/preferences once implemented:

- notification sound selections
- feature enablement flags that must travel with the account across sessions/devices

### 3.2 Local-only sensitive behavior

The following should remain local-first where possible:

- code-word detection runtime state
- speech-recognition availability state
- preview object URL lifecycle
- temporary emergency-close UI state

### 3.3 Hybrid handling candidates

The following may require a hybrid approach during implementation:

- whether the user has completed code-word setup
- whether DM start/receive gating is enforced account-wide or device-local

**Decision:** Phase 1+ implementation should treat code-word setup completion as an account-visible preference, while keeping the actual recognition/runtime behavior local-device oriented.

---

## 4. MVP Preview File Matrix

| Type | Preview in MVP | Notes |
|---|---|---|
| PNG | Yes | Standard image preview |
| JPEG/JPG | Yes | Standard image preview |
| PDF | Yes | Dedicated PDF preview container/viewer |
| GIF | Later / optional | Only if safe rendering path is approved |
| TXT | Optional later | Lower priority than image/PDF |
| DOC/DOCX | No direct MVP preview | Fallback to download |
| XLS/XLSX | No direct MVP preview | Fallback to download |
| ZIP/other binaries | No | Download only |

---

## 5. Notification Event Mapping Baseline

The following event-to-sound mapping should be used in implementation planning:

| Event | Sound Preference Key | Notes |
|---|---|---|
| New direct message | `dm_sound` | Standard DM message arrival |
| New encrypted document/file in DM | `dm_document_sound` | Must be distinct-capable from DM |
| Incoming video call/ring | `video_ring_sound` | Used for call attention state |
| User leaves chat | `chat_leave_sound` | Membership/participant departure event |

**Decision:** event routing logic should not reuse the generic unread-message ding once this feature ships.

---

## 6. Security Constraints

The following constraints apply to all later implementation phases:

1. No plaintext passwords, code words, or decrypted document contents in logs.
2. No server-side document preview path that bypasses client-side decryption.
3. Code-word monitoring must be opt-in and clearly disclosed.
4. Visibility toggles must not falsely imply microphone/camera/network transmission has stopped.
5. Cleanup behavior must cover lock, logout, and emergency-close transitions.

---

## 7. Accessibility Baseline

The new features must be designed with the following minimum accessibility expectations:

- selection-box conversation UI must support keyboard and focus visibility
- sound selectors must have text labels and preview controls accessible to screen readers
- video visibility toggles must announce on/off state clearly
- emergency-close setup must not rely only on color or audio cues
- preview window must provide a keyboard-accessible close path

---

## 8. Current Codebase Impact Areas Identified

Based on current project structure, these areas are expected to be touched in later phases:

### Backend
- `backend/messenger/views.py`
- `backend/messenger/serializers.py`
- `backend/messenger/models.py`
- `backend/messenger/urls.py`
- `backend/messenger/tests.py`

### Frontend
- `frontend/src/App.vue`
- `frontend/src/stores/auth.ts`
- `frontend/src/stores/chat.ts`
- `frontend/src/stores/video.ts`
- `frontend/src/stores/security.ts`
- `frontend/src/types.ts`

---

## 9. Recommended Next Implementation Order

After this Phase 0 baseline, implementation should proceed in this order:

1. password change
2. notification preference model + routed sound playback
3. conversation selection-box + video visibility toggles
4. code-word gate and fallback path
5. secure previewer
6. hardening and full QA

---

## 10. Definition of Done for Phase 0

Phase 0 is considered complete because:

- requested capabilities have been normalized into concrete feature definitions
- ambiguous UX/security questions have initial implementation decisions
- MVP scope boundaries are documented
- storage, routing, and security expectations are defined
- affected code areas are identified for later execution phases

This document serves as the requirements baseline for subsequent implementation work.
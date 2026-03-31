# Secure Messenger — User Experience Enhancements Phased Plan

This phased plan captures the newly requested user-facing capabilities and organizes them into a practical delivery order for implementation across frontend, backend, security, and QA.

## Requested Capability Summary

The product needs the following additions and adjustments:

1. Allow a user to change their password.
2. Allow a user to choose notification sounds independently for:
   - direct messages
   - direct-message document/file events
   - video stream incoming ring events
3. Add a separate selectable notification sound for when a user leaves the chat.
4. Allow the user to toggle off either the local or remote video stream in the current video UI.
5. Change conversations from button-driven interaction to a selection-box pattern.
6. Add a configurable spoken code word capability that will close the chat.
   - The user must configure this before they can start or receive a DM.
7. Add an image/document previewer window for common file types such as:
   - PNG
   - JPEG
   - PDF
   - similar supported previewable formats

---

## Product Direction and Design Intent

These enhancements should improve privacy control, accessibility, user customization, and safe handling of sensitive conversations without weakening the secure-messaging posture.

Guiding principles:

- preserve secure defaults
- require explicit user consent for sensitive controls
- keep configuration understandable and reversible
- avoid mixing unrelated notification events
- maintain clear separation between transport behavior and user-interface preferences
- ensure new features fit the existing secure DM, document, and video workflows

---

## Implementation Status Snapshot

| Phase | Capability Area | Status |
|---|---|---|
| 0 | Requirements, UX decisions, and security constraints | Planned |
| 1 | Account security: password change | Planned |
| 2 | Notification preferences and independent sound routing | Planned |
| 3 | Conversation list UX and video visibility toggles | Planned |
| 4 | Code-word emergency close capability | Planned |
| 5 | Encrypted image/document previewer window | Planned |
| 6 | Hardening, accessibility, telemetry, and QA sign-off | Planned |

---

## Phase 0 — Requirements Alignment and Architectural Decisions

### Goal
Lock down feature definitions, security boundaries, and UX expectations before implementation begins.

### Scope
- Confirm where user preferences will be stored:
  - backend profile/preferences model
  - encrypted local preference storage where appropriate
- Confirm whether notification sounds are:
  - bundled static assets
  - environment-configurable assets
  - user-uploaded custom sounds
- Confirm supported preview file types for MVP.
- Confirm whether code-word detection is:
  - browser speech recognition based
  - manual typed panic phrase fallback
  - both
- Define what “close the chat” means operationally:
  - hide active DM window
  - stop notification playback
  - end active video UI session locally
  - trigger lock/wipe behavior
  - optionally navigate away from DM view
- Confirm conversation selection-box behavior in desktop and mobile breakpoints.

### Key Decisions Required
- Password change flow should require current password verification.
- Notification sounds must be independently assignable per event class.
- Code-word setup must be completed before DM initiation or DM acceptance.
- Previewer must not bypass existing encryption/decryption constraints.

### Deliverables
- Final UX and security notes for all requested features.
- Agreed event taxonomy for notification sounds.
- Supported file preview matrix.
- Panic/code-word behavior definition.

### Exit Criteria
- No major ambiguity remains around feature behavior or security expectations.

---

## Phase 1 — Password Change Capability

### Goal
Allow authenticated users to securely change their password.

### Scope

#### Backend
- Add password-change endpoint for authenticated users.
- Require:
  - current password
  - new password
  - confirmation of new password
- Enforce password validation policy.
- Invalidate or review session/token behavior after password change.
- Add audit/event logging for password change success/failure without storing secrets.

#### Frontend
- Add account/security settings section for password change.
- Show validation states for:
  - incorrect current password
  - weak password
  - mismatch confirmation
  - successful update
- Provide clear post-change messaging if reauthentication is required.

### Acceptance Criteria
- User can change password only after supplying valid current credentials.
- Weak or mismatched passwords are rejected with clear feedback.
- Password update succeeds without exposing secrets in logs.
- Session handling after password change behaves consistently with security policy.

### Dependencies
- Existing authenticated account settings flow.

---

## Phase 2 — Notification Preferences and Independent Sound Controls

### Goal
Give users precise control over how different secure-communication events sound.

### Scope

#### Notification Event Classes
Create independent sound preferences for at least:

1. DM message notification
2. DM document/file notification
3. Video stream incoming ring notification
4. User-left-chat notification

These must not share a forced common sound unless the user explicitly chooses the same sound for multiple event classes.

#### Backend / Data Model
- Add user notification-preference storage for each event class.
- Support future extensibility for mute, volume, and enable/disable flags.

#### Frontend
- Add notification settings panel with separate selectors for each event class.
- Present a list of available sounds for each selector.
- Add preview/play controls so a user can hear the selected sound before saving.
- Show current assignment clearly.
- Ensure save/cancel/reset-to-default flows are intuitive.

#### Client Behavior
- Route events to the correct sound bucket.
- Ensure DM, DM document, video ring, and user-left-chat events do not overwrite or collide with one another.
- Respect browser permission and autoplay restrictions where relevant.

### Acceptance Criteria
- User can independently select different sounds for all four event classes.
- A DM document event can sound different from a standard DM.
- A video incoming ring can sound different from both DM event types.
- A user-left-chat event can sound different from all other events.
- Sound previews work reliably from settings.

### Implementation Notes
- Consider a normalized structure such as:
  - `dm_sound`
  - `dm_document_sound`
  - `video_ring_sound`
  - `chat_leave_sound`
- Plan for future additions like mute, vibration, priority, or accessibility sound packs.

---

## Phase 3 — Conversation Selection UX and Video Stream Visibility Controls

### Goal
Improve usability in conversation navigation and video layout control.

### Scope

#### A. Conversations as Selection Box
- Replace the current button-oriented conversation interaction with a selection-box pattern.
- Support:
  - selected state
  - keyboard navigation
  - focus visibility
  - single active conversation selection
- Preserve unread indicators and status badges where applicable.

#### B. Video Stream Toggle Controls
- Add controls that allow the user to independently toggle visibility for:
  - local video pane
  - remote video pane
- Clarify that this is a UI visibility control unless intentionally coupled to media transmission behavior.
- If local-video transmission mute is later desired, it should be treated as a separate feature from visual hide/show.

### UX Expectations
- User can hide local self-view if desired.
- User can hide the remote pane locally if desired.
- Toggling one pane must not unintentionally disable the other.
- The active state should be obvious in the interface.

### Acceptance Criteria
- Conversation navigation uses a selection-box style instead of discrete buttons.
- Only one conversation is selected at a time.
- Local video can be hidden without affecting remote visibility.
- Remote video can be hidden without affecting local visibility.
- UI clearly reflects current video-pane state.

### Dependencies
- Existing chat store and video store state management.

---

## Phase 4 — Code-Word Emergency Close Capability

### Goal
Provide a configurable emergency mechanism allowing the user to speak a code word that closes the chat.

### Scope

#### Functional Requirement
- User must configure the code word before they can:
  - start a DM
  - receive/accept a DM

#### Configuration UX
- Add a setup flow in secure preferences or DM onboarding.
- Require confirmation of the configured code word.
- Explain limitations of speech recognition accuracy and environmental noise.
- Provide an explicit enable/disable control.
- Provide a fallback mechanism if microphone or speech recognition is unavailable.

#### Runtime Behavior
- When the configured code word is detected, the application should perform the defined emergency-close action.
- Emergency-close behavior should minimally consider:
  - closing active DM/chat view
  - closing preview windows tied to the chat
  - stopping local notification audio associated with that chat
  - hiding or terminating visible video-call UI state locally
  - optionally invoking lock-now behavior if approved by product/security

#### Security and Abuse Considerations
- Avoid storing the raw code word in plaintext if possible.
- Define whether the feature is local-device only.
- Document false-positive and false-negative behavior.
- Add opt-in consent for microphone monitoring.
- Ensure the feature does not activate automatically without setup.

### Acceptance Criteria
- User cannot start or receive a DM until code-word setup is complete, if this requirement is enabled globally.
- User can configure, update, or disable their code word through settings.
- Code-word detection triggers the defined emergency-close behavior.
- Failure states are communicated clearly when speech services are unavailable.

### Recommended Delivery Strategy
- Phase 4A: configuration gate + typed/manual emergency close fallback
- Phase 4B: speech recognition integration
- Phase 4C: hardened behavior, false-trigger mitigation, and accessibility review

---

## Phase 5 — Secure Image and Document Previewer Window

### Goal
Allow users to preview supported files inside a dedicated preview window while respecting encryption and authorization boundaries.

### Scope

#### Supported MVP Types
- PNG
- JPEG/JPG
- PDF
- other preview-safe formats if validated during implementation

#### UX
- Open preview in a dedicated previewer window or modal.
- Show file metadata such as:
  - filename
  - type
  - size
- Provide actions such as:
  - close preview
  - download
  - open in external viewer where allowed

#### Security / Encryption Requirements
- Preview only after authorized client-side decrypt flow succeeds.
- Do not introduce a plaintext upload or server-side preview path.
- Prevent unauthorized preview access from stale or non-member sessions.
- Ensure preview window cleanup behavior is defined on lock/logout/emergency close.

#### Technical Considerations
- Use blob/object URL lifecycle management carefully.
- Revoke object URLs when preview closes.
- Define PDF rendering approach.
- Handle unsupported files with fallback download messaging.

### Acceptance Criteria
- Supported images preview successfully in a dedicated preview UI.
- Supported PDFs preview successfully in a dedicated preview UI.
- Unsupported types fall back gracefully.
- Preview access respects existing authorization and client-side decryption rules.
- Preview state is cleared appropriately on lock/logout/emergency-close flows.

---

## Phase 6 — Hardening, Accessibility, and Quality Validation

### Goal
Finalize the above features for reliability, privacy, usability, and release readiness.

### Scope

#### Security Hardening
- Verify password-change audit and error handling.
- Verify code-word setup and execution cannot be trivially bypassed.
- Verify preview flows do not leak plaintext through logs, caches, or stale object URLs.

#### Accessibility
- Ensure settings forms are keyboard accessible.
- Ensure selection-box conversations are screen-reader understandable.
- Ensure video visibility toggles announce state clearly.
- Ensure notification sound selectors have accessible labels and preview controls.

#### QA Coverage
- Password change success/failure/regression cases.
- Notification routing matrix for all four event classes.
- Conversation selection behavior across breakpoints.
- Local/remote video visibility permutations.
- Code-word configured/not-configured gating scenarios.
- Previewer coverage for image, PDF, unsupported type, logout, and lock transitions.

### Acceptance Criteria
- All requested features are test-covered and behaviorally consistent.
- No major accessibility blocker remains for the new UI.
- No security regression is introduced by the new settings or preview flows.

---

## Recommended Delivery Order

1. **Phase 0** — finalize decisions and definitions.
2. **Phase 1** — ship password change first because it is isolated and high-value.
3. **Phase 2** — implement notification preference model and sound routing.
4. **Phase 3** — improve conversation selection and video visibility UX.
5. **Phase 4** — deliver code-word capability in gated increments.
6. **Phase 5** — add secure previewer window after decryption/view lifecycle is defined.
7. **Phase 6** — complete hardening and QA sign-off.

---

## Cross-Cutting Engineering Considerations

### Backend
- user settings/preferences model updates
- password-change API and validation
- audit event support

### Frontend
- settings UI expansion
- notification sound asset selection and playback preview
- chat-list interaction refactor
- video UI controls
- preview window/modal experience
- code-word onboarding and runtime state handling

### Security
- no plaintext secrets in logs
- protected handling of password changes
- safe local behavior for code-word monitoring
- secure cleanup for previews and emergency-close actions

### Testing
- unit tests for preference/state logic
- integration tests for password change and preview authorization
- end-to-end tests for notification routing, DM gating, and emergency close behavior

---

## Final Outcome Target

When all phases are complete, the secure messenger should provide:

- secure password self-service updates
- granular and independent notification sound configuration
- better video layout control
- improved conversation selection usability
- an emergency code-word close mechanism with configuration gating
- a secure built-in previewer for common document and image formats

This plan is intended to be implementation-ready and suitable for staged execution by engineering teams or IDE-assisted coding workflows.
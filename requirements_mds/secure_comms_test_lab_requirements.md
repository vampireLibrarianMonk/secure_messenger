# Secure Communications Test Lab — Full Requirements Specification

## 1) Purpose

Build a **separate testing solution** for the secure messenger application that allows the team to validate secure direct messaging, video, encrypted document handling, and later controlled group-security behavior **without turning the product into a surveillance interface**.

This testing solution must be isolated from ordinary user flows and must rely on **synthetic/faux users, faux sessions, faux conversations, and faux test data** for the primary UI experience.

The objective is to provide a **safe, developer-friendly, QA-friendly, and LLM-handoff-friendly UI extension** that can be used to:

- simulate secure communication flows
- exercise testing workflows end-to-end
- visualize step-by-step connection/test progression
- expose diagnostics that ordinary users should not see
- generate operator-readable logs and results
- preserve the spirit of secure anonymous communication
- confirm whether the tested path reached true end-to-end encryption, transport-only protection, or unknown/unverified status

This direction aligns with the product requirement that message and file content remain unreadable to the server and unauthorized parties, the video requirement that server operators must not decrypt media payloads, and the admin-analysis requirement that operators validate security **without reading plaintext content or media**. fileciteturn6file3L1-L18 fileciteturn6file7L1-L18 fileciteturn6file13L1-L18

---

## 2) Product Direction

This solution is **not** the normal admin panel and **not** the normal user application.

It is a **separate testing solution** composed of:

1. a **Test Lab** page for selecting and launching tests
2. a **Connection Console** page for showing animated test progression and bash-style logs
3. a **specialized test-user experience** with diagnostics unavailable to ordinary users
4. an **admin review capability** for reviewing test outcomes and artifacts without exposing real user content

This solution must not become a UI for observing real anonymous users, real endpoint movement, or real communications content.

---

## 3) Core Design Principles

### 3.1 Privacy-preserving intent
The testing solution must preserve the spirit of secure anonymous communication.

Therefore:

- no real-user monitoring dashboard
- no live globe of real users
- no real content observation
- no plaintext message/media/file previews in the testing UI
- no production-facing surveillance features disguised as diagnostics

### 3.2 Synthetic-first operation
The primary UI must use **faux-generated actors and faux-generated test events**.

Examples:

- `test_user_alpha`
- `test_user_bravo`
- `test_user_charlie`
- `faux_node_alpha`
- `sim_room_0007`
- `sim_run_0042`
- `sim_doc_0021`

### 3.3 Separate role experiences
The product must distinguish among:

- **ordinary users**
- **test users**
- **admins/security reviewers**

Ordinary users must not see deep diagnostics. Test users may see scoped test diagnostics. Admins may review evidence and outcomes, but must not read real protected content.

### 3.4 Explicit uncertainty
The system must use explicit result states such as:

- `PASS`
- `FAIL`
- `UNKNOWN / UNVERIFIED`
- `TRANSPORT ONLY`
- `E2EE VERIFIED`

The system must never imply security when evidence is incomplete. This follows the admin-analysis rule that transport encryption, application-layer encryption, end-to-end encryption, and encryption-at-rest must be distinguished, and that missing proof must be shown as `unknown/unverified`. fileciteturn6file9L1-L13

### 3.5 Evidence over labels
The system must not assume something is secure merely because it uses HTTPS, WebSockets over TLS, WebRTC, JWT, or other security-sounding technologies. Tests must prove the protection class reached by the scenario. fileciteturn6file10L1-L18

---

## 4) Personas

### 4.1 Ordinary user
Ordinary users use the normal secure messenger UI.

They must not have access to:

- verbose diagnostics
- test harness controls
- debug traces
- expanded transport path details
- special testing menus

### 4.2 Test user
Test users exist only for controlled testing/lab environments.

They may access a **specialized testing menu** that allows them to:

- run scripted or simulated tests
- view synthetic connection states
- inspect scoped diagnostics for their own test scenario
- exercise DM, video, and document handling workflows
- participate in controlled optional group-security tests when enabled

### 4.3 Admin/security reviewer
Admins/security reviewers may:

- trigger or review test runs
- inspect outcomes, activity streams, and artifacts
- review evidence and logs produced by the test system
- review failures and unknown/unverified states
- govern creation and activation of test accounts

Admins must not be able to read decrypted message content, view media payloads, or use the testing solution as a real-user observation tool. This preserves the no-content-read boundary from the admin-analysis requirements. fileciteturn6file13L1-L18

---

## 5) Account Governance Requirements

### 5.1 Goal
The application must strictly govern the exact number of privileged lab accounts so the testing surface stays small, auditable, and intentional.

### 5.2 Admin count policy
There must be **no more than one active admin account** for this separate testing solution.

Rules:

- maximum active admins: `1`
- bootstrap must be idempotent
- duplicate admin creation is prohibited
- restarting the stack must not create an additional admin
- admin bootstrap credentials must not be hardcoded
- bootstrap activity must be audited without exposing plaintext secrets

This follows the secure bootstrap requirement that first-admin creation be deterministic and that restarts must not create duplicate admins. fileciteturn6file9L19-L44 fileciteturn6file6L1-L18

### 5.3 Test-user count policy
There must be **no more than two active test-user accounts by default**.

Rules:

- maximum active test users: `2`
- default active accounts should be sufficient for DM, encrypted file, and 1:1 video testing
- no self-registration for test users
- test accounts must be created only through controlled admin or seed logic
- inactive historical test accounts may exist only in archived/non-login form for audit continuity

This matches the MVP shape: two users can exchange ciphertext-only messages, two users can share encrypted files, and the video MVP is explicitly 1:1 first. fileciteturn6file0L1-L18 fileciteturn6file1L1-L18

### 5.4 Optional third test user policy
A **third active test user is not part of the default lab**.

A third test user may be enabled **only temporarily** when a specific group-behavior scenario is being tested and the dedicated group-testing feature flag is enabled.

Suggested feature flag:

- `group_testing_enabled`

Suggested rule:

- default active test users: `2`
- temporary max active test users when group testing is enabled: `3`
- after group testing is complete, the third test user should be deactivated or returned to archived status

### 5.5 Why a third user may be needed
Two users are enough for the current MVP security flows:

- direct message encryption/decryption
- encrypted file transfer
- 1:1 video signaling, TURN fallback, and media protection validation

However, a third user becomes useful when testing **group behavior** that cannot be meaningfully validated with only two participants.

### 5.6 Third-user group-behavior rationale
The third test user exists to validate **membership-change security behavior** rather than to simply add another person to a chat.

Use cases include:

- a third participant joining an existing group conversation
- rekey behavior when membership changes
- verifying that removed members lose access to future ciphertext
- validating sender-key or group-call distribution behavior
- confirming that join/leave events produce the right security warnings and state updates
- validating authorization boundaries when a participant is added or removed

This is especially relevant because your product requirements include group conversations and membership add/remove, while the video plan says optional group calls later should use sender keys and rekey on membership changes. fileciteturn6file8L19-L37 fileciteturn6file2L1-L24

### 5.7 Best-practice wording for the third user
The third test user should be described in the UI and requirements as:

> **Optional Group Behavior Participant** — a temporary third synthetic participant used only to validate secure membership-change behavior, group rekeying, join/leave handling, and post-removal access boundaries in controlled lab scenarios.

This wording is preferable to anything that sounds like routine expansion of the permanent test pool.

### 5.8 Best-practice group-testing scenarios
When the third test user is enabled, the lab should support at least these scenarios:

1. **Join and Rekey Test**
   - Users A and B already have a secure group or group-call context.
   - User C joins.
   - The system confirms rekey or membership-update behavior occurred.
   - The resulting state is checked for proper access continuity and warning behavior.

2. **Remove and Access Loss Test**
   - Users A, B, and C are in a secure group context.
   - User C is removed.
   - The system confirms future protected content is no longer accessible to C.
   - The system verifies that stale membership does not retain future decryption ability.

3. **Group Call Membership Change Test**
   - A and B are in an active call or group-call simulation.
   - C joins or leaves.
   - The system confirms join/leave signaling, rekey triggers, and resulting security state.

4. **Sender-Key Distribution Test**
   - Validate that group message or group-call sender-key distribution logic behaves correctly when the participant set changes.

5. **Post-Removal Residual Access Test**
   - Confirm a removed participant cannot retrieve or decrypt newly protected content after removal.

### 5.9 Group-testing guardrails
Group testing must still preserve the testing-lab spirit:

- use synthetic participants only
- no real-user observation
- no plaintext content exposure
- no hidden expansion from 2 users to 3 users outside flagged scenarios
- all third-user activation/deactivation actions should be audited

---

## 6) High-Level UI Structure

The new testing solution must contain exactly two primary UI destinations:

1. **Test Lab**
2. **Connection Console**

No globe, no real-time real-user topology view, and no broad surveillance-style operations dashboard.

---

## 7) Page A — Test Lab

### 7.1 Purpose
The Test Lab is the launch page where the operator chooses the synthetic scenario, selects the test type, configures test conditions, and starts the run.

### 7.2 Layout
The Test Lab should use a three-zone layout:

#### Left zone
Scenario and environment selection controls.

#### Center zone
Large animated icon tiles representing supported communication/security test categories.

#### Right zone
Run configuration, toggles, and launch controls.

### 7.3 Required controls

#### Primary dropdown — Test Scenario
Minimum options:

- DM basic encrypted exchange
- DM reconnect and retry
- Video signaling and relay test
- Video E2EE verification test
- Document upload/download encrypted flow
- Full communication suite
- Group join and rekey test *(only visible when `group_testing_enabled=true`)*
- Group remove and access-loss test *(only visible when `group_testing_enabled=true`)*
- Group call membership-change test *(only visible when `group_testing_enabled=true`)*

#### Secondary dropdown — Synthetic Environment
Minimum options:

- local sandbox
- staging simulator
- degraded relay environment
- packet-loss simulation
- reconnect simulation
- unknown/unverified branch

#### Third dropdown — Test Intensity
Minimum options:

- quick
- standard
- exhaustive

#### Optional toggles
Minimum toggles:

- show animation details
- verbose bash log
- inject warning conditions
- include faux relay nodes
- include unknown/unverified branch
- auto-scroll logs

#### Launch action
Primary action button:

- `Run Simulated Test`

### 7.4 Test type icon tiles
The UI must include animated icon tiles for at least:

- **Direct Message Test**
- **Video Session Test**
- **Document Transfer Test**
- **Full Communication Suite**
- **Group Behavior Test** *(gated behind `group_testing_enabled`)*

Each tile should:

- have a visually distinct icon
- support hover and selected state
- support subtle motion/animation
- show a plain-English description
- be compatible with keyboard selection

### 7.5 Plain-English requirement
The Test Lab must use human-readable test labels and descriptions rather than raw backend check names.

Each test option must clearly state what it validates.

### 7.6 Account-governance indicators
The Test Lab should visibly show lab account limits/status:

- Active admin accounts: `1 / 1`
- Active test users: `2 / 2`
- Group testing participant slot: `disabled` or `1 / 1 temporary`

This keeps operators aware of the intentionally small privileged-account surface.

---

## 8) Page B — Connection Console

### 8.1 Purpose
The Connection Console is a separate page that displays the test execution in a dial-up / handshake / terminal-inspired style.

The page exists to show:

- which faux endpoints are participating
- which test is running
- the ordered steps of the test
- the bash-style execution log
- the final result

### 8.2 Visual concept
The Connection Console should feel like a hybrid of:

- old dial-up / connection progress animation
- packet/handshake monitor
- modern terminal/log tail
- secure systems lab console

It must not look like a real-user monitoring dashboard.

### 8.3 Required sections

#### Header strip
Must show:

- test name
- source faux node
- target faux node or group participant set
- environment
- run id
- status

Example:

`Video E2EE Verification | faux_node_alpha -> faux_node_bravo | sim-run-0042 | Running`

Group example:

`Group Join and Rekey Test | faux_node_alpha + faux_node_bravo + faux_node_charlie | sim-run-0091 | Running`

#### Handshake animation strip
A left-to-right animated progression band showing the current step sequence.

Examples:

##### DM
`[source] -> [session] -> [encrypt] -> [route] -> [fetch] -> [decrypt] -> [target]`

##### Video
`[source] -> [signal] -> [ice] -> [relay/direct] -> [dtls] -> [e2ee-check] -> [target]`

##### Document
`[source] -> [file-key] -> [encrypt-blob] -> [upload] -> [wrap-key] -> [fetch] -> [decrypt] -> [target]`

##### Group behavior
`[group-init] -> [membership-change] -> [rekey] -> [redistribute] -> [access-check] -> [result]`

#### Ordered event feed
A structured, timestamped list of test events in execution order.

#### Bash-style log panel
A terminal-like panel with live textual output.

#### Result summary bar
A compact final summary with duration, key outcome, and notable warnings/errors.

### 8.4 Panel states
The Connection Console must support:

- idle state
- running state
- completed state
- failed state
- unknown/unverified state

### 8.5 Animation rules
Steps in the handshake strip must visually support:

- inactive
- active
- completed
- warning
- failed
- unknown/unverified

### 8.6 Log style
The bash-style log must:

- use a monospaced presentation
- stream line-by-line updates while the test runs
- include readable step/status markers
- avoid sensitive plaintext or key material
- remain intelligible to non-developer operators

---

## 9) Synthetic Data Model

The UI must primarily operate on **synthetic fixtures/generated test objects**.

### 9.1 Synthetic user examples
- `test_user_alpha`
- `test_user_bravo`
- `test_user_charlie`

### 9.2 Synthetic node examples
- `faux_node_alpha`
- `faux_node_bravo`
- `faux_node_charlie`
- `faux_relay_01`

### 9.3 Synthetic run examples
- `sim_run_0001`
- `sim_run_0042`

### 9.4 Synthetic room/session examples
- `sim_room_0007`
- `sim_session_0012`

### 9.5 Synthetic document examples
- `sim_doc_0021`

### 9.6 Synthetic event examples
- `TEST_ORDERED`
- `SESSION_CONTEXT_READY`
- `DM_ENCRYPT_BEGIN`
- `DM_CIPHERTEXT_CONFIRMED`
- `VIDEO_SIGNAL_BEGIN`
- `ICE_EXCHANGE_STARTED`
- `TURN_SELECTED`
- `DTLS_ESTABLISHED`
- `APP_E2EE_CHECK_BEGIN`
- `APP_E2EE_CONFIRMED`
- `DOC_KEY_GENERATED`
- `DOC_BLOB_ENCRYPTED`
- `DOC_UPLOAD_COMPLETE`
- `RECIPIENT_DECRYPT_CONFIRMED`
- `GROUP_MEMBER_JOIN`
- `GROUP_MEMBER_REMOVED`
- `GROUP_REKEY_BEGIN`
- `GROUP_REKEY_CONFIRMED`
- `POST_REMOVAL_ACCESS_CHECK`
- `TEST_COMPLETE`
- `TEST_FAILED`
- `TEST_UNKNOWN`

---

## 10) Test User Menu Requirements

### 10.1 Purpose
The test-user experience must include a **specialized testing menu** with diagnostics that ordinary users do not have.

### 10.2 Scope
This menu is permitted only for:

- dedicated test users
- sandbox/lab environments
- optionally admins in testing mode

### 10.3 Required sections
Minimum sections:

- Run Scenario
- Connection Console
- DM Test Actions
- Video Test Actions
- Document Test Actions
- Diagnostics
- Export Test Artifact

Add when `group_testing_enabled=true`:

- Group Behavior Test Actions

### 10.4 DM diagnostics
Minimum diagnostics:

- session state
- key/fingerprint state
- envelope created state
- ciphertext-before-send confirmation
- delivery state
- decrypt success state
- key-change warning state
- lock/wipe event state

These diagnostics should reflect the product rule that encryption/decryption happens on client devices and the server stores ciphertext only for messages/files. fileciteturn6file8L1-L18

### 10.5 Video diagnostics
Minimum diagnostics:

- signaling connected
- session id
- ICE state transitions
- candidate pair type
- TURN usage
- call setup duration
- reconnect/disconnect events
- strict-mode support state
- transport protected vs app-layer E2EE verified

These align with the video connectivity gate and E2EE criteria. fileciteturn6file11L1-L24 fileciteturn6file12L1-L24

### 10.6 Document diagnostics
Minimum diagnostics:

- file selected
- file key generated
- encrypted blob produced
- upload complete
- wrapped key sent
- recipient fetch complete
- decrypt success
- hash matched
- no plaintext upload path detected

These match the encrypted attachment design in the product requirements. fileciteturn6file4L1-L18

### 10.7 Group diagnostics
When the optional third test user is enabled, minimum group diagnostics should include:

- current participant set
- membership-change event detected
- rekey trigger started
- rekey completion confirmed
- sender-key or group-key distribution state
- removed-member future-access denial check
- post-join warning or verification state
- authorization state for all participants

### 10.8 Things test users must not see
Even in test mode, do not expose:

- raw private keys
- unrestricted internal traces
- real user communications
- hidden server-side decrypt tools
- broad production presence visibility

---

## 11) Admin Review Requirements

### 11.1 Purpose
The admin/security reviewer role should review test artifacts and outcomes, not use the UI to observe real users.

### 11.2 Admin capabilities
Admins may:

- trigger simulated runs
- review status and results
- inspect ordered event feeds
- inspect bash-style logs
- review synthetic diagnostics and artifacts
- compare pass/fail/unknown states
- activate or deactivate the temporary third test user for approved group tests
- enforce the max-account policy

### 11.3 Admin restrictions
Admins must not be able to:

- read real decrypted message bodies
- view real decrypted attachments
- inspect media content
- use test tooling to track real user communications

---

## 12) Supported Test Domains

### 12.1 Direct Messaging
The test system must support synthetic validation of:

- client-side encryption before send
- ciphertext-only routing expectation
- recipient retrieval simulation
- recipient local decrypt confirmation
- reconnect/retry paths
- key-change warning behavior
- lock/logout key wipe interaction

This is grounded in the requirement that two users exchange messages where the server stores ciphertext only and recipients decrypt client-side. fileciteturn6file0L1-L18

### 12.2 Video
The test system must support synthetic validation of:

- signaling startup
- SDP/ICE flow simulation
- direct vs relay path representation
- DTLS transport establishment state
- app-layer E2EE verification state
- reconnect and teardown scenarios
- TURN fallback scenarios
- strict-mode unsupported path handling

This follows the 1:1 video MVP, E2EE criteria, and connectivity gate. fileciteturn6file1L1-L24 fileciteturn6file11L1-L24

### 12.3 Document handling
The test system must support synthetic validation of:

- file key generation
- client-side blob encryption
- upload path simulation
- wrapped key transfer simulation
- recipient fetch/decrypt simulation
- decrypt-only-on-client expectation

### 12.4 Group behavior
When `group_testing_enabled=true`, the system must support synthetic validation of:

- group membership add/remove behavior
- rekey-on-join and rekey-on-leave
- sender-key distribution logic
- post-removal future-access denial
- group authorization integrity after participant change
- group-call membership-change handling for later video phases

This directly follows the product requirement for group conversations and membership add/remove, and the video plan’s later-phase sender keys plus rekey on membership changes. fileciteturn6file8L19-L37 fileciteturn6file2L1-L24

---

## 13) Encryption-Confirmation Requirements

### 13.1 Requirement
Every supported test must explicitly state what level of protection it confirmed.

The output must not simply say “passed.”

### 13.2 Allowed result classifications
Each test must end with one of:

- `PASS — E2EE VERIFIED`
- `PASS — TRANSPORT ONLY`
- `FAIL`
- `UNKNOWN / UNVERIFIED`

### 13.3 DM encryption confirmation
A DM test should only reach `PASS — E2EE VERIFIED` if the test confirms:

- payload encryption occurs client-side before send
- server handles ciphertext only
- recipient-side decrypt occurs client-side
- no required evidence suggests plaintext server exposure

### 13.4 Document encryption confirmation
A document test should only reach `PASS — E2EE VERIFIED` if the test confirms:

- file key is generated client-side
- blob is encrypted client-side before upload
- uploaded blob is encrypted at rest on the server
- wrapped file key is transferred inside the protected envelope
- decrypt occurs only on authorized client devices

### 13.5 Video encryption confirmation
A video test should only reach `PASS — E2EE VERIFIED` if the test confirms:

- authenticated signaling succeeded
- transport security exists
- app-layer frame encryption is active when supported
- server cannot decode media payloads

If only DTLS/WebRTC transport protection is confirmed, the result must be `PASS — TRANSPORT ONLY`, not `E2EE VERIFIED`. This follows the video E2EE criteria and the admin-analysis distinction between transport encryption and true E2EE. fileciteturn6file11L1-L24 fileciteturn6file9L1-L13

### 13.6 Group encryption confirmation
A group test should only reach `PASS — E2EE VERIFIED` if the test confirms, as applicable:

- membership change triggered the required rekey/update behavior
- authorized current members retain access
- removed members do not retain future access
- sender-key or group-key distribution reflects the current participant set
- no evidence indicates stale members can decrypt newly protected content

---

## 14) Logging and Activity Stream Requirements

### 14.1 Bash-style console output
The system must produce a bash-like or shell-like textual output during test runs.

The log should contain:

- step execution markers
- readable status lines
- warning/failure lines
- run/result lines
- timestamps where appropriate

### 14.2 Ordered event stream
The system must also maintain a structured event sequence for UI rendering.

Each event should have, at minimum:

- timestamp
- event type
- display label
- status
- optional detail text

### 14.3 Allowed observability fields
The test UI may display metadata-style observability fields such as:

- correlation id
- session id
- message id
- room id
- pseudonymous sender/recipient ids
- device id
- transport path selected
- TURN usage indicator
- encryption state indicator
- auth state indicator

These fields mirror the admin-analysis observability guidance. fileciteturn6file10L1-L18

### 14.4 Prohibited output
The UI must not render:

- plaintext messages
- decrypted attachments
- media payload content
- raw key material
- secrets/tokens/passwords

---

## 15) Result Model

### 15.1 Supported terminal states
Each run must end in one of:

- PASS
- FAIL
- UNKNOWN / UNVERIFIED

For video and transport-aware scenarios, the UI may also use:

- TRANSPORT ONLY
- E2EE VERIFIED

### 15.2 Final summary requirements
The final summary must include:

- run id
- scenario name
- duration
- result
- notable warnings
- key path detail (for example direct vs relay)
- operator-friendly explanation

---

## 16) Environment and Access Rules

### 16.1 Allowed environments
This testing solution is intended for:

- local development
- sandbox
- staging
- internal pre-production test environments

### 16.2 Not for ordinary production surveillance
The test solution must not be repurposed into a production-facing live observation tool.

### 16.3 Access control
Use explicit role gating and environment gating.

Suggested roles:

- `ordinary_user`
- `test_user`
- `security_admin`

Suggested feature flags:

- `test_menu_enabled`
- `verbose_diagnostics_enabled`
- `synthetic_scenarios_enabled`
- `video_preflight_enabled`
- `document_crypto_lab_enabled`
- `group_testing_enabled`

---

## 17) UX Requirements

### 17.1 Accessibility
The UI should support:

- keyboard navigation
- reduced motion compatibility where practical
- readable contrast in console/log views
- non-color-only state distinctions

### 17.2 Operator clarity
The UI must be understandable by non-developer operators.

Use:

- plain-English labels
- readable progress states
- explicit warnings and errors
- clear final state messaging

### 17.3 No raw-JSON dependence
Operators should not need to inspect raw JSON to understand test behavior.

---

## 18) Non-Functional Requirements

### 18.1 Frontend stack alignment
The UI extension must align with the existing stack direction:

- Vue 3
- TypeScript
- Pinia

This matches the underlying product and video implementation plans. fileciteturn6file7L1-L18 fileciteturn6file3L19-L37

### 18.2 Componentization
The feature should be built as modular UI components and stores.

### 18.3 Testability
The synthetic nature of the system should make it easy to:

- replay scenarios
- inject warning/failure branches
- compare outcomes
- use with IDE agents and coding copilots

---

## 19) Suggested Component Structure

```text
secure-test-lab/
  pages/
    TestLabPage.vue
    ConnectionConsolePage.vue
  components/
    TestScenarioDropdown.vue
    EnvironmentDropdown.vue
    IntensityDropdown.vue
    TestTypeIconGrid.vue
    RunSimulationButton.vue
    AccountGovernanceCard.vue
    ConsoleHeader.vue
    AnimatedHandshakeStrip.vue
    OrderedEventFeed.vue
    BashLogPanel.vue
    ResultSummaryBar.vue
    DiagnosticsPanel.vue
  stores/
    useTestLabStore.ts
    useConnectionConsoleStore.ts
    useDiagnosticsStore.ts
    useAccountGovernanceStore.ts
  lib/
    fauxData.ts
    scenarioCatalog.ts
    eventFormatter.ts
    resultModel.ts
```

---

## 20) Suggested Scenario/Event Contracts

### 20.1 Scenario object
A scenario definition should include:

- id
- label
- description
- category (`dm`, `video`, `document`, `full`, `group`)
- environment presets
- intensity presets
- supported toggles
- required participant count
- ordered synthetic steps
- expected outcomes

### 20.2 Event object
An event definition should include:

- id
- timestamp
- type
- label
- status
- detail
- stage index

### 20.3 Log line object
A log line should include:

- timestamp
- level
- text
- optional step reference

---

## 21) Acceptance Criteria

This testing solution is complete when:

1. The product has a separate **Test Lab** page and **Connection Console** page.
2. The UI can launch at least DM, video, document, and full-suite simulated runs.
3. The UI uses faux-generated users/nodes/sessions by default.
4. The Connection Console shows an animated handshake strip, ordered event stream, and bash-style log output.
5. Test users can access a specialized diagnostics menu that ordinary users do not have.
6. Admins can review outcomes without access to real plaintext content or real media payloads.
7. The UI clearly distinguishes PASS, FAIL, TRANSPORT ONLY, E2EE VERIFIED, and UNKNOWN / UNVERIFIED where applicable.
8. The system does not require raw JSON inspection for core operator understanding.
9. The design does not reintroduce real-user surveillance patterns.
10. The app enforces no more than one active admin account.
11. The app enforces no more than two active test-user accounts by default.
12. A third active test user is possible only when group testing is explicitly enabled and approved.
13. Every test explicitly states what level of encryption/protection it confirmed.
14. The resulting markdown spec is implementation-ready for IDE agents and coding copilots.

---

## 22) Immediate Build Recommendation

Build in this order:

### Phase 1
- account-governance enforcement
- Test Lab page
- scenario dropdowns
- animated icon tiles
- Run Simulated Test action
- Connection Console page
- handshake strip
- ordered event feed
- bash-style log panel
- result summary bar

### Phase 2
- test-user diagnostics menu
- warning/failure injection branches
- replay/re-run support
- better synthetic event fixtures
- per-test encryption-confirmation result model

### Phase 3
- optional group-behavior scenarios with third-user gating
- export test artifact support
- compare run outcomes
- richer scenario catalog
- feature-flagged verbose diagnostics

---

## 23) Implementation Reminder

This solution must remain a **testing lab**, not a hidden surveillance capability.

If a proposed feature increases visibility into real user activity, real endpoint topology, or real protected content, it should be treated as out-of-scope for this testing solution unless explicitly redesigned to preserve privacy and anonymity.

The lab should remain intentionally small and governed:

- one active admin
- two active test users by default
- optional temporary third user only for approved group-behavior validation

That policy keeps the tool aligned with the spirit of secure anonymous communication while still letting the team validate DM, file, 1:1 video, and later group-membership security behavior.


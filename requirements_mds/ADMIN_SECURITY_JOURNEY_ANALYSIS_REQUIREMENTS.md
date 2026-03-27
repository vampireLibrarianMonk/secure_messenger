# Admin Capability Requirements — Exploratory Security Journey Analysis (No Content Access)

## 1) Purpose

Define an **admin-only security analysis capability** that allows authorized admins/security engineers to verify whether the secure messaging and video features are functioning safely in real-world operation **without exposing plaintext message content or media**.

This capability is investigative and evidence-driven. It must help answer whether the system is secure **in practice**, not only secure by architecture claims.

---

## 2) Core Constraint

Admins must be able to confirm app health, crypto posture, and control effectiveness **without being able to read user DM content, file plaintext, or video/audio payloads**.

---

## 3) Required Analysis Flows

The capability must support an exploratory end-to-end security journey analysis for:

1. **Direct message (DM) lifecycle**
2. **Live video connection lifecycle**

---

## 4) Required Outputs Per Flow

For each flow, the analysis output must include:

- Complete stage sequence from initiation to delivery/termination
- Security assumptions at each stage
- Assets exposed at each stage
- Trust boundaries crossed
- Attack surface introduced
- Logging and telemetry that should be captured
- Evidence required to verify stage security
- Likely failure modes and what “insecure” looks like
- Specific code/config/infra/protocol checks to run

---

## 5) Scope Coverage Checklist

Where present in implementation, include analysis of:

- Client UI
- Browser/mobile runtime
- Local storage/cache/memory exposure
- Authentication/session issuance
- Token refresh/revocation
- Message composition
- Attachment handling
- Pre-transit message encryption
- Key generation/storage/exchange/rotation/recovery
- Signaling server
- TURN/STUN usage
- WebRTC negotiation
- SDP exchange
- ICE candidate exchange
- Media transport
- Server-side relays
- Push notifications
- Queue/broker behavior
- API gateway/reverse proxy
- Database writes
- Search indexing
- Logging pipeline
- Analytics/telemetry
- Admin tooling
- Backups/snapshots
- Cross-region replication
- Retention/deletion workflows
- DNS/TLS termination
- Infrastructure secrets
- Rate limiting/abuse controls

---

## 6) Deliverable A — DM Journey Map

For one DM end-to-end flow, enumerate each stage (example anchors):

- user authenticated
- message drafted
- message encrypted (or not)
- metadata created
- API request formed
- transport initiated
- reverse proxy receives request
- application server processing
- queue/store/broker interactions
- recipient notification
- recipient fetch/decrypt/render
- retention/deletion/log side effects

For **each stage**, provide:

- stage number and name
- component involved
- data in plaintext
- data encrypted
- who can theoretically read it
- logs expected to exist
- logs that must never contain sensitive data
- validation method
- compromise severity

---

## 7) Deliverable B — Video Session Journey Map

For one video call lifecycle, enumerate each stage (example anchors):

- room/session creation
- auth and authorization
- signaling bootstrap
- STUN/TURN discovery
- SDP offer/answer
- ICE exchange
- P2P vs relay path decision
- DTLS/SRTP establishment
- media flow
- reconnection
- call termination
- artifact cleanup

For **each stage**, provide:

- stage number and name
- protocol involved
- server visibility: metadata vs content
- media protection classification:
  - end-to-end encrypted
  - hop-by-hop encrypted
  - TLS-only transport protection
- malicious server operator visibility
- network attacker visibility
- concrete tests to validate security claims

---

## 8) Deliverable C — Security Verification Matrix

Produce a matrix with these columns:

- stage
- expected security property
- evidence source
- how to test
- pass/fail criteria
- common misconfiguration
- recommended remediation

---

## 9) Deliverable D — Logging Design (Privacy-Preserving)

Design a logging strategy that supports full journey tracing while preventing sensitive-data leakage.

Must include correlation and observability fields:

- correlation_id
- session_id
- message_id
- room_id
- sender_id / recipient_id (or pseudonymous tokens)
- device_id
- key timestamps (create/send/receive/decrypt/end)
- transport path chosen
- TURN relay usage indicator
- encryption state indicator
- auth state indicator
- moderation/abuse flags

Must explicitly classify each field as:

- allowed
- hashed/tokenized
- redacted
- forbidden from logs

---

## 10) Deliverable E — Threat Modeling

For DM and video, include threats:

- passive network attacker
- active MITM
- malicious insider
- compromised client endpoint
- stolen token/session
- replay attacks
- impersonation
- metadata leakage
- notification leakage
- backup leakage
- logging leakage

For each threat, map:

- affected stages
- likely indicators
- controls
- residual risk

---

## 11) Deliverable F — Reality Check Questions (Mandatory)

The analysis must answer directly:

1. Is the system truly end-to-end encrypted or only transport encrypted?
2. Can the server read DM message bodies?
3. Can the server read video/audio media?
4. Can push notifications leak sensitive content?
5. Can logs/backups/analytics/moderation tooling expose plaintext?
6. Can admins/cloud operators access secrets or session data?
7. What exact proof is required before claiming the app is secure?

---

## 12) Analytical Constraints

The analysis must **not** assume security from technology labels alone.

Do not assume secure by default because of:

- HTTPS/TLS
- WebSocket TLS
- WebRTC usage
- JWT presence

Do not equate “encrypted in transit” with E2EE.

Do not assume TURN relay implies no relay visibility.

Always distinguish:

- transport encryption
- application-layer encryption
- end-to-end encryption
- encryption-at-rest

Any missing code/config evidence must be explicitly marked as **unknown/unverified**.

---

## 13) Output Structure Requirement

Any generated report from this admin capability must be formatted as:

1. Executive summary
2. DM stage-by-stage journey
3. Video stage-by-stage journey
4. Security verification matrix
5. Logging design
6. Top 10 likely security gaps
7. Highest-value next tests (codebase + deployed environment)

The output should be concrete, investigative, and actionable.

---

## 14) Access Control and Safeguards for This Capability

1. Restrict to designated admin/security roles only.
2. Require audit trail for every analysis run.
3. Store only metadata and verification artifacts needed for security posture assessment.
4. Prohibit inclusion of decrypted message/media content in output.
5. Apply retention limits for generated analysis artifacts.
6. Optionally require break-glass approval for expanded diagnostics.

---

## 15) Docker Admin Bootstrap Requirement (Operational)

There must be a deterministic and secure way to establish the first admin user when running the Docker image/container.

### 15.1 Required behavior

1. On container startup, bootstrap logic checks whether an eligible admin already exists.
2. If no admin exists, create one using startup configuration.
3. Bootstrap must be idempotent (safe to run repeatedly).
4. Bootstrap must complete before normal app serving is considered healthy.

### 15.2 Configuration requirements

Admin bootstrap settings must come from environment variables and/or orchestrator secrets (not source code), for example:

- `BOOTSTRAP_ADMIN_ENABLED`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD` (or one-time generated secret)

Rules:

1. No default hardcoded credentials in image, repo, or manifests.
2. Password/secret values must be provided via secret stores (Docker secrets/Kubernetes secrets/CI vault), not plaintext committed files.
3. If a temporary password is used, force password reset on first login.

### 15.3 Security controls

1. Bootstrap execution must emit audit logs (success/failure, timestamp, actor=`bootstrap_process`) without logging plaintext password/secret.
2. Bootstrap should be disable-able in production after first successful admin provisioning.
3. Limit bootstrap scope to least privilege (create admin only; no broad data access side effects).
4. Failed bootstrap attempts must fail fast and surface clear operational errors.

### 15.4 Verification checks

1. Bring up stack from clean state (`docker compose up` or equivalent) and verify admin auto-provisioning occurs once.
2. Restart containers and verify no duplicate admin users are created.
3. Validate logs do not contain plaintext credentials.
4. Validate admin can authenticate and access only intended admin security-analysis capability.

### 15.5 Insecure anti-patterns (must not be used)

- Static admin credentials embedded in Dockerfile/entrypoint
- Printing generated password to persistent logs without protection
- Recreating/resetting admin account on every restart
- Granting bootstrap account unrestricted/debug superpowers beyond required admin role

---

## 16) Success Criteria

This admin capability is considered complete when:

1. It can reconstruct DM and video security journeys end-to-end from evidence.
2. It enables validation of encryption and trust-boundary claims.
3. It identifies where plaintext could leak across app/server/infra/logging layers.
4. It provides defensible proof paths for security claims without exposing user content.
5. It preserves strict no-content-read access for admins.
6. It includes secure, repeatable Docker-based first-admin provisioning that does not expose credentials.

---

## 17) Universal Admin Menu + Organized UI Requirement

The capability must provide a **single universal admin security menu** that allows authorized users to trigger all required functionality and view results in a coherent, evidence-first interface.

### 17.1 Universal menu structure (required)

The menu must include, at minimum, these sections:

1. **Overview / Dashboard**
   - Report status summary (draft/review/final)
   - Last run time and actor
   - Open high-severity gaps
2. **Run Analysis**
   - Trigger analysis run (DM, Video, Both)
   - Select optional checks (logging, threat review, scope coverage validation)
   - Show run state (queued/running/completed/failed)
3. **DM Journey**
   - Stage-by-stage table and detail panel
4. **Video Journey**
   - Stage-by-stage table and detail panel
5. **Verification Matrix**
   - Test properties, evidence links, pass/fail readiness
6. **Scope Coverage**
   - Checklist of required scope areas with present/absent/unknown markers
7. **Logging Design**
   - Field policy classifications (allowed/hashed/redacted/forbidden)
8. **Threat Model**
   - Threats, indicators, controls, residual risk
9. **Top Gaps & Next Tests**
   - Ranked top 10 likely gaps and prioritized next tests
10. **Reality Check**
   - Mandatory direct answers for Section 11 questions
11. **Evidence & Snapshots**
   - Compiled exports, snapshots, SHA-256 hashes, integrity checks
12. **Audit Trail**
   - Run triggers, compiled views, exports, snapshots, retention actions

### 17.2 Interaction requirements

1. Every menu section must support filtering by `report_id` and optionally `flow_type`.
2. UI must preserve stable correlation context (e.g., report ID, run ID, actor, timestamps) while navigating tabs.
3. Trigger actions (run/export/snapshot) must return immediate confirmation and status feedback.
4. Any asynchronous operations must expose progress and final state clearly.
5. Detail views must support drill-down without requiring raw JSON inspection.
6. **Run Analysis** must present tests in a **selection box style control** (single or multi-select as configured) instead of requiring users to infer backend check keys.
7. The selected test options must map to backend checks deterministically and be visible before execution.

### 17.2.1 Plain-English test catalog requirement

The Run Analysis section must include a human-readable test catalog so non-developer operators can understand what each test validates.

Minimum catalog entries:

1. **Direct Message Journey**
   - Plain-English description of DM lifecycle validation and exposure checks.
2. **Live Video Journey**
   - Plain-English description of signaling/media path and visibility checks.
3. **Logging & Exposure Controls**
   - Plain-English description of metadata logging guardrails and plaintext prevention.

Rules:

1. Labels must avoid internal jargon-only names where possible.
2. Backend check identifiers may exist, but UI must prioritize plain-English wording.
3. If test catalog definitions change, UI and backend mappings must remain synchronized.

### 17.3 Data safety and display constraints

1. UI must never render plaintext DM bodies, decrypted attachments, or media payload content.
2. Sensitive fields must be displayed according to logging policy classification:
   - allowed
   - hashed/tokenized
   - redacted
   - forbidden
3. If evidence is missing, UI must display `unknown/unverified` explicitly (not blank or implied pass).
4. Any “secure” badge/indicator is prohibited unless backed by required evidence paths.

### 17.4 Access control and authorization behavior in UI

1. Menu visibility and actions must be restricted to authorized admin/security roles.
2. Users failing first-login password reset policy must not access security-analysis UI actions.
3. Non-admin users must be denied access and shown a generic authorization error without leaking system internals.

### 17.5 Required UX outputs

The UI must provide these views in addition to API output:

1. **Organized report workspace** with pinned sections matching Section 13 output order.
2. **Evidence panel** per stage linking to code/config/infra/protocol verification notes.
3. **Audit timeline** sorted by timestamp with actor and action.
4. **Snapshot integrity panel** showing stored hash, recomputed hash, and match/mismatch status.
5. **Run activity stream** that clearly logs what is being tested and in what order.

### 17.5.1 Run-state and operator feedback requirement

Run operations must provide explicit operator feedback throughout the full lifecycle.

Required states/messages:

1. Run requested
2. Test(s) queued with readable names
3. Running/in-progress
4. Completed or failed
5. Post-run refresh complete (dashboard/artifacts updated)

UI behavior constraints:

1. Trigger button must be disabled while run state is in-progress.
2. Trigger button label should reflect active state (example: `Running...`).
3. Errors must be explicit and actionable (e.g., no report selected, no tests selected).
4. Feedback should include timestamps where possible to aid operator traceability.

### 17.6 Verification criteria for universal menu

1. Admin can navigate all required sections from one menu without direct API calls.
2. Admin can trigger run/export/snapshot from UI and observe corresponding audit events.
3. UI never reveals prohibited content fields under normal or error paths.
4. UI accurately reflects unknown/unverified states when evidence is absent.
5. Section names and ordering remain consistent with this requirements document.
6. Run Analysis uses plain-English test labels with clear descriptions.
7. Test selection is possible through an explicit selection-box style control.
8. While a run is active, trigger control is disabled until completion/failure state resolves.
9. Operator can see an intuitive run activity stream describing exactly what was tested.

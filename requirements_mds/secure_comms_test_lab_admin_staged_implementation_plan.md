# Secure Comms Test Lab — Admin Implementation Stages

This plan breaks implementation into reviewable stages, starting with **UI scaffolding/placeholders** and then layering each capability in a safe order.

## Implementation Status Snapshot (Required vs Implemented)

| Stage | Required (Summary) | Implemented Status |
|---|---|---|
| 0 | Foundations/flags/guardrails | ✅ Implemented (`TEST_LAB_*` settings, role/flag vocabulary, policy limits) |
| 1 | UI scaffolding/placeholders | ✅ Implemented (Admin Test Lab shell + tabs and placeholder-first structure) |
| 2 | Synthetic scenario catalog + run wiring | ✅ Implemented (`scenarioCatalog`, faux generators, run ID/users/events wiring) |
| 3 | Connection console progression/log UX | ✅ Implemented (state strip, ordered feed, bash-style logs, run summary states) |
| 4 | Admin governance enforcement | ✅ Implemented (bootstrap policy surface + test-user management + governance status/audit events) |
| 5 | Result integrity model | ✅ Implemented (`PASS — E2EE VERIFIED` / `PASS — TRANSPORT ONLY` / `FAIL` / `UNKNOWN`) |
| 6 | Admin review workspace + safe artifacts | ✅ Implemented (`/api/test-lab/runs/`, persisted artifact review, observability metadata, no-plaintext guard) |
| 7 | Test-user diagnostics menu | ✅ Implemented (Diagnostics tab gated by role + verbose diagnostics flag) |
| 8 | Warning/failure injection + replay/re-run | ✅ Implemented (injection toggles, local run history, replay/re-run, outcome comparison) |
| 9 | Feature-flagged group behavior capability | ✅ Implemented (additional group scenarios, group slot messaging, feature-flag gating) |
| 10 | Hardening/accessibility/release readiness | 🟡 Partially implemented (privacy guardrails + a11y live region + operational hardening done; full automated E2E suite/release sign-off still recommended) |

### Important Reality Check

Current execution flow remains **synthetic/faux** (simulation-driven). The admin test lab now has stronger governance, diagnostics, review artifacts, and result classification integrity, but it is **not yet a real external harness-driven execution system**.

---

## Stage 0 — Foundations & Guardrails (Pre-UI)

### Goal
Establish admin/test-lab boundaries before feature work expands.

### Scope
- Define/confirm roles and flags used by the lab:
  - `security_admin`
  - `test_user`
  - `test_menu_enabled`
  - `synthetic_scenarios_enabled`
  - `verbose_diagnostics_enabled`
  - `group_testing_enabled`
- Confirm environment gating (local/sandbox/staging only).
- Create placeholder policy hooks for account limits:
  - max active admins = 1
  - max active test users (default) = 2
  - optional temporary third test user when group testing enabled

### Deliverables
- Role/flag constants and TODO comments where enforcement will land.
- Minimal admin/test-lab route guard placeholder.
- Short README note describing non-surveillance constraints.

### Exit Criteria
- Codebase has explicit role/flag vocabulary used by upcoming UI work.

---

## Stage 1 — UI Scaffolding & Placeholders (Requested First)

### Goal
Create skeleton admin-facing Test Lab surfaces with placeholder data.

### Scope
- Add new pages with placeholder content:
  - `TestLabPage.vue`
  - `ConnectionConsolePage.vue`
- Add placeholder components (render-only, no live logic):
  - scenario/environment/intensity selectors
  - icon grid
  - run button
  - account governance card
  - console header
  - handshake strip
  - ordered feed
  - bash log panel
  - result summary bar
- Add stub stores:
  - `useTestLabStore.ts`
  - `useConnectionConsoleStore.ts`
  - `useAccountGovernanceStore.ts`
- Wire routes/navigation so admins can reach both pages.

### Deliverables
- Full component/page structure exists and compiles.
- Placeholder/mock strings displayed for all major sections.
- No backend dependence yet.

### Exit Criteria
- Admin can navigate to Test Lab and Connection Console and see full shell UI.

---

## Stage 2 — Synthetic Scenario Catalog + Run Wiring

### Goal
Power the scaffold with synthetic scenario metadata and basic run flow.

### Scope
- Create catalog/contracts:
  - `scenarioCatalog.ts`
  - `fauxData.ts`
  - `resultModel.ts`
  - `eventFormatter.ts`
- Define scenario objects for:
  - DM basic/reconnect
  - video signaling/E2EE verification
  - document encrypted flow
  - full communication suite
- Wire selectors and icon tiles to selected scenario state.
- Implement `Run Simulated Test` action to create a synthetic run record and transition to Connection Console.

### Deliverables
- Scenarios are selectable via human-readable labels.
- Run IDs, synthetic node names, and initial event timeline generated.

### Exit Criteria
- Operator can launch a synthetic run and reach a populated console view.

---

## Stage 3 — Connection Console Execution Experience

### Goal
Make console behavior feel real with ordered progression and terminal logs.

### Scope
- Handshake strip state machine:
  - inactive, active, completed, warning, failed, unknown
- Ordered event feed with timestamps and status tags.
- Bash-style log streaming simulation (line-by-line updates).
- Result summary bar with duration and warnings.
- Support console states:
  - idle, running, completed, failed, unknown/unverified

### Deliverables
- Animated/simulated progression for DM, video, document, full-suite.
- Readable operator-focused status presentation (no raw JSON required).

### Exit Criteria
- Console clearly shows run progression and terminal-like outputs end-to-end.

---

## Stage 4 — Admin Governance Enforcement (Core Admin Capability)

### Goal
Implement enforceable admin account and test-user limits required by policy.

### Scope
- Backend enforcement for active-account ceilings:
  - 1 active admin max
  - 2 active test users default max
- Controlled pathway for creating/deactivating test users.
- Audit events for bootstrap and account state changes.
- Surface governance status on Test Lab card:
  - `Active admin accounts: 1 / 1`
  - `Active test users: 2 / 2`

### Deliverables
- Real enforcement logic (not just UI display).
- UI indicators backed by real policy checks.

### Exit Criteria
- Violating account limits is blocked and auditable.

---

## Stage 5 — Encryption Confirmation Model & Result Integrity

### Goal
Ensure every test reports the specific protection level proven.

### Scope
- Implement terminal result classes:
  - `PASS — E2EE VERIFIED`
  - `PASS — TRANSPORT ONLY`
  - `FAIL`
  - `UNKNOWN / UNVERIFIED`
- Map scenario evidence requirements by domain (DM/video/document).
- Add explicit “insufficient evidence” handling for unknown/unverified outcomes.

### Deliverables
- Result model used consistently in console and admin review surfaces.
- No ambiguous “pass” without protection-level context.

### Exit Criteria
- All supported scenarios end with explicit, policy-compliant classification.

---

## Stage 6 — Admin Review Workspace (Artifacts Without Plaintext)

### Goal
Provide admin review power while preserving no-content-read boundaries.

### Scope
- Add admin review list/detail views for synthetic runs.
- Display:
  - ordered event feeds
  - bash logs
  - result summaries
  - metadata observability fields (session/correlation/transport indicators)
- Enforce prohibited output rules (no plaintext, no keys, no media content).

### Deliverables
- Admin can inspect outcomes and diagnostics for lab runs only.

### Exit Criteria
- Review flow supports investigation without decrypting protected content.

---

## Stage 7 — Test User Specialized Menu + Domain Diagnostics

### Goal
Add scoped diagnostics for test users, hidden from ordinary users.

### Scope
- Add testing menu sections:
  - Run Scenario, Connection Console, DM/Video/Document actions, Diagnostics, Export Artifact
- Add per-domain diagnostic state panels:
  - DM encryption lifecycle
  - video signaling/ICE/TURN/DTLS/E2EE state
  - document key/blob/upload/decrypt/hash checks
- Gate visibility strictly by role and environment.

### Deliverables
- Test users get deep but safe diagnostics in lab mode.

### Exit Criteria
- Ordinary users cannot access this menu; test users can.

---

## Stage 8 — Warning/Failure Injection + Replay/Re-run

### Goal
Increase operator/QA usefulness through controlled synthetic branch testing.

### Scope
- Implement toggles:
  - inject warning conditions
  - include unknown/unverified branch
  - verbose bash log
  - auto-scroll logs
- Add replay/re-run from historical scenario config.
- Add scenario comparison basics (run-to-run outcome deltas).

### Deliverables
- Operators can intentionally exercise warning/failure/unknown paths.

### Exit Criteria
- Test Lab supports deterministic reruns and branch visibility.

---

## Stage 9 — Optional Group Behavior Capability (Feature-Flagged)

### Goal
Add temporary third-user group security tests safely and only when enabled.

### Scope
- Feature-gate all group scenario UI behind `group_testing_enabled`.
- Implement scenarios:
  - join + rekey
  - remove + access loss
  - group call membership change
  - sender-key distribution checks
  - post-removal residual access checks
- Implement temporary third test-user activation/deactivation workflow with audit logging.

### Deliverables
- Group behavior tests available only in approved flagged contexts.

### Exit Criteria
- Third user cannot remain permanently active outside approved group-testing flow.

---

## Stage 10 — Hardening, Accessibility, and Release Readiness

### Goal
Finalize stability and operator usability before broad internal rollout.

### Scope
- Accessibility pass (keyboard navigation, contrast, non-color status cues, reduced motion).
- Security/privacy pass against prohibited-output checklist.
- E2E tests for main admin workflows and result classifications.
- Documentation for operators + implementation notes for future contributors/LLM handoff.

### Deliverables
- Release checklist signed for internal environments.

### Exit Criteria
- Lab is implementation-ready, privacy-preserving, and operationally clear.

### Current Status Notes
- ✅ Added prohibited-output guardrails in artifact persistence path.
- ✅ Added accessibility live-region support and visually-hidden utility for status announcements.
- ✅ Added operator-facing controls and safer log handling (credential redaction retained).
- ⚠️ Remaining recommended hardening: explicit automated E2E workflow assertions and formal release sign-off checklist execution in CI.

---

## Suggested Execution Rhythm

1. **Implement Stages 0–1 first** (foundations + scaffolding placeholders).
2. Add interactive synthetic flow via **Stages 2–3**.
3. Deliver hard policy requirements in **Stages 4–5**.
4. Expand review + diagnostics in **Stages 6–8**.
5. Add optional group behavior behind flags in **Stage 9**.
6. Finalize with **Stage 10** hardening.

This keeps risk low while making UI progress visible immediately.
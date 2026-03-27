# 04 — Audit: Full Communication Suite (`documentation/04-full-communication-suite.md`)

## Audit Verdict
**Verdict: VERIFIED as a synthetic cross-domain aggregator; not a real integrated cryptographic execution harness.**

## What the Document Claims
The full suite claims it runs DM, video, and document checks in one scenario and classifies based on combined evidence.

## Code Evidence

### A) Scenario definition exists and matches claimed sequence
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "full-suite"`
  - `category: "full"`
  - `orderedSteps: ["dm", "video", "document", "result"]`

### B) Combined evidence model exists
- `frontend/src/lib/resultModel.ts`
  - For `scenario === "full"`, evidence lines include DM, document, and (where applicable) video/group checks.
  - Result logic can return `PASS — E2EE VERIFIED`, `UNKNOWN / UNVERIFIED`, `FAIL`.
  - Full-suite now requires **runtime-verified** video app-layer evidence before `PASS — E2EE VERIFIED` can be emitted.
  - Runtime experimental obfuscation evidence is explicitly downgraded from cryptographic E2EE claims.

### C) Synthetic execution supports cross-domain logging and artifacts
- `frontend/src/components/AdminTestLabPanel.vue`
  - logs synthetic full-suite steps
  - stores run artifacts with scenario/result/evidence/diagnostics
  - supports warning, unknown branch, and failure branch toggles
  - exhaustive full-suite runs can now emit `runtime_experimental_obfuscation` video-evidence source, which remains non-E2EE-verified by policy.

## Security Interpretation
This suite correctly functions as a **meta-test of synthetic evidence consistency** across domains.

However it does **not** orchestrate real DM send+decrypt + real document transfer + live video call in a single automated executable harness. It simulates these domains through scenario events and evidence flags.

## Standards/Framework Traceability
- Uses same underlying standards basis as domain components (AES-GCM/SHA-256, WebRTC stack concepts).
- No evidence of external ISO certification statement in suite implementation.

## Required Codebase Changes to Close Security Gaps
1. **Convert full-suite from synthetic aggregator to hybrid evidence runner**
   - Add executable test orchestration that invokes real DM/document/video flows and records concrete checkpoints, not only simulated event states.
   - Implement this as a dedicated orchestration module referenced by `frontend/src/components/AdminTestLabPanel.vue` and backed by verifiable artifact schema.

2. **Enforce domain-complete pass gating**
   - Update `frontend/src/lib/resultModel.ts` so `PASS — E2EE VERIFIED` in `full` scenario is impossible unless each included domain has concrete proof artifacts.
   - Add per-domain required evidence IDs and fail/unknown when any domain is synthetic-only.

3. **Add cross-domain consistency tests**
   - Add automated tests validating that DM/video/document evidence cannot be mixed inconsistently (e.g., video transport-only while full-suite reports full E2EE).
   - Add regression tests for warning/unknown/failure branch precedence.

4. **Harden artifact trust model**
   - In `backend/messenger/views.py` (`TestLabRunArtifactView`), add stricter schema validation and optional artifact signing to prevent forged evidence payloads.

## Implementation Progress Update (Current Phase)
### Completed in this phase
- Added backend schema enforcement in `backend/messenger/views.py` so `PASS — E2EE VERIFIED` artifacts for `video`/`full` categories must include:
  - `diagnostics.video.app_layer_evidence_source = runtime_verified`
  - non-`transport_only` app-layer classification markers.
- Added backend unit tests in `backend/messenger/tests.py` covering:
  - rejection of video E2EE-verified artifacts with `runtime_experimental_obfuscation`,
  - rejection of video E2EE-verified artifacts with `transport_only`,
  - acceptance path for `runtime_verified` evidence source.

### Security impact
- Strengthens server-side artifact trust boundaries by preventing client-submitted synthetic payloads from overstating cryptographic video/full-suite assurance.

### Remaining gap
- True standards-aligned media frame cryptography (SFrame/AES-GCM class) remains unimplemented; `runtime_verified` currently represents policy gating surface, not completed cryptographic media protocol assurance.

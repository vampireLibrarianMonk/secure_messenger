# 00 — Audit Method and Standards Basis

## Scope
This audit reviews the seven scenario documents in `documentation/01` through `documentation/07` and verifies whether each document's claims are supported by actual implementation.

Primary evidence sources:

- `frontend/src/components/AdminTestLabPanel.vue`
- `frontend/src/lib/scenarioCatalog.ts`
- `frontend/src/lib/resultModel.ts`
- `frontend/src/lib/fauxData.ts`
- `frontend/src/lib/crypto.ts`
- `frontend/src/App.vue`
- `frontend/src/stores/video.ts`
- `backend/messenger/views.py`
- `backend/messenger/consumers.py`
- `backend/messenger/models.py`
- `backend/messenger/tests.py`
- `README.md`

## High-Level Reality Check
The documented tests are **synthetic simulation scenarios** in the Admin Test Lab, not end-to-end cryptographic proof harnesses against live production traffic. This is explicitly aligned with project scope in `README.md` and requirements docs.

## Cryptographic/Protocol Standards Traceability (Observed)

### 1) Message + file encryption primitives (client-side)
- **AES-GCM** via WebCrypto (`window.crypto.subtle.encrypt/decrypt`, `AES-GCM`, 12-byte IV)
- **Random key material** via WebCrypto CSPRNG (`window.crypto.getRandomValues`)
- **SHA-256** hashing for file digest (`subtle.digest("SHA-256", ...)`)

Potential standards mapping:
- AES-GCM conceptually aligns to NIST SP 800-38D mode usage.
- SHA-256 aligns to FIPS 180-4 algorithm family.

### 2) Key agreement identity support
- Tries **X25519** first, falls back to **ECDH P-256** when unsupported.

Potential standards mapping:
- X25519: RFC 7748 curve definition (algorithm family basis).
- ECDH P-256: NIST P-256 / FIPS 186 family basis.

### 3) Video transport
- WebRTC signaling + ICE candidate exchange + peer connection flow present.
- App behavior assumes WebRTC transport protections (DTLS/SRTP equivalent path).
- Current frontend includes runtime insertable-stream hooks and experimental XOR frame obfuscation, but this is **not** standards-based or cryptographically sufficient app-layer media E2EE.

Potential standards mapping:
- ICE conceptually aligns to RFC 8445 process model.
- DTLS-SRTP transport model aligns to standard WebRTC stack behavior.

## Compliance/Certification Statement
No evidence in this repository establishes formal compliance certification (e.g., ISO/IEC 27001 certification, SOC 2 attestation, FIPS 140 validated crypto module operation mode, etc.).

Therefore, this audit only confirms **implementation traceability**, not external certification.

## Required Codebase Changes to Close Security Gaps
1. **Formalize crypto architecture docs into enforceable controls**
   - Add a security architecture document mapping each advertised capability (DM E2EE, document E2EE, video transport/app-layer E2EE, group rekey) to exact code paths and threat assumptions.
   - Add CI checks requiring every audit claim to reference a concrete implementation test.

2. **Add missing cryptographic verification tests in backend/frontend CI**
   - Expand `backend/messenger/tests.py` with tests that validate ciphertext-only persistence, membership authorization edge cases, and artifact redaction constraints.
   - Add frontend unit/integration tests for `frontend/src/lib/crypto.ts` and message/file workflow correctness.

3. **Introduce standards conformance matrix**
   - Add `documentation/appendix/standards-matrix.md` linking algorithms/protocols to RFC/NIST references and implementation status (`implemented`, `partial`, `planned`).
   - Add explicit “not certified” markers where ISO/FIPS/SOC evidence is absent.

4. **Strengthen secure defaults and validation gates**
   - Add runtime validations rejecting insecure cryptographic parameter drift (e.g., non-12-byte GCM nonce, malformed key lengths).
   - Add policy checks preventing synthetic `PASS — E2EE VERIFIED` where required concrete crypto components are unimplemented.

## Backend Artifact Trust-Model Hardening (Current)
- `backend/messenger/views.py` (`_validate_run_artifact_schema`) now enforces additional video/full artifact integrity rules:
  - if `category in {"video","full"}` and `result == "PASS — E2EE VERIFIED"`, then
    - `diagnostics.video.app_layer_evidence_source` must equal `runtime_verified`, and
    - `diagnostics.video.transport_vs_app_layer` cannot be `transport_only`.
- This blocks forged/synthetic artifact payloads from claiming cryptographic E2EE status without runtime-verified evidence source markers.

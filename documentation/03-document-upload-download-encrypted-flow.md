# 03 — Document Upload/Download Encrypted Flow

## 1) Quick Summary (Layperson)
This test simulates secure document sharing: a sender encrypts a file, uploads encrypted content, sends a wrapped key, and the recipient fetches/decrypts.

## 2) Test Metadata
- **Test ID:** `document-encrypted`
- **Category:** `document`
- **Participants required:** 2
- **Supported environments:** `local sandbox`, `staging simulator`, `reconnect simulation`
- **Supported intensities:** `quick`, `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Step-by-Step Flow (What Happens)
1. **file-key** — per-file key generation stage.
2. **encrypt-blob** — file payload encryption stage.
3. **upload** — encrypted blob transfer stage.
4. **wrap-key** — wrapped key transfer stage.
5. **fetch** — recipient retrieval stage.
6. **decrypt** — recipient decryption stage.

## 4) Expected Observability (Console + Logs)
- Log flow lines use document-safe synthetic semantics:
  - `[encrypted document key-wrap #N]`
- Diagnostics confirm:
  - `file_key_generated`
  - `encrypted_blob_produced`
  - `wrapped_key_sent`
  - `no_plain_upload_path_detected`

## 5) Result Logic for Security Review
For document/full evidence paths, these checkpoints are evaluated:
- Client-side blob encryption confirmed
- Wrapped-key transfer confirmed
- Recipient decrypt confirmation

Classification behavior:
- **PASS — E2EE VERIFIED** when required document evidence is complete and no anomaly conditions block attestation.
- **UNKNOWN / UNVERIFIED** when warnings, unknown branch, or incomplete evidence exist.
- **FAIL** when failure branch aborts execution.

## 6) Security-Relevant Assertions
- Upload stage is represented as encrypted blob transfer.
- Key management and data payload stages are separated in explicit steps.
- No plaintext document payload is included in synthetic logs/artifacts.

## 7) Reviewer Checklist
- [ ] Key generation precedes encryption.
- [ ] Encryption precedes upload.
- [ ] Wrapped-key and decrypt stages are both present.
- [ ] Diagnostics indicate no plaintext upload path.
- [ ] Final result aligns with evidence and warning state.


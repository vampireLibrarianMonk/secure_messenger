# 03 — Audit: Document Upload/Download Encrypted Flow (`documentation/03-document-upload-download-encrypted-flow.md`)

## Audit Verdict
**Verdict: STRONGLY VERIFIED for client-side encrypted file flow in current implementation, with caveats on key-wrapping rigor.**

## What the Document Claims
The document claims file-key generation, client encryption, encrypted upload, wrapped key transfer, fetch, and recipient decrypt.

## Code Evidence

### A) Scenario definition and synthetic steps match
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "document-encrypted"`
  - ordered steps: `file-key`, `encrypt-blob`, `upload`, `wrap-key`, `fetch`, `decrypt`

### B) Actual file encryption/decryption exists in app code
- `frontend/src/lib/crypto.ts`
  - `encryptFile(file)`:
    - generates 32-byte random key
    - generates 12-byte nonce
    - AES-GCM encrypts file bytes client-side
    - computes SHA-256 digest
  - `decryptFile(...)`:
    - AES-GCM decrypts encrypted blob client-side

### C) Upload path carries encrypted blob + key metadata
- `frontend/src/App.vue` (`sendEncryptedFile`)
  - uploads encrypted blob (`.enc`) via `/attachments/`
  - includes `wrapped_file_key`, `file_nonce`, `sha256`, `mime_type`

### D) Server-side persistence model supports encrypted envelope style
- `backend/messenger/models.py` `Attachment` stores:
  - `blob`, `sha256`, `wrapped_file_key`, `file_nonce`
- `backend/messenger/views.py` `AttachmentViewSet.perform_create` persists upload metadata and file object.

### E) Recipient decrypt/download path is implemented
- `frontend/src/App.vue` (`downloadAttachment`)
  - fetches blob from attachment URL
  - decrypts locally with `decryptFile(encryptedBlob, wrapped_file_key, file_nonce, ...)`
  - triggers local download of decrypted content.

## Important Cryptographic Caveat
`wrapped_file_key` is currently treated as directly-usable key material in app flow, not a separately encrypted/wrapped key envelope using a recipient public key/KMS construct.

Implication:
- The architecture is client-encrypted and server stores encrypted blob, but formal key-wrapping semantics are simplified in current implementation.

## Standards/Framework Traceability
- AES-GCM and SHA-256 usage are clearly present (WebCrypto primitives).
- No evidence of formal standards certification claims (ISO/FIPS module validation statements) in repository docs/code.

## Required Codebase Changes to Close Security Gaps
1. **Implement true file-key wrapping per recipient/device**
   - Replace direct `wrapped_file_key` usage with actual key-wrap/envelope encryption using recipient public keys (from `Device.identity_key`) in `frontend/src/App.vue` and crypto helpers.
   - Support multi-recipient key envelopes for group document sharing.

2. **Add attachment integrity verification on download**
   - In `frontend/src/App.vue` download flow, recompute SHA-256 after decrypt and compare to stored `attachment.sha256`.
   - Fail closed with explicit user error if digest mismatch occurs.

3. **Harden backend validation for attachment metadata**
   - In serializers/views, validate `file_nonce`, `wrapped_file_key`, and `sha256` format/length before persistence.
   - Add size and MIME policy enforcement in `backend/messenger/views.py` for upload hardening.

4. **Add security tests for attachment path**
   - Add backend tests for unauthorized fetch/upload and malformed metadata rejection.
   - Add frontend tests for decrypt failure and integrity mismatch handling.

# 01 — DM Basic Encrypted Exchange

## 1) Quick Summary (Layperson)
This test simulates a one-to-one secure message exchange between two temporary test users.
It verifies that a message is treated like encrypted data during send/route/fetch and that the recipient can decrypt at the end.

If everything is clean (no warning/failure/unknown branch injection), this test should complete in a pass state.

## 2) Test Metadata
- **Test ID:** `dm-basic`
- **Category:** `dm`
- **Participants required:** 2
- **Supported environments:** `local sandbox`, `staging simulator`, `reconnect simulation`
- **Supported intensities:** `quick`, `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Synthetic Users and Data Creation
- Two ephemeral test users are generated at run start (`test-user-<hash>`).
- Each gets a synthetic 32-hex credential and assigned faux node.
- Start logs show `CREATE_USER ... credential=generated_secure_hex(redacted)`.
- End logs show `DESTROY_USER ...` teardown for both users.

## 4) Step-by-Step Flow (What Happens)
1. **session**
   - Session begins for sender/recipient pair.
   - Event feed marks step active then completed.
2. **encrypt**
   - Sender-side encryption stage is simulated.
3. **route**
   - Ciphertext routing stage is simulated (`[dm ciphertext #N]`).
4. **fetch**
   - Recipient retrieval stage is simulated.
5. **decrypt**
   - Recipient decryption stage is simulated.

## 5) Expected Observability (Console + Logs)
- **Connection Console** shows ordered event state transitions: `active` -> `completed`.
- **Bash-style log** includes directional flow and ciphertext labels:
  - `sender -> recipient [dm ciphertext #<step>]`
- **Run Summary** includes:
  - State
  - Duration
  - Warning count

## 6) Pass/Fail/Unknown Logic (Security Review View)
Result classification is evidence-driven:
- **PASS — E2EE VERIFIED** when all DM evidence checks are satisfied and no warning/failure/unknown-branch condition blocks attestation.
- **FAIL** if failure branch is injected and run aborts.
- **UNKNOWN / UNVERIFIED** if evidence is incomplete, warnings require manual review, or unknown/unverified environment branch is selected.

DM evidence checkpoints:
- Client-side encryption confirmed
- Ciphertext-only routing confirmed
- Recipient decrypt path confirmed

## 7) Security-Relevant Assertions
- No plaintext payload is logged in the synthetic flow.
- Routing semantics are represented as ciphertext transport.
- Recipient-side decrypt stage is explicit in event order.
- Artifact metadata enables traceability without exposing secrets.

## 8) Reviewer Checklist
- [ ] Exactly two test users were created and destroyed.
- [ ] Event order is session -> encrypt -> route -> fetch -> decrypt.
- [ ] Log lines show ciphertext routing semantics (not plaintext body content).
- [ ] Warning count is 0 for clean pass expectation.
- [ ] Result classification matches run conditions.

## 9) Common Non-Pass Causes
- Warning injection enabled.
- Unknown/unverified branch enabled.
- Failure branch enabled.
- Missing/partial evidence due to aborted or anomalous run.

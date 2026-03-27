# 05 — Group Join and Rekey Test

## 1) Quick Summary (Layperson)
This test simulates a group scenario where membership changes and encryption keys are rotated (rekeyed) so the group remains secure.

## 2) Test Metadata
- **Test ID:** `group-join-rekey`
- **Category:** `group`
- **Participants required:** 3
- **Feature flag required:** `group_testing_enabled`
- **Supported environments:** `staging simulator`, `unknown/unverified branch`
- **Supported intensities:** `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Step-by-Step Flow (What Happens)
1. **group-init** — group session starts.
2. **membership-change** — participant set changes.
3. **rekey** — key rotation is triggered.
4. **redistribute** — updated key material is redistributed.
5. **access-check** — access behavior is validated after rekey.

## 4) Evidence and Classification
Group-focused evidence includes:
- Membership-change rekey behavior confirmed
- Post-change access behavior confirmation

Outcome behavior:
- **PASS — E2EE VERIFIED** when rekey and access checks confirm expected secure behavior with complete evidence and no blockers.
- **UNKNOWN / UNVERIFIED** when warnings, unknown branch, or incomplete evidence prevent attestation.
- **FAIL** if failure branch is injected.

## 5) Security-Relevant Assertions
- Membership changes must cause cryptographic state update.
- Rekey redistribution must occur after membership event.
- Access behavior after rekey must match policy expectation.

## 6) Reviewer Checklist
- [ ] Group init happened before membership change.
- [ ] Rekey step executed after membership change.
- [ ] Redistribute step occurred before access check.
- [ ] Result evidence explicitly references rekey behavior.
- [ ] No unexpected warnings or forced unknown branch.


# 07 — Group Call Membership-Change Test

## 1) Quick Summary (Layperson)
This test simulates a secure group-call scenario where participants join/leave and call encryption state must stay correct as membership changes.

## 2) Test Metadata
- **Test ID:** `group-call-membership-change`
- **Category:** `group`
- **Participants required:** 3
- **Feature flag required:** `group_testing_enabled`
- **Supported environments:** `staging simulator`, `degraded relay environment`, `unknown/unverified branch`
- **Supported intensities:** `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Step-by-Step Flow (What Happens)
1. **group-call-init** — call setup for group participants.
2. **membership-change** — join/leave event occurs.
3. **rekey** — call key state rotates to match membership.
4. **sender-key-distribute** — updated sender key material distribution.
5. **access-check** — verify expected participant access state.
6. **result** — final evidence outcome.

## 4) Security Review Focus Areas
- Call signaling continuity during membership changes.
- Rekey timing relative to join/leave events.
- Sender-key distribution correctness.
- Access behavior after cryptographic state update.

## 5) Evidence and Classification
- Group rekey and access evidence feed classification.
- **PASS — E2EE VERIFIED** requires complete evidence with no blockers.
- **UNKNOWN / UNVERIFIED** indicates insufficient evidence, warning-required manual verification, or unknown branch.
- **FAIL** if failure branch is injected.

## 6) Security-Relevant Assertions
- Membership changes are security-sensitive events and must trigger key-state updates.
- Sender-key distribution should not precede rekey completion.
- Final access expectations must match post-change group policy.

## 7) Reviewer Checklist
- [ ] Membership change is visible and ordered before rekey.
- [ ] Rekey is completed before sender-key distribution is treated as valid.
- [ ] Access-check outcome matches expected policy.
- [ ] Evidence summary references group security checkpoints.
- [ ] Any warnings are justified and manually reviewed.


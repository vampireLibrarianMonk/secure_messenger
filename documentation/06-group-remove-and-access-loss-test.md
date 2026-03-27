# 06 — Group Remove and Access-Loss Test

## 1) Quick Summary (Layperson)
This test simulates removing a group member and checks that the removed user can no longer access newly protected group content.

## 2) Test Metadata
- **Test ID:** `group-remove-access-loss`
- **Category:** `group`
- **Participants required:** 3
- **Feature flag required:** `group_testing_enabled`
- **Supported environments:** `staging simulator`, `unknown/unverified branch`
- **Supported intensities:** `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Step-by-Step Flow (What Happens)
1. **group-init** — group starts with initial members.
2. **membership-change** — one participant is removed.
3. **rekey** — cryptographic keys rotate.
4. **post-removal-access-check** — removed participant access is checked.
5. **result** — final evidence classification.

## 4) Security Objective
Primary objective is post-removal confidentiality:
- A removed member should not retain access to new protected content after rekey.

## 5) Evidence and Classification
- Rekey and post-removal denial evidence feed into final classification.
- **PASS — E2EE VERIFIED** requires successful rekey and denial behavior evidence.
- **UNKNOWN / UNVERIFIED** indicates evidence gap or unverified branch.
- **FAIL** indicates explicit failure branch.

## 6) Security-Relevant Assertions
- Removal event and rekey sequencing is mandatory.
- Post-removal check must run after rekey completion.
- Artifacts should allow review without exposing plaintext.

## 7) Reviewer Checklist
- [ ] Removal action is visible in ordered events.
- [ ] Rekey occurs before access-loss assertion.
- [ ] Post-removal access check indicates expected denial behavior.
- [ ] Result evidence includes group/access assertions.
- [ ] Warning/failure/unknown conditions are intentional and documented.


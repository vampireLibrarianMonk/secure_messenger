# 04 — Full Communication Suite

## 1) Quick Summary (Layperson)
This test runs DM, video, and document security checks as one combined scenario. It is used for broad confidence checks and cross-domain consistency.

## 2) Test Metadata
- **Test ID:** `full-suite`
- **Category:** `full`
- **Participants required:** 2
- **Supported environments:** `local sandbox`, `staging simulator`, `unknown/unverified branch`
- **Supported intensities:** `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)

## 3) Step-by-Step Flow (What Happens)
1. **dm** — direct-message synthetic chain
2. **video** — video transport/app-layer checks
3. **document** — encrypted document flow checks
4. **result** — combined evidence evaluation and classification

## 4) Evidence Model (Cross-Domain)
This suite aggregates evidence from:
- DM checkpoints (encrypt/routing/decrypt)
- Video checkpoints (transport and app-layer)
- Document checkpoints (blob encryption, wrapped key, recipient decrypt)
- Group checkpoints are only applied when scenario category is group/full logic paths require them where relevant

## 5) Result Logic for Security Review
- **PASS — E2EE VERIFIED** only when required evidence across domains is complete and no blockers are present.
- **UNKNOWN / UNVERIFIED** if evidence chain is incomplete, unknown branch selected, or warnings require manual verification.
- **FAIL** if failure branch occurs.

## 6) Security-Relevant Assertions
- Ensures one domain does not mask failures in another domain.
- Preserves no-plaintext synthetic artifact constraints.
- Provides unified audit line for multi-channel posture review.

## 7) Reviewer Checklist
- [ ] DM/video/document stages all executed.
- [ ] Evidence lines for each domain are present in result summary.
- [ ] Any warning is justified and reviewed.
- [ ] Unknown/unverified environment branch use is intentional.
- [ ] Final result is consistent with domain evidence completeness.


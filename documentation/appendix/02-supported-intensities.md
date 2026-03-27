# Appendix 02 — Supported Intensities

This appendix explains the common intensity levels used across the test documents.

## `quick`
**Plain-language meaning:**
A shorter/faster run for rapid checks.

**Security-review meaning:**
- Best for smoke validation and fast feedback
- May not assert all optional deep evidence paths in some scenarios
- Should not be the only basis for high-confidence sign-off

## `standard`
**Plain-language meaning:**
Balanced run depth and runtime; the default level for most reviews.

**Security-review meaning:**
- Intended primary operating intensity for routine security review
- Captures typical evidence set for pass/unknown/fail outcomes
- Good tradeoff between coverage and execution time

## `exhaustive`
**Plain-language meaning:**
Deeper run with expanded execution coverage.

**Security-review meaning:**
- Prefer when validating difficult edge cases or release-critical reviews
- Higher confidence due to broader path coverage
- Usually longer runtime and larger artifact/log output

---

## How to use this appendix during review
- Use test docs for scenario-specific expected behavior.
- Use this appendix to choose evidence depth appropriate for the decision being made.

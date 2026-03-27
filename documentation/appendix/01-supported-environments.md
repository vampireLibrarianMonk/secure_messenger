# Appendix 01 — Supported Environments

This appendix explains the common environment labels used in test documentation.

## `local sandbox`
**Plain-language meaning:**
A safe local test setup on developer/admin infrastructure where behavior can be observed quickly.

**Security-review meaning:**
- Highest test controllability
- Lowest external dependency variance
- Best baseline for reproducibility and triage

## `staging simulator`
**Plain-language meaning:**
A pre-production-like synthetic environment that behaves closer to operational deployment.

**Security-review meaning:**
- Better representation of realistic integration behavior
- Useful for validating policy/gating behavior before production
- May include additional system interactions not present in local-only runs

## `reconnect simulation`
**Plain-language meaning:**
An environment mode focused on interruption and recovery behavior (disconnect/reconnect).

**Security-review meaning:**
- Exercises state re-establishment and continuity paths
- Useful for validating that security assumptions hold across reconnect events
- Helps detect evidence gaps during session transitions

---

## How to use this appendix during review
- Use each test document for scenario-specific steps.
- Use this appendix to interpret what risk/context the selected environment introduces.

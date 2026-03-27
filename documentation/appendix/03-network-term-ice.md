# Appendix 03 — Network Term: ICE

## ICE (Interactive Connectivity Establishment)

**Plain-language meaning:**
ICE is the process a voice/video system uses to find a working network path between participants.

**Security-review meaning:**
- ICE gathers possible connection candidates (local/direct, reflexive, relay/TURN).
- ICE exchanges and tests candidate pairs to select a viable media path.
- Route choice (direct vs relay) affects network exposure, observability, and transport assumptions.

## Why ICE appears in test steps
When a test includes an `ice` step, it is validating/simulating connectivity discovery and path probing before secure transport is considered established.

## Related terms
- **Direct path:** peer-to-peer candidate path when reachable.
- **Relay path:** TURN-assisted path when direct connectivity is not viable.

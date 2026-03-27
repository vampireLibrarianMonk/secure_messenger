# 02 — Video E2EE Verification Test

## 1) Quick Summary (Layperson)
This test simulates a secure video call setup and media protection checks between two temporary users.
It validates transport security and (when conditions allow) app-layer media encryption confirmation.

## 2) Test Metadata
- **Test ID:** `video-e2ee`
- **Category:** `video`
- **Participants required:** 2
- **Supported environments:** `local sandbox`, `degraded relay environment`, `packet-loss simulation`
- **Supported intensities:** `quick`, `standard`, `exhaustive`
- **Environment definitions:** see [Appendix 01 — Supported Environments](./appendix/01-supported-environments.md)
- **Intensity definitions:** see [Appendix 02 — Supported Intensities](./appendix/02-supported-intensities.md)
- **ICE term definition:** see [Appendix 03 — Network Term: ICE](./appendix/03-network-term-ice.md)

## 3) Step-by-Step Flow (What Happens)
1. **signal** — signaling session is established.
2. **ice** — network path probing is simulated (see [Appendix 03 — ICE](./appendix/03-network-term-ice.md)).
3. **relay/direct** — route path is selected (direct or relay).
4. **dtls** — transport protection handshake stage is simulated.
5. **e2ee-check** — app-layer media encryption evidence stage is evaluated.

## 4) Expected Observability (Console + Logs)
- Event feed shows each step entering `active` then `completed`.
- Log flow shows synthetic video payload semantics:
  - `[video frame + signaling envelope #N]`
- Diagnostics indicate:
  - `candidate_pair_type` (direct/relay)
  - `turn_usage`
  - `transport_vs_app_layer`

## 5) Result Logic for Security Review
- **PASS — E2EE VERIFIED** when both transport protection and app-layer media E2EE evidence are confirmed.
- **PASS — TRANSPORT ONLY** when transport protection is confirmed but app-layer E2EE evidence is not confirmed.
- **UNKNOWN / UNVERIFIED** if evidence is incomplete, warnings exist requiring manual review, or unknown branch is selected.
- **FAIL** if failure branch is injected.

Important nuance:
- In `quick` intensity, app-layer E2EE confirmation may not be asserted by design, which can lead to transport-only outcome even without failure.

## 6) Security-Relevant Assertions
- Transport protection stage (`dtls`) is explicit in flow.
- App-layer E2EE check is separated from transport security to avoid false equivalence.
- Relay/direct behavior is observable for path risk analysis.

## 7) Reviewer Checklist
- [ ] Signal/ICE/path selection stages execute in order (ICE definition: [Appendix 03](./appendix/03-network-term-ice.md)).
- [ ] Transport protection evidence is present.
- [ ] App-layer E2EE evidence is correctly classified (or explicitly absent).
- [ ] Warning count aligns with anomaly toggles.
- [ ] Final classification reflects evidence and environment branch.


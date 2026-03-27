# Stage 3 — Logging Design + Threat Modeling Rework (Privacy-Preserving)

This stage validates admin-only APIs for two required deliverables from:

- `requirements_mds/ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS.md`

with emphasis on Sections **9** and **10**:

- Logging design field classification (allowed/hashed/redacted/forbidden)
- Threat modeling entries mapped to DM/video/both flows

## Scope clarification: what Stage 3 is (and is not)

Stage 3 is the **logging + threat-model data layer and API scaffolding**.

It is not yet full automated report composition. It adds structured artifacts that feed later consolidated reporting.

Stage 3 adds:

1. **Logging policy rows** (`SecurityLoggingFieldPolicy`)
2. **Threat model rows** (`SecurityThreatModelItem`)
3. **Admin-only CRUD endpoints** for both datasets

Stage 3 reinforces the no-content-read constraint: these APIs store analysis metadata only (no plaintext DM/media payloads).

---

## What was implemented in Stage 3

- New models in `backend/messenger/models.py`:
  - `SecurityLoggingFieldPolicy`
  - `SecurityThreatModelItem`
- New migration:
  - `backend/messenger/migrations/0003_stage3_logging_and_threat_models.py`
- New serializers in `backend/messenger/serializers.py`:
  - `SecurityLoggingFieldPolicySerializer`
  - `SecurityThreatModelItemSerializer`
- New admin-only API endpoints in `backend/messenger/views.py` + `backend/messenger/urls.py`:
  - `GET/POST /api/admin/security/logging-policies/`
  - `GET/POST /api/admin/security/threat-model/`
- Added Django admin registrations in `backend/messenger/admin.py`.

---

## 1) Build updated backend image

```bash
docker build -t secure-messenger-backend:stage3 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run backend with bootstrap admin enabled

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage3 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  secure-messenger-backend:stage3
```

## 3) Login and export admin token

```bash
export ACCESS_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$BOOTSTRAP_ADMIN_USERNAME\",\"password\":\"$BOOTSTRAP_ADMIN_PASSWORD\"}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')
```

## 4) Create a report and export `REPORT_ID`

```bash
export REPORT_ID=$(curl -s -X POST http://127.0.0.1:8000/api/admin/security/reports/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "title": "Stage 3 logging + threat model",
    "flow_type": "both",
    "status": "draft"
  }' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 5) Add logging policy rows

```bash
curl -s -X POST http://127.0.0.1:8000/api/admin/security/logging-policies/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"field_name\": \"message_body\",
    \"classification\": \"forbidden\",
    \"rationale\": \"Never log plaintext content.\"
  }"
```

Recommended baseline fields to classify in this stage:

- `correlation_id` → allowed
- `session_id` → tokenized/hashed
- `message_id` → allowed
- `room_id` → allowed
- `sender_id` / `recipient_id` → tokenized/hashed
- `device_id` → tokenized/hashed
- `encryption_state` → allowed
- `auth_state` → allowed
- `transport_path_chosen` → allowed
- `turn_relay_used` → allowed
- `message_body` / `media_payload` / `plaintext_attachment` → forbidden

Example additional row (metadata allowed with minimization):

```bash
curl -s -X POST http://127.0.0.1:8000/api/admin/security/logging-policies/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"field_name\": \"message_id\",
    \"classification\": \"allowed\",
    \"rationale\": \"Needed for correlation and delivery tracing.\"
  }"
```

## 6) Add threat model rows

```bash
curl -s -X POST http://127.0.0.1:8000/api/admin/security/threat-model/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"flow_type\": \"dm\",
    \"threat\": \"Passive network attacker\",
    \"affected_stages\": \"Transport initiation, API transit\",
    \"likely_indicators\": \"Certificate warnings, traffic anomalies\",
    \"controls\": \"TLS hardening, cert monitoring, pinning where feasible\",
    \"residual_risk\": \"Compromised endpoint still leaks plaintext\",
    \"severity\": \"high\"
  }"
```

Also add entries for required threat set:

- active MITM
- malicious insider
- compromised client endpoint
- stolen token/session
- replay attacks
- impersonation
- metadata leakage
- notification leakage
- backup leakage
- logging leakage

## 7) Verify list/filter behavior

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/logging-policies/?report=$REPORT_ID"

curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/threat-model/?report=$REPORT_ID&flow_type=dm"
```

Expected:

- Logging policy rows for the selected report are returned.
- Threat rows are filterable by report and flow type.
- Each threat row contains affected stages, indicators, controls, and residual risk.

## 8) Negative authz check (non-admin)

```bash
curl -i http://127.0.0.1:8000/api/admin/security/logging-policies/ \
  -H "Authorization: Bearer <NON_ADMIN_TOKEN>"
```

Expected:

- HTTP 403 Forbidden

## Cleanup

```bash
docker rm -f sm-backend-stage3
```

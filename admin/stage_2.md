# Stage 2 — Security Journey Data Model + Admin API Scaffolding Verification

This stage validates that admin-only APIs exist for building the security journey analysis artifacts:

- Security journey reports
- Stage-by-stage journey entries (DM/video)
- Security verification matrix items

## Scope clarification: what Stage 2 is (and is not)

Stage 2 is **not only** a reports phase.

Stage 2 is the **data-model + admin API scaffolding phase** for the security-analysis capability, and includes three artifact layers:

1. **Reports** (`SecurityJourneyReport`)
   - Top-level analysis container for a DM/video/both assessment.
2. **Journey stages** (`SecurityJourneyStage`)
   - Per-step lifecycle breakdown entries (e.g., auth, encryption, transport, delivery).
3. **Verification matrix items** (`SecurityVerificationMatrixItem`)
   - Stage-linked evidence/testing rows (expected property, test method, pass/fail criteria, remediation).

So reports are only one part of Stage 2; this stage establishes the full structured backend foundation used by later stages.

## What was implemented in Stage 2

- New models:
  - `SecurityJourneyReport`
  - `SecurityJourneyStage`
  - `SecurityVerificationMatrixItem`
- New migration:
  - `backend/messenger/migrations/0002_security_journey_models.py`
- Admin-only API endpoints (JWT + `IsSecurityAdmin`):
  - `GET/POST /api/admin/security/reports/`
  - `GET/POST /api/admin/security/stages/`
  - `GET/POST /api/admin/security/verification-matrix/`

## 1) Build updated backend image

```bash
docker build -t secure-messenger-backend:stage2 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run backend with bootstrap admin enabled

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage2 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  secure-messenger-backend:stage2
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
    "title": "DM + Video exploratory review",
    "flow_type": "both",
    "status": "draft",
    "executive_summary": "Initial exploratory draft.",
    "reality_check_answers": {"is_e2ee": "unknown"}
  }' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 5) Add a DM stage entry

```bash
export STAGE_ID=$(curl -s -X POST http://127.0.0.1:8000/api/admin/security/stages/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"flow_type\": \"dm\",
    \"stage_number\": 1,
    \"stage_name\": \"User authenticated\",
    \"component\": \"Auth API\",
    \"protocol\": \"HTTPS\",
    \"security_assumptions\": \"JWT validation and TLS are correctly configured.\",
    \"severity_if_compromised\": \"high\"
  }" | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 6) Add a verification matrix item

```bash
curl -s -X POST http://127.0.0.1:8000/api/admin/security/verification-matrix/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"stage\": $STAGE_ID,
    \"stage_label\": \"DM-1\",
    \"expected_security_property\": \"Only authenticated users can submit messages.\",
    \"evidence_source\": \"Auth middleware logs\",
    \"how_to_test\": \"Attempt unauthenticated POST /api/messages/\",
    \"pass_fail_criteria\": \"Must return 401/403\",
    \"common_misconfiguration\": \"AllowAny accidentally applied\",
    \"recommended_remediation\": \"Restore IsAuthenticated and add regression tests\"
  }"
```

## 7) Verify list/filter behavior

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/stages/?report=$REPORT_ID&flow_type=dm"
```

Expected:

- Returns at least one stage with the created `report` and `flow_type=dm`.

## 8) Negative authz check (non-admin)

Login with non-admin user and call:

```bash
curl -i http://127.0.0.1:8000/api/admin/security/reports/ \
  -H "Authorization: Bearer <NON_ADMIN_TOKEN>"
```

Expected:

- HTTP 403 Forbidden

## Cleanup

```bash
docker rm -f sm-backend-stage2
```

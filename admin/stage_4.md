# Stage 4 — Consolidated Report Rework + Mandatory Reality Checks

This stage reworks compiled output to align with:

- `requirements_mds/ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS.md`

It validates final assembly of the analysis outputs into one compiled response matching required report structure and mandatory reality-check questions.

## Scope clarification: what Stage 4 is (and is not)

Stage 4 is the **compiled-output and final-section scaffolding phase**.

It adds:

1. **Top security gaps dataset**
2. **Highest-value next tests dataset**
3. **Compiled report endpoint** that aggregates all Stage 2/3/4 artifacts into one response

Plus:

4. **Scope coverage section** inclusion
5. **Mandatory reality-check key normalization** with `unknown/unverified` defaults where evidence is missing

This is still structured backend scaffolding, not automatic security reasoning over live traffic.

---

## What was implemented in Stage 4

- New models in `backend/messenger/models.py`:
  - `SecurityGapItem`
  - `SecurityNextTestItem`
- New migration:
  - `backend/messenger/migrations/0004_stage4_gaps_and_next_tests.py`
- New serializers:
  - `SecurityGapItemSerializer`
  - `SecurityNextTestItemSerializer`
- New admin-only endpoints:
  - `GET/POST /api/admin/security/gaps/`
  - `GET/POST /api/admin/security/next-tests/`
- Added report compilation endpoint:
  - `GET /api/admin/security/reports/{id}/compiled/`

Compiled response includes:

- executive summary
- DM stage-by-stage journey
- video stage-by-stage journey
- verification matrix
- scope coverage
- logging design
- top 10 likely security gaps
- highest value next tests
- threat model
- reality check answers

Reality check answer keys are normalized to:

- `is_system_truly_e2ee_or_transport_only`
- `can_server_read_dm_bodies`
- `can_server_read_media`
- `can_push_notifications_leak_sensitive_content`
- `can_logs_backups_analytics_or_moderation_expose_plaintext`
- `can_admins_or_cloud_operators_access_secrets_or_session_data`
- `proof_required_before_claiming_secure`

---

## 1) Build updated backend image

```bash
docker build -t secure-messenger-backend:stage4 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run backend with bootstrap admin enabled

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage4 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  secure-messenger-backend:stage4
```

## 3) Login and export admin token

```bash
export ACCESS_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$BOOTSTRAP_ADMIN_USERNAME\",\"password\":\"$BOOTSTRAP_ADMIN_PASSWORD\"}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')
```

## 4) Create report and export `REPORT_ID`

```bash
export REPORT_ID=$(curl -s -X POST http://127.0.0.1:8000/api/admin/security/reports/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "title": "Stage 4 consolidated report",
    "flow_type": "both",
    "status": "draft",
    "executive_summary": "Initial consolidated output",
    "reality_check_answers": {"is_true_e2ee": "unknown"}
  }' | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 5) Add gap + next test rows

```bash
curl -s -X POST http://127.0.0.1:8000/api/admin/security/gaps/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"rank\": 1,
    \"title\": \"Potential metadata leakage through notifications\",
    \"severity\": \"high\",
    \"recommended_remediation\": \"Minimize push payloads and redact sensitive fields\"
  }"

curl -s -X POST http://127.0.0.1:8000/api/admin/security/next-tests/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{
    \"report\": $REPORT_ID,
    \"priority\": \"high\",
    \"name\": \"Push payload leakage test\",
    \"scope\": \"dm,video\",
    \"method\": \"Inspect payloads across provider pipelines\",
    \"pass_fail_criteria\": \"No plaintext content or secrets\"
  }"
```

## 6) Get compiled report payload

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/reports/$REPORT_ID/compiled/"
```

Expected top-level keys:

- `executive_summary`
- `dm_stage_by_stage_journey`
- `video_stage_by_stage_journey`
- `verification_matrix`
- `scope_coverage`
- `logging_design`
- `top_10_likely_security_gaps`
- `highest_value_next_tests`
- `threat_model`
- `reality_check_answers`

## 7) Negative authz check

```bash
curl -i "http://127.0.0.1:8000/api/admin/security/reports/$REPORT_ID/compiled/" \
  -H "Authorization: Bearer <NON_ADMIN_TOKEN>"
```

Expected:

- HTTP 403 Forbidden

## Cleanup

```bash
docker rm -f sm-backend-stage4
```

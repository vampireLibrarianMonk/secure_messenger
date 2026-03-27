# Stage 5 — Audit Trail + Run Trigger + Retention Safeguards Rework

This stage is reworked against:

- `requirements_mds/ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS.md`

and validates operational safeguards required for admin security analysis artifacts:

- auditable access to compiled/exported analysis output
- auditable triggering of analysis runs in no-content-read mode
- retention-bound cleanup of aged analysis artifacts

## Scope clarification: what Stage 5 is (and is not)

Stage 5 is the **auditability + retention-controls phase**.

It adds:

1. **Security analysis audit events** for compiled report access/export actions
2. **Security run trigger endpoint** that records no-content-read analysis invocation
3. **Admin audit event visibility endpoint**
4. **Retention purge management command** to remove aged analysis artifacts

This stage does not add plaintext content access and preserves metadata-only admin workflows.

---

## What was implemented in Stage 5

- New model in `backend/messenger/models.py`:
  - `SecurityAnalysisAuditEvent`
- New migration:
  - `backend/messenger/migrations/0005_stage5_audit_events.py`
- New serializer:
  - `SecurityAnalysisAuditEventSerializer`
- New admin-only endpoint:
  - `GET /api/admin/security/audit-events/`
- New admin-only run endpoint:
  - `POST /api/admin/security/run/`
  - emits `run_triggered` audit events and returns `no_content_read_mode=true`
- Enhanced report actions:
  - `GET /api/admin/security/reports/{id}/compiled/` now emits `compiled_view` audit events
  - `GET /api/admin/security/reports/{id}/export/` emits `export` audit events
- New retention command:
  - `python manage.py purge_security_analysis_artifacts`
  - retention controlled by `SECURITY_ANALYSIS_RETENTION_DAYS` (default: 90)

---

## 1) Build updated backend image

```bash
docker build -t secure-messenger-backend:stage5 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run backend with bootstrap admin enabled

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage5 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  -e SECURITY_ANALYSIS_RETENTION_DAYS=90 \
  secure-messenger-backend:stage5
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
  -d '{"title":"Stage 5 audit check","flow_type":"both","status":"draft"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 5) Trigger compiled/export events

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/reports/$REPORT_ID/compiled/" > /dev/null

curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/reports/$REPORT_ID/export/" > /dev/null
```

## 6) Verify audit log visibility

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/audit-events/?report=$REPORT_ID"
```

Expected:

- Includes events with `action` values:
  - `compiled_view`
  - `export`

## 7) Trigger security analysis run (no-content-read)

```bash
curl -i -X POST "http://127.0.0.1:8000/api/admin/security/run/" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"report_id\":$REPORT_ID,\"requested_checks\":[\"dm\",\"video\",\"logging\"]}"
```

Expected:

- HTTP 202 Accepted
- JSON includes `"no_content_read_mode": true`
- audit events include `action=run_triggered`

## 8) Negative authz check

```bash
curl -i "http://127.0.0.1:8000/api/admin/security/audit-events/" \
  -H "Authorization: Bearer <NON_ADMIN_TOKEN>"
```

Expected:

- HTTP 403 Forbidden

## 9) Run retention purge command

```bash
docker exec sm-backend-stage5 python manage.py purge_security_analysis_artifacts
```

Expected:

- Command prints purge summary (reports deleted, audit events deleted, cutoff).
- A new `retention_purge` audit event is recorded.

## Cleanup

```bash
docker rm -f sm-backend-stage5
```

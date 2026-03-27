# Stage 6 — Snapshot & Attestation Rework (Evidence Integrity + No-Content Constraints)

This stage is reworked against:

- `requirements_mds/ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS.md`

and validates snapshot capture for compiled analysis evidence, with digest-based integrity tracking and admin-only access.

## Scope clarification: what Stage 6 is (and is not)

Stage 6 is the **snapshot + integrity-attestation phase**.

It adds:

1. Structured report snapshots derived from compiled output
2. SHA-256 digest for each snapshot payload
3. Snapshot create/list APIs for admin security roles
4. Audit emission for snapshot creation

This does not claim cryptographic non-repudiation. It provides operational integrity evidence (content hash + immutable event trail) for security-analysis artifacts.

---

## What was implemented in Stage 6

- Extended audit action choices with `snapshot_create`
- New model in `backend/messenger/models.py`:
  - `SecurityReportSnapshot`
- New migration:
  - `backend/messenger/migrations/0006_stage6_report_snapshots.py`
- New serializer:
  - `SecurityReportSnapshotSerializer`
- New report action:
  - `POST /api/admin/security/reports/{id}/snapshots/`
  - Generates compiled payload, computes SHA-256, stores snapshot, emits `snapshot_create` audit event
- New admin-only snapshot endpoint:
  - `GET /api/admin/security/snapshots/`
  - Supports `?report=<id>` filtering
- Added Django admin registration for `SecurityReportSnapshot`

### Requirement mapping

- Section 13 (output structure): snapshot payload captures compiled report sections as generated.
- Section 14 (access safeguards): snapshot endpoints remain admin-gated and auditable.
- Section 16 (defensible proof paths): SHA-256 digest enables repeatable artifact integrity checks.

---

## 1) Build updated backend image

```bash
docker build -t secure-messenger-backend:stage6 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run backend with bootstrap admin enabled

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage6 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  secure-messenger-backend:stage6
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
  -d '{"title":"Stage 6 snapshot check","flow_type":"both","status":"draft"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["id"])')
```

## 5) Create snapshot from compiled report

```bash
curl -s -X POST "http://127.0.0.1:8000/api/admin/security/reports/$REPORT_ID/snapshots/" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{"notes":"baseline release snapshot"}'
```

Expected:

- Response includes `payload_sha256` of length 64
- Snapshot includes `payload` section
- Snapshot creation emits `snapshot_create` audit event

## 6) Verify snapshot listing and audit event

```bash
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/snapshots/?report=$REPORT_ID"

curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/audit-events/?report=$REPORT_ID&action=snapshot_create"
```

Expected:

- Snapshot list returns at least one row for the report
- Audit list includes at least one `snapshot_create` event

## 7) Verify digest integrity manually

```bash
export SNAPSHOT_JSON=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/admin/security/snapshots/?report=$REPORT_ID")

echo "$SNAPSHOT_JSON" | python -c 'import sys,json,hashlib; arr=json.load(sys.stdin); s=arr[0]; payload=json.dumps(s["payload"], sort_keys=True, separators=(",",":")); print("stored:", s["payload_sha256"]); print("calc:", hashlib.sha256(payload.encode()).hexdigest())'
```

Expected:

- `stored` and `calc` digests match

## 8) Negative authz check

```bash
curl -i "http://127.0.0.1:8000/api/admin/security/snapshots/" \
  -H "Authorization: Bearer <NON_ADMIN_TOKEN>"
```

Expected:

- HTTP 403 Forbidden

## 9) No-content-read validation reminders

Before promoting a snapshot as evidence, verify:

- No decrypted DM content included in stage narratives
- No plaintext media payloads in any field
- Logging design includes forbidden classification for message/media content fields
- Any unknown/unverified claims remain explicitly marked in reality-check answers

## Cleanup

```bash
docker rm -f sm-backend-stage6
```

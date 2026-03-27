# Stage 1 — Docker Bootstrap + Access-Gate Rework (Mapped to ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS)

This stage is reworked against:

- `requirements_mds/ADMIN_SECURITY_JOURNEY_ANALYSIS_REQUIREMENTS.md`

and specifically covers Section **14** (access safeguards) + Section **15** (Docker admin bootstrap requirement).

## Stage 1 objective

Provide a deterministic, secure, auditable, idempotent first-admin bootstrap path that does **not** leak credentials and that enforces a first-login password reset before admin capability access.

## Implemented controls in this rework

1. **Bootstrap account state tracking**
   - `SecurityAdminAccountState` model stores:
     - `must_reset_password`
     - `bootstrap_source`
     - `last_bootstrap_at`
2. **Force-reset-on-first-login behavior**
   - Bootstrap marks admin accounts as `must_reset_password=True`
   - New endpoint: `POST /api/auth/password-reset/` clears that flag after successful password change
3. **Admin capability gate hardened**
   - `IsSecurityAdmin` now denies admin APIs if `must_reset_password=True`
4. **Bootstrap idempotency + safety policy**
   - If an admin already exists, bootstrap skips by default
   - Optional reconciliation requires explicit `BOOTSTRAP_ADMIN_ALLOW_RECONCILE=1`
5. **Bootstrap audit logging (without secret leakage)**
   - Structured bootstrap logs added via `security.bootstrap` logger
   - Password redaction filter applied in logging config
6. **Startup sequencing**
   - migrations run first, bootstrap runs before app start in `docker-entrypoint.sh`

## Prerequisites

- Docker running locally
- Repository available at `/home/flaniganp/Documents/secure_messenger`

## 1) Build backend image

```bash
docker build -t secure-messenger-backend:stage1 /home/flaniganp/Documents/secure_messenger/backend
```

## 2) Run container with bootstrap settings

```bash
export ADMIN_HEX_SUFFIX=$(python -c 'import secrets; print(secrets.token_hex(8))')
export BOOTSTRAP_ADMIN_USERNAME="secadmin-$ADMIN_HEX_SUFFIX"
export BOOTSTRAP_ADMIN_EMAIL="secadmin-$ADMIN_HEX_SUFFIX@example.com"
export BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_HEX_SUFFIX"

docker run -d --name sm-backend-stage1 -p 8000:8000 \
  -e BOOTSTRAP_ADMIN_ENABLED=1 \
  -e BOOTSTRAP_ADMIN_USERNAME="$BOOTSTRAP_ADMIN_USERNAME" \
  -e BOOTSTRAP_ADMIN_EMAIL="$BOOTSTRAP_ADMIN_EMAIL" \
  -e BOOTSTRAP_ADMIN_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" \
  -e BOOTSTRAP_ADMIN_GROUP=security_admin \
  secure-messenger-backend:stage1
```

## 3) Check startup logs

```bash
docker logs sm-backend-stage1 --tail 200
```

Expected:

- migration step executes
- admin bootstrap step executes
- app starts
- no plaintext password appears in logs

## 4) Verify admin bootstrap state (must reset password)

```bash
docker exec sm-backend-stage1 python manage.py shell -c "from django.contrib.auth.models import User; from messenger.models import SecurityAdminAccountState; u=User.objects.get(username='$BOOTSTRAP_ADMIN_USERNAME'); s=SecurityAdminAccountState.objects.get(user=u); print(u.username, u.is_superuser, u.is_staff, u.is_active, s.must_reset_password, s.bootstrap_source)"
```

Expected output pattern:

```text
<your-admin-username> True True True True docker_bootstrap
```

## 5) Verify idempotency on restart (no duplicate admin)

```bash
docker restart sm-backend-stage1
docker exec sm-backend-stage1 python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='$BOOTSTRAP_ADMIN_USERNAME').count())"
```

Expected output:

```text
1
```

## 6) Login with bootstrap credentials and verify admin endpoint is blocked until reset

```bash
export ACCESS_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$BOOTSTRAP_ADMIN_USERNAME\",\"password\":\"$BOOTSTRAP_ADMIN_PASSWORD\"}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')

curl -i http://127.0.0.1:8000/api/admin/security/status/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Expected:

- HTTP 403 (must reset password before admin security capability usage)

## 7) Reset password and re-check admin access

```bash
export NEW_BOOTSTRAP_ADMIN_PASSWORD="${ADMIN_HEX_SUFFIX}X!"

curl -i -X POST http://127.0.0.1:8000/api/auth/password-reset/ \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d "{\"old_password\":\"$BOOTSTRAP_ADMIN_PASSWORD\",\"new_password\":\"$NEW_BOOTSTRAP_ADMIN_PASSWORD\"}"

export ACCESS_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$BOOTSTRAP_ADMIN_USERNAME\",\"password\":\"$NEW_BOOTSTRAP_ADMIN_PASSWORD\"}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')

curl -i http://127.0.0.1:8000/api/admin/security/status/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Expected:

- password reset call returns HTTP 200
- admin security status now returns HTTP 200
- response contains `"admin_security_access": "ok"`

## 8) Negative authorization test (non-admin)

Use a non-admin user token against admin endpoint.

Expected:

- HTTP 403 Forbidden

## 9) Existing-admin skip behavior check

Optional policy check for Section 15.1 (skip bootstrap when admin exists):

```bash
docker exec sm-backend-stage1 env BOOTSTRAP_ADMIN_ENABLED=1 \
  BOOTSTRAP_ADMIN_USERNAME=another-admin \
  BOOTSTRAP_ADMIN_EMAIL=another-admin@example.com \
  BOOTSTRAP_ADMIN_PASSWORD=AnotherPass123! \
  BOOTSTRAP_ADMIN_ALLOW_RECONCILE=0 \
  python manage.py bootstrap_admin
```

Expected:

- command logs skip behavior (existing admin)
- no new admin user is created

## Cleanup

```bash
docker rm -f sm-backend-stage1
```

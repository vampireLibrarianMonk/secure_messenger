# Stage 1 — Docker Admin Bootstrap Verification Directions

This stage validates that backend startup can securely bootstrap an admin user and enforce admin-only access checks.

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
- app starts
- no plaintext password appears in logs

## 4) Verify admin user properties

```bash
docker exec sm-backend-stage1 python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(username='$BOOTSTRAP_ADMIN_USERNAME'); print(u.username, u.is_superuser, u.is_staff, u.is_active)"
```

Expected output pattern:

```text
<your-admin-username> True True True
```

## 5) Verify idempotency on restart

```bash
docker restart sm-backend-stage1
docker exec sm-backend-stage1 python manage.py shell -c "from django.contrib.auth.models import User; print(User.objects.filter(username='$BOOTSTRAP_ADMIN_USERNAME').count())"
```

Expected output:

```text
1
```

## 6) Login as bootstrap admin and export JWT env var

```bash
export ACCESS_TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$BOOTSTRAP_ADMIN_USERNAME\",\"password\":\"$BOOTSTRAP_ADMIN_PASSWORD\"}" \
  | python -c 'import sys,json; print(json.load(sys.stdin)["access"])')
```

## 7) Verify admin-only endpoint

```bash
curl -i http://127.0.0.1:8000/api/admin/security/status/ \
  -H "Authorization: Bearer $ACCESS_TOKEN"
```

Expected:

- HTTP 200 for admin token
- JSON includes `"admin_security_access": "ok"`

## 8) Negative authorization test

Use a non-admin user token against the same endpoint.

Expected:

- HTTP 403 Forbidden

## Cleanup

```bash
docker rm -f sm-backend-stage1
```

# Secure Messenger

Secure Messenger is a privacy-first messaging app with encrypted chat, encrypted file sharing, and WebRTC video calling.

- **Backend:** Django + DRF + Channels (ASGI)
- **Frontend:** Vue 3 + Vite + TypeScript + Pinia
- **Security model:** client-side encryption/decryption via WebCrypto; server stores ciphertext and encrypted file blobs.

## Current Features

- JWT auth (register/login/refresh/logout/me)
- Conversation creation and membership management
- Real-time chat via WebSockets
- Client-side encrypted text messages
- Client-side encrypted file upload + receiver-side decrypt/download
- Session lock controls (manual lock, inactivity timeout, local key wipe)
- WebRTC video calls with websocket signaling
- Video diagnostics (signaling test, local loopback, camera/mic test)
- Simplified video UI (start/join/end controls + collapsible debug tools)
- Distinct outgoing/incoming call ring sounds
- Admin Secure Test Lab (synthetic/faux execution) with:
  - role/environment/feature-flag gating
  - scenario run + connection console simulation
  - evidence-based result classes (`PASS — E2EE VERIFIED`, `PASS — TRANSPORT ONLY`, `FAIL`, `UNKNOWN / UNVERIFIED`)
  - persisted run artifact review (`/api/test-lab/runs/`) with no-plaintext/secret-field guardrails
  - diagnostics workspace for security admin/test-user roles (flag-gated)
  - warning/failure injection toggles, replay/re-run, and run outcome comparison basics
  - feature-flagged group behavior scenarios

## Project Structure

- `backend/` – Django API + Channels websocket service
- `frontend/` – Vue app

## Run with Docker (Recommended)

This is the easiest way to run frontend/backend in isolated containers.

### 1) Build images

From project root:

```bash
docker build -t secure-messenger-backend:latest /home/flaniganp/Documents/secure_messenger/backend

docker build \
  --build-arg VITE_API_BASE=http://localhost:8000/api \
  --build-arg VITE_WS_BASE=ws://localhost:8000 \
  -t secure-messenger-frontend:latest \
  /home/flaniganp/Documents/secure_messenger/frontend
```

### 2) Create an isolated app network

```bash
docker network create secure-messenger-net
```

If it already exists, Docker will return an error; that is safe to ignore.

### 3) Run backend container

Generate a secure admin bootstrap password (16 hex chars) and export it for this shell session:

```bash
export TEST_LAB_ADMIN_PASSWORD=$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')
```

```bash
docker run -d \
  --name secure-messenger-backend \
  --network secure-messenger-net \
  -p 8000:8000 \
  -e DJANGO_DEBUG=1 \
  -e TEST_LAB_ENV=local \
  -e TEST_LAB_ALLOWED_ENVIRONMENTS=local,sandbox,staging \
  -e TEST_LAB_TEST_MENU_ENABLED=1 \
  -e TEST_LAB_SYNTHETIC_SCENARIOS_ENABLED=1 \
  -e TEST_LAB_VERBOSE_DIAGNOSTICS_ENABLED=1 \
  -e TEST_LAB_GROUP_TESTING_ENABLED=1 \
  -e TEST_LAB_ADMIN_USERNAMES=lab_admin \
  -e TEST_LAB_TEST_USER_USERNAMES=test_user_alpha,test_user_beta,test_user_gamma \
  -e TEST_LAB_ADMIN_USERNAME=lab_admin \
  -e TEST_LAB_ADMIN_EMAIL=lab_admin@example.com \
  -e TEST_LAB_ADMIN_PASSWORD="$TEST_LAB_ADMIN_PASSWORD" \
  secure-messenger-backend:latest \
  /bin/sh -c "python manage.py migrate && python manage.py bootstrap_single_admin && python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application"
```

This startup command is idempotent and enforces the single-admin bootstrap policy:

- applies migrations
- creates exactly one active admin if none exists
- refuses creation if a different second admin is requested

### 4) Run frontend container

```bash
docker run -d \
  --name secure-messenger-frontend \
  --network secure-messenger-net \
  -p 5175:80 \
  secure-messenger-frontend:latest
```

Open:

- Frontend: `http://127.0.0.1:5175`
- Backend API: `http://127.0.0.1:8000/api`

### 5) Run backend checks/tests inside the backend container

Per your workflow preference, run checks/tests in container context:

```bash
# Django system checks
docker exec -it secure-messenger-backend python manage.py check

# Run migrations
docker exec -it secure-messenger-backend python manage.py migrate

# Run test suite
docker exec -it secure-messenger-backend python manage.py test
```

### 6) Optional PostgreSQL + Redis containers

If you enable these, use named volumes so data survives normal image/container cleanup:

```bash
docker volume create sm_pgdata
docker volume create sm_redisdata

docker run -d \
  --name sm-postgres \
  --network secure-messenger-net \
  -e POSTGRES_DB=secure_messenger \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -v sm_pgdata:/var/lib/postgresql/data \
  postgres:16

docker run -d \
  --name sm-redis \
  --network secure-messenger-net \
  -v sm_redisdata:/data \
  redis:7-alpine
```

Then run backend with full env wiring to Postgres + Redis:

```bash
# Replace the default backend container (if running)
docker rm -f secure-messenger-backend 2>/dev/null || true

docker run -d \
  --name secure-messenger-backend \
  --network secure-messenger-net \
  -p 8000:8000 \
  -e DJANGO_DEBUG=1 \
  -e TEST_LAB_ENV=local \
  -e TEST_LAB_ALLOWED_ENVIRONMENTS=local,sandbox,staging \
  -e TEST_LAB_TEST_MENU_ENABLED=1 \
  -e TEST_LAB_SYNTHETIC_SCENARIOS_ENABLED=1 \
  -e TEST_LAB_VERBOSE_DIAGNOSTICS_ENABLED=1 \
  -e TEST_LAB_GROUP_TESTING_ENABLED=1 \
  -e TEST_LAB_ADMIN_USERNAMES=lab_admin \
  -e TEST_LAB_TEST_USER_USERNAMES=test_user_alpha,test_user_beta,test_user_gamma \
  -e TEST_LAB_ADMIN_USERNAME=lab_admin \
  -e TEST_LAB_ADMIN_EMAIL=lab_admin@example.com \
  -e TEST_LAB_ADMIN_PASSWORD="$TEST_LAB_ADMIN_PASSWORD" \
  -e USE_POSTGRES=1 \
  -e POSTGRES_DB=secure_messenger \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_HOST=sm-postgres \
  -e POSTGRES_PORT=5432 \
  -e USE_REDIS=1 \
  -e REDIS_URL=redis://sm-redis:6379/0 \
  secure-messenger-backend:latest \
  /bin/sh -c "python manage.py migrate && python manage.py bootstrap_single_admin && python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application"

# Optional sanity check
docker exec -i secure-messenger-backend python manage.py check
```

### 6b) Quick refresh (rebuild + restart backend/frontend)

Use this when you changed code and want both app containers refreshed while keeping Postgres/Redis running:

```bash
ADMIN_PASS=$(docker exec -i secure-messenger-backend /bin/sh -c 'printenv TEST_LAB_ADMIN_PASSWORD' 2>/dev/null || true) && docker build -t secure-messenger-backend:latest /home/flaniganp/Documents/secure_messenger/backend && docker build -t secure-messenger-frontend:latest /home/flaniganp/Documents/secure_messenger/frontend && docker rm -f secure-messenger-frontend secure-messenger-backend 2>/dev/null || true && docker run -d --name secure-messenger-backend --network secure-messenger-net -p 8000:8000 -e DJANGO_DEBUG=1 -e TEST_LAB_ENV=local -e TEST_LAB_ALLOWED_ENVIRONMENTS=local,sandbox,staging -e TEST_LAB_TEST_MENU_ENABLED=1 -e TEST_LAB_SYNTHETIC_SCENARIOS_ENABLED=1 -e TEST_LAB_VERBOSE_DIAGNOSTICS_ENABLED=1 -e TEST_LAB_GROUP_TESTING_ENABLED=1 -e TEST_LAB_ADMIN_USERNAMES=lab_admin -e TEST_LAB_TEST_USER_USERNAMES=test_user_alpha,test_user_beta,test_user_gamma -e TEST_LAB_ADMIN_USERNAME=lab_admin -e TEST_LAB_ADMIN_EMAIL=lab_admin@example.com -e TEST_LAB_ADMIN_PASSWORD="$ADMIN_PASS" -e USE_POSTGRES=1 -e POSTGRES_DB=secure_messenger -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_HOST=sm-postgres -e POSTGRES_PORT=5432 -e USE_REDIS=1 -e REDIS_URL=redis://sm-redis:6379/0 secure-messenger-backend:latest /bin/sh -c "python manage.py migrate && python manage.py bootstrap_single_admin && python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application" && docker run -d --name secure-messenger-frontend --network secure-messenger-net -p 5175:80 secure-messenger-frontend:latest
```

Then verify:

```bash
docker exec -i secure-messenger-backend python manage.py check
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

### 7) Stop and remove app containers

```bash
docker rm -f secure-messenger-frontend secure-messenger-backend sm-postgres sm-redis 2>/dev/null || true
```

### 8) Docker cleanup commands

Use these when you want a clean rebuild baseline.

```bash
# Remove app containers
docker rm -f secure-messenger-frontend secure-messenger-backend sm-postgres sm-redis 2>/dev/null || true

# Remove app images
docker rmi -f secure-messenger-frontend:latest secure-messenger-backend:latest 2>/dev/null || true

# Remove dangling build cache/layers
docker builder prune -af

# Optional: remove local app network
docker network rm secure-messenger-net 2>/dev/null || true
```

If you intentionally want to delete persisted database/cache data too:

```bash
# WARNING: deletes persisted Postgres/Redis data volumes
docker volume rm sm_pgdata sm_redisdata 2>/dev/null || true
```

> Note on pruning: `docker builder prune` and removing images/containers do **not** remove named volumes unless you explicitly prune volumes (for example with `docker volume prune` or `docker system prune --volumes`).

## Run Locally

> Important: run backend with an **ASGI server** (Daphne) so websocket/video signaling routes work.

### 1) Backend setup

```bash
cd backend
pip install -r requirements.txt
pip install daphne
python manage.py migrate
```

### 2) Start backend (ASGI + websockets)

```bash
cd backend
python -m daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

### 3) Frontend setup

```bash
cd frontend
npm install
```

### 4) Start frontend

From the **project root**:

```bash
VITE_API_BASE=http://127.0.0.1:8000/api VITE_WS_BASE=ws://127.0.0.1:8000 npm --prefix frontend run dev -- --host 127.0.0.1 --port 5175
```

Or if you are already inside `frontend/`:

```bash
VITE_API_BASE=http://127.0.0.1:8000/api VITE_WS_BASE=ws://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 5175
```

Open: `http://127.0.0.1:5175`

## Quick Validation Flow

1. Register/login two users in separate browser profiles.
2. Create/select a shared conversation.
3. Send encrypted messages both ways.
4. Upload a file from one side; verify receiver sees **Download ...** and can download.
5. Test video:
   - Caller presses **Start Call**
   - Receiver should see **Join Call** and incoming ring
   - Receiver presses **Join Call**
6. Use Video **Debug tools** for troubleshooting if needed.

## Optional Environment Notes

- `USE_POSTGRES=1` enables PostgreSQL settings (backend)
- `USE_REDIS=1` enables Redis channel layer (backend)
- `TEST_LAB_VERBOSE_DIAGNOSTICS_ENABLED=1` enables diagnostics tab for test-user/security-admin roles
- `TEST_LAB_GROUP_TESTING_ENABLED=1` enables group-behavior scenarios

## Admin Test Lab Scope Note

The Admin Test Lab currently runs **synthetic/faux simulations** for secure-communications scenarios. It provides governance controls, evidence-based classification, diagnostics, and artifact review workflows, but is not yet integrated with an external real execution harness.

## Security Note

This project is a practical secure-messaging prototype. Do not treat it as production-ready cryptographic software without independent security review and hardening.

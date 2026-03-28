# Secure Messenger on AWS EC2

This guide walks through deploying Secure Messenger on a single EC2 instance using Docker.

## Critical browser security requirement

For this app, **public EC2 browser access should be HTTPS-only**.

- `crypto.randomUUID()` and other Web Crypto features are available only in a **secure context**.
- `http://<public-ec2-ip>` is not a secure context, so the frontend can fail with errors like:
  - `TypeError: crypto.randomUUID is not a function`

Use a domain + TLS (`https://...`) for normal EC2 access.

## Architecture (EC2 path)

- One EC2 host runs:
  - backend container (Django + Daphne)
  - frontend container (Nginx static serving built Vue app)
- Optional: local Postgres/Redis containers on the same host.
- Optional: Nginx/Caddy reverse proxy + TLS certificates.

> This is a good starter path for low-to-medium traffic and simple operations.

---

## 1) Prerequisites

1. AWS account + IAM user/role permissions for EC2, VPC, and Security Groups.
2. AWS CLI configured locally.
3. SSH key pair created in AWS (`.pem` key available locally).
4. Route 53 domain/subdomains mapped to your EC2 Elastic IP (required for proper HTTPS browser access).

---

## 2) Create EC2 instance

Recommended baseline:

- AMI: Ubuntu 22.04 LTS
- Instance type guidance:
  - `t3.small`: acceptable for light dev/test usage
  - `t3.medium`: recommended starting point for small production-like workloads
  - scale up (e.g., `t3.large`) if you expect higher concurrency/video usage
- Storage: 30+ GB gp3
- Security Group inbound:
  - TCP 22 from your admin IP
  - TCP 80 from internet (or restricted CIDR)
  - TCP 443 from internet (or restricted CIDR)

Launch and connect:

```bash
ssh -i /path/to/your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

---

## 2b) Allocate Elastic IP + map Route 53 domain (basic)

Use this so your app has a stable public IP and domain that points directly to your EC2 host.

### A) Allocate and associate an Elastic IP

1. AWS Console -> **EC2** -> **Elastic IPs** -> **Allocate Elastic IP address**.
2. Select the new Elastic IP -> **Actions** -> **Associate Elastic IP address**.
3. Associate it to your running EC2 instance.

After this, your instance has a stable public IPv4 address.

### B) Create/Use a Route 53 hosted zone

1. AWS Console -> **Route 53** -> **Hosted zones**.
2. Create or open your hosted zone (example: `example.com`).
3. If newly created, update registrar name servers to Route 53 name servers.

### C) Create DNS records pointing to the Elastic IP

Create A records (example):

- `app.example.com` -> `<ELASTIC_IP>`
- `api.example.com` -> `<ELASTIC_IP>`

You can do this via Route 53 console (Record type **A**, Value = Elastic IP).

### D) Validate DNS resolution

From your machine:

```bash
dig +short app.example.com
dig +short api.example.com
```

Expected: both return your Elastic IP.

---

## 3) Install Docker on EC2

On the EC2 host:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Log out/in once after group change.

---

## 4) Copy project and build images

Option A (recommended): clone directly on EC2.

```bash
git clone <YOUR_REPO_URL>.git
cd secure-chat
```

Build backend image:

```bash
docker build -t secure-chat-backend:latest ./backend
```

Build frontend image (set production API/WS URLs):

```bash
docker build \
  --build-arg VITE_API_BASE=https://secure-chat.my-deployment.com/api \
  --build-arg VITE_WS_BASE=wss://secure-chat.my-deployment.com \
  --build-arg VITE_ICE_SERVERS='[{"urls":["stun:stun.l.google.com:19302"]}]' \
  -t secure-chat-frontend:latest \
  ./frontend
```

If callers are on different networks and calls fail to connect after "Join", add TURN in `VITE_ICE_SERVERS` and rebuild frontend.

---

## 5) Start backend/frontend containers

Create network:

```bash
docker network create secure-chat-net || true
docker volume create sm_media
```

Generate secrets (example):

```bash
export DJANGO_SECRET_KEY=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
export TEST_LAB_ADMIN_PASSWORD=$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')
```

Run backend:

```bash
docker run -d \
  --name secure-chat-backend \
  --network secure-chat-net \
  -p 8000:8000 \
  --restart unless-stopped \
  -v sm_media:/app/media \
  -e DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \
  -e DJANGO_DEBUG=0 \
  -e DJANGO_ALLOWED_HOSTS="secure-chat.my-deployment.com,<EC2_PUBLIC_IP>" \
  -e CORS_ALLOWED_ORIGINS="https://secure-chat.my-deployment.com" \
  -e TEST_LAB_ADMIN_USERNAME=lab_admin \
  -e TEST_LAB_ADMIN_EMAIL=lab_admin@example.com \
  -e TEST_LAB_ADMIN_PASSWORD="$TEST_LAB_ADMIN_PASSWORD" \
  secure-chat-backend:latest \
  /bin/sh -c "python manage.py migrate && python manage.py bootstrap_single_admin && python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application"
```

Run frontend:

```bash
docker run -d \
  --name secure-chat-frontend \
  --network secure-chat-net \
  -p 8080:80 \
  --restart unless-stopped \
  secure-chat-frontend:latest
```

> Use this direct frontend port only for container-level checks. For real browser usage, terminate TLS and access via `https://...`.

### 5b) Create users via CLI (UI registration is disabled)

Create users directly inside the backend container:

```bash
docker exec -i secure-chat-backend python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_user(username='user_a', email='user_a@example.com', password='ChangeMe123_')"
docker exec -i secure-chat-backend python manage.py shell -c "from django.contrib.auth.models import User; User.objects.create_user(username='user_b', email='user_b@example.com', password='ChangeMe123_')"
```

---

## 6) Optional: run Postgres and Redis containers

Postgres/Redis are optional for this project path. You can register/login users without them (SQLite + default in-memory channel layer).

```bash
docker volume create sm_pgdata
docker volume create sm_redisdata

docker run -d \
  --name sm-postgres \
  --network secure-chat-net \
  -e POSTGRES_DB=secure_messenger \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD='<STRONG_DB_PASSWORD>' \
  -v sm_pgdata:/var/lib/postgresql/data \
  postgres:16

docker run -d \
  --name sm-redis \
  --network secure-chat-net \
  -v sm_redisdata:/data \
  redis:7-alpine
```

Then restart backend with:

- `USE_POSTGRES=1`, `POSTGRES_*` pointing to `sm-postgres`
- `USE_REDIS=1`, `REDIS_URL=redis://sm-redis:6379/0`

---

## 7) HTTPS and domain (required for browser usage)

Place a reverse proxy (Nginx/Caddy) in front of containers and terminate TLS with valid certificates.

Typical DNS mapping:

- `app.example.com` -> frontend
- `api.example.com` -> backend

Keep backend private to host network where possible; expose only proxy ports 80/443 publicly.

### Quick Caddy example (automatic Let's Encrypt)

Create/update `Caddyfile`:

```caddy
secure-chat.my-deployment.com {
  @api path /api/* /ws/*

  reverse_proxy @api secure-chat-backend:8000

  handle_path /media/* {
    root * /srv
    file_server
  }

  reverse_proxy secure-chat-frontend:80
}
```

This Caddy setup assumes Caddy runs on the same Docker network as backend/frontend (`secure-chat-net`).

Why `handle_path /media/*`? In this deployment, backend commonly runs with `DJANGO_DEBUG=0`, and Django does not serve media URLs by default in that mode. Serving `/media/*` from the shared Docker volume avoids attachment 404s.

Command form (recommended) to update the file directly on EC2:

```bash
cat > Caddyfile <<'EOF'
secure-chat.my-deployment.com {
  @api path /api/* /ws/*

  reverse_proxy @api secure-chat-backend:8000

  handle_path /media/* {
    root * /srv
    file_server
  }

  reverse_proxy secure-chat-frontend:80
}
EOF
```

Run Caddy:

```bash
docker rm -f sm-caddy 2>/dev/null || true

docker run -d \
  --name sm-caddy \
  --network secure-chat-net \
  --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v $PWD/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy_data:/data \
  -v caddy_config:/config \
  -v sm_media:/srv:ro \
  caddy:2
```

Before opening the website, verify Caddy and app upstreams are healthy:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker logs --tail 80 sm-caddy
curl -I https://secure-chat.my-deployment.com/
curl -i https://secure-chat.my-deployment.com/api/
```

Expected:

- Caddy container is `Up`
- `/` returns `200`
- `/api/` returns app response (often `401` when unauthenticated)

Then access only:

- `https://secure-chat.my-deployment.com`

> Ensure EC2 security group allows inbound TCP `80` and `443`, otherwise Let's Encrypt validation will fail.

---

## 8) Validation checklist

On EC2:

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker logs --tail 100 secure-chat-backend
docker exec -i secure-chat-backend python manage.py check
```

From browser:

1. Open frontend URL over HTTPS (`https://secure-chat.my-deployment.com`).
2. Login two pre-provisioned users.
3. Verify encrypted messaging and file exchange.
4. Verify websocket connectivity and video call flow.

Quick CLI validation:

```bash
curl -I https://secure-chat.my-deployment.com/
curl -i https://secure-chat.my-deployment.com/api/
```

Expected:

- `/` returns `200`
- `/api/` may return `401` when unauthenticated (this is healthy)

### 8b) Real-time call + file preflight checks (recommended)

Before user testing, verify these specifics:

```bash
# backend must mount the shared media volume used by Caddy
docker inspect secure-chat-backend --format '{{json .Mounts}}'

# Caddy must mount the same volume read-only for /media serving
docker inspect sm-caddy --format '{{json .Mounts}}'
```

Expected: backend has `sm_media -> /app/media` and Caddy has `sm_media -> /srv`.

Then in the app UI:

1. Open a conversation.
2. Use **Video -> Debug tools -> Signaling Test** on both users.
3. Start call from User A, click **Join Call** on User B.
4. Upload a file from User A and download from User B.

If signaling test passes but call does not connect, that usually means NAT traversal needs TURN (not just STUN).

---

## 9) Troubleshooting quick hits

- **Frontend cannot reach backend:** verify `VITE_API_BASE`/`VITE_WS_BASE` were set at image build time.
- **`crypto.randomUUID is not a function`:** you're likely on insecure HTTP origin; switch to HTTPS domain access.
- **Caddy 502 `dial tcp 127.0.0.1:8080 connect: connection refused`:** Caddy is in a container; use Docker service names (`secure-chat-frontend:80`, `secure-chat-backend:8000`) and attach Caddy to `secure-chat-net`.
- **Let's Encrypt `Timeout during connect (likely firewall problem)`:** open EC2 security group inbound TCP `80` and `443`.
- **Attachment download `404` with files present in `/app/media/attachments`:** Caddy must serve `/media/*` from `sm_media` (mounted read-only to `/srv`), or Django must be explicitly configured to serve media in production.
- **Attachment upload appears but receiver gets 404:** ensure backend is started with `-v sm_media:/app/media` and Caddy with `-v sm_media:/srv:ro` (same volume name).
- **Attachment uploaded before media volume was mounted:** old files may be unrecoverable after container restart; upload a new file after `sm_media` is in place.
- **Caller can start but receiver cannot complete call join:** verify `VITE_WS_BASE=wss://secure-chat.my-deployment.com`, run in-app **Signaling Test**, and add TURN servers via `VITE_ICE_SERVERS` for cross-network NAT traversal.
- **Calls still fail after config changes:** frontend env is baked at image build time; rebuild frontend with `--no-cache` and restart the frontend container.
- **Video call audio is loud/garbled:** test both participants on the same browser family first (Firefox↔Firefox or Chrome↔Chrome). Mixed browser stacks can produce unstable behavior with current runtime media transform behavior in this prototype.
- **400 bad host / CORS errors:** check `DJANGO_ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS`.
- **Websocket issues:** ensure reverse proxy forwards `Upgrade` and `Connection` headers.
- **Container restarts:** inspect logs and confirm migrations/bootstrap command success.

---

## 9b) Internet exposure and security hardening (important)

Do you need EC2 reachable from the internet? For this architecture, **yes, but minimally**:

- Keep only `80/443` publicly open (required for HTTPS app access and certificate issuance).
- Keep `22` restricted to your admin IP only (or prefer AWS SSM Session Manager and close `22`).

Recommended hardening baseline:

1. Security group inbound:
   - `80/tcp` from `0.0.0.0/0`
   - `443/tcp` from `0.0.0.0/0`
   - `22/tcp` from **your IP only** (or disabled when using SSM)
2. Never expose backend container port `8000` publicly in SG.
3. Keep app access via Caddy only (`80/443`).
4. Enable automatic security updates on the host.
5. Use strong secrets and rotate credentials regularly.
6. Add CloudWatch/host monitoring + fail2ban/rate limiting as needed.
7. Consider AWS WAF/CloudFront in front of the app for additional protection.

---

## 9c) Lessons learned runbook (document download + call join)

Use this exact sequence after deployment changes:

```bash
# 1) Verify expected container mounts
docker inspect secure-chat-backend --format '{{json .Mounts}}'
docker inspect sm-caddy --format '{{json .Mounts}}'

# 2) Verify HTTPS/API health before UI tests
curl -I https://secure-chat.my-deployment.com/
curl -i https://secure-chat.my-deployment.com/api/

# 3) Rebuild frontend whenever VITE_* changes (WS/ICE vars are build-time)
docker build --no-cache \
  --build-arg VITE_API_BASE=https://secure-chat.my-deployment.com/api \
  --build-arg VITE_WS_BASE=wss://secure-chat.my-deployment.com \
  --build-arg VITE_ICE_SERVERS='[{"urls":["stun:stun.l.google.com:19302"]}]' \
  -t secure-chat-frontend:latest \
  ./frontend

docker rm -f secure-chat-frontend
docker run -d --name secure-chat-frontend --network secure-chat-net -p 8080:80 --restart unless-stopped secure-chat-frontend:latest
```

Then validate in UI (in order):

1. Run **Video -> Debug tools -> Signaling Test** on both accounts.
2. Start call on user A, click **Join Call** on user B.
3. Upload a **new** file and verify receiver can download/open it.

---

## 10) Docker cleanup and reset (start fresh)

Use this section to fully reset the EC2 deployment and rebuild from scratch.

### Stop and remove running containers

```bash
docker rm -f secure-chat-frontend secure-chat-backend secure-messenger-frontend secure-messenger-backend sm-postgres sm-redis sm-caddy 2>/dev/null || true
```

### Remove app images

```bash
docker rmi -f secure-chat-frontend:latest secure-chat-backend:latest caddy:2 2>/dev/null || true
```

### Remove app network

```bash
docker network rm secure-chat-net 2>/dev/null || true
```

### Remove persisted volumes (WARNING: deletes DB/cache/caddy data)

```bash
docker volume rm sm_pgdata sm_redisdata caddy_data caddy_config 2>/dev/null || true
```

### Remove dangling build cache

```bash
docker builder prune -af
```

### Full one-shot reset command

```bash
docker rm -f secure-chat-frontend secure-chat-backend secure-messenger-frontend secure-messenger-backend sm-postgres sm-redis sm-caddy 2>/dev/null || true && \
docker rmi -f secure-chat-frontend:latest secure-chat-backend:latest caddy:2 2>/dev/null || true && \
docker network rm secure-chat-net 2>/dev/null || true && \
docker volume rm sm_pgdata sm_redisdata caddy_data caddy_config 2>/dev/null || true && \
docker builder prune -af
```

If Docker still reports `Bind for 0.0.0.0:8000 failed: port is already allocated`, identify and remove the leftover container using port 8000 before restarting backend:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}' | grep 8000 || true
docker rm -f secure-chat-backend secure-messenger-backend 2>/dev/null || true
```

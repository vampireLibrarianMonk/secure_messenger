# Kubernetes Operations (Helm)

This document covers day-2 operations for deploying and managing Secure Messenger on k3s with Helm.

- Initial cluster setup: see [`README-SETUP.md`](./README-SETUP.md)
- Charts:
  - `./backend`
  - `./frontend`

---

## 1) Namespace and release naming

Examples in this guide use:

- Namespace: `secure-messenger`
- Backend release: `sm-backend`
- Frontend release: `sm-frontend`

Export helpers:

```bash
export NS=secure-messenger
export BACKEND_RELEASE=sm-backend
export FRONTEND_RELEASE=sm-frontend
```

---

## 2) Install backend chart

### 2.1 Minimal install (chart-managed secret)

The backend chart supports:

- non-secret env vars under `env`
- secret env vars under `secretEnv`
- optional externally managed secret via `existingSecretName`
- migration hook job enabled by default (`migrationJob.enabled=true`)
- PVC-backed media mount at `/app/media`

Recommended baseline (Postgres + Redis + strict hosts/CORS):

```bash
helm upgrade --install "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --set image.repository=secure-messenger-backend \
  --set image.tag=local \
  --set env.POSTGRES_HOST=postgres-postgresql \
  --set env.REDIS_URL=redis://redis-master:6379/0 \
  --set env.DJANGO_ALLOWED_HOSTS="api.secure-messenger.local" \
  --set env.CORS_ALLOWED_ORIGINS="https://secure-messenger.local" \
  --set secretEnv.DJANGO_SECRET_KEY="replace-with-strong-key" \
  --set secretEnv.POSTGRES_PASSWORD="replace-with-db-password"
```

Install with secure overrides:

```bash
helm upgrade --install "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --set image.repository=secure-messenger-backend \
  --set image.tag=local \
  --set env.DJANGO_ALLOWED_HOSTS="api.secure-messenger.local" \
  --set env.CORS_ALLOWED_ORIGINS="https://secure-messenger.local" \
  --set secretEnv.DJANGO_SECRET_KEY="replace-with-strong-key" \
  --set secretEnv.POSTGRES_PASSWORD="replace-with-db-password"
```

### 2.2 Install using an existing Kubernetes secret

Create secret once:

```bash
kubectl -n "$NS" create secret generic sm-backend-env \
  --from-literal=DJANGO_SECRET_KEY='replace-with-strong-key' \
  --from-literal=POSTGRES_PASSWORD='replace-with-db-password'
```

Install chart referencing that secret:

```bash
helm upgrade --install "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --set image.repository=secure-messenger-backend \
  --set image.tag=local \
  --set existingSecretName=sm-backend-env
```

---

## 3) Install frontend chart

```bash
helm upgrade --install "$FRONTEND_RELEASE" ./kubernetes/frontend \
  -n "$NS" \
  --set image.repository=secure-messenger-frontend \
  --set image.tag=local
```

> Note: frontend Vite env vars are build-time (`VITE_*`) and are baked into the image during `docker build`.

### 3.1 Build frontend image with production API/WS/ICE values

```bash
docker build -t secure-messenger-frontend:local ./frontend \
  --build-arg VITE_API_BASE=https://api.secure-messenger.local/api \
  --build-arg VITE_WS_BASE=wss://api.secure-messenger.local \
  --build-arg VITE_ICE_SERVERS='[{"urls":["stun:stun.l.google.com:19302"]}]'
```

For restricted NAT environments, include TURN in `VITE_ICE_SERVERS`, e.g.:

```json
[
  {"urls": ["stun:stun.l.google.com:19302"]},
  {
    "urls": ["turn:turn.example.com:3478"],
    "username": "turn-user",
    "credential": "turn-password"
  }
]
```

---

## 4) Ingress + TLS

Enable ingress per chart:

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=api.secure-messenger.local \
  --set ingress.tls[0].hosts[0]=api.secure-messenger.local \
  --set ingress.tls[0].secretName=api-secure-messenger-tls

helm upgrade "$FRONTEND_RELEASE" ./kubernetes/frontend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=secure-messenger.local \
  --set ingress.tls[0].hosts[0]=secure-messenger.local \
  --set ingress.tls[0].secretName=secure-messenger-tls
```

---

## 5) Verify deployment health

```bash
helm list -n "$NS"
kubectl -n "$NS" get deploy,po,svc
kubectl -n "$NS" get ingress
kubectl -n "$NS" rollout status deploy/"$BACKEND_RELEASE"-secure-messenger-backend
kubectl -n "$NS" rollout status deploy/"$FRONTEND_RELEASE"-secure-messenger-frontend
```

Tail logs:

```bash
kubectl -n "$NS" logs deploy/"$BACKEND_RELEASE"-secure-messenger-backend -f
kubectl -n "$NS" logs deploy/"$FRONTEND_RELEASE"-secure-messenger-frontend -f
```

---

## 6) Updating env vars and secrets

### 6.1 Update regular (non-secret) env vars

Example: turn on Redis and point to a different host.

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set env.USE_REDIS="1" \
  --set env.REDIS_URL="redis://redis-master:6379/0"
```

### 6.2 Update chart-managed secret values

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set secretEnv.DJANGO_SECRET_KEY="new-strong-key" \
  --set secretEnv.POSTGRES_PASSWORD="new-db-password"
```

### 6.3 Update externally managed secret values

If `existingSecretName` is used, update secret directly and restart deployment:

```bash
kubectl -n "$NS" create secret generic sm-backend-env \
  --from-literal=DJANGO_SECRET_KEY='new-strong-key' \
  --from-literal=POSTGRES_PASSWORD='new-db-password' \
  -o yaml --dry-run=client | kubectl apply -f -

kubectl -n "$NS" rollout restart deploy/"$BACKEND_RELEASE"-secure-messenger-backend
```

### 6.4 Control migration job behavior

The backend chart runs migrations as a Helm hook Job by default. Disable if needed:

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set migrationJob.enabled=false
```

---

## 7) Port forwarding for local access

Frontend:

```bash
kubectl -n "$NS" port-forward svc/"$FRONTEND_RELEASE"-secure-messenger-frontend 5175:80
```

Backend:

```bash
kubectl -n "$NS" port-forward svc/"$BACKEND_RELEASE"-secure-messenger-backend 8000:8000
```

Then open:

- Frontend: `http://127.0.0.1:5175`
- Backend API base: `http://127.0.0.1:8000/api`

---

## 8) Upgrade charts and images

Rebuild/reimport images (from repo root):

```bash
docker build -t secure-messenger-backend:local ./backend
docker build -t secure-messenger-frontend:local ./frontend

docker save secure-messenger-backend:local -o /tmp/secure-messenger-backend-local.tar
docker save secure-messenger-frontend:local -o /tmp/secure-messenger-frontend-local.tar

sudo k3s ctr images import /tmp/secure-messenger-backend-local.tar
sudo k3s ctr images import /tmp/secure-messenger-frontend-local.tar
```

Apply chart upgrades:

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend -n "$NS" --reuse-values
helm upgrade "$FRONTEND_RELEASE" ./kubernetes/frontend -n "$NS" --reuse-values
```

---

## 9) Uninstall

Remove releases:

```bash
helm uninstall "$FRONTEND_RELEASE" -n "$NS"
helm uninstall "$BACKEND_RELEASE" -n "$NS"
```

Optional cleanup:

```bash
kubectl delete namespace "$NS"
```

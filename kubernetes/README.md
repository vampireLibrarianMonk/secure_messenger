# Kubernetes Operations (Helm) — Day 2 Operations

This document is the **Day 2 operations guide** for deploying and managing Secure Messenger on k3s with Helm.

## Day 1 vs Day 2 terminology

- **Day 1 operations**: first-time provisioning/bootstrap work to get a fresh environment ready (cluster install, base dependencies, initial deploy readiness).
- **Day 2 operations**: ongoing lifecycle work after bootstrap (upgrades, scaling, troubleshooting, config changes, routine ops).

- Initial cluster setup: see [`README-SETUP.md`](./README-SETUP.md)
- Charts:
  - `./backend`
  - `./frontend`

## Scope of this file

- **Use this file for ongoing operations** after first-time cluster bootstrap.
- **Do not use this file as the first-time setup guide**; use [`README-SETUP.md`](./README-SETUP.md) for that.

## After reboot quick check (Day 2)

If you reboot your machine, quickly verify k3s is running before normal operations:

```bash
sudo systemctl status k3s --no-pager
kubectl get nodes
```

If k3s is not running:

```bash
sudo systemctl start k3s
```

If `kubectl` is not installed globally, use:

```bash
sudo k3s kubectl get nodes
```

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
export INGRESS_CLASS=traefik
```

> For ingress-nginx users, set `INGRESS_CLASS=nginx`.

---

## 2) Standard operations

### 2.1 Install backend chart

#### Minimal install (chart-managed secret)

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

#### Install using an existing Kubernetes secret

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

### 2.2 Install frontend chart

```bash
helm upgrade --install "$FRONTEND_RELEASE" ./kubernetes/frontend \
  -n "$NS" \
  --set image.repository=secure-messenger-frontend \
  --set image.tag=local
```

> Note: frontend Vite env vars are build-time (`VITE_*`) and are baked into the image during `docker build`.

#### Build frontend image with production API/WS/ICE values

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

### 2.3 Verify deployment health

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

If Helm is not installed yet:

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

---

### 2.4 Port forwarding for local access

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

### 2.5 Upgrade charts and images

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

### 2.6 Uninstall

Remove releases:

```bash
helm uninstall "$FRONTEND_RELEASE" -n "$NS"
helm uninstall "$BACKEND_RELEASE" -n "$NS"
```

Optional cleanup:

```bash
kubectl delete namespace "$NS"
```

---

## 3) Cleanup (Optional)

Use this section to clean temporary local artifacts after image build/import work.

Remove exported image tar files:

```bash
rm -f /tmp/secure-messenger-backend-local.tar
rm -f /tmp/secure-messenger-frontend-local.tar
```

If you also want to remove deployed cluster resources, use **2.6 Uninstall** above.

---

## 4) Advanced operations

### 4.1 Ingress + TLS

Enable ingress per chart:

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.className="$INGRESS_CLASS" \
  --set ingress.hosts[0].host=api.secure-messenger.local \
  --set ingress.tls[0].hosts[0]=api.secure-messenger.local \
  --set ingress.tls[0].secretName=api-secure-messenger-tls

helm upgrade "$FRONTEND_RELEASE" ./kubernetes/frontend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.className="$INGRESS_CLASS" \
  --set ingress.hosts[0].host=secure-messenger.local \
  --set ingress.tls[0].hosts[0]=secure-messenger.local \
  --set ingress.tls[0].secretName=secure-messenger-tls
```

---

### 4.2 Updating env vars and secrets

#### Update regular (non-secret) env vars

Example: turn on Redis and point to a different host.

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set env.USE_REDIS="1" \
  --set env.REDIS_URL="redis://redis-master:6379/0"
```

#### Update chart-managed secret values

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set secretEnv.DJANGO_SECRET_KEY="new-strong-key" \
  --set secretEnv.POSTGRES_PASSWORD="new-db-password"
```

#### Update externally managed secret values

If `existingSecretName` is used, update secret directly and restart deployment:

```bash
kubectl -n "$NS" create secret generic sm-backend-env \
  --from-literal=DJANGO_SECRET_KEY='new-strong-key' \
  --from-literal=POSTGRES_PASSWORD='new-db-password' \
  -o yaml --dry-run=client | kubectl apply -f -

kubectl -n "$NS" rollout restart deploy/"$BACKEND_RELEASE"-secure-messenger-backend
```

#### Control migration job behavior

The backend chart runs migrations as a Helm hook Job by default. Disable if needed:

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set migrationJob.enabled=false
```

---

## 5) Next steps: access from another LAN computer (example: `10.0.0.77` -> `10.0.0.43`)

Use this when k3s is running on server `10.0.0.43` and another computer on the same network (`10.0.0.77`) needs to open the app.

### 5.0 Determine ingress exposure mode first (k3s)

Set namespace helper and inspect ingress controller service:

```bash
export INGRESS_NS=${INGRESS_NS:-kube-system}
kubectl -n "$INGRESS_NS" get svc
```

- **Traefik default on k3s:** often reachable on node IP ports `80/443`.
- **ingress-nginx NodePort mode:** use the controller NodePort (example `31121`) for HTTPS.

If using ingress-nginx and unsure of HTTPS NodePort:

```bash
kubectl -n ingress-nginx get svc ingress-nginx-controller \
  -o jsonpath='{.spec.ports[?(@.port==443)].nodePort}'
```

Set this once for commands below:

```bash
export INGRESS_HTTPS_PORT=443   # e.g. set to 31121 for ingress-nginx NodePort
```

### 5.1 Important for video calls

For browser camera/mic + WebRTC reliability across computers, use **HTTPS/WSS** (secure context). HTTP may work for basic API tests but commonly fails for media permissions on non-localhost origins.

### 5.2 Recommended LAN setup (Ingress + hostnames)

1) Pick LAN hostnames (example):

- Frontend: `secure-messenger.lan`
- Backend API/WS: `api.secure-messenger.lan`

2) Create a self-signed TLS cert secret (quick LAN testing):

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /tmp/secure-messenger-lan.key \
  -out /tmp/secure-messenger-lan.crt \
  -subj "/CN=secure-messenger.lan" \
  -addext "subjectAltName=DNS:secure-messenger.lan,DNS:api.secure-messenger.lan"

kubectl -n "$NS" create secret tls secure-messenger-lan-tls \
  --cert=/tmp/secure-messenger-lan.crt \
  --key=/tmp/secure-messenger-lan.key \
  --dry-run=client -o yaml | kubectl apply -f -
```

3) Build frontend image with those public URLs:

```bash
docker build -t secure-messenger-frontend:local ./frontend \
  --build-arg VITE_API_BASE=https://api.secure-messenger.lan:${INGRESS_HTTPS_PORT}/api \
  --build-arg VITE_WS_BASE=wss://api.secure-messenger.lan:${INGRESS_HTTPS_PORT} \
  --build-arg VITE_ICE_SERVERS='[{"urls":["stun:stun.l.google.com:19302"]}]'

docker save secure-messenger-frontend:local -o /tmp/secure-messenger-frontend-local.tar
sudo k3s ctr images import /tmp/secure-messenger-frontend-local.tar
helm upgrade "$FRONTEND_RELEASE" ./kubernetes/frontend -n "$NS" --reuse-values
kubectl -n "$NS" rollout restart deploy/"$FRONTEND_RELEASE"-secure-messenger-frontend
kubectl -n "$NS" rollout status deploy/"$FRONTEND_RELEASE"-secure-messenger-frontend --timeout=180s
```

4) Ensure backend allows those hosts/origins:

> Use `--set-string` and escape commas in `DJANGO_ALLOWED_HOSTS` to avoid Helm parse errors.

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend \
  -n "$NS" \
  --reuse-values \
  --set-string env.DJANGO_ALLOWED_HOSTS=api.secure-messenger.lan\,10.0.0.43\,127.0.0.1 \
  --set-string env.CORS_ALLOWED_ORIGINS=https://secure-messenger.lan:${INGRESS_HTTPS_PORT}
```

5) Enable ingress for both charts:

> Include explicit `pathType` (and frontend `/` path) so ingress manifests stay valid.

```bash
helm upgrade "$BACKEND_RELEASE" ./kubernetes/backend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.className="$INGRESS_CLASS" \
  --set ingress.hosts[0].host=api.secure-messenger.lan \
  --set ingress.hosts[0].paths[0].path=/api \
  --set ingress.hosts[0].paths[0].pathType=Prefix \
  --set ingress.hosts[0].paths[1].path=/ws \
  --set ingress.hosts[0].paths[1].pathType=Prefix \
  --set ingress.tls[0].hosts[0]=api.secure-messenger.lan \
  --set ingress.tls[0].secretName=secure-messenger-lan-tls

helm upgrade "$FRONTEND_RELEASE" ./kubernetes/frontend -n "$NS" --reuse-values \
  --set ingress.enabled=true \
  --set ingress.className="$INGRESS_CLASS" \
  --set ingress.hosts[0].host=secure-messenger.lan \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix \
  --set ingress.tls[0].hosts[0]=secure-messenger.lan \
  --set ingress.tls[0].secretName=secure-messenger-lan-tls
```

6) On **both** server (`10.0.0.43`) and client (`10.0.0.77`), map hostnames in hosts file:

```text
10.0.0.43 secure-messenger.lan
10.0.0.43 api.secure-messenger.lan
```

Quick append command (Linux/macOS):

```bash
echo '10.0.0.43 secure-messenger.lan api.secure-messenger.lan' | sudo tee -a /etc/hosts
```

Windows (run Command Prompt as Administrator):

```cmd
echo 10.0.0.43 secure-messenger.lan api.secure-messenger.lan>>C:\Windows\System32\drivers\etc\hosts
```

Verify:

```bash
getent hosts secure-messenger.lan api.secure-messenger.lan
```

After hosts changes, flush DNS cache:

- Linux (systemd-resolved):

```bash
sudo resolvectl flush-caches
```

- Windows (Administrator CMD):

```cmd
ipconfig /flushdns
```

7) Verify ingress exists and then open from browser:

```bash
kubectl -n "$NS" get ingress
```

```text
https://secure-messenger.lan:${INGRESS_HTTPS_PORT}
```

If `INGRESS_HTTPS_PORT=443`, you can use `https://secure-messenger.lan`.

### 5.3 TLS note for LAN

For real browser media tests between computers, configure TLS certs trusted by both machines (self-signed trust chain, internal CA, or other cert strategy) and set ingress TLS values as in **4.1 Ingress + TLS**.

### 5.4 Firewall/network checks

- Ensure client can reach server `10.0.0.43` on ingress ports (typically `80/443`).
- Ensure no host firewall blocks those ports.
- If calls connect but no media flows, add TURN to `VITE_ICE_SERVERS` (see section **2.2**).

### 5.5 Quick LAN smoke test checklist

Run these in order after applying section **5.2**.

1) **Server (`10.0.0.43`): verify ingress + app resources are up**

```bash
kubectl -n "$NS" get deploy,svc,ingress
kubectl -n "$NS" rollout status deploy/"$BACKEND_RELEASE"-secure-messenger-backend --timeout=180s
kubectl -n "$NS" rollout status deploy/"$FRONTEND_RELEASE"-secure-messenger-frontend --timeout=180s
```

Expected: deployments `successfully rolled out`, ingress hosts present.

2) **Client (`10.0.0.77`): verify name resolution to server IP**

```bash
getent hosts secure-messenger.lan api.secure-messenger.lan
```

Expected: both resolve to `10.0.0.43`.

3) **Client (`10.0.0.77`): verify backend API is reachable**

```bash
curl -k -I https://api.secure-messenger.lan:31121/api/
```

Expected: HTTP response (401 is acceptable without auth; it proves reachability).

If not using NodePort 31121, run with your chosen port:

```bash
curl -k -I https://api.secure-messenger.lan:${INGRESS_HTTPS_PORT}/api/
```

4) **Client (`10.0.0.77`): open frontend**

Open:

```text
https://secure-messenger.lan:${INGRESS_HTTPS_PORT}
```

Expected: app loads without network errors in browser console.

5) **Cross-computer functional test**

- Login as user A on one machine and user B on the other.
- Create/open DM between those users.
- Send text both directions.
- Start/Join call and verify both local + remote media render.

Expected: DM messages deliver both directions; call transitions to connected/active.

6) **If DM works but media fails**

- Confirm browser has camera/mic permissions on both machines.
- Confirm secure context (`https://...`) is used, not `http://`.
- Add TURN entries to `VITE_ICE_SERVERS`, rebuild frontend image, redeploy (section **2.2** + **5.2**).

### 5.6 Lessons learned / common pitfalls

- If you see `Could not resolve host`, add `/etc/hosts` entries on the machine you are testing from (server and client).
- If Helm says `key "43" has no value`, your comma-separated `DJANGO_ALLOWED_HOSTS` was not escaped; use `--set-string ...\, ...\, ...`.
- If Helm says ingress `spec.rules[0].http.paths: Required value`, explicitly set frontend path `/` and `pathType=Prefix`.
- If release names look like `-secure-messenger-frontend`, your shell vars were empty; either export `NS/BACKEND_RELEASE/FRONTEND_RELEASE` first or use explicit names (`sm-backend`, `sm-frontend`).



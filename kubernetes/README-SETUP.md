# Kubernetes Setup (k3s) — Day 1 Bootstrap

This document is the **Day 1 bootstrap guide** for a local k3s environment.

## Day 1 vs Day 2 terminology

- **Day 1 operations**: first-time provisioning/bootstrap work to get a fresh environment ready (cluster install, base dependencies, initial deploy readiness).
- **Day 2 operations**: ongoing lifecycle work after bootstrap (upgrades, scaling, troubleshooting, config changes, routine ops).

- Use this document once (or rarely) to prepare cluster prerequisites.
- For ongoing operations after setup, use [`README.md`](./README.md).

## 1) Install k3s

On Linux:

```bash
curl -sfL https://get.k3s.io | sh -
```

Verify:

```bash
sudo k3s kubectl get nodes
```

You should see a node in `Ready` state.

### Ensure k3s starts on boot/reboot

k3s installs a systemd service (`k3s`) that should auto-start after reboot.

Verify it is enabled:

```bash
sudo systemctl is-enabled k3s
```

If needed, enable/start it:

```bash
sudo systemctl enable k3s
sudo systemctl start k3s
```

Check runtime status:

```bash
sudo systemctl status k3s --no-pager
```

## 2) Configure kubectl access

Use the k3s kubeconfig for your user shell:

```bash
mkdir -p /home/$USER/.kube
sudo cp /etc/rancher/k3s/k3s.yaml /home/$USER/.kube/config
sudo chown $USER:$USER /home/$USER/.kube/config
export KUBECONFIG=/home/$USER/.kube/config
```

Optional (persist for future shells):

```bash
echo 'export KUBECONFIG=/home/'"$USER"'/.kube/config' >> /home/$USER/.bashrc
```

## 3) Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
helm version
```

## 4) Create namespace for this app

```bash
kubectl create namespace secure-messenger
```

## 5) Install data-plane dependencies (Postgres + Redis)

The backend expects:

- **PostgreSQL** (`USE_POSTGRES=1`)
- **Redis channel layer** (`USE_REDIS=1`) for websocket fanout across replicas
- **Persistent media storage** via PVC mounted at `/app/media`

For local k3s, the simplest path is Bitnami charts:

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

helm upgrade --install postgres bitnami/postgresql \
  -n secure-messenger \
  --set auth.postgresPassword=postgres \
  --set auth.username=postgres \
  --set auth.password=postgres \
  --set auth.database=secure_messenger

helm upgrade --install redis bitnami/redis \
  -n secure-messenger \
  --set auth.enabled=false
```

These are the backend connection values created by the commands above:

- `POSTGRES_HOST=postgres-postgresql`
- `POSTGRES_PORT=5432`
- `REDIS_URL=redis://redis-master:6379/0`

> Important: these are **backend app env values** (for the Helm backend chart), not shell vars you must export globally.
> You should pass them with `helm --set env.*=...` (or in a values override file) when installing/upgrading the backend chart.
>
> Also, in `kubernetes/backend/values.yaml` the following are already enabled by default:
>
> - `USE_POSTGRES=1`
> - `USE_REDIS=1`
> - persistent media PVC mounted at `/app/media`

## 6) Build app images and import into k3s container runtime

From repo root:

```bash
docker build -t secure-messenger-backend:local ./backend

docker build -t secure-messenger-frontend:local ./frontend \
  --build-arg VITE_API_BASE=https://api.secure-messenger.local/api \
  --build-arg VITE_WS_BASE=wss://api.secure-messenger.local \
  --build-arg VITE_ICE_SERVERS='[{"urls":["stun:stun.l.google.com:19302"]}]'
```

Export and import into k3s container runtime:

```bash
docker save secure-messenger-backend:local -o /tmp/secure-messenger-backend-local.tar
docker save secure-messenger-frontend:local -o /tmp/secure-messenger-frontend-local.tar

sudo k3s ctr images import /tmp/secure-messenger-backend-local.tar
sudo k3s ctr images import /tmp/secure-messenger-frontend-local.tar
```

## 7) (Optional) Install nginx ingress controller

Install this if you plan to use ingress hosts/TLS now:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller
```

## 8) Initial app install smoke test

Install backend + frontend once to confirm the setup is functional.

> Note: `migrationJob.enabled=false` avoids pre-install hook ordering issues on first install.
> Run migrations manually after backend rollout.

Backend:

```bash
helm upgrade --install sm-backend ./kubernetes/backend \
  -n secure-messenger \
  --set migrationJob.enabled=false \
  --set image.repository=secure-messenger-backend \
  --set image.tag=local \
  --set env.POSTGRES_HOST=postgres-postgresql \
  --set env.POSTGRES_PORT=5432 \
  --set env.REDIS_URL=redis://redis-master:6379/0 \
  --set secretEnv.DJANGO_SECRET_KEY='replace-with-strong-key' \
  --set secretEnv.POSTGRES_PASSWORD='postgres'
```

```bash
kubectl -n secure-messenger rollout status deploy/sm-backend-secure-messenger-backend --timeout=180s
kubectl -n secure-messenger exec deploy/sm-backend-secure-messenger-backend -- python manage.py migrate --noinput
```

Frontend:

```bash
helm upgrade --install sm-frontend ./kubernetes/frontend \
  -n secure-messenger \
  --set image.repository=secure-messenger-frontend \
  --set image.tag=local \
  --set image.pullPolicy=IfNotPresent
```

## 9) Quick preflight checks

```bash
kubectl get ns
kubectl -n secure-messenger get all
helm lint ./kubernetes/backend
helm lint ./kubernetes/frontend
```

## 10) Cleanup (Optional)

If you want to remove bootstrap artifacts after setup:

```bash
rm -f /tmp/secure-messenger-backend-local.tar
rm -f /tmp/secure-messenger-frontend-local.tar
```

If you also want to remove deployed app resources, use the **cleanup/uninstall** sections in [`README.md`](./README.md).

When these checks pass, continue with [`README.md`](./README.md) for Day 2 operations.

# Kubernetes Setup (k3s)

This guide covers first-time setup of a local k3s cluster suitable for deploying the Secure Messenger Helm charts.

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

## 5) Install/prepare data plane dependencies

The backend is configured for:

- **PostgreSQL** (`USE_POSTGRES=1`)
- **Redis channel layer** (`USE_REDIS=1`) for websocket fanout across replicas
- **Persistent media storage** via PVC mounted at `/app/media`

For local k3s, the simplest path is to install Postgres + Redis via Helm:

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

Use these connection values for backend chart installs:

- `POSTGRES_HOST=postgres-postgresql`
- `POSTGRES_PORT=5432`
- `REDIS_URL=redis://redis-master:6379/0`

## 6) Build images and make them available to k3s

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

## 7) Install nginx ingress controller (if not already present)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller
```

## 8) Quick preflight checks

```bash
kubectl get ns
kubectl -n secure-messenger get all
helm lint ./kubernetes/backend
helm lint ./kubernetes/frontend
```

When these pass, continue with `kubernetes/README.md` for regular operations.

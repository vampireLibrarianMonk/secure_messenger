# Secure Messenger on AWS ECS

This guide covers deploying Secure Messenger to AWS ECS using ECR for images and an Application Load Balancer (ALB) for ingress.

## Architecture (ECS path)

- **ECR** stores backend and frontend container images.
- **ECS Cluster** runs services (Fargate recommended).
- **ALB** routes traffic:
  - frontend host/path -> frontend service
  - API/WS host/path -> backend service
- **CloudWatch Logs** captures container logs.
- **SSM Parameter Store / Secrets Manager** stores runtime secrets.

> This is the recommended path for scalable production-like operations.

---

## 1) Prerequisites

1. AWS account + IAM permissions for ECS, ECR, ALB, VPC, IAM roles, CloudWatch.
2. AWS CLI configured (`aws configure`) in your target region.
3. Docker installed locally.
4. Existing VPC with at least two public/private subnets across AZs.
5. ACM certificate (recommended) for your domain(s).

Environment helpers:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=<YOUR_ACCOUNT_ID>
export APP_NAME=secure-messenger
export ECR_BACKEND=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP_NAME-backend
export ECR_FRONTEND=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$APP_NAME-frontend
```

---

## 2) Create ECR repositories

```bash
aws ecr create-repository --repository-name $APP_NAME-backend --region $AWS_REGION
aws ecr create-repository --repository-name $APP_NAME-frontend --region $AWS_REGION
```

Authenticate Docker to ECR:

```bash
aws ecr get-login-password --region $AWS_REGION | \
docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

---

## 3) Build and push images

From repo root:

```bash
docker build -t $APP_NAME-backend:latest ./backend
docker tag $APP_NAME-backend:latest $ECR_BACKEND:latest
docker push $ECR_BACKEND:latest
```

Build frontend with production URL values:

```bash
docker build \
  --build-arg VITE_API_BASE=https://api.example.com/api \
  --build-arg VITE_WS_BASE=wss://api.example.com \
  -t $APP_NAME-frontend:latest \
  ./frontend

docker tag $APP_NAME-frontend:latest $ECR_FRONTEND:latest
docker push $ECR_FRONTEND:latest
```

---

## 4) Create ECS cluster

```bash
aws ecs create-cluster --cluster-name $APP_NAME-cluster --region $AWS_REGION
```

---

## 5) IAM roles for ECS tasks

You need:

- **Execution role** (pull image, write logs, read secrets if configured)
- **Task role** (app runtime permissions if needed)

Minimum baseline policies usually include:

- `AmazonECSTaskExecutionRolePolicy` attached to execution role.

---

## 6) Store secrets and runtime config

Example using SSM Parameter Store:

```bash
aws ssm put-parameter \
  --name /secure-messenger/prod/DJANGO_SECRET_KEY \
  --type SecureString \
  --value "<STRONG_SECRET_KEY>" \
  --overwrite \
  --region $AWS_REGION
```

Repeat for DB password and other sensitive values. Non-sensitive values can be plain task environment variables.

---

## 7) Register backend task definition

Create `backend-taskdef.json` (example skeleton):

```json
{
  "family": "secure-messenger-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/secureMessengerTaskRole",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "<ECR_BACKEND_IMAGE_URI>",
      "essential": true,
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "DJANGO_DEBUG", "value": "0" },
        { "name": "DJANGO_ALLOWED_HOSTS", "value": "api.example.com" },
        { "name": "CORS_ALLOWED_ORIGINS", "value": "https://app.example.com" }
      ],
      "secrets": [
        {
          "name": "DJANGO_SECRET_KEY",
          "valueFrom": "arn:aws:ssm:<REGION>:<ACCOUNT_ID>:parameter/secure-messenger/prod/DJANGO_SECRET_KEY"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/secure-messenger-backend",
          "awslogs-region": "<REGION>",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "command": [
        "/bin/sh",
        "-c",
        "python manage.py migrate && python manage.py bootstrap_single_admin && python -m daphne -b 0.0.0.0 -p 8000 config.asgi:application"
      ]
    }
  ]
}
```

Register:

```bash
aws ecs register-task-definition \
  --cli-input-json file://backend-taskdef.json \
  --region $AWS_REGION
```

---

## 8) Register frontend task definition

Create `frontend-taskdef.json` (same pattern) with container port `80` and frontend ECR image URI.

Register:

```bash
aws ecs register-task-definition \
  --cli-input-json file://frontend-taskdef.json \
  --region $AWS_REGION
```

---

## 9) Create ALB + target groups + listeners

Typical setup:

- One ALB
- One target group for backend (`:8000`)
- One target group for frontend (`:80`)
- HTTPS listener (443) with ACM certificate
- Listener rules route by host/path

Example routing strategy:

- `app.example.com` -> frontend target group
- `api.example.com` with `/api/*` and `/ws/*` -> backend target group

Ensure security groups allow ALB -> ECS task traffic on service ports.

---

## 10) Create ECS services

Create backend service (Fargate) linked to backend target group.

Create frontend service (Fargate) linked to frontend target group.

Key settings:

- Deployment type: rolling update
- Desired count: start with 1 each, scale later
- Health check grace period: set for backend startup/migrations
- Subnets/security groups aligned with your network model

---

## 11) Health checks and autoscaling

Recommended initial health checks:

- Backend target group: path `/api/` (or dedicated health endpoint if added)
- Frontend target group: path `/`

After baseline stability, enable ECS Service Auto Scaling for CPU/memory targets.

---

## 12) Validation checklist

1. ECS services show desired tasks as `RUNNING`.
2. ALB target groups show healthy targets.
3. Frontend URL loads successfully.
4. API endpoints reachable through `api.example.com`.
5. Websocket signaling works for chat/call flow.
6. CloudWatch logs show clean startup and request handling.

Useful commands:

```bash
aws ecs describe-services --cluster $APP_NAME-cluster --services secure-messenger-backend secure-messenger-frontend --region $AWS_REGION
aws logs tail /ecs/secure-messenger-backend --follow --region $AWS_REGION
aws logs tail /ecs/secure-messenger-frontend --follow --region $AWS_REGION
```

---

## 13) Troubleshooting quick hits

- **Tasks stop immediately:** check CloudWatch logs + task `stoppedReason`.
- **502/503 from ALB:** verify container port mappings and health check path.
- **CORS/host errors:** verify backend env values for allowed hosts/origins.
- **Frontend points to wrong API:** rebuild frontend image with correct `VITE_*` values.
- **Secrets not loading:** confirm execution role permissions for SSM/Secrets Manager ARNs.

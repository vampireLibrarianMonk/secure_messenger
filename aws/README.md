# AWS Deployment Guides

This folder contains AWS-focused deployment documentation for Secure Messenger.

## Documents in this folder

- [`EC2-SETUP.md`](./EC2-SETUP.md): deploy on a single EC2 instance using Docker.
- [`ECS-SETUP.md`](./ECS-SETUP.md): deploy on ECS (Fargate or EC2 launch type) with ECR + ALB.

## Which one should I use?

- Use **EC2** if you want the fastest single-host setup and full instance-level control.
- Use **ECS** if you want a more scalable, managed, production-style deployment pattern.

## Shared prerequisites

Before following either guide, make sure you have:

1. AWS account access with permissions for networking, compute, IAM, ECR, and logging.
2. AWS CLI configured (`aws configure`) for your target region.
3. Docker installed locally to build/push images.
4. This repository checked out locally.
5. Secure values prepared for:
   - `DJANGO_SECRET_KEY`
   - database credentials (if using Postgres)
   - any production CORS/host settings

## Important security note

Do not commit secrets into this repository. Use AWS Systems Manager Parameter Store or AWS Secrets Manager for sensitive runtime values.

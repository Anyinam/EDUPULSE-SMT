# GitHub Actions AWS Production Inputs

Use this file as the source of truth when populating the GitHub Actions `production` environment for EduPulse.

## Secret Handling Rule

Production secret values should live in AWS Secrets Manager, not in the repository and not in a committed `.env` file.

GitHub should only store:

- the AWS credentials needed to run the deployment workflow
- non-secret deployment variables
- AWS Secrets Manager ARNs that point to the real secret values

The ECS task definitions then pull the actual runtime secret values directly from AWS Secrets Manager at container start.

## GitHub Secrets

- `AWS_ACCESS_KEY_ID`: IAM access key for the deployment user or role broker.
- `AWS_SECRET_ACCESS_KEY`: matching secret access key.

## GitHub Variables

- `AWS_REGION`: AWS region, for example `us-east-1`.
- `PRODUCTION_URL`: external app URL. Use the hostname backed by your live ACM certificate, for example `https://edupulse.com.gh` or `https://app.edupulse.com.gh`.

### ECR

- `ECR_BACKEND_REPOSITORY`: backend ECR repository name.
- `ECR_FRONTEND_REPOSITORY`: frontend ECR repository name.

### ECS cluster and services

- `ECS_CLUSTER_NAME`: ECS cluster name.
- `ECS_APP_SERVICE`: ECS service name for the web app.
- `ECS_SCHEDULER_SERVICE`: ECS service name for the scheduler.
- `ECS_APP_TASK_FAMILY`: ECS task family for the app task.
- `ECS_SCHEDULER_TASK_FAMILY`: ECS task family for the scheduler task.
- `ECS_MIGRATION_TASK_FAMILY`: ECS task family for the migration task.
- `ECS_APP_CPU`: app task CPU units, default `1024`.
- `ECS_APP_MEMORY`: app task memory, default `2048`.
- `ECS_SCHEDULER_CPU`: scheduler task CPU units, default `512`.
- `ECS_SCHEDULER_MEMORY`: scheduler task memory, default `1024`.
- `ECS_MIGRATION_CPU`: migration task CPU units, default `512`.
- `ECS_MIGRATION_MEMORY`: migration task memory, default `1024`.
- `ECS_TASK_EXECUTION_ROLE_ARN`: task execution role ARN.
- `ECS_TASK_ROLE_ARN`: task role ARN.
- `ECS_SUBNET_IDS`: comma-separated subnet IDs for `awsvpcConfiguration`.
- `ECS_SECURITY_GROUP_IDS`: comma-separated security group IDs for one-off migration tasks.

### Domain and runtime

- `FRONTEND_ORIGIN`: main frontend origin, for example `https://app.edupulse.com.gh`.
- `CORS_ALLOWED_ORIGINS`: comma-separated browser origins allowed to call the API.
- `GUNICORN_WORKERS`: Gunicorn worker count, default `4`.

### Email and optional integrations

- `MAIL_SERVER`: SMTP server hostname.
- `MAIL_PORT`: SMTP port.
- `MAIL_USE_TLS`: `true` or `false`.
- `MAIL_USERNAME`: SMTP username.
- `MAIL_DEFAULT_SENDER`: visible sender address.
- `PLATFORM_OWNER_KEY_SECRET_ARN`: optional Secrets Manager ARN for the platform-owner API key.

### CloudWatch log groups

- `BACKEND_LOG_GROUP`: backend log group name.
- `FRONTEND_LOG_GROUP`: frontend log group name.
- `SCHEDULER_LOG_GROUP`: scheduler log group name.
- `MIGRATION_LOG_GROUP`: migration log group name.

### Secrets Manager ARNs

- `DATABASE_URL_SECRET_ARN`
- `SECRET_KEY_SECRET_ARN`
- `JWT_SECRET_KEY_SECRET_ARN`
- `DATA_ENCRYPTION_KEY_SECRET_ARN`
- `LEDGER_SECRET_KEY_SECRET_ARN`
- `BANK_WEBHOOK_SECRET_ARN`
- `PLATFORM_OWNER_KEY_SECRET_ARN`
- `MAIL_PASSWORD_SECRET_ARN`
- `PAYSTACK_SECRET_KEY_SECRET_ARN`
- `PAYSTACK_PUBLIC_KEY_SECRET_ARN`

## Recommended Population Order

1. Create the CloudFormation stack in `infra/aws/cloudformation/edupulse-ecs-platform.yml`.
2. Copy the stack outputs for cluster name, service names, ECR repos, and log groups.
3. Create AWS Secrets Manager secrets and copy their ARNs into the GitHub variables above.
4. Set GitHub `production` environment secrets and variables.
5. Trigger the `deploy-production` workflow on `main`.
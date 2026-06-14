# EduPulse AWS CloudFormation

This directory contains the infrastructure template that provisions the shared AWS platform for EduPulse production.

## What the stack creates

- ECS cluster with Container Insights enabled
- Two ECR repositories: backend and frontend
- CloudWatch log groups for app, frontend, scheduler, and migration tasks
- Internet-facing Application Load Balancer
- ACM certificate for `app` and `api` subdomains, or support for an existing certificate ARN
- Route53 alias records for the app and API domains
- ECS app service with both `edupulse-frontend` and `edupulse-backend` load-balanced containers
- ECS scheduler service without public exposure
- ALB and ECS security groups
- SNS topic and basic CloudWatch alarms

## Before you deploy

You must already have:

- a VPC with public and private subnets
- an RDS PostgreSQL database or other reachable PostgreSQL endpoint
- IAM task execution and task roles
- initial app and scheduler task definitions registered in ECS
- a Route53 hosted zone for your production domain

## Example deploy command

```bash
aws cloudformation deploy \
  --stack-name edupulse-production \
  --template-file infra/aws/cloudformation/edupulse-ecs-platform.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    EnvironmentName=production \
    VpcId=vpc-xxxxxxxx \
    PublicSubnetIds=subnet-a,subnet-b \
    PrivateSubnetIds=subnet-c,subnet-d \
    HostedZoneId=ZXXXXXXXXXXXXX \
    RootDomainName=edupulse.com.gh \
    AppTaskDefinitionArn=arn:aws:ecs:us-east-1:123456789012:task-definition/edupulse-app:1 \
    SchedulerTaskDefinitionArn=arn:aws:ecs:us-east-1:123456789012:task-definition/edupulse-scheduler:1 \
    EcsTaskExecutionRoleArn=arn:aws:iam::123456789012:role/edupulse-ecs-execution \
    EcsTaskRoleArn=arn:aws:iam::123456789012:role/edupulse-app-task
```

## After deploy

1. Read the stack outputs.
2. Populate GitHub Actions variables using `infra/aws/GITHUB_ACTIONS_VARIABLES.md`.
3. Push to `main` or run the `deploy-production` workflow manually.
# EduPulse AWS Cost Analysis & Reduction Plan (Revised)

> [!IMPORTANT]
> Target: **\$60–70/month**. All estimates use **us-east-1** on-demand pricing (Nov 2026). Actual costs depend on your exact region, task sizes, and traffic. ✅ Corrected: no NAT Gateway — both services use `AssignPublicIp: ENABLED`.

---

## ✅ Corrected Architecture Facts

| Item | Reality |
|---|---|
| **App Service** (`AppService`) | `AssignPublicIp: DISABLED` → runs in **private subnets** |
| **Scheduler Service** (`SchedulerService`) | `AssignPublicIp: ENABLED` → runs in **public subnets** |
| **NAT Gateway** | **You confirmed: none** ✅ |
| **App task default CPU/mem** | Workflow fallback: `512` CPU / `1024` MB |
| **Scheduler task default CPU/mem** | Workflow fallback: `256` CPU / `512` MB |
| **Secrets** | 11 secrets in Secrets Manager |
| **Log groups** | 4 groups, 7-day default retention |
| **ECR** | 2 repos, 5-image retention |
| **Scheduler desired count** | Defaults to `0` ✅ |

> [!WARNING]
> **Important:** `AppService` has `AssignPublicIp: DISABLED` and uses `PrivateSubnetIds`. Without a NAT Gateway, this task **cannot reach the internet** (ECR image pulls, Secrets Manager, SES, Paystack). It must be relying on **VPC Interface Endpoints** or be misconfigured. Check this — if it's actually working, you have VPC endpoints (which cost ~\$7–10/mo each). If it's broken, switching to public subnets saves both the endpoint cost AND the fix.

---

## 🔍 Cost Breakdown — Current vs. Optimized

| Service | What you have | Est. \$/mo now | Optimized config | Est. \$/mo after |
|---|---|---|---|---|
| **ALB** | 1 internet-facing ALB | ~\$18–22 | Same (unavoidable) | ~\$18 |
| **ECS Fargate – App** | 1 task, 512 CPU / 1024 MB (default) | ~\$18 | 256 CPU / 512 MB | ~\$9 |
| **ECS Fargate – Scheduler** | 0 tasks ✅ | \$0 | Keep at 0 | \$0 |
| **VPC Endpoints** (if any) | Unknown — needed if app is in private subnet w/o NAT | ~\$7–28 | Eliminate by moving app to public subnet | \$0 |
| **Database (RDS)** | External — unknown instance size | \$15–50 | t3.micro, single-AZ | ~\$15 |
| **Secrets Manager** | 11 secrets × \$0.40 | ~\$4.40 | Move to SSM Parameter Store | ~\$0 |
| **CloudWatch Logs** | 4 groups, 7-day retention | ~\$2–4 | 3-day retention | ~\$1 |
| **ECR** | 2 repos, 5-image limit | ~\$0.50 | 3-image limit | ~\$0.20 |
| **Route53** | 1 hosted zone + 2 records | ~\$0.50 | Same | ~\$0.50 |
| **S3** | Versioned document bucket | ~\$0.10 | Same | ~\$0.10 |
| **ACM** | 1 certificate | Free | Free | \$0 |
| **SNS + Alarms** | 2 alarms, 1 topic | ~\$0.10 | Same | ~\$0.10 |
| **SES** | Transactional email | ~\$0.10/1k | Same | ~\$0.10 |

---

## 🚨 The Real Cost Drivers (Corrected)

### #1 — 🔴 App Task in Private Subnet with No NAT (Critical)

Your `AppService` is in `PrivateSubnetIds` with `AssignPublicIp: DISABLED` but you say there's no NAT Gateway. For this to work you must have **VPC Interface Endpoints** for:
- ECR (image pulls): `ecr.api` + `ecr.dkr` + `s3` gateway = ~\$14–21/mo
- Secrets Manager: ~\$7/mo
- CloudWatch Logs: ~\$7/mo

**That's up to \$35/mo in hidden endpoint costs.**

**The fix is simple:** Move the app task to **public subnets** (`AssignPublicIp: ENABLED`), just like the scheduler already does. This:
- Eliminates VPC endpoint costs entirely (\$0 vs. ~\$28–35/mo)
- Uses the free Internet Gateway for outbound traffic
- Is exactly what your Scheduler already does successfully

### #2 — 🔴 ALB — \$18–22/mo (Fixed, Unavoidable)

The ALB is `\$0.008/hr` base + LCU charges. It's unavoidable while you need HTTPS. Accept it as a fixed baseline.

### #3 — 🟡 App Task Over-sized — Saves ~\$9/mo

Your workflow defaults to `ECS_APP_CPU=512` / `ECS_APP_MEMORY=1024` (0.5 vCPU / 1 GB). Dropping to `256`/`512` halves the Fargate compute cost.

| Config | \$/mo (1 task, 24/7) |
|---|---|
| 512 CPU / 1024 MB (current default) | ~\$18 |
| **256 CPU / 512 MB** ✅ | **~\$9** |

### #4 — 🟡 Secrets Manager — \$4.40/mo

11 secrets × \$0.40/mo = \$4.40, plus API call charges on every container start. **SSM Parameter Store SecureString is free** for standard parameters.

### #5 — 🟢 Database (Unknown)

Your `DATABASE_URL` is external. If it's RDS:
- **t3.micro, single-AZ** = ~\$15/mo ✅ fine
- **t3.small or higher** = \$30+/mo → downsize

---

## ✅ Action Plan to Hit \$60–70/mo

### Step 1 — Fix the App Service Network Config (Biggest Win)

Move `AppService` from private to public subnets in the CloudFormation template:

```yaml
# In AppService NetworkConfiguration — change to:
AwsvpcConfiguration:
  AssignPublicIp: ENABLED          # was DISABLED
  SecurityGroups:
    - !Ref AppServiceSecurityGroup
  Subnets: !Ref PublicSubnetIds   # was PrivateSubnetIds
```

Then delete any VPC Interface Endpoints you have for ECR, Secrets Manager, and CloudWatch.

### Step 2 — Right-size the App Task

Set in GitHub Actions environment variables:

```
ECS_APP_CPU=256
ECS_APP_MEMORY=512
GUNICORN_WORKERS=2
```

### Step 3 — Migrate Secrets Manager → SSM Parameter Store (saves \$4.40/mo)

Create SSM SecureString parameters to replace all 11 Secrets Manager secrets:

```bash
# Example — repeat for each secret
aws ssm put-parameter \
  --name /edupulse/production/database-url \
  --type SecureString \
  --value "your-db-url"
```

Then update the task definition `secrets` block from `secretsmanager` ARNs to `ssm` ARNs:

```json
// Before (Secrets Manager):
{"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..."}

// After (SSM — free):
{"name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:REGION:ACCOUNT:parameter/edupulse/production/database-url"}
```

The ECS task execution role needs `ssm:GetParameters` and `kms:Decrypt` (for the default SSM key). Update the IAM policy accordingly.

### Step 4 — Lower Log Retention and ECR Retention

Update CloudFormation parameters:
```
LogRetentionInDays=3
EcrImageRetentionCount=3
```

### Step 5 — Confirm Scheduler is at 0

```
ECS_SCHEDULER_DESIRED_COUNT=0   # (already the default, just confirm)
```

---

## 📊 Projected Monthly Cost After All Steps

| Service | After \$/mo |
|---|---|
| ALB | \$18 |
| ECS Fargate App (256 / 512 MB) | \$9 |
| ECS Fargate Scheduler | \$0 |
| VPC Endpoints (eliminated) | \$0 |
| RDS t3.micro single-AZ | \$15 |
| SSM Parameter Store (11 params) | \$0 |
| CloudWatch Logs (3-day) | \$1 |
| ECR (2 repos, 3 images) | \$0.20 |
| Route53 | \$0.50 |
| S3 (documents) | \$0.10 |
| SES | ~\$0.10 |
| SNS + Alarms | \$0.10 |
| **Total** | **~\$44–45** |

> [!NOTE]
> Even adding buffer for data transfer, Fargate surge, and SES volume, the final bill should land solidly in the **\$55–65/month** range — right in your target.

---

## 🗺️ Check These in Your AWS Console Now

1. **VPC Console → Endpoints** — count how many interface endpoints you have; each is ~\$7/mo
2. **ECS Console → App task** — confirm actual CPU/Memory of the running task definition
3. **Cost Explorer → Group by Service** — check for any surprise services (ElastiCache, EC2, etc.)
4. **RDS Console** → confirm instance type and Multi-AZ is OFF
5. **Secrets Manager** → count your secrets (should be 11 — confirm none are free-tier grandfathered)

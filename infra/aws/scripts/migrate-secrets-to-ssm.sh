#!/usr/bin/env bash
# =============================================================================
# migrate-secrets-to-ssm.sh
#
# Migrates EduPulse secrets from AWS Secrets Manager to SSM Parameter Store.
# Reads existing secret values from Secrets Manager, creates SSM SecureString
# parameters, then prints the new SSM ARNs ready to paste into GitHub Actions.
#
# Usage:
#   chmod +x infra/aws/scripts/migrate-secrets-to-ssm.sh
#   ./infra/aws/scripts/migrate-secrets-to-ssm.sh
#
# Prerequisites:
#   - AWS CLI configured with credentials that have:
#       secretsmanager:GetSecretValue  (to read current values)
#       ssm:PutParameter               (to create new parameters)
#       kms:GenerateDataKey            (if using a custom KMS key)
#   - The 11 Secrets Manager secret ARNs set as env vars (see below), OR
#     the script will prompt you for each value interactively.
#
# After running:
#   1. Update GitHub Actions variables with the printed SSM ARNs.
#   2. Add ssm:GetParameters to your ECS task execution role IAM policy.
#   3. Push a deploy commit and confirm ECS tasks start healthy.
#   4. Run this script with --delete-old to remove Secrets Manager secrets.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Config — edit these if needed
# ---------------------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
SSM_PATH_PREFIX="/edupulse/production"   # all params live under this prefix
DRY_RUN="${DRY_RUN:-false}"              # set DRY_RUN=true to preview without writing
DELETE_OLD="${1:-}"                      # pass --delete-old to remove SM secrets after

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Confirm AWS identity
# ---------------------------------------------------------------------------
info "Checking AWS credentials..."
CALLER_IDENTITY=$(aws sts get-caller-identity --region "$AWS_REGION" --output json 2>&1) || {
  error "AWS credentials not configured or expired. Run 'aws configure' or refresh your session."
  exit 1
}
ACCOUNT_ID=$(echo "$CALLER_IDENTITY" | python3 -c "import sys,json; print(json.load(sys.stdin)['Account'])")
info "Account: ${ACCOUNT_ID}  |  Region: ${AWS_REGION}"

echo ""
warn "This will create SSM SecureString parameters under: ${SSM_PATH_PREFIX}/"
warn "It will READ current values from Secrets Manager (needs secretsmanager:GetSecretValue)."
if [[ "$DRY_RUN" == "true" ]]; then
  warn "DRY RUN mode — no parameters will be written."
fi
echo ""
read -r -p "Continue? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
echo ""

# ---------------------------------------------------------------------------
# Helper: get a secret value from Secrets Manager by ARN or name
# Falls back to interactive prompt if ARN env var is not set.
# ---------------------------------------------------------------------------
get_secret_value() {
  local arn_env_var="$1"   # e.g. DATABASE_URL_SECRET_ARN
  local secret_label="$2"  # human label for the prompt

  local arn="${!arn_env_var:-}"

  if [[ -n "$arn" ]]; then
    aws secretsmanager get-secret-value \
      --secret-id "$arn" \
      --region "$AWS_REGION" \
      --query 'SecretString' \
      --output text 2>/dev/null || {
        warn "Could not read ${arn_env_var} from Secrets Manager. Falling back to prompt."
        read -r -s -p "  Enter value for ${secret_label}: " val; echo ""; echo "$val"
      }
  else
    warn "${arn_env_var} env var not set — entering value manually."
    read -r -s -p "  Enter value for ${secret_label}: " val; echo ""; echo "$val"
  fi
}

# ---------------------------------------------------------------------------
# Helper: create (or update) one SSM SecureString parameter
# ---------------------------------------------------------------------------
put_ssm_param() {
  local name="$1"
  local value="$2"

  if [[ "$DRY_RUN" == "true" ]]; then
    info "[DRY RUN] Would create: ${name}"
    return 0
  fi

  aws ssm put-parameter \
    --region "$AWS_REGION" \
    --name "$name" \
    --type SecureString \
    --value "$value" \
    --overwrite \
    --no-cli-pager \
    --output text > /dev/null

  success "Created: ${name}"
}

# ---------------------------------------------------------------------------
# Map: SSM param name  →  Secrets Manager ARN env var  →  GitHub Actions var name
#
# Format: "ssm_suffix|sm_arn_env_var|github_actions_var_name|label"
# ---------------------------------------------------------------------------
declare -a SECRETS=(
  "database-url|DATABASE_URL_SECRET_ARN|DATABASE_URL_SECRET_ARN|Database URL"
  "secret-key|SECRET_KEY_SECRET_ARN|SECRET_KEY_SECRET_ARN|Flask SECRET_KEY"
  "jwt-secret-key|JWT_SECRET_KEY_SECRET_ARN|JWT_SECRET_KEY_SECRET_ARN|JWT secret key"
  "data-encryption-key|DATA_ENCRYPTION_KEY_SECRET_ARN|DATA_ENCRYPTION_KEY_SECRET_ARN|Data encryption key"
  "ledger-secret-key|LEDGER_SECRET_KEY_SECRET_ARN|LEDGER_SECRET_KEY_SECRET_ARN|Ledger secret key"
  "bank-webhook-secret|BANK_WEBHOOK_SECRET_ARN|BANK_WEBHOOK_SECRET_ARN|Bank webhook secret"
  "platform-owner-key|PLATFORM_OWNER_KEY_SECRET_ARN|PLATFORM_OWNER_KEY_SECRET_ARN|Platform owner key"
  "mail-password|MAIL_PASSWORD_SECRET_ARN|MAIL_PASSWORD_SECRET_ARN|Mail/SMTP password"
  "paystack-secret-key|PAYSTACK_SECRET_KEY_SECRET_ARN|PAYSTACK_SECRET_KEY_SECRET_ARN|Paystack secret key"
  "paystack-public-key|PAYSTACK_PUBLIC_KEY_SECRET_ARN|PAYSTACK_PUBLIC_KEY_SECRET_ARN|Paystack public key"
  "ratelimit-storage-uri|RATELIMIT_STORAGE_URI_SECRET_ARN|RATELIMIT_STORAGE_URI_SECRET_ARN|Rate limit storage URI (Redis)"
)

# ---------------------------------------------------------------------------
# Main migration loop
# ---------------------------------------------------------------------------
declare -A NEW_ARNS   # stores new SSM ARNs keyed by GitHub Actions var name

info "Starting migration of ${#SECRETS[@]} secrets..."
echo ""

for entry in "${SECRETS[@]}"; do
  IFS='|' read -r ssm_suffix sm_env_var gh_var label <<< "$entry"

  ssm_name="${SSM_PATH_PREFIX}/${ssm_suffix}"

  # Skip optional secrets that have no ARN env var set and confirm with user
  if [[ -z "${!sm_env_var:-}" ]]; then
    read -r -p "  ${label} ARN not set — skip? [Y/n] " skip_confirm
    if [[ ! "$skip_confirm" =~ ^[Nn]$ ]]; then
      warn "Skipping ${ssm_name}"
      continue
    fi
  fi

  secret_value=$(get_secret_value "$sm_env_var" "$label")

  if [[ -z "$secret_value" ]]; then
    warn "Empty value for ${label} — skipping."
    continue
  fi

  put_ssm_param "$ssm_name" "$secret_value"

  # Build the SSM ARN
  ssm_arn="arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${ssm_name}"
  NEW_ARNS["$gh_var"]="$ssm_arn"
done

# ---------------------------------------------------------------------------
# Print GitHub Actions variable update instructions
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo -e "${GREEN}  GitHub Actions variables — update these values${NC}"
echo "============================================================"
echo ""
echo "  Go to: GitHub repo → Settings → Environments → production → Variables"
echo "  Update each variable below with its new SSM ARN:"
echo ""

for gh_var in "${!NEW_ARNS[@]}"; do
  echo -e "  ${YELLOW}${gh_var}${NC}"
  echo "    ${NEW_ARNS[$gh_var]}"
  echo ""
done

# ---------------------------------------------------------------------------
# Print IAM policy snippet
# ---------------------------------------------------------------------------
echo "============================================================"
echo -e "${GREEN}  IAM — add this to your ECS task execution role${NC}"
echo "============================================================"
echo ""
cat <<IAM
  {
    "Effect": "Allow",
    "Action": [
      "ssm:GetParameters",
      "ssm:GetParameter"
    ],
    "Resource": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter${SSM_PATH_PREFIX}/*"
  }
IAM
echo ""
echo "  Role to update: the value of your ECS_TASK_EXECUTION_ROLE_ARN GitHub variable."
echo "  You can add this inline via:"
echo ""
echo "    aws iam put-role-policy \\"
echo "      --role-name <your-execution-role-name> \\"
echo "      --policy-name edupulse-ssm-read \\"
echo "      --policy-document file://infra/aws/iam/ssm-read-policy.json"
echo ""

# ---------------------------------------------------------------------------
# Optionally delete old Secrets Manager secrets
# ---------------------------------------------------------------------------
if [[ "$DELETE_OLD" == "--delete-old" ]]; then
  echo "============================================================"
  warn "  --delete-old flag set. Deleting Secrets Manager secrets..."
  echo "============================================================"
  echo ""
  warn "Only do this AFTER confirming ECS tasks start healthy with the new SSM ARNs!"
  read -r -p "  Confirm deletion of old Secrets Manager secrets? [y/N] " del_confirm
  if [[ "$del_confirm" =~ ^[Yy]$ ]]; then
    for entry in "${SECRETS[@]}"; do
      IFS='|' read -r ssm_suffix sm_env_var gh_var label <<< "$entry"
      arn="${!sm_env_var:-}"
      if [[ -n "$arn" ]]; then
        aws secretsmanager delete-secret \
          --secret-id "$arn" \
          --recovery-window-in-days 7 \
          --region "$AWS_REGION" \
          --no-cli-pager > /dev/null
        success "Scheduled deletion (7-day recovery): ${arn}"
      fi
    done
  else
    info "Skipped deletion. Run with --delete-old after your next successful deploy."
  fi
fi

echo ""
success "Done. Next steps:"
echo "  1. Update the GitHub Actions variables above."
echo "  2. Add the IAM policy to your ECS task execution role."
echo "  3. Push a deploy commit → confirm ECS tasks start healthy."
echo "  4. Re-run this script with --delete-old to remove Secrets Manager secrets."
echo ""


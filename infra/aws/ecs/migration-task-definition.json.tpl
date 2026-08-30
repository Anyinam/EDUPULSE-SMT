{
  "family": "${ECS_MIGRATION_TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "${ECS_MIGRATION_CPU}",
  "memory": "${ECS_MIGRATION_MEMORY}",
  "executionRoleArn": "${ECS_TASK_EXECUTION_ROLE_ARN}",
  "taskRoleArn": "${ECS_TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "edupulse-migrate",
      "image": "${BACKEND_IMAGE}",
      "essential": true,
      "environment": [
        {"name": "FLASK_ENV", "value": "production"},
        {"name": "TRUST_PROXY_HEADERS", "value": "true"},
        {"name": "FRONTEND_ORIGIN", "value": "${FRONTEND_ORIGIN}"},
        {"name": "CORS_ALLOWED_ORIGINS", "value": "${CORS_ALLOWED_ORIGINS}"},
        {"name": "EMAIL_PROVIDER", "value": "${EMAIL_PROVIDER}"},
        {"name": "SES_REGION", "value": "${SES_REGION}"},
        {"name": "MFA_REQUIRED", "value": "${MFA_REQUIRED}"},
        {"name": "APP_ROLE", "value": "migrate"},
        {"name": "ENABLE_SCHEDULER", "value": "false"},
        {"name": "RUN_DB_MIGRATIONS", "value": "true"},
        {"name": "SEED_DEMO_DATA", "value": "false"},
        {"name": "ALLOW_ALL_DASHBOARDS", "value": "false"},
        {"name": "RATE_LIMIT_ENABLED", "value": "true"},
        {"name": "MAIL_SERVER", "value": "${MAIL_SERVER}"},
        {"name": "MAIL_PORT", "value": "${MAIL_PORT}"},
        {"name": "MAIL_USE_TLS", "value": "${MAIL_USE_TLS}"},
        {"name": "MAIL_USERNAME", "value": "${MAIL_USERNAME}"},
        {"name": "MAIL_DEFAULT_SENDER", "value": "${MAIL_DEFAULT_SENDER}"},
        {"name": "GUNICORN_WORKERS", "value": "1"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "${DATABASE_URL_SECRET_ARN}"},
        {"name": "SECRET_KEY", "valueFrom": "${SECRET_KEY_SECRET_ARN}"},
        {"name": "JWT_SECRET_KEY", "valueFrom": "${JWT_SECRET_KEY_SECRET_ARN}"},
        {"name": "DATA_ENCRYPTION_KEY", "valueFrom": "${DATA_ENCRYPTION_KEY_SECRET_ARN}"},
        {"name": "LEDGER_SECRET_KEY", "valueFrom": "${LEDGER_SECRET_KEY_SECRET_ARN}"},
        {"name": "BANK_WEBHOOK_SECRET", "valueFrom": "${BANK_WEBHOOK_SECRET_ARN}"},
        {"name": "PLATFORM_OWNER_KEY", "valueFrom": "${PLATFORM_OWNER_KEY_SECRET_ARN}"},
        {"name": "MAIL_PASSWORD", "valueFrom": "${MAIL_PASSWORD_SECRET_ARN}"},
        {"name": "PAYSTACK_SECRET_KEY", "valueFrom": "${PAYSTACK_SECRET_KEY_SECRET_ARN}"},
        {"name": "PAYSTACK_PUBLIC_KEY", "valueFrom": "${PAYSTACK_PUBLIC_KEY_SECRET_ARN}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${MIGRATION_LOG_GROUP}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
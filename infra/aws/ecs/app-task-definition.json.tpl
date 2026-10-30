{
  "family": "${ECS_APP_TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "${ECS_APP_CPU}",
  "memory": "${ECS_APP_MEMORY}",
  "executionRoleArn": "${ECS_TASK_EXECUTION_ROLE_ARN}",
  "taskRoleArn": "${ECS_TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "edupulse-backend",
      "image": "${BACKEND_IMAGE}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "FLASK_ENV", "value": "production"},
        {"name": "TRUST_PROXY_HEADERS", "value": "true"},
        {"name": "FRONTEND_ORIGIN", "value": "${FRONTEND_ORIGIN}"},
        {"name": "CORS_ALLOWED_ORIGINS", "value": "${CORS_ALLOWED_ORIGINS}"},
        {"name": "EMAIL_PROVIDER", "value": "${EMAIL_PROVIDER}"},
        {"name": "SES_REGION", "value": "${SES_REGION}"},
        {"name": "MFA_REQUIRED", "value": "${MFA_REQUIRED}"},
        {"name": "APP_ROLE", "value": "web"},
        {"name": "ENABLE_SCHEDULER", "value": "false"},
        {"name": "RUN_DB_MIGRATIONS", "value": "false"},
        {"name": "SEED_DEMO_DATA", "value": "false"},
        {"name": "ALLOW_ALL_DASHBOARDS", "value": "false"},
        {"name": "RATE_LIMIT_ENABLED", "value": "true"},
        {"name": "MAIL_SERVER", "value": "${MAIL_SERVER}"},
        {"name": "MAIL_PORT", "value": "${MAIL_PORT}"},
        {"name": "MAIL_USE_TLS", "value": "${MAIL_USE_TLS}"},
        {"name": "MAIL_USERNAME", "value": "${MAIL_USERNAME}"},
        {"name": "MAIL_DEFAULT_SENDER", "value": "${MAIL_DEFAULT_SENDER}"},
        {"name": "DOCUMENT_STORAGE_S3_BUCKET", "value": "${DOCUMENT_STORAGE_S3_BUCKET}"},
        {"name": "DOCUMENT_STORAGE_S3_PREFIX", "value": "${DOCUMENT_STORAGE_S3_PREFIX}"},
        {"name": "GUNICORN_WORKERS", "value": "${GUNICORN_WORKERS}"}
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
        {"name": "PAYSTACK_PUBLIC_KEY", "valueFrom": "${PAYSTACK_PUBLIC_KEY_SECRET_ARN}"},
        {"name": "RATELIMIT_STORAGE_URI", "valueFrom": "${RATELIMIT_STORAGE_URI_SECRET_ARN}"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${BACKEND_LOG_GROUP}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/api/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    },
    {
      "name": "edupulse-frontend",
      "image": "${FRONTEND_IMAGE}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "API_UPSTREAM_URL", "value": "http://127.0.0.1:5000"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${FRONTEND_LOG_GROUP}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "dependsOn": [
        {
          "containerName": "edupulse-backend",
          "condition": "START"
        }
      ]
    }
  ]
}
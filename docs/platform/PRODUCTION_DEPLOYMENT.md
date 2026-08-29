"""
Production Deployment Configuration for EduPulse

This file contains all configurations needed for deploying EduPulse
to a production environment with proper security, scaling, and monitoring.
"""

# ============================================================================
# 1. ENVIRONMENT SETUP
# ============================================================================

PRODUCTION_ENV = {
    # Flask Configuration
    'FLASK_ENV': 'production',
    'FLASK_DEBUG': False,
    'FLASK_PROPAGATE_EXCEPTIONS': False,
    
    # Security
    'SECRET_KEY': '${GENERATE_SECURE_KEY}',  # Use secrets manager
    'JWT_SECRET_KEY': '${GENERATE_JWT_KEY}',  # Use secrets manager
    
    # Database
    'SQLALCHEMY_DATABASE_URI': '${DATABASE_URL}',  # PostgreSQL from secrets manager
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'pool_size': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 40,
    },
    
    # JWT Configuration
    'JWT_TOKEN_LOCATION': ['headers'],
    'JWT_ACCESS_TOKEN_EXPIRES': 3600,  # 1 hour
    'JWT_ERROR_MESSAGE_KEY': 'message',
    
    # Session Configuration
    'SESSION_COOKIE_SECURE': True,  # HTTPS only
    'SESSION_COOKIE_HTTPONLY': True,  # No JavaScript access
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'PERMANENT_SESSION_LIFETIME': 3600,
    
    # Email Configuration
    'MAIL_SERVER': '${MAIL_SERVER}',
    'MAIL_PORT': 587,
    'MAIL_USE_TLS': True,
    'MAIL_USERNAME': '${MAIL_USERNAME}',
    'MAIL_PASSWORD': '${MAIL_PASSWORD}',
    'MAIL_DEFAULT_SENDER': 'noreply@edupulse.edu',
    
    # Security Features
    'ALLOW_ALL_DASHBOARDS': False,  # Disable dev mode
    'RATE_LIMIT_ENABLED': True,
    'DEBUG_TB_ENABLED': False,
    
    # HTTP Headers
    'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # 1 year for static files
}

# ============================================================================
# 2. AWS ECS DEPLOYMENT CONFIGURATION
# ============================================================================

ECS_TASK_DEFINITION = {
    "family": "edupulse-backend",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "1024",
    "memory": "2048",
    
    "containerDefinitions": [
        {
            "name": "edupulse-backend",
            "image": "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/edupulse-backend:${TAG}",
            "portMappings": [
                {
                    "containerPort": 5000,
                    "hostPort": 5000,
                    "protocol": "tcp"
                }
            ],
            
            "environment": [
                {"name": "FLASK_ENV", "value": "production"},
                {"name": "ALLOW_ALL_DASHBOARDS", "value": "False"},
            ],
            
            "secrets": [
                {
                    "name": "DATABASE_URL",
                    "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:edupulse/db-url"
                },
                {
                    "name": "JWT_SECRET_KEY",
                    "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:edupulse/jwt-key"
                },
                {
                    "name": "SECRET_KEY",
                    "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:edupulse/secret-key"
                },
                {
                    "name": "MAIL_PASSWORD",
                    "valueFrom": "arn:aws:secretsmanager:${REGION}:${ACCOUNT_ID}:secret:edupulse/mail-password"
                },
            ],
            
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "/ecs/edupulse-backend",
                    "awslogs-region": "${REGION}",
                    "awslogs-stream-prefix": "ecs"
                }
            },
            
            "healthCheck": {
                "command": ["CMD-SHELL", "curl -f http://localhost:5000/ || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 60
            }
        }
    ]
}

# ============================================================================
# 3. DOCKER COMPOSE PRODUCTION CONFIGURATION
# ============================================================================

DOCKER_COMPOSE_PRODUCTION_OVERRIDE = """
version: '3.8'

services:
  backend:
    image: edupulse-backend:${VERSION}
    environment:
      - FLASK_ENV=production
      - DEBUG=False
      - ALLOW_ALL_DASHBOARDS=False
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - MAIL_SERVER=smtp.gmail.com
      - MAIL_PORT=587
      - MAIL_USERNAME=${MAIL_USERNAME}
      - MAIL_PASSWORD=${MAIL_PASSWORD}
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      db:
        condition: service_healthy
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    restart: always
    depends_on:
      - backend
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
"""

# ============================================================================
# 4. KUBERNETES DEPLOYMENT CONFIGURATION
# ============================================================================

KUBERNETES_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edupulse-backend
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  
  selector:
    matchLabels:
      app: edupulse-backend
  
  template:
    metadata:
      labels:
        app: edupulse-backend
    
    spec:
      serviceAccountName: edupulse
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      
      containers:
      - name: backend
        image: edupulse-backend:latest
        imagePullPolicy: Always
        
        ports:
        - name: http
          containerPort: 5000
        
        env:
        - name: FLASK_ENV
          value: "production"
        - name: ALLOW_ALL_DASHBOARDS
          value: "False"
        
        envFrom:
        - configMapRef:
            name: edupulse-config
        - secretRef:
            name: edupulse-secrets
        
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        
        livenessProbe:
          httpGet:
            path: /
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        
        readinessProbe:
          httpGet:
            path: /
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
        
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
          capabilities:
            drop:
              - ALL
      
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - edupulse-backend
              topologyKey: kubernetes.io/hostname

---
apiVersion: v1
kind: Service
metadata:
  name: edupulse-backend-service
  namespace: production
spec:
  type: LoadBalancer
  selector:
    app: edupulse-backend
  ports:
  - port: 80
    targetPort: 5000
    protocol: TCP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: edupulse-backend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: edupulse-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
"""

# ============================================================================
# 5. DATABASE BACKUP STRATEGY
# ============================================================================

BACKUP_SCRIPT = """#!/bin/bash

# EduPulse Production Database Backup Script
# Run daily via cron or scheduled job

set -e

BACKUP_DIR="/backups/edupulse"
DB_HOST=${DB_HOST:-localhost}
DB_USER=${DB_USER:-edupulse_user}
DB_NAME=${DB_NAME:-edupulse_db}
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Generate timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/edupulse_backup_$TIMESTAMP.sql.gz"

echo "[$(date)] Starting backup of $DB_NAME..."

# Perform backup with compression
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME | gzip > $BACKUP_FILE

echo "[$(date)] Backup completed: $BACKUP_FILE"

# Encrypt backup (optional)
if [ -f "$1" ]; then
    gpg --encrypt --recipient $1 $BACKUP_FILE
    rm $BACKUP_FILE
    BACKUP_FILE="$BACKUP_FILE.gpg"
    echo "[$(date)] Backup encrypted"
fi

# Upload to S3
aws s3 cp $BACKUP_FILE s3://edupulse-backups/$(date +%Y/%m/%d)/ 
echo "[$(date)] Backup uploaded to S3"

# Cleanup old backups (local)
find $BACKUP_DIR -name "*.sql.gz*" -mtime +$RETENTION_DAYS -delete

# Cleanup old backups (S3)
aws s3 rm s3://edupulse-backups --recursive --exclude "*" \\
    --include "*.sql.gz*" --timestamp $(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)

echo "[$(date)] Backup complete and rotated"
"""

# ============================================================================
# 6. MONITORING & ALERTING CONFIGURATION
# ============================================================================

MONITORING_CONFIG = {
    "cloudwatch": {
        "namespace": "EduPulse/Production",
        "metrics": [
            {
                "MetricName": "FailedLogins",
                "Statistic": "Sum",
                "Period": 300,
                "AlarmThreshold": 5,
                "ComparisonOperator": "GreaterThanThreshold"
            },
            {
                "MetricName": "UnauthorizedAccess",
                "Statistic": "Sum",
                "Period": 300,
                "AlarmThreshold": 10,
                "ComparisonOperator": "GreaterThanThreshold"
            },
            {
                "MetricName": "DatabaseConnections",
                "Statistic": "Average",
                "Period": 300,
                "AlarmThreshold": 80,
                "ComparisonOperator": "GreaterThanThreshold"
            },
            {
                "MetricName": "API_ResponseTime",
                "Statistic": "Average",
                "Period": 60,
                "AlarmThreshold": 1000,  # milliseconds
                "ComparisonOperator": "GreaterThanThreshold"
            }
        ]
    },
    
    "datadog": {
        "service": "edupulse",
        "env": "production",
        "monitors": [
            {
                "name": "High error rate",
                "query": "avg:trace.web.request.errors{service:edupulse} > 0.05",
                "type": "metric alert"
            },
            {
                "name": "Database latency high",
                "query": "avg:trace.db.query.duration{service:edupulse} > 2000",
                "type": "metric alert"
            }
        ]
    }
}

# ============================================================================
# 7. SSL/TLS CERTIFICATE MANAGEMENT
# ============================================================================

SSL_CONFIG = """
# Nginx SSL Configuration

ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
ssl_prefer_server_ciphers on;
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;

# HSTS
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# SSL Stapling
ssl_stapling on;
ssl_stapling_verify on;
ssl_trusted_certificate /etc/nginx/certs/ca-chain.crt;

# Certificate Renewal (Let's Encrypt)
# Use certbot for automatic renewal:
# certbot certonly --webroot -w /usr/share/nginx/html -d edupulse.edu
"""

print("""
EduPulse Production Deployment Configuration
=============================================

This configuration file contains all necessary settings for production deployment.

Key Setup Steps:
1. Generate secure keys:
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"

2. Set environment variables in secrets manager:
   - AWS Secrets Manager
   - Kubernetes Secrets
   - Environment variables in CI/CD

3. Database Setup:
   a. Create PostgreSQL instance
  b. Run migrations using the dedicated ECS migration task template
   c. Enable SSL connections

4. Deploy using one of:
   - Docker: docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
  - AWS ECS: Use the checked-in task templates under infra/aws/ecs/
   - Kubernetes: kubectl apply -f kubernetes-deployment.yaml

AWS ECS production path in this repository:
- Web app task: infra/aws/ecs/app-task-definition.json.tpl
- Scheduler task: infra/aws/ecs/scheduler-task-definition.json.tpl
- Migration task: infra/aws/ecs/migration-task-definition.json.tpl
- CloudFormation platform stack: infra/aws/cloudformation/edupulse-ecs-platform.yml
- CloudFormation usage guide: infra/aws/cloudformation/README.md
- Template renderer: infra/aws/render_task_definition.py
- CI/CD deploy workflow: .github/workflows/security-tests-deploy.yml
- GitHub Actions variable checklist: infra/aws/GITHUB_ACTIONS_VARIABLES.md

Production runtime rules now enforced by code:
- Web containers do not start background jobs; only the dedicated scheduler task runs APScheduler jobs.
- Automatic demo seeding is disabled unless SEED_DEMO_DATA=true is set explicitly.
- Schema bootstrapping via db.create_all() is no longer part of production startup.
- CORS must be configured through FRONTEND_ORIGIN or CORS_ALLOWED_ORIGINS.
- Reverse-proxy TLS headers must be enabled with TRUST_PROXY_HEADERS=true when running behind AWS load balancers.

Required GitHub Actions repository/environment variables for AWS deployment:
- AWS_REGION
- ECR_BACKEND_REPOSITORY
- ECR_FRONTEND_REPOSITORY
- ECS_CLUSTER_NAME
- ECS_APP_SERVICE
- ECS_SCHEDULER_SERVICE
- ECS_APP_TASK_FAMILY
- ECS_SCHEDULER_TASK_FAMILY
- ECS_MIGRATION_TASK_FAMILY
- ECS_TASK_EXECUTION_ROLE_ARN
- ECS_TASK_ROLE_ARN
- ECS_SUBNET_IDS
- ECS_SECURITY_GROUP_IDS
- FRONTEND_ORIGIN
- CORS_ALLOWED_ORIGINS
- MAIL_SERVER
- MAIL_PORT
- MAIL_USE_TLS
- MAIL_USERNAME
- MAIL_DEFAULT_SENDER
- BACKEND_LOG_GROUP
- FRONTEND_LOG_GROUP
- SCHEDULER_LOG_GROUP
- MIGRATION_LOG_GROUP
- DATABASE_URL_SECRET_ARN
- SECRET_KEY_SECRET_ARN
- JWT_SECRET_KEY_SECRET_ARN
- DATA_ENCRYPTION_KEY_SECRET_ARN
- LEDGER_SECRET_KEY_SECRET_ARN
- BANK_WEBHOOK_SECRET_ARN
- MAIL_PASSWORD_SECRET_ARN
- PAYSTACK_SECRET_KEY_SECRET_ARN
- PAYSTACK_PUBLIC_KEY_SECRET_ARN
- Optional: WHATSAPP_API_TOKEN_SECRET_ARN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_BUSINESS_ACCOUNT_ID, PLATFORM_OWNER_KEY_SECRET_ARN

5. Setup monitoring and alerting
6. Configure automated backups
7. Enable SSL/TLS certificates

See SETUP.md for detailed deployment instructions.
""")

# 🔐 Production Security Setup Guide for EduPulse

## Overview
This guide covers critical security configurations required before launching EduPulse to production in Ghana. Follow these steps carefully to ensure data protection, payment security, and system integrity.

---

## ✅ Pre-Launch Security Checklist

### 1. Environment Variables (CRITICAL)

**Generate Strong Secrets:**
```bash
# Generate Flask & JWT secrets (64 characters recommended)
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_hex(32))"

# Generate Ledger HMAC key for financial audit immutability
python -c "import secrets; print('LEDGER_SECRET_KEY=' + secrets.token_hex(32))"

# Generate AES-256 encryption key for sensitive data
python -c "from cryptography.fernet import Fernet; print('DATA_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

**Set Environment Variables:**
```bash
# On your production server
export SECRET_KEY="your_generated_secret_key"
export JWT_SECRET_KEY="your_generated_jwt_key"
export LEDGER_SECRET_KEY="your_generated_ledger_key"
export DATA_ENCRYPTION_KEY="your_generated_encryption_key"
export DATABASE_URL="postgresql://user:password@localhost:5432/edupulse_prod"
```

**Docker Compose:**
Create `.env` file in project root (copy from `.env.example`):
```bash
cp .env.example .env
nano .env  # Edit and fill in real values
```

⚠️ **NEVER commit `.env` file to version control!**

---

### 2. Paystack Payment Integration

**Get API Keys:**
1. Sign up at [Paystack Dashboard](https://dashboard.paystack.com/)
2. Go to Settings > API Keys & Webhooks
3. Copy your **Live Secret Key** and **Live Public Key**

**Set Environment Variables:**
```bash
export PAYSTACK_SECRET_KEY="sk_live_xxxxxxxxxx"
export PAYSTACK_PUBLIC_KEY="pk_live_xxxxxxxxxx"
```

**Configure Webhook:**
1. In Paystack Dashboard: Settings > API Keys & Webhooks
2. Add webhook URL: `https://api.edupulse.com.gh/api/paystack/webhook`
3. Select events:
   - ✅ `charge.success`
   - ✅ `subscription.create`
   - ✅ `subscription.not_renew`
   - ✅ `invoice.payment_failed`

**Test Payments:**
```bash
# Use test mode first
export PAYSTACK_SECRET_KEY="sk_test_xxxxxxxxxx"
export PAYSTACK_PUBLIC_KEY="pk_test_xxxxxxxxxx"

# Test card: 4084 0840 8408 4081 (Success)
# CVV: 408  |  PIN: 0000  |  Expiry: 12/28
```

---

### 3. Database Security

**Create Production Database:**
```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE edupulse_prod;
CREATE USER edupulse_user WITH ENCRYPTED PASSWORD 'your_super_strong_password';
GRANT ALL PRIVILEGES ON DATABASE edupulse_prod TO edupulse_user;
```

**Enable SSL Connections:**
```bash
# In postgresql.conf
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
```

**Connection String with SSL:**
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/edupulse_prod?sslmode=require"
```

**Automated Backups:**
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/var/backups/edupulse"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > "$BACKUP_DIR/backup_$TIMESTAMP.sql"
gzip "$BACKUP_DIR/backup_$TIMESTAMP.sql"

# Keep last 30 days only
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

Schedule with cron:
```bash
crontab -e
# Add: 0 2 * * * /path/to/backup_script.sh
```

---

### 4. Email Configuration (Gmail SMTP)

**Generate App Password:**
1. Go to [Google Account](https://myaccount.google.com/)
2. Security > 2-Step Verification (must be enabled)
3. App Passwords > Select "Mail" > Generate
4. Copy 16-character password

**Set Environment Variables:**
```bash
export MAIL_SERVER="smtp.gmail.com"
export MAIL_PORT=587
export MAIL_USE_TLS=True
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your 16-digit app password"
export MAIL_DEFAULT_SENDER="noreply@edupulse.com.gh"
```

**Test Email:**
```python
from backend.utils import send_email_notification
send_email_notification(
    to_email="test@example.com",
    subject="EduPulse Production Test",
    body="Email service is working!"
)
```

---

### 5. WhatsApp Business API Integration (Ghana-specific)

**Setup WhatsApp Business API:**
1. Sign up at [Meta for Developers](https://developers.facebook.com/)
2. Create Business App
3. Add WhatsApp Product
4. Get Phone Number ID and API Token

**Set Environment Variables:**
```bash
export WHATSAPP_API_TOKEN="your_whatsapp_api_token"
export WHATSAPP_PHONE_NUMBER_ID="your_phone_number_id"
export WHATSAPP_BUSINESS_ACCOUNT_ID="your_business_account_id"
```

**Test Message:**
```python
import requests

url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
headers = {
    "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
    "Content-Type": "application/json"
}
payload = {
    "messaging_product": "whatsapp",
    "to": "233XXXXXXXXX",  # Ghana format
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {"code": "en"}
    }
}
response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

**Webhook Configuration:**
1. In Meta Dashboard: WhatsApp > Configuration
2. Webhook URL: `https://api.edupulse.com.gh/api/whatsapp/webhook`
3. Verify Token: Generate random string: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
4. Subscribe to: `messages`, `message_status`

---

### 6. SSL/TLS Certificates (HTTPS)

**Option A: Let's Encrypt (Free, Recommended)**
```bash
# Install Certbot
sudo apt-get update
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d edupulse.com.gh -d app.edupulse.com.gh -d api.edupulse.com.gh

# Auto-renewal (already configured by certbot)
sudo certbot renew --dry-run
```

**Option B: Cloudflare (Free SSL + CDN)**
1. Sign up at [Cloudflare](https://www.cloudflare.com/)
2. Add your domain `edupulse.com.gh`
3. Update nameservers at domain registrar
4. Enable "Full (Strict)" SSL mode
5. Enable "Always Use HTTPS"

**Nginx Configuration:**
```nginx
server {
    listen 443 ssl http2;
    server_name api.edupulse.com.gh;
    
    ssl_certificate /etc/letsencrypt/live/edupulse.com.gh/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/edupulse.com.gh/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

### 7. Firewall & Network Security

**UFW Configuration (Ubuntu):**
```bash
# Enable firewall
sudo ufw enable

# Allow essential ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS

# Block direct database access
sudo ufw deny 5432/tcp

# Check status
sudo ufw status
```

**Restrict Database Access:**
```bash
# PostgreSQL: Edit pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Only allow local connections
local   all             all                                     peer
host    edupulse_prod   edupulse_user   127.0.0.1/32            md5
```

---

### 8. Monitoring & Alerts

**Sentry (Error Tracking):**
```bash
# Install
pip install sentry-sdk[flask]

# Set environment variable
export SENTRY_DSN="https://xxxxx@sentry.io/xxxxx"
```

**Application Code:**
```python
# backend/api/api.py
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FlaskIntegration()],
        environment="production",
        traces_sample_rate=0.1
    )
```

**UptimeRobot (Downtime Alerts):**
1. Sign up at [UptimeRobot](https://uptimerobot.com/)
2. Add monitors:
   - `https://api.edupulse.com.gh/api/health`
   - `https://app.edupulse.com.gh`
3. Set alert contacts (email, SMS, WhatsApp)

---

### 9. Rate Limiting & DDoS Protection

**Cloudflare (Recommended):**
- Automatic DDoS protection
- Rate limiting rules
- Bot protection
- Web Application Firewall (WAF)

**Application-Level Rate Limiting:**
```python
# Already implemented in backend/middleware.py
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Enable in production
RATELIMIT_ENABLED=True
```

---

### 10. Docker Production Deployment

**Optimized docker-compose.yml:**
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    restart: always
    depends_on:
      db:
        condition: service_healthy
    environment:
      SECRET_KEY: ${SECRET_KEY}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      LEDGER_SECRET_KEY: ${LEDGER_SECRET_KEY}
      DATA_ENCRYPTION_KEY: ${DATA_ENCRYPTION_KEY}
      DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      PAYSTACK_SECRET_KEY: ${PAYSTACK_SECRET_KEY}
      PAYSTACK_PUBLIC_KEY: ${PAYSTACK_PUBLIC_KEY}
      WHATSAPP_API_TOKEN: ${WHATSAPP_API_TOKEN}
    ports:
      - "5000:5000"

  frontend:
    build: ./frontend
    restart: always
    ports:
      - "3000:80"

volumes:
  postgres_data:
```

**Deploy:**
```bash
docker-compose --env-file .env -f docker-compose.yml up -d --build
```

---

## 🚀 Launch Checklist

Before going live, verify:

- [ ] All environment variables set in production `.env`
- [ ] Strong secrets generated (32+ characters each)
- [ ] Paystack live keys configured
- [ ] Paystack webhook URL added and verified
- [ ] Database backups scheduled (daily)
- [ ] SSL certificate installed and auto-renewal working
- [ ] Firewall rules configured
- [ ] Sentry error tracking enabled
- [ ] UptimeRobot monitors configured
- [ ] Email service tested (send test email)
- [ ] WhatsApp API tested (send test message)
- [ ] Terms management system configured (create terms for academic year)
- [ ] Test subscription payment end-to-end
- [ ] Cloudflare DNS configured (if using)
- [ ] Domain pointed to server IP
- [ ] Nginx/reverse proxy configured
- [ ] Health check endpoint responding: `/api/health`
- [ ] Rate limiting enabled
- [ ] CORS origins restricted to your domain
- [ ] `DEBUG=False` in production
- [ ] Admin accounts created with strong passwords
- [ ] School onboarding tested

---

## 📞 Support Contacts

**Technical Issues:**
- Paystack Support: [support@paystack.com](mailto:support@paystack.com)
- WhatsApp Business API: [Meta for Developers](https://developers.facebook.com/support/)
- Domain/SSL: Your hosting provider

**Emergency Contacts:**
- Database failure: [Your DBA contact]
- Payment issues: [Your finance team]
- System down: [Your DevOps lead]

---

## 🔄 Regular Maintenance

**Daily:**
- Check error logs: `docker-compose logs backend --tail=100`
- Monitor payment webhook logs
- Review Sentry errors

**Weekly:**
- Verify backup integrity
- Check disk space: `df -h`
- Review UptimeRobot uptime percentage

**Monthly:**
- Update dependencies: `pip list --outdated`
- SSL certificate renewal check (auto-renews but verify)
- Security audit: review access logs
- Performance optimization: analyze slow queries

**Quarterly:**
- Database optimization: `VACUUM ANALYZE;`
- Security patches: `sudo apt update && sudo apt upgrade`
- Disaster recovery test: restore from backup

---

## 🛡️ Security Incident Response

**If compromised:**
1. **Immediately** rotate all secrets (SECRET_KEY, JWT_SECRET_KEY, LEDGER_SECRET_KEY)
2. Force logout all users
3. Check audit logs for unauthorized access
4. Review ledger chain integrity: `/api/finance/audit/verify`
5. Notify affected schools if data breach
6. Document incident and resolution

**Contact Authorities:**
- Ghana Cybersecurity Authority: [www.nca.org.gh](https://www.nca.org.gh/)
- Data Protection Commission: [www.dataprotection.org.gh](https://www.dataprotection.org.gh/)

---

**Version:** 1.0  
**Last Updated:** February 2026  
**Author:** EduPulse Security Team

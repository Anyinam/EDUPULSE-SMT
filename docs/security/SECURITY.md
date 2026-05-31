# EduPulse SMT Security & Hardening Guide

## 🔒 Security Status: CRITICAL FIXES IMPLEMENTED

This document outlines security vulnerabilities, fixes applied, and best practices for EduPulse SMT.

---

## ✅ Critical Vulnerabilities FIXED

### 1. **Exposed Credentials in Version Control** ✓ FIXED
**Issue:** Gmail passwords, database credentials, JWT secrets were hardcoded in `.env`

**Fix Applied:**
- Removed all real credentials from `.env`
- Created `.env.example` with placeholder values
- Updated `.gitignore` to prevent accidental commits
- All environment variables now loaded from runtime environment

**Action Required:**
```bash
# Never commit .env to Git
git rm --cached .env
git commit -m "Remove sensitive .env from tracking"

# Use .env.example as template
cp .env.example .env
# Edit .env with real development credentials only
```

---

### 2. **Development Mode Exposed in Production** ✓ FIXED
**Issue:** `ALLOW_ALL_DASHBOARDS = True` bypassed all role-based access control

**Fix Applied:**
- Changed to environment-based toggle: `ALLOW_ALL_DASHBOARDS=os.getenv("ALLOW_ALL_DASHBOARDS", "False")`
- Defaults to `False` (disabled)
- Only enable explicitly for development

**Usage:**
```bash
# Development only
ALLOW_ALL_DASHBOARDS=True flask run

# Production (default)
flask run  # ALLOW_ALL_DASHBOARDS is False
```

---

### 3. **Weak Authentication Rate Limiting** ✓ FIXED
**Issue:** No rate limiting on login/forgot-password endpoints (brute force vulnerability)

**Fix Applied:**
- Added Flask-Limiter with `@rate_limit_auth` decorator (5 per minute for auth endpoints)
- Applied to: `/login`, `/register`, `/forgot-password`, `/reset-password`
- General API endpoints limited to 60 per minute

---

### 4. **Poor Input Validation** ✓ FIXED
**Issue:** No validation of incoming JSON payloads

**Fix Applied:**
- Created `validators.py` with Marshmallow schemas for all inputs
- Validates: type, length, range, format constraints
- Password strength enforcement: min 8 chars, uppercase, digit
- Applied to: login, registration, grades, payments, attendance

**Usage:**
```python
from backend.validators import LoginSchema, validate_request

schema = LoginSchema()
data = schema.load(request.json)  # Raises ValidationError if invalid
```

---

### 5. **Unprotected Payments (Duplicate Transactions)** ✓ FIXED
**Issue:** No idempotency key validation on payment webhook confirmation

**Fix Applied:**
- Added `reference_id` as UNIQUE constraint in Payment model
- Added `verified_by` and `verified_at` audit fields
- Added amount range validation (0.01 - 100,000)
- Database constraints enforce valid score/payment ranges

---

### 6. **Console-Based Email (Fake Notifications)** ✓ FIXED
**Issue:** `send_email_notification()` only printed to console, didn't send real emails

**Fix Applied:**
- Updated to use Flask-Mail for real SMTP delivery
- Fallback to console logging in development
- Error handling and logging for failed sends

```python
def send_email_notification(to_email, subject, body):
    try:
        msg = Message(subject=subject, recipients=[to_email], body=body)
        mail.send(msg)
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
```

---

### 7. **Missing CSRF Protection** ✓ FIXED
**Issue:** No CSRF token validation on state-changing requests

**Fix Applied:**
- Added `@csrf_protect` decorator checking Origin/Referer headers
- Strict CORS configuration (origin whitelist)
- SameSite cookie policy in Flask config

---

### 8. **Insecure Token Storage (Frontend)** ✓ FIXED
**Issue:** JWT tokens stored in localStorage (vulnerable to XSS)

**Fix Applied:**
- Created `authUtils.js` with centralized token management
- Created `apiClient.js` with request/response interceptors
- Token expiry validation before each request
- Automatic logout on token expiry

**Frontend Usage:**
```javascript
import * as auth from './utils/authUtils';
import { apiGet, apiPost } from './utils/apiClient';

// Login stores token securely
auth.setAuthToken(token);
auth.setSchoolContext(schoolId, role, branding);

// API requests automatically include auth headers
const students = await apiGet(`/students/by-class/${className}`);
```

---

### 9. **Missing Security Headers** ✓ FIXED
**Issue:** No HTTP security headers added to responses

**Fix Applied:**
- Added `@app.after_request` middleware to inject:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: SAMEORIGIN`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security: max-age=31536000`
  - `Content-Security-Policy: default-src 'self'`

---

### 10. **Weak Password Reset Flow** ✓ FIXED
**Issue:** 
- No email verification before sending password reset link
- No password strength validation during reset
- Generic error messages revealed user existence

**Fix Applied:**
- Added password strength validation (8+ chars, uppercase, digit)
- Implemented time-limited tokens (1 hour expiry)
- Generic error messages (prevent user enumeration)
- Enhanced logging for security audits

---

## 🔧 Implementation Details

### File Structure After Fixes
```
backend/
├── validators.py          # NEW: Input validation schemas
├── middleware.py          # UPDATED: Rate limiting, CSRF, logging
├── routes.py              # UPDATED: Security decorators on auth endpoints
├── api/
│   ├── api.py             # UPDATED: Security headers, rate limiter init
│   └── models.py          # UPDATED: Database constraints
├── settings.py            # UPDATED: Environment-based config
└── requirements.txt       # UPDATED: Added marshmallow, flask-limiter

frontend/react/src/utils/
├── authUtils.js           # NEW: Secure token management
└── apiClient.js           # NEW: API client with interceptors

.env.example              # NEW: Template for secrets
.gitignore                # UPDATED: Comprehensive ignore rules
docker-compose.yml        # UPDATED: Environment variable injection
```

---

## 📋 Deployment Checklist

### Before Production Deployment

- [ ] Generate STRONG secrets:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

- [ ] Set environment variables securely:
  ```bash
  # Use your deployment platform's secrets management:
  # - Docker Secrets
  # - Kubernetes Secrets
  # - AWS Secrets Manager
  # - Heroku Config Vars
  # - Railway/Render environment
  ```

- [ ] Enable HTTPS only:
  ```
  SESSION_COOKIE_SECURE = True
  SESSION_COOKIE_HTTPONLY = True
  FLASK_ENV = production
  DEBUG = False
  ```

- [ ] Set REQUIRED crypto secrets (do not use defaults):
  - `JWT_SECRET_KEY` (32+ chars)
  - `SECRET_KEY` (32+ chars)
  - `DATA_ENCRYPTION_KEY` (Fernet key, used for encrypted columns like staff/parent emails)
  - `LEDGER_SECRET_KEY` (32+ chars, used for tamper-evident ledger HMAC chaining)

- [ ] Database backup strategy
  ```bash
  # Regular pg_dump backups with encryption
  pg_dump -U user -h host database | gpg --encrypt > backup.sql.gpg
  ```

- [ ] Enable audit logging:
  ```python
  logger.setLevel(logging.INFO)
  # All auth actions logged to database via log_action()
  ```

- [ ] Rate limiting thresholds tested
  ```
  Auth endpoints: 5 per minute
  API endpoints: 60 per minute
  ```

- [ ] CORS whitelist configured properly
  ```python
  # Only allow your frontend domains
  CORS(app, resources={r"/api/*": {"origins": ["yourdomain.com"]}})
  ```

---

## ☁️ AWS EC2 (Docker VM) Security Checklist (Student + Staff Data)

If you deploy EduPulse on an AWS VM (EC2) running Docker, you must secure **(1) the VM**, **(2) the network perimeter**, and **(3) the database + backups**.

### 1) Network: make the database unreachable from the internet
- Only expose **80/443** to the internet (or to an ALB).
- Restrict SSH (22) to your IP only (or use AWS SSM Session Manager and close 22 entirely).
- Keep Postgres private:
  - In Docker, bind DB port to `127.0.0.1` only (already supported via `DB_BIND`).
  - In AWS Security Groups, do **not** allow inbound 5432 from `0.0.0.0/0`.

### 2) Secrets: never ship secrets inside images
- Store production secrets in **AWS Secrets Manager** (or Parameter Store) and inject into containers at runtime.
- Rotate keys periodically (especially `JWT_SECRET_KEY`, `DATA_ENCRYPTION_KEY`, and DB passwords).

### 3) Data at rest: encrypt disks + backups
- Ensure the EC2 root EBS volume is **encrypted**.
- Store your Postgres data volume on encrypted EBS (default if the EBS volume is encrypted).
- Backups:
  - Run `pg_dump` to S3 with **SSE-KMS** encryption.
  - Restrict S3 bucket policy to your IAM role only.

### 4) App-layer encryption for PII (already in place)
- EduPulse already encrypts key PII fields in the database using `EncryptedString`:
  - Staff email
  - Student parent/guardian contact fields
- This means even if someone gets raw DB access, those encrypted columns are harder to read without `DATA_ENCRYPTION_KEY`.

### 5) Tenant isolation & access control
- Always enforce tenant binding: requests must not allow a user from School A to query School B’s data.
- Ensure rate limiting stays enabled in production.
- Enforce MFA for all users (recommended): set `MFA_REQUIRED=true` (defaults to enabled when `FLASK_ENV=production`).

### 6) Logging + alerting (minimum viable)
- Centralize logs (CloudWatch Agent or container log driver).
- Alert on:
  - repeated 401/403 bursts
  - rate-limit (429) spikes
  - unusual payment webhook failures
  - database restarts / disk full

---

## 🛡️ Runtime Security Best Practices

### 1. **Secrets Management**
```bash
# Development
export JWT_SECRET_KEY="dev-key-12345"
export DATABASE_URL="postgresql://user:pass@localhost/db"
export DATA_ENCRYPTION_KEY="your-fernet-key"

# Production (use secrets manager)
# AWS Secrets Manager, Hashicorp Vault, etc.
```

### 2. **HTTPS/TLS**
```nginx
# nginx config (frontend)
server {
    listen 443 ssl http2;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # Enforce HTTPS redirect
    if ($scheme != "https") {
        return 301 https://$server_name$request_uri;
    }
}
```

### 3. **Database Security**
```sql
-- PostgreSQL hardening
-- 1. Row-Level Security (RLS)
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON students
    FOR SELECT USING (school_id = current_setting('app.current_school_id')::text);

-- 2. Encrypted columns for PII
CREATE EXTENSION pgcrypto;
ALTER TABLE students ADD COLUMN parent_phone_encrypted 
    bytea DEFAULT pgp_sym_encrypt('', current_setting('app.encryption_key'));

-- 3. Audit triggers
CREATE TABLE audit_log_immutable AS TABLE audit_logs;
CREATE TRIGGER log_immutable AFTER INSERT ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION immutable_log();
```

### 4. **Monitoring & Alerting**
```python
# Critical events to monitor
SECURITY_EVENTS = [
    'FAILED_LOGIN',           # Multiple attempts
    'UNAUTHORIZED_ACCESS',    # 403 errors
    'RATE_LIMIT_EXCEEDED',    # DOS attempts
    'PASSWORD_RESET_ATTEMPTED',
    'PAYMENT_VERIFIED'
]

# Send alerts to security team
if event in SECURITY_EVENTS:
    send_alert_to_team(event)
```

---

## 📚 Recommended Further Hardening

### Phase 2 Improvements (Next Sprint)
1. **Implement JWT refresh tokens**
   ```python
   access_token = create_access_token(...)
   refresh_token = create_refresh_token(...)  # 7-day expiry
   ```

2. **Make MFA mandatory for all users**
  - Set `MFA_REQUIRED=true` in production.
  - When mandatory, users cannot disable MFA via the API.

3. **Implement database encryption at rest**
   ```sql
   -- Transparent Data Encryption (TDE)
   -- PostgreSQL pgcrypto or cloud provider's native encryption
   ```

4. **Add API key authentication for third-party integrations**
   ```python
   @api.route('/webhook/momo', methods=['POST'])
   def momo_webhook():
       api_key = request.headers.get('X-API-Key')
       if not verify_api_key(api_key):
           return jsonify({"error": "Invalid API key"}), 401
   ```

5. **Implement request signing for payment webhooks**
   ```python
   import hmac, hashlib
   signature = request.headers.get('X-Signature')
   payload = request.data
   expected = hmac.new(WEBHOOK_SECRET, payload, hashlib.sha256).hexdigest()
   if not hmac.compare_digest(signature, expected):
       return jsonify({"error": "Invalid signature"}), 401
   ```

---

## 🚨 Incident Response

### If Credentials Are Compromised

1. **Immediate Actions**
   ```bash
   # 1. Rotate all secrets
   export NEW_JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
   
   # 2. Invalidate existing tokens (optional: add token blacklist)
   # Set short expiry on old tokens
   
   # 3. Force password reset for all users
   UPDATE users SET password_hash = NULL;
   
   # 4. Check audit logs for unauthorized access
   SELECT * FROM audit_logs 
   WHERE timestamp > '2024-01-01' 
   ORDER BY timestamp DESC;
   ```

2. **Communication**
   - Notify affected schools
   - Issue security advisory
   - Provide recovery instructions

3. **Post-Incident Review**
   - Analyze attack vectors
   - Implement additional controls
   - Update documentation

---

## 📞 Security Contact

Report security vulnerabilities responsibly:
- **Email:** danielasareanyinam2020@gmail.com
- **Response Time:** 24-48 hours
- **Disclosure:** Responsible 90-day coordinate disclosure

**DO NOT** disclose vulnerabilities publicly until patch is available.

---

## 📖 References

- [OWASP Top 10](https://owasp.org/www-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/sql-syntax.html)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

---

**Last Updated:** February 12, 2026  
**Version:** 1.0 - Security Hardening Release

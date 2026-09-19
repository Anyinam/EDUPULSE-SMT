# EduPulse SMT Setup & Installation Guide

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Docker & Docker Compose (optional, for containerized setup)

---

## 🚀 Quick Start (Development)

### 1. Clone & Navigate
```bash
cd /home/anyinam/Documents/EduPulse
```

### 2. Backend Setup

#### Option A: Virtual Environment
```bash
# Create virtual environment
python3 -m venv Eduenv

# Activate (Linux/Mac)
source Eduenv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

#### Option B: Using Docker
```bash
docker-compose up --build
```

### 3. Configure Environment

```bash
# Copy example to actual .env (NEVER commit .env)
cp .env.example .env

# Edit .env with your credentials (development only)
nano .env

# Required fields to customize:
# POSTGRES_USER=your_username
# POSTGRES_PASSWORD=your_password  # Generate strong password
# MAIL_USERNAME=your-email@gmail.com
# MAIL_PASSWORD=your-app-password  # From Google App Passwords
# DATA_ENCRYPTION_KEY=your-fernet-key
# PAYSTACK_SECRET_KEY=sk_test_or_live_key
# PAYSTACK_PUBLIC_KEY=pk_test_or_live_key
# BANK_WEBHOOK_SECRET=shared secret used to verify bank/provider callbacks
```

`BANK_WEBHOOK_SECRET` is platform-level. It does not come from each school's bank account.
Use one of these models:
- if the bank or payment aggregator gives you a webhook signing secret, store that exact value in `.env`
- if the bank asks you to define a shared secret for callback signing, generate your own strong random value and configure the same value on both sides

`PAYSTACK_SECRET_KEY` is required for both:

- paid subscription checkout verification
- tracked-transfer tuition collection through Paystack dedicated virtual accounts

`PAYSTACK_PUBLIC_KEY` is required for frontend checkout flows that still redirect schools or families through Paystack.

### Payment Feature Setup Notes

- Tracked transfer accounts do not become available for a school just because platform Paystack keys exist.
- Each school must still save verified bank details in Settings so EduPulse can create that school's Paystack settlement subaccount.
- If a school enables tuition installments, the saved installment schedule must add up exactly to the configured tuition amount before the fee settings can be saved.

### 4. Initialize Database

Note: The default dev SQLite database is `instance/edupulse.db`.
The current local reset and seed flows rebuild the schema from Alembic migrations before inserting demo data.

```bash
# Apply migrations explicitly when needed
alembic upgrade head

# Run seed script to rebuild and create demo data
python backend/seed.py

# Optional empty-schema reset (drops local data and rebuilds from migrations)
python backend/reset_db.py
```

### 5. Start Backend
```bash
# From backend directory
cd backend
python -m flask run --reload
# Backend runs on http://localhost:5000
```

### 6. Frontend Setup

```bash
# Open new terminal
cd frontend/react

# Install dependencies
npm install

# Start dev server
npm run dev
# Frontend runs on http://localhost:5173
```

### 7. Access Application

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:5000/api
- **PostgreSQL:** localhost:5432

---

## 🔑 Authentication

### Test Credentials (After seed.py)

**School:** CCA-OFK
```
Proprietor:
- Username: proprietor_cca
- Password: cca2026

Homeroom Teacher:
- Username: homeroom_teacher
- Password: homeroom123

Subject Teacher:
- Username: subject_teacher
- Password: subject123

Headmaster:
- Username: headmaster_cca
- Password: headmaster123

Finance Officer:
- Username: finance_cca
- Password: finance123

Kitchen Staff:
- Username: kitchen_staff
- Password: kitchen123

Store Manager:
- Username: store_manager
- Password: store123
```

---

## 🐳 Docker Deployment

### Development Setup
```bash
# Copy .env
cp .env.example .env
nano .env  # Edit credentials

# Start all services
docker-compose up --build

# Seed database (from another terminal)
docker exec edupulse-backend-1 python backend/seed.py

# Stop services
docker-compose down
```

### Production Setup
```bash
# Use production environment file
cp .env.example .env.production
nano .env.production

# Set production flags
FLASK_ENV=production
DEBUG=False
ALLOW_ALL_DASHBOARDS=False

# Start with production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📦 Backend Commands

```bash
# Run tests (when test suite is created)
pytest tests/ -v

# Database migrations
# Local schema lifecycle is Alembic-first
alembic upgrade head
alembic downgrade -1

# Generate test/demo data (rebuilds schema from migrations first)
python backend/seed.py

# Rebuild empty local schema from migrations
python backend/reset_db.py

# Check database
psql -U edupulse_user -d edupulse_db
```

---

## 🎨 Frontend Commands

```bash
# Development
npm run dev          # Start dev server
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # ESLint check

# Install new packages
npm install package-name
npm install -D dev-package-name
```

---

## 🔐 Security Configuration

### Generate Strong Secrets
```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('LEDGER_SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('BANK_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
python3 -c "from cryptography.fernet import Fernet; print('DATA_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

### Gmail App Password
1. Go to [Google Account](https://myaccount.google.com)
2. Select "Security" in left menu
3. Enable "2-Step Verification" (if not enabled)
4. Search for "App passwords"
5. Generate password for "Mail" → "Windows Computer"
6. Copy 16-character password to `.env` as `MAIL_PASSWORD`

### Rate Limiting Configuration
Edit `backend/settings.py`:
```python
RATE_LIMIT_AUTH = "5 per minute"     # Login attempts
RATE_LIMIT_API = "60 per minute"     # General API
```

### CORS Configuration
Do not hardcode production origins in code. Set environment variables instead:

```bash
FRONTEND_ORIGIN=https://app.edupulse.com.gh
CORS_ALLOWED_ORIGINS=https://app.edupulse.com.gh,https://admin.edupulse.com.gh
TRUST_PROXY_HEADERS=true
```

For local development, localhost defaults are still supported when `FLASK_ENV` is not production.

### Runtime Roles

Production and container runtime now support explicit app roles:

```bash
APP_ROLE=web
APP_ROLE=scheduler
APP_ROLE=migrate
```

- `web` serves the API
- `scheduler` runs background jobs such as trial and reconciliation sweeps
- `migrate` applies Alembic migrations and exits

---

## 🐛 Troubleshooting

### Issue: "Connection refused" (Database)
```bash
# Check if PostgreSQL is running
psql -U edupulse_user -d postgres

# Start PostgreSQL (macOS)
brew services start postgresql

# Or via Docker
docker-compose up db
```

### Issue: "ModuleNotFoundError"
```bash
# Reinstall requirements
pip install -r backend/requirements.txt --force-reinstall

# Check Python version
python3 --version  # Should be 3.10+
```

### Issue: "Permission denied" (.env)
```bash
# Fix permissions
chmod 600 .env
```

### Issue: Port already in use
```bash
# Kill process on port
lsof -ti:5000 | xargs kill -9  # Backend
lsof -ti:5173 | xargs kill -9  # Frontend
```

### Issue: "CORS error" accessing API
```bash
# Check CORS is enabled in backend/api/api.py
# Frontend URL must be in CORS allowed origins
```

---

## 📊 Database Structure

```
PostgreSQL edupulse_db
├── schools (multi-tenant isolation)
├── users (proprietor, teachers, headmaster, kitchen)
├── students (per school)
├── student_grades (academic performance)
├── payments (tuition, feeding tracking)
├── attendance (daily attendance)
├── lesson_notes (teacher submissions)
├── academic_work_logs (classwork/homework)
├── report_card_status (approval workflow)
├── audit_logs (security/compliance)
├── inventory (canteen items)
└── support_tickets (user issues)
```

---

## 🔍 Monitoring & Logs

### Backend Logs
```bash
# Watch logs in real-time
tail -f backend.log

# Flask debug logs
FLASK_ENV=development FLASK_DEBUG=1 python -m flask run
```

### Database Logs
```bash
# PostgreSQL logs (Docker)
docker logs edupulse-db-1 -f

# Or view directly
tail -f /var/log/postgresql/postgresql.log
```

### Frontend Logs
```bash
# Browser console (DevTools)
# Ctrl+Shift+I → Console tab
```

---

## 🚀 Performance Tips

### Backend
```python
# Enable query result caching
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/api/students')
@cache.cached(timeout=300)
def get_students():
    return db.session.query(Student).all()
```

### Frontend
```javascript
// Minimize API requests - batch queries
const [students, teachers, payments] = await Promise.all([
  apiGet('/students'),
  apiGet('/teachers'),
  apiGet('/payments')
]);

// Use React.memo for expensive components
const MemoizedStudentList = React.memo(StudentList);
```

### Database
```sql
-- Create indexes on frequently queried fields
CREATE INDEX idx_student_school_id ON students(school_id);
CREATE INDEX idx_payment_student_id ON payments(student_id);
CREATE INDEX idx_grade_student_id ON student_grades(student_id);
```

---

## 📝 Useful Commands

```bash
# Database backup
pg_dump -U edupulse_user -d edupulse_db > backup.sql

# Database restore
psql -U edupulse_user -d edupulse_db < backup.sql

# Check database size
SELECT pg_size_pretty(pg_database_size('edupulse_db'));

# List all tables
\dt

# Exit PostgreSQL
\q
```

---

## 🆘 Support

For issues or questions:
1. Check [SECURITY.md](./SECURITY.md) for security-related setup
2. Review logs for error messages
3. Check GitHub issues or create new one
4. Contact: danielasareanyinam2020@gmail.com

---

**Last Updated:** February 12, 2026  
**Version:** 1.0 - Secure Setup Guide

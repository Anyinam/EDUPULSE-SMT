# EduPulse Firewall & Network Security Setup

## Current Status: ✅ Production-Safe Defaults

- Backend (Flask/Gunicorn): **Bound to 127.0.0.1:5000** (localhost only)
- Database (PostgreSQL): **Bound to 127.0.0.1:5433** (localhost only)
- Frontend (Vite): **Runs on 5173** (development only)

## Firewall Configuration

### For Development (Current Setup)

If you want to allow network access during development, configure UFW:

```bash
# 1. Enable UFW if not already enabled
sudo ufw enable

# 2. Set default policies (deny incoming, allow outgoing)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 3. Allow SSH (to avoid lockout)
sudo ufw allow 22/tcp

# 4. Allow development ports
sudo ufw allow 5000/tcp    # Backend API
sudo ufw allow 5173/tcp    # Frontend (Vite)
sudo ufw allow 5433/tcp    # Database (if needed from host)

# 5. View status
sudo ufw status verbose
```

### For Production (Recommended)

**Keep bindings as localhost-only** (default in updated `.env`):

```bash
# .env settings
BACKEND_BIND=127.0.0.1
DB_BIND=127.0.0.1

# UFW rules (if server needs SSH access)
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp         # SSH only
# No need to expose app ports if using reverse proxy
```

Then use a **reverse proxy** (Nginx/Apache) to handle external requests:

```nginx
# /etc/nginx/sites-available/edupulse
server {
    listen 80;
    listen [::]:80;
    server_name edupulse.yourdomain.com;

    location /api {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        # Serve frontend static files
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }
}
```

## Network Security Matrix

| Scenario | Backend | Database | Firewall | Notes |
|----------|---------|----------|----------|-------|
| **Local Development** | 127.0.0.1:5000 | 127.0.0.1:5433 | UFW disabled | ✅ Default |
| **Team Development** | 0.0.0.0:5000 (set ENV) | 127.0.0.1:5433 | UFW enabled | Requires BACKEND_BIND=0.0.0.0 |
| **Production (Secure)** | 127.0.0.1:5000 | 127.0.0.1:5433 | UFW enabled | ✅ Recommended |
| **Behind Reverse Proxy** | 127.0.0.1:5000 | 127.0.0.1:5433 (internal) | UFW enabled | ✅ Best practice |

## Changing Bindings

To enable network access during development:

```bash
# Edit .env
BACKEND_BIND=0.0.0.0
DB_BIND=0.0.0.0

# Restart containers
docker-compose down
docker-compose up --build
```

⚠️ **Warning:** Only use `0.0.0.0` in development networks you trust.

## Firewall Rules Summary

```bash
# View current rules
sudo ufw status numbered

# Delete a rule
sudo ufw delete <rule_number>

# Reset to defaults
sudo ufw reset

# Disable firewall (development only)
sudo sudo ufw disable
```

## Port Reference

| Port | Service | Binding | Default Status |
|------|---------|---------|-----------------|
| 22 | SSH | External | Not controlled by UFW setup |
| 5000 | Flask Backend | LOCALHOST | ✅ Production-safe |
| 5173 | Frontend (Dev) | localhost:5173 | Dev only |
| 5433 | PostgreSQL | LOCALHOST | ✅ Production-safe |

## CORS & Network Security

Even if ports are exposed to the network, **CORS is still restricted**:

```python
# backend/api/api.py
CORS(
    app,
    resources={
        r"/api/*": {"origins": ["localhost:3000", "localhost:5173", "127.0.0.1"]}
    },
    supports_credentials=True,
)
```

Requests from other domains will be rejected at the HTTP level.

## Verification

```bash
# Test backend is listening only on localhost
netstat -tulpn | grep 5000
# Expected: tcp 127.0.0.1:5000

# Test database is listening only on localhost
netstat -tulpn | grep 5433
# Expected: tcp 127.0.0.1:5433
```

## Security Checklist

- ✅ Backend bound to localhost by default
- ✅ Database bound to localhost by default
- ✅ CORS restricted to development origins
- ✅ JWT authentication required for API
- ✅ Firewall rules configurable via ENV
- ✅ Rate limiting enabled
- ⚠️ Consider HTTPS with reverse proxy for production
- ⚠️ Consider adding fail2ban for brute-force protection

---

For production deployment, consult [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)

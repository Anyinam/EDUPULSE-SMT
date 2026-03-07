# backend/settings.py
# Configuration for local development environment
import os

# Set to True to bypass role checks and allow access to all dashboards from localhost
# SECURITY: This should NEVER be True in production
ALLOW_ALL_DASHBOARDS = os.getenv("ALLOW_ALL_DASHBOARDS", "False").lower() == "true"

# API Configuration
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
RATE_LIMIT_AUTH = "5 per minute"  # Login/password reset attempts
RATE_LIMIT_API = "100 per hour"  # General API requests

# Security Configuration
JWT_ACCESS_TOKEN_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30"))
MAX_CONTENT_LENGTH_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", "10"))
AUTH_LOCKOUT_ATTEMPTS = int(os.getenv("AUTH_LOCKOUT_ATTEMPTS", "10"))
AUTH_LOCKOUT_WINDOW_MIN = int(os.getenv("AUTH_LOCKOUT_WINDOW_MIN", "15"))
AUTH_LOCKOUT_DURATION_MIN = int(os.getenv("AUTH_LOCKOUT_DURATION_MIN", "15"))
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
CSP_POLICY = os.getenv(
    "CSP_POLICY",
    "default-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'; "
    "img-src 'self' data:; "
    f"connect-src 'self' {FRONTEND_ORIGIN}; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'",
)

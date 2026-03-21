import os
import logging
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from flask_mail import Mail, Message
from werkzeug.security import check_password_hash, generate_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend import settings as app_settings
from backend.middleware import limiter, run_billing_enforcement_sweep

from .models import School, StudentGrade, User, db

load_dotenv()

app = Flask(__name__)
logger = logging.getLogger(__name__)


def _is_production_env() -> bool:
    return os.getenv("FLASK_ENV", "development").lower() == "production"


def _validate_security_configuration() -> None:
    is_production = _is_production_env()
    weak_values = {
        "change-me-in-production",
        "pisa-dev-key",
        "default-unsafe-key",
        "edupulse-dev-secret-key-change-in-production",
    }

    checks = {
        "JWT_SECRET_KEY": (os.getenv("JWT_SECRET_KEY") or "").strip(),
        "DATA_ENCRYPTION_KEY": (os.getenv("DATA_ENCRYPTION_KEY") or "").strip(),
        "LEDGER_SECRET_KEY": (os.getenv("LEDGER_SECRET_KEY") or "").strip(),
    }

    issues = []
    for name, value in checks.items():
        if not value:
            issues.append(f"{name} is not set")
            continue
        if value in weak_values:
            issues.append(f"{name} is using a known weak default")
        if len(value) < 32:
            issues.append(f"{name} is shorter than 32 characters")

    if issues:
        message = "; ".join(issues)
        if is_production:
            raise RuntimeError(f"Startup blocked due to insecure configuration: {message}")
        logger.warning("Security configuration warning (development): %s", message)


_validate_security_configuration()

# SECURITY: Strict CORS configuration
CORS(
    app,
    resources={
        r"/api/*": {"origins": ["localhost:3000", "localhost:5173", "127.0.0.1"]}
    },
    supports_credentials=True,
    max_age=3600,
)

# Configure database - use TEST_DATABASE_URL in testing, DATABASE_URL in production
db_url = os.getenv("TEST_DATABASE_URL") or os.getenv(
    "DATABASE_URL", "sqlite:///edupulse.db"
)

raw_database_url = os.getenv("DATABASE_URL", "")
is_strict_env = (os.getenv("FLASK_ENV", "development").lower() == "production")
if "dev_user" in raw_database_url:
    message = (
        "DATABASE_URL contains deprecated user 'dev_user'. "
        "Update DATABASE_URL to use 'edupulse_user' (or your valid DB user)."
    )
    if is_strict_env:
        raise RuntimeError(f"Startup blocked: {message}")
    logger.warning("Startup warning: %s", message)

if "try123" in raw_database_url:
    message = (
        "DATABASE_URL contains weak default password 'try123'. "
        "Set a strong database password in DATABASE_URL."
    )
    if is_strict_env:
        raise RuntimeError(f"Startup blocked: {message}")
    logger.warning("Startup warning: %s", message)


def _log_db_config(active_db_url: str) -> None:
    source = "TEST_DATABASE_URL" if os.getenv("TEST_DATABASE_URL") else "DATABASE_URL/default"
    try:
        parsed = urlparse(active_db_url)
        scheme = parsed.scheme or "unknown"
        username = parsed.username or "(none)"
        hostname = parsed.hostname or "(local)"
        database = (parsed.path or "").lstrip("/") or "(default)"

        if scheme.startswith("sqlite"):
            sqlite_target = active_db_url.replace("sqlite:///", "", 1)
            logger.info(
                "DB startup config | source=%s | dialect=sqlite | target=%s",
                source,
                sqlite_target or "edupulse.db",
            )
            return

        logger.info(
            "DB startup config | source=%s | dialect=%s | host=%s | db=%s | user=%s",
            source,
            scheme,
            hostname,
            database,
            username,
        )
    except Exception as exc:
        logger.warning("DB startup config parse failed: %s", exc)


_log_db_config(db_url)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
jwt_secret_key = (os.getenv("JWT_SECRET_KEY") or "").strip()
if not jwt_secret_key:
    jwt_secret_key = "local-dev-only-jwt-secret-change-me"
app.config["JWT_SECRET_KEY"] = jwt_secret_key
app.config["JWT_TOKEN_LOCATION"] = ["headers"]  # Only headers, not query strings
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
    minutes=app_settings.JWT_ACCESS_TOKEN_MINUTES
)
app.config["MAX_CONTENT_LENGTH"] = app_settings.MAX_CONTENT_LENGTH_MB * 1024 * 1024

# Email Configuration
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@edupulse.local")

app.config["SESSION_COOKIE_SECURE"] = True  # HTTPS only in production
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Initialize rate limiting
limiter.init_app(app)

# IMPORTANT: Initialize the DB with the App
db.init_app(app)

# Create tables if they don't exist (prevents 500 error on fresh start).
# Skip in tests where fixtures manage the database lifecycle.
if (
    os.getenv("ALLOW_CREATE_ALL") == "1"
    and os.getenv("ALEMBIC_RUNNING") != "1"
    and os.getenv("FLASK_ENV") != "testing"
):
    with app.app_context():
        db.create_all()

mail = Mail(app)
jwt = JWTManager(app)

# Initialize Background Scheduler for trial expiration jobs
scheduler = BackgroundScheduler()

# Schedule trial expiration check - runs daily at 2 AM
@scheduler.scheduled_job('cron', hour=2, minute=0, id='process_expired_trials')
def scheduled_process_expired_trials():
    """Scheduled job to process expired trials."""
    with app.app_context():
        from backend.trial_job import process_expired_trials
        result = process_expired_trials()
        import logging
        logging.getLogger(__name__).info(f"Scheduled trial expiration job result: {result}")

# Schedule trial reminder emails - runs daily at 9 AM
@scheduler.scheduled_job('cron', hour=9, minute=0, id='send_trial_reminders')
def scheduled_send_trial_reminders():
    """Scheduled job to send trial reminder emails."""
    with app.app_context():
        from backend.trial_job import send_trial_reminder_email
        result = send_trial_reminder_email(days_before_expiry=3)
        import logging
        logging.getLogger(__name__).info(f"Scheduled trial reminder job result: {result}")


@scheduler.scheduled_job('cron', hour=3, minute=0, id='billing_enforcement_sweep')
def scheduled_billing_enforcement_sweep():
    """Scheduled job to recalculate grace/overdue/suspended billing statuses."""
    with app.app_context():
        result = run_billing_enforcement_sweep(commit=True)
        logging.getLogger(__name__).info(
            "Scheduled billing enforcement sweep result: checked=%s updated=%s",
            result.get("checked"),
            result.get("updated"),
        )


@scheduler.scheduled_job('interval', minutes=15, id='overage_auto_charge_sweep')
def scheduled_overage_auto_charge_sweep():
    """Scheduled job to charge pending overage invoices after grace period."""
    with app.app_context():
        from backend.overage_billing_job import process_pending_overage_invoices

        result = process_pending_overage_invoices()
        logging.getLogger(__name__).info(
            "Scheduled overage auto-charge sweep result: checked=%s attempted=%s charged=%s failed=%s",
            result.get("checked"),
            result.get("attempted"),
            result.get("charged"),
            result.get("failed"),
        )


@scheduler.scheduled_job('cron', hour=2, minute=30, id='paystack_reconciliation_sweep')
def scheduled_paystack_reconciliation_sweep():
    """Scheduled job to recover successful Paystack transactions that never reached the local database."""
    with app.app_context():
        from backend.routes import run_paystack_reconciliation_sweep

        result = run_paystack_reconciliation_sweep(lookback_hours=24)
        logging.getLogger(__name__).info(
            "Scheduled Paystack reconciliation result: checked=%s recovered=%s duplicates=%s unmapped=%s errors=%s",
            result.get("checked"),
            result.get("recovered"),
            result.get("duplicate"),
            result.get("unmapped"),
            result.get("errors"),
        )

# Start scheduler if not already running
if not scheduler.running:
    try:
        scheduler.start()
        print("Background scheduler started for trial jobs")
    except Exception as e:
        print(f"Error starting background scheduler: {e}")



# Security Headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    response.headers["Content-Security-Policy"] = app_settings.CSP_POLICY
    return response


# Register Routes
from backend.routes import api as api_blueprint

app.register_blueprint(api_blueprint, url_prefix="/api")


@app.route("/")
def index():
    """Root endpoint to verify backend is running."""
    return jsonify({"message": "EduPulse SMT API is running", "version": "1.0.0"})


# GES 1-9 Grading Scale
def get_ges_grade(score):
    if score >= 80:
        return 1, "Highest"
    if score >= 70:
        return 2, "Higher"
    if score >= 60:
        return 3, "High"
    if score >= 55:
        return 4, "High Average"
    if score >= 50:
        return 5, "Average"
    if score >= 45:
        return 6, "Low Average"
    if score >= 40:
        return 7, "Low"
    if score >= 35:
        return 8, "Lower"
    return 9, "Lowest"


# Legacy function - disabled due to model changes
# def calculate_positions(class_name):
#     """Calculates rankings for a specific class based on total marks."""
#     students = StudentRecord.query.filter_by(class_name=class_name).all()
#
#     # 1. Create a list with calculated totals
#     scores = []
#     for s in students:
#         total = s.math + s.english + s.science
#         scores.append({'id': s.id, 'total': total})
#
#     # 2. Sort by total (Highest first)
#     scores.sort(key=lambda x: x['total'], reverse=True)
#
#     # 3. Assign positions (handles ties)
#     for index, item in enumerate(scores):
#         student = StudentRecord.query.get(item['id'])
#         student.position = index + 1
#         student.total_marks = item['total']
#         student.average = round(item['total'] / 3, 2)
#
#     db.session.commit()

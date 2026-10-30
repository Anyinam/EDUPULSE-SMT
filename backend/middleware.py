import logging
import os
import re
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.api.models import School, User, db
from backend.subscription_state import get_effective_plan
from backend.subscription_features import (
    ADDON_CATALOG,
    FEATURE_ADDON_REQUIREMENTS,
    PLAN_FEATURES,
    SUBSCRIPTION_TIERS,
    get_feature_level,
    get_plan_display_name,
    has_feature,
    get_school_feature_level,
)

logger = logging.getLogger(__name__)

DEFAULT_CSRF_ORIGINS = {
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "https://edupulse.edu",
    "http://edupulse.edu",
}

# Subscription enforcement windows
GRACE_PERIOD_DAYS = 7
OVERDUE_PERIOD_DAYS = 14

# Endpoints that must remain reachable for account recovery/payment.
BILLING_RECOVERY_PREFIXES = (
    "/api/school/subscription",
    "/api/paystack",
    "/api/payment",
    "/api/finance/paystack",
    "/api/help",
)

# Suspended schools retain limited read-only access to archived records so
# proprietors can review historical terms and billing evidence while resolving payment.
SUSPENDED_READONLY_PATHS = {
    "/api/finance/receipts",
    "/api/school/terms",
    "/api/school/terms/active",
    "/api/finance/summary",
    "/api/finance/transactions",
    "/api/finance/audit/ledger",
    "/api/finance/audit/summary",
    "/api/finance/audit/events",
    "/api/finance/audit/events/export",
}

SUSPENDED_READONLY_PATH_PATTERNS = (
    re.compile(r"^/api/students/\d+/payments$"),
    re.compile(r"^/api/students/\d+/terminal-report$"),
    re.compile(r"^/api/students/\d+/reports$"),
)


def _to_utc(dt_value):
    if dt_value is None:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc)


def _billing_restriction_payload(status_info, message):
    return {
        "message": message,
        "error": "billing_restriction",
        "redirect_to": "/proprietor?tab=subscription",
        "billing_status": status_info,
    }


def is_billing_recovery_path(path):
    return any(path.startswith(prefix) for prefix in BILLING_RECOVERY_PREFIXES)


def is_suspended_readonly_path(path, method):
    if (method or "GET").upper() not in {"GET", "HEAD"}:
        return False
    if path in SUSPENDED_READONLY_PATHS:
        return True
    return any(pattern.match(path or "") for pattern in SUSPENDED_READONLY_PATH_PATTERNS)


def _normalize_origin(value):
    candidate = (value or "").strip().rstrip("/")
    if not candidate:
        return ""

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _allowed_csrf_origins():
    allowed = set(DEFAULT_CSRF_ORIGINS)

    configured_origins = (os.getenv("CORS_ALLOWED_ORIGINS") or "").strip()
    if configured_origins:
        for origin in configured_origins.split(","):
            normalized = _normalize_origin(origin)
            if normalized:
                allowed.add(normalized)

    frontend_origin = _normalize_origin(os.getenv("FRONTEND_ORIGIN"))
    if frontend_origin:
        allowed.add(frontend_origin)

    return allowed


def get_billing_status_info(school, now=None):
    """Compute effective billing status from due dates and current school state."""
    status = (school.subscription_status or "Active").strip().title()
    now_utc = _to_utc(now or datetime.now(timezone.utc))
    due_date = _to_utc(school.next_billing_date)

    # Keep manual account deactivation as fully suspended.
    if not school.is_active:
        return {
            "status": "Suspended",
            "previous_status": status,
            "status_changed": status != "Suspended",
            "days_past_due": None,
            "next_billing_date": due_date.isoformat() if due_date else None,
            "reason": "account_inactive",
        }

    # Free tier has no recurring subscription enforcement.
    if (school.subscription_plan or "Free Tier") == "Free Tier":
        return {
            "status": "Active",
            "previous_status": status,
            "status_changed": status != "Active",
            "days_past_due": 0,
            "next_billing_date": due_date.isoformat() if due_date else None,
            "reason": "free_tier",
        }

    if due_date is None:
        return {
            "status": "Active",
            "previous_status": status,
            "status_changed": status != "Active",
            "days_past_due": 0,
            "next_billing_date": None,
            "reason": "no_due_date",
        }

    days_past_due = max(0, (now_utc.date() - due_date.date()).days)
    if days_past_due == 0:
        computed_status = "Active"
    elif days_past_due <= GRACE_PERIOD_DAYS:
        computed_status = "Grace"
    elif days_past_due <= OVERDUE_PERIOD_DAYS:
        computed_status = "Overdue"
    else:
        computed_status = "Suspended"

    return {
        "status": computed_status,
        "previous_status": status,
        "status_changed": computed_status != status,
        "days_past_due": days_past_due,
        "next_billing_date": due_date.isoformat() if due_date else None,
        "reason": "past_due" if days_past_due > 0 else "current",
    }


def refresh_school_billing_status(school, commit=False):
    """Persist computed billing status when it changes and return status details."""
    info = get_billing_status_info(school)
    if info["status_changed"]:
        school.subscription_status = info["status"]
        if commit:
            db.session.commit()
    return info


def enforce_school_billing_access(school):
    """Return a Flask response tuple when access must be restricted, else None."""
    status_info = refresh_school_billing_status(school, commit=True)
    g.billing_status = status_info

    path = request.path or ""
    if is_billing_recovery_path(path):
        return None

    method = (request.method or "GET").upper()
    status = status_info.get("status")

    # Suspended: lock almost all product access, keep billing flows available.
    if status == "Suspended":
        if is_suspended_readonly_path(path, method):
            return None
        return jsonify(
            _billing_restriction_payload(
                status_info,
                "Subscription is suspended due to unpaid billing. Complete payment to restore access.",
            )
        ), 402

    # Overdue: keep read-only access, block state-changing actions.
    if status == "Overdue" and method in {"POST", "PUT", "PATCH", "DELETE"}:
        return jsonify(
            _billing_restriction_payload(
                status_info,
                "Account is overdue. Read-only access is enabled until payment is completed.",
            )
        ), 402

    return None


def run_billing_enforcement_sweep(commit=True):
    """Recompute billing states for all paid-plan schools (for scheduled jobs)."""
    schools = School.query.filter(School.subscription_plan != "Free Tier").all()
    changed = 0
    for school in schools:
        status_info = get_billing_status_info(school)
        if status_info["status_changed"]:
            school.subscription_status = status_info["status"]
            changed += 1

    if commit and changed:
        db.session.commit()

    return {"checked": len(schools), "updated": changed}

# Load rate limit settings
try:
    from backend.settings import ALLOW_ALL_DASHBOARDS, RATE_LIMIT_ENABLED
except ImportError:
    ALLOW_ALL_DASHBOARDS = False
    RATE_LIMIT_ENABLED = True

def _rate_limit_key():
    # Staff in one school often share a NAT IP, so bucket signed-in users individually.
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
    except Exception:
        identity = None
    if identity is not None:
        return f"user:{identity}"
    return f"ip:{get_remote_address()}"


# The SPA polls dashboards and loads several endpoints per page, so the old
# 50/hour default throttled normal use and surfaced as locked/Free Tier screens.
# Use shared storage (e.g. redis://...) so limits hold across ECS tasks and gunicorn
# workers. Unset falls back to per-process memory. If the shared store is unreachable,
# limiting degrades to in-memory instead of failing requests.
RATE_LIMIT_STORAGE_URI = (os.getenv("RATELIMIT_STORAGE_URI") or "").strip() or "memory://"
if not RATE_LIMIT_STORAGE_URI.startswith(("memory://", "redis://", "rediss://")):
    # A malformed value (e.g. a JSON secret) must not stop the app from booting.
    logging.getLogger(__name__).warning(
        "RATELIMIT_STORAGE_URI must start with redis:// or rediss://; using in-memory rate limits."
    )
    RATE_LIMIT_STORAGE_URI = "memory://"
_shared_rate_limit_storage = not RATE_LIMIT_STORAGE_URI.startswith("memory://")

limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["20000 per day", "2000 per hour", "300 per minute"] if RATE_LIMIT_ENABLED else [],
    enabled=RATE_LIMIT_ENABLED,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    storage_options={"socket_connect_timeout": 2, "socket_timeout": 2} if _shared_rate_limit_storage else {},
    in_memory_fallback_enabled=_shared_rate_limit_storage,
    swallow_errors=_shared_rate_limit_storage,
    key_prefix="edupulse",
)


def multi_tenant_guard(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Extraction: Get the School-ID from the Header
        # Requirement: Identification of organization or business email
        school_id = request.headers.get("X-School-ID") or request.args.get("school_id")

        if not school_id:
            return jsonify({"message": "Organization ID missing"}), 400

        # 2. Security: Verify the school exists (Multi-level access control)
        school = School.query.get(school_id)
        if not school:
            return jsonify({"message": "Business entity not recognized"}), 404

        # 3. Isolation: Store school context in Flask's global 'g' object
        # This ensures all DB queries are filtered by this ID
        g.school_id = school_id

        # 4. Tenant binding (defense-in-depth): If a JWT is present, ensure it belongs
        # to the tenant specified by X-School-ID. This closes gaps where routes have
        # @jwt_required() but do not use @role_required().
        try:
            verify_jwt_in_request(optional=True)
            identity = get_jwt_identity()
        except Exception:
            # Token was provided but is invalid/expired.
            return jsonify({"message": "Authentication required"}), 401

        if identity is not None:
            try:
                user = User.query.get(int(identity))
            except Exception:
                user = None

            if not user:
                return jsonify({"message": "Authentication required"}), 401

            # Cache user for downstream decorators/handlers.
            g.current_user = user

            if str(user.school_id) != str(g.school_id):
                return (
                    jsonify(
                        {
                            "message": "Access denied: User does not belong to this school organization."
                        }
                    ),
                    403,
                )

        restriction = enforce_school_billing_access(school)
        if restriction:
            return restriction

        payload = request.get_json(silent=True) if (
            request.path.rstrip("/") == "/api/school/fees" and request.method == "POST"
        ) else None
        requirement = get_operational_entitlement(request.path, request.method, payload)
        if requirement:
            feature_name, min_level = requirement
            return feature_required(feature_name, min_level)(f)(*args, **kwargs)

        return f(*args, **kwargs)

    return decorated_function


def get_operational_entitlement(path, method, payload=None):
    """Return the entitlement for explicitly scoped operational routes."""
    path = (path or "").rstrip("/")
    method = (method or "GET").upper()
    if method == "OPTIONS":
        return None

    if method == "POST" and re.fullmatch(r"/api/homeroom/attendance(?:/[^/]+)?", path):
        return "attendance", "full_access"

    # Report Builder depends on entered grades, so it follows grade entry off the Free plan.
    # Reading a saved report (GET .../report/<id>) stays open for approval and view screens.
    if path in {
        "/api/homeroom/report-builder/students",
        "/api/homeroom/report-builder/submit",
        "/api/homeroom/class-subject-rankings",
    } or (method == "POST" and path == "/api/homeroom/report-builder/report") or path.startswith(
        "/api/homeroom/report-builder/auto-fill/"
    ):
        return "report_generation", True

    if method == "POST" and path == "/api/school/fees" and isinstance(payload, dict):
        if any(key in payload for key in {
            "feeding_fee", "feeding_daily_fee", "feeding_weekly_fee", "feeding_monthly_fee",
        }):
            return "feeding", "full_access"

    # Student CSV upload stays open on Free; the route itself enforces the plan's student cap.
    if method == "POST" and path in {
        "/api/admissions/students/bulk-update-status",
        "/api/staff/bulk-upload",
    }:
        return "bulk_operations", True

    if path == "/api/inventory" or path.startswith("/api/inventory/"):
        return "payment_tracking", True

    if method in {"GET", "HEAD"} and path in {
        "/api/staff/my-lesson-notes",
        "/api/headmaster/lesson-notes",
    }:
        return "lesson_notes", True

    if method == "POST" and (
        path == "/api/staff/lesson-note"
        or re.fullmatch(r"/api/headmaster/lesson-note/\d+/(?:review|rescore)", path)
    ):
        return "lesson_notes", True

    return None


def role_required(*allowed_roles):
    """
    Pillar 5: Multi-level access control.
    Restricts features (like Financial Ledger) based on user profile.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request()
            except Exception as e:
                print(f"JWT Auth Failed: {e}", flush=True)
                return jsonify({"message": "Authentication required"}), 401

            user_id = get_jwt_identity()
            user = getattr(g, "current_user", None)
            if not user or str(user.id) != str(user_id):
                user = User.query.get(int(user_id))

            # Allow access if DEV_MODE is enabled in settings.py, otherwise enforce role(s)
            user_roles = []
            if user:
                if isinstance(user.roles, list) and user.roles:
                    user_roles = user.roles
                elif user.role:
                    user_roles = [user.role]

            if "homeroom" in user_roles and "teacher" not in user_roles:
                user_roles = user_roles + ["teacher"]

            if (
                not user or not any(r in allowed_roles for r in user_roles)
            ) and not ALLOW_ALL_DASHBOARDS:
                return (
                    jsonify(
                        {
                            "message": f"Menu disabled: Access required for {allowed_roles}"
                        }
                    ),
                    403,
                )

            # Security Fix: Tenant Isolation
            # Ensure the authenticated user belongs to the school context requested
            if str(user.school_id) != str(g.school_id):
                return (
                    jsonify(
                        {
                            "message": "Access denied: User does not belong to this school organization."
                        }
                    ),
                    403,
                )

            if not hasattr(g, "billing_status"):
                school = School.query.get(g.school_id)
                if school:
                    restriction = enforce_school_billing_access(school)
                    if restriction:
                        return restriction

            return f(*args, **kwargs)

        return wrapper

    return decorator


def subscription_required(min_plan):
    """
    Enforces subscription tiers: Free Tier < Basic < Premium
    Supports per-school trial overrides.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Ensure context is loaded
            if not hasattr(g, "school_id"):
                return jsonify({"message": "School context missing"}), 400

            school = School.query.get(g.school_id)
            tiers = SUBSCRIPTION_TIERS

            effective_plan = get_effective_plan(school)

            if tiers.get(effective_plan, 0) < tiers.get(min_plan, 0):
                return (
                    jsonify(
                        {
                            "message": f"Feature requires {min_plan} plan. Current: {effective_plan}"
                        }
                    ),
                    403,
                )

            return f(*args, **kwargs)

        return wrapper

    return decorator


def feature_required(feature_name, min_level=True):
    """
    Enforces feature-level access based on subscription plan.

    Args:
        feature_name: Name of the feature to check
        min_level: Minimum access level ('basic', 'full_access', 'full', True for any access)
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not hasattr(g, "school_id"):
                return jsonify({"message": "School context missing"}), 400

            school = School.query.get(g.school_id)
            effective_plan = get_effective_plan(school)

            feature_level = get_school_feature_level(
                school, feature_name, effective_plan=effective_plan
            )

            # Check if feature is available
            if not feature_level:
                required_plan = get_required_plan_for_feature(feature_name)
                addon_key = FEATURE_ADDON_REQUIREMENTS.get(feature_name)
                required_access = get_plan_display_name(required_plan)
                if addon_key and effective_plan != "Free Tier":
                    addon_name = (ADDON_CATALOG.get(addon_key) or {}).get("name")
                    if addon_name:
                        required_access = f"{required_access} + {addon_name}"
                return (
                    jsonify(
                        {
                            "message": f"Feature '{feature_name}' not available in {effective_plan} plan",
                            "required_plan": required_access,
                            "current_plan": effective_plan,
                        }
                    ),
                    403,
                )

            # Check if access level meets requirement
            if min_level and min_level != True:
                access_levels = {
                    "view_only": 1,
                    "basic": 2,
                    "full_access": 3,
                    "full": 3,
                }
                required_level = access_levels.get(min_level, 0)
                current_level = access_levels.get(
                    feature_level, 3 if feature_level is True else 0
                )

                if current_level < required_level:
                    return (
                        jsonify(
                            {
                                "message": f"Insufficient access level for '{feature_name}'",
                                "required": min_level,
                                "current": feature_level,
                            }
                        ),
                        403,
                    )

            return f(*args, **kwargs)

        return wrapper

    return decorator

def get_required_plan_for_feature(feature_name):
    """Find minimum plan required for a feature"""
    if feature_name in FEATURE_ADDON_REQUIREMENTS:
        return "Basic"

    for plan_name in ["Free Tier", "Basic", "Premium"]:
        if has_feature(plan_name, feature_name):
            return plan_name
    return "Premium"


def check_quota(school, resource_type):
    """
    Check if school is within quota for a resource type.
    resource_type: 'classes', 'students', 'staff'

    Returns: (is_within_quota, current_count, limit)
    """
    from backend.api.models import AcademicClass, Student, User

    effective_plan = get_effective_plan(school)
    plan_info = PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["Free Tier"])

    if resource_type == "students":
        count = Student.query.filter_by(school_id=school.id).count()
        limit = plan_info.get("max_students", 50)
    elif resource_type == "classes":
        count = AcademicClass.query.filter_by(school_id=school.id).count()
        limit = plan_info.get("max_classes", 1)
    elif resource_type == "staff":
        count = User.query.filter(User.school_id == school.id, User.role != "proprietor").count()
        limit = plan_info.get("max_staff", 3)
    else:
        return (True, 0, 0)

    return (count < limit, count, limit)


def csrf_protect(f):
    """
    CSRF Protection for state-changing endpoints.
    For now, relies on SameSite cookie policy and verifies origin.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        # Only apply to POST, PUT, DELETE requests
        if request.method not in ["POST", "PUT", "DELETE"]:
            return f(*args, **kwargs)

        # Verify request origin
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")

        allowed_origins = _allowed_csrf_origins()
        normalized_origin = _normalize_origin(origin)
        normalized_referer = _normalize_origin(referer)
        is_same_origin = (
            normalized_origin in allowed_origins
            or normalized_referer in allowed_origins
        )

        # If cross-origin request detected from non-allowed origin
        if (origin or referer) and not is_same_origin:
            logger.warning(
                f"CSRF attempt detected from origin={origin}, referer={referer}"
            )
            return jsonify({"message": "CSRF validation failed"}), 403

        return f(*args, **kwargs)

    return wrapper


def rate_limit_auth(f):
    """Apply stricter rate limiting to authentication endpoints."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if RATE_LIMIT_ENABLED and not current_app.testing:
            return limiter.limit("5 per minute")(f)(*args, **kwargs)
        return f(*args, **kwargs)

    return wrapper


def rate_limit_api(f):
    """Apply standard rate limiting to API endpoints."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if RATE_LIMIT_ENABLED and not current_app.testing:
            return limiter.limit("60 per minute")(f)(*args, **kwargs)
        return f(*args, **kwargs)

    return wrapper

import logging
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from backend.api.models import School, User
from backend.subscription_features import (
    PLAN_FEATURES,
    SUBSCRIPTION_TIERS,
    get_feature_level,
    has_feature,
)

logger = logging.getLogger(__name__)

# Load rate limit settings
try:
    from backend.settings import ALLOW_ALL_DASHBOARDS, RATE_LIMIT_ENABLED
except ImportError:
    ALLOW_ALL_DASHBOARDS = False
    RATE_LIMIT_ENABLED = True

# Rate limiter instance - conditionally set default limits
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"] if RATE_LIMIT_ENABLED else [],
    enabled=RATE_LIMIT_ENABLED
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
        return f(*args, **kwargs)

    return decorated_function


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

            feature_level = get_feature_level(effective_plan, feature_name)

            # Check if feature is available
            if not feature_level:
                return (
                    jsonify(
                        {
                            "message": f"Feature '{feature_name}' not available in {effective_plan} plan",
                            "required_plan": get_required_plan_for_feature(
                                feature_name
                            ),
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


def get_effective_plan(school):
    """Get effective subscription plan, honoring trial overrides"""
    if not school:
        return "Free Tier"

    effective_plan = school.subscription_plan or "Free Tier"

    if school.trial_plan and school.trial_end_date:
        if datetime.now(timezone.utc) < school.trial_end_date:
            effective_plan = school.trial_plan

    return effective_plan


def get_required_plan_for_feature(feature_name):
    """Find minimum plan required for a feature"""
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
        count = User.query.filter_by(school_id=school.id).count()
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

        # List of allowed origins (support both domains and localhost with ports)
        allowed_origins = [
            "localhost",
            "127.0.0.1",
            "edupulse.edu",
            "localhost:3000",  # React frontend port
            "localhost:5173",  # Vite dev server alternate port
            "127.0.0.1:3000",
            "127.0.0.1:5173",
        ]

        # Check if origin/referer comes from an allowed source
        is_same_origin = False

        if origin:
            # Origin header check (e.g., "http://localhost:3000")
            is_same_origin = any(
                origin.endswith(
                    allowed
                )  # "http://localhost:3000".endswith("localhost:3000") ✓
                or origin.endswith(
                    allowed
                )  # "http://localhost".endswith("localhost") ✓
                or f"//{allowed}" in origin
                for allowed in allowed_origins
            )

        if referer and not is_same_origin:
            # Referer header check (e.g., "http://localhost:3000/login")
            is_same_origin = any(
                f"//{allowed}"
                in referer  # "http://localhost:3000/login" contains "//localhost:3000" ✓
                or referer.endswith(allowed)
                or f"{allowed}/" in referer
                for allowed in allowed_origins
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

"""
Subscription Feature Matrix & Enforcement
Defines what features are available in each subscription tier.
Pricing model (termly):
- Base platform fee per term
- Included students at no overage
- Per-student overage fee above the included threshold

Convenience fees do NOT apply to subscription charges.
"""

from datetime import datetime, timezone
from backend.subscription_state import get_effective_plan, normalize_plan_name

SUBSCRIPTION_TIERS = {"Free Tier": 0, "Basic": 1, "Premium": 2}

PLAN_DISPLAY_NAMES = {
    "Free Tier": "Free",
    "Basic": "School OS",
    "Premium": "School OS Plus",
}

ADDON_CATALOG = {
    "automation_pack": {
        "key": "automation_pack",
        "name": "Automation Pack",
        "price_per_term": 250,
        "eligible_plans": ["Basic", "Premium"],
        "module_keys": ["automation_pack_addon"],
        "description": "Automated MoMo and bank payment workflows for paid schools.",
    },
    "ai_pack": {
        "key": "ai_pack",
        "name": "AI Pack",
        "price_per_term": 200,
        "eligible_plans": ["Basic", "Premium"],
        "module_keys": ["ai_pack_addon"],
        "description": "Predictive insights, narratives, and AI-assisted academic workflows.",
    },
}

FEATURE_ADDON_REQUIREMENTS = {
    "ai_analysis": "ai_pack",
    "ai_narratives": "ai_pack",
    "student_rescue_agent": "ai_pack",
    "exam_intelligence": "ai_pack",
    "webhook_payment_automation": "automation_pack",
}

ADDON_FEATURE_LEVELS = {
    "ai_analysis": "full",
    "ai_narratives": True,
    "student_rescue_agent": True,
    "exam_intelligence": True,
    "webhook_payment_automation": True,
}

# Pricing model (3 terms per year)
PRICING = {
    "Free Tier": {"per_student_per_term": 0, "max_free_students": 50},
    "Basic": {
        "base_fee_per_term": 300,
        "included_students": 50,
        "per_student_per_term": 7,
        "per_student_per_term_range": "7",
    },
    "Premium": {
        "base_fee_per_term": 600,
        "included_students": 100,
        "per_student_per_term": 9,
        "per_student_per_term_range": "9",
    },
}

PLAN_FEATURES = {
    "Free Tier": {
        "max_classes": 1,
        "max_students": 50,
        "max_staff": 3,
        "report_templates": ["gradman_v1"],
        "ui_color": "gray",
        "features": {
            "attendance": "view_only",
            "feeding": "view_only",
            "lesson_notes": False,
            "exam_intelligence": False,
            "grade_entry": False,
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": False,
            "ai_narratives": False,
            "ai_registrar": False,
            "student_rescue_agent": False,
            "payment_tracking": False,
            "webhook_payment_automation": False,
            "advanced_analytics": False,
            "html_templates": False,
            "bulk_operations": False,
            "ai_bursar_addon_available": False,
            "communications_automation_addon_available": False,
        },
        "description": "Basic attendance & viewing for up to 50 students",
        "price": "Free (Up to 50 students)",
        "billing_cycle": "N/A",
        "marketing_features": [
            {"name": "Up to 50 students", "included": True},
            {"name": "1 class only", "included": True},
            {"name": "Attendance and feeding overview", "included": True, "note": "Read-only"},
            {"name": "Grade viewing", "included": True},
            {"name": "Basic report generation", "included": True, "note": "1 template"},
            {"name": "Student roster management", "included": True},
            {"name": "Payment tracking and reconciliation", "included": False},
            {"name": "AI Registrar admissions workflow", "included": False},
            {"name": "Advanced analytics", "included": False},
        ],
        "addon_options": [],
        "packaging_summary": "Free entry tier for early setup and light record keeping.",
    },
    "Basic": {
        "max_classes": 5,
        "max_students": 200,
        "max_staff": 15,
        "report_templates": [
            "gradman_v1",
            "parent_focus",
            "progress_insights",
            "compact_clear",
            "guardian_narrative",
            "classic_traditional",
        ],
        "ui_color": "blue",
        "features": {
            "attendance": "full_access",
            "feeding": "full_access",
            "lesson_notes": True,
            "exam_intelligence": False,
            "grade_entry": True,
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": False,
            "ai_narratives": False,
            "ai_registrar": True,
            "student_rescue_agent": False,
            "payment_tracking": True,
            "webhook_payment_automation": False,
            "advanced_analytics": False,
            "html_templates": False,
            "bulk_operations": True,
            "ai_bursar_addon_available": True,
            "communications_automation_addon_available": True,
        },
        "description": "Mass-market operating system for growing schools with up to 200 students.",
        "price": "300 GHS base + 7 GHS/student above 50/term",
        "price_range": "7 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "100 students: 300 + (50 x 7) = 650 GHS per term",
        "marketing_features": [
            {"name": "Up to 200 students", "included": True},
            {"name": "5 classes and 15 staff accounts", "included": True},
            {"name": "Full attendance, feeding, and grade operations", "included": True},
            {"name": "Payment tracking and reconciliation tools", "included": True},
            {"name": "Lesson notes and worklog", "included": True},
            {"name": "System alerts and student support tickets", "included": True},
            {"name": "6 report templates", "included": True},
            {"name": "AI Registrar admissions workflow", "included": True},
            {"name": "Automation Pack add-on", "included": False, "note": "Optional at GH₵250/term"},
            {"name": "AI Pack add-on", "included": False, "note": "Optional at GH₵200/term"},
        ],
        "addon_options": [
            "Automation Pack - GH₵250/term",
            "AI Pack - GH₵200/term",
        ],
        "packaging_summary": "School OS is the paid entry tier for day-to-day operations. Automation and advanced AI stay optional add-ons.",
        "popular": True,
    },
    "Premium": {
        "max_classes": float("inf"),
        "max_students": float("inf"),
        "max_staff": float("inf"),
        "report_templates": [
            "gradman_v1",
            "parent_focus",
            "progress_insights",
            "compact_clear",
            "guardian_narrative",
            "classic_traditional",
        ],
        "ui_color": "amber",
        "features": {
            "attendance": "full_access",
            "feeding": "full_access",
            "lesson_notes": True,
            "exam_intelligence": False,
            "grade_entry": True,
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": False,
            "ai_narratives": False,
            "ai_registrar": True,
            "student_rescue_agent": False,
            "payment_tracking": True,
            "webhook_payment_automation": False,
            "advanced_analytics": True,
            "html_templates": True,
            "bulk_operations": True,
            "ai_bursar_addon_available": True,
            "communications_automation_addon_available": True,
        },
        "description": "Advanced finance, analytics, and admin workflows for established schools.",
        "price": "600 GHS base + 9 GHS/student above 100/term",
        "price_range": "9 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "150 students: 600 + (50 x 9) = 1,050 GHS per term",
        "marketing_features": [
            {"name": "Unlimited students, classes, and staff", "included": True},
            {"name": "Everything in School OS", "included": True, "bold": True},
            {"name": "Advanced financial analytics and reconciliation", "included": True},
            {"name": "Custom HTML report templates", "included": True},
            {"name": "Priority support and stronger admin controls", "included": True},
            {"name": "Automation Pack add-on", "included": False, "note": "Optional at GH₵250/term"},
            {"name": "AI Pack add-on", "included": False, "note": "Optional at GH₵200/term"},
        ],
        "addon_options": [
            "Automation Pack - GH₵250/term",
            "AI Pack - GH₵200/term",
        ],
        "packaging_summary": "School OS Plus covers higher-governance operations. AI and payment automation remain optional so schools do not pay for tools they are not using.",
    },
}


def get_plan_display_name(plan_name):
    """Return the public-facing plan label for a stored plan key."""
    return PLAN_DISPLAY_NAMES.get(plan_name, plan_name)


def get_addons_for_plan(plan_name):
    """Return add-ons that can be purchased with a given paid plan."""
    if plan_name == "Free Tier":
        return []

    addons = []
    for addon in ADDON_CATALOG.values():
        if plan_name in addon.get("eligible_plans", []):
            addons.append(
                {
                    "key": addon["key"],
                    "name": addon["name"],
                    "price_per_term": addon["price_per_term"],
                    "description": addon["description"],
                }
            )
    return addons


def _enabled_modules_for_school(school):
    settings = getattr(school, "settings", None)
    modules = getattr(settings, "enabled_modules", None) if settings else None
    return modules if isinstance(modules, dict) else {}


def _is_active_premium_trial(school, effective_plan=None):
    if not school or normalize_plan_name(getattr(school, "trial_plan", None)) != "Premium":
        return False

    trial_end = getattr(school, "trial_end_date", None)
    if not trial_end:
        return False
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)

    plan_name = normalize_plan_name(effective_plan) if effective_plan else get_effective_plan(school)
    return plan_name == "Premium" and datetime.now(timezone.utc) < trial_end


def school_has_addon(school, addon_key, effective_plan=None):
    """Return True if a school can use a paid add-on under its current plan."""
    plan_name = normalize_plan_name(effective_plan) if effective_plan else get_effective_plan(school)
    addon = ADDON_CATALOG.get(addon_key)
    if not school or not addon or plan_name not in addon.get("eligible_plans", []):
        return False

    if _is_active_premium_trial(school, effective_plan=plan_name):
        return True

    modules = _enabled_modules_for_school(school)
    return any(bool(modules.get(module_key, False)) for module_key in addon.get("module_keys", []))


def get_school_feature_level(school, feature_name, effective_plan=None):
    """Resolve plan and add-on restrictions for a school's feature access."""
    plan_name = normalize_plan_name(effective_plan) if effective_plan else get_effective_plan(school)
    addon_requirement = FEATURE_ADDON_REQUIREMENTS.get(feature_name)
    if addon_requirement:
        if school_has_addon(school, addon_requirement, effective_plan=plan_name):
            return ADDON_FEATURE_LEVELS.get(feature_name, True)
        return False

    return get_feature_level(plan_name, feature_name)


def school_has_feature(school, feature_name, effective_plan=None):
    """Check whether a school can access a feature after add-on rules are applied."""
    feature_value = get_school_feature_level(school, feature_name, effective_plan=effective_plan)
    return feature_value not in [False, None]



def get_term_cost_breakdown(plan_name, num_students):
    """Return transparent term billing breakdown for a subscription plan."""
    pricing = PRICING.get(plan_name, {})

    if plan_name == "Free Tier" or not pricing:
        return {
            "base_fee": 0.0,
            "included_students": 0,
            "billable_students": 0,
            "per_student_rate": 0.0,
            "student_overage_cost": 0.0,
            "convenience_fee": 0.0,
            "total": 0.0,
        }

    normalized_students = max(0, int(num_students or 0))
    base_fee = float(pricing.get("base_fee_per_term", 0) or 0)
    included_students = int(pricing.get("included_students", 0) or 0)
    per_student_rate = float(pricing.get("per_student_per_term", 0) or 0)
    billable_students = max(0, normalized_students - included_students)
    student_overage_cost = billable_students * per_student_rate
    total = base_fee + student_overage_cost

    return {
        "base_fee": round(base_fee, 2),
        "included_students": included_students,
        "billable_students": billable_students,
        "per_student_rate": round(per_student_rate, 2),
        "student_overage_cost": round(student_overage_cost, 2),
        "convenience_fee": 0.0,
        "total": round(total, 2),
    }



def calculate_term_cost(plan_name, num_students):
    """Calculate the billed term cost for a plan at a given student count."""
    return get_term_cost_breakdown(plan_name, num_students).get("total", 0.0)



def calculate_annual_cost(plan_name, num_students):
    """Calculate the annual cost (3 terms) based on plan and number of students."""
    return calculate_term_cost(plan_name, num_students) * 3



def get_plan_limit(plan_name, limit_type):
    """Get a specific limit for a plan."""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get(f"max_{limit_type}", 0)



def has_feature(plan_name, feature_name):
    """Check if plan has a feature enabled."""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    feature_value = plan.get("features", {}).get(feature_name, False)
    return feature_value not in [False, None]



def get_feature_level(plan_name, feature_name):
    """Get the access level for a feature."""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get("features", {}).get(feature_name, False)



def can_access_report_template(plan_name, template_id):
    """Check if plan can access a specific report template."""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return template_id in plan.get("report_templates", [])



def get_all_accessible_templates(plan_name):
    """Get all report templates accessible to a plan."""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get("report_templates", [])


FEATURE_MATRIX_DISPLAY = {
    "Free Tier": {
        "max_classes": "1 Class",
        "max_students": "50 Students",
        "attendance": "No Edit Access",
        "feeding": "No Edit Access",
        "grade_entry": "Not Available",
        "lesson_notes": "Not Available",
        "report_generation": "1 Template",
        "ai_features": "Not Available",
        "payment_tracking": "Not Available",
        "html_templates": "Not Available",
    },
    "Basic": {
        "max_classes": "5 Classes",
        "max_students": "200 Students",
        "attendance": "Full Access",
        "feeding": "Full Access",
        "grade_entry": "Full Access",
        "lesson_notes": "Full Access",
        "report_generation": "6 Templates",
        "ai_features": "AI Pack Optional",
        "payment_tracking": "Basic Tracking",
        "html_templates": "Not Available",
    },
    "Premium": {
        "max_classes": "Unlimited",
        "max_students": "Unlimited",
        "attendance": "Full Access",
        "feeding": "Full Access",
        "grade_entry": "Full Access",
        "lesson_notes": "Full Access",
        "report_generation": "All Templates",
        "ai_features": "AI Pack Optional",
        "payment_tracking": "Advanced Reconciliation",
        "html_templates": "Custom Upload",
    },
}

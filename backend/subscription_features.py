"""
Subscription Feature Matrix & Enforcement
Defines what features are available in each subscription tier.
Pricing model (termly):
- Base platform fee per term
- Included students at no overage
- Per-student overage fee above the included threshold

Convenience fees do NOT apply to subscription charges.
"""

SUBSCRIPTION_TIERS = {"Free Tier": 0, "Basic": 1, "Premium": 2}

# Pricing model (3 terms per year)
PRICING = {
    "Free Tier": {"per_student_per_term": 0, "max_free_students": 50},
    "Basic": {
        "base_fee_per_term": 360,
        "included_students": 30,
        "per_student_per_term": 12,
        "per_student_per_term_range": "10-15",
    },
    "Premium": {
        "base_fee_per_term": 750,
        "included_students": 30,
        "per_student_per_term": 22,
        "per_student_per_term_range": "22",
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
            {"name": "Manual grade entry", "included": True},
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
            "ai_analysis": "basic",
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
        "description": "Full operations with up to 200 students, 5 classes",
        "price": "360 GHS base + 12 GHS/student above 30/term",
        "price_range": "10-15 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "100 students: 360 + (70 x 12) = 1,200 GHS per term",
        "marketing_features": [
            {"name": "Up to 200 students", "included": True},
            {"name": "5 classes and 15 staff accounts", "included": True},
            {"name": "Full attendance, feeding, and grade operations", "included": True},
            {"name": "Payment tracking and reconciliation tools", "included": True},
            {"name": "Lesson notes and worklog", "included": True},
            {"name": "System alerts and student support tickets", "included": True},
            {"name": "6 report templates", "included": True},
            {"name": "AI Registrar admissions workflow", "included": True},
            {"name": "AI-generated narratives", "included": False, "note": "Premium only"},
            {"name": "Webhook payment automation", "included": False, "note": "Premium only"},
            {"name": "Student Rescue Agent", "included": False, "note": "Premium only"},
        ],
        "addon_options": [
            "AI Bursar Add-on",
            "Communications Automation Add-on",
        ],
        "packaging_summary": "AI Registrar is bundled into Basic. Future workflow workers stay optional add-ons.",
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
            "exam_intelligence": True,
            "grade_entry": True,
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": "full",
            "ai_narratives": True,
            "ai_registrar": True,
            "student_rescue_agent": True,
            "payment_tracking": True,
            "webhook_payment_automation": True,
            "advanced_analytics": True,
            "html_templates": True,
            "bulk_operations": True,
            "ai_bursar_addon_available": True,
            "communications_automation_addon_available": True,
        },
        "description": "Unlimited access to all features with AI-powered insights",
        "price": "750 GHS base + 22 GHS/student above 30/term",
        "price_range": "22 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "100 students: 750 + (70 x 22) = 2,290 GHS per term",
        "marketing_features": [
            {"name": "Unlimited students, classes, and staff", "included": True},
            {"name": "Everything in Basic", "included": True, "bold": True},
            {"name": "AI Registrar admissions workflow", "included": True},
            {"name": "Student Rescue Agent bundled", "included": True},
            {"name": "AI-generated narratives and predictive scoring", "included": True},
            {"name": "Academic plus financial correlation analysis", "included": True},
            {"name": "Webhook payment automation", "included": True},
            {"name": "Advanced financial analytics and reconciliation", "included": True},
            {"name": "Custom HTML report templates", "included": True},
            {"name": "Priority support", "included": True},
        ],
        "addon_options": [
            "AI Bursar Add-on",
            "Communications Automation Add-on",
        ],
        "packaging_summary": "Premium bundles AI Registrar plus the broader AI and governance stack.",
    },
}


def calculate_term_cost(plan_name, num_students):
    """Calculate the cost for a term based on plan and number of students."""
    breakdown = get_term_cost_breakdown(plan_name, num_students)
    return breakdown["total"]



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
        "ai_features": "Basic AI Feedback",
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
        "ai_features": "Full AI Suite",
        "payment_tracking": "Full Reconciliation",
        "html_templates": "Custom Upload",
    },
}

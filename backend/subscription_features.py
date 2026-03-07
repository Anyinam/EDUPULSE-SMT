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
    "Free Tier": {"per_student_per_term": 0, "max_free_students": 100},
    "Basic": {
        "base_fee_per_term": 360,
        "included_students": 30,
        "per_student_per_term": 12,
        "per_student_per_term_range": "10-15",
    },
    "Premium": {
        "base_fee_per_term": 510,
        "included_students": 30,
        "per_student_per_term": 17,
        "per_student_per_term_range": "15-20",
    },
}

PLAN_FEATURES = {
    "Free Tier": {
        "max_classes": 1,
        "max_students": 50,
        "max_staff": 3,
        "report_templates": ["gradman_v1"],  # Only basic template
        "features": {
            "attendance": "view_only",  # Can view but not edit
            "feeding": "view_only",  # Can view but not edit
            "lesson_notes": False,  # Cannot access
            "grade_entry": False,  # Cannot edit grades
            "grade_viewing": True,  # Can view grades
            "report_generation": True,  # Can generate reports (limited templates)
            "ai_analysis": False,  # No AI features
            "ai_narratives": False,  # No grade narratives
            "payment_tracking": False,  # No payment features
            "advanced_analytics": False,  # No advanced analytics
            "html_templates": False,  # Cannot upload HTML
            "bulk_operations": False,  # No bulk attendance/feeding
        },
        "description": "Basic attendance & viewing for up to 50 students",
        "price": "Free (Up to 50 students)",
        "billing_cycle": "N/A",
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
        ],
        "features": {
            "attendance": "full_access",  # Full read/write
            "feeding": "full_access",  # Full read/write
            "lesson_notes": True,  # Can create and manage
            "grade_entry": True,  # Can enter and edit grades
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": "basic",  # Basic AI feedback on lesson notes
            "ai_narratives": False,  # No grade narratives (Premium feature)
            "payment_tracking": True,  # Basic payment recording
            "advanced_analytics": False,  # No advanced analytics
            "html_templates": False,  # Cannot upload HTML
            "bulk_operations": True,  # Can do bulk operations
        },
        "description": "Full operations with up to 200 students, 5 classes",
        "price": "200 GHS base + 12 GHS/student above 25/term",
        "price_range": "10-15 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "100 students: 200 + (75 × 12) = 1,100 GHS per term",
    },
    "Premium": {
        "max_classes": float("inf"),  # Unlimited
        "max_students": float("inf"),  # Unlimited
        "max_staff": float("inf"),  # Unlimited
        "report_templates": [
            "gradman_v1",
            "parent_focus",
            "progress_insights",
            "compact_clear",
            "guardian_narrative",
        ],
        "features": {
            "attendance": "full_access",
            "feeding": "full_access",
            "lesson_notes": True,
            "grade_entry": True,
            "grade_viewing": True,
            "report_generation": True,
            "ai_analysis": "full",  # Full AI analysis & scoring
            "ai_narratives": True,  # AI-generated grade narratives
            "payment_tracking": True,  # Full payment reconciliation
            "advanced_analytics": True,  # Full analytics dashboard
            "html_templates": True,  # Can upload custom HTML templates
            "bulk_operations": True,
        },
        "description": "Unlimited access to all features with AI-powered insights",
        "price": "510 GHS base + 17 GHS/student above 30/term",
        "price_range": "15-20 GHS/student/term",
        "billing_cycle": "per term (3 terms/year)",
        "example_cost": "100 students: 510 + (70 × 17) = 1,700 GHS per term",
    },
}


def calculate_term_cost(plan_name, num_students):
    """Calculate the cost for a term based on plan and number of students."""
    breakdown = get_term_cost_breakdown(plan_name, num_students)
    return breakdown["total"]


def get_term_cost_breakdown(plan_name, num_students):
    """Return transparent term billing breakdown for a subscription plan.

    Returns:
        {
            "base_fee": float,
            "included_students": int,
            "billable_students": int,
            "per_student_rate": float,
            "student_overage_cost": float,
            "convenience_fee": float,
            "total": float,
        }
    """
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
    """Get a specific limit for a plan"""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get(f"max_{limit_type}", 0)


def has_feature(plan_name, feature_name):
    """Check if plan has a feature enabled"""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    feature_value = plan.get("features", {}).get(feature_name, False)
    # Return True if feature is enabled (True, 'basic', 'full_access', 'view_only')
    return feature_value not in [False, None]


def get_feature_level(plan_name, feature_name):
    """Get the access level for a feature (False, 'view_only', 'basic', 'full_access', 'full', True)"""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get("features", {}).get(feature_name, False)


def can_access_report_template(plan_name, template_id):
    """Check if plan can access a specific report template"""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return template_id in plan.get("report_templates", [])


def get_all_accessible_templates(plan_name):
    """Get all report templates accessible to a plan"""
    plan = PLAN_FEATURES.get(plan_name, PLAN_FEATURES["Free Tier"])
    return plan.get("report_templates", [])


# Feature matrix display
FEATURE_MATRIX_DISPLAY = {
    "Free Tier": {
        "max_classes": "1 Class",
        "max_students": "100 Students",
        "attendance": "❌ View Only",
        "feeding": "❌ View Only",
        "grade_entry": "❌ Not Available",
        "lesson_notes": "❌ Not Available",
        "report_generation": "✅ (1 Template)",
        "ai_features": "❌ Not Available",
        "payment_tracking": "❌ Not Available",
        "html_templates": "❌ Not Available",
    },
    "Basic": {
        "max_classes": "5 Classes",
        "max_students": "200 Students",
        "attendance": "✅ Full Access",
        "feeding": "✅ Full Access",
        "grade_entry": "✅ Full Access",
        "lesson_notes": "✅ Full Access",
        "report_generation": "✅ (5 Templates)",
        "ai_features": "⚡ Basic AI Feedback",
        "payment_tracking": "✅ Basic Tracking",
        "html_templates": "❌ Not Available",
    },
    "Premium": {
        "max_classes": "♾️ Unlimited",
        "max_students": "♾️ Unlimited",
        "attendance": "✅ Full Access",
        "feeding": "✅ Full Access",
        "grade_entry": "✅ Full Access",
        "lesson_notes": "✅ Full Access",
        "report_generation": "✅ (All Templates)",
        "ai_features": "⚡⚡ Full AI Suite",
        "payment_tracking": "✅ Full Reconciliation",
        "html_templates": "✅ Custom Upload",
    },
}

from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.api.models import AcademicTerm, School, Student, db
from backend.subscription_state import get_effective_plan, normalize_utc_datetime, now_utc
from backend.subscription_features import PRICING, PLAN_FEATURES


TRIAL_DURATION_DAYS = 30

NATIONAL_BASIC_TERM_CALENDARS = {
    "2026/2027": [
        {
            "name": "Term 1",
            "start_date": date(2026, 9, 8),
            "end_date": date(2026, 12, 17),
        },
        {
            "name": "Term 2",
            "start_date": date(2027, 1, 5),
            "end_date": date(2027, 3, 25),
        },
        {
            "name": "Term 3",
            "start_date": date(2027, 4, 20),
            "end_date": date(2027, 7, 22),
        },
    ],
}

LEGACY_NATIONAL_BASIC_TERM_STARTS = {
    "Term 1": (9, 9),
    "Term 2": (1, 7),
    "Term 3": (5, 7),
}

def _now_utc() -> datetime:
    return now_utc()


def _normalize_dt(dt_value: datetime | None) -> datetime | None:
    return normalize_utc_datetime(dt_value)


def _build_national_basic_term_windows(academic_year_start: int) -> list[dict[str, Any]]:
    academic_year = f"{academic_year_start}/{academic_year_start + 1}"
    published_calendar = get_published_national_basic_term_windows(academic_year)
    if published_calendar:
        return published_calendar

    term_1_start = date(academic_year_start, *LEGACY_NATIONAL_BASIC_TERM_STARTS["Term 1"])
    term_2_start = date(academic_year_start + 1, *LEGACY_NATIONAL_BASIC_TERM_STARTS["Term 2"])
    term_3_start = date(academic_year_start + 1, *LEGACY_NATIONAL_BASIC_TERM_STARTS["Term 3"])

    return [
        {
            "name": "Term 1",
            "academic_year": academic_year,
            "start_date": term_1_start,
            "end_date": term_2_start - timedelta(days=1),
            "source": "national_basic_default",
        },
        {
            "name": "Term 2",
            "academic_year": academic_year,
            "start_date": term_2_start,
            "end_date": term_3_start - timedelta(days=1),
            "source": "national_basic_default",
        },
        {
            "name": "Term 3",
            "academic_year": academic_year,
            "start_date": term_3_start,
            "end_date": term_3_start + timedelta(days=119),
            "source": "national_basic_default",
        },
    ]


def get_published_national_basic_term_windows(academic_year: str) -> list[dict[str, Any]]:
    published_calendar = NATIONAL_BASIC_TERM_CALENDARS.get(academic_year)
    if not published_calendar:
        return []

    enriched_terms: list[dict[str, Any]] = []
    for index, term_window in enumerate(published_calendar):
        next_term = published_calendar[index + 1] if index + 1 < len(published_calendar) else None
        enriched_terms.append(
            {
                **term_window,
                "academic_year": academic_year,
                "source": "national_basic_calendar",
                "reopening_date": next_term["start_date"] if next_term else None,
            }
        )
    return enriched_terms


def get_next_published_national_basic_term_start(current_date: date) -> date | None:
    future_starts = [
        term_window["start_date"]
        for academic_year in NATIONAL_BASIC_TERM_CALENDARS
        for term_window in get_published_national_basic_term_windows(academic_year)
        if term_window["start_date"] > current_date
    ]
    return min(future_starts) if future_starts else None


def get_recommended_published_national_basic_academic_year(current_date: date | None = None) -> str | None:
    today = current_date or _now_utc().date()
    published_years = sorted(NATIONAL_BASIC_TERM_CALENDARS.keys())
    if not published_years:
        return None

    for academic_year in published_years:
        term_windows = get_published_national_basic_term_windows(academic_year)
        if any(term_window["start_date"] <= today <= term_window["end_date"] for term_window in term_windows):
            return academic_year

    future_candidates: list[tuple[date, str]] = []
    past_candidates: list[tuple[date, str]] = []
    for academic_year in published_years:
        term_windows = get_published_national_basic_term_windows(academic_year)
        if not term_windows:
            continue
        first_start = term_windows[0]["start_date"]
        if first_start >= today:
            future_candidates.append((first_start, academic_year))
        else:
            past_candidates.append((first_start, academic_year))

    if future_candidates:
        future_candidates.sort()
        return future_candidates[0][1]

    if past_candidates:
        past_candidates.sort()
        return past_candidates[-1][1]

    return published_years[-1]


def _get_national_basic_term_reference(current_date: date | None = None) -> dict[str, Any] | None:
    today = current_date or _now_utc().date()
    for academic_year_start in range(today.year - 1, today.year + 2):
        for term_window in _build_national_basic_term_windows(academic_year_start):
            if term_window["start_date"] <= today <= term_window["end_date"]:
                return term_window
    return None


def _term_reference_to_end_datetime(term_reference: dict[str, Any] | None) -> datetime | None:
    if not term_reference or not term_reference.get("end_date"):
        return None
    end_date = term_reference["end_date"]
    return datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59, tzinfo=timezone.utc)


def _trial_start_from_end(trial_end: datetime | None) -> datetime | None:
    normalized_end = _normalize_dt(trial_end)
    if not normalized_end:
        return None
    return normalized_end - timedelta(days=TRIAL_DURATION_DAYS)


def get_current_term_reference(school_id: str) -> dict[str, Any] | None:
    today = _now_utc().date()
    active_term = AcademicTerm.query.filter_by(school_id=school_id, is_active=True).first()

    if active_term and active_term.start_date and active_term.end_date:
        if active_term.start_date <= today <= active_term.end_date:
            return {
                "name": active_term.name,
                "academic_year": active_term.academic_year,
                "start_date": active_term.start_date,
                "end_date": active_term.end_date,
                "source": "school_active_term",
            }

    return _get_national_basic_term_reference(today)


def _get_active_term_trial_end(school_id: str) -> tuple[datetime | None, AcademicTerm | None]:
    active_term = AcademicTerm.query.filter_by(school_id=school_id, is_active=True).first()
    term_reference = get_current_term_reference(school_id) or {}
    return _term_reference_to_end_datetime(term_reference), active_term


def get_term_proration_context(school_id: str, now: datetime | None = None) -> dict[str, Any]:
    now_utc = _normalize_dt(now) or _now_utc()
    term_reference = get_current_term_reference(school_id) or {}
    term_end = _term_reference_to_end_datetime(term_reference)

    if not term_reference or not term_end:
        return {
            "days_remaining": None,
            "days_in_term": None,
            "proration_ratio": 1.0,
            "term_name": None,
            "academic_year": None,
            "reference_source": None,
            "term_end_date": None,
        }

    start_date = term_reference.get("start_date")
    days_in_term = max(1, ((term_reference["end_date"] - start_date).days + 1) if start_date else 120)
    days_remaining = max(1, (term_end.date() - now_utc.date()).days + 1)
    proration_ratio = max(0.0, min(1.0, days_remaining / float(days_in_term)))

    return {
        "days_remaining": days_remaining,
        "days_in_term": days_in_term,
        "proration_ratio": round(proration_ratio, 6),
        "term_name": term_reference.get("name"),
        "academic_year": term_reference.get("academic_year"),
        "reference_source": term_reference.get("source"),
        "term_end_date": term_end.isoformat(),
    }


def _get_plan_pricing(school: School) -> dict[str, Any]:
    default_pricing = PRICING.get(school.subscription_plan or "Free Tier", {})
    return {
        "base_fee": school.custom_base_fee if school.custom_base_fee is not None else float(default_pricing.get("base_fee_per_term", 0) or 0),
        "included_students": school.custom_included_students if school.custom_included_students is not None else int(default_pricing.get("included_students", 0) or 0),
        "overage_rate": school.custom_overage_rate if school.custom_overage_rate is not None else float(default_pricing.get("per_student_per_term", 0) or 0),
    }


def ensure_trial_expiry(school: School, commit: bool = False) -> bool:
    trial_end = _normalize_dt(school.trial_end_date)
    if school.trial_plan and trial_end and _now_utc() >= trial_end:
        school.trial_plan = None
        school.is_trial_active = False
        if commit:
            db.session.commit()
        return True
    return False


def sync_student_meter(school: School, commit: bool = True) -> int:
    active_students = Student.query.filter(
        Student.school_id == school.id,
        Student.status.in_(["Active", "active"]),
    ).count()
    school.current_student_count = active_students
    school.last_metered_at = _now_utc()
    if commit:
        db.session.commit()
    return active_students


def get_billing_visibility(school_id: str, commit: bool = True) -> dict[str, Any]:
    school = School.query.get(school_id)
    if not school:
        return {"error": "School not found"}

    trial_reference = get_current_term_reference(school.id)
    ensure_trial_expiry(school, commit=False)
    active_students = sync_student_meter(school, commit=False)
    trial_start = _trial_start_from_end(school.trial_end_date)
    effective_plan = get_effective_plan(school)

    pricing = _get_plan_pricing(school)
    plan_info = PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["Free Tier"])
    
    included = max(0, int(pricing["included_students"] or 0))
    max_students = plan_info.get("max_students", 50)
    
    # Calculate usage based on PLAN LIMIT, not included students
    if max_students == float("inf"):
        # Premium: unlimited
        usage_percent = 0.0  # Never at capacity
        capacity_display = "∞ Unlimited"
    else:
        usage_percent = round((active_students / max_students) * 100, 2) if max_students > 0 else 0.0
        capacity_display = f"{max_students}"
    
    # Alert based on plan limit, not included students
    if max_students == float("inf"):
        alert_level = "ok"
        alert_message = "Unlimited capacity available."
    elif active_students >= max_students:
        alert_level = "critical"
        alert_message = f"Over Capacity - You have {active_students} students but limit is {max_students}. Upgrade to add more."
    elif usage_percent >= 80:
        alert_level = "warning"
        alert_message = f"Approaching Capacity Limit ({usage_percent:.1f}% used)"
    else:
        alert_level = "ok"
        alert_message = f"Within plan limit. {max_students - active_students} students available."

    overage_students = max(0, active_students - included)
    overage_cost = round(overage_students * float(pricing["overage_rate"] or 0), 2)
    total_due = round(float(pricing["base_fee"] or 0) + overage_cost, 2)

    if commit:
        db.session.commit()

    return {
        "school_id": school.id,
        "plan": effective_plan,
        "base_plan": school.subscription_plan or "Free Tier",
        "plan_version": school.plan_version,
        "pricing_locked": bool(school.pricing_locked_at),
        "pricing_locked_at": school.pricing_locked_at.isoformat() if school.pricing_locked_at else None,
        "trial": {
            "active": bool(school.trial_plan and school.trial_end_date),
            "is_active": bool(school.trial_plan and school.trial_end_date),
            "plan": school.trial_plan,
            "start_date": trial_start.isoformat() if trial_start else None,
            "end_date": school.trial_end_date.isoformat() if school.trial_end_date else None,
            "term_name": trial_reference.get("name") if trial_reference else None,
            "academic_year": trial_reference.get("academic_year") if trial_reference else None,
            "reference_source": trial_reference.get("source") if trial_reference else None,
        },
        "meter": {
            "current_count": active_students,
            "active_students": active_students,
            "plan_limit": max_students if max_students != float("inf") else None,  # None for unlimited
            "included_students": included,
            "overage_students": overage_students,
            "usage_percent": usage_percent,
            "last_synced": school.last_metered_at.isoformat() if school.last_metered_at else None,
            "last_metered_at": school.last_metered_at.isoformat() if school.last_metered_at else None,
            "alert": {
                "level": alert_level,
                "title": "Over Capacity" if alert_level == "critical" else ("Approaching Capacity" if alert_level == "warning" else "Healthy Capacity"),
                "message": alert_message,
            },
        },
        "pricing": {
            "base_fee": round(float(pricing["base_fee"] or 0), 2),
            "included_students": included,
            "overage_rate": round(float(pricing["overage_rate"] or 0), 2),
            "version": school.plan_version,
        },
        "cost_breakdown": {
            "base_fee": round(float(pricing["base_fee"] or 0), 2),
            "overage_students": overage_students,
            "overage_rate": round(float(pricing["overage_rate"] or 0), 2),
            "overage_cost": overage_cost,
            "total_due": total_due,
        },
    }


def activate_premium_trial(school_id: str, trial_plan: str = "Premium", days: int | None = None) -> dict[str, Any]:
    school = School.query.get(school_id)
    if not school:
        return {"error": "School not found"}

    if trial_plan not in {"Basic", "Premium"}:
        return {"error": "Trial plan must be School OS or School OS Plus"}

    ensure_trial_expiry(school, commit=False)
    if school.trial_plan and school.trial_end_date:
        return {"error": "An active trial already exists"}

    if school.trial_end_date is not None:
        return {"error": "This school has already used its one-time subscription trial"}

    current_plan = school.subscription_plan or "Free Tier"
    if current_plan == trial_plan:
        return {"error": "This school is already on that base plan"}

    plan_order = ["Free Tier", "Basic", "Premium"]
    if plan_order.index(trial_plan) <= plan_order.index(current_plan):
        return {"error": "Trials are only available for higher subscription plans"}

    term_reference = get_current_term_reference(school_id) or {}
    duration_days = max(1, int(days or TRIAL_DURATION_DAYS))
    trial_end = _now_utc() + timedelta(days=duration_days)

    from backend.subscription_features import get_plan_display_name

    school.trial_plan = trial_plan
    school.trial_end_date = trial_end
    school.is_trial_active = True
    db.session.commit()

    return {
        "message": f"{get_plan_display_name(trial_plan)} trial activated for 30 days",
        "trial_plan": school.trial_plan,
        "trial_plan_display_name": get_plan_display_name(school.trial_plan),
        "trial_start_date": _now_utc().isoformat(),
        "trial_end_date": school.trial_end_date.isoformat(),
        "trial_mode": "month",
        "trial_duration_days": duration_days,
        "term_name": term_reference.get("name"),
        "academic_year": term_reference.get("academic_year"),
        "reference_source": term_reference.get("source"),
    }


def end_trial(school_id: str) -> dict[str, Any]:
    school = School.query.get(school_id)
    if not school:
        return {"error": "School not found"}

    if school.trial_end_date is None:
        school.trial_end_date = _now_utc()

    school.trial_plan = None
    school.is_trial_active = False
    db.session.commit()

    return {
        "message": "Trial ended. School is now on base subscription plan.",
        "base_plan": school.subscription_plan or "Free Tier",
    }


def lock_pricing_version(school_id: str, version: str | None = None) -> dict[str, Any]:
    school = School.query.get(school_id)
    if not school:
        return {"error": "School not found"}

    plan_pricing = PRICING.get(school.subscription_plan or "Free Tier", {})
    school.plan_version = version or f"{(school.subscription_plan or 'Free Tier').lower().replace(' ', '_')}_v1"
    school.pricing_locked_at = _now_utc()
    school.custom_base_fee = float(plan_pricing.get("base_fee_per_term", 0) or 0)
    school.custom_included_students = int(plan_pricing.get("included_students", 0) or 0)
    school.custom_overage_rate = float(plan_pricing.get("per_student_per_term", 0) or 0)
    db.session.commit()

    return {
        "message": "Pricing locked for grandfathering",
        "plan_version": school.plan_version,
        "custom_base_fee": school.custom_base_fee,
        "custom_included_students": school.custom_included_students,
        "custom_overage_rate": school.custom_overage_rate,
        "pricing_locked_at": school.pricing_locked_at.isoformat() if school.pricing_locked_at else None,
    }

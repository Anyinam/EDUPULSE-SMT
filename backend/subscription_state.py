from datetime import datetime, timezone


PLAN_NAME_ALIASES = {
    "free": "Free Tier",
    "free tier": "Free Tier",
    "school os": "Basic",
    "basic": "Basic",
    "school os plus": "Premium",
    "premium": "Premium",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_utc_datetime(dt_value: datetime | None) -> datetime | None:
    if not dt_value:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value


def normalize_plan_name(plan_name: str | None) -> str:
    normalized = str(plan_name or "").strip().lower()
    if not normalized:
        return "Free Tier"
    return PLAN_NAME_ALIASES.get(normalized, str(plan_name).strip() or "Free Tier")


def get_effective_plan(school, now: datetime | None = None) -> str:
    if not school:
        return "Free Tier"

    effective_plan = normalize_plan_name(school.subscription_plan)
    trial_end = normalize_utc_datetime(getattr(school, "trial_end_date", None))
    comparison_now = now or now_utc()

    if getattr(school, "trial_plan", None) and trial_end and comparison_now < trial_end:
        effective_plan = normalize_plan_name(school.trial_plan)

    return effective_plan


def get_trial_days_remaining(trial_end_date: datetime | None, now: datetime | None = None) -> int:
    normalized_end = normalize_utc_datetime(trial_end_date)
    if not normalized_end:
        return 0

    comparison_now = now or now_utc()
    return max(0, (normalized_end - comparison_now).days)


def is_trial_active(school, now: datetime | None = None) -> bool:
    if not school:
        return False

    comparison_now = now or now_utc()
    trial_end = normalize_utc_datetime(getattr(school, "trial_end_date", None))
    return bool(getattr(school, "trial_plan", None) and trial_end and comparison_now < trial_end)
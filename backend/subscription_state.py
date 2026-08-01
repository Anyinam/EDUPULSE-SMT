from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_utc_datetime(dt_value: datetime | None) -> datetime | None:
    if not dt_value:
        return None
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=timezone.utc)
    return dt_value


def get_effective_plan(school, now: datetime | None = None) -> str:
    if not school:
        return "Free Tier"

    effective_plan = school.subscription_plan or "Free Tier"
    trial_end = normalize_utc_datetime(getattr(school, "trial_end_date", None))
    comparison_now = now or now_utc()

    if getattr(school, "trial_plan", None) and trial_end and comparison_now < trial_end:
        effective_plan = school.trial_plan

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
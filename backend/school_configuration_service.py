TUITION_CONVENIENCE_FEE_KEY = "__tuition_convenience_fee_percentage__"
TUITION_INSTALLMENT_PLAN_KEY = "__tuition_installment_plan__"


class TuitionInstallmentPlanValidationError(ValueError):
    pass


def _build_equal_installment_amounts(total_amount, installment_count):
    normalized_total = round(float(total_amount or 0.0), 2)
    normalized_count = max(1, int(installment_count or 1))
    if normalized_count == 1:
        return [normalized_total]

    total_minor = int(round(normalized_total * 100))
    equal_minor = total_minor // normalized_count
    remainder_minor = total_minor - (equal_minor * normalized_count)

    amounts = []
    for index in range(normalized_count):
        amount_minor = equal_minor + (remainder_minor if index == normalized_count - 1 else 0)
        amounts.append(round(amount_minor / 100.0, 2))
    return amounts


def _read_tuition_installment_plan(settings):
    other_fees = settings.other_fees if settings and isinstance(settings.other_fees, dict) else {}
    raw_plan = other_fees.get(TUITION_INSTALLMENT_PLAN_KEY)
    if not isinstance(raw_plan, dict):
        return {
            "enabled": False,
            "installment_count": 1,
            "schedule": [],
        }

    enabled = bool(raw_plan.get("enabled"))
    try:
        installment_count = max(1, int(raw_plan.get("installment_count") or 1))
    except (TypeError, ValueError):
        installment_count = 1

    normalized_schedule = []
    for index, item in enumerate(raw_plan.get("schedule") or [], start=1):
        if not isinstance(item, dict):
            continue
        try:
            amount = round(max(0.0, float(item.get("amount") or 0.0)), 2)
        except (TypeError, ValueError):
            amount = 0.0
        normalized_schedule.append(
            {
                "installment_number": int(item.get("installment_number") or index),
                "label": item.get("label") or f"Installment {index}",
                "amount": amount,
                "start_date": (item.get("start_date") or "").strip() or None,
                "due_date": (item.get("due_date") or "").strip() or None,
            }
        )

    return {
        "enabled": enabled and installment_count > 1,
        "installment_count": installment_count,
        "schedule": normalized_schedule,
    }


def _normalize_tuition_installment_plan(plan_payload, tuition_fee):
    if not isinstance(plan_payload, dict) or not bool(plan_payload.get("enabled")):
        return {
            "enabled": False,
            "installment_count": 1,
            "schedule": [],
        }

    try:
        installment_count = max(2, int(plan_payload.get("installment_count") or 2))
    except (TypeError, ValueError):
        installment_count = 2

    equal_amounts = _build_equal_installment_amounts(tuition_fee, installment_count)
    raw_schedule = plan_payload.get("schedule") or []
    normalized_schedule = []
    total_minor = 0
    tuition_total_minor = int(round(round(float(tuition_fee or 0.0), 2) * 100))

    for index in range(installment_count):
        raw_item = raw_schedule[index] if index < len(raw_schedule) and isinstance(raw_schedule[index], dict) else {}
        fallback_amount = equal_amounts[index]
        try:
            raw_amount = raw_item.get("amount")
            amount = round(max(0.0, float(raw_amount if raw_amount not in (None, "") else fallback_amount)), 2)
        except (TypeError, ValueError):
            amount = fallback_amount
        amount_minor = int(round(amount * 100))
        if amount_minor <= 0:
            raise TuitionInstallmentPlanValidationError(
                f"Installment {index + 1} must have an amount greater than zero."
            )
        total_minor += amount_minor
        normalized_schedule.append(
            {
                "installment_number": index + 1,
                "label": (raw_item.get("label") or f"Installment {index + 1}").strip() if isinstance(raw_item.get("label"), str) else f"Installment {index + 1}",
                "amount": round(amount_minor / 100.0, 2),
                "start_date": (raw_item.get("start_date") or "").strip() or None,
                "due_date": (raw_item.get("due_date") or "").strip() or None,
            }
        )

    if total_minor != tuition_total_minor:
        raise TuitionInstallmentPlanValidationError(
            "Installment amounts must add up exactly to the tuition fee."
        )

    return {
        "enabled": True,
        "installment_count": installment_count,
        "schedule": normalized_schedule,
    }


def _normalize_visible_other_fees(raw_other_fees):
    if not isinstance(raw_other_fees, dict):
        return {}
    normalized = {}
    for fee_name, amount in raw_other_fees.items():
        if fee_name in {TUITION_CONVENIENCE_FEE_KEY, TUITION_INSTALLMENT_PLAN_KEY}:
            continue
        try:
            normalized[fee_name] = round(float(amount), 2)
        except (TypeError, ValueError):
            continue
    return normalized


def _read_tuition_convenience_fee_percentage(settings):
    other_fees = settings.other_fees if settings and isinstance(settings.other_fees, dict) else {}
    try:
        return round(float(other_fees.get(TUITION_CONVENIENCE_FEE_KEY, 1.95) or 0.0), 2)
    except (TypeError, ValueError):
        return 1.95


def update_school_fees(
    data,
    school_id,
    actor_id,
    *,
    school_settings_model,
    set_feeding_plan_fees,
    log_action,
    db_session,
):
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        settings = school_settings_model(school_id=school_id)
        db_session.add(settings)

    if "tuition_fee" in data:
        settings.tuition_fee = float(data["tuition_fee"]) if data["tuition_fee"] else 0.0
    if "feeding_fee" in data:
        settings.feeding_fee = float(data["feeding_fee"]) if data["feeding_fee"] else 0.0
    if any(key in data for key in ["feeding_daily_fee", "feeding_weekly_fee", "feeding_monthly_fee"]):
        set_feeding_plan_fees(
            settings,
            data.get("feeding_daily_fee"),
            data.get("feeding_weekly_fee"),
            data.get("feeding_monthly_fee"),
        )
    settings.uniform_fee = 0.0
    if "transport_fee" in data:
        settings.transport_fee = float(data["transport_fee"]) if data["transport_fee"] else 0.0
    if "terminal_report_fee" in data:
        settings.terminal_report_fee = float(data["terminal_report_fee"]) if data["terminal_report_fee"] else 0.0
    if "admission_fee_enabled" in data:
        settings.admission_fee_enabled = bool(data.get("admission_fee_enabled"))
    if "admission_fee_amount" in data:
        settings.admission_fee_amount = float(data["admission_fee_amount"]) if data["admission_fee_amount"] else 0.0
    other_fees_payload = _normalize_visible_other_fees(data.get("other_fees", settings.other_fees or {}))
    tuition_convenience_fee_percentage = data.get("tuition_convenience_fee_percentage")
    if tuition_convenience_fee_percentage in (None, ""):
        tuition_convenience_fee_percentage = _read_tuition_convenience_fee_percentage(settings)
    try:
        tuition_convenience_fee_percentage = round(max(0.0, float(tuition_convenience_fee_percentage or 0.0)), 2)
    except (TypeError, ValueError):
        tuition_convenience_fee_percentage = 1.95
    normalized_installment_plan = _normalize_tuition_installment_plan(
        data.get("tuition_installment_plan"),
        settings.tuition_fee or 0.0,
    )
    settings.other_fees = {
        **other_fees_payload,
        TUITION_CONVENIENCE_FEE_KEY: tuition_convenience_fee_percentage,
        TUITION_INSTALLMENT_PLAN_KEY: normalized_installment_plan,
    }

    log_action(
        actor_id,
        school_id,
        "FEES_UPDATE",
        f"Updated school fees: Tuition={settings.tuition_fee}, Feeding={settings.feeding_fee}, Transport={settings.transport_fee}, Tuition convenience fee={tuition_convenience_fee_percentage}%",
    )
    db_session.commit()
    return {"message": "Fees updated successfully."}


def get_school_fees_payload(school_id, *, school_settings_model, get_feeding_plan_fees):
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        return {
            "tuition_fee": 0.0,
            "tuition_convenience_fee_percentage": 1.95,
            "tuition_installment_plan": {
                "enabled": False,
                "installment_count": 1,
                "schedule": [],
            },
            "feeding_fee": 0.0,
            "feeding_daily_fee": 0.0,
            "feeding_weekly_fee": 0.0,
            "feeding_monthly_fee": 0.0,
            "uniform_fee": 0.0,
            "transport_fee": 0.0,
            "terminal_report_fee": 0.0,
            "admission_fee_enabled": False,
            "admission_fee_amount": 0.0,
            "other_fees": {},
        }

    feeding_plan_fees = get_feeding_plan_fees(settings)
    visible_other_fees = _normalize_visible_other_fees(settings.other_fees or {})
    return {
        "tuition_fee": settings.tuition_fee or 0.0,
        "tuition_convenience_fee_percentage": _read_tuition_convenience_fee_percentage(settings),
        "tuition_installment_plan": _read_tuition_installment_plan(settings),
        "feeding_fee": feeding_plan_fees["primary"],
        "feeding_daily_fee": feeding_plan_fees["daily"],
        "feeding_weekly_fee": feeding_plan_fees["weekly"],
        "feeding_monthly_fee": feeding_plan_fees["monthly"],
        "uniform_fee": 0.0,
        "transport_fee": settings.transport_fee or 0.0,
        "terminal_report_fee": settings.terminal_report_fee or 0.0,
        "admission_fee_enabled": bool(settings.admission_fee_enabled),
        "admission_fee_amount": settings.admission_fee_amount or 0.0,
        "other_fees": visible_other_fees,
    }


def update_grading_scheme(data, school_id, actor_id, *, school_settings_model, log_action, db_session):
    class_score_max = data.get("class_score_max")
    exam_score_max = data.get("exam_score_max")

    if class_score_max is None or exam_score_max is None:
        return None, {"message": "Both class_score_max and exam_score_max are required"}, 400

    try:
        class_score_max = int(class_score_max)
        exam_score_max = int(exam_score_max)
    except (ValueError, TypeError):
        return None, {"message": "Scores must be valid integers"}, 400

    if class_score_max + exam_score_max != 100:
        return None, {"message": "Class score and exam score must add up to 100"}, 400

    if class_score_max < 0 or exam_score_max < 0:
        return None, {"message": "Scores must be positive"}, 400

    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        settings = school_settings_model(school_id=school_id)
        db_session.add(settings)

    settings.class_score_max = class_score_max
    settings.exam_score_max = exam_score_max

    log_action(
        actor_id,
        school_id,
        "GRADING_SCHEME_UPDATE",
        f"Updated grading scheme to {class_score_max}/{exam_score_max}",
    )
    db_session.commit()
    return {
        "message": "Grading scheme updated successfully",
        "class_score_max": class_score_max,
        "exam_score_max": exam_score_max,
    }, None, 200


def get_grading_scheme_payload(school_id, *, school_settings_model):
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        return {"class_score_max": 30, "exam_score_max": 70}

    return {
        "class_score_max": settings.class_score_max or 30,
        "exam_score_max": settings.exam_score_max or 70,
    }
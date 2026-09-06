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
    if "other_fees" in data:
        settings.other_fees = data["other_fees"] if isinstance(data["other_fees"], dict) else {}

    log_action(
        actor_id,
        school_id,
        "FEES_UPDATE",
        f"Updated school fees: Tuition={settings.tuition_fee}, Feeding={settings.feeding_fee}, Transport={settings.transport_fee}",
    )
    db_session.commit()
    return {"message": "Fees updated successfully."}


def get_school_fees_payload(school_id, *, school_settings_model, get_feeding_plan_fees):
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        return {
            "tuition_fee": 0.0,
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
    return {
        "tuition_fee": settings.tuition_fee or 0.0,
        "feeding_fee": feeding_plan_fees["primary"],
        "feeding_daily_fee": feeding_plan_fees["daily"],
        "feeding_weekly_fee": feeding_plan_fees["weekly"],
        "feeding_monthly_fee": feeding_plan_fees["monthly"],
        "uniform_fee": 0.0,
        "transport_fee": settings.transport_fee or 0.0,
        "terminal_report_fee": settings.terminal_report_fee or 0.0,
        "admission_fee_enabled": bool(settings.admission_fee_enabled),
        "admission_fee_amount": settings.admission_fee_amount or 0.0,
        "other_fees": settings.other_fees or {},
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
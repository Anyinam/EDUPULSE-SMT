from datetime import datetime, timezone


def initialize_student_paystack_payment(
    data,
    school_id,
    student_model,
    sanitize_string,
    resolve_payment_from_reference,
    call_paystack_api,
):
    student_id = data.get("student_id")
    reference_code = sanitize_string(data.get("reference_code")) or None
    payment_type = sanitize_string(data.get("payment_type", "Tuition"))
    amount = data.get("amount")
    payment_category = data.get("payment_category") if isinstance(data.get("payment_category"), dict) else {}

    student = None
    if student_id:
        student = student_model.query.filter_by(id=student_id, school_id=school_id).first_or_404()
    elif reference_code:
        resolved_student, resolved_type, resolved_category = resolve_payment_from_reference(
            reference_code,
            school_id_hint=school_id,
        )
        if not resolved_student:
            return None, {"error": f"Invalid reference code: {reference_code}"}, 400
        student = resolved_student
        payment_type = resolved_type or payment_type or "Tuition"
        payment_category = {
            **(resolved_category or {}),
            **(payment_category or {}),
            "reference_code": reference_code,
        }
    else:
        return None, {"error": "student_id or reference_code required"}, 400

    if amount in (None, ""):
        return None, {"error": "amount required"}, 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None, {"error": "amount must be numeric"}, 400

    if amount <= 0:
        return None, {"error": "amount must be greater than zero"}, 400

    if reference_code and "reference_code" not in payment_category:
        payment_category = {
            **(payment_category or {}),
            "reference_code": reference_code,
        }

    import uuid

    reference = f"PS-{student.student_code}-{payment_type[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"
    paystack_payload = {
        "email": student.parent_email or f"{student.student_code}@temp.edupulse.gh",
        "amount": int(amount * 100),
        "reference": reference,
        "currency": "GHS",
        "metadata": {
            "student_id": student.id,
            "student_code": student.student_code,
            "student_name": student.name,
            "school_id": school_id,
            "payment_type": payment_type,
            "reference_code": reference_code,
            "payment_category": payment_category,
        },
        "callback_url": data.get("callback_url", "https://edupulse.com/payment-complete"),
    }

    result, error = call_paystack_api("/transaction/initialize", method="POST", data=paystack_payload)
    if error:
        return None, error, 502

    return {
        "status": "success",
        "authorization_url": result.get("authorization_url"),
        "access_code": result.get("access_code"),
        "reference": reference,
        "amount": amount,
        "student": {
            "id": student.id,
            "name": student.name,
            "student_code": student.student_code,
        },
        "reference_code": reference_code,
        "payment_type": payment_type,
        "message": f"Payment link generated for {student.name}",
    }, None, 200


def initialize_parent_admission_fee_payment(
    school_id,
    status_token,
    school,
    settings,
    application,
    fee_config,
    payment_summary,
    get_payment_provider_settings,
    build_parent_status_path,
    build_parent_public_url,
    normalize_parent_admission_payment_summary,
    set_parent_admission_payment_summary,
    call_paystack_api,
    db_session,
    token_hex_fn,
):
    if payment_summary.get("status") == "paid":
        return None, {"message": "Admission fee has already been paid.", "payment_summary": payment_summary}, 409

    amount = round(float(fee_config["amount"] or 0.0), 2)
    if amount <= 0:
        return None, {"message": "Admission fee amount is not configured."}, 409

    callback_url = build_parent_public_url(build_parent_status_path(school_id, status_token))
    reference = f"PADM-{application.application_code}-{token_hex_fn(4).upper()}"
    provider_settings = get_payment_provider_settings(settings)
    paystack_payload = {
        "email": application.parent_email or f"{application.application_code.lower()}@parents.edupulse.invalid",
        "amount": int(amount * 100),
        "reference": reference,
        "currency": "GHS",
        "metadata": {
            "transaction_type": "parent_admission_fee",
            "school_id": school_id,
            "parent_admission_application_id": application.id,
            "application_code": application.application_code,
            "status_token": application.status_token,
            "payment_type": fee_config["label"],
        },
        "callback_url": callback_url,
    }
    if provider_settings.get("paystack_subaccount_code"):
        paystack_payload["subaccount"] = provider_settings["paystack_subaccount_code"]

    result, error = call_paystack_api("/transaction/initialize", method="POST", data=paystack_payload)
    if error:
        return None, error, 502

    initiated_summary = normalize_parent_admission_payment_summary(
        {
            **payment_summary,
            "status": "initiated",
            "reference": reference,
            "amount": amount,
            "provider": "paystack",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        fee_config=fee_config,
    )
    set_parent_admission_payment_summary(application, initiated_summary)
    db_session.commit()

    return {
        "status": "success",
        "authorization_url": result.get("authorization_url"),
        "access_code": result.get("access_code"),
        "reference": reference,
        "amount": amount,
        "application_code": application.application_code,
        "payment_summary": initiated_summary,
        "message": f"Payment link generated for {application.application_code}",
    }, None, 200
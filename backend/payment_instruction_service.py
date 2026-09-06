from datetime import datetime, timezone


def build_payment_collection_intent_payload(intent, sanitize_string):
    if not intent:
        return None
    split_config = intent.meta.get("split_config") if isinstance(intent.meta, dict) else {}
    return {
        "id": intent.id,
        "provider": intent.provider,
        "channel": intent.collection_channel,
        "status": intent.intent_status,
        "reference_code": intent.reference_code,
        "payment_type": intent.payment_type,
        "base_amount": round(float(intent.base_amount or 0.0), 2),
        "convenience_fee_amount": round(float(intent.convenience_fee_amount or 0.0), 2),
        "estimated_provider_fee_amount": round(float(intent.estimated_provider_fee_amount or 0.0), 2),
        "platform_fee_amount": round(float(intent.platform_fee_amount or 0.0), 2),
        "total_amount": round(float(intent.total_amount or 0.0), 2),
        "currency": intent.currency or "GH₵",
        "bank_name": intent.provider_bank_name,
        "bank_slug": intent.provider_bank_slug,
        "account_name": intent.provider_account_name,
        "account_number": intent.provider_account_number,
        "subaccount_code": intent.provider_subaccount_code,
        "split_code": sanitize_string(split_config.get("split_code") or "") or None,
        "settlement_mode": sanitize_string(split_config.get("settlement_mode") or "reference_first") or "reference_first",
        "school_settlement_amount": round(float(split_config.get("school_settlement_amount") or intent.base_amount or 0.0), 2),
        "platform_settlement_amount": round(float(split_config.get("platform_settlement_amount") or 0.0), 2),
        "provider_customer_code": intent.provider_customer_code,
        "expires_at": intent.expires_at.isoformat() if intent.expires_at else None,
        "paid_at": intent.paid_at.isoformat() if intent.paid_at else None,
    }


def get_student_payment_collection_intents(student, payment_collection_intent_model):
    if not student:
        return {}

    now = datetime.now(timezone.utc)
    intents = (
        payment_collection_intent_model.query.filter_by(
            school_id=student.school_id,
            student_id=student.id,
            provider="paystack",
            collection_channel="dedicated_virtual_account",
        )
        .order_by(payment_collection_intent_model.id.desc())
        .all()
    )

    latest_by_reference = {}
    for intent in intents:
        if intent.reference_code in latest_by_reference:
            continue
        if intent.intent_status == "deactivated":
            continue
        if intent.expires_at and intent.expires_at < now and intent.intent_status == "assigned" and not intent.paid_at:
            intent.intent_status = "expired"
            continue
        latest_by_reference[intent.reference_code] = intent
    return latest_by_reference


def attach_virtual_routes_to_payment_codes(student, codes_list, get_student_payment_collection_intents_fn, build_payment_collection_intent_payload_fn):
    latest_by_reference = get_student_payment_collection_intents_fn(student)
    for code in codes_list:
        intent = latest_by_reference.get(code.get("reference_code"))
        route_payload = build_payment_collection_intent_payload_fn(intent)
        code["virtual_route"] = route_payload
        code["virtual_bank_account"] = route_payload.get("account_number") if route_payload else None
        code["virtual_bank_name"] = route_payload.get("bank_name") if route_payload else None
        code["subaccount_code"] = route_payload.get("subaccount_code") if route_payload else None
        code["has_virtual_route"] = bool(route_payload and route_payload.get("status") in {"assigned", "paid"})
        code["preferred_payment_model"] = "virtual_account_ready" if code["has_virtual_route"] else "reference_first"


def build_student_payment_instruction_payload(
    student,
    school_id,
    school_model,
    school_settings_model,
    generate_all_payment_codes,
    get_school_admission_fee_config,
    get_feeding_plan_fees,
    attach_virtual_routes_to_payment_codes_fn,
    get_payment_provider_settings,
    paystack_dva_supported_countries,
    sanitize_string,
    get_payment_collection_pricing,
):
    school = school_model.query.get(school_id)
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    other_fees = dict(settings.other_fees or {}) if settings and isinstance(settings.other_fees, dict) else {}
    admission_fee = get_school_admission_fee_config(settings)
    feeding_plan_fees = get_feeding_plan_fees(settings)
    if admission_fee["enabled"]:
        other_fees.setdefault(admission_fee["label"], admission_fee["amount"])

    fees_config = {
        "tuition_fee": settings.tuition_fee if settings else 0.0,
        "feeding_fee": feeding_plan_fees["primary"],
        "uniform_fee": settings.uniform_fee if settings else 0.0,
        "transport_fee": settings.transport_fee if settings else 0.0,
        "terminal_report_fee": settings.terminal_report_fee if settings else 0.0,
        "other_fees": other_fees,
    }

    payment_codes = generate_all_payment_codes(student.student_code, fees_config)

    codes_list = []
    for fee_type, code in payment_codes.items():
        if fee_type == "Feeding" and feeding_plan_fees["has_explicit_plans"]:
            continue

        if fee_type == "Tuition":
            base_amount = fees_config["tuition_fee"] + fees_config["terminal_report_fee"]
            display_name = "Tuition + Terminal Report"
        elif fee_type == "Feeding":
            base_amount = fees_config["feeding_fee"]
            display_name = fee_type
        elif fee_type == "Uniform":
            base_amount = fees_config["uniform_fee"]
            display_name = fee_type
        elif fee_type == "Transport":
            base_amount = fees_config["transport_fee"]
            display_name = fee_type
        else:
            base_amount = fees_config["other_fees"].get(fee_type, 0.0)
            display_name = fee_type

        if student.is_on_scholarship:
            if fee_type == "Tuition" and student.scholarship_covers_tuition:
                base_amount = 0.0
            if fee_type == "Feeding" and student.scholarship_covers_feeding:
                base_amount = 0.0

        codes_list.append({
            "fee_type": display_name,
            "code": code,
            "reference_code": code,
            "payment_identity_base": student.student_code,
            "payment_category": {"fee_type": fee_type},
            "base_amount": round(base_amount, 2),
            "cash_amount": round(base_amount, 2),
            "total_amount": round(base_amount, 2),
            "amount": round(base_amount, 2),
            "virtual_bank_account": None,
            "virtual_bank_name": None,
            "momo_shortcode": None,
            "subaccount_code": None,
            "has_virtual_route": False,
            "preferred_payment_model": "reference_first",
            "virtual_route": None,
            "is_scholarship_fee": bool(
                (fee_type == "Tuition" and student.scholarship_covers_tuition)
                or (fee_type == "Feeding" and student.scholarship_covers_feeding)
            ),
            "instructions": (
                f"Use the stable learner payment identity {student.student_code} with reference {code}. "
                + "Phone payments should use the structured reference through bank transfer, bank app, USSD, or the school's approved digital channel. "
                + f"The amount to pay for this fee is GH₵ {base_amount:.2f}, and the same reference can also be presented at the school office."
            ),
        })

    if feeding_plan_fees["has_explicit_plans"]:
        frequency_specs = [
            ("Daily", "DAY", feeding_plan_fees["daily"]),
            ("Weekly", "WEK", feeding_plan_fees["weekly"]),
            ("Monthly", "MON", feeding_plan_fees["monthly"]),
        ]

        for frequency_label, frequency_code, configured_amount in frequency_specs:
            if configured_amount <= 0:
                continue

            base_amount = 0.0 if student.is_on_scholarship and student.scholarship_covers_feeding else configured_amount
            reference_code = f"{student.student_code}-FEED-{frequency_code}"

            codes_list.append({
                "fee_type": f"Feeding ({frequency_label})",
                "code": reference_code,
                "reference_code": reference_code,
                "payment_identity_base": student.student_code,
                "payment_category": {"fee_type": "Feeding", "frequency": frequency_label},
                "base_amount": round(base_amount, 2),
                "cash_amount": round(base_amount, 2),
                "total_amount": round(base_amount, 2),
                "amount": round(base_amount, 2),
                "virtual_bank_account": None,
                "virtual_bank_name": None,
                "momo_shortcode": None,
                "subaccount_code": None,
                "has_virtual_route": False,
                "preferred_payment_model": "reference_first",
                "virtual_route": None,
                "is_scholarship_fee": bool(student.is_on_scholarship and student.scholarship_covers_feeding),
                "instructions": (
                    f"Use reference {reference_code} for the {frequency_label.lower()} feeding plan. "
                    + "Phone payments should use the structured reference through bank transfer, bank app, USSD, or the school's approved digital channel. "
                    + f"The amount to pay for this plan is GH₵ {base_amount:.2f}, and the same reference can also be presented at the school office."
                ),
            })

    attach_virtual_routes_to_payment_codes_fn(student, codes_list)
    provider_settings = get_payment_provider_settings(settings)
    country_supports_dvas = bool(
        (settings.country_code if settings and settings.country_code else "GH") in paystack_dva_supported_countries
    )
    supports_fee_route_dvas = bool(
        country_supports_dvas and sanitize_string(provider_settings.get("paystack_subaccount_code") or "")
    )

    return {
        "student_id": student.id,
        "student_name": student.name,
        "student_code": student.student_code,
        "class": student.current_class,
        "parent_name": student.parent_name,
        "parent_phone": student.parent_phone,
        "parent_email": student.parent_email,
        "payment_identity": {
            "model": "reference_first",
            "student_code": student.student_code,
            "stable_payment_identity": student.student_code,
            "supports_structured_references": True,
            "supports_fee_route_dvas": supports_fee_route_dvas,
            "dva_country_supported": country_supports_dvas,
            "tracked_transfer_ready": supports_fee_route_dvas,
            "tracked_transfer_readiness_note": None if supports_fee_route_dvas else (
                "Save verified school bank details in Settings so EduPulse can create the school Paystack settlement subaccount first."
                if country_supports_dvas
                else "Tracked transfer accounts are not available for this school country yet."
            ),
            "supported_rails": ["bank_app", "ussd_or_shortcode", "school_office_manual"],
            "recommended_examples": [item["reference_code"] for item in codes_list[:3]],
        },
        "admission_fee": admission_fee,
        "payment_collection_pricing": get_payment_collection_pricing(),
        "school_payment_account": {
            "bank_name": school.bank_name if school else None,
            "bank_account": school.bank_account if school else None,
            "bank_account_name": school.bank_account_name if school else None,
            "bank_branch": school.bank_branch if school else None,
        },
        "payment_codes": codes_list,
        "note": "Preferred model: use the learner's stable payment identity and structured reference across the school's approved payment channels.",
    }
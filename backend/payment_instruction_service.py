from datetime import datetime, timezone


TUITION_CONVENIENCE_FEE_KEY = "__tuition_convenience_fee_percentage__"


def _get_tuition_convenience_fee_percentage(settings):
    other_fees = settings.other_fees if settings and isinstance(settings.other_fees, dict) else {}
    try:
        configured = float(other_fees.get(TUITION_CONVENIENCE_FEE_KEY, 1.95) or 0.0)
        if configured <= 0:
            return 1.95
        return round(configured, 2)
    except (TypeError, ValueError):
        return 1.95


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
        expires_at = intent.expires_at
        if expires_at and getattr(expires_at, "tzinfo", None) is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < now and intent.intent_status == "assigned" and not intent.paid_at:
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
    feeding_plan_fees = get_feeding_plan_fees(settings)
    admission_fee = get_school_admission_fee_config(settings)
    tuition_convenience_fee_percentage = _get_tuition_convenience_fee_percentage(settings)

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

    def append_standard_code(fee_type, reference_code, base_amount, payment_category, instructions, *, amount=None, pricing_override=None):
        normalized_base_amount = round(float(base_amount or 0.0), 2)
        normalized_total_amount = round(float(amount if amount is not None else normalized_base_amount), 2)
        codes_list.append({
            "fee_type": fee_type,
            "code": reference_code,
            "reference_code": reference_code,
            "payment_identity_base": student.student_code,
            "payment_category": payment_category,
            "base_amount": normalized_base_amount,
            "cash_amount": normalized_base_amount,
            "total_amount": normalized_total_amount,
            "amount": normalized_total_amount,
            "virtual_bank_account": None,
            "virtual_bank_name": None,
            "momo_shortcode": None,
            "subaccount_code": None,
            "has_virtual_route": False,
            "preferred_payment_model": "reference_first",
            "virtual_route": None,
            "is_scholarship_fee": False,
            "pricing_override": pricing_override,
            "instructions": instructions,
        })

    tuition_reference = payment_codes.get("Tuition")
    if tuition_reference:
        base_amount = fees_config["tuition_fee"]
        if student.is_on_scholarship and student.scholarship_covers_tuition:
            base_amount = 0.0
        convenience_fee_amount = round(base_amount * (tuition_convenience_fee_percentage / 100.0), 2)
        total_amount = round(base_amount + convenience_fee_amount, 2)

        append_standard_code(
            "Tuition",
            tuition_reference,
            base_amount,
            {"fee_type": "Tuition"},
            (
                f"EduPulse automatically prepares a tracked transfer account for reference {tuition_reference}. "
                + f"Parents should pay GH₵ {total_amount:.2f} to that account using reference {tuition_reference}. "
                + f"The school tuition amount remains GH₵ {base_amount:.2f}; the tracked transfer total includes a {tuition_convenience_fee_percentage:.2f}% convenience fee."
            ),
            amount=total_amount,
            pricing_override={
                "estimated_provider_fee_rate_pct": tuition_convenience_fee_percentage,
                "estimated_provider_fee_flat": 0.0,
                "platform_fee_flat": 0.0,
                "charge_parent_convenience_fee": True,
                "platform_fee_label": "Convenience Fee",
            },
        )
        codes_list[-1]["is_scholarship_fee"] = bool(student.scholarship_covers_tuition)

    feeding_plan_entries = [
        ("Daily", "DAY", round(float(feeding_plan_fees.get("daily") or 0.0), 2)),
        ("Weekly", "WEK", round(float(feeding_plan_fees.get("weekly") or 0.0), 2)),
        ("Monthly", "MON", round(float(feeding_plan_fees.get("monthly") or 0.0), 2)),
    ]
    has_explicit_feeding_plans = any(amount > 0 for _frequency, _suffix, amount in feeding_plan_entries)
    if has_explicit_feeding_plans:
        for frequency, suffix, amount in feeding_plan_entries:
            if amount <= 0:
                continue
            reference_code = f"{student.student_code}-FEED-{suffix}"
            append_standard_code(
                f"Feeding ({frequency})",
                reference_code,
                amount,
                {"fee_type": "Feeding", "frequency": frequency},
                f"Use reference {reference_code} when recording or confirming the {frequency.lower()} feeding payment for this learner.",
            )
    else:
        feeding_reference = payment_codes.get("Feeding")
        if feeding_reference and feeding_plan_fees.get("primary"):
            append_standard_code(
                "Feeding",
                feeding_reference,
                feeding_plan_fees.get("primary") or 0.0,
                {"fee_type": "Feeding", "frequency": "Monthly"},
                f"Use reference {feeding_reference} when recording or confirming feeding payment for this learner.",
            )

    uniform_reference = payment_codes.get("Uniform")
    if uniform_reference and fees_config.get("uniform_fee"):
        append_standard_code(
            "Uniform",
            uniform_reference,
            fees_config.get("uniform_fee") or 0.0,
            {"fee_type": "Uniform"},
            f"Use reference {uniform_reference} when recording or confirming the uniform payment for this learner.",
        )

    transport_reference = payment_codes.get("Transport")
    if transport_reference and fees_config.get("transport_fee"):
        append_standard_code(
            "Transport",
            transport_reference,
            fees_config.get("transport_fee") or 0.0,
            {"fee_type": "Transport"},
            f"Use reference {transport_reference} when recording or confirming the transport payment for this learner.",
        )

    for fee_name, amount in other_fees.items():
        if fee_name == TUITION_CONVENIENCE_FEE_KEY:
            continue
        reference_code = payment_codes.get(fee_name)
        if not reference_code or float(amount or 0.0) <= 0:
            continue
        append_standard_code(
            fee_name,
            reference_code,
            amount,
            {"fee_type": fee_name},
            f"Use reference {reference_code} when recording or confirming the {fee_name.lower()} payment for this learner.",
        )

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
            "supported_rails": ["bank_app", "ussd_or_shortcode"],
            "recommended_examples": [item["reference_code"] for item in codes_list[:3]],
        },
        "admission_fee": admission_fee,
        "payment_collection_pricing": get_payment_collection_pricing(),
        "school_payment_account": {
            "bank_name": None,
            "bank_account": None,
            "bank_account_name": None,
            "bank_branch": None,
        },
        "fees_configuration": {
            "tuition_fee": round(float(fees_config["tuition_fee"] or 0.0), 2),
            "terminal_report_fee": round(float(fees_config["terminal_report_fee"] or 0.0), 2),
            "tuition_convenience_fee_percentage": tuition_convenience_fee_percentage,
        },
        "payment_codes": codes_list,
        "note": "Tuition collection now uses the EduPulse tracked transfer account only. The school tuition amount stays separate from the report-card fee, and the school bank account is intentionally hidden from parent-facing instructions.",
    }
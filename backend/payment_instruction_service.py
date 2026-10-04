from datetime import datetime, timezone

from backend.payment_workflow import calculate_payment_collection_breakdown, get_tuition_collection_pricing


TUITION_CONVENIENCE_FEE_KEY = "__tuition_convenience_fee_percentage__"
TUITION_INSTALLMENT_PLAN_KEY = "__tuition_installment_plan__"


def _get_tuition_convenience_fee_percentage(settings):
    other_fees = settings.other_fees if settings and isinstance(settings.other_fees, dict) else {}
    try:
        configured = float(other_fees.get(TUITION_CONVENIENCE_FEE_KEY, 1.95) or 0.0)
        if configured <= 0:
            return 1.95
        return round(configured, 2)
    except (TypeError, ValueError):
        return 1.95


def _read_tuition_installment_plan(settings):
    other_fees = settings.other_fees if settings and isinstance(settings.other_fees, dict) else {}
    raw_plan = other_fees.get(TUITION_INSTALLMENT_PLAN_KEY)
    if not isinstance(raw_plan, dict):
        return {"enabled": False, "installment_count": 1, "schedule": []}

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
        if amount <= 0:
            continue
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
        "enabled": enabled and installment_count > 1 and len(normalized_schedule) >= 2,
        "installment_count": installment_count,
        "schedule": normalized_schedule,
    }


def _parse_schedule_date(raw_value):
    try:
        return datetime.fromisoformat(str(raw_value)).date() if raw_value else None
    except (TypeError, ValueError):
        return None


def _get_confirmed_tuition_payments(student, payment_model):
    if not student or not payment_model:
        return []
    payments = (
        payment_model.query.filter_by(
            school_id=student.school_id,
            student_id=student.id,
            payment_type="Tuition",
        )
        .order_by(payment_model.date_paid.asc(), payment_model.id.asc())
        .all()
    )
    return [payment for payment in payments if payment.status in {"Verified", "Confirmed"}]


def _get_payment_applied_amount(payment):
    if not payment:
        return 0.0
    category = payment.payment_category if isinstance(payment.payment_category, dict) else {}
    try:
        return round(float(category.get("applied_school_fee_amount", payment.amount) or 0.0), 2)
    except (TypeError, ValueError):
        return round(float(payment.amount or 0.0), 2) if payment.amount else 0.0


def build_payment_collection_intent_payload(intent, sanitize_string):
    if not intent:
        return None
    split_config = intent.meta.get("split_config") if isinstance(intent.meta, dict) else {}
    split_config = split_config if isinstance(split_config, dict) else {}
    pricing = intent.meta.get("pricing") if isinstance(intent.meta, dict) else {}
    pricing = pricing if isinstance(pricing, dict) else {}
    fee_model = pricing.get("fee_model")
    rounding_surplus_amount = round(
        float(intent.total_amount or 0.0) - float(intent.base_amount or 0.0)
        - float(intent.estimated_provider_fee_amount or 0.0) - float(intent.platform_fee_amount or 0.0),
        2,
    ) if fee_model == "gross_up_margin_v1" else 0.0
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
        "fee_model": fee_model,
        "rounding_surplus_amount": rounding_surplus_amount,
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
        if route_payload:
            amount_fields = (
                "base_amount", "total_amount", "convenience_fee_amount",
                "estimated_provider_fee_amount", "platform_fee_amount", "rounding_surplus_amount",
            )
            matches_pricing = route_payload.get("fee_model") == code.get("fee_model") and all(
                round(float(route_payload.get(field) or 0.0), 2) == round(float(code.get(field) or 0.0), 2)
                for field in amount_fields
            )
            if not matches_pricing:
                route_payload = None
        historical_paid = bool(intent and (intent.intent_status == "paid" or intent.paid_at))
        nothing_due = round(float(code.get("base_amount") or 0.0), 2) <= 0
        if nothing_due:
            route_payload = None
        code["virtual_route"] = route_payload
        code["virtual_bank_account"] = route_payload.get("account_number") if route_payload else None
        code["virtual_bank_name"] = route_payload.get("bank_name") if route_payload else None
        code["subaccount_code"] = route_payload.get("subaccount_code") if route_payload else None
        code["has_virtual_route"] = bool(route_payload and route_payload.get("status") in {"assigned", "paid"})
        code["needs_virtual_route_preparation"] = not code["has_virtual_route"] and not historical_paid and not nothing_due
        code["preferred_payment_model"] = (
            "virtual_account_ready" if code["has_virtual_route"]
            else "historical_paid" if historical_paid else "reference_first"
        )


def build_student_payment_instruction_payload(
    student,
    school_id,
    school_model,
    school_settings_model,
    payment_model,
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
    payment_collection_pricing = get_payment_collection_pricing()
    tuition_pricing = get_tuition_collection_pricing(payment_collection_pricing)
    tuition_installment_plan = _read_tuition_installment_plan(settings)

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
        breakdown = calculate_payment_collection_breakdown(normalized_base_amount, pricing_override or {})
        normalized_total_amount = round(float(amount if amount is not None else breakdown["total_amount"]), 2)
        fee_model = breakdown.get("fee_model")
        codes_list.append({
            "fee_type": fee_type,
            "code": reference_code,
            "reference_code": reference_code,
            "payment_identity_base": student.student_code,
            "payment_category": {**payment_category, "fee_model": fee_model} if fee_model else payment_category,
            "base_amount": normalized_base_amount,
            "convenience_fee_amount": breakdown["convenience_fee_amount"],
            "estimated_provider_fee_amount": breakdown["estimated_provider_fee_amount"],
            "platform_fee_amount": breakdown["platform_fee_amount"],
            "rounding_surplus_amount": breakdown.get("rounding_surplus_amount", 0.0),
            "fee_model": fee_model,
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
        outstanding_tuition_amount = round(float(student.total_tuition_owed or 0.0), 2)
        base_amount = outstanding_tuition_amount if outstanding_tuition_amount > 0 else fees_config["tuition_fee"]
        if student.is_on_scholarship and student.scholarship_covers_tuition:
            base_amount = 0.0
        confirmed_tuition_payments = _get_confirmed_tuition_payments(student, payment_model)
        tuition_paid_amount = round(sum(_get_payment_applied_amount(payment) for payment in confirmed_tuition_payments), 2)

        if tuition_installment_plan.get("enabled") and not student.scholarship_covers_tuition:
            remaining_credit = max(0.0, tuition_paid_amount)
            today = datetime.now(timezone.utc).date()
            for installment in tuition_installment_plan.get("schedule") or []:
                installment_amount = round(float(installment.get("amount") or 0.0), 2)
                if installment_amount <= 0:
                    continue
                installment_number = int(installment.get("installment_number") or 1)
                applied_amount = round(min(installment_amount, remaining_credit), 2)
                remaining_credit = round(max(0.0, remaining_credit - applied_amount), 2)
                outstanding_amount = round(max(0.0, installment_amount - applied_amount), 2)
                start_date = _parse_schedule_date(installment.get("start_date"))
                due_date = _parse_schedule_date(installment.get("due_date"))
                if outstanding_amount <= 0.009:
                    installment_status = "paid"
                elif applied_amount > 0:
                    installment_status = "partial"
                elif start_date and today < start_date:
                    installment_status = "upcoming"
                elif due_date and today > due_date:
                    installment_status = "overdue"
                else:
                    installment_status = "open"

                total_amount = calculate_payment_collection_breakdown(installment_amount, tuition_pricing)["total_amount"]
                reference_code = f"{student.student_code}-TUIT-I{installment_number}"
                schedule_window = []
                if installment.get("start_date"):
                    schedule_window.append(f"opens {installment['start_date']}")
                if installment.get("due_date"):
                    schedule_window.append(f"due {installment['due_date']}")
                schedule_window_text = f" ({', '.join(schedule_window)})" if schedule_window else ""
                append_standard_code(
                    "Tuition",
                    reference_code,
                    installment_amount,
                    {
                        "fee_type": "Tuition",
                        "installment_number": installment_number,
                        "installment_label": installment.get("label") or f"Installment {installment_number}",
                        "installment_status": installment_status,
                        "installment_start_date": installment.get("start_date"),
                        "installment_due_date": installment.get("due_date"),
                        "installment_paid_amount": applied_amount,
                        "installment_outstanding_amount": outstanding_amount,
                    },
                    (
                        f"EduPulse automatically prepares a tracked transfer account for {installment.get('label') or f'Installment {installment_number}'}{schedule_window_text}. "
                        + f"Parents should pay GH₵ {total_amount:.2f} to that account using reference {reference_code}. "
                        + f"The installment base amount is GH₵ {installment_amount:.2f}; the tracked transfer total includes provider processing and the EduPulse service fee."
                    ),
                    amount=total_amount,
                    pricing_override=tuition_pricing,
                )
                codes_list[-1]["is_tuition_installment"] = True
                codes_list[-1]["is_scholarship_fee"] = False
            tuition_credit_balance = round(max(0.0, remaining_credit), 2)
        else:
            # total_tuition_owed is only set by imports/seeds; otherwise derive the balance from confirmed payments.
            if outstanding_tuition_amount <= 0 and not (student.is_on_scholarship and student.scholarship_covers_tuition):
                base_amount = round(max(0.0, float(fees_config["tuition_fee"] or 0.0) - tuition_paid_amount), 2)
            tuition_settled = base_amount <= 0.009
            total_amount = calculate_payment_collection_breakdown(base_amount, tuition_pricing)["total_amount"]

            append_standard_code(
                "Tuition",
                tuition_reference,
                base_amount,
                {"fee_type": "Tuition", "tuition_status": "paid" if tuition_settled else "open"},
                (
                    f"Tuition for reference {tuition_reference} is fully settled. No further tuition payment is required."
                    if tuition_settled else
                    f"EduPulse automatically prepares a tracked transfer account for reference {tuition_reference}. "
                    + f"Parents should pay GH₵ {total_amount:.2f} to that account using reference {tuition_reference}. "
                    + f"The current tuition balance for this learner is GH₵ {base_amount:.2f}; the tracked transfer total includes provider processing and the EduPulse service fee."
                ),
                amount=total_amount,
                pricing_override=tuition_pricing,
            )
            codes_list[-1]["is_scholarship_fee"] = bool(student.scholarship_covers_tuition)
            tuition_credit_balance = 0.0
    else:
        tuition_credit_balance = 0.0

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
        if fee_name in {TUITION_CONVENIENCE_FEE_KEY, TUITION_INSTALLMENT_PLAN_KEY}:
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
            "model": "installment_reference_first" if tuition_installment_plan.get("enabled") else "reference_first",
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
            "tuition_installments_enabled": bool(tuition_installment_plan.get("enabled")),
            "tuition_credit_balance": tuition_credit_balance,
        },
        "admission_fee": admission_fee,
        "payment_collection_pricing": payment_collection_pricing,
        "school_payment_account": {
            "bank_name": None,
            "bank_account": None,
            "bank_account_name": None,
            "bank_branch": None,
        },
        "fees_configuration": {
            "tuition_fee": round(float(fees_config["tuition_fee"] or 0.0), 2),
            "terminal_report_fee": round(float(fees_config["terminal_report_fee"] or 0.0), 2),
            "tuition_convenience_fee_percentage": _get_tuition_convenience_fee_percentage(settings),
            "tuition_transfer_pricing": tuition_pricing,
            "tuition_platform_margin_rate_pct": tuition_pricing["platform_margin_rate_pct"],
            "tuition_provider_fee_rate_pct": tuition_pricing["estimated_provider_fee_rate_pct"],
            "tuition_provider_fee_flat": tuition_pricing["estimated_provider_fee_flat"],
        },
        "tuition_installment_plan": tuition_installment_plan,
        "payment_codes": codes_list,
        "note": "Tuition collection now uses the EduPulse tracked transfer account only. The school tuition amount stays separate from the report-card fee, and the school bank account is intentionally hidden from parent-facing instructions.",
    }
from datetime import datetime, timedelta, timezone


def get_or_create_paystack_transfer_split(
    school,
    provider_settings,
    base_amount,
    total_amount,
    settings,
    sanitize_string,
    call_paystack_api,
    get_payment_collection_split_cache,
    set_payment_collection_split_cache,
    resolve_payment_collection_currency_code,
):
    school_subaccount_code = sanitize_string(provider_settings.get("paystack_subaccount_code") or "") or ""
    if not school_subaccount_code:
        return None, "School settlement is not ready yet. Save verified bank details first so EduPulse can create the school's Paystack subaccount."

    base_amount_minor = int(round(float(base_amount or 0.0) * 100))
    total_amount_minor = int(round(float(total_amount or 0.0) * 100))
    if base_amount_minor <= 0:
        return None, "A positive school fee amount is required before a transfer account can be created."
    if total_amount_minor < base_amount_minor:
        return None, "The payable total cannot be smaller than the school fee amount."

    currency_code = resolve_payment_collection_currency_code(settings)
    cache_key = f"{school.id}:{currency_code}:{school_subaccount_code}:{base_amount_minor}"
    cache = get_payment_collection_split_cache()
    cached_split = cache.get(cache_key) if isinstance(cache, dict) else None
    cached_split_code = sanitize_string((cached_split or {}).get("split_code") or "") or ""
    if cached_split_code:
        return {
            "split_code": cached_split_code,
            "split_id": sanitize_string((cached_split or {}).get("split_id") or "") or None,
            "currency": currency_code,
            "school_settlement_amount_minor": base_amount_minor,
            "platform_settlement_amount_minor": max(0, total_amount_minor - base_amount_minor),
            "school_settlement_amount": round(base_amount_minor / 100.0, 2),
            "platform_settlement_amount": round(max(0, total_amount_minor - base_amount_minor) / 100.0, 2),
            "settlement_mode": "paystack_flat_split",
            "fee_bearer": "account",
        }, None

    split_payload = {
        "name": f"EduPulse Transfer Split {school.id} {base_amount_minor}",
        "type": "flat",
        "currency": currency_code,
        "bearer_type": "account",
        "subaccounts": [
            {
                "subaccount": school_subaccount_code,
                "share": base_amount_minor,
            }
        ],
    }
    result, error = call_paystack_api("/split", method="POST", data=split_payload)
    if error:
        return None, f"Unable to configure Paystack settlement split for this transfer account: {error}"
    if not isinstance(result, dict):
        return None, "Paystack split creation returned an unexpected response."

    split_code = sanitize_string(result.get("split_code") or "") or ""
    if not split_code:
        return None, "Paystack did not return a split code for the transfer settlement."

    next_cache = cache if isinstance(cache, dict) else {}
    next_cache[cache_key] = {
        "split_code": split_code,
        "split_id": sanitize_string(result.get("id") or "") or None,
        "school_id": school.id,
        "currency": currency_code,
        "school_subaccount_code": school_subaccount_code,
        "school_settlement_amount_minor": base_amount_minor,
        "settlement_mode": "paystack_flat_split",
        "fee_bearer": "account",
    }
    set_payment_collection_split_cache(next_cache)

    return {
        "split_code": split_code,
        "split_id": sanitize_string(result.get("id") or "") or None,
        "currency": currency_code,
        "school_settlement_amount_minor": base_amount_minor,
        "platform_settlement_amount_minor": max(0, total_amount_minor - base_amount_minor),
        "school_settlement_amount": round(base_amount_minor / 100.0, 2),
        "platform_settlement_amount": round(max(0, total_amount_minor - base_amount_minor) / 100.0, 2),
        "settlement_mode": "paystack_flat_split",
        "fee_bearer": "account",
    }, None


def get_paystack_dva_provider(country_code, sanitize_string, call_paystack_api, supported_countries, default_provider_preference):
    normalized_country = (sanitize_string(country_code or "GH") or "GH").upper()
    if normalized_country not in supported_countries:
        return None, "Dedicated virtual accounts are currently available only for supported Paystack countries like Ghana and Nigeria."

    providers, error = call_paystack_api("/dedicated_account/available_providers", method="GET")
    if error:
        return None, f"Unable to load Paystack dedicated-account providers: {error}"
    if not isinstance(providers, list) or not providers:
        return None, "Paystack did not return any dedicated-account providers for this integration."

    indexed = {sanitize_string(item.get("provider_slug") or "") or "": item for item in providers}
    for preferred_slug in default_provider_preference:
        if preferred_slug in indexed:
            return indexed[preferred_slug], None

    first_provider = next((item for item in providers if sanitize_string(item.get("provider_slug") or "")), None)
    if not first_provider:
        return None, "Paystack returned provider entries without usable provider slugs."
    return first_provider, None


def create_paystack_collection_customer(email, full_name, phone, metadata, sanitize_string, split_person_name_fn, call_paystack_api):
    first_name, last_name = split_person_name_fn(full_name, sanitize_string)
    payload = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
    }
    if phone:
        payload["phone"] = phone
    if metadata:
        payload["metadata"] = metadata

    result, error = call_paystack_api("/customer", method="POST", data=payload)
    if error:
        return None, f"Unable to create the Paystack customer for this payment route: {error}"
    if not isinstance(result, dict):
        return None, "Paystack customer creation returned an unexpected response."
    customer_code = sanitize_string(result.get("customer_code") or result.get("code") or "") or ""
    if not customer_code:
        return None, "Paystack customer creation did not return a customer code."
    return {
        "customer_code": customer_code,
        "first_name": first_name,
        "last_name": last_name,
    }, None


def create_paystack_dedicated_virtual_account(
    customer_code,
    provider_slug,
    provider_settings,
    split_code,
    phone,
    first_name,
    last_name,
    sanitize_string,
    call_paystack_api,
):
    payload = {
        "customer": customer_code,
        "preferred_bank": provider_slug,
    }
    if split_code:
        payload["split_code"] = split_code
    elif provider_settings.get("paystack_subaccount_code"):
        payload["subaccount"] = provider_settings["paystack_subaccount_code"]
    if phone:
        payload["phone"] = phone
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name

    result, error = call_paystack_api("/dedicated_account", method="POST", data=payload)
    if error:
        return None, f"Unable to create the Paystack transfer account: {error}"
    if not isinstance(result, dict):
        return None, "Paystack dedicated-account creation returned an unexpected response."
    account_number = sanitize_string(result.get("account_number") or "") or ""
    if not account_number:
        return None, "Paystack did not return an account number for the dedicated account."
    return result, None


def create_or_reuse_student_virtual_account_intent(
    student,
    school,
    settings,
    payment_code,
    payment_collection_intent_model,
    sanitize_string,
    get_payment_collection_pricing,
    calculate_payment_collection_breakdown_fn,
    get_payment_provider_settings,
    get_or_create_paystack_transfer_split_fn,
    get_paystack_dva_provider_fn,
    build_intent_customer_email_fn,
    create_paystack_collection_customer_fn,
    create_paystack_dedicated_virtual_account_fn,
    paystack_dva_intent_ttl_days,
    db_session,
):
    now = datetime.now(timezone.utc)
    reference_code = sanitize_string(payment_code.get("reference_code") or payment_code.get("code") or "") or ""
    if not reference_code:
        return None, "A payment reference is required before a transfer route can be created."

    base_amount = round(float(payment_code.get("base_amount") or payment_code.get("amount") or 0.0), 2)
    if base_amount <= 0:
        return None, "This fee route does not currently require payment."

    pricing = dict(get_payment_collection_pricing() or {})
    if isinstance(payment_code.get("pricing_override"), dict):
        pricing.update(payment_code["pricing_override"])
    pricing_breakdown = calculate_payment_collection_breakdown_fn(base_amount, pricing)

    existing = (
        payment_collection_intent_model.query.filter_by(
            school_id=student.school_id,
            student_id=student.id,
            reference_code=reference_code,
            provider="paystack",
            collection_channel="dedicated_virtual_account",
        )
        .order_by(payment_collection_intent_model.id.desc())
        .first()
    )
    existing_expires_at = existing.expires_at if existing else None
    if existing_expires_at and getattr(existing_expires_at, "tzinfo", None) is None:
        existing_expires_at = existing_expires_at.replace(tzinfo=timezone.utc)

    pricing_matches_existing = bool(
        existing
        and round(float(existing.base_amount or 0.0), 2) == pricing_breakdown["base_amount"]
        and round(float(existing.total_amount or 0.0), 2) == pricing_breakdown["total_amount"]
        and round(float(existing.convenience_fee_amount or 0.0), 2) == pricing_breakdown["convenience_fee_amount"]
    )

    if existing and existing.intent_status == "assigned" and (not existing_expires_at or existing_expires_at >= now):
        if pricing_matches_existing:
            return existing, None
        existing.intent_status = "deactivated"
    if existing and existing.intent_status == "paid":
        return existing, None
    if existing and existing.intent_status == "assigned" and existing_expires_at and existing_expires_at < now:
        existing.intent_status = "expired"

    provider_settings = get_payment_provider_settings(settings)
    split_config, error = get_or_create_paystack_transfer_split_fn(
        school,
        provider_settings,
        pricing_breakdown["base_amount"],
        pricing_breakdown["total_amount"],
        settings=settings,
    )
    if error:
        return None, error

    provider, error = get_paystack_dva_provider_fn(settings.country_code if settings else "GH")
    if error:
        return None, error

    reference_email = build_intent_customer_email_fn(student.parent_email or school.school_email, student.school_id, reference_code)
    customer_name = student.parent_name or student.guardian_name or student.name
    customer_result, error = create_paystack_collection_customer_fn(
        reference_email,
        customer_name,
        student.parent_phone or school.school_phone,
        metadata={
            "school_id": student.school_id,
            "student_id": student.id,
            "reference_code": reference_code,
            "payment_type": payment_code.get("payment_category", {}).get("fee_type") or payment_code.get("fee_type"),
        },
    )
    if error:
        return None, error

    dedicated_account, error = create_paystack_dedicated_virtual_account_fn(
        customer_result["customer_code"],
        sanitize_string(provider.get("provider_slug") or "") or "",
        provider_settings,
        split_code=split_config.get("split_code") if split_config else None,
        phone=student.parent_phone or school.school_phone,
        first_name=customer_result["first_name"],
        last_name=customer_result["last_name"],
    )
    if error:
        return None, error

    bank_payload = dedicated_account.get("bank") if isinstance(dedicated_account.get("bank"), dict) else {}
    intent = payment_collection_intent_model(
        school_id=student.school_id,
        student_id=student.id,
        provider="paystack",
        collection_channel="dedicated_virtual_account",
        intent_status="assigned",
        reference_code=reference_code,
        payment_type=sanitize_string(payment_code.get("payment_category", {}).get("fee_type") or payment_code.get("fee_type") or "Tuition") or "Tuition",
        payment_category=payment_code.get("payment_category") if isinstance(payment_code.get("payment_category"), dict) else {},
        base_amount=pricing_breakdown["base_amount"],
        convenience_fee_amount=pricing_breakdown["convenience_fee_amount"],
        estimated_provider_fee_amount=pricing_breakdown["estimated_provider_fee_amount"],
        platform_fee_amount=pricing_breakdown["platform_fee_amount"],
        total_amount=pricing_breakdown["total_amount"],
        currency=settings.currency if settings and settings.currency else "GH₵",
        provider_customer_code=customer_result["customer_code"],
        provider_dedicated_account_id=str(dedicated_account.get("id") or "") or None,
        provider_bank_slug=sanitize_string(bank_payload.get("slug") or provider.get("provider_slug") or "") or None,
        provider_bank_name=sanitize_string(bank_payload.get("name") or provider.get("bank_name") or "") or None,
        provider_account_name=sanitize_string(dedicated_account.get("account_name") or "") or None,
        provider_account_number=sanitize_string(dedicated_account.get("account_number") or "") or None,
        provider_subaccount_code=provider_settings.get("paystack_subaccount_code") or None,
        expires_at=now + timedelta(days=paystack_dva_intent_ttl_days),
        meta={
            "provider": provider,
            "pricing": pricing_breakdown["pricing"],
            "split_config": split_config,
            "raw_account": dedicated_account,
        },
    )
    db_session.add(intent)
    db_session.flush()
    return intent, None


def extract_paystack_virtual_account_identifiers(payload, sanitize_string):
    authorization = payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {}
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    dedicated_account = payload.get("dedicated_account") if isinstance(payload.get("dedicated_account"), dict) else {}
    receiver = payload.get("receiver") if isinstance(payload.get("receiver"), dict) else {}
    recipient = payload.get("recipient") if isinstance(payload.get("recipient"), dict) else {}
    payload_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    customer_metadata = customer.get("metadata") if isinstance(customer.get("metadata"), dict) else {}
    dedicated_account_metadata = dedicated_account.get("metadata") if isinstance(dedicated_account.get("metadata"), dict) else {}
    if not dedicated_account and isinstance(customer.get("dedicated_account"), dict):
        dedicated_account = customer.get("dedicated_account")

    receiver_account = authorization.get("receiver_account") if isinstance(authorization.get("receiver_account"), dict) else {}
    receiver_account_details = (
        authorization.get("receiver_account_details")
        if isinstance(authorization.get("receiver_account_details"), dict)
        else {}
    )

    metadata_candidates = [
        payload_metadata,
        customer_metadata,
        dedicated_account_metadata,
    ]

    def _extract_metadata_value(*keys):
        for metadata in metadata_candidates:
            for key in keys:
                value = sanitize_string(metadata.get(key) or "") if isinstance(metadata, dict) else ""
                if value:
                    return value
        return None

    account_number_candidates = [
        sanitize_string(dedicated_account.get("account_number") or "") or None,
        sanitize_string(receiver.get("account_number") or "") or None,
        sanitize_string(recipient.get("account_number") or "") or None,
        sanitize_string(payload.get("receiver_account_number") or "") or None,
        sanitize_string(payload.get("destination_account_number") or "") or None,
        sanitize_string(payload.get("account_number") or "") or None,
        sanitize_string(authorization.get("receiver_account_number") or "") or None,
        sanitize_string(authorization.get("receiver_bank_account_number") or "") or None,
        sanitize_string(receiver_account.get("account_number") or "") or None,
        sanitize_string(receiver_account_details.get("account_number") or "") or None,
    ]
    customer_code = sanitize_string(customer.get("customer_code") or payload.get("customer_code") or "") or None
    dedicated_account_id = sanitize_string(
        dedicated_account.get("id")
        or receiver.get("dedicated_account_id")
        or recipient.get("dedicated_account_id")
        or payload.get("dedicated_account_id")
        or ""
    ) or None

    return {
        "account_number": next((value for value in account_number_candidates if value), None),
        "customer_code": customer_code,
        "dedicated_account_id": dedicated_account_id,
        "reference_code": _extract_metadata_value("reference_code", "payment_reference", "student_payment_code"),
        "payment_type": _extract_metadata_value("payment_type", "fee_type"),
        "student_id": _extract_metadata_value("student_id"),
        "school_id": _extract_metadata_value("school_id"),
    }


def record_paystack_virtual_account_payment(
    payload,
    event,
    sanitize_string,
    payment_collection_intent_model,
    record_paystack_finance_payment,
    db_session,
):
    identifiers = extract_paystack_virtual_account_identifiers(payload, sanitize_string)
    query = payment_collection_intent_model.query.filter_by(provider="paystack", collection_channel="dedicated_virtual_account")
    intent = None

    def _matches_hint(candidate, key, expected_value):
        if not expected_value:
            return True
        actual_value = getattr(candidate, key, None)
        return sanitize_string(actual_value or "") == sanitize_string(expected_value or "")

    def _find_by_exact_identifier(column_name, value):
        if not value:
            return None
        candidate = query.filter_by(**{column_name: value}).order_by(payment_collection_intent_model.id.desc()).first()
        if not candidate:
            return None
        if not _matches_hint(candidate, "reference_code", identifiers.get("reference_code")):
            return None
        if not _matches_hint(candidate, "payment_type", identifiers.get("payment_type")):
            return None
        if not _matches_hint(candidate, "student_id", identifiers.get("student_id")):
            return None
        if not _matches_hint(candidate, "school_id", identifiers.get("school_id")):
            return None
        return candidate

    if identifiers.get("account_number"):
        intent = _find_by_exact_identifier("provider_account_number", identifiers["account_number"])
    if not intent and identifiers.get("dedicated_account_id"):
        intent = _find_by_exact_identifier("provider_dedicated_account_id", identifiers["dedicated_account_id"])
    if not intent and identifiers.get("customer_code"):
        customer_query = query.filter_by(provider_customer_code=identifiers["customer_code"])
        if identifiers.get("reference_code"):
            customer_query = customer_query.filter_by(reference_code=identifiers["reference_code"])
        if identifiers.get("payment_type"):
            customer_query = customer_query.filter_by(payment_type=identifiers["payment_type"])
        if identifiers.get("student_id"):
            try:
                customer_query = customer_query.filter_by(student_id=int(identifiers["student_id"]))
            except (TypeError, ValueError):
                return None
        if identifiers.get("school_id"):
            customer_query = customer_query.filter_by(school_id=identifiers["school_id"])

        candidates = customer_query.order_by(payment_collection_intent_model.id.desc()).all()
        if len(candidates) == 1:
            intent = candidates[0]
        elif len(candidates) > 1:
            active_candidates = [candidate for candidate in candidates if candidate.intent_status in {"assigned", "paid"}]
            if len(active_candidates) == 1:
                intent = active_candidates[0]

    if not intent:
        return None

    split_config = intent.meta.get("split_config") if isinstance(intent.meta, dict) else {}

    tx_ref = sanitize_string(payload.get("reference") or str(payload.get("id") or ""))
    if intent.provider_reference and intent.provider_reference == tx_ref and intent.intent_status == "paid":
        return {"status": "duplicate", "reference": tx_ref, "intent_id": intent.id}, 200

    try:
        gross_amount_paid = round(float(payload.get("amount") or 0) / 100.0, 2)
    except Exception:
        gross_amount_paid = 0.0

    applied_school_fee_amount = round(
        min(max(gross_amount_paid, 0.0), float(intent.base_amount or 0.0)),
        2,
    )
    collected_convenience_fee_amount = round(
        max(0.0, gross_amount_paid - applied_school_fee_amount),
        2,
    )

    adjusted_payload = {
        **payload,
        "amount": int(round(applied_school_fee_amount * 100)),
        "metadata": {
            "school_id": intent.school_id,
            "student_id": intent.student_id,
            "payment_type": intent.payment_type,
            "payment_category": {
                **(intent.payment_category or {}),
                "reference_code": intent.reference_code,
                "collection_channel": intent.collection_channel,
                "payment_collection_intent_id": intent.id,
                "transfer_total_amount": round(float(intent.total_amount or 0.0), 2),
                "gross_amount_paid": gross_amount_paid,
                "charged_total_amount": gross_amount_paid,
                "applied_school_fee_amount": applied_school_fee_amount,
                "convenience_fee_amount": round(float(intent.convenience_fee_amount or 0.0), 2),
                "collected_convenience_fee_amount": collected_convenience_fee_amount,
                "platform_fee_amount": round(float(intent.platform_fee_amount or 0.0), 2),
                "estimated_provider_fee_amount": round(float(intent.estimated_provider_fee_amount or 0.0), 2),
                "settlement_mode": sanitize_string(split_config.get("settlement_mode") or "reference_first") or "reference_first",
                "split_code": sanitize_string(split_config.get("split_code") or "") or None,
                "school_settlement_amount": round(float(split_config.get("school_settlement_amount") or intent.base_amount or 0.0), 2),
                "platform_settlement_amount": round(float(split_config.get("platform_settlement_amount") or 0.0), 2),
            },
            "reference_code": intent.reference_code,
        },
    }

    body, status_code = record_paystack_finance_payment(adjusted_payload, event=event, school_id_scope=intent.school_id)
    if status_code >= 400:
        return body, status_code

    authorization = payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {}
    intent.intent_status = "paid" if body.get("status") in {"recorded", "duplicate", "blocked"} else intent.intent_status
    intent.provider_reference = tx_ref or intent.provider_reference
    intent.provider_last_event = event
    intent.paid_at = datetime.now(timezone.utc)
    intent.payer_name = sanitize_string(authorization.get("sender_name") or intent.payer_name or "") or intent.payer_name
    intent.payer_bank_name = sanitize_string(authorization.get("sender_bank") or intent.payer_bank_name or "") or intent.payer_bank_name
    intent.meta = {
        **(intent.meta or {}),
        "last_charge_success_payload": {
            "reference": tx_ref,
            "authorization": authorization,
            "customer": payload.get("customer") if isinstance(payload.get("customer"), dict) else {},
        },
    }
    db_session.commit()
    return {
        **body,
        "payment_collection_intent_id": intent.id,
        "transfer_total_amount": round(float(intent.total_amount or 0.0), 2),
        "gross_amount_paid": gross_amount_paid,
        "applied_school_fee_amount": applied_school_fee_amount,
        "provider_account_number": intent.provider_account_number,
        "provider_bank_name": intent.provider_bank_name,
    }, status_code

def record_paystack_parent_admission_payment(
    payload,
    event,
    sanitize_string,
    parent_admission_application_model,
    school_settings_model,
    get_parent_admission_payment_summary,
    normalize_parent_admission_payment_summary,
    get_school_admission_fee_config,
    set_parent_admission_payment_summary,
    log_action,
    db_session,
):
    tx_ref = sanitize_string(payload.get("reference") or str(payload.get("id") or ""))
    if not tx_ref:
        return {"status": "error", "message": "Missing transaction reference"}, 400

    amount_minor = payload.get("amount")
    try:
        amount = round(float(amount_minor or 0) / 100.0, 2)
    except Exception:
        return {"status": "error", "message": "Invalid payment amount"}, 400

    if amount <= 0:
        return {"status": "error", "message": "Amount must be greater than zero"}, 400

    metadata = payload.get("metadata") or {}
    school_id = sanitize_string(metadata.get("school_id") or "") or None
    application = None

    application_id = metadata.get("parent_admission_application_id")
    if application_id is not None:
        try:
            query = parent_admission_application_model.query.filter_by(id=int(application_id))
            if school_id:
                query = query.filter_by(school_id=school_id)
            application = query.first()
        except (TypeError, ValueError):
            application = None

    if not application:
        status_token = sanitize_string(metadata.get("status_token") or "") or None
        if status_token:
            query = parent_admission_application_model.query.filter_by(status_token=status_token)
            if school_id:
                query = query.filter_by(school_id=school_id)
            application = query.first()

    if not application:
        return {"status": "unmapped", "reference": tx_ref}, 200

    settings = school_settings_model.query.filter_by(school_id=application.school_id).first()
    payment_summary = get_parent_admission_payment_summary(application, settings)
    if payment_summary.get("status") == "paid" and payment_summary.get("reference") == tx_ref:
        return {"status": "duplicate", "reference": tx_ref, "application_id": application.id}, 200

    paid_at = sanitize_string(payload.get("paid_at") or payload.get("created_at") or "") or datetime.now(timezone.utc).isoformat()
    updated_summary = normalize_parent_admission_payment_summary(
        {
            **payment_summary,
            "status": "paid",
            "reference": tx_ref,
            "amount": amount,
            "provider": "paystack",
            "paid_at": paid_at,
        },
        fee_config=get_school_admission_fee_config(settings),
    )
    set_parent_admission_payment_summary(application, updated_summary)

    log_action(
        user_id=None,
        school_id=application.school_id,
        action="PARENT_ADMISSION_FEE_PAID",
        details=f"Parent admission fee paid for {application.application_code} (ref={tx_ref}, amount=GH₵{amount:.2f})",
    )
    db_session.commit()
    return {"status": "recorded", "reference": tx_ref, "application_id": application.id}, 200
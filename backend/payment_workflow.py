import re


def public_payment_setup_failure_message():
    return (
        "EduPulse could not connect to the payment provider right now. "
        "Please try again shortly or use the school office for manual assistance."
    )


def tenant_email_delivery_failure_message():
    return "Invite created, but the welcome email could not be delivered right now."


def public_tracked_transfer_failure_message():
    return (
        "EduPulse could not prepare the tracked transfer account right now. "
        "Please try again shortly or use the school office for manual assistance."
    )


def looks_like_provider_error(message, sanitize_string):
    normalized = (sanitize_string(message or "") or "").lower()
    if not normalized:
        return False
    if normalized.startswith("school settlement is not ready yet"):
        return False
    provider_markers = [
        "paystack",
        "unauthorized",
        "dedicated-account",
        "dedicated account",
        "transfer account",
        "customer creation",
        "customer for this payment route",
        "bank directory",
        "bank account with paystack",
        "split code",
        "provider",
        "401",
        "403",
        "404",
        "500",
    ]
    return any(marker in normalized for marker in provider_markers)


def build_intent_customer_email(base_email, school_id, reference_code, sanitize_string):
    email = sanitize_string(base_email or "") or ""
    safe_ref = re.sub(r"[^a-z0-9]+", "-", (reference_code or "").lower()).strip("-") or "payment"
    safe_school = re.sub(r"[^a-z0-9]+", "-", (school_id or "").lower()).strip("-") or "school"
    if "@" in email:
        local_part, domain = email.split("@", 1)
        local_part = local_part or "parent"
        domain = domain or "example.com"
        return f"{local_part}+edupulse-{safe_school}-{safe_ref}@{domain}"
    return f"edupulse-{safe_school}-{safe_ref}@parents.edupulse.invalid"


def split_person_name(full_name, sanitize_string, fallback_last_name="Customer"):
    parts = [part for part in (sanitize_string(full_name or "") or "").split() if part]
    if not parts:
        return "EduPulse", fallback_last_name
    if len(parts) == 1:
        return parts[0], fallback_last_name
    return parts[0], " ".join(parts[1:])


def calculate_payment_collection_breakdown(base_amount, pricing):
    base_amount = round(float(base_amount or 0.0), 2)
    estimated_provider_fee_amount = round(
        (base_amount * (float(pricing.get("estimated_provider_fee_rate_pct") or 0.0) / 100.0))
        + float(pricing.get("estimated_provider_fee_flat") or 0.0),
        2,
    )
    platform_fee_amount = round(float(pricing.get("platform_fee_flat") or 0.0), 2)
    convenience_fee_amount = round(
        (estimated_provider_fee_amount + platform_fee_amount)
        if pricing.get("charge_parent_convenience_fee", True)
        else 0.0,
        2,
    )
    return {
        "base_amount": base_amount,
        "estimated_provider_fee_amount": estimated_provider_fee_amount,
        "platform_fee_amount": platform_fee_amount,
        "convenience_fee_amount": convenience_fee_amount,
        "total_amount": round(base_amount + convenience_fee_amount, 2),
        "pricing": pricing,
    }
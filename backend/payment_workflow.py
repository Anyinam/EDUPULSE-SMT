import hashlib
import re
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP


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


_CUSTOMER_EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_EMAIL_LOCAL_PART_MAX = 64
_PHONE_DIAL_CODES = {"GH": ("233", 9), "NG": ("234", 10)}


def first_valid_customer_email(*candidates):
    for value in candidates:
        email = str(value or "").strip()
        if _CUSTOMER_EMAIL_PATTERN.match(email):
            return email
    return ""


def build_intent_customer_email(base_email, school_id, reference_code, sanitize_string):
    email = (sanitize_string(base_email or "") or "").strip()
    safe_ref = re.sub(r"[^a-z0-9]+", "-", (reference_code or "").lower()).strip("-") or "payment"
    safe_school = re.sub(r"[^a-z0-9]+", "-", (school_id or "").lower()).strip("-") or "school"
    tag = f"edupulse-{safe_school}-{safe_ref}"
    if _CUSTOMER_EMAIL_PATTERN.match(email):
        local_part, domain = email.rsplit("@", 1)
        local_part = local_part.split("+", 1)[0] or "parent"
        candidate = f"{local_part}+{tag}"
        if len(candidate) > _EMAIL_LOCAL_PART_MAX:
            digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()[:16]
            candidate = f"{local_part[:_EMAIL_LOCAL_PART_MAX - len(digest) - 4]}+ep-{digest}"
        return f"{candidate}@{domain.lower()}"
    if len(tag) > _EMAIL_LOCAL_PART_MAX:
        tag = f"edupulse-{hashlib.sha256(tag.encode('utf-8')).hexdigest()[:24]}"
    return f"{tag}@parents.edupulse.invalid"


def normalize_paystack_customer_phone(*candidates, country_code="GH"):
    """Return the first candidate as an E.164 number Paystack accepts, else an empty string."""
    dial_code, national_length = _PHONE_DIAL_CODES.get((country_code or "GH").upper(), _PHONE_DIAL_CODES["GH"])
    for value in candidates:
        digits = re.sub(r"\D+", "", str(value or ""))
        if digits.startswith("00"):
            digits = digits[2:]
        if digits.startswith(dial_code) and len(digits) == len(dial_code) + national_length:
            return f"+{digits}"
        if digits.startswith("0") and len(digits) == national_length + 1:
            return f"+{dial_code}{digits[1:]}"
        if len(digits) == national_length:
            return f"+{dial_code}{digits}"
    return ""


def split_person_name(full_name, sanitize_string, fallback_last_name="Customer"):
    parts = [part for part in (sanitize_string(full_name or "") or "").split() if part]
    if not parts:
        return "EduPulse", fallback_last_name
    if len(parts) == 1:
        return parts[0], fallback_last_name
    return parts[0], " ".join(parts[1:])


def get_tuition_collection_pricing(pricing=None):
    pricing = pricing or {}
    return {
        "fee_model": "gross_up_margin_v1",
        "estimated_provider_fee_rate_pct": pricing.get("tuition_provider_fee_rate_pct", 1.95),
        "estimated_provider_fee_flat": pricing.get("tuition_provider_fee_flat", 0),
        "platform_margin_rate_pct": pricing.get("tuition_platform_margin_rate_pct", 1),
        "platform_fee_flat": 0,
        "charge_parent_convenience_fee": True,
        "platform_fee_label": "Processing and EduPulse service fee",
    }


def calculate_payment_collection_breakdown(base_amount, pricing):
    if pricing.get("fee_model") == "gross_up_margin_v1":
        penny = Decimal("0.01")
        base = Decimal(str(base_amount or 0)).quantize(penny, rounding=ROUND_HALF_UP)
        provider_rate = Decimal(str(pricing.get("estimated_provider_fee_rate_pct", 1.95))) / 100
        provider_flat = Decimal(str(pricing.get("estimated_provider_fee_flat", 0)))
        margin_rate = Decimal(str(pricing.get("platform_margin_rate_pct", 1))) / 100
        platform_flat = Decimal(str(pricing.get("platform_fee_flat", 0)))
        if not all(value.is_finite() for value in (base, provider_rate, provider_flat, margin_rate, platform_flat)):
            raise ValueError("Payment fee configuration must be finite.")
        if base < 0 or not 0 <= provider_rate < 1 or min(provider_flat, margin_rate, platform_flat) < 0:
            raise ValueError("Invalid payment fee configuration.")
        platform_margin = (base * margin_rate + platform_flat).quantize(penny, rounding=ROUND_HALF_UP)
        total = ((base + platform_margin + provider_flat) / (1 - provider_rate)).quantize(penny, rounding=ROUND_CEILING) if base else Decimal(0)
        provider_fee = (total * provider_rate + provider_flat).quantize(penny, rounding=ROUND_HALF_UP) if base else Decimal(0)
        return {
            "fee_model": "gross_up_margin_v1",
            "base_amount": float(base),
            "estimated_provider_fee_amount": float(provider_fee),
            "platform_fee_amount": float(platform_margin if base else Decimal(0)),
            "convenience_fee_amount": float(total - base),
            "total_amount": float(total),
            "rounding_surplus_amount": float(total - base - provider_fee - (platform_margin if base else Decimal(0))),
            "pricing": pricing,
        }

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
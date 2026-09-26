"""Overage auto-billing sweep.

Keeps ledger entries immutable:
- Pending invoices are ledger entries with tx_type starting with 'subscription' and metadata.status == 'Pending'.
- Successful auto-charges create a NEW ledger entry that references the invoice.

This avoids mutating invoice metadata (which would break the ledger hash chain).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.api.models import AcademicTerm, LedgerEntry, PlatformSetting, School, User, add_ledger_entry, db
from backend.subscription_metering import get_billing_visibility, get_next_published_national_basic_term_start
from backend.subscription_state import normalize_plan_name
from backend.utils import send_email_notification

logger = logging.getLogger(__name__)

DEFAULT_OVERAGE_GRACE_DAYS = 30
DEFAULT_DOWNGRADE_AFTER_DAYS = 2
DEFAULT_RETRY_COOLDOWN_HOURS = 24
INVOICE_TYPES = {"subscription_prorated"}
SETTLEMENT_TYPE = "subscription_overage_charge"
FAILED_TYPE = "subscription_overage_charge_failed"
RENEWAL_TYPE = "subscription_renewal"
RENEWAL_FAILED_TYPE = "subscription_renewal_failed"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except Exception:
        return None


def _get_auto_billing_config(school_id: str) -> dict[str, Any]:
    setting = PlatformSetting.query.filter_by(setting_key=f"auto_billing:{school_id}").first()
    return setting.setting_value if setting and isinstance(setting.setting_value, dict) else {}


def _get_default_authorization(config: dict[str, Any]) -> tuple[str | None, str | None]:
    cards = config.get("cards") if isinstance(config.get("cards"), list) else []
    default_card = next((c for c in cards if isinstance(c, dict) and c.get("is_default")), None)
    if not default_card and cards:
        default_card = next((c for c in cards if isinstance(c, dict)), None)

    if default_card:
        return (
            (default_card.get("authorization_code") or config.get("authorization_code")),
            (default_card.get("customer_email") or config.get("customer_email")),
        )

    return (config.get("authorization_code"), config.get("customer_email"))


def _invoice_due_date(entry: LedgerEntry, grace_days: int) -> datetime:
    meta = entry.meta or {}
    due_date = _parse_iso_date(meta.get("due_date"))
    if due_date:
        return datetime.combine(due_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    created_at = entry.created_at
    if created_at is None:
        created_at = _now_utc()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at + timedelta(days=max(1, int(grace_days)))


def _already_settled(invoice_ref: str) -> bool:
    if not invoice_ref:
        return False
    settlements = LedgerEntry.query.filter_by(tx_type=SETTLEMENT_TYPE).all()
    for settlement in settlements:
        meta = settlement.meta or {}
        if meta.get("invoice_tx_ref") == invoice_ref:
            return True
    return False


def _last_attempt_at(school_id: str, invoice_ref: str) -> datetime | None:
    if not invoice_ref:
        return None
    attempts = (
        LedgerEntry.query.filter(
            LedgerEntry.school_id == school_id,
            LedgerEntry.tx_type.in_([SETTLEMENT_TYPE, FAILED_TYPE]),
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(50)
        .all()
    )
    for entry in attempts:
        meta = entry.meta or {}
        if meta.get("invoice_tx_ref") != invoice_ref:
            continue
        created_at = entry.created_at
        if not created_at:
            return None
        if created_at.tzinfo is None:
            return created_at.replace(tzinfo=timezone.utc)
        return created_at
    return None


def _append_billing_timeline_event(
    school_id: str,
    *,
    event_type: str,
    status: str,
    title: str,
    details: str,
    amount: float | None = None,
    reference: str | None = None,
    due_date: str | None = None,
    next_retry_at: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    import hashlib
    import json
    import time

    setting_key = f"billing_timeline:{school_id}"
    setting = PlatformSetting.query.filter_by(setting_key=setting_key).first()
    events = setting.setting_value if setting and isinstance(setting.setting_value, list) else []

    event = {
        "id": hashlib.sha256(
            f"{school_id}:{event_type}:{reference or ''}:{time.time()}".encode("utf-8")
        ).hexdigest()[:20],
        "created_at": _now_utc().isoformat(),
        "event_type": event_type,
        "status": status,
        "title": title,
        "details": details,
        "amount": amount,
        "reference": reference,
        "due_date": due_date,
        "next_retry_at": next_retry_at,
        "metadata": metadata or {},
    }

    events.insert(0, event)
    events = events[:200]

    safe_events = json.loads(json.dumps(events))
    if not setting:
        setting = PlatformSetting(setting_key=setting_key, setting_value=safe_events)
        db.session.add(setting)
    else:
        setting.setting_value = safe_events


def _disable_auto_billing(school_id: str):
    setting_key = f"auto_billing:{school_id}"
    setting = PlatformSetting.query.filter_by(setting_key=setting_key).first()
    config = setting.setting_value if setting and isinstance(setting.setting_value, dict) else {}
    if not isinstance(config, dict):
        config = {}
    if config.get("enabled") is False and setting:
        return
    config = {**config, "enabled": False, "updated_at": _now_utc().isoformat()}
    if not setting:
        db.session.add(PlatformSetting(setting_key=setting_key, setting_value=config))
    else:
        setting.setting_value = config


def _next_term_renewal_at(
    school_id: str,
    current_due_at: datetime,
    now: datetime | None = None,
) -> datetime:
    comparison_at = max(current_due_at, now or _now_utc())
    comparison_date = comparison_at.date()
    terms = AcademicTerm.query.filter_by(school_id=school_id).all()
    future_dates = []
    for term in terms:
        if term.billing_due_date and term.billing_due_date > comparison_date:
            future_dates.append(term.billing_due_date)
        elif term.start_date and term.start_date > comparison_date:
            future_dates.append(term.start_date)

    if future_dates:
        next_date = min(future_dates)
        return datetime.combine(next_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    published_next_date = get_next_published_national_basic_term_start(comparison_date)
    if published_next_date:
        return datetime.combine(published_next_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    return comparison_at + timedelta(days=120)


def _renewal_cycle_processed(school_id: str, cycle_key: str) -> bool:
    entries = LedgerEntry.query.filter(
        LedgerEntry.school_id == school_id,
        LedgerEntry.tx_type == RENEWAL_TYPE,
    ).all()
    return any((entry.meta or {}).get("renewal_cycle") == cycle_key for entry in entries)


def _last_renewal_attempt_at(school_id: str, cycle_key: str) -> datetime | None:
    attempts = (
        LedgerEntry.query.filter_by(
            school_id=school_id,
            tx_type=RENEWAL_FAILED_TYPE,
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(20)
        .all()
    )
    for entry in attempts:
        if (entry.meta or {}).get("renewal_cycle") != cycle_key:
            continue
        created_at = entry.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at
    return None


def process_due_term_renewals(
    *,
    now: datetime | None = None,
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS,
    limit: int = 200,
) -> dict[str, int]:
    """Auto-charge due paid-plan renewals from the current active enrollment."""
    now_utc = now or _now_utc()
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    checked = attempted = charged = skipped = failed = 0
    schools_with_billing_dates = (
        School.query.filter(School.next_billing_date.isnot(None))
        .order_by(School.next_billing_date.asc())
        .all()
    )
    candidates = []
    for school in schools_with_billing_dates:
        due_at = school.next_billing_date
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if normalize_plan_name(school.subscription_plan) in {"Basic", "Premium"} and due_at <= now_utc:
            candidates.append(school)
        if len(candidates) >= max(1, int(limit)):
            break

    from backend.paystack_integration import PaystackError, charge_authorization

    for school in candidates:
        checked += 1
        due_at = school.next_billing_date
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        cycle_key = due_at.date().isoformat()

        if _renewal_cycle_processed(school.id, cycle_key):
            school.next_billing_date = _next_term_renewal_at(school.id, due_at, now_utc)
            db.session.commit()
            skipped += 1
            continue

        config = _get_auto_billing_config(school.id)
        authorization_code, customer_email = _get_default_authorization(config)
        if not config.get("enabled") or not authorization_code:
            skipped += 1
            continue

        email = customer_email or getattr(school, "billing_email", None)
        if not email:
            proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
            email = proprietor.email if proprietor else None
        if not email:
            failed += 1
            continue

        last_attempt = _last_renewal_attempt_at(school.id, cycle_key)
        if last_attempt and (now_utc - last_attempt) < timedelta(hours=max(1, int(retry_cooldown_hours))):
            skipped += 1
            continue

        plan_name = normalize_plan_name(school.subscription_plan)
        billing_visibility = get_billing_visibility(school.id, commit=False)
        student_count = int((billing_visibility.get("meter") or {}).get("active_students") or 0)
        breakdown = billing_visibility.get("cost_breakdown") or {}
        amount_cedis = float(breakdown.get("total_due") or 0)
        metadata = {
            "school_id": school.id,
            "transaction_type": RENEWAL_TYPE,
            "plan_name": plan_name,
            "renewal_cycle": cycle_key,
            "student_count": student_count,
            "included_students": breakdown.get("included_students", 0),
            "overage_students": breakdown.get("overage_students", 0),
            "overage_rate": breakdown.get("overage_rate", 0),
            "base_fee": breakdown.get("base_fee", 0),
        }

        attempted += 1
        try:
            tx = charge_authorization(
                email=email,
                amount_cents=int(round(amount_cedis * 100)),
                authorization_code=authorization_code,
                metadata=metadata,
            )
            paystack_reference = tx.get("reference") or f"RENEW-{school.id}-{cycle_key}"
            add_ledger_entry(
                school_id=school.id,
                tx_type=RENEWAL_TYPE,
                tx_ref=paystack_reference,
                amount=amount_cedis,
                source="paystack_auto",
                created_at=now_utc,
                metadata={
                    **metadata,
                    "status": "Completed",
                    "paystack_reference": tx.get("reference"),
                    "authorization_last4": (tx.get("authorization") or {}).get("last4"),
                    "charged_at": now_utc.isoformat(),
                },
            )
            school.current_student_count = student_count
            school.last_metered_at = now_utc
            school.subscription_status = "Active"
            school.next_billing_date = _next_term_renewal_at(school.id, due_at, now_utc)
            db.session.commit()
            charged += 1
        except PaystackError as exc:
            db.session.rollback()
            add_ledger_entry(
                school_id=school.id,
                tx_type=RENEWAL_FAILED_TYPE,
                tx_ref=f"FAIL-RENEW-{school.id}-{now_utc.strftime('%Y%m%d%H%M%S')}",
                amount=0.0,
                source="paystack_auto",
                created_at=now_utc,
                metadata={
                    **metadata,
                    "status": "Failed",
                    "attempted_at": now_utc.isoformat(),
                    "error": str(exc),
                },
            )
            db.session.commit()
            failed += 1

    return {
        "checked": checked,
        "attempted": attempted,
        "charged": charged,
        "skipped": skipped,
        "failed": failed,
    }


def process_pending_overage_invoices(
    *,
    now: datetime | None = None,
    grace_days: int = DEFAULT_OVERAGE_GRACE_DAYS,
    downgrade_after_days: int = DEFAULT_DOWNGRADE_AFTER_DAYS,
    retry_cooldown_hours: int = DEFAULT_RETRY_COOLDOWN_HOURS,
    limit: int = 200,
) -> dict[str, int]:
    """Charge pending overage invoices that are past due.

    Returns counts: checked / attempted / charged / skipped / failed.
    """

    now_utc = now or _now_utc()
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    checked = attempted = charged = skipped = failed = 0

    candidates = (
        LedgerEntry.query.filter(LedgerEntry.tx_type.in_(INVOICE_TYPES))
        .order_by(LedgerEntry.created_at.asc())
        .limit(max(1, int(limit)))
        .all()
    )

    from backend.paystack_integration import PaystackError, charge_authorization

    for entry in candidates:
        checked += 1
        meta = entry.meta or {}
        if meta.get("status") != "Pending":
            skipped += 1
            continue

        invoice_ref = entry.tx_ref
        if _already_settled(invoice_ref):
            skipped += 1
            continue

        due_at = _invoice_due_date(entry, grace_days)
        if now_utc < due_at:
            skipped += 1
            continue

        downgrade_after = due_at + timedelta(days=max(0, int(downgrade_after_days)))

        school = School.query.get(entry.school_id)
        if not school:
            failed += 1
            continue

        # If already past downgrade window and still unpaid, revert to Free Tier.
        if downgrade_after_days is not None and now_utc >= downgrade_after and not _already_settled(invoice_ref):
            previous_plan = school.subscription_plan
            school.subscription_plan = "Free Tier"
            school.subscription_status = "Active"
            school.next_billing_date = None
            school.trial_plan = None
            school.trial_end_date = None
            _disable_auto_billing(entry.school_id)

            proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
            if proprietor and proprietor.email:
                try:
                    send_email_notification(
                        proprietor.email,
                        f"Subscription downgraded to Free Tier - {school.name}",
                        (
                            f"Hello {proprietor.username},\n\n"
                            f"We could not complete the overage payment for invoice {invoice_ref} after the grace period. "
                            f"Your subscription has been reverted to Free Tier.\n\n"
                            f"To restore Basic/Premium, please visit the Subscription page and make payment.\n\n"
                            f"- EduPulse Billing"
                        ),
                    )
                except Exception:
                    logger.exception("Failed to send downgrade email for school %s", school.id)

            _append_billing_timeline_event(
                school_id=school.id,
                event_type="plan_downgrade",
                status="completed",
                title="Plan reverted to Free Tier",
                details=f"Invoice {invoice_ref} remained unpaid after grace window; plan reverted from {previous_plan} to Free Tier.",
                reference=invoice_ref,
                due_date=due_at.date().isoformat(),
            )

            db.session.commit()
            charged += 1  # treat downgrade as a processed outcome
            continue

        config = _get_auto_billing_config(entry.school_id)
        if not config.get("enabled"):
            skipped += 1
            continue

        authorization_code, customer_email = _get_default_authorization(config)
        if not authorization_code:
            skipped += 1
            continue

        email = customer_email or getattr(school, "billing_email", None)
        if not email:
            proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
            email = proprietor.email if proprietor else None
        if not email:
            failed += 1
            continue

        amount_cedis = float(entry.amount or 0)
        if amount_cedis <= 0:
            skipped += 1
            continue

        last_attempt = _last_attempt_at(entry.school_id, invoice_ref)
        if last_attempt and (now_utc - last_attempt) < timedelta(hours=max(1, int(retry_cooldown_hours))):
            skipped += 1
            continue

        attempted += 1
        try:
            tx = charge_authorization(
                email=email,
                amount_cents=int(round(amount_cedis * 100)),
                authorization_code=authorization_code,
                metadata={
                    "school_id": entry.school_id,
                    "invoice_tx_ref": invoice_ref,
                    "invoice_type": entry.tx_type,
                    "reason": meta.get("kind") or "overage",
                },
            )

            paystack_reference = tx.get("reference") or f"AUTO-{entry.school_id}-{now_utc.strftime('%Y%m%d%H%M%S')}"

            add_ledger_entry(
                school_id=entry.school_id,
                tx_type=SETTLEMENT_TYPE,
                tx_ref=paystack_reference,
                amount=amount_cedis,
                source="paystack_auto",
                metadata={
                    "status": "Completed",
                    "invoice_tx_ref": invoice_ref,
                    "paystack_reference": tx.get("reference"),
                    "authorization_last4": (tx.get("authorization") or {}).get("last4"),
                    "charged_at": now_utc.isoformat(),
                },
            )

            db.session.commit()
            charged += 1

            logger.info(
                "Auto-charged overage invoice %s for school %s: GH₵ %.2f",
                invoice_ref,
                entry.school_id,
                amount_cedis,
            )

        except PaystackError as exc:
            db.session.rollback()
            failed += 1

            # Record failure as immutable ledger entry (amount=0) for audit + throttling.
            fail_ref = f"FAIL-{invoice_ref}-{now_utc.strftime('%Y%m%d%H%M%S')}"
            add_ledger_entry(
                school_id=entry.school_id,
                tx_type=FAILED_TYPE,
                tx_ref=fail_ref,
                amount=0.0,
                source="paystack_auto",
                metadata={
                    "status": "Failed",
                    "invoice_tx_ref": invoice_ref,
                    "attempted_at": now_utc.isoformat(),
                    "error": str(exc),
                    "due_date": due_at.date().isoformat(),
                },
            )

            # Notify proprietor.
            proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
            if proprietor and proprietor.email:
                try:
                    deadline = downgrade_after.date().isoformat() if downgrade_after_days is not None else None
                    send_email_notification(
                        proprietor.email,
                        f"Action required: subscription auto-billing failed - {school.name}",
                        (
                            f"Hello {proprietor.username},\n\n"
                            f"We attempted to charge your saved card for an overage invoice and it failed.\n\n"
                            f"Invoice: {invoice_ref}\n"
                            f"Amount: GH₵ {amount_cedis:.2f}\n"
                            f"Reason: {str(exc)}\n\n"
                            + (f"Please settle this by {deadline} to avoid reverting to Free Tier.\n\n" if deadline else "")
                            + "You can resolve this from your Proprietor dashboard → Subscription & Billing.\n\n"
                            + "- EduPulse Billing"
                        ),
                    )
                except Exception:
                    logger.exception("Failed to send auto-billing failure email for school %s", school.id)

            _append_billing_timeline_event(
                school_id=school.id,
                event_type="overage_charge",
                status="failed",
                title="Auto-billing failed",
                details=f"Auto-billing failed for invoice {invoice_ref}. {str(exc)}",
                amount=float(amount_cedis),
                reference=invoice_ref,
                due_date=due_at.date().isoformat(),
                next_retry_at=(now_utc + timedelta(hours=max(1, int(retry_cooldown_hours)))).isoformat(),
            )

            db.session.commit()

            logger.warning(
                "Auto-charge failed for invoice %s (school %s): %s",
                invoice_ref,
                entry.school_id,
                str(exc),
            )
        except Exception as exc:
            db.session.rollback()
            failed += 1
            logger.exception(
                "Unexpected auto-charge error for invoice %s (school %s): %s",
                invoice_ref,
                entry.school_id,
                str(exc),
            )

    return {
        "checked": checked,
        "attempted": attempted,
        "charged": charged,
        "skipped": skipped,
        "failed": failed,
    }

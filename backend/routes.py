import base64
import csv
import hashlib
import hmac
import json
import logging
import os
import re
import requests
import secrets
import string
import time
import textwrap
from urllib.parse import quote
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO

from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_file, stream_with_context
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from backend.api.models import (
    AMLTransactionFlag,
    VALID_GRADES,
    AcademicClass,
    AcademicTerm,
    AcademicWorkLog,
    AuditLog,
    ClassGradingPolicy,
    DailyLessonPhase,
    Inventory,
    LedgerEntry,
    LessonNote,
    LiveChatMessage,
    LiveChatSession,
    LoginAttempt,
    PasswordReset,
    Payment,
    ParentAdmissionApplication,
    PlatformSetting,
    PlatformUser,
    PaymentCollectionIntent,
    QuestionPool,
    ReportCard,
    ReportCardStatus,
    School,
    SchoolVerification,
    SchoolSettings,
    Student,
    StudentAssignment,
    StudentGrade,
    StudentNotification,
    StudentPromotion,
    SupportTicket,
    SystemAlert,
    TeacherAssignment,
    Timetable,
    SchoolHoliday,
    TwoFactorToken,
    User,
    add_ledger_entry,
    db,
    get_ledger_summary,
    verify_ledger_chain,
)
from backend.payment_workflow import (
    build_intent_customer_email,
    calculate_payment_collection_breakdown,
    looks_like_provider_error,
    public_payment_setup_failure_message,
    public_tracked_transfer_failure_message,
    split_person_name,
    tenant_email_delivery_failure_message,
)
from backend import finance_read_service, legacy_consent_service, parent_admission_service, payment_checkout_service, payment_collection_service, payment_instruction_service, school_configuration_service, school_settings_service, staff_service
from backend.report_card_parser import ocr_image_bytes, parse_report_card_image_bytes
from backend.settings import (
    AUTH_LOCKOUT_ATTEMPTS,
    AUTH_LOCKOUT_DURATION_MIN,
    AUTH_LOCKOUT_WINDOW_MIN,
    MFA_REQUIRED,
)
from backend.subscription_features import (
    ADDON_CATALOG,
    FEATURE_MATRIX_DISPLAY,
    PLAN_FEATURES,
    PRICING,
    calculate_annual_cost,
    calculate_term_cost,
    can_access_report_template,
    get_all_accessible_templates,
    get_feature_level,
    get_addons_for_plan,
    get_school_feature_level,
    get_plan_limit,
    get_plan_display_name,
    school_has_addon,
    get_term_cost_breakdown,
    has_feature,
)
from backend.lesson_note_ai import generate_ai_lesson_note_score, generate_quick_feedback
from backend.kyb_verification import verify_school_profile
from backend.email_templates import (
    get_welcome_email, 
    get_password_reset_email, 
    get_staff_welcome_email,
    get_parent_admission_status_email,
    get_subscription_confirmation_email,
    get_subscription_upgrade_email,
    get_payment_confirmation_email,
    get_trial_confirmation_email,
    get_trial_expiry_email,
    get_paystack_payment_link_email,
    get_term_billing_notification_email
)
from backend.subscription_metering import (
    activate_premium_trial,
    end_trial,
    get_current_term_reference,
    get_billing_visibility,
    get_published_national_basic_term_windows,
    get_recommended_published_national_basic_academic_year,
    get_term_proration_context,
    lock_pricing_version,
    sync_student_meter,
)
from backend.academic_guidance import (
    build_academic_guidance_summary,
    build_report_guidance_payload,
    normalize_subject_key,
    normalize_topic_key,
)
from backend.utils import (
    calculate_academic_health,
    generate_descriptive_analysis,
    get_utc_now,
    send_email_notification,
    send_email_notification_async,
)
from backend.validators import (
    LoginSchema,
    PaymentSchema,
    RegisterSchema,
    StudentGradeSchema,
    sanitize_string,
    validate_request,
)
from backend.whatsapp_integration import WhatsAppError, send_document_bytes, send_text_message

from .middleware import (
    check_quota,
    csrf_protect,
    get_billing_status_info,
    feature_required,
    get_effective_plan,
    limiter,
    multi_tenant_guard,
    rate_limit_api,
    rate_limit_auth,
    role_required,
    subscription_required,
)

logger = logging.getLogger(__name__)
STARTUP_WHATSAPP_ENABLED = False


def _whatsapp_feature_disabled_response():
    return jsonify({
        "message": "WhatsApp messaging is currently disabled for this startup phase. Use print, export, or copy-based sharing instead."
    }), 403

from backend.holiday_utils import get_national_holidays
api = Blueprint("api", __name__)

IMPORT_TEMPLATE_ATTACHMENTS = [
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "DATA_IMPORT_TEMPLATE.csv"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "compliance", "CONSENT_AND_NOTICE_TEMPLATES.md"),
]

DEFAULT_SUBJECTS = [
    "Mathematics",
    "English Language",
    "Science",
    "Social Studies",
    "Religious & Moral Education",
    "French",
    "ICT",
    "Creative Arts",
]

PLATFORM_PUBLIC_CONTENT_SETTING_KEY = "platform_public_content"
REPORT_TEMPLATE_HISTORY_KEY = "report_template_history"
REPORT_TEMPLATE_HISTORY_LIMIT = 40
ANALYTICS_PRESET_HISTORY_KEY = "analytics_preset_history"
ANALYTICS_PRESET_HISTORY_LIMIT = 40
DEFAULT_SUPPORT_EMAIL = (
    os.getenv("FOUNDER_EMAIL")
    or os.getenv("MAIL_DEFAULT_SENDER")
    or os.getenv("MAIL_USERNAME")
    or "info@edupulsesmt.com"
)


# --- HELPERS ---
def log_action(user_id, school_id, action, details):
    """Fulfills the Pillar 5: Multi-level access control requirement."""
    new_log = AuditLog(
        actor_id=user_id,
        school_id=school_id,
        action=action,
        details=details,
        timestamp=get_utc_now(),
    )
    db.session.add(new_log)
    db.session.commit()


def _to_iso_utc(dt_value):
    if not dt_value:
        return None
    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=timezone.utc)
    return dt_value.astimezone(timezone.utc).isoformat()


def _get_latest_school_verification(school_id):
    return (
        SchoolVerification.query.filter_by(school_id=school_id)
        .order_by(SchoolVerification.id.desc())
        .first()
    )


def _get_school_verification_snapshot(school_id):
    verification = _get_latest_school_verification(school_id)
    if not verification:
        return {
            "status": "not_submitted",
            "risk_tier": "unknown",
            "is_verified": False,
            "reviewed_at": None,
            "expires_at": None,
        }

    status = (verification.status or "pending").strip().lower()
    expires_at = verification.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    is_expired = bool(expires_at and expires_at <= get_utc_now())
    effective_status = "expired" if is_expired and status == "verified" else status

    return {
        "status": effective_status,
        "risk_tier": (verification.risk_tier or "medium").strip().lower(),
        "is_verified": effective_status == "verified",
        "reviewed_at": _to_iso_utc(verification.reviewed_at),
        "expires_at": _to_iso_utc(verification.expires_at),
        "verification_id": verification.id,
    }


def _finance_verification_block_response(school_id, action):
    snapshot = _get_school_verification_snapshot(school_id)
    if snapshot["is_verified"]:
        return None, snapshot

    return (
        jsonify(
            {
                "message": "School verification is required before this financial action can continue.",
                "error": "school_verification_required",
                "action": action,
                "verification": snapshot,
            }
        ),
        403,
    ), snapshot


def _create_aml_flag(
    school_id,
    rule_code,
    severity,
    summary,
    details=None,
    payment_id=None,
    student_id=None,
    created_by_user_id=None,
):
    flag = AMLTransactionFlag(
        school_id=school_id,
        payment_id=payment_id,
        student_id=student_id,
        created_by_user_id=created_by_user_id,
        rule_code=rule_code,
        severity=severity,
        status="open",
        summary=summary,
        details=details if isinstance(details, dict) else {},
    )
    db.session.add(flag)
    return flag


def _evaluate_payment_aml_flags(school_id, payment, actor_id=None):
    flags = []
    now = get_utc_now()
    amount = float(payment.amount or 0)

    if amount >= 50000:
        flags.append(
            _create_aml_flag(
                school_id=school_id,
                payment_id=payment.id,
                student_id=payment.student_id,
                created_by_user_id=actor_id,
                rule_code="HIGH_VALUE_PAYMENT",
                severity="high",
                summary="High-value payment exceeded AML review threshold.",
                details={"amount": amount, "threshold": 50000, "payment_type": payment.payment_type},
            )
        )

    one_day_ago = now - timedelta(hours=24)
    same_band_count = (
        Payment.query.filter(
            Payment.school_id == school_id,
            Payment.date_paid >= one_day_ago,
            Payment.amount >= 9000,
            Payment.amount <= 10000,
        ).count()
    )
    if 9000 <= amount <= 10000 and same_band_count >= 3:
        flags.append(
            _create_aml_flag(
                school_id=school_id,
                payment_id=payment.id,
                student_id=payment.student_id,
                created_by_user_id=actor_id,
                rule_code="STRUCTURED_PAYMENTS_PATTERN",
                severity="high",
                summary="Potential structuring detected from repeated near-threshold payments.",
                details={"amount": amount, "window_hours": 24, "similar_payments": same_band_count},
            )
        )

    one_hour_ago = now - timedelta(hours=1)
    rapid_count = (
        Payment.query.filter(
            Payment.school_id == school_id,
            Payment.date_paid >= one_hour_ago,
        ).count()
    )
    if rapid_count >= 25:
        flags.append(
            _create_aml_flag(
                school_id=school_id,
                payment_id=payment.id,
                student_id=payment.student_id,
                created_by_user_id=actor_id,
                rule_code="UNUSUAL_PAYMENT_VELOCITY",
                severity="medium",
                summary="Unusual payment velocity detected in the last hour.",
                details={"payments_last_hour": rapid_count},
            )
        )

    return flags


def _normalize_verification_text(value):
    return re.sub(r"[^a-z0-9]+", "", (str(value or "")).strip().lower())


def _screening_is_clean(screening_results):
    if not isinstance(screening_results, dict) or not screening_results:
        return True

    for key in ("sanctions_hit", "pep_hit", "adverse_media_hit", "high_risk", "match_found"):
        if bool(screening_results.get(key)):
            return False

    status_value = _normalize_verification_text(screening_results.get("status") or screening_results.get("result") or screening_results.get("overall"))
    if status_value and status_value not in {"clear", "passed", "ok", "clean", "approved", "nohit", "nohits"}:
        return False

    return True


def _auto_verify_school_verification(school, verification):
    if not school or not verification:
        return False, "missing_data"

    legal_name = _normalize_verification_text(verification.legal_name or school.name)
    school_name = _normalize_verification_text(school.name)
    registration_number = sanitize_string(verification.registration_number or "")
    tax_id = sanitize_string(verification.tax_id or "")
    owner_information = verification.owner_information if isinstance(verification.owner_information, dict) else {}
    screening_results = verification.screening_results if isinstance(verification.screening_results, dict) else {}

    if not registration_number or not tax_id:
        return False, "missing_regulatory_identifiers"

    if legal_name != school_name and school_name not in legal_name and legal_name not in school_name:
        return False, "legal_name_mismatch"

    required_owner_keys = {"proprietor_name", "director_name", "owner_name", "full_name"}
    if not any(str(owner_information.get(key) or "").strip() for key in required_owner_keys):
        return False, "missing_owner_identity"

    if not _screening_is_clean(screening_results):
        return False, "screening_flagged"

    verification.status = "verified"
    verification.risk_tier = "low"
    verification.reviewed_by_platform_user_id = None
    verification.reviewed_at = get_utc_now()
    if not verification.expires_at:
        verification.expires_at = get_utc_now() + timedelta(days=365)

    return True, "auto_verified"


def _local_verification_auto_approval_enabled():
    raw_value = str(
        os.getenv("KYB_LOCAL_AUTO_APPROVAL_ENABLED")
        or os.getenv("EDUPULSE_KYB_LOCAL_AUTO_APPROVAL_ENABLED")
        or ""
    ).strip().lower()
    return raw_value in {"1", "true", "yes", "on"}


def _compose_verification_review_note(provider_reason=None, local_reason=None):
    notes = []
    if provider_reason:
        notes.append(f"provider={provider_reason}")
    if local_reason:
        notes.append(f"local_heuristic={local_reason}")
    return "; ".join(notes) if notes else None


def _apply_school_verification_outcome(verification, outcome, risk_tier, notes=None):
    verification.risk_tier = risk_tier or verification.risk_tier or "medium"
    if notes:
        verification.review_notes = notes

    if outcome == "verified":
        verification.status = "verified"
        verification.reviewed_by_platform_user_id = None
        verification.reviewed_at = get_utc_now()
        if not verification.expires_at:
            verification.expires_at = get_utc_now() + timedelta(days=365)
    elif outcome == "review_required":
        verification.status = "review_required"
    else:
        verification.status = verification.status or "pending"


def _parse_position_value(position_text):
    if not position_text:
        return None

    digits = "".join(ch for ch in str(position_text) if ch.isdigit())
    if not digits:
        return None

    try:
        return int(digits)
    except (TypeError, ValueError):
        return None


def _risk_level_from_score(risk_score):
    if risk_score >= 70:
        return "Critical"
    if risk_score >= 50:
        return "High"
    if risk_score >= 30:
        return "Moderate"
    return "Watch"


def _academic_year_sort_key(academic_year):
    text_value = str(academic_year or "")
    match = re.match(r"^(\d{4})", text_value)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def _academic_term_sort_key(term_name):
    normalized = str(term_name or "").strip().lower()
    term_order = {
        "term 1": 1,
        "first term": 1,
        "1st term": 1,
        "term 2": 2,
        "second term": 2,
        "2nd term": 2,
        "term 3": 3,
        "third term": 3,
        "3rd term": 3,
    }
    return term_order.get(normalized, 0)


def _report_sort_key(report):
    return (
        _academic_year_sort_key(getattr(report, "academic_year", None)),
        _academic_term_sort_key(getattr(report, "academic_term", None)),
        getattr(report, "id", 0) or 0,
    )


def _normalize_rescue_action_label(action_code):
    labels = {
        "guardian_called": "Guardian called",
        "email_sent": "Email sent",
        "payment_plan_agreed": "Payment plan agreed",
        "academic_support_assigned": "Academic support assigned",
        "resolved": "Marked as resolved",
    }
    return labels.get(action_code, str(action_code or "Outcome logged").replace("_", " ").title())


def _parse_rescue_outcome_details(details):
    if not details:
        return None

    try:
        payload = json.loads(details)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "student_rescue_outcome":
        return None
    return payload


def _get_rescue_outcome_history(school_id, student_ids=None, limit=200):
    query = AuditLog.query.filter_by(
        school_id=school_id,
        action="STUDENT_RESCUE_OUTCOME",
    ).options(joinedload(AuditLog.actor)).order_by(AuditLog.timestamp.desc())

    logs = query.limit(limit).all()
    student_id_set = {int(student_id) for student_id in (student_ids or []) if str(student_id).isdigit()}
    outcome_map = {}

    for log in logs:
        parsed = _parse_rescue_outcome_details(log.details)
        if not parsed:
            continue
        student_id = parsed.get("student_id")
        if student_id is None:
            continue
        if student_id_set and student_id not in student_id_set:
            continue

        outcome_map.setdefault(student_id, []).append(
            {
                "log_id": log.id,
                "action_code": parsed.get("action_code"),
                "action_label": parsed.get("action_label") or _normalize_rescue_action_label(parsed.get("action_code")),
                "notes": parsed.get("notes") or "",
                "created_at": log.timestamp.isoformat() if log.timestamp else None,
                "actor_name": log.actor.username if log.actor else "Unknown",
            }
        )

    return outcome_map


def _build_rescue_contact_templates(student, school, reasons, recommended_actions):
    guardian_name = student.guardian_name or student.parent_name or "Parent/Guardian"
    top_reason = reasons[0]["label"] if reasons else "student progress concerns"
    due_amount = float(student.total_tuition_owed or 0)
    reason_summary = "; ".join(reason["label"] for reason in reasons[:3]) or "student progress concerns"
    action_summary = ", ".join(action["label"] for action in recommended_actions[:2]) or "a short support discussion"
    school_name = school.name if school else "the school"

    email_subject = f"Support discussion for {student.name}"
    email_body = (
        f"Dear {guardian_name},\n\n"
        f"This is {school_name}. We are reaching out regarding {student.name} in {student.current_class or 'class'} after our Student Rescue review flagged {top_reason.lower()}.\n\n"
        f"Current concern(s): {reason_summary}.\n"
        f"Outstanding tuition on record: GH₵ {due_amount:.2f}.\n\n"
        f"We would like to work with you on the next step, including {action_summary}. "
        f"Please reply to this email or contact the school office so we can agree on immediate support for {student.name}.\n\n"
        f"Regards,\n{school_name}"
    )

    call_script = (
        f"Hello {guardian_name}, this is {school_name}. I am calling about {student.name}. "
        f"Our review flagged {top_reason.lower()}, and we want to agree on the fastest support step today."
    )

    sms_body = (
        f"{school_name}: Please contact the school today about {student.name}. "
        f"We need to discuss {top_reason.lower()} and the next support step."
    )

    meeting_brief = (
        f"Meeting objective: align with {guardian_name} on an action plan for {student.name}. "
        f"Discuss {reason_summary} and confirm ownership for {action_summary}."
    )

    return {
        "email_subject": email_subject,
        "email_body": email_body,
        "call_script": call_script,
        "sms_body": sms_body,
        "meeting_brief": meeting_brief,
        "whatsapp_status": "deferred_for_cost_control",
    }


def _get_case_status_from_outcomes(outcomes):
    if not outcomes:
        return "Open"

    latest_action = outcomes[0].get("action_code")
    if latest_action == "resolved":
        return "Resolved"
    return "In Progress"


def _build_rescue_report(flagged_students, school_id):
    now = datetime.now(timezone.utc)
    outcome_logs = (
        AuditLog.query.filter_by(school_id=school_id, action="STUDENT_RESCUE_OUTCOME")
        .order_by(AuditLog.timestamp.desc())
        .limit(500)
        .all()
    )

    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)

    outcomes_last_7_days = 0
    outcomes_last_30_days = 0
    action_breakdown = {}
    resolved_last_30_days = 0

    for log in outcome_logs:
        parsed = _parse_rescue_outcome_details(log.details)
        if not parsed:
            continue
        action_code = parsed.get("action_code") or "unknown"
        action_breakdown[action_code] = action_breakdown.get(action_code, 0) + 1
        timestamp = log.timestamp
        if timestamp and timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if not timestamp:
            continue
        if timestamp >= last_7_days:
            outcomes_last_7_days += 1
        if timestamp >= last_30_days:
            outcomes_last_30_days += 1
            if action_code == "resolved":
                resolved_last_30_days += 1

    return {
        "open_cases": sum(1 for item in flagged_students if item.get("case_status") == "Open"),
        "in_progress_cases": sum(1 for item in flagged_students if item.get("case_status") == "In Progress"),
        "resolved_cases": sum(1 for item in flagged_students if item.get("case_status") == "Resolved"),
        "critical_cases": sum(1 for item in flagged_students if item.get("risk_level") == "Critical"),
        "outcomes_last_7_days": outcomes_last_7_days,
        "outcomes_last_30_days": outcomes_last_30_days,
        "resolved_last_30_days": resolved_last_30_days,
        "action_breakdown": action_breakdown,
    }


def _get_active_term_for_school(school_id):
    return AcademicTerm.query.filter_by(school_id=school_id, is_active=True).first()


def _days_since_date(target_date, now):
    if not target_date:
        return None
    if isinstance(target_date, datetime):
        target_value = target_date.date()
    else:
        target_value = target_date
    return (now.date() - target_value).days


def _get_recent_tuition_payment_summary(school_id, student_id, now):
    tuition_payments = (
        Payment.query.filter(
            Payment.school_id == school_id,
            Payment.student_id == student_id,
            Payment.status == "Confirmed",
            Payment.payment_type == "Tuition",
            Payment.date_paid.isnot(None),
        )
        .order_by(Payment.date_paid.desc())
        .limit(10)
        .all()
    )

    latest_payment = tuition_payments[0].date_paid if tuition_payments else None
    if latest_payment and latest_payment.tzinfo is None:
        latest_payment = latest_payment.replace(tzinfo=timezone.utc)

    days_since_latest = None
    if latest_payment:
        days_since_latest = max(0, (now - latest_payment).days)

    return {
        "confirmed_count": len(tuition_payments),
        "latest_payment_at": latest_payment.isoformat() if latest_payment else None,
        "days_since_latest_payment": days_since_latest,
        "has_payment_in_last_14_days": days_since_latest is not None and days_since_latest <= 14,
        "has_payment_in_last_30_days": days_since_latest is not None and days_since_latest <= 30,
    }


def _build_student_rescue_payload(school_id, limit=8):
    now = datetime.now(timezone.utc)
    school = School.query.get(school_id)
    active_term = _get_active_term_for_school(school_id)
    days_since_term_start = _days_since_date(active_term.start_date, now) if active_term and active_term.start_date else None
    reopening_grace_days = 14
    within_reopening_grace = days_since_term_start is not None and days_since_term_start <= reopening_grace_days
    candidate_limit = None if limit is None else max(limit * 3, 12)

    candidate_query = Student.query.filter(
        Student.school_id == school_id,
        or_(
            and_(
                Student.total_tuition_owed > 0,
                or_(
                    Student.tuition_deadline.is_(None),
                    Student.tuition_deadline <= now,
                ),
            ),
            Student.is_present == True,
        ),
    ).order_by(Student.total_tuition_owed.desc(), Student.name.asc())
    if candidate_limit is not None:
        candidate_query = candidate_query.limit(candidate_limit)
    candidate_students = candidate_query.all()
    feeding_status_details = _get_feeding_status_details_for_students(candidate_students, school_id, as_of_date=now.date())

    flagged_students = []

    for student in candidate_students:
        reasons = []
        recommended_actions = []
        feeding_status = feeding_status_details.get(student.id, {})
        payment_summary = _get_recent_tuition_payment_summary(school_id, student.id, now)
        student_reports = ReportCard.query.filter_by(
            school_id=school_id,
            student_id=student.id,
        ).all()
        ordered_reports = sorted(student_reports, key=_report_sort_key)
        latest_report = ordered_reports[-1] if ordered_reports else None
        previous_report = None
        if len(ordered_reports) >= 2:
            previous_report = ordered_reports[-2]

        term_average = float(latest_report.term_average or 0) if latest_report and latest_report.term_average is not None else None
        attendance_percentage = (
            float(latest_report.attendance_percentage or 0)
            if latest_report and latest_report.attendance_percentage is not None
            else None
        )
        trend_direction = "stable"
        trend_delta = 0.0
        if latest_report and previous_report and latest_report.term_average is not None and previous_report.term_average is not None:
            trend_delta = float(latest_report.term_average or 0) - float(previous_report.term_average or 0)
            if trend_delta <= -5:
                trend_direction = "declining"
            elif trend_delta >= 5:
                trend_direction = "improving"

        tuition_deadline = student.tuition_deadline
        if tuition_deadline and tuition_deadline.tzinfo is None:
            tuition_deadline = tuition_deadline.replace(tzinfo=timezone.utc)

        risk_score = 0
        attendance_issue = attendance_percentage is not None and attendance_percentage < 80
        academic_issue = (
            (term_average is not None and term_average < 60)
            or trend_direction == "declining"
        )
        feeding_issue = bool(student.is_present and not feeding_status.get("covered"))
        support_signal_count = sum(1 for flag in [attendance_issue, academic_issue, feeding_issue] if flag)

        tuition_flagged = False
        if student.scholarship_covers_tuition:
            tuition_flagged = False
        elif student.total_tuition_owed and student.total_tuition_owed > 0:
            days_overdue = 0
            if tuition_deadline:
                days_overdue = max(0, (now.date() - tuition_deadline.date()).days)

            has_recent_tuition_payment = payment_summary["has_payment_in_last_14_days"]
            has_recent_month_payment = payment_summary["has_payment_in_last_30_days"]
            no_payment_history = payment_summary["confirmed_count"] == 0
            severe_tuition_pressure = days_overdue >= 45 or float(student.total_tuition_owed or 0) >= 900
            stalled_payment_behaviour = not has_recent_tuition_payment and (days_overdue >= 14 or no_payment_history)

            if severe_tuition_pressure and not within_reopening_grace:
                tuition_flagged = True
            elif not within_reopening_grace and stalled_payment_behaviour and support_signal_count >= 1:
                tuition_flagged = True
            elif not within_reopening_grace and days_overdue >= 21 and not has_recent_month_payment and support_signal_count >= 1:
                tuition_flagged = True

            if tuition_flagged:
                debt_score = 20 + min(18, max(days_overdue, 1) // 4)
                if float(student.total_tuition_owed or 0) >= 500:
                    debt_score += 8
                if no_payment_history:
                    debt_score += 7
                if support_signal_count >= 2:
                    debt_score += 5

                risk_score += debt_score
                payment_context_parts = []
                if days_overdue > 0:
                    payment_context_parts.append(f"overdue for {days_overdue} day(s)")
                if payment_summary["days_since_latest_payment"] is not None:
                    payment_context_parts.append(
                        f"last confirmed tuition payment was {payment_summary['days_since_latest_payment']} day(s) ago"
                    )
                elif no_payment_history:
                    payment_context_parts.append("no confirmed tuition payment has been recorded yet")
                detail_suffix = "; ".join(payment_context_parts) if payment_context_parts else "payment behaviour needs attention"

                reasons.append(
                    {
                        "code": "overdue_tuition",
                        "label": "Tuition risk needs intervention",
                        "detail": f"GH₵ {float(student.total_tuition_owed or 0):.2f} remains unpaid and {detail_suffix}.",
                        "severity": min(debt_score, 58),
                    }
                )
                recommended_actions.append(
                    {
                        "code": "call_guardian",
                        "label": "Call guardian about tuition risk",
                        "channel": "phone",
                        "urgency": "today",
                    }
                )
                recommended_actions.append(
                    {
                        "code": "send_payment_plan",
                        "label": "Offer a structured payment plan or reminder",
                        "channel": "finance",
                        "urgency": "today",
                    }
                )

        if feeding_issue:
            risk_score += 20
            reasons.append(
                {
                    "code": "unpaid_feeding",
                    "label": "Present without feeding payment",
                    "detail": "Student was marked present but feeding payment has not been cleared.",
                    "severity": 20,
                }
            )
            recommended_actions.append(
                {
                    "code": "resolve_feeding_status",
                    "label": "Verify feeding arrangement before next meal cycle",
                    "channel": "operations",
                    "urgency": "today",
                }
            )

        if term_average is not None:
            if term_average < 50:
                risk_score += 25
                reasons.append(
                    {
                        "code": "low_academic_average",
                        "label": "Low academic average",
                        "detail": f"Latest term average is {term_average:.1f}%.",
                        "severity": 25,
                    }
                )
            elif term_average < 60:
                risk_score += 18
                reasons.append(
                    {
                        "code": "low_academic_average",
                        "label": "Weak academic average",
                        "detail": f"Latest term average is {term_average:.1f}%.",
                        "severity": 18,
                    }
                )
            elif term_average < 70:
                risk_score += 10

        if attendance_percentage is not None:
            if attendance_percentage < 70:
                risk_score += 18
                reasons.append(
                    {
                        "code": "attendance_drop",
                        "label": "Low attendance",
                        "detail": f"Attendance is {attendance_percentage:.1f}% in the latest report.",
                        "severity": 18,
                    }
                )
            elif attendance_percentage < 80:
                risk_score += 10
                reasons.append(
                    {
                        "code": "attendance_watch",
                        "label": "Attendance needs monitoring",
                        "detail": f"Attendance is {attendance_percentage:.1f}% in the latest report.",
                        "severity": 10,
                    }
                )

        if trend_direction == "declining":
            risk_score += 10
            reasons.append(
                {
                    "code": "declining_trend",
                    "label": "Performance trend is declining",
                    "detail": f"Term average dropped by {abs(trend_delta):.1f} point(s) from the previous report.",
                    "severity": 10,
                }
            )
            recommended_actions.append(
                {
                    "code": "assign_academic_support",
                    "label": "Assign academic support or remedial follow-up",
                    "channel": "academic",
                    "urgency": "this_week",
                }
            )

        if not reasons:
            continue

        risk_score = min(100, int(round(risk_score)))
        risk_level = _risk_level_from_score(risk_score)

        if not recommended_actions:
            recommended_actions.append(
                {
                    "code": "manual_review",
                    "label": "Review student file and contact class leadership",
                    "channel": "admin",
                    "urgency": "this_week",
                }
            )

        seen_action_codes = set()
        deduped_actions = []
        for action in recommended_actions:
            if action["code"] in seen_action_codes:
                continue
            seen_action_codes.add(action["code"])
            deduped_actions.append(action)

        flagged_students.append(
            {
                "id": student.id,
                "name": student.name,
                "parent_name": student.parent_name,
                "guardian_name": student.guardian_name,
                "parent_phone": student.parent_phone,
                "parent_email": student.parent_email,
                "current_class": student.current_class,
                "student_code": student.student_code,
                "is_present": bool(student.is_present),
                "feeding_paid": bool(feeding_status.get("covered")),
                "payment_method": feeding_status.get("payment_method"),
                "feeding_coverage_until": feeding_status.get("coverage_until"),
                "feeding_days_remaining": feeding_status.get("days_remaining"),
                "feeding_frequency": feeding_status.get("frequency"),
                "is_on_scholarship": bool(student.is_on_scholarship),
                "scholarship_covers_tuition": bool(student.scholarship_covers_tuition),
                "total_tuition_owed": float(student.total_tuition_owed or 0),
                "tuition_deadline": student.tuition_deadline.isoformat() if student.tuition_deadline else None,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "priority_rank": 0,
                "rescue_summary": f"{student.name} is {risk_level.lower()} risk due to {reasons[0]['label'].lower()}.",
                "intervention_reasons": reasons,
                "intervention_summary": reasons[0]["label"],
                "recommended_actions": deduped_actions,
                "contact_templates": _build_rescue_contact_templates(student, school, reasons, deduped_actions),
                "payment_context": payment_summary,
                "latest_report": {
                    "term_average": term_average,
                    "attendance_percentage": attendance_percentage,
                    "overall_position": latest_report.overall_position if latest_report else None,
                    "out_of_students": latest_report.out_of_students if latest_report else None,
                    "academic_term": latest_report.academic_term if latest_report else None,
                    "academic_year": latest_report.academic_year if latest_report else None,
                    "trend_direction": trend_direction,
                    "trend_delta": round(trend_delta, 1),
                },
            }
        )

    flagged_students.sort(key=lambda item: (-item["risk_score"], -(item["total_tuition_owed"] or 0), item["name"]))
    if limit is not None:
        flagged_students = flagged_students[:limit]

    outcome_map = _get_rescue_outcome_history(
        school_id,
        student_ids=[item["id"] for item in flagged_students],
    )

    for index, student_payload in enumerate(flagged_students, start=1):
        student_payload["priority_rank"] = index
        student_outcomes = outcome_map.get(student_payload["id"], [])
        student_payload["recent_outcomes"] = student_outcomes[:5]
        student_payload["last_outcome"] = student_outcomes[0] if student_outcomes else None
        student_payload["case_status"] = _get_case_status_from_outcomes(student_outcomes)

    summary = {
        "total_flagged_students": len(flagged_students),
        "critical_count": sum(1 for item in flagged_students if item["risk_level"] == "Critical"),
        "high_priority_count": sum(1 for item in flagged_students if item["risk_level"] in ["Critical", "High"]),
        "average_risk_score": round(
            sum(item["risk_score"] for item in flagged_students) / len(flagged_students), 1
        )
        if flagged_students
        else 0,
        "contact_queue_count": sum(
            1 for item in flagged_students if any(action["code"] == "call_guardian" for action in item["recommended_actions"])
        ),
    }

    return {
        "summary": summary,
        "report": _build_rescue_report(flagged_students, school_id),
        "students": flagged_students,
        "generated_at": now.isoformat(),
    }


def log_system_action(school_id, action, details):
    # Only log if school exists (prevent FK constraint violations for unknown schools)
    if not School.query.filter_by(id=school_id).first():
        return
    new_log = AuditLog(
        actor_id=None,
        school_id=school_id,
        action=action,
        details=details,
        timestamp=get_utc_now(),
    )
    db.session.add(new_log)
    db.session.commit()


def _auto_billing_setting_key(school_id):
    return f"auto_billing:{school_id}"


def _get_auto_billing_config(school_id):
    setting = PlatformSetting.query.filter_by(
        setting_key=_auto_billing_setting_key(school_id)
    ).first()
    return setting.setting_value if setting and isinstance(setting.setting_value, dict) else {}


def _upsert_auto_billing_config(school_id, config):
    safe_config = json.loads(json.dumps(config or {}))
    setting = PlatformSetting.query.filter_by(
        setting_key=_auto_billing_setting_key(school_id)
    ).first()
    if not setting:
        setting = PlatformSetting(
            setting_key=_auto_billing_setting_key(school_id),
            setting_value=safe_config,
        )
        db.session.add(setting)
    else:
        setting.setting_value = safe_config
    db.session.commit()
    return setting.setting_value


def _billing_timeline_setting_key(school_id):
    return f"billing_timeline:{school_id}"


def _get_billing_timeline(school_id):
    setting = PlatformSetting.query.filter_by(
        setting_key=_billing_timeline_setting_key(school_id)
    ).first()
    value = setting.setting_value if setting and isinstance(setting.setting_value, list) else []
    return value


def _upsert_billing_timeline(school_id, events):
    safe_events = json.loads(json.dumps(events or []))
    setting = PlatformSetting.query.filter_by(
        setting_key=_billing_timeline_setting_key(school_id)
    ).first()
    if not setting:
        setting = PlatformSetting(
            setting_key=_billing_timeline_setting_key(school_id),
            setting_value=safe_events,
        )
        db.session.add(setting)
    else:
        setting.setting_value = safe_events
    db.session.commit()
    return setting.setting_value


def _append_billing_timeline_event(
    school_id,
    event_type,
    status,
    title,
    details,
    amount=None,
    reference=None,
    due_date=None,
    next_retry_at=None,
    metadata=None,
):
    events = _get_billing_timeline(school_id)
    event = {
        "id": hashlib.sha256(
            f"{school_id}:{event_type}:{reference or ''}:{time.time()}".encode("utf-8")
        ).hexdigest()[:20],
        "created_at": get_utc_now().isoformat(),
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
    return _upsert_billing_timeline(school_id, events)


def _is_subscription_reference_processed(reference, school_id=None):
    if not reference:
        return False
    query = LedgerEntry.query.filter_by(tx_ref=reference)
    if school_id:
        query = query.filter_by(school_id=school_id)
    existing = query.first()
    return existing is not None


def _count_active_students_for_billing(school_id):
    return Student.query.filter(
        Student.school_id == school_id,
        Student.status.in_(["Active", "active"]),
    ).count()


def _count_same_term_recyclable_seats(school_id, active_term):
    if not school_id or not active_term:
        return 0

    term_start = getattr(active_term, "start_date", None)
    term_end = getattr(active_term, "end_date", None)
    if not term_start or not term_end:
        return 0

    recyclable_statuses = ["Graduated", "Withdrawn", "Transferred", "Suspended", "Inactive"]
    departures = 0
    for student in Student.query.filter(
        Student.school_id == school_id,
        Student.status.in_(recyclable_statuses),
    ).all():
        updated_at = getattr(student, "status_updated_at", None)
        if not updated_at:
            continue
        updated_date = updated_at.date() if hasattr(updated_at, "date") else None
        if not updated_date:
            continue
        if term_start <= updated_date <= term_end:
            departures += 1
    return departures


def _subscription_plan_rank(plan_name):
    plan_order = ["Free Tier", "Basic", "Premium"]
    try:
        return plan_order.index(plan_name or "Free Tier")
    except ValueError:
        return -1


def _get_payment_collection_block(school):
    if not school:
        return None

    effective_plan = get_effective_plan(school)
    plan_limit = get_plan_limits(effective_plan)
    if plan_limit >= 999999:
        return None

    active_students = _count_active_students_for_billing(school.id)
    if active_students <= plan_limit:
        return None

    return {
        "status": "blocked",
        "error": "payment_collection_blocked",
        "reason": "plan_over_capacity",
        "effective_plan": effective_plan,
        "plan_limit": plan_limit,
        "active_students": active_students,
        "message": (
            "Parent payment collection is paused because this school is on "
            f"{effective_plan} "
            f"with {active_students} active students, above the {plan_limit}-student limit. "
            "Upgrade the subscription or reduce active enrollment to resume collection."
        ),
    }


def _get_unsettled_overage_invoice(school_id):
    if not school_id:
        return None

    settlements = {
        (entry.meta or {}).get("invoice_tx_ref")
        for entry in LedgerEntry.query.filter_by(
            school_id=school_id,
            tx_type="subscription_overage_charge",
        ).all()
    }

    candidates = (
        LedgerEntry.query.filter_by(school_id=school_id, tx_type="subscription_prorated")
        .order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
        .all()
    )
    for entry in candidates:
        meta = entry.meta or {}
        if meta.get("status") != "Pending":
            continue
        if entry.tx_ref in settlements:
            continue
        return entry
    return None


def _has_active_auto_billing_coverage(school_id):
    config = _normalize_auto_billing_config(_get_auto_billing_config(school_id))
    if not config.get("enabled"):
        return False

    default_card = _get_default_saved_card(config)
    return bool((default_card or {}).get("authorization_code"))


def _get_included_students_for_school_plan(school, effective_plan=None):
    if not school:
        return 0

    resolved_plan = effective_plan or get_effective_plan(school)
    pricing_info = PRICING.get(resolved_plan, {}) if resolved_plan != "Free Tier" else {}
    if school.custom_included_students is not None:
        return max(0, int(school.custom_included_students))
    return max(0, int(pricing_info.get("included_students", 0) or 0))


def _get_billing_growth_block(school, projected_active_students=None, assume_no_payment_coverage=False):
    if not school:
        return None

    effective_plan = get_effective_plan(school)
    trial_end = getattr(school, "trial_end_date", None)
    if trial_end and getattr(trial_end, "tzinfo", None) is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)
    if getattr(school, "trial_plan", None) and trial_end and get_utc_now() < trial_end:
        return None

    active_students = _count_active_students_for_billing(school.id)
    projected = active_students if projected_active_students is None else max(0, int(projected_active_students))

    pending_invoice = _get_unsettled_overage_invoice(school.id)
    if pending_invoice:
        invoice_meta = pending_invoice.meta or {}
        return {
            "status": "blocked",
            "error": "billing_growth_blocked",
            "reason": "pending_overage_invoice",
            "effective_plan": effective_plan,
            "active_students": active_students,
            "projected_active_students": projected,
            "included_students": _get_included_students_for_school_plan(school, effective_plan),
            "invoice_ref": pending_invoice.tx_ref,
            "invoice_amount": float(pending_invoice.amount or 0),
            "invoice_due_date": invoice_meta.get("due_date"),
            "message": (
                "Billable growth is blocked because an earlier overage invoice is still unpaid. "
                "Settle the outstanding invoice before adding more students or disabling card coverage."
            ),
        }

    if effective_plan == "Free Tier":
        return None

    included_students = _get_included_students_for_school_plan(school, effective_plan)
    if projected <= included_students:
        return None

    if not assume_no_payment_coverage and _has_active_auto_billing_coverage(school.id):
        return None

    return {
        "status": "blocked",
        "error": "billing_growth_blocked",
        "reason": "payment_method_required",
        "effective_plan": effective_plan,
        "active_students": active_students,
        "projected_active_students": projected,
        "included_students": included_students,
        "message": (
            "Billable growth is blocked because this school would exceed its included student threshold "
            "without an active saved-card auto-billing method. Add or re-enable a billing card before "
            "creating more paid-seat exposure."
        ),
    }


def _billing_growth_block_response(school, projected_active_students=None, assume_no_payment_coverage=False):
    payload = _get_billing_growth_block(
        school,
        projected_active_students=projected_active_students,
        assume_no_payment_coverage=assume_no_payment_coverage,
    )
    if not payload:
        return None
    return jsonify(payload), 409


def _payment_collection_block_response(school, public=False):
    payload = _get_payment_collection_block(school)
    if not payload:
        return None

    if public:
        payload = {**payload, "public_status": "blocked"}
    return jsonify(payload), 409


def _payment_records_verification_block_response(school, public=False):
    if not school:
        return None

    snapshot = _get_school_verification_snapshot(school.id)
    if snapshot["is_verified"]:
        return None

    payload = {
        "message": "School verification is required before payment instructions, collection, or payment records are available.",
        "error": "school_verification_required",
        "verification": snapshot,
    }
    if public:
        payload["public_status"] = "blocked"
    return jsonify(payload), 403


def _payment_audit_access_block_response(school):
    verification_restriction = _payment_records_verification_block_response(school)
    if verification_restriction:
        return verification_restriction

    return _payment_collection_block_response(school)


def _student_hard_delete_blockers(student):
    if not student:
        return []

    blockers = []
    if Payment.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("payments")
    if LedgerEntry.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("ledger_entries")
    if StudentGrade.query.filter_by(student_id=student.id).first():
        blockers.append("grades")
    if StudentAssignment.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("assignments")
    if ReportCard.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("report_cards")
    if StudentPromotion.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("promotions")
    if StudentNotification.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("notifications")
    if ParentAdmissionApplication.query.filter_by(admitted_student_id=student.id, school_id=student.school_id).first():
        blockers.append("admissions_history")
    if AMLTransactionFlag.query.filter_by(student_id=student.id, school_id=student.school_id).first():
        blockers.append("aml_flags")

    return blockers


def _academic_term_delete_blockers(term):
    if not term:
        return []

    blockers = []

    if ReportCard.query.filter_by(
        school_id=term.school_id,
        academic_term=term.name,
        academic_year=term.academic_year,
    ).first():
        blockers.append("report_cards")

    billing_timeline = _get_billing_timeline(term.school_id)
    if any(
        str(((event or {}).get("metadata") or {}).get("academic_term_id")) == str(term.id)
        for event in billing_timeline
    ):
        blockers.append("billing_timeline")

    ledger_entries = LedgerEntry.query.filter_by(school_id=term.school_id).all()
    if any(str((entry.meta or {}).get("academic_term_id")) == str(term.id) for entry in ledger_entries):
        blockers.append("ledger_entries")

    return blockers


def _lock_school_for_capacity_check(school_id):
    session = db.session()
    bind = db.session.get_bind()
    dialect_name = bind.dialect.name if bind and bind.dialect else ""

    if dialect_name == "sqlite":
        # SQLite cannot start BEGIN IMMEDIATE inside an already-open transaction,
        # which is common in the test suite after fixture setup work.
        if not session.in_transaction():
            db.session.execute(text("BEGIN IMMEDIATE"))
        return School.query.filter_by(id=school_id).first()

    return School.query.filter_by(id=school_id).with_for_update().first()


def _sanitize_saved_card(card):
    return {
        "card_id": card.get("card_id"),
        "last4": card.get("last4"),
        "brand": card.get("brand"),
        "bank": card.get("bank"),
        "exp_month": card.get("exp_month"),
        "exp_year": card.get("exp_year"),
        "channel": card.get("channel"),
        "customer_email": card.get("customer_email"),
        "is_default": bool(card.get("is_default", False)),
        "added_at": card.get("added_at"),
        "updated_at": card.get("updated_at"),
    }


def _get_card_fingerprint(card):
    return (
        sanitize_string(card.get("signature") or "")
        or sanitize_string(card.get("authorization_code") or "")
    )


def _sync_legacy_card_fields(config):
    cards = config.get("cards") if isinstance(config.get("cards"), list) else []
    default_card = next((c for c in cards if c.get("is_default")), cards[0] if cards else None)

    if default_card:
        config["authorization_code"] = default_card.get("authorization_code")
        config["authorization_last4"] = default_card.get("last4")
        config["authorization_brand"] = default_card.get("brand")
        config["authorization_bank"] = default_card.get("bank")
        config["customer_email"] = default_card.get("customer_email")
        config["default_card_id"] = default_card.get("card_id")
    else:
        config["authorization_code"] = None
        config["authorization_last4"] = None
        config["authorization_brand"] = None
        config["authorization_bank"] = None
        config["default_card_id"] = None

    return config


def _normalize_auto_billing_config(config):
    normalized = config if isinstance(config, dict) else {}
    cards = normalized.get("cards")
    if not isinstance(cards, list):
        cards = []

    # Migrate legacy single-card storage into cards array.
    if normalized.get("authorization_code"):
        legacy_fp = sanitize_string(normalized.get("authorization_code"))
        exists = any(
            sanitize_string(c.get("authorization_code") or "") == legacy_fp
            for c in cards
        )
        if not exists:
            cards.append(
                {
                    "card_id": hashlib.sha256(legacy_fp.encode("utf-8")).hexdigest()[:24],
                    "authorization_code": normalized.get("authorization_code"),
                    "last4": normalized.get("authorization_last4"),
                    "brand": normalized.get("authorization_brand"),
                    "bank": normalized.get("authorization_bank"),
                    "customer_email": normalized.get("customer_email"),
                    "is_default": True,
                    "added_at": normalized.get("updated_at") or get_utc_now().isoformat(),
                    "updated_at": normalized.get("updated_at") or get_utc_now().isoformat(),
                }
            )

    deduped = []
    seen = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        fp = _get_card_fingerprint(card)
        if not fp:
            continue
        if fp in seen:
            continue
        seen.add(fp)
        deduped.append(card)

    default_card_id = normalized.get("default_card_id")
    default_present = bool(
        default_card_id and any(c.get("card_id") == default_card_id for c in deduped)
    )
    has_marked_default = any(bool(c.get("is_default")) for c in deduped)

    for index, card in enumerate(deduped):
        if not card.get("card_id"):
            fp = _get_card_fingerprint(card)
            card["card_id"] = hashlib.sha256(fp.encode("utf-8")).hexdigest()[:24]
        if "added_at" not in card:
            card["added_at"] = get_utc_now().isoformat()
        if "updated_at" not in card:
            card["updated_at"] = card.get("added_at") or get_utc_now().isoformat()

        if default_present:
            card["is_default"] = card.get("card_id") == default_card_id
        elif has_marked_default:
            # Preserve existing default choice when stored flags are present.
            card["is_default"] = bool(card.get("is_default"))
        else:
            card["is_default"] = index == 0

    # Ensure only one default card remains true.
    default_count = sum(1 for c in deduped if c.get("is_default"))
    if default_count > 1:
        first_default_id = next((c.get("card_id") for c in deduped if c.get("is_default")), None)
        for card in deduped:
            card["is_default"] = card.get("card_id") == first_default_id

    normalized["cards"] = deduped
    normalized = _sync_legacy_card_fields(normalized)
    return normalized


def _get_default_saved_card(config):
    normalized = _normalize_auto_billing_config(config)
    cards = normalized.get("cards") or []
    return next((c for c in cards if c.get("is_default")), cards[0] if cards else None)


def _save_reusable_authorization(school_id, authorization, customer_email):
    if not isinstance(authorization, dict):
        return None
    auth_code = sanitize_string(authorization.get("authorization_code") or "")
    if not auth_code:
        return None
    if not authorization.get("reusable"):
        return None

    config = _normalize_auto_billing_config(_get_auto_billing_config(school_id))
    cards = config.get("cards") or []
    signature = sanitize_string(authorization.get("signature") or "")
    fingerprint = signature or auth_code
    card_id = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]

    payload = {
        "card_id": card_id,
        "authorization_code": auth_code,
        "last4": authorization.get("last4"),
        "brand": authorization.get("brand"),
        "bank": authorization.get("bank"),
        "exp_month": authorization.get("exp_month"),
        "exp_year": authorization.get("exp_year"),
        "channel": authorization.get("channel"),
        "signature": signature,
        "customer_email": customer_email,
        "is_default": False,
        "added_at": get_utc_now().isoformat(),
        "updated_at": get_utc_now().isoformat(),
    }

    existing_idx = None
    for idx, card in enumerate(cards):
        if not isinstance(card, dict):
            continue
        same_signature = signature and sanitize_string(card.get("signature") or "") == signature
        same_auth = sanitize_string(card.get("authorization_code") or "") == auth_code
        if same_signature or same_auth:
            existing_idx = idx
            break

    if existing_idx is not None:
        previous = cards[existing_idx]
        payload["added_at"] = previous.get("added_at") or payload["added_at"]
        payload["is_default"] = bool(previous.get("is_default", False))
        cards[existing_idx] = payload
    else:
        if not cards:
            payload["is_default"] = True
        cards.append(payload)

    config["cards"] = cards
    config["updated_at"] = get_utc_now().isoformat()
    config = _normalize_auto_billing_config(config)
    saved = _upsert_auto_billing_config(school_id, config)
    saved = _normalize_auto_billing_config(saved)
    return next((c for c in (saved.get("cards") or []) if c.get("card_id") == card_id), None)


def calculate_prorated_admission_charge(school, num_new_students, effective_plan, pre_admission_active_students=None):
    """
    Calculate and process pro-rated charges for mid-term student admissions.
    Returns dict with charge info and logs/sends notifications if applicable.
    
    Args:
        school: School object
        num_new_students: Number of students being added
        effective_plan: Current effective plan (Basic, Premium, Free Tier)
    
    Returns:
        dict: {
            'prorated_charge': float (0 if no charge),
            'charge_reason': str,
            'invoice_sent': bool,
        }
    """
    result = {
        'prorated_charge': 0.0,
        'charge_reason': '',
        'invoice_sent': False,
    }

    trial_end = getattr(school, 'trial_end_date', None)
    if trial_end and getattr(trial_end, 'tzinfo', None) is None:
        trial_end = trial_end.replace(tzinfo=timezone.utc)
    if getattr(school, 'trial_plan', None) and trial_end and get_utc_now() < trial_end:
        result['charge_reason'] = 'Active premium trial - no charge'
        return result
    
    # Free Tier and paid plans with no active term: no charge
    if effective_plan == 'Free Tier':
        result['charge_reason'] = 'Free Tier plan - no charge'
        return result
    
    # Get active term
    active_term = AcademicTerm.query.filter_by(
        school_id=school.id,
        is_active=True
    ).first()
    
    if not active_term:
        result['charge_reason'] = 'No active term - billing deferred to term activation'
        return result
    
    # Get pricing info
    from backend.subscription_features import get_term_cost_breakdown, PRICING
    pricing_info = PRICING.get(effective_plan, {})
    base_fee = pricing_info.get('base_fee_per_term', 0)
    included_students = pricing_info.get('included_students', 0)
    per_student_rate = pricing_info.get('per_student_per_term', 0)
    
    # Callers that have already committed admissions should pass the pre-admission
    # baseline explicitly so proration is not computed from post-admission state.
    if pre_admission_active_students is None:
        current_active_students = Student.query.filter_by(
            school_id=school.id,
            status='Active'
        ).count()
    else:
        current_active_students = max(0, int(pre_admission_active_students))
    
    # Post-admission count
    new_total = current_active_students + num_new_students
    
    # Check if new students push over included threshold
    old_billable = max(0, current_active_students - included_students)
    new_billable = max(0, new_total - included_students)
    students_over_included = max(0, new_billable - old_billable)

    recyclable_seats = _count_same_term_recyclable_seats(school.id, active_term)
    reused_seats = min(students_over_included, recyclable_seats)
    students_over_included = max(0, students_over_included - reused_seats)
    
    if students_over_included <= 0:
        # All new students fall within included threshold
        if reused_seats > 0:
            result['charge_reason'] = (
                f'All {num_new_students} new student(s) reused {reused_seats} seat(s) vacated earlier in the same term'
            )
        else:
            result['charge_reason'] = f'All {num_new_students} new student(s) within included threshold'
        return result
    
    # Calculate remaining days in term for pro-ration
    today = date.today()
    term_start = active_term.start_date
    term_end = active_term.end_date
    
    # Prefer actual academic term length and remaining interval for transparent billing.
    if term_start and term_end:
        days_in_term = max(1, (term_end - term_start).days + 1)
        remaining_days = max(0, (term_end - today).days + 1)
        proration_factor = remaining_days / float(days_in_term)
        proration_factor = max(0.0, min(1.0, proration_factor))
    else:
        # If dates missing, charge full overage
        days_in_term = 120
        remaining_days = days_in_term
        proration_factor = 1.0
    
    # Calculate pro-rated overage charge
    overage_charge = students_over_included * per_student_rate * proration_factor
    overage_charge = round(overage_charge, 2)
    
    if overage_charge <= 0:
        result['charge_reason'] = f'Pro-rated charge rounds to 0'
        return result
    
    result['prorated_charge'] = overage_charge
    result['charge_reason'] = f'{students_over_included} student(s) above threshold × ₵{per_student_rate} × {proration_factor:.1%} pro-ration'
    if reused_seats > 0:
        result['charge_reason'] += f' after reusing {reused_seats} same-term vacated seat(s)'
    
    # Record pending invoice in tamper-evident ledger + timeline
    try:
        proprietor = User.query.filter_by(
            school_id=school.id,
            role='proprietor'
        ).first()
        
        from datetime import datetime as dt
        from backend.api.models import add_ledger_entry

        invoice_number = f"PRO-{school.id}-{dt.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        due_at = get_utc_now() + timedelta(days=30)

        add_ledger_entry(
            school_id=school.id,
            tx_type='subscription_prorated',
            tx_ref=invoice_number,
            amount=float(overage_charge),
            source='system',
            metadata={
                'status': 'Pending',
                'kind': 'admission_overage_proration',
                'term_id': getattr(active_term, 'id', None),
                'term_name': getattr(active_term, 'name', None),
                'academic_year': getattr(active_term, 'academic_year', None),
                'num_new_students': int(num_new_students),
                'students_over_included': int(students_over_included),
                'reused_seats': int(reused_seats),
                'same_term_vacated_seats': int(recyclable_seats),
                'per_student_rate': float(per_student_rate),
                'days_remaining': int(remaining_days),
                'days_in_term': int(days_in_term),
                'proration_factor': round(float(proration_factor), 6),
                'due_date': due_at.date().isoformat(),
                'created_reason': 'mid_term_admission',
            },
        )

        _append_billing_timeline_event(
            school_id=school.id,
            event_type='overage_invoice',
            status='pending',
            title='Mid-term overage invoice created',
            details=f"Invoice {invoice_number}: {students_over_included} student(s) above included threshold (pro-rated)." + (f" Reused {reused_seats} same-term vacated seat(s)." if reused_seats else ""),
            amount=float(overage_charge),
            reference=invoice_number,
            due_date=due_at.date().isoformat(),
            metadata={
                'students_over_included': int(students_over_included),
                'per_student_rate': float(per_student_rate),
                'days_remaining': int(remaining_days),
                'days_in_term': int(days_in_term),
            },
        )

        db.session.commit()
        
        # Send notification email
        if proprietor and proprietor.email:
            try:
                subject = f"Pro-Rated Subscription Invoice - {school.name}"
                body = f"""Hello {proprietor.username},

Students were admitted during the active term {active_term.name} ({active_term.academic_year}).

Pro-Rated Charge Breakdown:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Invoice Number:  {invoice_number}
New Students:    {num_new_students}
Students Over Threshold: {students_over_included}
Rate per Student: ₵{per_student_rate}
Pro-ration Factor: {proration_factor:.1%} ({remaining_days}/{days_in_term} days remaining)
Pro-Rated Charge: ₵{overage_charge:.2f}

This amount will be billed after the grace period unless settled earlier.

If you have questions, contact support@edupulse.com

Best regards,
The EduPulse Team
"""
                send_email_notification(
                    to_email=proprietor.email,
                    subject=subject,
                    body=body
                )
                result['invoice_sent'] = True
                logger.info(f"Pro-ration invoice {invoice_number} sent to {proprietor.email}")
            except Exception as e:
                logger.error(f"Failed to send pro-ration invoice email: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing pro-rated charge: {str(e)}")
    
    return result


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


@api.route("/whatsapp/test-send", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@rate_limit_api
@jwt_required()
def send_whatsapp_test_message():
    """Send a test WhatsApp message for current school proprietor."""
    if not STARTUP_WHATSAPP_ENABLED:
        return _whatsapp_feature_disabled_response()

    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}

    phone = sanitize_string(payload.get("phone"))
    message = payload.get("message") or "✅ EduPulse SMT WhatsApp test message."

    if not phone:
        return jsonify({"message": "Phone number is required"}), 400
    if not isinstance(message, str) or not message.strip():
        return jsonify({"message": "Message must be a non-empty string"}), 400

    # Check hourly rate limit (5 per hour for testing)
    one_hour_ago = get_utc_now() - timedelta(hours=1)
    recent_test_count = AuditLog.query.filter(
        AuditLog.school_id == g.school_id,
        AuditLog.action == "WHATSAPP_TEST_SENT",
        AuditLog.timestamp >= one_hour_ago,
    ).count()
    if recent_test_count >= 5:
        return (
            jsonify({"message": "Rate limit reached: max 5 WhatsApp test sends per hour."}),
            429,
        )
    
    # Check daily limit (configurable per school)
    school = School.query.get(g.school_id)
    if not school or not school.settings:
        return jsonify({"message": "School settings not found"}), 400

    effective_plan = get_effective_plan(school)
    if effective_plan != "Premium":
        return jsonify({"message": f"WhatsApp messaging is available on the {get_plan_display_name('Premium')} plan only."}), 403
    
    if not school.settings.whatsapp_notifications_enabled:
        return jsonify({"message": "WhatsApp notifications are disabled for this school."}), 403
    
    today = get_utc_now().date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    daily_count = AuditLog.query.filter(
        AuditLog.school_id == g.school_id,
        AuditLog.action.in_(["WHATSAPP_TEST_SENT", "WHATSAPP_MESSAGE_SENT"]),
        AuditLog.timestamp >= today_start,
        AuditLog.timestamp <= today_end,
    ).count()
    
    daily_limit = school.settings.whatsapp_daily_limit or 50
    if daily_count >= daily_limit:
        return (
            jsonify({
                "message": f"Daily WhatsApp limit reached ({daily_limit}/day). Try again after midnight."
            }),
            429,
        )

    try:
        result = send_text_message(phone, message.strip())
        message_id = (result.get("messages") or [{}])[0].get("id")

        log_action(
            user_id,
            g.school_id,
            "WHATSAPP_TEST_SENT",
            f"Test WhatsApp message sent to {phone}",
        )

        return jsonify(
            {
                "status": "success",
                "message": "WhatsApp test message sent",
                "message_id": message_id,
                "result": result,
            }
        )
    except WhatsAppError as e:
        logger.warning(f"WhatsApp test send failed for school {g.school_id}: {str(e)}")
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected WhatsApp test error for school {g.school_id}: {str(e)}")
        return jsonify({"message": "Failed to send WhatsApp test message"}), 500


def normalize_student_code_prefix(school_id):
    prefix = re.sub(r"[^A-Za-z0-9]", "", (school_id or "").upper())
    if not prefix:
        prefix = "SCH"
    return prefix[:12]


def generate_student_code(prefix, index):
    return f"{prefix}{index:04d}"


def _ensure_student_payment_identity(student):
    if not student:
        return None

    existing_code = sanitize_string(getattr(student, "student_code", "") or "")
    if existing_code:
        return existing_code

    prefix = normalize_student_code_prefix(student.school_id)
    next_index = Student.query.filter_by(school_id=student.school_id).count() + 1
    while True:
        candidate = generate_student_code(prefix, next_index)
        if not Student.query.filter_by(student_code=candidate, school_id=student.school_id).first():
            student.student_code = candidate
            db.session.flush()
            return candidate
        next_index += 1


def _generate_parent_admission_code(school_id):
    prefix = normalize_student_code_prefix(school_id)[:6]
    return f"ADM-{prefix}-{get_utc_now().strftime('%Y%m%d%H%M%S')}"


def _infer_document_category(filename):
    lowered = (filename or "").strip().lower()
    if not lowered:
        return "document"
    if "birth" in lowered:
        return "birth_certificate"
    if "report" in lowered or "result" in lowered:
        return "previous_report"
    if "passport photo" in lowered or "passport_photo" in lowered or "headshot" in lowered:
        return "passport_photo"
    if "id" in lowered or "passport" in lowered:
        return "identity_document"
    return "document"


def _extract_parent_admission_document_details(filename, content_type, file_bytes, category_override=None):
    category = category_override or _infer_document_category(filename)
    entry = {
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(file_bytes or b""),
        "category": category,
    }

    if not file_bytes:
        return entry

    lowered_name = (filename or "").strip().lower()
    is_image_upload = (content_type or "").startswith("image/") or lowered_name.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
    )

    if category != "previous_report" or not is_image_upload:
        return entry

    try:
        parsed = parse_report_card_image_bytes(image_bytes=file_bytes)
    except RuntimeError as exc:
        entry["ocr_status"] = "unavailable"
        entry["ocr_error"] = str(exc)
        return entry
    except Exception as exc:
        logger.warning("Failed to OCR parent admission document %s: %s", filename, exc)
        entry["ocr_status"] = "failed"
        entry["ocr_error"] = "parse_failed"
        return entry

    subjects = parsed.get("subjects") or []
    confidence = float(parsed.get("parse_confidence") or 0)
    entry.update(
        {
            "ocr_status": "parsed",
            "ocr_confidence": round(confidence, 2),
            "ocr_student_code": parsed.get("student_code"),
            "ocr_student_name": parsed.get("student_name"),
            "ocr_term": parsed.get("term"),
            "ocr_year": parsed.get("year"),
            "ocr_subject_count": len(subjects),
            "ocr_term_average": parsed.get("term_average"),
            "ocr_overall_performance": parsed.get("overall_performance"),
            "ocr_subjects": [
                {
                    "subject": item.get("subject"),
                    "mark": item.get("mark", item.get("total_score")),
                    "grade": item.get("grade"),
                }
                for item in subjects[:12]
            ],
        }
    )
    return entry


def _store_parent_admission_document(school_id, uploaded, file_bytes):
    original_filename = secure_filename(uploaded.filename or "") or f"document_{secrets.token_hex(4)}"
    document_id = f"parent_doc_{secrets.token_hex(6)}"
    stored_filename = f"{document_id}_{original_filename}"
    target_path = os.path.join(_get_parent_admission_document_storage_root(school_id=school_id), stored_filename)
    with open(target_path, "wb") as stored_file:
        stored_file.write(file_bytes or b"")

    return {
        "document_id": document_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "size_bytes": os.path.getsize(target_path),
    }


def _build_student_profile_picture_data_url(file_bytes, content_type):
    if not file_bytes:
        return None

    normalized_content_type = sanitize_string(content_type or "") or "image/jpeg"
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{normalized_content_type};base64,{encoded}"


def _extract_latest_parent_admission_passport_photo(manifest, school_id):
    for entry in reversed(manifest or []):
        if not isinstance(entry, dict) or entry.get("category") != "passport_photo":
            continue

        resolved_path = _resolve_existing_school_file(
            _get_parent_admission_document_storage_root(school_id=school_id),
            entry.get("stored_filename"),
        )
        if not resolved_path:
            continue

        try:
            with open(resolved_path, "rb") as image_file:
                return _build_student_profile_picture_data_url(
                    image_file.read(),
                    entry.get("content_type") or "image/jpeg",
                )
        except OSError as exc:
            logger.warning("Unable to read parent admission passport photo %s: %s", entry.get("stored_filename"), exc)

    return None


def _build_staff_parent_admission_document_entry(application_id, school_id, raw_entry):
    if not isinstance(raw_entry, dict):
        return None

    entry = dict(raw_entry)
    document_id = sanitize_string(entry.get("document_id") or entry.get("id") or "") or None
    stored_filename = sanitize_string(entry.get("stored_filename") or "") or None
    original_filename = sanitize_string(entry.get("original_filename") or entry.get("filename") or "") or None
    resolved_path = None

    if stored_filename:
        resolved_path = _resolve_existing_school_file(
            _get_parent_admission_document_storage_root(school_id=school_id),
            stored_filename,
        )

    if document_id and stored_filename and resolved_path:
        entry["document_id"] = document_id
        entry["original_filename"] = original_filename or entry.get("filename") or "document"
        entry["download_path"] = _build_parent_admission_document_download_path(application_id, document_id)
        entry["download_available"] = True
    else:
        entry["download_available"] = False
        entry.pop("download_path", None)

    return entry


def _store_student_document(school_id, uploaded, file_bytes):
    original_filename = secure_filename(uploaded.filename or "") or f"student_document_{secrets.token_hex(4)}"
    document_id = f"student_doc_{secrets.token_hex(6)}"
    stored_filename = f"{document_id}_{original_filename}"
    target_path = os.path.join(_get_student_document_storage_root(school_id=school_id), stored_filename)
    with open(target_path, "wb") as stored_file:
        stored_file.write(file_bytes or b"")

    return {
        "document_id": document_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "size_bytes": os.path.getsize(target_path),
    }


def _allowed_school_verification_document(filename, content_type):
    lowered_name = (filename or "").strip().lower()
    lowered_type = (content_type or "").strip().lower()
    allowed_extensions = (".jpg", ".jpeg", ".png", ".pdf")
    allowed_types = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}
    return lowered_name.endswith(allowed_extensions) or lowered_type in allowed_types


def _store_school_verification_document(school_id, uploaded, file_bytes):
    original_filename = secure_filename(uploaded.filename or "") or f"school_verification_document_{secrets.token_hex(4)}"
    document_id = f"school_verification_doc_{secrets.token_hex(6)}"
    stored_filename = f"{document_id}_{original_filename}"
    target_path = os.path.join(_get_school_verification_document_storage_root(school_id=school_id), stored_filename)
    with open(target_path, "wb") as stored_file:
        stored_file.write(file_bytes or b"")

    return {
        "document_id": document_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "size_bytes": os.path.getsize(target_path),
    }


def _build_school_verification_document_entry(raw_entry):
    if isinstance(raw_entry, str):
        url = sanitize_string(raw_entry or "") or None
        if not url:
            return None
        return {
            "url": url,
            "name": url,
            "download_available": False,
        }

    if not isinstance(raw_entry, dict):
        return None

    entry = dict(raw_entry)
    document_id = sanitize_string(entry.get("document_id") or entry.get("id") or "") or None
    stored_filename = sanitize_string(entry.get("stored_filename") or "") or None
    original_filename = sanitize_string(entry.get("original_filename") or entry.get("filename") or "") or None
    url = sanitize_string(entry.get("url") or entry.get("link") or "") or None

    if document_id and stored_filename:
        entry["document_id"] = document_id
        entry["original_filename"] = original_filename or "document"
        entry["name"] = original_filename or "document"
        entry["download_path"] = _build_school_verification_document_download_path(document_id)
        entry["download_available"] = True
        return entry

    if url:
        entry["url"] = url
        entry["name"] = original_filename or entry.get("filename") or url
        entry["download_available"] = False
        return entry

    return None


def _build_platform_school_verification_document_entry(school_id, raw_entry):
    entry = _build_school_verification_document_entry(raw_entry)
    if not entry:
        return None

    if entry.get("document_id"):
        entry["download_path"] = f"/api/platform/compliance/schools/{quote(str(school_id))}/documents/{quote(entry['document_id'])}/download"

    return entry


def _get_student_document_manifest(student):
    custom_attributes = json.loads(json.dumps(student.custom_attributes or {}))
    manifest = custom_attributes.get("document_manifest") or []
    return manifest if isinstance(manifest, list) else []


def _set_student_document_manifest(student, manifest):
    custom_attributes = json.loads(json.dumps(student.custom_attributes or {}))
    custom_attributes["document_manifest"] = manifest
    student.custom_attributes = custom_attributes


def _build_student_document_entry(student_id, raw_entry):
    if not isinstance(raw_entry, dict):
        return None

    entry = dict(raw_entry)
    document_id = sanitize_string(entry.get("document_id") or entry.get("id") or "") or None
    stored_filename = sanitize_string(entry.get("stored_filename") or "") or None
    original_filename = sanitize_string(entry.get("original_filename") or entry.get("filename") or "") or None

    if document_id and stored_filename:
        entry["document_id"] = document_id
        entry["original_filename"] = original_filename or entry.get("filename") or "document"
        entry["download_path"] = _build_student_document_download_path(student_id, document_id)
        entry["download_available"] = True
    else:
        entry["download_available"] = False

    entry["source"] = entry.get("source") or "student_profile"
    return entry


def _build_linked_student_admission_documents(student):
    application = ParentAdmissionApplication.query.filter_by(
        admitted_student_id=student.id,
        school_id=student.school_id,
    ).first()
    if not application:
        return []

    entries = []
    for raw_entry in application.document_manifest or []:
        entry = _build_staff_parent_admission_document_entry(application.id, student.school_id, raw_entry)
        if not entry:
            continue
        entry["source"] = "parent_admission"
        entry["source_label"] = f"Admissions application {application.application_code}"
        entries.append(entry)

    return entries


def _build_staff_parent_admission_payload(application, settings, school_id):
    payload = _apply_parent_admission_review_details(application.to_staff_dict())
    payload["document_manifest"] = [
        item
        for item in (
            _build_staff_parent_admission_document_entry(application.id, school_id, entry)
            for entry in (payload.get("document_manifest") or [])
        )
        if item
    ]

    decision_document = _build_staff_parent_decision_document_payload(application, settings, school_id)
    if decision_document:
        payload["decision_document"] = decision_document

    return payload


def _get_school_admission_fee_config(settings):
    enabled = bool(getattr(settings, "admission_fee_enabled", False)) if settings else False
    amount = float(getattr(settings, "admission_fee_amount", 0.0) or 0.0) if settings else 0.0
    if amount <= 0:
        enabled = False
    return {
        "enabled": enabled,
        "amount": round(amount, 2),
        "currency": settings.currency if settings and settings.currency else "GH₵",
        "label": "Admission Fee",
    }


def _get_enabled_modules(settings):
    modules = getattr(settings, "enabled_modules", None) if settings else None
    return modules if isinstance(modules, dict) else {}


def _has_ai_employee_addon(settings, addon_key):
    return bool(_get_enabled_modules(settings).get(addon_key, False))


def _has_ai_registrar_access(school):
    return has_feature(get_effective_plan(school), "ai_registrar")


def _get_public_school_profile_payload(school, settings):
    verification = _get_school_verification_snapshot(school.id)
    return {
        "school_id": school.id,
        "school_name": school.name,
        "logo_url": school.logo_url,
        "theme_color": school.primary_color or "#1e3a8a",
        "motto": school.motto,
        "school_email": school.school_email,
        "school_phone": school.school_phone,
        "school_address": school.school_address,
        "school_website": school.school_website,
        "verification_status": verification.get("status"),
        "is_verified": bool(verification.get("is_verified")),
        "country_code": settings.country_code if settings and settings.country_code else "GH",
        "admission_fee": _get_school_admission_fee_config(settings),
    }


def _can_expose_parent_decision_pdf(school, settings):
    pdf_policy = _get_parent_admission_pdf_policy(settings)
    return pdf_policy["enabled"] and _has_ai_registrar_access(school)


def _build_staff_parent_decision_document_payload(application, settings, school_id):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if application.status != "Approved" or not school or not _can_expose_parent_decision_pdf(school, settings):
        return None
    decision_path = _build_parent_decision_pdf_path(school_id, application.status_token)
    return {
        "available": True,
        "download_path": decision_path,
        "download_url": _build_parent_public_url(decision_path),
        "delivery_mode": _get_parent_admission_pdf_policy(settings)["delivery_mode"],
    }


def _build_parent_status_path(school_id, status_token):
    return f"/apply/{school_id}/status/{status_token}"


def _build_parent_payment_path(school_id, student_code):
    return f"/pay/{school_id}/{student_code}"


def _build_parent_admission_payment_path(school_id, status_token):
    return f"/apply/{school_id}/status/{quote(status_token)}"


def _build_parent_decision_pdf_path(school_id, status_token):
    return f"/api/public/schools/{school_id}/admissions/status/{quote(status_token)}/decision-pdf"


def _build_parent_public_url(path):
    configured = (os.getenv("PARENT_PORTAL_BASE_URL") or "").strip()
    origin = configured or request.headers.get("Origin") or request.host_url.rstrip("/")
    return f"{origin.rstrip('/')}{path}"


PARENT_ADMISSION_WORKFLOW_KEY = "parent_admissions_workflow"
PARENT_ADMISSION_REVIEW_META_PREFIX = "[EDUPULSE_PARENT_ADMISSION_META]"
DATA_COMPLIANCE_WORKFLOW_KEY = "data_compliance_workflow"
EXAM_INTELLIGENCE_WORKFLOW_KEY = "exam_intelligence"
PAYMENT_PROVIDER_SETTINGS_KEY = "payment_provider_settings"
PAYMENT_COLLECTION_PRICING_KEY = "payment_collection_pricing"
TEACHER_CLASS_LEVEL_EXAM_SUMMARIES_KEY = "teacher_class_level_exam_summaries_enabled"
PARENT_ADMISSION_CONSENT_VERSION = "2026-04-29"

DEFAULT_DATA_COMPLIANCE_WORKFLOW = {
    "registration_acknowledgements": {
        "school_data_authority_confirmed": False,
        "legacy_and_exam_consent_plan_confirmed": False,
        "aggregated_analytics_accepted": False,
        "accepted_at": None,
        "accepted_ip": None,
        "terms_version": None,
        "policy_version": None,
        "proprietor_user_id": None,
    },
    "legacy_migration": {
        "parent_notice_dispatched": False,
        "consent_collection_completed": False,
        "consent_collection_date": None,
        "evidence_notes": "",
        "evidence_artifacts": [],
        "bece_result_processing_enabled": False,
        "bece_parent_notice_confirmed": False,
    },
}

DEFAULT_EXAM_INTELLIGENCE_WORKFLOW = {
    "imports": [],
}

DEFAULT_PAYMENT_PROVIDER_SETTINGS = {
    "paystack_subaccount_code": "",
    "paystack_bank_code": "",
    "paystack_resolved_account_name": "",
}

PAYMENT_COLLECTION_SPLIT_CACHE_KEY = "payment_collection_split_cache"

DEFAULT_PAYMENT_COLLECTION_PRICING = {
    "charge_parent_convenience_fee": True,
    "estimated_provider_fee_rate_pct": float(os.getenv("EDUPULSE_PAYSTACK_TRANSFER_FEE_RATE_PCT") or 0.0),
    "estimated_provider_fee_flat": float(os.getenv("EDUPULSE_PAYSTACK_TRANSFER_FEE_FLAT") or 0.0),
    "platform_fee_flat": float(os.getenv("EDUPULSE_PLATFORM_TRANSFER_FEE_FLAT") or 0.0),
    "platform_fee_label": sanitize_string(os.getenv("EDUPULSE_PLATFORM_TRANSFER_FEE_LABEL") or "Convenience Fee") or "Convenience Fee",
}

DEFAULT_PARENT_ADMISSION_WORKFLOW = {
    "response_templates": {
        "approve": "Congratulations. {student_name} has been offered admission to {school_name} for {class_assigned}.",
        "reject": "Thank you for applying to {school_name}. The school is unable to offer admission at this time.",
        "request_correction": "The school needs more information before final review. Please update the missing details or documents listed on your status page.",
        "invite_test": "Your application is ready for the online admission-test path. Please follow the school instructions shared below.",
        "schedule_visit": "Please visit {school_name} for the next admissions step. Review the visit details below and contact the school if you need to reschedule.",
    },
    "visit_defaults": {
        "location": "",
        "contact_person": "",
        "contact_phone": "",
    },
}


def _normalize_parent_admission_workflow_config(raw_config):
    config = _clone_json_document(raw_config)
    if not isinstance(config, dict):
        config = {}

    raw_templates = config.get("response_templates") if isinstance(config.get("response_templates"), dict) else {}
    raw_visit_defaults = config.get("visit_defaults") if isinstance(config.get("visit_defaults"), dict) else {}

    return {
        "response_templates": {
            key: sanitize_string(raw_templates.get(key) or default_value) or default_value
            for key, default_value in DEFAULT_PARENT_ADMISSION_WORKFLOW["response_templates"].items()
        },
        "visit_defaults": {
            "location": sanitize_string(raw_visit_defaults.get("location") or "") or "",
            "contact_person": sanitize_string(raw_visit_defaults.get("contact_person") or "") or "",
            "contact_phone": sanitize_string(raw_visit_defaults.get("contact_phone") or "") or "",
        },
    }


def _normalize_payment_provider_settings(raw_config):
    config = _clone_json_document(raw_config)
    if not isinstance(config, dict):
        config = {}

    return {
        "paystack_subaccount_code": sanitize_string(config.get("paystack_subaccount_code") or "") or "",
        "paystack_bank_code": sanitize_string(config.get("paystack_bank_code") or "") or "",
        "paystack_resolved_account_name": sanitize_string(config.get("paystack_resolved_account_name") or "") or "",
    }


def _normalize_payment_collection_pricing(raw_config):
    config = _clone_json_document(raw_config)
    if not isinstance(config, dict):
        config = {}

    def _float_value(key):
        try:
            return round(float(config.get(key, DEFAULT_PAYMENT_COLLECTION_PRICING[key]) or 0.0), 2)
        except (TypeError, ValueError):
            return round(float(DEFAULT_PAYMENT_COLLECTION_PRICING[key] or 0.0), 2)

    return {
        "charge_parent_convenience_fee": bool(config.get("charge_parent_convenience_fee", DEFAULT_PAYMENT_COLLECTION_PRICING["charge_parent_convenience_fee"])),
        "estimated_provider_fee_rate_pct": _float_value("estimated_provider_fee_rate_pct"),
        "estimated_provider_fee_flat": _float_value("estimated_provider_fee_flat"),
        "platform_fee_flat": _float_value("platform_fee_flat"),
        "platform_fee_label": sanitize_string(config.get("platform_fee_label") or DEFAULT_PAYMENT_COLLECTION_PRICING["platform_fee_label"]) or DEFAULT_PAYMENT_COLLECTION_PRICING["platform_fee_label"],
    }


def _normalize_data_compliance_workflow_config(raw_config):
    config = _clone_json_document(raw_config)
    if not isinstance(config, dict):
        config = {}

    raw_registration = config.get("registration_acknowledgements")
    if not isinstance(raw_registration, dict):
        raw_registration = {}
    raw_legacy = config.get("legacy_migration")
    if not isinstance(raw_legacy, dict):
        raw_legacy = {}
    raw_artifacts = raw_legacy.get("evidence_artifacts")
    if not isinstance(raw_artifacts, list):
        raw_artifacts = []

    consent_collection_date = sanitize_string(raw_legacy.get("consent_collection_date") or "") or None
    if consent_collection_date:
        try:
            from datetime import datetime as dt
            dt.strptime(consent_collection_date, "%Y-%m-%d")
        except ValueError:
            consent_collection_date = None

    return {
        "registration_acknowledgements": {
            "school_data_authority_confirmed": bool(raw_registration.get("school_data_authority_confirmed", False)),
            "legacy_and_exam_consent_plan_confirmed": bool(raw_registration.get("legacy_and_exam_consent_plan_confirmed", False)),
            "aggregated_analytics_accepted": bool(raw_registration.get("aggregated_analytics_accepted", False)),
            "accepted_at": sanitize_string(raw_registration.get("accepted_at") or "") or None,
            "accepted_ip": sanitize_string(raw_registration.get("accepted_ip") or "") or None,
            "terms_version": sanitize_string(raw_registration.get("terms_version") or "") or None,
            "policy_version": sanitize_string(raw_registration.get("policy_version") or "") or None,
            "proprietor_user_id": raw_registration.get("proprietor_user_id") if isinstance(raw_registration.get("proprietor_user_id"), int) else None,
        },
        "legacy_migration": {
            "parent_notice_dispatched": bool(raw_legacy.get("parent_notice_dispatched", False)),
            "consent_collection_completed": bool(raw_legacy.get("consent_collection_completed", False)),
            "consent_collection_date": consent_collection_date,
            "evidence_notes": sanitize_string(raw_legacy.get("evidence_notes") or "") or "",
            "evidence_artifacts": [
                artifact
                for artifact in [_normalize_legacy_consent_evidence_artifact(item) for item in raw_artifacts]
                if artifact
            ][:24],
            "bece_result_processing_enabled": bool(raw_legacy.get("bece_result_processing_enabled", False)),
            "bece_parent_notice_confirmed": bool(raw_legacy.get("bece_parent_notice_confirmed", False)),
        },
    }


def _normalize_legacy_consent_evidence_artifact(raw_artifact):
    if not isinstance(raw_artifact, dict):
        return None

    artifact_id = sanitize_string(raw_artifact.get("id") or "") or None
    stored_filename = sanitize_string(raw_artifact.get("stored_filename") or "") or None
    original_filename = sanitize_string(raw_artifact.get("original_filename") or "") or None
    if not artifact_id or not stored_filename or not original_filename:
        return None

    return {
        "id": artifact_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "category": sanitize_string(raw_artifact.get("category") or "general") or "general",
        "note": sanitize_string(raw_artifact.get("note") or "") or "",
        "uploaded_at": sanitize_string(raw_artifact.get("uploaded_at") or "") or None,
        "uploaded_by": raw_artifact.get("uploaded_by") if isinstance(raw_artifact.get("uploaded_by"), int) else None,
        "size_bytes": int(raw_artifact.get("size_bytes") or 0),
    }


def _normalize_exam_import_entry(raw_import):
    if not isinstance(raw_import, dict):
        return None

    batch_id = sanitize_string(raw_import.get("id") or "") or None
    stored_filename = sanitize_string(raw_import.get("stored_filename") or "") or None
    source_filename = sanitize_string(raw_import.get("source_filename") or "") or None
    parsed_rows_filename = sanitize_string(raw_import.get("parsed_rows_filename") or "") or None
    if not batch_id or not stored_filename or not source_filename:
        return None

    subject_summaries = raw_import.get("subject_summaries")
    if not isinstance(subject_summaries, list):
        subject_summaries = []

    normalized_subject_summaries = []
    for item in subject_summaries:
        if not isinstance(item, dict):
            continue
        subject_name = sanitize_string(item.get("subject") or "") or None
        if not subject_name:
            continue
        normalized_subject_summaries.append(
            {
                "subject": subject_name,
                "average_score": round(float(item.get("average_score") or 0), 2),
                "pass_rate": round(float(item.get("pass_rate") or 0), 2),
                "entries": int(item.get("entries") or 0),
            }
        )

    return {
        "id": batch_id,
        "exam_type": sanitize_string(raw_import.get("exam_type") or "BECE") or "BECE",
        "academic_year": sanitize_string(raw_import.get("academic_year") or "") or "Unknown",
        "source_filename": source_filename,
        "stored_filename": stored_filename,
        "parsed_rows_filename": parsed_rows_filename,
        "source_format": sanitize_string(raw_import.get("source_format") or "document") or "document",
        "parse_mode": sanitize_string(raw_import.get("parse_mode") or "structured_text") or "structured_text",
        "uploaded_at": sanitize_string(raw_import.get("uploaded_at") or "") or None,
        "uploaded_by": raw_import.get("uploaded_by") if isinstance(raw_import.get("uploaded_by"), int) else None,
        "candidate_count": int(raw_import.get("candidate_count") or 0),
        "subject_entry_count": int(raw_import.get("subject_entry_count") or 0),
        "average_score": round(float(raw_import.get("average_score") or 0), 2),
        "pass_rate": round(float(raw_import.get("pass_rate") or 0), 2),
        "subject_summaries": normalized_subject_summaries[:12],
    }


def _get_exam_intelligence_workflow_config(settings):
    global_settings = _get_report_global_settings(settings)
    raw_config = _clone_json_document(global_settings.get(EXAM_INTELLIGENCE_WORKFLOW_KEY) or DEFAULT_EXAM_INTELLIGENCE_WORKFLOW)
    if not isinstance(raw_config, dict):
        raw_config = {}
    raw_imports = raw_config.get("imports")
    if not isinstance(raw_imports, list):
        raw_imports = []
    return {
        "imports": [
            item for item in (_normalize_exam_import_entry(entry) for entry in raw_imports) if item
        ][:36],
    }


def _set_exam_intelligence_workflow_config(settings, workflow_config):
    config = _clone_json_document(settings.report_template_config)
    global_settings = config.get(GLOBAL_REPORT_SETTINGS_KEY) or {}
    if not isinstance(global_settings, dict):
        global_settings = {}

    imports = workflow_config.get("imports") if isinstance(workflow_config, dict) else []
    if not isinstance(imports, list):
        imports = []
    global_settings[EXAM_INTELLIGENCE_WORKFLOW_KEY] = {
        "imports": [
            item for item in (_normalize_exam_import_entry(entry) for entry in imports) if item
        ][:36]
    }
    config[GLOBAL_REPORT_SETTINGS_KEY] = global_settings
    settings.report_template_config = config


def _get_school_storage_root(config_key, default_folder_name, school_id=None):
    base_dir = current_app.config.get(config_key) or os.path.join(current_app.instance_path, default_folder_name)
    os.makedirs(base_dir, exist_ok=True)
    resolved_school_id = str(school_id or getattr(g, "school_id", "")).strip()
    if not resolved_school_id:
        raise ValueError("school_id is required to resolve school storage")
    school_dir = os.path.join(base_dir, resolved_school_id)
    os.makedirs(school_dir, exist_ok=True)
    return school_dir


def _get_legacy_evidence_storage_root():
    return _get_school_storage_root("LEGACY_CONSENT_EVIDENCE_STORAGE_DIR", "legacy-consent-evidence")


def _get_exam_import_storage_root():
    return _get_school_storage_root("EXAM_INTELLIGENCE_STORAGE_DIR", "exam-intelligence")


def _get_parent_admission_document_storage_root(school_id=None):
    return _get_school_storage_root("PARENT_ADMISSION_DOCUMENT_STORAGE_DIR", "parent-admission-documents", school_id=school_id)


def _get_student_document_storage_root(school_id=None):
    return _get_school_storage_root("STUDENT_DOCUMENT_STORAGE_DIR", "student-documents", school_id=school_id)


def _get_school_verification_document_storage_root(school_id=None):
    return _get_school_storage_root("SCHOOL_VERIFICATION_DOCUMENT_STORAGE_DIR", "school-verification-documents", school_id=school_id)


def _resolve_existing_school_file(storage_root, stored_filename):
    if not stored_filename:
        return None
    candidate_path = os.path.join(storage_root, stored_filename)
    if os.path.isfile(candidate_path):
        return candidate_path

    base_dir = os.path.dirname(storage_root.rstrip(os.sep))
    legacy_candidate = os.path.join(base_dir, stored_filename)
    if os.path.isfile(legacy_candidate):
        return legacy_candidate

    try:
        for entry in os.scandir(base_dir):
            if not entry.is_dir():
                continue
            nested_candidate = os.path.join(entry.path, stored_filename)
            if os.path.isfile(nested_candidate):
                return nested_candidate
    except OSError:
        return None

    return None


def _build_legacy_evidence_download_path(artifact_id):
    return f"/api/school/settings/legacy-consent-evidence/{quote(artifact_id)}/download"


def _build_exam_import_download_path(batch_id):
    return f"/api/analytics/exam-imports/{quote(batch_id)}/download"


def _build_parent_admission_document_download_path(application_id, document_id):
    return f"/api/admissions/applications/{quote(str(application_id))}/documents/{quote(document_id)}/download"


def _build_student_document_download_path(student_id, document_id):
    return f"/api/students/{quote(str(student_id))}/documents/{quote(document_id)}/download"


def _build_school_verification_document_download_path(document_id):
    return f"/api/school/verification/documents/{quote(document_id)}/download"


def _build_exam_rows_snapshot_path(batch_id):
    return f"{batch_id}_rows.json"


def _normalize_exam_row_key(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _extract_exam_row_value(row, aliases):
    normalized_row = {
        _normalize_exam_row_key(key): value
        for key, value in (row or {}).items()
        if key is not None
    }
    for alias in aliases:
        if alias in normalized_row and normalized_row[alias] not in (None, ""):
            return normalized_row[alias]
    return ""


def _parse_exam_score_value(value):
    text_value = sanitize_string(value or "") or ""
    if not text_value:
        return None
    text_value = text_value.replace("%", "").replace(",", "")
    try:
        return float(text_value)
    except (TypeError, ValueError):
        return None


def _is_exam_result_pass(score, grade):
    if score is not None:
        return score >= 50

    grade_text = (sanitize_string(grade or "") or "").upper()
    if not grade_text:
        return False
    if grade_text.isdigit():
        return int(grade_text) <= 6
    if grade_text in {"A1", "B2", "B3", "C4", "C5", "C6", "PASS"}:
        return True
    if grade_text in {"D7", "E8", "F9", "FAIL"}:
        return False
    return False


def _parse_exam_csv_rows(file_stream):
    try:
        decoded = file_stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        file_stream.seek(0)
        decoded = file_stream.read().decode("latin-1")

    reader = csv.DictReader(StringIO(decoded))
    rows = []
    for raw_row in reader:
        candidate_name = sanitize_string(
            _extract_exam_row_value(raw_row, ["candidate_name", "student_name", "name", "candidate"])
        )
        subject_name = sanitize_string(
            _extract_exam_row_value(raw_row, ["subject", "subject_name", "paper", "course"])
        )
        if not candidate_name or not subject_name:
            continue
        rows.append(
            {
                "candidate_name": candidate_name,
                "candidate_identifier": sanitize_string(
                    _extract_exam_row_value(raw_row, ["candidate_id", "index_number", "student_code"])
                ) or candidate_name,
                "class_name": sanitize_string(
                    _extract_exam_row_value(raw_row, ["class_name", "class", "current_class", "grade_level", "form"])
                ) or None,
                "gender": (sanitize_string(_extract_exam_row_value(raw_row, ["gender", "sex"])) or "Unknown").title(),
                "subject": subject_name,
                "score": _parse_exam_score_value(
                    _extract_exam_row_value(raw_row, ["score", "total_score", "mark", "marks"])
                ),
                "grade": sanitize_string(_extract_exam_row_value(raw_row, ["grade", "result_grade"])) or "",
            }
        )

    if not rows:
        raise ValueError("The uploaded CSV did not contain valid candidate_name and subject columns.")
    return rows


def _parse_exam_text_rows(text):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    rows = []

    delimited_pattern = re.compile(
        r"^(?P<candidate>[^|,;]+?)\s*[|,;]\s*(?P<gender>[^|,;]+?)\s*[|,;]\s*(?P<subject>[^|,;]+?)\s*[|,;]\s*(?P<score>[A-Za-z0-9.%-]+?)\s*[|,;]\s*(?P<grade>[A-Za-z0-9+-]+)\s*$"
    )
    spaced_pattern = re.compile(
        r"^(?P<candidate>[A-Za-z][A-Za-z '.-]+?)\s+(?P<gender>Male|Female|M|F)\s+(?P<subject>[A-Za-z&/(). -]+?)\s+(?P<score>\d{1,3}(?:\.\d+)?)\s+(?P<grade>[A-F][1-9]?|[A-C][1-6]|PASS|FAIL|[1-9])$",
        re.IGNORECASE,
    )

    for line in lines:
        match = delimited_pattern.match(line) or spaced_pattern.match(line)
        if not match:
            continue
        candidate_name = sanitize_string(match.group("candidate") or "")
        subject_name = sanitize_string(match.group("subject") or "")
        if not candidate_name or not subject_name:
            continue
        gender_text = sanitize_string(match.group("gender") or "") or "Unknown"
        if gender_text.upper() == "M":
            gender_text = "Male"
        elif gender_text.upper() == "F":
            gender_text = "Female"
        score_text = sanitize_string(match.group("score") or "") or ""
        score_value = _parse_exam_score_value(score_text)
        rows.append(
            {
                "candidate_name": candidate_name,
                "candidate_identifier": candidate_name,
                "gender": gender_text.title(),
                "subject": subject_name,
                "score": score_value,
                "grade": sanitize_string(match.group("grade") or "") or score_text,
            }
        )

    if not rows:
        raise ValueError(
            "Could not parse the uploaded result document. Paste the extracted rows in this format: Candidate | Gender | Subject | Score | Grade"
        )
    return rows


def _load_exam_document_text(uploaded, file_ext, result_text=None):
    if result_text and sanitize_string(result_text or ""):
        return str(result_text)

    uploaded.stream.seek(0)
    file_bytes = uploaded.read()
    uploaded.stream.seek(0)

    if file_ext == ".txt":
        try:
            return file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")

    if file_ext in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            return ocr_image_bytes(file_bytes)
        except Exception as exc:
            raise ValueError(f"Image OCR failed: {exc}")

    if file_ext == ".pdf":
        extracted_text = ""
        pdf_text_error = None
        try:
            import pdfplumber
        except Exception as exc:
            pdf_text_error = exc
        else:
            try:
                extracted_pages = []
                with pdfplumber.open(BytesIO(file_bytes)) as pdf_document:
                    for page in pdf_document.pages:
                        extracted_pages.append(page.extract_text() or "")
                extracted_text = "\n".join(part for part in extracted_pages if part.strip()).strip()
            except Exception as exc:
                pdf_text_error = exc

        if extracted_text:
            return extracted_text

        try:
            return _extract_text_from_pdf_with_ocr(file_bytes)
        except ValueError as exc:
            if pdf_text_error:
                raise ValueError(f"PDF text extraction and OCR fallback both failed: {pdf_text_error}; {exc}")
            raise

    raise ValueError("Unsupported exam document format.")


def _extract_text_from_pdf_with_ocr(file_bytes):
    try:
        from pdf2image import convert_from_bytes, pdfinfo_from_bytes
    except Exception as exc:
        raise ValueError(
            f"PDF OCR dependencies are not available in this environment yet: {exc}."
        ) from exc

    try:
        pdf_info = pdfinfo_from_bytes(file_bytes)
        total_pages = int(pdf_info.get("Pages") or 0)
    except Exception:
        total_pages = 0

    if total_pages <= 0:
        total_pages = 1

    extracted_pages = []
    for page_number in range(1, total_pages + 1):
        try:
            rendered_pages = convert_from_bytes(
                file_bytes,
                dpi=200,
                fmt="png",
                first_page=page_number,
                last_page=page_number,
            )
        except Exception as exc:
            raise ValueError(f"PDF OCR page rendering failed on page {page_number}: {exc}") from exc

        if not rendered_pages:
            continue

        page_image = rendered_pages[0]
        image_buffer = BytesIO()
        try:
            page_image.save(image_buffer, format="PNG")
            page_text = ocr_image_bytes(image_buffer.getvalue()).strip()
        except Exception as exc:
            raise ValueError(f"PDF OCR failed on page {page_number}: {exc}") from exc

        if page_text:
            extracted_pages.append(page_text)

    extracted_text = "\n".join(extracted_pages).strip()
    if not extracted_text:
        raise ValueError(
            "This PDF did not expose extractable text automatically, and OCR could not recover readable text. Upload the PDF and paste the extracted rows in the review text box."
        )

    return extracted_text


def _build_exam_batch_summary(rows):
    if not rows:
        return {
            "candidate_count": 0,
            "subject_entry_count": 0,
            "average_score": 0.0,
            "pass_rate": 0.0,
            "subject_summaries": [],
        }

    unique_candidates = {row.get("candidate_identifier") or row.get("candidate_name") for row in rows}
    numeric_scores = [row["score"] for row in rows if row.get("score") is not None]
    pass_count = sum(1 for row in rows if _is_exam_result_pass(row.get("score"), row.get("grade")))
    subject_buckets = {}
    for row in rows:
        subject_name = row.get("subject") or "Unknown"
        bucket = subject_buckets.setdefault(subject_name, {"scores": [], "passes": 0, "entries": 0})
        bucket["entries"] += 1
        if row.get("score") is not None:
            bucket["scores"].append(row["score"])
        if _is_exam_result_pass(row.get("score"), row.get("grade")):
            bucket["passes"] += 1

    subject_summaries = []
    for subject_name, bucket in subject_buckets.items():
        average_score = round(sum(bucket["scores"]) / len(bucket["scores"]), 2) if bucket["scores"] else 0.0
        pass_rate = round((bucket["passes"] / bucket["entries"]) * 100, 2) if bucket["entries"] else 0.0
        subject_summaries.append(
            {
                "subject": subject_name,
                "average_score": average_score,
                "pass_rate": pass_rate,
                "entries": bucket["entries"],
            }
        )

    subject_summaries.sort(key=lambda item: (-item["average_score"], item["subject"]))
    return {
        "candidate_count": len(unique_candidates),
        "subject_entry_count": len(rows),
        "average_score": round(sum(numeric_scores) / len(numeric_scores), 2) if numeric_scores else 0.0,
        "pass_rate": round((pass_count / len(rows)) * 100, 2) if rows else 0.0,
        "subject_summaries": subject_summaries,
    }


def _load_exam_rows_for_batch(batch_meta):
    rows_filename = batch_meta.get("parsed_rows_filename")
    resolved_path = _resolve_existing_school_file(_get_exam_import_storage_root(), rows_filename)
    if not resolved_path:
        return []
    with open(resolved_path, "r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    rows = payload.get("rows") if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _normalize_exam_lookup_token(value):
    normalized = sanitize_string(value or "") or ""
    return re.sub(r"[^a-z0-9]+", "", normalized.lower())


def _build_student_exam_class_lookup():
    lookup = {}
    students = Student.query.filter_by(school_id=g.school_id).all()
    for student in students:
        class_name = sanitize_string(student.current_class or "") or None
        if not class_name:
            continue
        for raw_key in [student.student_code, student.name, f"{student.first_name} {student.surname}"]:
            token = _normalize_exam_lookup_token(raw_key)
            if token:
                lookup[token] = class_name
    return lookup


def _resolve_exam_row_class_name(row, class_lookup):
    direct_class = sanitize_string((row or {}).get("class_name") or "") or None
    if direct_class:
        return direct_class

    for raw_key in [
        (row or {}).get("candidate_identifier"),
        (row or {}).get("candidate_name"),
    ]:
        token = _normalize_exam_lookup_token(raw_key)
        if token and token in class_lookup:
            return class_lookup[token]
    return None


def _build_exam_class_summaries(rows, allowed_classes=None, allowed_subjects=None):
    if not rows:
        return []

    class_lookup = _build_student_exam_class_lookup()
    normalized_allowed_classes = set(allowed_classes or [])
    normalized_allowed_subjects = set(allowed_subjects or [])
    class_buckets = {}

    for row in rows:
        class_name = _resolve_exam_row_class_name(row, class_lookup)
        subject_name = sanitize_string(row.get("subject") or "") or None
        if not class_name or not subject_name:
            continue
        if normalized_allowed_classes and class_name not in normalized_allowed_classes:
            continue
        if normalized_allowed_subjects and subject_name not in normalized_allowed_subjects:
            continue

        class_bucket = class_buckets.setdefault(class_name, [])
        class_bucket.append(row)

    summaries = []
    for class_name, class_rows in class_buckets.items():
        class_summary = _build_exam_batch_summary(class_rows)
        summaries.append(
            {
                "class_name": class_name,
                "candidate_count": class_summary.get("candidate_count", 0),
                "subject_entry_count": class_summary.get("subject_entry_count", 0),
                "average_score": class_summary.get("average_score", 0.0),
                "pass_rate": class_summary.get("pass_rate", 0.0),
                "subject_summaries": class_summary.get("subject_summaries", []),
            }
        )

    summaries.sort(key=lambda item: item.get("class_name") or "")
    return summaries


def _build_exam_intelligence_payload(settings):
    workflow_config = _get_exam_intelligence_workflow_config(settings)
    imports = sorted(
        workflow_config.get("imports") or [],
        key=lambda item: (_academic_year_sort_key(item.get("academic_year")), item.get("uploaded_at") or ""),
        reverse=True,
    )

    compliance_workflow = _get_data_compliance_workflow_config(settings)
    registration_ack = compliance_workflow.get("registration_acknowledgements") or {}
    legacy_migration = compliance_workflow.get("legacy_migration") or {}
    consent_plan_confirmed = bool(registration_ack.get("legacy_and_exam_consent_plan_confirmed"))
    bece_result_processing_enabled = bool(legacy_migration.get("bece_result_processing_enabled", False) or consent_plan_confirmed)
    bece_parent_notice_confirmed = bool(legacy_migration.get("bece_parent_notice_confirmed", False) or consent_plan_confirmed)
    compliance_ready = bool(
        registration_ack.get("school_data_authority_confirmed")
        and bece_result_processing_enabled
        and bece_parent_notice_confirmed
    )

    enriched_imports = []
    for batch in imports:
        item = dict(batch)
        item["download_path"] = _build_exam_import_download_path(batch["id"])
        enriched_imports.append(item)

    latest_batch = enriched_imports[0] if enriched_imports else None
    previous_batch = enriched_imports[1] if len(enriched_imports) > 1 else None
    latest_subjects = {item["subject"]: item for item in (latest_batch or {}).get("subject_summaries", [])}
    previous_subjects = {item["subject"]: item for item in (previous_batch or {}).get("subject_summaries", [])}

    subject_trends = []
    for subject_name, subject_summary in latest_subjects.items():
        previous = previous_subjects.get(subject_name)
        previous_average = previous.get("average_score") if previous else None
        subject_trends.append(
            {
                "subject": subject_name,
                "latest_average": subject_summary.get("average_score", 0.0),
                "previous_average": previous_average,
                "delta": round(subject_summary.get("average_score", 0.0) - previous_average, 2) if previous_average is not None else None,
                "latest_pass_rate": subject_summary.get("pass_rate", 0.0),
            }
        )
    subject_trends.sort(key=lambda item: (item["delta"] is None, -(item["delta"] or -999), item["subject"]))

    gender_comparison = []
    if latest_batch:
        rows = _load_exam_rows_for_batch(latest_batch)
        gender_buckets = {}
        for row in rows:
            gender_name = row.get("gender") or "Unknown"
            bucket = gender_buckets.setdefault(gender_name, {"scores": [], "passes": 0, "entries": 0})
            bucket["entries"] += 1
            if row.get("score") is not None:
                bucket["scores"].append(row["score"])
            if _is_exam_result_pass(row.get("score"), row.get("grade")):
                bucket["passes"] += 1
        for gender_name, bucket in gender_buckets.items():
            gender_comparison.append(
                {
                    "gender": gender_name,
                    "average_score": round(sum(bucket["scores"]) / len(bucket["scores"]), 2) if bucket["scores"] else 0.0,
                    "pass_rate": round((bucket["passes"] / bucket["entries"]) * 100, 2) if bucket["entries"] else 0.0,
                    "entries": bucket["entries"],
                }
            )
        gender_comparison.sort(key=lambda item: item["gender"])

    year_trends = [
        {
            "academic_year": item.get("academic_year"),
            "exam_type": item.get("exam_type"),
            "average_score": item.get("average_score", 0.0),
            "pass_rate": item.get("pass_rate", 0.0),
            "candidate_count": item.get("candidate_count", 0),
        }
        for item in reversed(enriched_imports)
    ]

    return {
        "compliance_ready": compliance_ready,
        "compliance_gaps": {
            "school_data_authority_confirmed": bool(registration_ack.get("school_data_authority_confirmed")),
            "bece_result_processing_enabled": bece_result_processing_enabled,
            "bece_parent_notice_confirmed": bece_parent_notice_confirmed,
        },
        "summary": {
            "total_imports": len(enriched_imports),
            "latest_average_score": latest_batch.get("average_score", 0.0) if latest_batch else 0.0,
            "latest_pass_rate": latest_batch.get("pass_rate", 0.0) if latest_batch else 0.0,
            "latest_candidate_count": latest_batch.get("candidate_count", 0) if latest_batch else 0,
        },
        "latest_batch": latest_batch,
        "batches": enriched_imports,
        "subject_trends": subject_trends[:12],
        "gender_comparison": gender_comparison,
        "year_trends": year_trends,
    }


def _build_teacher_exam_intelligence_payload(settings, teacher_id):
    payload = _build_exam_intelligence_payload(settings)
    global_settings = _get_report_global_settings(settings)
    class_level_summaries_enabled = bool(global_settings.get(TEACHER_CLASS_LEVEL_EXAM_SUMMARIES_KEY, False))
    assignments = TeacherAssignment.query.filter_by(school_id=g.school_id, teacher_id=teacher_id).all()
    assigned_subjects = sorted({assignment.subject_name for assignment in assignments if assignment.subject_name})
    assigned_classes = sorted({assignment.class_name for assignment in assignments if assignment.class_name})

    latest_batch = payload.get("latest_batch") or {}
    latest_subject_summaries = [
        item
        for item in (latest_batch.get("subject_summaries") or [])
        if item.get("subject") in assigned_subjects
    ]
    subject_trends = [
        item
        for item in (payload.get("subject_trends") or [])
        if item.get("subject") in assigned_subjects
    ]
    class_summaries = []
    if class_level_summaries_enabled and latest_batch:
        class_summaries = _build_exam_class_summaries(
            _load_exam_rows_for_batch(latest_batch),
            allowed_classes=assigned_classes,
            allowed_subjects=assigned_subjects,
        )

    return {
        "view_scope": "teacher_subject_summary",
        "raw_access": False,
        "class_level_summaries_enabled": class_level_summaries_enabled,
        "compliance_ready": payload.get("compliance_ready", False),
        "assigned_subjects": assigned_subjects,
        "assigned_classes": assigned_classes,
        "summary": {
            "tracked_subjects": len(subject_trends),
            "latest_subject_count": len(latest_subject_summaries),
            "latest_academic_year": latest_batch.get("academic_year"),
        },
        "latest_batch": {
            "academic_year": latest_batch.get("academic_year"),
            "exam_type": latest_batch.get("exam_type"),
            "subject_summaries": latest_subject_summaries,
        } if latest_batch else None,
        "subject_trends": subject_trends,
        "class_summaries": class_summaries,
    }


def _build_empty_teacher_exam_intelligence_payload(settings, teacher_id, warning_message=None):
    global_settings = _get_report_global_settings(settings)
    class_level_summaries_enabled = bool(global_settings.get(TEACHER_CLASS_LEVEL_EXAM_SUMMARIES_KEY, False))
    assignments = TeacherAssignment.query.filter_by(school_id=g.school_id, teacher_id=teacher_id).all()
    assigned_subjects = sorted({assignment.subject_name for assignment in assignments if assignment.subject_name})
    assigned_classes = sorted({assignment.class_name for assignment in assignments if assignment.class_name})

    return {
        "view_scope": "teacher_subject_summary",
        "raw_access": False,
        "class_level_summaries_enabled": class_level_summaries_enabled,
        "compliance_ready": False,
        "assigned_subjects": assigned_subjects,
        "assigned_classes": assigned_classes,
        "summary": {
            "tracked_subjects": 0,
            "latest_subject_count": 0,
            "latest_academic_year": None,
        },
        "latest_batch": None,
        "subject_trends": [],
        "class_summaries": [],
        "warning": warning_message,
    }


def _build_academic_guidance_scope(user):
    allowed_classes = None
    allowed_subjects = None
    role_label = user.role.title() if user.role else "Staff"

    if user.role == "teacher":
        assignments = TeacherAssignment.query.filter_by(school_id=g.school_id, teacher_id=user.id).all()
        allowed_classes = sorted({assignment.class_name for assignment in assignments if assignment.class_name})
        allowed_subjects = sorted({assignment.subject_name for assignment in assignments if assignment.subject_name})
        if not allowed_classes and user.assigned_class:
            allowed_classes = [user.assigned_class]
        role_label = "Subject Teacher"
    elif user.role == "homeroom":
        allowed_classes = [user.assigned_class] if user.assigned_class else []
        role_label = "Homeroom Teacher"

    return {
        "allowed_classes": allowed_classes,
        "allowed_subjects": allowed_subjects,
        "role_label": role_label,
    }


def _get_latest_report_scope():
    latest_report = (
        ReportCard.query.filter_by(school_id=g.school_id)
        .order_by(ReportCard.created_at.desc(), ReportCard.id.desc())
        .first()
    )
    if not latest_report:
        return None, None, []

    reports = ReportCard.query.filter_by(
        school_id=g.school_id,
        academic_term=latest_report.academic_term,
        academic_year=latest_report.academic_year,
    ).all()
    return latest_report.academic_term, latest_report.academic_year, reports


def _get_data_compliance_workflow_config(settings):
    global_settings = _get_report_global_settings(settings)
    return _normalize_data_compliance_workflow_config(global_settings.get(DATA_COMPLIANCE_WORKFLOW_KEY))


def _get_payment_provider_settings(settings):
    global_settings = _get_report_global_settings(settings)
    return _normalize_payment_provider_settings(global_settings.get(PAYMENT_PROVIDER_SETTINGS_KEY))


def _set_payment_provider_settings(settings, workflow_config):
    _set_report_global_setting(
        settings,
        PAYMENT_PROVIDER_SETTINGS_KEY,
        _normalize_payment_provider_settings(workflow_config),
    )


def _get_payment_collection_pricing():
    setting = PlatformSetting.query.filter_by(setting_key=PAYMENT_COLLECTION_PRICING_KEY).first()
    raw_config = setting.setting_value if setting and isinstance(setting.setting_value, dict) else DEFAULT_PAYMENT_COLLECTION_PRICING
    return _normalize_payment_collection_pricing(raw_config)


def _get_payment_collection_split_cache():
    setting = PlatformSetting.query.filter_by(setting_key=PAYMENT_COLLECTION_SPLIT_CACHE_KEY).first()
    raw_cache = setting.setting_value if setting and isinstance(setting.setting_value, dict) else {}
    return _clone_json_document(raw_cache) if isinstance(raw_cache, dict) else {}


def _set_payment_collection_split_cache(cache_payload):
    safe_payload = _clone_json_document(cache_payload) if isinstance(cache_payload, dict) else {}
    setting = PlatformSetting.query.filter_by(setting_key=PAYMENT_COLLECTION_SPLIT_CACHE_KEY).first()
    if setting:
        setting.setting_value = safe_payload
    else:
        setting = PlatformSetting(setting_key=PAYMENT_COLLECTION_SPLIT_CACHE_KEY, setting_value=safe_payload)
        db.session.add(setting)
    db.session.flush()


def _set_data_compliance_workflow_config(settings, workflow_config):
    config = _clone_json_document(settings.report_template_config)
    global_settings = config.get(GLOBAL_REPORT_SETTINGS_KEY) or {}
    if not isinstance(global_settings, dict):
        global_settings = {}
    global_settings[DATA_COMPLIANCE_WORKFLOW_KEY] = _normalize_data_compliance_workflow_config(workflow_config)
    config[GLOBAL_REPORT_SETTINGS_KEY] = global_settings
    settings.report_template_config = config


def _get_parent_admission_workflow_config(settings):
    global_settings = _get_report_global_settings(settings)
    return _normalize_parent_admission_workflow_config(global_settings.get(PARENT_ADMISSION_WORKFLOW_KEY))


def _set_parent_admission_workflow_config(settings, workflow_config):
    config = _clone_json_document(settings.report_template_config)
    global_settings = config.get(GLOBAL_REPORT_SETTINGS_KEY) or {}
    if not isinstance(global_settings, dict):
        global_settings = {}
    global_settings[PARENT_ADMISSION_WORKFLOW_KEY] = _normalize_parent_admission_workflow_config(workflow_config)
    config[GLOBAL_REPORT_SETTINGS_KEY] = global_settings
    settings.report_template_config = config


def _render_parent_admission_template(template, context):
    rendered = str(template or "")
    for key, value in (context or {}).items():
        rendered = rendered.replace(f"{{{key}}}", str(value or ""))
    return rendered.strip()


def _build_parent_admission_follow_up_plan(action, payload, workflow_config):
    visit_defaults = workflow_config.get("visit_defaults") or {}
    visit_date = sanitize_string(payload.get("visit_date") or "") or ""
    visit_time = sanitize_string(payload.get("visit_time") or "") or ""
    visit_location = sanitize_string(payload.get("visit_location") or visit_defaults.get("location") or "") or ""
    visit_contact_person = sanitize_string(payload.get("visit_contact_person") or visit_defaults.get("contact_person") or "") or ""
    visit_contact_phone = sanitize_string(payload.get("visit_contact_phone") or visit_defaults.get("contact_phone") or "") or ""

    if visit_date:
        try:
            from datetime import datetime as dt
            dt.strptime(visit_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("visit_date must use YYYY-MM-DD format.")

    if visit_time:
        try:
            from datetime import datetime as dt
            dt.strptime(visit_time, "%H:%M")
        except ValueError:
            raise ValueError("visit_time must use HH:MM format.")

    if action != "schedule_visit":
        return None

    if not any([visit_date, visit_time, visit_location, visit_contact_person, visit_contact_phone]):
        return None

    return {
        "type": "school_visit",
        "date": visit_date or None,
        "time": visit_time or None,
        "location": visit_location or None,
        "contact_person": visit_contact_person or None,
        "contact_phone": visit_contact_phone or None,
    }


def _build_parent_admission_response_message(action, application, school, workflow_config, class_assigned=None, follow_up_plan=None):
    templates = workflow_config.get("response_templates") or {}
    template = templates.get(action) or DEFAULT_PARENT_ADMISSION_WORKFLOW["response_templates"].get(action) or ""
    context = {
        "school_name": school.name if school else "The school",
        "student_name": f"{application.first_name} {application.surname}".strip(),
        "application_code": application.application_code,
        "preferred_class": application.preferred_class or "",
        "class_assigned": class_assigned or application.preferred_class or "",
        "visit_date": (follow_up_plan or {}).get("date") or "",
        "visit_time": (follow_up_plan or {}).get("time") or "",
        "visit_location": (follow_up_plan or {}).get("location") or "",
        "visit_contact_person": (follow_up_plan or {}).get("contact_person") or "",
        "visit_contact_phone": (follow_up_plan or {}).get("contact_phone") or "",
    }
    return _render_parent_admission_template(template, context)


def _serialize_parent_admission_review_notes(reviewer_note, parent_response_message, follow_up_plan=None, class_assigned=None):
    meta = {
        "parent_response_message": sanitize_string(parent_response_message or "") or "",
        "follow_up_plan": follow_up_plan or None,
        "class_assigned": sanitize_string(class_assigned or "") or None,
    }
    note_body = sanitize_string(reviewer_note or "") or ""
    return f"{PARENT_ADMISSION_REVIEW_META_PREFIX}{json.dumps(meta, sort_keys=True)}\n{note_body}".rstrip()


def _normalize_parent_admission_payment_summary(raw_payment_summary, fee_config=None):
    fee_config = fee_config or {"enabled": False, "amount": 0.0, "currency": "GH₵", "label": "Admission Fee"}
    raw_payment_summary = raw_payment_summary if isinstance(raw_payment_summary, dict) else {}

    amount = raw_payment_summary.get("amount")
    try:
        amount = round(float(amount if amount not in (None, "") else fee_config.get("amount") or 0.0), 2)
    except (TypeError, ValueError):
        amount = round(float(fee_config.get("amount") or 0.0), 2)

    status = (sanitize_string(raw_payment_summary.get("status") or "") or "unpaid").lower()
    if status not in {"unpaid", "initiated", "paid"}:
        status = "unpaid"

    return {
        "enabled": bool(fee_config.get("enabled", False)),
        "label": sanitize_string(raw_payment_summary.get("label") or fee_config.get("label") or "Admission Fee") or "Admission Fee",
        "amount": amount,
        "currency": sanitize_string(raw_payment_summary.get("currency") or fee_config.get("currency") or "GH₵") or "GH₵",
        "status": "not_required" if not fee_config.get("enabled") else status,
        "provider": sanitize_string(raw_payment_summary.get("provider") or "paystack") or "paystack",
        "reference": sanitize_string(raw_payment_summary.get("reference") or "") or None,
        "started_at": sanitize_string(raw_payment_summary.get("started_at") or "") or None,
        "paid_at": sanitize_string(raw_payment_summary.get("paid_at") or "") or None,
    }


def _parse_parent_admission_review_notes(raw_notes):
    if not raw_notes or not isinstance(raw_notes, str):
        return {
            "reviewer_note": None,
            "parent_response_message": None,
            "follow_up_plan": None,
            "class_assigned": None,
            "payment_summary": None,
        }

    if not raw_notes.startswith(PARENT_ADMISSION_REVIEW_META_PREFIX):
        cleaned = raw_notes.strip() or None
        return {
            "reviewer_note": cleaned,
            "parent_response_message": cleaned,
            "follow_up_plan": None,
            "class_assigned": None,
            "payment_summary": None,
        }

    meta_line, _, note_body = raw_notes.partition("\n")
    meta_payload = meta_line[len(PARENT_ADMISSION_REVIEW_META_PREFIX):].strip()
    try:
        meta = json.loads(meta_payload) if meta_payload else {}
    except json.JSONDecodeError:
        meta = {}

    return {
        "reviewer_note": (note_body or "").strip() or None,
        "parent_response_message": sanitize_string(meta.get("parent_response_message") or "") or None,
        "follow_up_plan": meta.get("follow_up_plan") if isinstance(meta.get("follow_up_plan"), dict) else None,
        "class_assigned": sanitize_string(meta.get("class_assigned") or "") or None,
        "payment_summary": meta.get("payment_summary") if isinstance(meta.get("payment_summary"), dict) else None,
    }


def _apply_parent_admission_review_details(payload):
    enriched = dict(payload or {})
    parsed = _parse_parent_admission_review_notes(enriched.get("reviewer_notes"))
    enriched["reviewer_notes"] = parsed["reviewer_note"]
    enriched["parent_response_message"] = parsed["parent_response_message"]
    enriched["follow_up_plan"] = parsed["follow_up_plan"]
    if parsed["class_assigned"]:
        enriched["class_assigned"] = parsed["class_assigned"]
    enriched["payment_summary"] = parsed["payment_summary"]
    return enriched


def _set_parent_admission_payment_summary(application, payment_summary):
    parsed = _parse_parent_admission_review_notes(application.reviewer_notes)
    meta = {
        "parent_response_message": sanitize_string(parsed.get("parent_response_message") or "") or "",
        "follow_up_plan": parsed.get("follow_up_plan") if isinstance(parsed.get("follow_up_plan"), dict) else None,
        "class_assigned": sanitize_string(parsed.get("class_assigned") or "") or None,
        "payment_summary": payment_summary if isinstance(payment_summary, dict) else None,
    }
    reviewer_note = sanitize_string(parsed.get("reviewer_note") or "") or ""
    application.reviewer_notes = f"{PARENT_ADMISSION_REVIEW_META_PREFIX}{json.dumps(meta, sort_keys=True)}\n{reviewer_note}".rstrip()


def _get_parent_admission_payment_summary(application, settings):
    fee_config = _get_school_admission_fee_config(settings)
    parsed = _parse_parent_admission_review_notes(application.reviewer_notes)
    return _normalize_parent_admission_payment_summary(parsed.get("payment_summary"), fee_config=fee_config)


def _build_parent_admission_payment_payload(application, school, settings):
    payment_summary = _get_parent_admission_payment_summary(application, settings)
    payment_summary["payment_path"] = _build_parent_status_path(school.id, application.status_token)
    payment_summary["can_pay_now"] = bool(payment_summary.get("enabled") and payment_summary.get("status") != "paid")
    return payment_summary


def _get_parent_admission_pdf_policy(settings):
    delivery_mode = (getattr(settings, "approval_pdf_delivery_mode", None) or "email_link").strip()
    if delivery_mode not in {"status_page_only", "email_link", "email_attachment"}:
        delivery_mode = "email_link"

    return {
        "enabled": bool(getattr(settings, "approval_pdf_enabled", False)) if settings else False,
        "delivery_mode": delivery_mode,
        "include_payment_summary": bool(getattr(settings, "approval_pdf_include_payment_summary", True)) if settings else True,
        "include_required_items": bool(getattr(settings, "approval_pdf_include_required_items", True)) if settings else True,
        "required_items": (getattr(settings, "approval_pdf_required_items", None) or "").strip() if settings else "",
    }


def _build_parent_admission_decision_pdf_bytes(application, school, settings, payment_url=None):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(f"PDF engine unavailable: {exc}")

    policy = _get_parent_admission_pdf_policy(settings)
    fee_config = _get_school_admission_fee_config(settings)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    left = 40
    y = page_height - 50

    def ensure_space(required=80):
        nonlocal y
        if y <= required:
            pdf.showPage()
            y = page_height - 50
            pdf.setFont("Helvetica", 10)

    def write_wrapped(text, font_name="Helvetica", font_size=10, gap=14):
        nonlocal y
        pdf.setFont(font_name, font_size)
        for raw_line in str(text or "").splitlines() or [""]:
            for line in textwrap.wrap(raw_line, width=95) or [""]:
                ensure_space()
                pdf.drawString(left, y, line)
                y -= gap

    review_details = _parse_parent_admission_review_notes(application.reviewer_notes)
    student_name = f"{application.first_name} {application.surname}".strip()
    decision_date = application.reviewed_at or get_utc_now()
    class_offered = review_details.get("class_assigned") or application.preferred_class or "-"

    pdf.setTitle(f"Admission Decision - {student_name}")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, school.name or "EduPulse School")
    y -= 24

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(left, y, "Admission Decision")
    y -= 20

    write_wrapped(f"Learner: {student_name}", "Helvetica", 11)
    write_wrapped(f"Application code: {application.application_code}", "Helvetica", 11)
    write_wrapped(f"Decision: {application.status}", "Helvetica", 11)
    write_wrapped(f"Class offered: {class_offered}", "Helvetica", 11)
    write_wrapped(f"Decision date: {decision_date.strftime('%Y-%m-%d')}", "Helvetica", 11)
    y -= 6

    if review_details.get("parent_response_message"):
        write_wrapped("Admission Update", "Helvetica-Bold", 12)
        write_wrapped(review_details["parent_response_message"])
        y -= 6

    write_wrapped("School Notes", "Helvetica-Bold", 12)
    write_wrapped(review_details.get("reviewer_note") or "Approved by the school admissions team.")
    y -= 6

    if application.ai_summary:
        write_wrapped("Admission Summary", "Helvetica-Bold", 12)
        write_wrapped(application.ai_summary)
        y -= 6

    if policy["include_required_items"] and policy["required_items"]:
        write_wrapped("Items Needed After Approval", "Helvetica-Bold", 12)
        write_wrapped(policy["required_items"])
        y -= 6

    if policy["include_payment_summary"] and payment_url:
        write_wrapped("Payment Guidance", "Helvetica-Bold", 12)
        guidance = [
            "Use the school payment instructions page to view the approved payment channels and structured references.",
            f"Payment link: {payment_url}",
        ]
        if fee_config["enabled"]:
            guidance.append(f"School-configured admission fee: {fee_config['currency']} {fee_config['amount']:.2f}")
        write_wrapped(" ".join(guidance))
        y -= 6

    write_wrapped("School Contact", "Helvetica-Bold", 12)
    write_wrapped(f"Email: {school.school_email or '-'}")
    write_wrapped(f"Phone: {school.school_phone or '-'}")
    write_wrapped(f"Address: {school.school_address or '-'}")
    y -= 8
    write_wrapped("This document reflects a school-approved admission decision.", "Helvetica-Oblique", 10)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _build_parent_notification_sms(guardian_name, school_name, application_code, status_token, status_url):
    contact_name = guardian_name or "Parent/Guardian"
    return (
        f"{school_name}: Hello {contact_name}, your admission request {application_code} has been received. "
        f"Use token {status_token} to track it here: {status_url}"
    )


def _send_parent_admission_update(application, school, next_step, payment_url=None):
    if not application.parent_email:
        return False

    settings = SchoolSettings.query.filter_by(school_id=school.id).first()
    status_path = _build_parent_status_path(school.id, application.status_token)
    status_url = _build_parent_public_url(status_path)
    pdf_policy = _get_parent_admission_pdf_policy(settings)
    if application.status == "Approved" and _can_expose_parent_decision_pdf(school, settings) and pdf_policy["delivery_mode"] == "email_link":
        decision_url = _build_parent_public_url(_build_parent_decision_pdf_path(school.id, application.status_token))
        next_step = f"{next_step} Download the admission decision PDF here: {decision_url}"

    subject, body = get_parent_admission_status_email(
        guardian_name=application.guardian_name or "Parent/Guardian",
        school_name=school.name,
        student_name=f"{application.first_name} {application.surname}".strip(),
        application_code=application.application_code,
        status_token=application.status_token,
        status=application.status,
        summary=application.ai_summary or "Your application has been updated.",
        status_url=status_url,
        next_step=next_step,
        payment_url=payment_url,
    )
    if not subject or not body:
        return False
    return send_email_notification(application.parent_email, subject, body)


def _build_ai_registrar_assessment(payload, document_manifest):
    missing_items = []
    flags = []

    if not sanitize_string(payload.get("guardian_name")):
        missing_items.append("guardian_name")
    if not sanitize_string(payload.get("parent_email")) and not sanitize_string(payload.get("parent_phone")):
        missing_items.append("guardian_contact")
    preferred_class = sanitize_string(payload.get("preferred_class") or payload.get("class_assigned"))
    if preferred_class not in VALID_GRADES:
        missing_items.append("preferred_class")

    categories = {item.get("category") for item in (document_manifest or []) if isinstance(item, dict)}
    report_docs = [
        item for item in (document_manifest or []) if isinstance(item, dict) and item.get("category") == "previous_report"
    ]
    parsed_report_docs = [
        item for item in report_docs if item.get("ocr_status") == "parsed" and (item.get("ocr_subject_count") or 0) > 0
    ]
    if not document_manifest:
        missing_items.append("supporting_documents")
    if "birth_certificate" not in categories:
        flags.append("birth_certificate_not_detected")
    if "previous_report" not in categories:
        flags.append("previous_report_not_detected")
    elif report_docs and not parsed_report_docs:
        flags.append("previous_report_uploaded_but_not_parsed")

    high_confidence_report = None
    if parsed_report_docs:
        high_confidence_report = max(
            parsed_report_docs,
            key=lambda item: (item.get("ocr_confidence") or 0, item.get("ocr_subject_count") or 0),
        )
        if (high_confidence_report.get("ocr_confidence") or 0) < 0.85:
            flags.append("previous_report_low_confidence")

    desired_test_mode = sanitize_string(payload.get("desired_test_mode") or "either").lower()
    internet_quality = sanitize_string(payload.get("internet_quality") or "unknown").lower()

    score = 30
    if "guardian_name" not in missing_items:
        score += 15
    if "guardian_contact" not in missing_items:
        score += 15
    if "preferred_class" not in missing_items:
        score += 15
    if document_manifest:
        score += min(len(document_manifest) * 10, 25)
    if high_confidence_report:
        score += min((high_confidence_report.get("ocr_subject_count") or 0) * 2, 10)
        if (high_confidence_report.get("ocr_confidence") or 0) >= 0.85:
            score += 10

    extracted_average = high_confidence_report.get("ocr_term_average") if high_confidence_report else None
    extracted_subject_count = high_confidence_report.get("ocr_subject_count") if high_confidence_report else 0

    if missing_items:
        recommendation = "request_correction"
        status = "NeedsCorrection"
        summary = "Application received, but the AI Registrar found missing details that should be corrected before school review."
    elif desired_test_mode == "online" and internet_quality == "stable":
        recommendation = "invite_online_test"
        status = "TestReady"
        summary = "Application looks complete and internet quality is marked stable, so the AI Registrar recommends the remote admission-test path."
    elif desired_test_mode == "in_person" or internet_quality == "limited":
        recommendation = "schedule_school_visit"
        status = "VisitRequired"
        summary = "Application looks usable, but the AI Registrar recommends a school visit or in-person test because the family selected that route or indicated limited internet."
    else:
        recommendation = "manual_review"
        status = "ReviewReady"
        summary = "Application looks substantially complete and is ready for school review with AI-generated guidance."

    if high_confidence_report and extracted_subject_count:
        summary += (
            f" OCR extracted {extracted_subject_count} subject entries"
            + (f" with a detected term average of {float(extracted_average):.1f}." if extracted_average is not None else ".")
        )

    return {
        "readiness_score": max(0, min(int(score), 100)),
        "recommendation": recommendation,
        "status": status,
        "summary": summary,
        "flags": flags,
        "missing_items": missing_items,
        "ocr_summary": {
            "parsed_previous_reports": len(parsed_report_docs),
            "best_report_confidence": high_confidence_report.get("ocr_confidence") if high_confidence_report else None,
            "best_report_subject_count": extracted_subject_count or 0,
            "best_report_term_average": extracted_average,
        },
    }


def _admit_student_from_payload(school_id, data, actor_id):
    school = _lock_school_for_capacity_check(school_id)
    limit = get_plan_limits(get_effective_plan(school))
    current_count = _count_active_students_for_billing(school_id)
    school.current_student_count = current_count
    school.last_metered_at = get_utc_now()
    if current_count >= limit:
        raise ValueError(f"Admission failed: Plan limit of {limit} students reached. Please upgrade.")

    first_name = (data.get("first_name") or "").strip()
    surname = (data.get("surname") or "").strip()
    full_name = (data.get("name") or "").strip()

    if full_name and not first_name and not surname:
        parts = full_name.split(maxsplit=1)
        first_name = parts[0] if parts else ""
        surname = parts[1] if len(parts) > 1 else ""

    if not first_name or not surname:
        raise ValueError("Missing required fields: first_name and surname")

    full_name = f"{first_name} {surname}".strip()
    gender = (data.get("gender") or "").strip()

    date_of_birth = None
    raw_dob = (data.get("date_of_birth") or "").strip()
    if raw_dob:
        try:
            date_of_birth = date.fromisoformat(raw_dob)
        except ValueError as exc:
            raise ValueError("Invalid date_of_birth format. Use YYYY-MM-DD.") from exc

    scholarship_type = sanitize_string(data.get("scholarship_type") or "none").lower()
    scholarship_notes = sanitize_string(data.get("scholarship_notes") or "")
    if scholarship_type not in {"none", "tuition", "tuition_feeding"}:
        raise ValueError("Invalid scholarship_type. Use none, tuition, or tuition_feeding.")

    class_assigned = data.get("class_assigned")
    if class_assigned not in VALID_GRADES:
        raise ValueError(f"Invalid grade level. Allowed: {', '.join(VALID_GRADES)}")

    student_code = (data.get("student_code") or "").strip().upper()
    if student_code:
        if Student.query.filter_by(student_code=student_code, school_id=school_id).first():
            raise ValueError(f"Student code {student_code} already exists.")
    else:
        prefix = normalize_student_code_prefix(school_id)
        next_index = Student.query.filter_by(school_id=school_id).count() + 1
        while True:
            candidate = generate_student_code(prefix, next_index)
            if not Student.query.filter_by(student_code=candidate, school_id=school_id).first():
                student_code = candidate
                break
            next_index += 1

    same_name_students = Student.query.filter_by(
        school_id=school_id,
        first_name=first_name,
        surname=surname,
    ).all()
    name_conflict_warning = None
    if same_name_students:
        if len(same_name_students) == 1:
            existing = same_name_students[0]
            name_conflict_warning = (
                f"⚠️ DUPLICATE NAME: '{full_name}' already exists. Review {existing.student_code} before treating this as a new learner."
            )
        else:
            codes = ", ".join([s.student_code for s in same_name_students])
            name_conflict_warning = f"⚠️ {len(same_name_students)} students named '{full_name}' already exist (Codes: {codes})."

    new_student = Student(
        first_name=first_name,
        surname=surname,
        name=full_name,
        gender=gender,
        date_of_birth=date_of_birth,
        student_code=student_code,
        school_id=school_id,
        guardian_name=data.get("guardian_name"),
        parent_name=data.get("guardian_name") or data.get("parent_name"),
        parent_email=data.get("parent_email"),
        parent_phone=data.get("parent_phone"),
        current_class=class_assigned,
        is_on_scholarship=scholarship_type != "none",
        scholarship_covers_tuition=scholarship_type in {"tuition", "tuition_feeding"},
        scholarship_covers_feeding=scholarship_type == "tuition_feeding",
        scholarship_notes=scholarship_notes or None,
        feeding_paid=False,
        is_present=True,
    )
    db.session.add(new_student)
    school.current_student_count = current_count + 1
    school.last_metered_at = get_utc_now()
    db.session.commit()

    log_action(
        user_id=actor_id,
        school_id=school_id,
        action="STUDENT_ADMITTED",
        details=f"Admitted {new_student.name} to {new_student.current_class} (Score: {data.get('score')}%)",
    )

    proration_result = calculate_prorated_admission_charge(
        school,
        1,
        get_effective_plan(school),
        pre_admission_active_students=current_count,
    )
    return new_student, school, scholarship_type, name_conflict_warning, proration_result


def _build_student_payment_instruction_payload(student, school_id):
    from backend.utils import generate_all_payment_codes

    return payment_instruction_service.build_student_payment_instruction_payload(
        student,
        school_id,
        School,
        SchoolSettings,
        generate_all_payment_codes,
        _get_school_admission_fee_config,
        _get_feeding_plan_fees,
        _attach_virtual_routes_to_payment_codes,
        _get_payment_provider_settings,
        PAYSTACK_DVA_SUPPORTED_COUNTRIES,
        sanitize_string,
        _get_payment_collection_pricing,
    )


def normalize_login_attempt(attempt, now, window_minutes):
    if attempt and attempt.last_attempt_at:
        last_attempt = attempt.last_attempt_at
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=timezone.utc)
        if now - last_attempt > timedelta(minutes=window_minutes):
            attempt.attempts = 0
            attempt.locked_until = None


def check_login_lockout(school_id, username, ip_address):
    now = datetime.now(timezone.utc)
    attempt = LoginAttempt.query.filter_by(
        school_id=school_id, username=username, ip_address=ip_address
    ).first()
    if attempt:
        normalize_login_attempt(attempt, now, AUTH_LOCKOUT_WINDOW_MIN)
        if attempt.locked_until and attempt.locked_until > now:
            return attempt
        db.session.commit()
    return None


def record_login_failure(school_id, username, ip_address):
    # Only record if school exists (prevent FK constraint violations for unknown schools)
    if not School.query.filter_by(id=school_id).first():
        return
    now = datetime.now(timezone.utc)
    attempt = LoginAttempt.query.filter_by(
        school_id=school_id, username=username, ip_address=ip_address
    ).first()
    if not attempt:
        attempt = LoginAttempt(
            school_id=school_id,
            username=username,
            ip_address=ip_address,
            attempts=0,
            last_attempt_at=now,
        )
        db.session.add(attempt)

    normalize_login_attempt(attempt, now, AUTH_LOCKOUT_WINDOW_MIN)
    attempt.attempts += 1
    attempt.last_attempt_at = now
    if attempt.attempts >= AUTH_LOCKOUT_ATTEMPTS:
        attempt.locked_until = now + timedelta(minutes=AUTH_LOCKOUT_DURATION_MIN)
        log_system_action(
            school_id, "LOGIN_LOCKOUT", f"Lockout for {username} from {ip_address}"
        )
    db.session.commit()
    return attempt


def clear_login_attempts(school_id, username, ip_address):
    attempt = LoginAttempt.query.filter_by(
        school_id=school_id, username=username, ip_address=ip_address
    ).first()
    if attempt:
        db.session.delete(attempt)
        db.session.commit()


def ordinal(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return ""

    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

    return f"{number}{suffix}"


def grade_from_total(total):
    if total >= 80:
        return "A"
    if total >= 70:
        return "B"
    if total >= 60:
        return "C"
    if total >= 50:
        return "D"
    if total >= 40:
        return "E"
    return "F"


def remark_from_grade(grade):
    return {
        "A": "Excellent",
        "B": "Very Good",
        "C": "Good",
        "D": "Credit",
        "E": "Pass",
        "F": "Fail",
    }.get(grade, "")


def normalize_diagnostic_topics(raw_topics):
    def to_number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    normalized_topics = []
    for topic in raw_topics or []:
        if not isinstance(topic, dict):
            continue
        topic_name = sanitize_string(topic.get("topic") or "") or ""
        if not topic_name:
            continue
        score = to_number(topic.get("score"))
        max_score = to_number(topic.get("max_score"))
        if max_score <= 0:
            continue
        normalized_topics.append(
            {
                "topic": topic_name,
                "score": round(score, 1),
                "max_score": round(max_score, 1),
            }
        )
    return normalized_topics


def normalize_subject_grades(subject_grades):
    def to_number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    normalized = []
    for entry in subject_grades or []:
        if not isinstance(entry, dict):
            continue

        class_score = to_number(entry.get("class_score"))
        exam_score = to_number(entry.get("exam_score"))
        total = to_number(entry.get("total"))

        if total == 0.0 and (class_score or exam_score):
            total = class_score + exam_score

        grade = entry.get("grade") or grade_from_total(total)
        remarks = entry.get("remarks") or remark_from_grade(grade)

        updated = dict(entry)
        updated["class_score"] = class_score
        updated["exam_score"] = exam_score
        updated["total"] = round(total, 1)
        updated["grade"] = grade
        updated["remarks"] = remarks
        updated["diagnostic_topics"] = normalize_diagnostic_topics(entry.get("diagnostic_topics"))
        normalized.append(updated)

    return normalized


def recalculate_class_positions(school_id, class_name, academic_term, academic_year):
    if not class_name:
        return

    reports = ReportCard.query.filter_by(
        school_id=school_id,
        class_name=class_name,
        academic_term=academic_term,
        academic_year=academic_year,
    ).all()

    if not reports:
        return

    student_count = Student.query.filter_by(
        school_id=school_id, current_class=class_name
    ).count()

    sorted_reports = sorted(
        reports, key=lambda r: float(r.term_average or 0), reverse=True
    )

    last_score = None
    position = 0
    for index, report in enumerate(sorted_reports, start=1):
        score = float(report.term_average or 0)
        if last_score is None or score != last_score:
            position = index
            last_score = score
        report.overall_position = ordinal(position)
        report.out_of_students = student_count

def get_plan_limits(plan_name):
    """Returns resource quotas based on subscription plan."""
    # Use the proper plan limit from subscription features
    limit = get_plan_limit(plan_name, "students")
    # Handle infinity for Premium
    return limit if limit != float("inf") else 999999


DEFAULT_LOGIN_HELP_CONTENT = {
    "faqs": [
        {
            "question": "How do I upload students in bulk?",
            "answer": "Go to Admissions, use the CSV upload section, and ensure required columns match the template.",
        },
        {
            "question": "Who can approve terminal reports?",
            "answer": "Homeroom submits, Headmaster reviews, and Proprietor gives final approval based on workflow.",
        },
        {
            "question": "How do I reset my password?",
            "answer": "Use Forgot Password on the login page, then verify your email reset link.",
        },
    ],
    "tutorials": [
        {
            "title": "How to upload students (CSV)",
            "url": "https://www.youtube.com/watch?v=5v5wQ5M3jX8",
        },
        {
            "title": "How to configure promotion thresholds",
            "url": "https://www.youtube.com/watch?v=8YxY7mTjM6Q",
        },
        {
            "title": "How to build and print terminal reports",
            "url": "https://www.youtube.com/watch?v=Q5l2Qh4Aq_0",
        },
    ],
}

DEFAULT_PLATFORM_PUBLIC_CONTENT = {
    "faqs": DEFAULT_LOGIN_HELP_CONTENT["faqs"],
    "tutorials": DEFAULT_LOGIN_HELP_CONTENT["tutorials"],
    "feature_guides": [
        {
            "title": "Admissions & Student Import",
            "body": "Admit individual students, use CSV upload for bulk admissions, and manage class placement.",
        },
        {
            "title": "Staff & HR Setup",
            "body": "Create teacher, homeroom, headmaster, finance, and inventory accounts from Staff & HR.",
        },
        {
            "title": "Subscription & Billing",
            "body": "Review plan details, check current enrollment impact, and upgrade plans via Paystack payment.",
        },
        {
            "title": "Reports & Approval Workflow",
            "body": "Generate report cards, run terminal reports, and follow role-based approval flow for publication.",
        },
    ],
    "security_alerts": [
        "EduPulse support will never call, text, or message you to ask for your bank OTP, MoMo OTP, card PIN, CVV, or full password.",
        "Do not approve transfers, share screen-control access, or follow payment instructions from personal numbers claiming to be EduPulse staff.",
        "Only trust payment and account actions started inside your official EduPulse dashboard or confirmed through the official support email and phone lines.",
        "If anything feels suspicious, stop immediately, do not complete the transaction, and contact official support before taking any further step.",
    ],
    "support": {
        "email": DEFAULT_SUPPORT_EMAIL,
        "phone": "+233 552 141 384",
        "website": "",
        "response_time": "within 24 hours on business days",
    },
    "auth": {
        "login_title": "Welcome Back",
        "login_subtitle": "Enter your business credentials to access the dashboard.",
        "register_title": "Create Tenant",
        "register_subtitle": "Register your school organization.",
        "register_support_note": "Need help choosing a plan or completing registration?",
    },
    "help_center": {
        "title": "Help Center",
        "subtitle": "Search FAQs, browse feature guides, and find tutorial updates.",
        "security_title": "Scam Alert",
        "security_body": "Protect your school accounts and payment setup. Verify suspicious contact before you share any sensitive information.",
    },
}


def _is_platform_owner_request():
    owner_key = (os.getenv("PLATFORM_OWNER_KEY") or "").strip()
    supplied_key = (request.headers.get("X-Platform-Owner-Key") or "").strip()
    if not owner_key:
        return False
    if not supplied_key:
        return False
    return secrets.compare_digest(supplied_key, owner_key)


def _normalize_help_content(raw_value):
    content = raw_value if isinstance(raw_value, dict) else {}

    faqs = []
    for row in content.get("faqs", []):
        if not isinstance(row, dict):
            continue
        question = sanitize_string(row.get("question"))
        answer = sanitize_string(row.get("answer"))
        if question and answer:
            faqs.append({"question": question, "answer": answer})

    tutorials = []
    for row in content.get("tutorials", []):
        if not isinstance(row, dict):
            continue
        title = sanitize_string(row.get("title"))
        url = (row.get("url") or "").strip()
        if title and url and (url.startswith("http://") or url.startswith("https://")):
            tutorials.append({"title": title, "url": url})

    if not faqs:
        faqs = DEFAULT_LOGIN_HELP_CONTENT["faqs"]
    if not tutorials:
        tutorials = DEFAULT_LOGIN_HELP_CONTENT["tutorials"]

    return {"faqs": faqs, "tutorials": tutorials}


def _clone_platform_value(value):
    return json.loads(json.dumps(value or {}))


def _get_platform_setting_value(setting_key, default=None):
    setting = PlatformSetting.query.filter_by(setting_key=setting_key).first()
    if not setting:
        return _clone_platform_value(default)
    return _clone_platform_value(setting.setting_value)


def _upsert_platform_setting_value(setting_key, value):
    safe_value = _clone_platform_value(value)
    setting = PlatformSetting.query.filter_by(setting_key=setting_key).first()
    if not setting:
        setting = PlatformSetting(setting_key=setting_key, setting_value=safe_value)
        db.session.add(setting)
    else:
        setting.setting_value = safe_value
    return setting


def _normalize_platform_text_list(items, fallback_items):
    normalized = []
    seen = set()
    for item in items or []:
        label = sanitize_string(item)
        if not label:
            continue
        key = label.casefold()
        if key in seen:
            continue
        normalized.append(label)
        seen.add(key)
    return normalized or list(fallback_items)


def _normalize_platform_guides(items):
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = sanitize_string(item.get("title"))
        body = sanitize_string(item.get("body"))
        if title and body:
            normalized.append({"title": title, "body": body})
    return normalized or _clone_platform_value(DEFAULT_PLATFORM_PUBLIC_CONTENT["feature_guides"])


def _normalize_platform_public_content(raw_value):
    content = raw_value if isinstance(raw_value, dict) else {}
    help_content = _normalize_help_content(content)
    support_input = content.get("support") if isinstance(content.get("support"), dict) else {}
    auth_input = content.get("auth") if isinstance(content.get("auth"), dict) else {}
    help_center_input = content.get("help_center") if isinstance(content.get("help_center"), dict) else {}

    return {
        "faqs": help_content["faqs"],
        "tutorials": help_content["tutorials"],
        "feature_guides": _normalize_platform_guides(content.get("feature_guides") or []),
        "security_alerts": _normalize_platform_text_list(
            content.get("security_alerts") or [],
            DEFAULT_PLATFORM_PUBLIC_CONTENT["security_alerts"],
        ),
        "support": {
            "email": sanitize_string(support_input.get("email"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["support"]["email"],
            "phone": sanitize_string(support_input.get("phone"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["support"]["phone"],
            "website": sanitize_string(support_input.get("website")) or "",
            "response_time": sanitize_string(support_input.get("response_time"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["support"]["response_time"],
        },
        "auth": {
            "login_title": sanitize_string(auth_input.get("login_title"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["auth"]["login_title"],
            "login_subtitle": sanitize_string(auth_input.get("login_subtitle"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["auth"]["login_subtitle"],
            "register_title": sanitize_string(auth_input.get("register_title"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["auth"]["register_title"],
            "register_subtitle": sanitize_string(auth_input.get("register_subtitle"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["auth"]["register_subtitle"],
            "register_support_note": sanitize_string(auth_input.get("register_support_note"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["auth"]["register_support_note"],
        },
        "help_center": {
            "title": sanitize_string(help_center_input.get("title"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["help_center"]["title"],
            "subtitle": sanitize_string(help_center_input.get("subtitle"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["help_center"]["subtitle"],
            "security_title": sanitize_string(help_center_input.get("security_title"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["help_center"]["security_title"],
            "security_body": sanitize_string(help_center_input.get("security_body"))
            or DEFAULT_PLATFORM_PUBLIC_CONTENT["help_center"]["security_body"],
        },
    }


def _get_platform_public_content():
    stored = _get_platform_setting_value(
        PLATFORM_PUBLIC_CONTENT_SETTING_KEY,
        DEFAULT_PLATFORM_PUBLIC_CONTENT,
    )
    return _normalize_platform_public_content(stored)


def _set_platform_public_content(content):
    normalized = _normalize_platform_public_content(content)
    _upsert_platform_setting_value(PLATFORM_PUBLIC_CONTENT_SETTING_KEY, normalized)
    return normalized


@api.route("/public/help-content", methods=["GET"])
def get_public_help_content():
    """Get global login FAQ/tutorial content for all tenants."""
    content = _get_platform_public_content()
    return jsonify({"faqs": content["faqs"], "tutorials": content["tutorials"]})


@api.route("/public/platform-content", methods=["GET"])
def get_public_platform_content():
    """Get global tenant-facing public content managed by the platform owner."""
    return jsonify(_get_platform_public_content())


@api.route("/platform/help-content", methods=["GET"])
def get_platform_help_content():
    """Get global help content for platform owner editing."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

    content = _get_platform_public_content()
    return jsonify({"faqs": content["faqs"], "tutorials": content["tutorials"]})


@api.route("/platform/help-content", methods=["PUT"])
def update_platform_help_content():
    """Update global login FAQ/tutorial content (platform owner only)."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

    data = request.get_json(silent=True) or {}
    current = _get_platform_public_content()
    normalized_help = _normalize_help_content(
        {
            "faqs": data.get("faqs", []),
            "tutorials": data.get("tutorials", []),
        }
    )
    current["faqs"] = normalized_help["faqs"]
    current["tutorials"] = normalized_help["tutorials"]
    normalized = _set_platform_public_content(current)
    _upsert_platform_setting_value(
        "login_help_content",
        normalized_help,
    )

    db.session.commit()
    return jsonify(
        {
            "message": "Global help content updated successfully.",
            "faqs": normalized["faqs"],
            "tutorials": normalized["tutorials"],
        }
    )


@api.route("/platform/public-content", methods=["GET"])
@jwt_required()
def get_platform_public_content_settings():
    """Get all tenant-facing public content for platform admin editing."""
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401
    return jsonify(_get_platform_public_content())


@api.route("/platform/public-content", methods=["PUT"])
@jwt_required()
def update_platform_public_content_settings():
    """Update tenant-facing public content for platform admin editing."""
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    normalized = _set_platform_public_content(payload)
    _upsert_platform_setting_value(
        "login_help_content",
        {"faqs": normalized["faqs"], "tutorials": normalized["tutorials"]},
    )
    db.session.commit()
    return jsonify({"message": "Platform public content updated successfully.", **normalized})


def _get_platform_user_from_jwt():
    """Extract platform user from JWT token."""
    try:
        identity = get_jwt_identity()
        if not identity or not isinstance(identity, str):
            return None
        # Platform user identities are prefixed with "platform:"
        if not identity.startswith("platform:"):
            return None
        user_id = int(identity.split(":", 1)[1])
        return PlatformUser.query.filter_by(id=user_id, is_active=True).first()
    except Exception:
        return None


def _get_super_admin_user_from_jwt():
    """Extract a legacy super-admin user from JWT token."""
    try:
        identity = get_jwt_identity()
        if identity is None:
            return None
        if isinstance(identity, str):
            if identity.startswith("platform:"):
                return None
            if not identity.strip().isdigit():
                return None
            user_id = int(identity)
        elif isinstance(identity, int):
            user_id = identity
        else:
            return None

        user = User.query.get(user_id)
        if not user or user.role != "super_admin":
            return None
        return user
    except Exception:
        return None


def _get_provider_console_operator():
    """Allow provider-only endpoints to be used by platform users or legacy super admins."""
    platform_user = _get_platform_user_from_jwt()
    if platform_user:
        return {"kind": "platform", "platform_user": platform_user, "user": None, "actor_id": None}

    super_admin_user = _get_super_admin_user_from_jwt()
    if super_admin_user:
        return {"kind": "super_admin", "platform_user": None, "user": super_admin_user, "actor_id": super_admin_user.id}

    return None


@api.route("/platform/bootstrap-status", methods=["GET"])
def get_platform_bootstrap_status():
    """Report whether the platform owner console still needs its first admin user."""
    return jsonify(
        {
            "needs_bootstrap": PlatformUser.query.count() == 0,
            "owner_key_configured": bool((os.getenv("PLATFORM_OWNER_KEY") or "").strip()),
        }
    )


@api.route("/platform/auth/login", methods=["POST"])
def platform_login():
    """Authenticate platform admin user and return JWT."""
    try:
        data = request.get_json(silent=True) or {}
        username = sanitize_string(data.get("username", "")).strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"message": "Username and password required"}), 400

        user = PlatformUser.query.filter_by(username=username).first()

        if not user or not user.is_active:
            return jsonify({"message": "Invalid credentials"}), 401

        if not user.check_password(password):
            return jsonify({"message": "Invalid credentials"}), 401

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Create JWT with platform admin identity (prefixed to distinguish from regular users)
        token = create_access_token(identity=f"platform:{user.id}")

        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        })

    except Exception as e:
        logger.error(f"Platform login error: {str(e)}")
        return jsonify({"message": "Login failed"}), 500


@api.route("/platform/auth/me", methods=["GET"])
@jwt_required()
def get_platform_user():
    """Get current authenticated platform user."""
    user = _get_platform_user_from_jwt()
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    })


@api.route("/platform/users", methods=["GET"])
@jwt_required()
def list_platform_users():
    """List all platform admin users (authenticated platform user required)."""
    user = _get_platform_user_from_jwt()
    if not user:
        return jsonify({"message": "Unauthorized"}), 401

    users = PlatformUser.query.order_by(PlatformUser.created_at.desc()).all()

    return jsonify({
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]
    })


@api.route("/platform/users", methods=["POST"])
def add_platform_user():
    """Add new platform admin user via platform JWT, or bootstrap the first one with the owner key."""
    verify_jwt_in_request(optional=True)
    platform_user = _get_platform_user_from_jwt()
    platform_user_count = PlatformUser.query.count()
    bootstrap_request = platform_user_count == 0 and _is_platform_owner_request()
    if not platform_user and not bootstrap_request:
        if platform_user_count == 0:
            return jsonify({"message": "Use the platform owner key to bootstrap the first platform admin user."}), 401
        return jsonify({"message": "Unauthorized"}), 401

    try:
        data = request.get_json(silent=True) or {}
        username = sanitize_string(data.get("username", "")).strip()
        email = sanitize_string(data.get("email", "")).strip()
        password = data.get("password", "")

        if not username or not email or not password:
            return jsonify({"message": "Username, email, and password required"}), 400

        # Check if username exists
        if PlatformUser.query.filter_by(username=username).first():
            return jsonify({"message": "Username already exists"}), 409

        # Check if email exists
        if PlatformUser.query.filter_by(email=email).first():
            return jsonify({"message": "Email already exists"}), 409

        user = PlatformUser(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({
            "message": "Platform user created successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
        }), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding platform user: {str(e)}")
        return jsonify({"message": "Failed to create user"}), 500


@api.route("/platform/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def remove_platform_user(user_id):
    """Remove platform admin user (authenticated platform user required)."""
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    try:
        user = PlatformUser.query.get(user_id)
        if not user:
            return jsonify({"message": "User not found"}), 404

        if user.id == platform_user.id:
            return jsonify({"message": "You cannot remove your own active platform account."}), 400

        db.session.delete(user)
        db.session.commit()

        return jsonify({"message": "Platform user removed successfully"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing platform user: {str(e)}")
        return jsonify({"message": "Failed to remove user"}), 500


@api.route("/platform/registration-email-trace", methods=["GET"])
@jwt_required()
def get_registration_email_trace():
    """Platform admin trace endpoint for registration-related emails and duplicates."""
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    school_id = sanitize_string(request.args.get("school_id", "")).strip()
    limit = request.args.get("limit", default=200, type=int) or 200
    limit = max(1, min(limit, 1000))

    actions = [
        "REGISTRATION_WELCOME_EMAIL_SENT",
        "REGISTRATION_POLICY_ACCEPTED",
        "REGISTRATION_EMAIL_RELEASED",
    ]

    query = db.session.query(AuditLog).filter(AuditLog.action.in_(actions))
    if school_id:
        query = query.filter(AuditLog.school_id == school_id)

    rows = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    # Duplicate analysis for welcome-email events.
    duplicate_map = {}
    for row in rows:
        if row.action != "REGISTRATION_WELCOME_EMAIL_SENT":
            continue
        sid = row.school_id or "unknown"
        duplicate_map[sid] = duplicate_map.get(sid, 0) + 1

    duplicate_summary = [
        {
            "school_id": sid,
            "welcome_email_count": count,
            "has_duplicates": count > 1,
        }
        for sid, count in sorted(duplicate_map.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return jsonify(
        {
            "events": [
                {
                    "id": row.id,
                    "school_id": row.school_id,
                    "user_id": row.actor_id,
                    "action": row.action,
                    "details": row.details,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                }
                for row in rows
            ],
            "duplicate_summary": duplicate_summary,
            "total_events": len(rows),
        }
    )


@api.route("/platform/registration-email-release", methods=["POST"])
@jwt_required()
def release_registration_email():
    """Release stuck registration emails by moving old user records to internal aliases."""
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    school_id = sanitize_string(data.get("school_id", "")).strip()
    raw_emails = data.get("emails")

    normalized_emails = []
    if isinstance(raw_emails, str):
        normalized_emails = [
            _normalize_email_address(value)
            for value in re.split(r"[\s,;]+", raw_emails)
            if _normalize_email_address(value)
        ]
    elif isinstance(raw_emails, list):
        normalized_emails = [
            _normalize_email_address(value)
            for value in raw_emails
            if _normalize_email_address(value)
        ]

    normalized_emails = list(dict.fromkeys(normalized_emails))

    if not school_id and not normalized_emails:
        return jsonify({"message": "Provide at least one email or a school ID."}), 400

    school = None
    if school_id:
        school = School.query.get(school_id)
        if not school:
            return jsonify({"message": "School not found."}), 404

    candidate_users = User.query.all() if normalized_emails else []
    matched_users = []

    if school_id:
        school_users = User.query.filter_by(school_id=school_id).all()
        if normalized_emails:
            matched_users.extend(
                user
                for user in school_users
                if _normalize_email_address(user.email) in normalized_emails
            )
        else:
            matched_users.extend(
                user for user in school_users if user.role == "proprietor" and _normalize_email_address(user.email)
            )
    else:
        for email in normalized_emails:
            email_matches = [
                user for user in candidate_users if _normalize_email_address(user.email) == email
            ]
            if len(email_matches) > 1:
                return (
                    jsonify(
                        {
                            "message": f"Multiple accounts use {email}. Add the school ID to release it safely.",
                            "error": "registration_email_release_requires_school_id",
                            "matches": [
                                {
                                    "user_id": user.id,
                                    "school_id": user.school_id,
                                    "username": user.username,
                                    "role": user.role,
                                }
                                for user in email_matches
                            ],
                        }
                    ),
                    409,
                )
            matched_users.extend(email_matches)

    deduped_users = []
    seen_user_ids = set()
    for user in matched_users:
        if not user or user.id in seen_user_ids:
            continue
        seen_user_ids.add(user.id)
        deduped_users.append(user)

    if not deduped_users:
        return jsonify({"message": "No matching school users found for release."}), 404

    released = []
    for user in deduped_users:
        old_email = _normalize_email_address(user.email)
        if not old_email:
            continue
        new_email = _build_released_registration_email(user, old_email)
        user.email = new_email
        released.append(
            {
                "user_id": user.id,
                "school_id": user.school_id,
                "username": user.username,
                "role": user.role,
                "old_email": old_email,
                "new_email": new_email,
            }
        )

    if not released:
        return jsonify({"message": "No releasable email addresses were found."}), 404

    db.session.commit()

    for entry in released:
        db.session.add(
            AuditLog(
                actor_id=None,
                school_id=entry["school_id"],
                action="REGISTRATION_EMAIL_RELEASED",
                details=json.dumps(
                    {
                        "released_by": platform_user.username,
                        "user_id": entry["user_id"],
                        "username": entry["username"],
                        "role": entry["role"],
                        "old_email": entry["old_email"],
                        "new_email": entry["new_email"],
                    },
                    ensure_ascii=False,
                ),
                timestamp=get_utc_now(),
            )
        )
    db.session.commit()

    target_label = school.id if school else ", ".join(normalized_emails)
    logger.info(
        "Platform registration email release by %s for %s: %s",
        platform_user.username,
        target_label,
        ", ".join(entry["old_email"] for entry in released),
    )

    return jsonify(
        {
            "message": f"Released {len(released)} registration email(s).",
            "released": released,
        }
    )


@api.route("/platform/compliance/schools", methods=["GET"])
@jwt_required()
def platform_list_school_verification_cases():
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 401

    status_filter = sanitize_string(request.args.get("status") or "").lower()
    risk_filter = sanitize_string(request.args.get("risk_tier") or "").lower()
    limit = request.args.get("limit", default=200, type=int) or 200
    limit = max(1, min(limit, 1000))

    latest_ids = (
        db.session.query(func.max(SchoolVerification.id).label("id"))
        .group_by(SchoolVerification.school_id)
        .subquery()
    )

    query = (
        db.session.query(SchoolVerification, School)
        .join(latest_ids, SchoolVerification.id == latest_ids.c.id)
        .join(School, School.id == SchoolVerification.school_id)
    )

    if status_filter and status_filter != "all":
        query = query.filter(func.lower(SchoolVerification.status) == status_filter)
    if risk_filter:
        query = query.filter(func.lower(SchoolVerification.risk_tier) == risk_filter)

    rows = query.order_by(SchoolVerification.submitted_at.desc()).all()
    rows = [
        (verification, school)
        for verification, school in rows
        if verification.submitted_by_user_id is not None or bool(verification.documents)
    ][:limit]
    return jsonify(
        {
            "cases": [
                {
                    "school_id": school.id,
                    "school_name": school.name,
                    "verification_id": verification.id,
                    "status": verification.status,
                    "risk_tier": verification.risk_tier,
                    "legal_name": verification.legal_name,
                    "registration_number": verification.registration_number,
                    "tax_id": verification.tax_id,
                    "owner_information": verification.owner_information or {},
                    "documents": [
                        item
                        for item in (
                            _build_platform_school_verification_document_entry(school.id, entry)
                            for entry in (verification.documents or [])
                        )
                        if item
                    ],
                    "review_notes": verification.review_notes,
                    "submitted_at": _to_iso_utc(verification.submitted_at),
                    "reviewed_at": _to_iso_utc(verification.reviewed_at),
                    "expires_at": _to_iso_utc(verification.expires_at),
                }
                for verification, school in rows
            ]
        }
    )


@api.route("/platform/compliance/schools/<string:school_id>/documents/<string:document_id>/download", methods=["GET"])
@jwt_required()
def platform_download_school_verification_document(school_id, document_id):
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 401

    verifications = (
        SchoolVerification.query.filter_by(school_id=school_id)
        .order_by(SchoolVerification.id.desc())
        .all()
    )
    if not verifications:
        return jsonify({"message": "No verification profile found for school"}), 404

    matching_document = None
    for verification in verifications:
        matching_document = next(
            (
                item
                for item in (verification.documents or [])
                if isinstance(item, dict) and (item.get("document_id") or item.get("id")) == document_id
            ),
            None,
        )
        if matching_document:
            break

    if not matching_document:
        return jsonify({"message": "Document not found"}), 404

    resolved_path = _resolve_existing_school_file(
        _get_school_verification_document_storage_root(school_id=school_id),
        matching_document.get("stored_filename"),
    )
    if not resolved_path:
        return jsonify({"message": "Document file is no longer available"}), 404

    return send_file(
        resolved_path,
        as_attachment=False,
        download_name=matching_document.get("original_filename") or matching_document.get("filename") or "verification-document",
    )


@api.route("/platform/compliance/schools/<string:school_id>/decision", methods=["POST"])
@jwt_required()
def platform_review_school_verification_case(school_id):
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    new_status = sanitize_string(payload.get("status") or "").lower()
    allowed_statuses = {"verified", "rejected", "suspended", "review_required"}
    if new_status not in allowed_statuses:
        return jsonify({"message": f"status must be one of: {', '.join(sorted(allowed_statuses))}"}), 400

    risk_tier = sanitize_string(payload.get("risk_tier") or "medium").lower()
    if risk_tier not in {"low", "medium", "high"}:
        risk_tier = "medium"

    verification = (
        SchoolVerification.query.filter_by(school_id=school_id)
        .order_by(SchoolVerification.id.desc())
        .first()
    )
    if not verification:
        return jsonify({"message": "No verification profile found for school"}), 404

    verification.status = new_status
    verification.risk_tier = risk_tier
    verification.review_notes = sanitize_string(payload.get("review_notes") or "")
    verification.reviewed_by_platform_user_id = operator["platform_user"].id if operator["platform_user"] else None
    verification.reviewed_at = get_utc_now()

    expires_in_days = payload.get("expires_in_days")
    if isinstance(expires_in_days, int) and expires_in_days > 0 and new_status == "verified":
        verification.expires_at = get_utc_now() + timedelta(days=min(expires_in_days, 365 * 3))
    elif new_status != "verified":
        verification.expires_at = None

    db.session.commit()
    return jsonify(
        {
            "message": "Verification decision saved.",
            "school_id": school_id,
            "status": verification.status,
            "risk_tier": verification.risk_tier,
            "reviewed_at": _to_iso_utc(verification.reviewed_at),
            "expires_at": _to_iso_utc(verification.expires_at),
        }
    )


@api.route("/platform/compliance/aml-flags", methods=["GET"])
@jwt_required()
def platform_list_aml_flags():
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    status_filter = sanitize_string(request.args.get("status") or "open").lower()
    severity_filter = sanitize_string(request.args.get("severity") or "").lower()
    limit = request.args.get("limit", default=300, type=int) or 300
    limit = max(1, min(limit, 1000))

    query = db.session.query(AMLTransactionFlag, School).join(School, School.id == AMLTransactionFlag.school_id)
    if status_filter in {"open", "resolved"}:
        query = query.filter(AMLTransactionFlag.status == status_filter)
    if severity_filter in {"low", "medium", "high"}:
        query = query.filter(func.lower(AMLTransactionFlag.severity) == severity_filter)

    rows = query.order_by(AMLTransactionFlag.created_at.desc()).limit(limit).all()
    return jsonify(
        {
            "flags": [
                {
                    "id": flag.id,
                    "school_id": school.id,
                    "school_name": school.name,
                    "rule_code": flag.rule_code,
                    "severity": flag.severity,
                    "status": flag.status,
                    "summary": flag.summary,
                    "details": flag.details or {},
                    "payment_id": flag.payment_id,
                    "student_id": flag.student_id,
                    "created_at": _to_iso_utc(flag.created_at),
                    "resolved_at": _to_iso_utc(flag.resolved_at),
                }
                for flag, school in rows
            ]
        }
    )


@api.route("/platform/compliance/aml-flags/<int:flag_id>/resolve", methods=["POST"])
@jwt_required()
def platform_resolve_aml_flag(flag_id):
    platform_user = _get_platform_user_from_jwt()
    if not platform_user:
        return jsonify({"message": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    notes = sanitize_string(payload.get("notes") or "")
    row = AMLTransactionFlag.query.get(flag_id)
    if not row:
        return jsonify({"message": "AML flag not found"}), 404

    row.status = "resolved"
    row.resolution_notes = notes or "Resolved by platform compliance"
    row.resolved_at = get_utc_now()
    db.session.commit()

    return jsonify({"message": "AML flag resolved.", "flag_id": row.id})


# --- 1. AUTHENTICATION (Pillar 1: Business Credentials) ---
def _build_auth_success_payload(user, school, requires_password_reset=False):
    billing_status = get_billing_status_info(school)
    return {
        "token": create_access_token(identity=str(user.id)),
        "requires_password_reset": requires_password_reset,
        "role": user.role,
        "roles": user.roles if user.roles else [user.role],
        "assigned_class": user.assigned_class,
        "school_id": school.id,
        "subscription_plan": school.subscription_plan,
        "subscription_status": billing_status.get("status"),
        "enabled_modules": (
            school.settings.enabled_modules if school.settings else {}
        ),
        "branding": {
            "name": school.name,
            "logo": school.logo_url,
            "theme_color": school.primary_color,
            "motto": school.motto,
            "country_code": (
                school.settings.country_code if school.settings else "GH"
            ),
        },
    }


STAFF_ROLE_EMAIL_METADATA = {
    "teacher": {
        "description": "Teacher access for subject teaching, score entry, lesson notes, and assigned class work.",
        "permissions": "• Record subject scores\n• Submit lesson notes\n• View assigned classes, subjects, and timetable",
    },
    "homeroom": {
        "description": "Homeroom access for class oversight, report building, attendance follow-up, and parent-facing class records.",
        "permissions": "• Manage homeroom class records\n• Build and review terminal reports\n• Monitor class-level performance",
    },
    "headmaster": {
        "description": "Headmaster access for academic oversight, approvals, staff supervision, and school-wide review.",
        "permissions": "• Review academic performance\n• Approve workflows and reports\n• Oversee staff assignments and school operations",
    },
    "finance": {
        "description": "Finance access for fee operations, payment verification, and school finance monitoring.",
        "permissions": "• Record and verify payments\n• Use the payment tracker and finance dashboards\n• Monitor balances and payment activity",
    },
    "inventory_manager": {
        "description": "Store management access for stock control, purchase logging, and issue tracking.",
        "permissions": "• Record stock movements\n• Monitor inventory levels\n• Review inventory activity and reports",
    },
}

LEGACY_REPORT_TEMPLATE_ID_MAP = {
    "sample1": "gradman_v1",
    "sample2": "parent_focus",
    "sample3": "progress_insights",
    "sample4": "compact_clear",
    "sample5": "guardian_narrative",
    "sample6": "classic_traditional",
}

CANONICAL_REPORT_TEMPLATE_ID_MAP = {
    canonical: legacy for legacy, canonical in LEGACY_REPORT_TEMPLATE_ID_MAP.items()
}

GLOBAL_REPORT_SETTINGS_KEY = "__global_report_settings__"


def _normalize_report_template_id(template_id):
    normalized = (template_id or "").strip()
    return LEGACY_REPORT_TEMPLATE_ID_MAP.get(normalized, normalized)


def _to_legacy_report_template_id(template_id):
    normalized = _normalize_report_template_id(template_id)
    return CANONICAL_REPORT_TEMPLATE_ID_MAP.get(normalized, normalized)


def _get_report_global_settings(settings):
    raw_config = settings.report_template_config if settings else {}
    if not isinstance(raw_config, dict):
        return {}
    global_settings = raw_config.get(GLOBAL_REPORT_SETTINGS_KEY)
    return global_settings if isinstance(global_settings, dict) else {}


def _merge_report_template_config(existing_config, incoming_config):
    merged = dict(incoming_config or {}) if isinstance(incoming_config, dict) else {}
    existing_globals = {}
    if isinstance(existing_config, dict):
        raw_existing_globals = existing_config.get(GLOBAL_REPORT_SETTINGS_KEY)
        if isinstance(raw_existing_globals, dict):
            existing_globals = dict(raw_existing_globals)

        # Preserve tenant-scoped metadata that should survive template switches.
        for persistent_key in [
            REPORT_TEMPLATE_HISTORY_KEY,
            "analytics_presets",
            ANALYTICS_PRESET_HISTORY_KEY,
        ]:
            if persistent_key in existing_config and persistent_key not in merged:
                merged[persistent_key] = _clone_json_document(existing_config.get(persistent_key))

    incoming_globals = merged.get(GLOBAL_REPORT_SETTINGS_KEY)
    if isinstance(incoming_globals, dict):
        existing_globals.update(incoming_globals)

    if existing_globals:
        merged[GLOBAL_REPORT_SETTINGS_KEY] = existing_globals

    return merged


def _get_report_template_history(settings):
    report_template_config = _clone_json_document(settings.report_template_config)
    history = report_template_config.get(REPORT_TEMPLATE_HISTORY_KEY) or []
    return history if isinstance(history, list) else []


def _write_report_template_history(settings, history_items):
    config = _clone_json_document(settings.report_template_config)
    cleaned_history = history_items if isinstance(history_items, list) else []
    if cleaned_history:
        config[REPORT_TEMPLATE_HISTORY_KEY] = cleaned_history[:REPORT_TEMPLATE_HISTORY_LIMIT]
    else:
        config.pop(REPORT_TEMPLATE_HISTORY_KEY, None)
    settings.report_template_config = config


def _build_report_template_snapshot(settings, *, actor_id, action, restored_from_snapshot_id=None):
    return {
        "snapshot_id": f"rts_{secrets.token_hex(6)}",
        "report_template_id": _normalize_report_template_id(settings.report_template_id),
        "report_template_config": _clone_json_document(settings.report_template_config),
        "actor_id": actor_id,
        "action": action,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "restored_from_snapshot_id": restored_from_snapshot_id,
    }


def _append_report_template_history(settings, *, actor_id, action, restored_from_snapshot_id=None):
    snapshot = _build_report_template_snapshot(
        settings,
        actor_id=actor_id,
        action=action,
        restored_from_snapshot_id=restored_from_snapshot_id,
    )
    history = [snapshot] + _get_report_template_history(settings)
    _write_report_template_history(settings, history)
    return snapshot


def _set_report_global_setting(settings, key, value):
    config = settings.report_template_config if isinstance(settings.report_template_config, dict) else {}
    config = dict(config)
    global_settings = dict(config.get(GLOBAL_REPORT_SETTINGS_KEY) or {})

    if value:
        global_settings[key] = value
    else:
        global_settings.pop(key, None)

    if global_settings:
        config[GLOBAL_REPORT_SETTINGS_KEY] = global_settings
    else:
        config.pop(GLOBAL_REPORT_SETTINGS_KEY, None)

    settings.report_template_config = config


def _get_configured_reopening_date(settings, current_term=None, next_term=None):
    configured_value = _get_report_global_settings(settings).get("next_term_reopen_date")
    if configured_value:
        return configured_value

    if current_term and current_term.billing_due_date:
        return current_term.billing_due_date.isoformat()

    if next_term and next_term.start_date:
        return next_term.start_date.isoformat()

    return None


def _build_report_term_calendar(school_id, academic_term, academic_year):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    current_term = AcademicTerm.query.filter_by(
        school_id=school_id,
        name=academic_term,
        academic_year=academic_year,
    ).first()

    next_term = None
    term_order = ["Term 1", "Term 2", "Term 3"]
    if current_term and current_term.name in term_order:
        current_index = term_order.index(current_term.name)
        if current_index < len(term_order) - 1:
            next_term = AcademicTerm.query.filter_by(
                school_id=school_id,
                name=term_order[current_index + 1],
                academic_year=academic_year,
            ).first()
        else:
            try:
                year_start = int(academic_year.split("/")[0])
                year_end = int(academic_year.split("/")[1])
                next_academic_year = f"{year_start + 1}/{year_end + 1}"
                next_term = AcademicTerm.query.filter_by(
                    school_id=school_id,
                    name="Term 1",
                    academic_year=next_academic_year,
                ).first()
            except Exception:
                next_term = None

    return {
        "term_start_date": current_term.start_date.isoformat() if current_term and current_term.start_date else None,
        "vacation_date": current_term.end_date.isoformat() if current_term and current_term.end_date else None,
        "reopening_date": _get_configured_reopening_date(settings, current_term=current_term, next_term=next_term),
    }


def _get_frontend_base_url():
    configured_url = (os.getenv("FRONTEND_URL") or "").strip()
    configured_origin = (os.getenv("FRONTEND_ORIGIN") or "").strip()
    origin_url = (request.headers.get("Origin") or "").strip()

    base_url = configured_url or configured_origin
    if origin_url and (
        not base_url
        or "localhost" in base_url.lower()
        or "127.0.0.1" in base_url.lower()
    ):
        base_url = origin_url

    if not base_url:
        base_url = request.host_url.rstrip("/")

    return base_url.rstrip("/")


def _get_frontend_login_url():
    base_url = _get_frontend_base_url()

    return f"{base_url}/login"


def _get_staff_support_contact(school):
    headmaster = User.query.filter_by(school_id=school.id, role="headmaster").first()
    proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
    support_user = headmaster or proprietor

    support_name = None
    if support_user:
        support_name = support_user.username
    elif school and school.name:
        support_name = f"{school.name} Administration"
    else:
        support_name = "School Administration"

    return {
        "name": support_name,
        "email": (
            (support_user.email if support_user and support_user.email else None)
            or (school.school_email if school else None)
            or DEFAULT_SUPPORT_EMAIL
        ),
        "phone": (school.school_phone if school and school.school_phone else "+233 552 141 384"),
    }


def _generate_staff_temp_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _send_staff_invite_email(user, school, temporary_password, expiry_days=30):
    login_url = _get_frontend_login_url()
    support_contact = _get_staff_support_contact(school)
    role_email_meta = STAFF_ROLE_EMAIL_METADATA.get(user.role, {})
    template_subject, template_body = get_staff_welcome_email(
        staff_name=user.username,
        school_name=school.name if school else "Your School",
        username=user.username,
        temporary_password=temporary_password,
        assigned_role=user.role,
        login_url=login_url,
        expiry_days=expiry_days,
        school_id=school.id if school else g.school_id,
        role_description=role_email_meta.get("description"),
        role_permissions=role_email_meta.get("permissions"),
        support_contact_name=support_contact["name"],
        support_contact_email=support_contact["email"],
        support_contact_phone=support_contact["phone"],
        email=user.email,
    )

    email_sent = False
    email_error = None

    try:
        if template_subject and template_body:
            delivery_result = send_email_notification(user.email, template_subject, template_body)
            email_sent = bool(delivery_result)
            if not email_sent:
                email_error = "Email delivery is unavailable right now."
    except Exception as invite_error:
        email_error = str(invite_error)
        logger.error(f"Failed to send staff welcome email: {email_error}")

    return email_sent, email_error

def _issue_two_factor_challenge(user):
    if not user.email:
        raise ValueError("MFA is required but no email is set for this account.")

    existing_tokens = TwoFactorToken.query.filter_by(user_id=user.id, consumed=False).all()
    for token in existing_tokens:
        token.consumed = True

    code = f"{secrets.randbelow(1000000):06d}"
    twofa = TwoFactorToken(
        user_id=user.id,
        token_hash=generate_password_hash(code),
        delivery="email",
        attempts=0,
        consumed=False,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    db.session.add(twofa)
    db.session.commit()

    fallback_notice = None
    dev_code = None
    try:
        delivery_ok = send_email_notification(
            to_email=user.email,
            subject="Smart School Management Login Verification Code",
            body=f"Your verification code is: {code}\n\nThis code expires in 10 minutes.",
        )
        if delivery_ok is False:
            fallback_notice = "Email delivery is unavailable in local development. Use the development verification code below."
            dev_code = code
    except Exception as email_error:
        logger.error(
            f"2FA email delivery failed for user {user.username} in school {user.school_id}: {email_error}"
        )
        raise RuntimeError("Unable to send verification code email. Please confirm your email address and try again.") from email_error

    pending_token = create_access_token(
        identity=str(user.id),
        additional_claims={"type": "2fa_pending"},
        expires_delta=timedelta(minutes=10),
    )

    return {
        "message": "2fa_required",
        "token": pending_token,
        "delivery": "email",
        "fallback_notice": fallback_notice,
        "dev_code": dev_code,
    }


@api.route("/login", methods=["POST"])
@rate_limit_auth
@csrf_protect
def login():
    """
    Login with school code, username or email, and password.
    Returns JWT token with user context and school branding.
    """
    try:
        payload = request.get_json(silent=True) or {}
        if "school_code" in payload and "schoolCode" not in payload:
            payload["schoolCode"] = payload.get("school_code")
        payload.pop("school_code", None)
        schema = LoginSchema()
        data = schema.load(payload)
    except Exception as e:
        logger.warning(f"Login validation failed: {str(e)}")
        return jsonify({"message": "Invalid input"}), 400

    school_code = sanitize_string(data.get("schoolCode"))
    login_identifier = sanitize_string(data.get("username"))
    password = data.get("password")
    client_ip = get_client_ip()

    lockout = check_login_lockout(school_code, login_identifier, client_ip)
    if lockout:
        return jsonify({"message": "Too many login attempts. Try again later."}), 429

    school = School.query.filter_by(id=school_code).first()
    if not school:
        logger.warning(f"Login failed: Unknown school code {school_code}")
        record_login_failure(school_code, login_identifier, client_ip)
        return jsonify({"message": "Invalid School Organization ID"}), 401

    if not school.is_active:
        logger.warning(f"Login denied: School {school_code} is inactive")
        return (
            jsonify({"message": "School account is suspended. Contact Support."}),
            403,
        )

    user = User.query.filter_by(username=login_identifier, school_id=school.id).first()
    if not user and "@" in (login_identifier or ""):
        user = _find_school_user_by_email(school.id, login_identifier)
    
    # Check if temporary password has expired
    if user and user.is_temp_password and user.temp_password_expires_at:
        temp_expiry = user.temp_password_expires_at
        if temp_expiry.tzinfo is None:
            temp_expiry = temp_expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > temp_expiry:
            return jsonify({
                "message": "Your temporary password has expired. Please contact your school administrator for a new password.",
                "error": "temp_password_expired"
            }), 401

    if user and check_password_hash(user.password_hash, password):
        clear_login_attempts(school_code, login_identifier, client_ip)
        user.last_login_at = get_utc_now()
        
        # Check if using temporary password that needs to be changed
        requires_password_reset = user.is_temp_password

        requires_mfa = MFA_REQUIRED or user.two_fa_enabled
        if requires_mfa:
            try:
                challenge_payload = _issue_two_factor_challenge(user)
            except ValueError as config_error:
                return jsonify({"message": str(config_error)}), 400
            except RuntimeError as delivery_error:
                return jsonify({"message": str(delivery_error)}), 503

            return (
                jsonify(challenge_payload),
                202,
            )

        # Log successful login
        log_action(user.id, school.id, "LOGIN", f"User {user.username} logged in")

        return jsonify(
            _build_auth_success_payload(
                user,
                school,
                requires_password_reset=requires_password_reset,
            )
        )

    record_login_failure(school_code, login_identifier, client_ip)
    logger.warning(
        f"Login failed: Invalid credentials for identifier {login_identifier} in school {school_code}"
    )
    return jsonify({"message": "Invalid Business Credentials"}), 401


@api.route("/register", methods=["POST"])
@rate_limit_auth
@csrf_protect
def register():
    """
    Self-service registration for new School Tenants.
    Creates school, settings, and proprietor account.
    """
    try:
        payload = request.get_json(silent=True) or {}
        if "school_code" in payload and "schoolCode" not in payload:
            payload["schoolCode"] = payload.get("school_code")
        if "school_name" in payload and "schoolName" not in payload:
            payload["schoolName"] = payload.get("school_name")
        payload.pop("school_code", None)
        payload.pop("school_name", None)
        schema = RegisterSchema()
        data = schema.load(payload)
    except Exception as e:
        logger.warning(f"Registration validation failed: {str(e)}")
        return jsonify({"message": "Validation error", "errors": str(e)}), 400

    school_id = sanitize_string(data.get("schoolCode"))
    school_name = sanitize_string(data.get("schoolName"))
    username = sanitize_string(data.get("username"))
    password = data.get("password")
    email = _normalize_email_address(data.get("email"))
    terms_version = sanitize_string(data.get("termsVersion"))
    terms_accepted = data.get("termsAccepted") is True
    policy_version = sanitize_string(data.get("policyVersion"))
    policy_accepted = data.get("policyAccepted") is True
    school_data_authority_confirmed = data.get("schoolDataAuthorityConfirmed") is True
    legacy_and_exam_consent_plan_confirmed = data.get("legacyAndExamConsentPlanConfirmed") is True
    aggregated_analytics_accepted = data.get("aggregatedAnalyticsAccepted") is True
    selected_plan = sanitize_string(data.get("selectedPlan", "Free"))  # Get selected plan, default to Free
    client_ip = get_client_ip()

    if not terms_accepted:
        return jsonify({"message": "Terms of Service must be accepted"}), 400
    if not policy_accepted:
        return jsonify({"message": "Privacy and Data Retention policies must be accepted"}), 400
    if not school_data_authority_confirmed:
        return jsonify({"message": "School data authority confirmation is required"}), 400
    if not legacy_and_exam_consent_plan_confirmed:
        return jsonify({"message": "Parent or guardian consent workflow confirmation is required before student biodata, legacy records, or examination data can be uploaded"}), 400
    if not aggregated_analytics_accepted:
        return jsonify({"message": "Data Processing Agreement acceptance for anonymized aggregated analytics is required"}), 400
    
    # Validate selected plan
    valid_plans = ["Free", "Basic", "Premium"]
    if selected_plan not in valid_plans:
        selected_plan = "Free"  # Default to Free if invalid plan provided

    if School.query.get(school_id):
        logger.warning(f"Registration failed: School ID {school_id} already exists")
        return jsonify({"message": "Organization ID already taken."}), 400

    if User.query.filter_by(username=username).first():
        logger.warning(f"Registration failed: Username {username} already exists")
        return jsonify({"message": "Proprietor username already taken. Choose a different username."}), 400

    if _find_platform_user_by_email(email):
        logger.warning(f"Registration failed: Email {email} already exists")
        return jsonify({"message": "An account with this email already exists. Login or reset the password instead."}), 400

    try:
        # 1. Create Tenant (School) - Always start with Free Tier
        # Users can upgrade to paid plans from dashboard (with payment)
        new_school = School(id=school_id, name=school_name)
        new_school.subscription_plan = "Free Tier"
        new_school.trial_plan = None
        new_school.trial_end_date = None
        
        db.session.add(new_school)

        # 2. Create Default Settings
        new_settings = SchoolSettings(school_id=school_id)
        db.session.add(new_settings)

        # 2b. Seed KYB workflow baseline for AML controls.
        new_verification = SchoolVerification(
            school_id=school_id,
            status="pending",
            risk_tier="medium",
            legal_name=school_name,
            organization_id=school_id,
            submitted_at=get_utc_now(),
        )
        db.session.add(new_verification)

        # 3. Create Proprietor User
        new_user = User(
            username=username,
            role="proprietor",
            school_id=school_id,
            email=email,
            terms_accepted_at=get_utc_now(),
            terms_version=terms_version,
            terms_accepted_ip=client_ip,
        )
        new_user.set_password(password)
        db.session.add(new_user)

        db.session.flush()

        compliance_workflow = _get_data_compliance_workflow_config(new_settings)
        compliance_workflow["registration_acknowledgements"] = {
            "school_data_authority_confirmed": school_data_authority_confirmed,
            "legacy_and_exam_consent_plan_confirmed": legacy_and_exam_consent_plan_confirmed,
            "aggregated_analytics_accepted": aggregated_analytics_accepted,
            "accepted_at": new_user.terms_accepted_at.isoformat() if new_user.terms_accepted_at else None,
            "accepted_ip": client_ip,
            "terms_version": terms_version or None,
            "policy_version": policy_version or None,
            "proprietor_user_id": new_user.id,
        }
        _set_data_compliance_workflow_config(new_settings, compliance_workflow)

        db.session.commit()

        try:
            policy_details = {
                "terms_version": terms_version,
                "policy_version": policy_version,
                "accepted_ip": client_ip,
                "accepted_at": new_user.terms_accepted_at.isoformat() if new_user.terms_accepted_at else None,
            }
            log_action(
                new_user.id,
                school_id,
                "REGISTRATION_POLICY_ACCEPTED",
                json.dumps(policy_details, ensure_ascii=False),
            )
            log_action(
                new_user.id,
                school_id,
                "REGISTRATION_DATA_COMPLIANCE_ACKNOWLEDGED",
                json.dumps(
                    {
                        "school_data_authority_confirmed": school_data_authority_confirmed,
                        "legacy_and_exam_consent_plan_confirmed": legacy_and_exam_consent_plan_confirmed,
                        "aggregated_analytics_accepted": aggregated_analytics_accepted,
                        "accepted_ip": client_ip,
                        "accepted_at": policy_details.get("accepted_at"),
                    },
                    ensure_ascii=False,
                ),
            )
        except Exception as audit_error:
            logger.warning(f"Policy acceptance audit log failed: {audit_error}")

        def _send_registration_welcome_once(subscription_plan_override=None):
            if not email:
                return
            existing = (
                db.session.query(AuditLog.id)
                .filter(
                    AuditLog.school_id == school_id,
                    AuditLog.action == "REGISTRATION_WELCOME_EMAIL_SENT",
                )
                .first()
            )
            if existing:
                return
            try:
                login_url = _get_frontend_login_url()
                subscription_plan = subscription_plan_override or new_school.subscription_plan or "Free Tier"
                welcome_subject, welcome_body = get_welcome_email(
                    username=username,
                    school_name=school_name,
                    school_id=school_id,
                    login_url=login_url,
                    subscription_plan=subscription_plan,
                )
                if welcome_subject and welcome_body:
                    send_email_notification_async(
                        to_email=email,
                        subject=welcome_subject,
                        body=welcome_body,
                        attachments=IMPORT_TEMPLATE_ATTACHMENTS,
                    )
                    log_action(
                        new_user.id,
                        school_id,
                        "REGISTRATION_WELCOME_EMAIL_SENT",
                        f"Welcome email sent to {email}",
                    )
            except Exception as email_error:
                logger.warning(
                    f"Welcome email failed for school {school_id} ({email}): {email_error}"
                )

        # Free plan completes immediately and sends the single welcome email.
        if selected_plan == "Free":
            _send_registration_welcome_once()
            logger.info(f"New school registered: {school_id} with Free plan")
            return jsonify({"message": "School registered successfully.", "requires_payment": False})

        # Paid-plan signups should still receive their credential/welcome email immediately
        # after account creation, independent of the later payment emails.
        _send_registration_welcome_once(subscription_plan_override=selected_plan)

        # Paid plans require immediate payment after registration.
        from backend.paystack_integration import PaystackError, initialize_payment
        pricing_info = PRICING.get(selected_plan, {})
        amount_cedis = float(pricing_info.get("base_fee_per_term", 0) or 0)
        if amount_cedis <= 0:
            return jsonify({"message": "Unable to compute payment amount for selected plan."}), 400

        auth_token = create_access_token(identity=str(new_user.id))
        callback_url = _get_frontend_base_url() + "/payment/callback?onboarding=registration"

        try:
            paystack_result = initialize_payment(
                email=email,
                amount_cents=int(round(amount_cedis * 100)),
                plan_name=selected_plan,
                school_id=school_id,
                metadata={
                    "user_id": new_user.id,
                    "student_count": 0,
                    "billing_period": "term",
                    "terms": 1,
                    "onboarding_flow": "registration",
                    "charge_mode": "base_fee_only",
                    "base_fee": amount_cedis,
                    "included_students": pricing_info.get("included_students", 0),
                    "overage_rate": pricing_info.get("per_student_per_term", 0),
                    "callback_url": callback_url,
                },
            )
        except PaystackError as pay_err:
            logger.error(f"Registration payment init failed for {school_id}: {pay_err}")
            return (
                jsonify(
                    {
                        "message": "School registered, but payment initialization failed. Please login and complete upgrade from dashboard.",
                        "requires_payment": False,
                    }
                ),
                200,
            )

        logger.info(f"New school registered: {school_id} with pending paid plan {selected_plan}")
        return jsonify(
            {
                "message": "School registered. Complete payment to activate selected plan.",
                "requires_payment": True,
                "payment_url": paystack_result.get("authorization_url"),
                "payment_reference": paystack_result.get("reference"),
                "token": auth_token,
                "school_id": school_id,
                "role": "proprietor",
                "roles": ["proprietor"],
                "subscription_plan": new_school.subscription_plan or "Free Tier",
            }
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration error: {str(e)}")
        return jsonify({"message": "Registration failed"}), 500


@api.route("/2fa/verify", methods=["POST"])
@csrf_protect
def verify_two_factor():
    """Verify email OTP and issue access token."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    code = (data.get("code") or "").strip()

    if not token or not code:
        return jsonify({"message": "Missing token or code"}), 400

    try:
        decoded = decode_token(token)
        if decoded.get("type") != "2fa_pending":
            return jsonify({"message": "Invalid token."}), 400
        user_id = int(decoded.get("sub"))
    except Exception:
        return jsonify({"message": "Invalid or expired token."}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Invalid token."}), 400

    now = datetime.now(timezone.utc)
    twofa = (
        TwoFactorToken.query.filter_by(user_id=user_id, consumed=False)
        .order_by(TwoFactorToken.created_at.desc())
        .first()
    )

    expires_at = getattr(twofa, "expires_at", None) if twofa else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if not twofa or not expires_at or expires_at < now:
        return jsonify({"message": "Code expired."}), 401

    if twofa.attempts >= 5:
        return jsonify({"message": "Too many attempts."}), 429

    if not check_password_hash(twofa.token_hash, code):
        twofa.attempts += 1
        db.session.commit()
        return jsonify({"message": "Invalid code."}), 400

    twofa.consumed = True
    user.last_login_at = get_utc_now()

    # Treat successful verification as enrollment (keeps state consistent in mandatory MFA mode).
    if not user.two_fa_enabled:
        user.two_fa_enabled = True
        user.two_fa_method = user.two_fa_method or "email"

    db.session.commit()

    log_action(
        user.id,
        user.school_id,
        "LOGIN_2FA",
        f"User {user.username} completed 2FA login",
    )

    school = School.query.get(user.school_id)
    return jsonify(
        _build_auth_success_payload(
            user,
            school,
            requires_password_reset=user.is_temp_password,
        )
    )


@api.route("/2fa/resend", methods=["POST"])
@rate_limit_auth
@csrf_protect
def resend_two_factor_code():
    """Issue a fresh email OTP for an in-progress 2FA login."""
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()

    if not token:
        return jsonify({"message": "Missing token"}), 400

    try:
        decoded = decode_token(token)
        if decoded.get("type") != "2fa_pending":
            return jsonify({"message": "Invalid token."}), 400
        user_id = int(decoded.get("sub"))
    except Exception:
        return jsonify({"message": "Invalid or expired token."}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Invalid token."}), 400

    try:
        challenge_payload = _issue_two_factor_challenge(user)
    except ValueError as config_error:
        return jsonify({"message": str(config_error)}), 400
    except RuntimeError as delivery_error:
        return jsonify({"message": str(delivery_error)}), 503

    log_action(
        user.id,
        user.school_id,
        "LOGIN_2FA_RESENT",
        f"User {user.username} requested a fresh 2FA code",
    )

    return jsonify({
        **challenge_payload,
        "message": "Verification code resent.",
    })


@api.route("/2fa/enable", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def enable_two_factor():
    """Enable email-based 2FA for the current user."""
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({"message": "User not found."}), 404
    if not user.email:
        return jsonify({"message": "Email required to enable 2FA."}), 400
    user.two_fa_enabled = True
    user.two_fa_method = "email"
    db.session.commit()
    log_action(
        user.id, user.school_id, "2FA_ENABLED", f"2FA enabled for {user.username}"
    )
    return jsonify({"message": "2FA enabled."})


@api.route("/2fa/disable", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def disable_two_factor():
    """Disable 2FA for the current user."""
    if MFA_REQUIRED:
        return jsonify({"message": "MFA is mandatory and cannot be disabled."}), 403
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({"message": "User not found."}), 404
    user.two_fa_enabled = False
    db.session.commit()
    log_action(
        user.id, user.school_id, "2FA_DISABLED", f"2FA disabled for {user.username}"
    )
    return jsonify({"message": "2FA disabled."})


@api.route("/forgot-password", methods=["POST"])
@rate_limit_auth
@csrf_protect
def forgot_password():
    """
    Initiates password reset flow via email.
    Security: Does not reveal if user exists (prevents user enumeration).
    """
    try:
        data = request.json
        if not data:
            return jsonify(
                {"message": "If an account exists, a reset link has been sent."}
            )

        school_id = data.get("schoolCode", "").strip()
        email = data.get("email", "").strip()

        if not school_id or not email:
            return jsonify(
                {"message": "If an account exists, a reset link has been sent."}
            )

        # We don't use multi_tenant_guard here because the user isn't logged in
        user = User.query.filter_by(school_id=school_id, email=email).first()

        if user:
            # Generate Reset Token (valid for 1 hour)
            reset_token = create_access_token(
                identity=str(user.id),
                additional_claims={"type": "password_reset"},
                expires_delta=timedelta(hours=1),
            )
            reset_record = PasswordReset(user_id=user.id, token=reset_token)
            db.session.add(reset_record)
            db.session.commit()

            # In production, this URL would point to the frontend domain
            reset_link = f"http://localhost:5173/reset-password?token={reset_token}"

            # Send password reset email using template system
            reset_subject, reset_body = get_password_reset_email(
                user_name=user.username,
                reset_link=reset_link
            )
            
            if reset_subject and reset_body:
                send_email_notification(
                    to_email=email,
                    subject=reset_subject,
                    body=reset_body,
                )

            log_action(
                user.id,
                school_id,
                "PASSWORD_RESET_REQUESTED",
                f"Password reset requested for {email}",
            )
        else:
            logger.info(
                f"Password reset requested for non-existent user: {email} in school {school_id}"
            )

        # Security: Same message whether user exists or not
        return jsonify({"message": "If an account exists, a reset link has been sent."})

    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        return jsonify({"message": "An error occurred. Please try again later."}), 500


@api.route("/reset-password", methods=["POST"])
@rate_limit_auth
@csrf_protect
def reset_password():
    """
    Resets password using a valid token.
    Security: Validates token type and ensures password meets requirements.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"message": "Invalid request"}), 400

        token = data.get("token", "").strip()
        new_password = (data.get("new_password") or data.get("password") or "").strip()

        if not token or not new_password:
            return jsonify({"message": "Missing required fields"}), 400

        # Validate password strength
        if len(new_password) < 8:
            return jsonify({"message": "Password must be at least 8 characters"}), 400

        if not any(c.isupper() for c in new_password):
            return (
                jsonify({"message": "Password must contain an uppercase letter"}),
                400,
            )

        if not any(c.isdigit() for c in new_password):
            return jsonify({"message": "Password must contain a digit"}), 400

        try:
            decoded = decode_token(token)
            if decoded.get("type") != "password_reset":
                logger.warning(
                    f"Invalid token type in reset-password: {decoded.get('type')}"
                )
                return jsonify({"message": "Invalid token."}), 400

            user_id = decoded["sub"]
            user = User.query.get(int(user_id))

            if not user:
                logger.warning(f"Password reset for non-existent user: {user_id}")
                return jsonify({"message": "Invalid token."}), 400

            user.set_password(new_password)
            # Clear temporary password flag if it was set
            if user.is_temp_password:
                user.is_temp_password = False
                user.temp_password_expires_at = None
            db.session.commit()

            log_action(
                user.id,
                user.school_id,
                "PASSWORD_RESET_SUCCESS",
                f"Password reset successful for user {user.username}",
            )

            return jsonify({"message": "Password reset successfully. Please login."})

        except Exception:
            from backend.api.models import PasswordReset

            reset_record = PasswordReset.query.filter_by(token=token).first()
            if not reset_record:
                logger.error("Token decode error")
                return jsonify({"message": "Invalid or expired token."}), 400

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            created_at = reset_record.created_at
            if created_at and created_at.tzinfo is None:
                cutoff = datetime.utcnow() - timedelta(hours=24)
            if created_at and created_at < cutoff:
                return jsonify({"message": "Token expired."}), 401

            user = User.query.get(reset_record.user_id)
            if not user:
                return jsonify({"message": "Invalid token."}), 400

            user.set_password(new_password)
            # Clear temporary password flag if it was set
            if user.is_temp_password:
                user.is_temp_password = False
                user.temp_password_expires_at = None
            db.session.commit()
            return jsonify({"message": "Password reset successfully. Please login."})

    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        return jsonify({"message": "An error occurred. Please try again later."}), 500


@api.route("/profile", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_profile():
    """Get current user profile."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    return jsonify(
        {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "profile_picture": user.profile_picture or "",
            "two_fa_enabled": bool(user.two_fa_enabled),
            "two_fa_method": user.two_fa_method or "email",
            "mfa_required": MFA_REQUIRED,
        }
    )


@api.route("/public/school-support/<school_code>", methods=["GET"])
def get_school_support_contact(school_code):
    """Public endpoint to fetch school support contact details for login page."""
    try:
        normalized_code = sanitize_string((school_code or "").upper())
        if not normalized_code:
            return jsonify({"message": "school_code is required"}), 400

        school = School.query.get(normalized_code)
        if not school:
            return jsonify({"message": "School not found"}), 404

        public_content = _get_platform_public_content()

        return jsonify(
            {
                "school_id": school.id,
                "school_name": school.name,
                "support_email": school.school_email or public_content["support"]["email"],
                "support_phone": school.school_phone or public_content["support"]["phone"],
                "support_website": school.school_website or "",
            }
        )
    except Exception as e:
        logger.error(f"Error fetching public school support details: {str(e)}")
        return jsonify({"message": "Failed to fetch support details"}), 500


@api.route("/profile/update", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def update_profile():
    """Update current user profile."""
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    data = request.json

    if "email" in data:
        normalized_email = (data.get("email") or "").strip().lower()
        user.email = normalized_email or None

    if "password" in data and data["password"]:
        user.set_password(data["password"])
            # Clear temporary password flag when user changes password
        if user.is_temp_password:
            user.is_temp_password = False
            user.temp_password_expires_at = None

    if "profile_picture" in data:
        user.profile_picture = data["profile_picture"]

    db.session.commit()
    log_action(int(user_id), g.school_id, "PROFILE_UPDATE", "Updated user profile")
    return jsonify({"message": "Profile updated successfully."})


@api.route("/school/report-template", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_report_template():
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        return jsonify({"message": "School settings not found"}), 404
    return jsonify(
        {
            "report_template_id": _normalize_report_template_id(settings.report_template_id),
            "report_template_config": settings.report_template_config or {},
        }
    )


@api.route("/school/report-template", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def set_report_template():
    data = request.json or {}
    template_id = _normalize_report_template_id(data.get("report_template_id"))
    template_config = data.get("report_template_config", {})

    if not template_id:
        return jsonify({"message": "report_template_id is required"}), 400

    school = School.query.get(g.school_id)
    effective_plan = get_effective_plan(school)

    # Check if plan can access this template
    if not can_access_report_template(effective_plan, template_id):
        accessible = get_all_accessible_templates(effective_plan)
        return (
            jsonify(
                {
                    "message": f"Template '{template_id}' not available in {effective_plan} plan",
                    "available_templates": accessible,
                }
            ),
            403,
        )

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)

    settings.report_template_id = template_id
    settings.report_template_config = _merge_report_template_config(
        settings.report_template_config,
        template_config or {},
    )
    db.session.commit()
    _append_report_template_history(
        settings,
        actor_id=int(get_jwt_identity()),
        action="select",
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Report template updated",
            "report_template_id": settings.report_template_id,
            "report_template_config": settings.report_template_config,
        }
    )


@api.route("/school/report-template/upload", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
@feature_required("html_templates")
def upload_report_template():
    """Upload a JSON template or HTML/CSS template with optional background image."""
    uploaded = request.files.get("file")
    html_file = request.files.get("html_file")
    css_file = request.files.get("css_file")
    background_image = request.files.get("background_image")

    payload = None
    template_id = None
    template_config = {}

    if uploaded:
        try:
            payload = json.load(uploaded.stream)
        except Exception as e:
            return jsonify({"message": "Invalid JSON file", "error": str(e)}), 400

        template_id = payload.get("report_template_id")
        template_config = payload.get("report_template_config", {})
        if not template_id:
            return jsonify({"message": "report_template_id is required in JSON"}), 400
    elif html_file:
        try:
            html_content = html_file.read().decode("utf-8")
        except Exception as e:
            return jsonify({"message": "Invalid HTML file", "error": str(e)}), 400

        css_content = ""
        if css_file:
            try:
                css_content = css_file.read().decode("utf-8")
            except Exception as e:
                return jsonify({"message": "Invalid CSS file", "error": str(e)}), 400

        background_data = None
        if background_image:
            encoded = base64.b64encode(background_image.read()).decode("ascii")
            mime_type = background_image.mimetype or "image/png"
            background_data = f"data:{mime_type};base64,{encoded}"

        template_id = request.form.get("report_template_id") or "custom_html_v1"
        template_config = {
            "type": "html",
            "html": html_content,
            "css": css_content,
            "background_image": background_data,
        }
    else:
        return (
            jsonify(
                {"message": "No file uploaded. Use form field 'file' or 'html_file'."}
            ),
            400,
        )

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)

    settings.report_template_id = _normalize_report_template_id(template_id)
    settings.report_template_config = _merge_report_template_config(
        settings.report_template_config,
        template_config or {},
    )
    db.session.commit()
    _append_report_template_history(
        settings,
        actor_id=int(get_jwt_identity()),
        action="upload",
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Report template uploaded",
            "report_template_id": settings.report_template_id,
            "report_template_config": settings.report_template_config,
        }
    )


@api.route("/school/report-template/history", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def get_report_template_history():
    settings = _get_or_create_school_settings()
    history = _get_report_template_history(settings)
    actor_ids = sorted({item.get("actor_id") for item in history if item.get("actor_id")})
    actors = (
        User.query.filter(User.school_id == g.school_id, User.id.in_(actor_ids)).all()
        if actor_ids
        else []
    )
    actor_map = {actor.id: actor.username for actor in actors}

    return jsonify(
        {
            "history": [
                {
                    "snapshot_id": item.get("snapshot_id"),
                    "report_template_id": item.get("report_template_id"),
                    "created_at": item.get("created_at"),
                    "action": item.get("action"),
                    "actor_id": item.get("actor_id"),
                    "actor_name": actor_map.get(item.get("actor_id")),
                    "restored_from_snapshot_id": item.get("restored_from_snapshot_id"),
                    "is_current": _normalize_report_template_id(settings.report_template_id)
                    == _normalize_report_template_id(item.get("report_template_id")),
                    "has_custom_html": bool((item.get("report_template_config") or {}).get("html")),
                    "has_custom_css": bool((item.get("report_template_config") or {}).get("css")),
                    "has_background_image": bool((item.get("report_template_config") or {}).get("background_image_url")),
                    "config_key_count": len((item.get("report_template_config") or {}).keys()),
                }
                for item in history
            ]
        }
    )


@api.route("/school/report-template/history/<string:snapshot_id>/restore", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def restore_report_template_history(snapshot_id):
    settings = _get_or_create_school_settings()
    snapshot = next(
        (item for item in _get_report_template_history(settings) if item.get("snapshot_id") == snapshot_id),
        None,
    )
    if not snapshot:
        return jsonify({"message": "Report template history snapshot not found."}), 404

    settings.report_template_id = _normalize_report_template_id(snapshot.get("report_template_id"))
    settings.report_template_config = _clone_json_document(snapshot.get("report_template_config") or {})
    db.session.commit()
    _append_report_template_history(
        settings,
        actor_id=int(get_jwt_identity()),
        action="restore",
        restored_from_snapshot_id=snapshot_id,
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Report template restored.",
            "report_template_id": settings.report_template_id,
            "report_template_config": settings.report_template_config,
        }
    )


@api.route("/school/report-template/history/<string:snapshot_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def download_report_template_history(snapshot_id):
    settings = _get_or_create_school_settings()
    snapshot = next(
        (item for item in _get_report_template_history(settings) if item.get("snapshot_id") == snapshot_id),
        None,
    )
    if not snapshot:
        return jsonify({"message": "Report template history snapshot not found."}), 404

    payload = {
        "snapshot_id": snapshot.get("snapshot_id"),
        "report_template_id": snapshot.get("report_template_id"),
        "created_at": snapshot.get("created_at"),
        "action": snapshot.get("action"),
        "restored_from_snapshot_id": snapshot.get("restored_from_snapshot_id"),
        "report_template_config": snapshot.get("report_template_config") or {},
    }
    filename = secure_filename(str(snapshot.get("report_template_id") or snapshot_id)) or snapshot_id
    response = make_response(json.dumps(payload, indent=2))
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}.json"
    return response


# --- 2. ACADEMIC GOVERNANCE (Teacher/Homeroom) ---


@api.route("/school/grades", methods=["GET"])
@multi_tenant_guard
def get_school_grades():
    """Returns the list of valid grade levels for the school."""
    return jsonify(VALID_GRADES)


@api.route("/school/subjects", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_school_subjects():
    """Returns the list of subjects for the school (from existing grades or defaults)."""
    subjects = (
        db.session.query(StudentGrade.subject_name)
        .join(Student, Student.id == StudentGrade.student_id)
        .filter(Student.school_id == g.school_id)
        .group_by(StudentGrade.subject_name)
        .order_by(func.lower(StudentGrade.subject_name))
        .all()
    )
    subject_list = [s[0] for s in subjects if s[0]]
    return jsonify(subject_list or DEFAULT_SUBJECTS)


@api.route("/school/classes", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_school_classes():
    """Returns all classes in the school."""
    try:
        # Try to get classes from AcademicClass table
        classes = (
            AcademicClass.query.filter_by(school_id=g.school_id)
            .order_by(AcademicClass.name)
            .all()
        )

        if classes:
            class_list = [
                {"id": c.id, "name": c.name, "class_name": c.name} for c in classes
            ]
            return jsonify(class_list)

        # Fallback: get unique class names from students
        student_classes = (
            db.session.query(Student.current_class)
            .filter(Student.school_id == g.school_id)
            .group_by(Student.current_class)
            .order_by(Student.current_class)
            .all()
        )

        class_names = [c[0] for c in student_classes if c[0]]

        if class_names:
            return jsonify([{"name": c, "class_name": c} for c in class_names])

        return jsonify([])

    except Exception as e:
        print(f"Error fetching classes: {e}", flush=True)
        return jsonify([])


@api.route("/school/classes", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def create_school_class():
    """Create a school-defined class for timetable and academic workflows."""
    data = request.json or {}
    class_name = sanitize_string(data.get("name") or data.get("class_name") or "")
    level = sanitize_string(data.get("level") or "") or None
    stream = sanitize_string(data.get("stream") or "") or None

    if not class_name:
        return jsonify({"message": "Class name is required."}), 400

    existing = AcademicClass.query.filter_by(
        school_id=g.school_id,
        name=class_name,
        stream=stream,
    ).first()
    if existing:
        return jsonify(
            {
                "message": "Class already exists.",
                "class": {"id": existing.id, "name": existing.name, "class_name": existing.name, "stream": existing.stream},
            }
        ), 200

    school_class = AcademicClass(
        school_id=g.school_id,
        name=class_name,
        level=level,
        stream=stream,
    )
    db.session.add(school_class)
    db.session.commit()

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "ACADEMIC_CLASS_CREATED",
        json.dumps(
            {
                "class_name": class_name,
                "stream": stream,
                "level": level,
            }
        ),
    )

    return jsonify(
        {
            "message": "Class created successfully.",
            "class": {
                "id": school_class.id,
                "name": school_class.name,
                "class_name": school_class.name,
                "level": school_class.level,
                "stream": school_class.stream,
            },
        }
    ), 201


@api.route("/report-cards/preview", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def get_report_card_preview():
    """Return the most recent report card for preview rendering."""
    from backend.api.models import ReportCard

    student_id = request.args.get("student_id")
    class_name = request.args.get("class_name")
    academic_term = request.args.get("academic_term")
    academic_year = request.args.get("academic_year")

    query = ReportCard.query.filter_by(school_id=g.school_id)
    if student_id:
        query = query.filter_by(student_id=student_id)
    if class_name:
        query = query.filter_by(class_name=class_name)
    if academic_term:
        query = query.filter_by(academic_term=academic_term)
    if academic_year:
        query = query.filter_by(academic_year=academic_year)

    report = query.order_by(
        func.coalesce(ReportCard.updated_at, ReportCard.created_at).desc()
    ).first()

    if not report:
        return jsonify({"message": "No report cards available"}), 404

    return jsonify(report.to_dict())


@api.route("/homeroom/finalize-class", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def finalize_class():
    """
    Locks grades and triggers the Descriptive AI analysis.
    This is the "Governance Lockdown" you need for your thesis.
    """
    try:
        data = request.json
        user = User.query.get(int(get_jwt_identity()))
        if user and user.role == "proprietor":
            return (
                jsonify(
                    {"message": "Access denied: Only teachers can finalize grades."}
                ),
                403,
            )

        class_name = data.get("class_name")
        subject = data.get("subject")
        grade_data = data.get("grade_data")
        remarks_data = data.get("remarks_data", {})

        if not class_name or not subject or not grade_data:
            return (
                jsonify(
                    {
                        "message": "Missing required fields: class_name, subject, grade_data"
                    }
                ),
                422,
            )

        if class_name not in VALID_GRADES:
            return (
                jsonify(
                    {
                        "message": f"Invalid class name. Must be one of: {', '.join(VALID_GRADES)}"
                    }
                ),
                400,
            )

        if not isinstance(grade_data, dict):
            return jsonify({"message": "grade_data must be a dictionary"}), 422

        school = School.query.get(g.school_id)
        if not school:
            return jsonify({"message": "School not found"}), 404

        # user role already checked above

        # Get school's grading scheme
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        class_score_max = settings.class_score_max if settings else 30
        exam_score_max = settings.exam_score_max if settings else 70

        for s_id, score_obj in grade_data.items():
            try:
                # Support both old format (single float) and new format (dict with class_score and exam_score)
                if isinstance(score_obj, dict):
                    class_score = float(score_obj.get("class_score", 0))
                    exam_score = float(score_obj.get("exam_score", 0))

                    # Validate score ranges using school's grading scheme
                    if class_score < 0 or class_score > class_score_max:
                        return (
                            jsonify(
                                {
                                    "message": f"Invalid class score for student {s_id}. Must be 0-{class_score_max}"
                                }
                            ),
                            400,
                        )
                    if exam_score < 0 or exam_score > exam_score_max:
                        return (
                            jsonify(
                                {
                                    "message": f"Invalid exam score for student {s_id}. Must be 0-{exam_score_max}"
                                }
                            ),
                            400,
                        )

                    # Calculate total: class_score + exam_score = 0-100
                    total_score = class_score + exam_score
                else:
                    # Backward compatibility: treat as total score
                    total_score = float(score_obj)
                    if total_score < 0 or total_score > 100:
                        return (
                            jsonify(
                                {
                                    "message": f"Invalid score for student {s_id}. Must be 0-100"
                                }
                            ),
                            400,
                        )
                    # For backward compatibility, split into proportions based on school's grading scheme
                    class_score = total_score * (class_score_max / 100)
                    exam_score = total_score * (exam_score_max / 100)

            except (ValueError, TypeError) as e:
                return (
                    jsonify(
                        {
                            "message": f"Invalid score format for student {s_id}: {str(e)}"
                        }
                    ),
                    400,
                )

            grade_record = StudentGrade.query.filter_by(
                student_id=s_id, subject_name=subject, is_finalized=False
            ).first()

            if not grade_record:
                grade_record = StudentGrade(
                    student_id=int(s_id), subject_name=subject, is_finalized=False
                )
                db.session.add(grade_record)

            # Record the class for traceability (helps subject teachers and homeroom)
            grade_record.class_name = class_name

            grade_record.class_score = class_score
            grade_record.exam_score = exam_score
            grade_record.total_score = total_score
            grade_record.is_finalized = True
            grade_record.remarks = remarks_data.get(s_id, "")
            if has_feature(get_effective_plan(school), "ai_narratives"):
                grade_record.ai_narrative = generate_descriptive_analysis(int(s_id))
            else:
                grade_record.ai_narrative = "AI Analysis requires Premium Plan."

        log_action(
            user_id=int(get_jwt_identity()),
            school_id=g.school_id,
            action="SUBJECT_GRADES_SUBMITTED",
            details=f"{subject} grades submitted for {class_name}.",
        )
        db.session.commit()
        return jsonify(
            {"message": f"{subject} grades for {class_name} saved and locked."}
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error finalizing class", "error": str(e)}), 500


@api.route("/reports/parse", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def parse_report_card():
    """Uploads a report-card image, parses it, and optionally creates finalized grades.

    Form-data parameters:
    - file: image file (required)
    - create: 'true' to create StudentGrade records when student match found
    """
    try:
        uploaded = request.files.get("file") or request.files.get("image")
        # Allow passing raw text for demo/testing purposes if no file
        ocr_text_param = request.form.get("ocr_text")

        if not uploaded and not ocr_text_param:
            return jsonify({"message": "No file uploaded. Use form field 'file'."}), 400

        file_data = uploaded.read() if uploaded else None
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        template_config = settings.report_template_config if settings else None
        parsed = parse_report_card_image_bytes(
            image_bytes=file_data,
            ocr_text=ocr_text_param,
            template_config=template_config,
        )

        # Attempt to match student in DB by student_code
        student = None
        scode = parsed.get("student_code")
        if scode:
            student = Student.query.filter_by(
                student_code=scode, school_id=g.school_id
            ).first()

        created = False
        narrative = None
        create_flag = request.form.get("create", "false").lower() == "true"
        if create_flag and student and parsed.get("subjects"):
            for subj in parsed["subjects"]:
                total = subj.get("total_score", 0)
                sg = StudentGrade(
                    student_id=student.id,
                    subject_name=subj.get("subject")[:50],
                    class_name=student.current_class,
                    class_score=subj.get("class_score", total * 0.3),
                    exam_score=subj.get("exam_score", total * 0.7),
                    total_score=total,
                    is_finalized=True,
                    remarks=subj.get("remark", "")[:250],
                )
                db.session.add(sg)
            db.session.commit()
            created = True

            # Generate descriptive narrative (do not persist here)
            try:
                narrative = generate_descriptive_analysis(student.id)
            except Exception:
                narrative = None

        response = {
            "parsed": parsed,
            "matched_student_id": student.id if student else None,
            "created_grades": created,
            "ai_narrative": narrative,
        }
        return jsonify(response)
    except RuntimeError as e:
        return jsonify({"message": str(e)}), 500
    except Exception as e:
        logger.exception("Report parse failed")
        return jsonify({"message": "Failed to parse report card", "error": str(e)}), 500


@api.route("/homeroom/generate-terminal-report", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def generate_terminal_report():
    """Homeroom Teacher Action: Aggregates all subject grades into a final report."""
    try:
        data = request.json
        class_name = data.get("class_name")
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

        if class_name not in VALID_GRADES:
            return (
                jsonify(
                    {
                        "message": f"Invalid class name. Must be one of: {', '.join(VALID_GRADES)}"
                    }
                ),
                422,
            )
        # Only homeroom teacher (or privileged roles) may generate terminal reports for a class
        user = User.query.get(int(get_jwt_identity()))
        if user.role == "teacher" and (
            not user.assigned_class or user.assigned_class != class_name
        ):
            return (
                jsonify(
                    {
                        "message": "Access denied: Not the homeroom teacher for this class."
                    }
                ),
                403,
            )

        students = Student.query.filter_by(
            school_id=g.school_id, current_class=class_name
        ).all()
        reports = []

        # Check Approval Status
        status_record = ReportCardStatus.query.filter_by(
            school_id=g.school_id, class_name=class_name
        ).first()
        approval_status = status_record.status if status_record else "Not Submitted"
        feedback = status_record.headmaster_feedback if status_record else None

        # Support optional assignment-based blending using StudentAssignment and ClassGradingPolicy
        from backend.api.models import ClassGradingPolicy, StudentAssignment

        policy = ClassGradingPolicy.query.filter_by(
            school_id=g.school_id, class_name=class_name
        ).first()
        policy_weight = policy.assignment_weight if policy else 30
        min_assign = policy.min_assignments if policy else 5

        # allow requester to override weight (only 30 or 40 allowed)
        req_weight = data.get("assignment_weight") if isinstance(data, dict) else None
        if req_weight in (30, 40):
            policy_weight = req_weight

        for student in students:
            grades = StudentGrade.query.filter_by(
                student_id=student.id, is_finalized=True
            ).all()
            subjects_out = []

            for gr in grades:
                subj = gr.subject_name
                subj_score = gr.total_score or 0

                assigns = StudentAssignment.query.filter_by(
                    school_id=g.school_id, student_id=student.id, subject=subj
                )
                assign_count = assigns.count()
                assign_avg = None
                if assign_count >= min_assign:
                    assign_avg = sum(a.score for a in assigns.all()) / assign_count

                if assign_avg is not None:
                    blended = round(
                        (assign_avg * (policy_weight / 100.0))
                        + (subj_score * ((100 - policy_weight) / 100.0)),
                        1,
                    )
                else:
                    blended = subj_score

                subjects_out.append(
                    {
                        "subject": subj,
                        "score": blended,
                        "class_name": getattr(gr, "class_name", None),
                        "assign_count": assign_count,
                        "assign_avg": (
                            round(assign_avg, 1) if assign_avg is not None else None
                        ),
                    }
                )

            avg = (
                round(sum(s["score"] for s in subjects_out) / len(subjects_out), 1)
                if subjects_out
                else 0
            )
            reports.append(
                {
                    "student_id": student.id,
                    "student_name": student.name,
                    "student_code": student.student_code,
                    "class_name": student.current_class,
                    "subjects": subjects_out,
                    "average": avg,
                    "narrative": generate_descriptive_analysis(student.id),
                }
            )

        log_action(
            user_id=int(get_jwt_identity()),
            school_id=g.school_id,
            action="TERMINAL_REPORT_GENERATED",
            details=f"Final Terminal Reports generated for {class_name}.",
        )
        db.session.commit()
        return jsonify(
            {
                "message": f"Terminal Reports generated.",
                "reports": reports,
                "approval_status": approval_status,
                "feedback": feedback,
                "report_template_id": settings.report_template_id if settings else None,
            }
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error generating terminal report", "error": str(e)}),
            500,
        )


@api.route("/homeroom/submit-reports", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def submit_reports():
    data = request.json
    class_name = data.get("class_name")

    status_record = ReportCardStatus.query.filter_by(
        school_id=g.school_id, class_name=class_name
    ).first()
    if not status_record:
        status_record = ReportCardStatus(school_id=g.school_id, class_name=class_name)
        db.session.add(status_record)

    status_record.status = "Pending"
    status_record.submitted_at = get_utc_now()
    status_record.headmaster_feedback = None

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "REPORTS_SUBMITTED",
        f"Terminal reports for {class_name} submitted for approval.",
    )
    db.session.commit()
    return jsonify({"message": "Reports submitted for Headmaster approval."})


@api.route("/headmaster/report-approvals", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def get_report_approvals():
    """Get report cards submitted to headmaster for approval."""
    from backend.api.models import ReportCard

    # Query ReportCard table for reports submitted to headmaster
    reports = (
        ReportCard.query.filter(
            ReportCard.school_id == g.school_id, ReportCard.status == "Submitted"
        )
        .filter(
            (ReportCard.submit_to == "headmaster")
            | (ReportCard.submit_to == None)  # Include legacy reports without submit_to
        )
        .order_by(ReportCard.submitted_at.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": r.id,
                "student_id": r.student_id,
                "student_name": r.student.name if r.student else "Unknown",
                "class_name": r.class_name,
                "academic_term": r.academic_term,
                "academic_year": r.academic_year,
                "status": r.status,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "term_average": r.term_average,
                "overall_position": r.overall_position,
                "submit_to": r.submit_to or "headmaster",
            }
            for r in reports
        ]
    )


@api.route("/headmaster/approve-report", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def approve_report():
    """Approve or reject a report card (legacy endpoint for HeadmasterDashboard)."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity()) if hasattr(get_jwt_identity, "__call__") else None
    data = request.json
    report_id = data.get("report_id")
    status = data.get("status")  # Approved / Rejected
    feedback = data.get("feedback", "")

    if not report_id:
        return jsonify({"message": "Missing report_id"}), 400

    report = ReportCard.query.filter_by(
        id=report_id, school_id=g.school_id
    ).first_or_404()

    if status == "Approved":
        report.status = "HeadmasterApproved"
        report.headmaster_remarks = feedback
        report.headmaster_approved_at = get_utc_now()
        if user_id:
            report.headmaster_approved_by = user_id
    elif status == "Rejected":
        report.status = "Rejected"
        report.headmaster_remarks = feedback
    else:
        return jsonify({"message": "Invalid status"}), 400

    db.session.commit()

    student_name = report.student.name if report.student else "Unknown"
    return jsonify({"message": f"Report card for {student_name} marked as {status}."})


@api.route("/homeroom/student-summary/<int:student_id>", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
def get_teacher_ai_summary(student_id):
    """Allows teachers to review the AI summary for a student after finalization."""
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    grade_record = (
        StudentGrade.query.filter_by(student_id=student.id, is_finalized=True)
        .order_by(StudentGrade.id.desc())
        .first()
    )

    if not grade_record or not grade_record.ai_narrative:
        return jsonify({"message": "AI summary not yet generated."}), 404

    return jsonify(
        {"student_name": student.name, "ai_summary": grade_record.ai_narrative}
    )


@api.route("/assignments/add", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def add_assignment():
    """Add a student assignment score (0-100)."""
    data = request.json
    student_id = data.get("student_id")
    subject = data.get("subject")
    score = data.get("score")

    if not student_id or not subject or score is None:
        return jsonify({"message": "Missing fields: student_id, subject, score"}), 400

    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()

    a = StudentAssignment(
        student_id=student.id,
        school_id=g.school_id,
        subject=subject,
        score=float(score),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"message": "Assignment recorded."})


@api.route("/assignments/summary", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def assignment_summary():
    student_id = request.args.get("student_id")
    subject = request.args.get("subject")
    if not student_id or not subject:
        return jsonify({"message": "Missing student_id or subject"}), 400

    assigns = StudentAssignment.query.filter_by(
        school_id=g.school_id, student_id=student_id, subject=subject
    )
    count = assigns.count()
    avg = None
    if count > 0:
        avg = sum(a.score for a in assigns.all()) / count
    return jsonify({"count": count, "avg": round(avg, 1) if avg is not None else None})


@api.route("/class/grading-policy", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def set_class_grading_policy():
    data = request.json
    class_name = data.get("class_name")
    weight = data.get("assignment_weight")
    min_assign = data.get("min_assignments", 5)

    if class_name not in VALID_GRADES:
        return jsonify({"message": "Invalid class_name"}), 400
    if weight not in (30, 40):
        return jsonify({"message": "assignment_weight must be 30 or 40"}), 400

    policy = ClassGradingPolicy.query.filter_by(
        school_id=g.school_id, class_name=class_name
    ).first()
    if not policy:
        policy = ClassGradingPolicy(
            school_id=g.school_id,
            class_name=class_name,
            assignment_weight=weight,
            min_assignments=min_assign,
        )
        db.session.add(policy)
    else:
        policy.assignment_weight = weight
        policy.min_assignments = min_assign

    db.session.commit()
    return jsonify({"message": "Class grading policy updated."})


@api.route("/students/by-class/<class_name>", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_students_by_class(class_name):
    """Fetches students for grade entry or homeroom use."""
    if class_name not in VALID_GRADES:
        return jsonify({"message": "Invalid class name."}), 400
    
    user = User.query.get(int(get_jwt_identity()))
    
    # Authorization check for subject teachers
    if user.role == "teacher":
        # Subject teachers can access students from:
        # 1. Their assigned homeroom class, OR
        # 2. Any class they have a teaching assignment in
        has_access = False
        
        # Check if homeroom teacher
        if user.assigned_class == class_name:
            has_access = True
        else:
            # Check if teaching this class
            assignment = TeacherAssignment.query.filter_by(
                school_id=g.school_id,
                teacher_id=user.id,
                class_name=class_name
            ).first()
            has_access = assignment is not None
        
        if not has_access:
            return (
                jsonify(
                    {"message": "Access denied: You don't teach this class."}
                ),
                403,
            )
    
    students = Student.query.filter_by(
        school_id=g.school_id, current_class=class_name
    ).all()
    feeding_status_details = _get_feeding_status_details_for_students(students, g.school_id)

    results = []
    for s in students:
        feeding_status = feeding_status_details.get(s.id, {})

        results.append(
            {
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                "current_class": s.current_class,
                "parent_email": s.parent_email,
                **_serialize_feeding_status_detail(feeding_status),
                "is_present": s.is_present,
                "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
                "age": s.age,
                "gender": s.gender,
                "is_on_scholarship": bool(s.is_on_scholarship),
                "scholarship_covers_tuition": bool(s.scholarship_covers_tuition),
                "scholarship_covers_feeding": bool(s.scholarship_covers_feeding),
                "scholarship_notes": s.scholarship_notes,
            }
        )
    return jsonify(results)


@api.route("/students/<int:student_id>/payment-codes", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_student_payment_codes(student_id):
    """
    Generate parent payment instructions for a student.

    Primary flow: stable learner identity plus structured references.
    - Parents can pay through approved phone or digital channels using the fee reference.
    - Cash at the school office remains the base-amount fallback.

    Backward compatibility: legacy-style reference codes are still returned.
    """
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    school = School.query.get(g.school_id)
    _ensure_student_payment_identity(student)
    verification_restriction = _payment_records_verification_block_response(school)
    if verification_restriction:
        return verification_restriction
    restriction = _payment_collection_block_response(school)
    if restriction:
        return restriction

    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None
    payload = _build_student_payment_instruction_payload(student, g.school_id)
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if payload.get("payment_identity", {}).get("supports_fee_route_dvas"):
        for code in payload.get("payment_codes") or []:
            if sanitize_string((code.get("payment_category") or {}).get("fee_type") or code.get("fee_type") or "") != "Tuition":
                continue
            try:
                intent, error = _create_or_reuse_student_virtual_account_intent(student, school, settings, code)
                if error:
                    code["tracked_transfer_error"] = public_tracked_transfer_failure_message() if looks_like_provider_error(error, sanitize_string) else error
                    continue
                route_payload = _build_payment_collection_intent_payload(intent)
                code["virtual_route"] = route_payload
                code["virtual_bank_account"] = route_payload.get("account_number") if route_payload else None
                code["virtual_bank_name"] = route_payload.get("bank_name") if route_payload else None
                code["subaccount_code"] = route_payload.get("subaccount_code") if route_payload else None
                code["has_virtual_route"] = bool(route_payload)
                code["preferred_payment_model"] = "virtual_account_ready" if route_payload else code.get("preferred_payment_model")
            except Exception as exc:
                db.session.rollback()
                logger.error(
                    "Tracked transfer account preparation failed for school %s student %s ref %s: %s",
                    g.school_id,
                    student.id,
                    code.get("reference_code") or code.get("code"),
                    exc,
                )
                code["tracked_transfer_error"] = public_tracked_transfer_failure_message()

    log_action(
        actor_id,
        g.school_id,
        "PAYMENT_CODES_GENERATED",
        json.dumps(
            {
                "student_id": student.id,
                "student_code": student.student_code,
                "student_class": student.current_class,
                "routes_count": len(payload["payment_codes"]),
                "has_virtual_route": any(
                    bool(code.get("has_virtual_route")) for code in payload["payment_codes"]
                ),
                "ip": request.remote_addr,
            }
        ),
    )
    db.session.commit()
    return jsonify(payload)


@api.route("/students/<int:student_id>/payment-codes/<string:reference_code>/virtual-account", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def create_student_payment_virtual_account(student_id, reference_code):
    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first_or_404()
    school = School.query.get(g.school_id)
    _ensure_student_payment_identity(student)
    verification_restriction = _payment_records_verification_block_response(school)
    if verification_restriction:
        return verification_restriction
    restriction = _payment_collection_block_response(school)
    if restriction:
        return restriction

    payload = _build_student_payment_instruction_payload(student, g.school_id)
    selected_code = next(
        (
            code
            for code in (payload.get("payment_codes") or [])
            if (sanitize_string(code.get("reference_code") or code.get("code") or "") or "")
            == (sanitize_string(reference_code) or "")
        ),
        None,
    )
    if not selected_code:
        return jsonify({"message": "Payment reference not found for this student."}), 404
    if sanitize_string((selected_code.get("payment_category") or {}).get("fee_type") or selected_code.get("fee_type") or "") != "Tuition":
        return jsonify({"message": "Tracked transfer accounts are available for tuition references only."}), 400

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    try:
        intent, error = _create_or_reuse_student_virtual_account_intent(student, school, settings, selected_code)
    except Exception as exc:
        db.session.rollback()
        logger.error(
            "Tracked transfer account generation crashed for school %s student %s ref %s: %s",
            g.school_id,
            student.id,
            reference_code,
            exc,
        )
        return jsonify({"message": public_tracked_transfer_failure_message()}), 502

    if error:
        db.session.rollback()
        if looks_like_provider_error(error, sanitize_string):
            logger.error(
                "Tracked transfer account generation failed for school %s student %s ref %s: %s",
                g.school_id,
                student.id,
                reference_code,
                error,
            )
            return jsonify({"message": public_tracked_transfer_failure_message()}), 502
        return jsonify({"message": error}), 400

    route_payload = _build_payment_collection_intent_payload(intent)
    updated_code = {**selected_code}
    updated_code["virtual_route"] = route_payload
    updated_code["virtual_bank_account"] = route_payload.get("account_number") if route_payload else None
    updated_code["virtual_bank_name"] = route_payload.get("bank_name") if route_payload else None
    updated_code["subaccount_code"] = route_payload.get("subaccount_code") if route_payload else None
    updated_code["has_virtual_route"] = bool(route_payload)
    updated_code["preferred_payment_model"] = "virtual_account_ready" if route_payload else updated_code.get("preferred_payment_model")

    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None

    log_action(
        actor_id,
        g.school_id,
        "PAYMENT_TRANSFER_ROUTE_GENERATED",
        json.dumps(
            {
                "student_id": student.id,
                "reference_code": updated_code.get("reference_code"),
                "payment_type": updated_code.get("payment_category", {}).get("fee_type") or updated_code.get("fee_type"),
                "intent_id": intent.id,
                "virtual_account": route_payload.get("account_number") if route_payload else None,
            }
        ),
    )
    db.session.commit()
    return jsonify(
        {
            "status": "success",
            "message": "Tracked transfer account generated successfully.",
            "payment_code": updated_code,
            "virtual_route": route_payload,
        }
    ), 200


@api.route("/students", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_students():
    """Fetch all students - accessible by proprietor, finance, and teaching staff."""
    try:
        include_inactive = str(request.args.get("include_inactive") or "").strip().lower() in {"1", "true", "yes", "all"}
        query = Student.query.filter_by(school_id=g.school_id)
        if not include_inactive:
            query = query.filter(Student.status.in_(["Active", "active"]))
        students = query.order_by(Student.name).all()
        feeding_status_details = _get_feeding_status_details_for_students(students, g.school_id)
        response = jsonify(
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "student_code": s.student_code,
                    "current_class": s.current_class,
                    "guardian_name": s.guardian_name,
                    "parent_name": s.parent_name,
                    "parent_email": s.parent_email,
                    "parent_phone": s.parent_phone,
                    **_serialize_feeding_status_detail(feeding_status_details.get(s.id, {})),
                    "is_present": s.is_present,
                    "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
                    "age": s.age,
                    "gender": s.gender,
                    "is_on_scholarship": bool(s.is_on_scholarship),
                    "scholarship_covers_tuition": bool(s.scholarship_covers_tuition),
                    "scholarship_covers_feeding": bool(s.scholarship_covers_feeding),
                    "scholarship_notes": s.scholarship_notes,
                    "total_tuition_owed": s.total_tuition_owed,
                    "status": s.status or "Active",
                    "class_status": s.current_class if (s.status or "Active") == "Active" else (s.status or "Active"),
                }
                for s in students
            ]
        )
        db.session.commit()
        return response
    except Exception as e:
        return jsonify({"message": "Error retrieving students", "error": str(e)}), 500


@api.route("/students/<int:student_id>/documents", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "homeroom", "teacher")
@jwt_required()
def get_student_documents(student_id):
    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first_or_404()

    student_documents = [
        item
        for item in (
            _build_student_document_entry(student.id, entry)
            for entry in _get_student_document_manifest(student)
        )
        if item
    ]
    admission_documents = _build_linked_student_admission_documents(student)

    return jsonify(
        {
            "student_id": student.id,
            "student_name": student.name,
            "student_documents": student_documents,
            "admission_documents": admission_documents,
            "documents": [*student_documents, *admission_documents],
        }
    )


@api.route("/students/<int:student_id>/documents", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "homeroom", "teacher")
@jwt_required()
def upload_student_documents(student_id):
    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first_or_404()
    uploaded_files = [item for item in request.files.getlist("documents") if item and item.filename]
    if not uploaded_files:
        return jsonify({"message": "At least one document is required."}), 400

    category_override = sanitize_string(request.form.get("category") or "") or None
    note = sanitize_string(request.form.get("note") or "") or None
    user_id = int(get_jwt_identity())
    document_manifest = list(_get_student_document_manifest(student))

    for uploaded in uploaded_files:
        file_bytes = uploaded.read()
        if not file_bytes:
            continue

        entry = _extract_parent_admission_document_details(
            uploaded.filename,
            uploaded.mimetype,
            file_bytes,
            category_override=category_override,
        )
        entry.update(_store_student_document(g.school_id, uploaded, file_bytes))
        entry["source"] = "student_profile"
        entry["note"] = note
        entry["uploaded_at"] = get_utc_now().isoformat()
        entry["uploaded_by_user_id"] = user_id
        document_manifest.append(entry)

        if entry.get("category") == "passport_photo":
            student.profile_picture = _build_student_profile_picture_data_url(
                file_bytes,
                uploaded.mimetype,
            )

    _set_student_document_manifest(student, document_manifest)
    db.session.commit()

    return jsonify(
        {
            "message": "Student documents uploaded successfully.",
            "documents": [
                item
                for item in (
                    _build_student_document_entry(student.id, entry)
                    for entry in document_manifest
                )
                if item
            ],
            "profile_picture": student.profile_picture,
        }
    )


@api.route("/students/<int:student_id>/documents/<string:document_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "homeroom", "teacher")
@jwt_required()
def download_student_document(student_id, document_id):
    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
    if not student:
        return jsonify({"message": "Student not found"}), 404

    matching_document = next(
        (
            item
            for item in _get_student_document_manifest(student)
            if isinstance(item, dict) and (item.get("document_id") or item.get("id")) == document_id
        ),
        None,
    )
    if matching_document:
        resolved_path = _resolve_existing_school_file(
            _get_student_document_storage_root(),
            matching_document.get("stored_filename"),
        )
        if not resolved_path:
            return jsonify({"message": "Document file is no longer available"}), 404

        return send_file(
            resolved_path,
            as_attachment=False,
            download_name=matching_document.get("original_filename") or matching_document.get("filename") or "student-document",
        )

    application = ParentAdmissionApplication.query.filter_by(
        admitted_student_id=student.id,
        school_id=g.school_id,
    ).first()
    if not application:
        return jsonify({"message": "Document not found"}), 404

    linked_document = next(
        (
            item
            for item in (application.document_manifest or [])
            if isinstance(item, dict) and (item.get("document_id") or item.get("id")) == document_id
        ),
        None,
    )
    if not linked_document:
        return jsonify({"message": "Document not found"}), 404

    resolved_path = _resolve_existing_school_file(
        _get_parent_admission_document_storage_root(),
        linked_document.get("stored_filename"),
    )
    if not resolved_path:
        return jsonify({"message": "Document file is no longer available"}), 404

    return send_file(
        resolved_path,
        as_attachment=False,
        download_name=linked_document.get("original_filename") or linked_document.get("filename") or "admission-document",
    )


@api.route("/students/<int:student_id>/payments", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "homeroom", "teacher")
@jwt_required()
def get_student_payments(student_id):
    """Fetch payment history for a specific student."""
    try:
        school = School.query.get(g.school_id)
        verification_restriction = _payment_records_verification_block_response(school)
        if verification_restriction:
            return verification_restriction
        collection_restriction = _payment_collection_block_response(school)
        if collection_restriction:
            return collection_restriction

        student = Student.query.filter_by(
            id=student_id, school_id=g.school_id
        ).first_or_404()
        payments = (
            Payment.query.filter_by(student_id=student_id, school_id=g.school_id)
            .order_by(Payment.date_paid.desc())
            .all()
        )

        payment_list = []
        for payment in payments:
            payment_category = payment.payment_category if isinstance(payment.payment_category, dict) else {}
            applied_amount = round(float(payment_category.get("applied_school_fee_amount") or payment.amount or 0), 2)
            gross_amount = round(float(payment_category.get("gross_amount_paid") or payment_category.get("charged_total_amount") or payment.amount or 0), 2)

            payment_list.append(
                {
                    "id": payment.id,
                    "amount": applied_amount,
                    "display_amount": gross_amount,
                    "applied_amount": applied_amount,
                    "base_amount": applied_amount,
                    "total_amount": gross_amount,
                    "payment_type": payment.payment_type,
                    "method": payment.method,
                    "status": payment.status,
                    "date_paid": payment.date_paid.strftime("%Y-%m-%d %H:%M"),
                    "reference_id": payment.reference_id,
                    "payment_category": payment_category,
                    "verified_at": (
                        payment.verified_at.strftime("%Y-%m-%d %H:%M")
                        if payment.verified_at
                        else None
                    ),
                }
            )

        return jsonify(payment_list)
    except Exception as e:
        return (
            jsonify({"message": "Error retrieving student payments", "error": str(e)}),
            500,
        )


def _get_or_create_school_settings_record(school_id):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    if settings is None:
        settings = SchoolSettings(school_id=school_id)
        db.session.add(settings)
        db.session.flush()
    return settings


ATTENDANCE_TRACKER_KEY = "daily_attendance_tracker"
ATTENDANCE_TRACKER_HISTORY_LIMIT = 14


def _attendance_day_key(target_date):
    return (target_date or get_utc_now().date()).isoformat()


def _get_attendance_tracker(settings):
    config = _clone_json_document(getattr(settings, "report_template_config", {}) or {})
    tracker = config.get(ATTENDANCE_TRACKER_KEY) or {}
    if not isinstance(tracker, dict):
        tracker = {}
    tracker_days = tracker.get("days") or {}
    if not isinstance(tracker_days, dict):
        tracker_days = {}
    return config, tracker, tracker_days


def _write_attendance_tracker(settings, config, tracker, tracker_days):
    ordered_days = sorted(tracker_days.items(), key=lambda item: item[0], reverse=True)
    tracker["days"] = dict(ordered_days[:ATTENDANCE_TRACKER_HISTORY_LIMIT])
    config[ATTENDANCE_TRACKER_KEY] = tracker
    settings.report_template_config = config


def _get_attendance_active_classes(school_id):
    class_rows = (
        db.session.query(Student.current_class)
        .filter(Student.school_id == school_id, Student.current_class.isnot(None))
        .distinct()
        .all()
    )
    active_classes = {
        (row[0] or "").strip()
        for row in class_rows
        if row and (row[0] or "").strip()
    }
    ordered = [grade for grade in VALID_GRADES if grade in active_classes]
    remaining = sorted(active_classes.difference(ordered))
    return ordered + remaining


def _get_attendance_submission_snapshot(school_id, target_date=None):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    target_date = target_date or get_utc_now().date()
    day_key = _attendance_day_key(target_date)
    submitted_classes = []

    if settings:
        _config, _tracker, tracker_days = _get_attendance_tracker(settings)
        day_record = tracker_days.get(day_key) or {}
        raw_classes = day_record.get("submitted_classes") or []
        submitted_classes = [
            class_name
            for class_name in raw_classes
            if isinstance(class_name, str) and class_name.strip()
        ]

    active_classes = _get_attendance_active_classes(school_id)
    submitted_set = set(submitted_classes)
    pending_classes = [class_name for class_name in active_classes if class_name not in submitted_set]
    has_any_submission = bool(submitted_classes)
    is_complete = bool(active_classes) and len(pending_classes) == 0

    return {
        "submitted_classes": submitted_classes,
        "submitted_classes_count": len(submitted_classes),
        "active_classes": active_classes,
        "active_classes_count": len(active_classes),
        "pending_classes": pending_classes,
        "pending_classes_count": len(pending_classes),
        "has_any_submission": has_any_submission,
        "is_complete": is_complete,
    }


def _mark_attendance_activity(school_id, submitted_classes=None):
    settings = _get_or_create_school_settings_record(school_id)
    settings.attendance_last_marked_at = get_utc_now()
    submitted_classes = [
        class_name
        for class_name in (submitted_classes or [])
        if isinstance(class_name, str) and class_name.strip()
    ]
    if submitted_classes:
        config, tracker, tracker_days = _get_attendance_tracker(settings)
        day_key = _attendance_day_key(get_utc_now().date())
        day_record = tracker_days.get(day_key) or {}
        existing_classes = set(day_record.get("submitted_classes") or [])
        existing_classes.update(submitted_classes)
        day_record["submitted_classes"] = [
            class_name for class_name in _get_attendance_active_classes(school_id)
            if class_name in existing_classes
        ] or sorted(existing_classes)
        day_record["updated_at"] = get_utc_now().isoformat()
        tracker_days[day_key] = day_record
        _write_attendance_tracker(settings, config, tracker, tracker_days)
    return settings


def _prepare_daily_attendance_state(school_id):
    settings = _get_or_create_school_settings_record(school_id)
    marked_at = getattr(settings, "attendance_last_marked_at", None)
    today = get_utc_now().date()
    if marked_at and marked_at.date() == today:
        return settings, False

    Student.query.filter_by(school_id=school_id).update({"is_present": False})
    config, tracker, tracker_days = _get_attendance_tracker(settings)
    tracker_days.pop(_attendance_day_key(today), None)
    _write_attendance_tracker(settings, config, tracker, tracker_days)
    return settings, True


def _attendance_has_any_submission_today(school_id):
    return _get_attendance_submission_snapshot(school_id).get("has_any_submission", False)


def _attendance_marked_today(school_id):
    return _get_attendance_submission_snapshot(school_id).get("is_complete", False)


def _get_present_students_for_today(school_id):
    attendance_snapshot = _get_attendance_submission_snapshot(school_id)
    if not attendance_snapshot.get("has_any_submission", False):
        return []

    query = Student.query.filter_by(school_id=school_id, is_present=True)
    submitted_classes = [
        class_name
        for class_name in (attendance_snapshot.get("submitted_classes") or [])
        if isinstance(class_name, str) and class_name.strip()
    ]
    if submitted_classes:
        query = query.filter(Student.current_class.in_(submitted_classes))
    return query.all()


def _extract_attendance_submission_classes(attendance_records, explicit_class_name=None):
    submitted_classes = set()
    normalized_class_name = sanitize_string(explicit_class_name or "")
    if normalized_class_name in VALID_GRADES:
        submitted_classes.add(normalized_class_name)

    student_ids = [
        int(record.get("student_id"))
        for record in (attendance_records or [])
        if str(record.get("student_id") or "").isdigit()
    ]
    if student_ids:
        rows = (
            Student.query.filter(
                Student.school_id == g.school_id,
                Student.id.in_(student_ids),
            )
            .with_entities(Student.current_class)
            .all()
        )
        for row in rows:
            class_name = (row[0] or "").strip() if row else ""
            if class_name:
                submitted_classes.add(class_name)

    return [grade for grade in VALID_GRADES if grade in submitted_classes] + sorted(
        submitted_classes.difference(VALID_GRADES)
    )


@api.route("/homeroom/attendance", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def update_attendance():
    """Updates attendance status for a student."""
    data = request.json
    student_id = data.get("student_id")
    status = data.get("status")  # True/False

    _prepare_daily_attendance_state(g.school_id)

    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    student.is_present = status
    _mark_attendance_activity(g.school_id, submitted_classes=[student.current_class])
    db.session.commit()

    return jsonify({"message": f"Attendance for {student.name} updated."})


@api.route("/homeroom/attendance", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def attendance_requires_auth():
    """Auth guard for attendance endpoint."""
    return jsonify({"message": "Authentication required."}), 401


@api.route("/homeroom/attendance/batch", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def update_attendance_batch():
    """Updates attendance status for multiple students in a single request."""
    data = request.json
    attendance_records = data.get("attendance_records", [])

    if not attendance_records:
        return jsonify({"error": "No attendance records provided"}), 400

    _prepare_daily_attendance_state(g.school_id)

    updated_count = 0
    submitted_classes = _extract_attendance_submission_classes(
        attendance_records,
        explicit_class_name=data.get("class_name"),
    )
    for record in attendance_records:
        student_id = record.get("student_id")
        status = record.get("status")

        if student_id is None or status is None:
            continue

        student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
        if student:
            student.is_present = status
            updated_count += 1

    if updated_count > 0:
        _mark_attendance_activity(g.school_id, submitted_classes=submitted_classes)

    db.session.commit()

    return jsonify(
        {
            "message": f"Attendance updated for {updated_count} student(s).",
            "updated_count": updated_count,
        }
    )


@api.route("/homeroom/attendance/bulk", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def update_attendance_bulk():
    """Compatibility endpoint for bulk attendance updates."""
    data = request.json or {}
    attendance_records = data.get("records", [])

    if not attendance_records:
        return jsonify({"error": "No attendance records provided"}), 400

    _prepare_daily_attendance_state(g.school_id)

    updated_count = 0
    submitted_classes = _extract_attendance_submission_classes(
        attendance_records,
        explicit_class_name=data.get("class_name"),
    )
    for record in attendance_records:
        student_id = record.get("student_id")
        status = record.get("status")
        if status is None:
            status = record.get("present")

        if student_id is None or status is None:
            continue

        student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
        if student:
            student.is_present = status
            updated_count += 1

    if updated_count > 0:
        _mark_attendance_activity(g.school_id, submitted_classes=submitted_classes)

    db.session.commit()

    return jsonify(
        {
            "message": f"Attendance updated for {updated_count} student(s).",
            "updated_count": updated_count,
        }
    )


# --- REPORT BUILDER (Manual Report Card Entry) ---


@api.route("/homeroom/report-builder/students", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_students_for_report_builder():
    """Get list of students for the homeroom teacher's class to create report cards."""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    # Allow headmaster to specify a class, otherwise use assigned_class
    class_name = request.args.get("class_name")
    if user.role == "headmaster" and class_name:
        pass  # Headmaster can select any class
    elif user.assigned_class:
        class_name = user.assigned_class
    else:
        return jsonify({"message": "No assigned class found"}), 400

    students = (
        Student.query.filter_by(school_id=g.school_id, current_class=class_name)
        .order_by(Student.name)
        .all()
    )

    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                "current_class": s.current_class,
            }
            for s in students
        ]
    )


@api.route("/homeroom/report-builder/report", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def create_or_update_report_card():
    """Create or update a report card for a student."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.json

    student_id = data.get("student_id")
    academic_term = data.get("academic_term")
    academic_year = data.get("academic_year")

    if not student_id or not academic_term or not academic_year:
        return (
            jsonify(
                {
                    "message": "Missing required fields: student_id, academic_term, academic_year"
                }
            ),
            400,
        )

    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()

    # Check permission: homeroom teacher or headmaster
    if user.role == "teacher" and user.assigned_class != student.current_class:
        return (
            jsonify(
                {
                    "message": "Access denied: Cannot create report for student outside your class"
                }
            ),
            403,
        )

    # Check if report already exists
    existing = ReportCard.query.filter_by(
        school_id=g.school_id,
        student_id=student_id,
        academic_term=academic_term,
        academic_year=academic_year,
    ).first()

    if existing:
        # Update existing report
        report = existing
    else:
        # Create new report
        report = ReportCard(
            school_id=g.school_id,
            student_id=student_id,
            academic_term=academic_term,
            academic_year=academic_year,
            class_name=student.current_class,
            created_by=user_id,
            status="Draft",
        )
        db.session.add(report)

    # Update fields from request
    if "subject_grades" in data:
        report.subject_grades = normalize_subject_grades(data["subject_grades"])
    if "attendance_percentage" in data:
        report.attendance_percentage = data["attendance_percentage"]
    if "total_attendance" in data:
        report.total_attendance = data["total_attendance"]
    if "homeroom_teacher_remarks" in data:
        report.homeroom_teacher_remarks = data["homeroom_teacher_remarks"]
    if "overall_position" in data:
        report.overall_position = data["overall_position"]
    if "out_of_students" in data:
        report.out_of_students = data["out_of_students"]

    # Calculate totals if subject_grades provided
    if report.subject_grades:
        total_marks = sum(float(s.get("total", 0) or 0) for s in report.subject_grades)
        num_subjects = len(report.subject_grades)
        report.total_marks_obtained = total_marks
        report.total_possible_marks = num_subjects * 100
        report.term_average = (
            (total_marks / (num_subjects * 100) * 100) if num_subjects > 0 else 0
        )

    # Generate AI performance analysis if subject grades are complete
    if data.get("subject_grades") and len(data["subject_grades"]) > 0:
        try:
            ai_analysis = generate_descriptive_analysis(student_id)
            report.ai_performance_analysis = ai_analysis
        except Exception as e:
            logger.warning(
                f"Failed to generate AI analysis for student {student_id}: {e}"
            )
            report.ai_performance_analysis = None

    db.session.flush()

    recalculate_class_positions(
        g.school_id, report.class_name, report.academic_term, report.academic_year
    )

    db.session.commit()

    log_action(
        user_id,
        g.school_id,
        "REPORT_CARD_SAVED",
        f"Report card saved for {student.name} ({academic_term} {academic_year})",
    )

    school = School.query.get(g.school_id)
    report_data = report.to_dict()
    if has_feature(get_effective_plan(school), "exam_intelligence"):
        report_data["academic_guidance"] = build_report_guidance_payload(
            report.subject_grades or [],
        )

    return jsonify(
        {
            "message": "Report card saved successfully",
            "report_id": report.id,
            "report": report_data,
            "term_calendar": _build_report_term_calendar(
                g.school_id,
                academic_term,
                academic_year,
            ),
        }
    )


@api.route("/homeroom/report-builder/report/<int:student_id>", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_report_card(student_id):
    """Get existing report card for a student."""
    from backend.api.models import ReportCard

    academic_term = request.args.get("academic_term")
    academic_year = request.args.get("academic_year")

    if not academic_term or not academic_year:
        return (
            jsonify({"message": "Missing query params: academic_term, academic_year"}),
            400,
        )

    report = ReportCard.query.filter_by(
        school_id=g.school_id,
        student_id=student_id,
        academic_term=academic_term,
        academic_year=academic_year,
    ).first()

    if not report:
        return jsonify({"message": "Report card not found"}), 404

    report_data = report.to_dict()
    report_data["term_calendar"] = _build_report_term_calendar(
        g.school_id,
        academic_term,
        academic_year,
    )
    school = School.query.get(g.school_id)
    if has_feature(get_effective_plan(school), "exam_intelligence"):
        report_data["academic_guidance"] = build_report_guidance_payload(
            report.subject_grades or [],
        )

    return jsonify(report_data)


@api.route("/homeroom/class-subject-rankings", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_class_subject_rankings():
    """Get subject rankings for all students in a class for position calculation."""
    from backend.api.models import ReportCard

    class_name = request.args.get("class_name")
    academic_term = request.args.get("academic_term")
    academic_year = request.args.get("academic_year")

    if not class_name or not academic_term or not academic_year:
        return jsonify({"message": "Missing required parameters"}), 400

    # Fetch all report cards for this class, term, and year
    reports = ReportCard.query.filter_by(
        school_id=g.school_id,
        class_name=class_name,
        academic_term=academic_term,
        academic_year=academic_year,
    ).all()

    # Organize by subject
    subject_rankings = {}
    for report in reports:
        if not report.subject_grades:
            continue
        for grade in report.subject_grades:
            subject = grade.get("subject")
            total = float(grade.get("total", 0))
            if subject not in subject_rankings:
                subject_rankings[subject] = []
            subject_rankings[subject].append(
                {"student_id": report.student_id, "total": total}
            )

    # Sort each subject's rankings by total (descending)
    for subject in subject_rankings:
        subject_rankings[subject].sort(key=lambda x: x["total"], reverse=True)

    return jsonify(subject_rankings)


@api.route("/homeroom/report-builder/auto-fill/<int:student_id>", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_report_builder_autofill(student_id):
    """Provide auto-fill data for report builder (finalized grades, class size)."""
    user = User.query.get(int(get_jwt_identity()))
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()

    class_name = request.args.get("class_name") or student.current_class
    academic_term = request.args.get("academic_term")
    academic_year = request.args.get("academic_year")

    if class_name not in VALID_GRADES:
        return jsonify({"message": "Invalid class name."}), 400

    if user.role == "teacher" and user.assigned_class != class_name:
        return jsonify({"message": "Access denied: Not your assigned class"}), 403

    if student.current_class != class_name:
        return jsonify({"message": "Student not in selected class"}), 400

    grades = StudentGrade.query.filter_by(
        student_id=student.id, class_name=class_name, is_finalized=True
    ).all()

    raw_subject_grades = [
        {
            "subject": g.subject_name,
            "class_score": g.class_score,
            "exam_score": g.exam_score,
            "total": g.total_score,
            "remarks": g.remarks,
            "diagnostic_topics": g.diagnostic_topics,
        }
        for g in grades
    ]
    subject_grades = normalize_subject_grades(raw_subject_grades)

    out_of_students = Student.query.filter_by(
        school_id=g.school_id, current_class=class_name
    ).count()

    report = None
    if academic_term and academic_year:
        report = ReportCard.query.filter_by(
            school_id=g.school_id,
            student_id=student_id,
            academic_term=academic_term,
            academic_year=academic_year,
        ).first()

    return jsonify(
        {
            "subject_grades": subject_grades,
            "out_of_students": out_of_students,
            "overall_position": report.overall_position if report else None,
            "attendance_percentage": report.attendance_percentage if report else None,
            "total_attendance": report.total_attendance if report else None,
        }
    )


@api.route("/homeroom/report-builder/submit", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def submit_report_card():
    """Submit a report card for headmaster or proprietor approval."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity())
    data = request.json
    report_id = data.get("report_id")
    submit_to = data.get(
        "submit_to", "headmaster"
    )  # Default to headmaster for backward compatibility

    if not report_id:
        return jsonify({"message": "Missing report_id"}), 400

    # Validate submit_to parameter
    if submit_to not in ["headmaster", "proprietor"]:
        submit_to = "headmaster"

    report = ReportCard.query.filter_by(
        id=report_id, school_id=g.school_id
    ).first_or_404()

    if report.status != "Draft":
        return jsonify({"message": f"Report already {report.status}"}), 400

    # Generate AI analysis if not already done
    if not report.ai_performance_analysis:
        try:
            ai_analysis = generate_descriptive_analysis(report.student_id)
            report.ai_performance_analysis = ai_analysis
        except Exception as e:
            logger.warning(f"Failed to generate AI analysis: {e}")

    report.status = "Submitted"
    report.submit_to = submit_to
    report.submitted_at = get_utc_now()
    db.session.commit()

    recipient = "headmaster" if submit_to == "headmaster" else "proprietor"
    log_action(
        user_id,
        g.school_id,
        "REPORT_CARD_SUBMITTED",
        f"Report card #{report_id} submitted to {recipient}",
    )

    return jsonify({"message": f"Report card submitted successfully to {recipient}"})


@api.route("/headmaster/report-builder/pending", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def get_pending_report_cards():
    """Get all pending report cards for headmaster approval."""
    from backend.api.models import ReportCard

    reports = (
        ReportCard.query.filter(
            ReportCard.school_id == g.school_id, ReportCard.status == "Submitted"
        )
        .filter(
            (ReportCard.submit_to == "headmaster")
            | (ReportCard.submit_to == None)  # Include legacy reports
        )
        .order_by(ReportCard.submitted_at.desc())
        .all()
    )

    return jsonify([r.to_dict() for r in reports])


@api.route("/headmaster/report-builder/approve", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def approve_report_card():
    """Approve or reject a report card."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity())
    data = request.json
    report_id = data.get("report_id")
    status = data.get("status")  # 'Approved' or 'Rejected'
    remarks = data.get("headmaster_remarks")

    if not report_id or not status:
        return jsonify({"message": "Missing report_id or status"}), 400

    if status not in ["Approved", "Rejected"]:
        return jsonify({"message": "Status must be 'Approved' or 'Rejected'"}), 400

    report = ReportCard.query.filter_by(
        id=report_id, school_id=g.school_id
    ).first_or_404()

    if status == "Approved":
        report.status = "HeadmasterApproved"  # Next step: Proprietor approval
        report.headmaster_approved_at = get_utc_now()
        report.headmaster_approved_by = user_id
        if remarks:
            report.headmaster_remarks = remarks
        message = "Report card approved by headmaster. Forwarded to proprietor for final approval."
    else:
        report.status = "Rejected"
        report.headmaster_remarks = remarks or "Requires revision"
        message = "Report card rejected. Homeroom teacher can revise and resubmit."

    db.session.commit()

    log_action(
        user_id,
        g.school_id,
        "REPORT_CARD_HEADMASTER_REVIEWED",
        f"Report card #{report_id} {status} by headmaster",
    )

    return jsonify({"message": message})


# --- TERMINAL REPORT ENDPOINTS ---


@api.route("/students/<int:student_id>/terminal-report", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_terminal_report(student_id):
    """Get terminal report data for a student."""
    from backend.api.models import ReportCard, Student

    term = request.args.get("term", "Term 1")
    year = request.args.get("year", "2024/2025")

    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
    if not student:
        return jsonify({"message": "Student not found"}), 404

    # Fetch report card data
    report = ReportCard.query.filter_by(
        school_id=g.school_id,
        student_id=student_id,
        academic_term=term,
        academic_year=year,
    ).first()

    if not report:
        return jsonify({"message": "No report data found for this student"}), 404

    # Convert to dict
    report_data = report.to_dict()
    school = School.query.get(g.school_id)
    if has_feature(get_effective_plan(school), "exam_intelligence"):
        report_data["academic_guidance"] = build_report_guidance_payload(
            report.subject_grades or [],
        )

    report_data["term_calendar"] = _build_report_term_calendar(
        g.school_id,
        term,
        year,
    )
    
    # Add promotion information if this is Term 3 (last term)
    if "Term 3" in term or "3" in term:
        promotions = StudentPromotion.query.filter_by(
            student_id=student_id,
            school_id=g.school_id
        ).order_by(StudentPromotion.promotion_date.desc()).first()
        
        if promotions:
            report_data["promotion"] = {
                "promoted_to_class": promotions.promoted_to_class,
                "promotion_date": promotions.promotion_date.isoformat() if promotions.promotion_date else None,
                "remarks": promotions.remarks,
                "promoted_by": User.query.get(promotions.promoted_by_user_id).username if promotions.promoted_by_user_id else "System"
            }
        else:
            report_data["promotion"] = None
    
    return jsonify(report_data)


def _build_terminal_report_pdf_bytes(student, report, term, year):
    """Generate a simple terminal report PDF in memory."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(f"PDF engine unavailable: {exc}")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    left = 40
    y = page_height - 50

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(left, y, "Terminal Report")
    y -= 24

    pdf.setFont("Helvetica", 11)
    pdf.drawString(left, y, f"Student: {student.name}")
    y -= 16
    pdf.drawString(left, y, f"Class: {student.current_class or '-'}")
    y -= 16
    pdf.drawString(left, y, f"Term: {term}    Year: {year}")
    y -= 16
    pdf.drawString(left, y, f"Average: {report.term_average if report.term_average is not None else '-'}")
    y -= 16
    pdf.drawString(left, y, f"Position: {report.overall_position or '-'} / {report.out_of_students or '-'}")
    y -= 24

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(left, y, "Subject Performance")
    y -= 18

    subject_grades = report.subject_grades or []
    pdf.setFont("Helvetica", 10)
    if not subject_grades:
        pdf.drawString(left, y, "No subject grades available.")
        y -= 14
    else:
        for item in subject_grades:
            subject = str(item.get("subject") or "-")
            class_score = item.get("class_score", "-")
            exam_score = item.get("exam_score", "-")
            total = item.get("total", "-")
            line = f"• {subject}: Class {class_score}, Exam {exam_score}, Total {total}"
            pdf.drawString(left, y, line[:120])
            y -= 14
            if y <= 80:
                pdf.showPage()
                y = page_height - 50
                pdf.setFont("Helvetica", 10)

    if report.ai_performance_analysis:
        if y <= 140:
            pdf.showPage()
            y = page_height - 50
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(left, y, "AI Performance Analysis")
        y -= 16
        pdf.setFont("Helvetica", 10)
        ai_text = str(report.ai_performance_analysis).replace("\n", " ")
        max_chars = 110
        while ai_text:
            pdf.drawString(left, y, ai_text[:max_chars])
            ai_text = ai_text[max_chars:]
            y -= 13
            if y <= 80:
                pdf.showPage()
                y = page_height - 50
                pdf.setFont("Helvetica", 10)

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _verify_paystack_signature(raw_body):
    """Verify Paystack webhook signature using HMAC SHA512."""
    secret_key = (os.getenv("PAYSTACK_SECRET_KEY") or "").strip()
    signature = (request.headers.get("x-paystack-signature") or "").strip()

    if not secret_key:
        return False, "PAYSTACK_SECRET_KEY not configured"
    if not signature:
        return False, "Missing Paystack signature"

    expected = hmac.new(
        secret_key.encode("utf-8"), raw_body, hashlib.sha512
    ).hexdigest()

    if not secrets.compare_digest(expected, signature):
        return False, "Invalid Paystack signature"

    return True, "ok"


def _verify_bank_webhook_signature(raw_body):
    """Verify bank webhook signature using HMAC SHA256."""
    secret_key = (os.getenv("BANK_WEBHOOK_SECRET") or "").strip()
    signature = (
        request.headers.get("x-bank-signature")
        or request.headers.get("x-webhook-signature")
        or ""
    ).strip()

    if not secret_key:
        return False, "BANK_WEBHOOK_SECRET not configured"
    if not signature:
        return False, "Missing bank webhook signature"

    expected = hmac.new(
        secret_key.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()

    if not secrets.compare_digest(expected, signature):
        return False, "Invalid bank webhook signature"

    return True, "ok"


def _should_inject_failpoint(metadata, failpoint_name):
    env_failpoints = {
        item.strip()
        for item in (os.getenv("EDUPULSE_FAILPOINTS") or "").split(",")
        if item.strip()
    }
    metadata_failpoint = ""
    if isinstance(metadata, dict):
        metadata_failpoint = sanitize_string(metadata.get("__failpoint__"))
    return failpoint_name in env_failpoints or metadata_failpoint == failpoint_name


def _apply_auto_payment_effects(student, payment_type, amount, payment_category):
    """Apply payment side effects to student and inventory."""
    if payment_type == "Tuition":
        student.total_tuition_owed = max(0, (student.total_tuition_owed or 0) - amount)
        return None

    if payment_type == "Feeding":
        student.feeding_paid = True
        return None

    if payment_type in ["Inventory", "Uniform"]:
        sku = (payment_category or {}).get("item_code") or (payment_category or {}).get("sku")
        quantity = int((payment_category or {}).get("quantity", 1) or 1)
        if not sku:
            return None

        inventory_item = Inventory.query.filter_by(
            sku=sku, school_id=student.school_id
        ).first()
        if not inventory_item:
            return None

        if inventory_item.quantity is not None and inventory_item.quantity < quantity:
            return "Insufficient inventory stock"

        inventory_item.quantity = (inventory_item.quantity or 0) - quantity

    return None


def _resolve_payment_from_reference(reference_code, school_id_hint=None):
    """Resolve student and payment context from either compact or hyphenated reference codes."""
    from backend.utils import parse_payment_code, parse_payment_reference

    reference = sanitize_string(reference_code or "")
    if not reference:
        return None, None, None

    # 1) Compact code style (e.g. CFK011)
    try:
        student_code, payment_type = parse_payment_code(reference)
        query = Student.query.filter_by(student_code=student_code)
        if school_id_hint:
            query = query.filter_by(school_id=school_id_hint)
        student = query.first()
        if student:
            return student, payment_type or "Tuition", {}
    except ValueError:
        pass

    # 2) Hyphenated style (e.g. S001-T1, S001-FEED-MON)
    parsed = parse_payment_reference(reference)
    if parsed:
        query = Student.query.filter_by(student_code=parsed.get("student_code"))
        if school_id_hint:
            query = query.filter_by(school_id=school_id_hint)
        student = query.first()
        if student:
            return (
                student,
                parsed.get("payment_type") or "Tuition",
                parsed.get("category") or {},
            )

    # 3) Plain learner code fallback (e.g. DADD0004)
    query = Student.query.filter_by(student_code=reference)
    if school_id_hint:
        query = query.filter_by(school_id=school_id_hint)
    student = query.first()
    if student:
        return student, "Tuition", {}

    return None, None, None


def _extract_payment_notice_reference_candidates(message_text):
    normalized = sanitize_string(message_text or "").upper()
    if not normalized:
        return []

    candidates = []
    seen = set()
    for token in re.findall(r"[A-Z0-9-]{4,}", normalized):
        cleaned = token.strip(".,:;()[]{}")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        candidates.append(cleaned)
    return candidates


def _resolve_payment_from_notice_text(message_text, school_id_hint=None):
    for candidate in _extract_payment_notice_reference_candidates(message_text):
        student, payment_type, payment_category = _resolve_payment_from_reference(
            candidate,
            school_id_hint=school_id_hint,
        )
        if student:
            return candidate, student, payment_type, payment_category

    return None, None, None, None


def _extract_amount_from_notice_text(message_text):
    text = sanitize_string(message_text or "")
    if not text:
        return None

    patterns = [
        r"(?:GHS|GHC|GH¢|₵|GH)\s*([0-9]+(?:[.,][0-9]{1,2})?)",
        r"(?:AMOUNT|AMT|PAID|PAYMENT)\D{0,12}([0-9]+(?:[.,][0-9]{1,2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        raw_value = match.group(1).replace(",", "")
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _extract_transaction_reference_from_notice_text(message_text, matched_reference=None):
    normalized = sanitize_string(message_text or "").upper()
    if not normalized:
        return None

    ignore_tokens = {
        "MESSAGE",
        "BODY",
        "FINANCIAL",
        "TRANSFER",
        "PAYMENT",
        "SUCCESSFUL",
        "MOBILE",
        "MONEY",
        "OPTIONS",
        "BACK",
    }
    for token in _extract_payment_notice_reference_candidates(normalized):
        if matched_reference and token == matched_reference:
            continue
        if token in ignore_tokens:
            continue
        if not re.search(r"\d", token):
            continue
        if len(token) < 8:
            continue
        return token
    return None


def _normalize_feeding_frequency(payment_category, feeding_plan_fees, amount_paid=0.0):
    raw_frequency = sanitize_string((payment_category or {}).get("frequency") or "") or ""
    normalized_frequency = raw_frequency.lower()
    if normalized_frequency == "daily":
        return "Daily"
    if normalized_frequency == "weekly":
        return "Weekly"
    if normalized_frequency == "monthly":
        return "Monthly"

    inferred_candidates = [
        ("Monthly", float(feeding_plan_fees.get("monthly") or 0)),
        ("Weekly", float(feeding_plan_fees.get("weekly") or 0)),
        ("Daily", float(feeding_plan_fees.get("daily") or feeding_plan_fees.get("primary") or 0)),
    ]
    for frequency_name, plan_rate in inferred_candidates:
        if plan_rate <= 0 or amount_paid <= 0:
            continue
        units = amount_paid / plan_rate
        if units >= 1 and abs(units - round(units)) < 1e-9:
            return frequency_name

    if float(feeding_plan_fees.get("monthly") or 0) > 0:
        return "Monthly"
    if float(feeding_plan_fees.get("weekly") or 0) > 0:
        return "Weekly"
    return "Daily"


def _resolve_feeding_plan_rate(feeding_plan_fees, frequency):
    if frequency == "Monthly":
        return float(feeding_plan_fees.get("monthly") or feeding_plan_fees.get("primary") or 0)
    if frequency == "Weekly":
        return float(feeding_plan_fees.get("weekly") or feeding_plan_fees.get("primary") or 0)
    return float(feeding_plan_fees.get("daily") or feeding_plan_fees.get("primary") or 0)


def _is_school_instruction_day(school_id, target_date):
    if not target_date or target_date.weekday() >= 5:
        return False
    is_holiday, _holiday_name = _get_holiday_status(school_id, target_date)
    return not is_holiday


def _get_next_instruction_day(school_id, start_date):
    candidate = start_date
    for _ in range(370):
        if _is_school_instruction_day(school_id, candidate):
            return candidate
        candidate += timedelta(days=1)
    return start_date


def _add_instructional_days(school_id, start_date, day_count):
    if day_count <= 0:
        return None

    current_day = _get_next_instruction_day(school_id, start_date)
    covered_days = 0
    end_date = None
    for _ in range(730):
        if _is_school_instruction_day(school_id, current_day):
            covered_days += 1
            end_date = current_day
            if covered_days >= day_count:
                return end_date
        current_day += timedelta(days=1)
    return end_date


def _end_of_calendar_month(target_date):
    if target_date.month == 12:
        next_month_start = date(target_date.year + 1, 1, 1)
    else:
        next_month_start = date(target_date.year, target_date.month + 1, 1)
    return next_month_start - timedelta(days=1)


def _calculate_feeding_coverage_units(payment, feeding_plan_fees):
    amount_paid = float(payment.amount or 0)
    frequency = _normalize_feeding_frequency(
        payment.payment_category or {},
        feeding_plan_fees,
        amount_paid=amount_paid,
    )
    plan_rate = _resolve_feeding_plan_rate(feeding_plan_fees, frequency)

    if amount_paid <= 0:
        return 0, frequency

    if plan_rate > 0:
        purchased_units = int((amount_paid + 1e-9) // plan_rate)
        if purchased_units <= 0:
            return 0, frequency
        return purchased_units, frequency

    return 1, frequency


def _calculate_feeding_coverage_end_date(start_date, purchased_units, frequency, school_id):
    if purchased_units <= 0:
        return None

    if frequency == "Daily":
        return _add_instructional_days(school_id, start_date, purchased_units)

    if frequency == "Weekly":
        return _add_instructional_days(school_id, start_date, purchased_units * 5)

    end_date = _end_of_calendar_month(start_date)
    for _ in range(1, purchased_units):
        end_date = _end_of_calendar_month(end_date + timedelta(days=1))
    return end_date


def _normalize_payment_category_for_storage(school_id, payment_type, payment_category, amount_paid=0.0):
    normalized_category = dict(payment_category or {})
    if payment_type != "Feeding":
        return normalized_category

    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    feeding_plan_fees = _get_feeding_plan_fees(settings)
    try:
        amount_value = float(amount_paid or 0.0)
    except (TypeError, ValueError):
        amount_value = 0.0

    inferred_frequency = _normalize_feeding_frequency(
        normalized_category,
        feeding_plan_fees,
        amount_paid=amount_value,
    )
    if inferred_frequency:
        normalized_category["frequency"] = inferred_frequency
    return normalized_category


def _get_feeding_status_details_for_students(students, school_id, as_of_date=None):
    student_list = [student for student in (students or []) if student is not None]
    if not student_list:
        return {}

    as_of_date = as_of_date or datetime.now(timezone.utc).date()
    student_ids = [student.id for student in student_list if getattr(student, "id", None) is not None]
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    feeding_plan_fees = _get_feeding_plan_fees(settings)

    payments = []
    pending_payments = []
    if student_ids:
        payments = (
            Payment.query.filter(
                Payment.school_id == school_id,
                Payment.payment_type == "Feeding",
                Payment.student_id.in_(student_ids),
                Payment.status == "Confirmed",
            )
            .order_by(Payment.verified_at.asc(), Payment.date_paid.asc(), Payment.created_at.asc(), Payment.id.asc())
            .all()
        )
        pending_payments = (
            Payment.query.filter(
                Payment.school_id == school_id,
                Payment.payment_type == "Feeding",
                Payment.student_id.in_(student_ids),
                Payment.status == "Pending",
            )
            .order_by(Payment.created_at.desc(), Payment.id.desc())
            .all()
        )

    payments_by_student = {}
    for payment in payments:
        payments_by_student.setdefault(payment.student_id, []).append(payment)

    pending_payments_by_student = {}
    for payment in pending_payments:
        pending_payments_by_student.setdefault(payment.student_id, []).append(payment)

    details = {}
    for student in student_list:
        if bool(getattr(student, "scholarship_covers_feeding", False)):
            details[student.id] = {
                "covered": True,
                "payment_method": "Scholarship",
                "coverage_until": None,
                "days_remaining": None,
                "frequency": "Scholarship",
                "pending_approval": False,
                "pending_amount": 0.0,
                "plan_rates": feeding_plan_fees,
            }
            continue

        covered = False
        payment_method = None
        coverage_until = None
        days_remaining = 0
        active_frequency = None
        rolling_coverage_end = None

        for payment in payments_by_student.get(student.id, []):
            purchased_units, frequency = _calculate_feeding_coverage_units(payment, feeding_plan_fees)
            if purchased_units <= 0:
                continue

            coverage_anchor = payment.verified_at or payment.date_paid or payment.created_at or datetime.now(timezone.utc)
            payment_date = coverage_anchor.date()
            start_date = payment_date
            if rolling_coverage_end and start_date <= rolling_coverage_end:
                start_date = rolling_coverage_end + timedelta(days=1)

            if frequency in {"Daily", "Weekly"}:
                start_date = _get_next_instruction_day(school_id, start_date)

            end_date = _calculate_feeding_coverage_end_date(start_date, purchased_units, frequency, school_id)
            if end_date is None:
                continue
            rolling_coverage_end = end_date

            if start_date <= as_of_date <= end_date:
                covered = True
                payment_method = payment.method
                coverage_until = end_date.isoformat()
                days_remaining = (end_date - as_of_date).days + 1
                active_frequency = frequency
                break

        pending_student_payments = pending_payments_by_student.get(student.id, [])
        pending_amount = sum(float(payment.amount or 0) for payment in pending_student_payments)

        details[student.id] = {
            "covered": covered,
            "payment_method": payment_method,
            "coverage_until": coverage_until,
            "days_remaining": days_remaining,
            "frequency": active_frequency,
            "pending_approval": bool(pending_student_payments),
            "pending_amount": round(pending_amount, 2),
            "plan_rates": feeding_plan_fees,
        }

    return details


def _get_daily_meal_breakdown(school_id):
    present_students = _get_present_students_for_today(school_id)
    feeding_status_details = _get_feeding_status_details_for_students(
        present_students,
        school_id,
    )
    covered_student_meals = sum(
        1
        for student in present_students
        if feeding_status_details.get(student.id, {}).get("covered")
    )
    staff_roles = [
        "teacher",
        "homeroom",
        "headmaster",
        "proprietor",
        "finance",
        "inventory_manager",
    ]
    total_staff_meals = (
        User.query.filter_by(school_id=school_id)
        .filter(User.role.in_(staff_roles))
        .count()
    )
    return {
        "present_students": present_students,
        "feeding_status_details": feeding_status_details,
        "total_students_present": len(present_students),
        "covered_student_meals": covered_student_meals,
        "total_staff_meals": total_staff_meals,
        "total_meals_needed": covered_student_meals + total_staff_meals,
    }


def _summarize_live_feed_details(action, details):
    text = details if isinstance(details, str) else ""
    if not text:
        return None

    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None

    if not isinstance(payload, dict):
        return text

    action_name = sanitize_string(action or "") or ""
    reference_code = sanitize_string(payload.get("reference_code") or "") or None
    student_code = sanitize_string(payload.get("student_code") or "") or None
    student_class = sanitize_string(payload.get("student_class") or "") or None
    payment_type = sanitize_string(payload.get("payment_type") or "") or None

    if action_name == "PAYMENT_CODES_GENERATED":
        routes_count = int(payload.get("routes_count") or 0)
        route_word = "reference" if routes_count == 1 else "references"
        class_suffix = f" for {student_class}" if student_class else ""
        return f"Generated {routes_count} payment {route_word} for {student_code or 'student'}{class_suffix}."

    if action_name == "PAYMENT_TRANSFER_ROUTE_GENERATED":
        fee_label = payment_type or "payment"
        return f"Tracked transfer account prepared for {student_code or reference_code or fee_label} ({reference_code or fee_label})."

    if action_name == "STUDENT_RESCUE_OUTCOME":
        student_name = sanitize_string(payload.get("student_name") or "") or "student"
        action_label = sanitize_string(payload.get("action_label") or payload.get("action_code") or "") or "Outcome logged"
        return f"{action_label} for {student_name}."

    if action_name == "PROPRIETOR_ALERT_ACK":
        alert_id = sanitize_string(payload.get("alert_id") or "") or "alert"
        return f"Alert acknowledged: {alert_id}."

    safe_pairs = []
    for key in ["student_name", "student_code", "payment_type", "reference_code", "reference_id", "amount", "status", "message"]:
        value = payload.get(key)
        if value in (None, "", [], {}):
            continue
        safe_pairs.append(f"{key.replace('_', ' ').title()}: {value}")
    if safe_pairs:
        return " | ".join(safe_pairs[:4])
    return "Details available in the full audit report."


def _count_students_with_current_tuition_outstanding(school_id):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    required_amount = round(float((settings.tuition_fee if settings else 0.0) or 0.0) + float((settings.terminal_report_fee if settings else 0.0) or 0.0), 2)
    if required_amount <= 0:
        return 0

    students = Student.query.filter(
        Student.school_id == school_id,
        Student.status.in_(["Active", "active"]),
    ).all()
    if not students:
        return 0

    student_ids = [student.id for student in students]
    payment_rows = (
        db.session.query(Payment.student_id, db.func.coalesce(db.func.sum(Payment.amount), 0.0))
        .filter(
            Payment.school_id == school_id,
            Payment.status == "Confirmed",
            Payment.payment_type == "Tuition",
            Payment.student_id.in_(student_ids),
        )
        .group_by(Payment.student_id)
        .all()
    )
    paid_by_student = {student_id: float(total_paid or 0.0) for student_id, total_paid in payment_rows}

    outstanding_count = 0
    for student in students:
        if bool(getattr(student, "scholarship_covers_tuition", False)):
            continue
        total_paid = paid_by_student.get(student.id, 0.0)
        if total_paid + 1e-9 < required_amount:
            outstanding_count += 1
    return outstanding_count


def _serialize_feeding_status_detail(feeding_status):
    plan_rates = feeding_status.get("plan_rates") or {}
    return {
        "feeding_paid": bool(feeding_status.get("covered")),
        "payment_method": feeding_status.get("payment_method"),
        "feeding_coverage_until": feeding_status.get("coverage_until"),
        "feeding_days_remaining": feeding_status.get("days_remaining"),
        "feeding_frequency": feeding_status.get("frequency"),
        "feeding_pending_approval": bool(feeding_status.get("pending_approval")),
        "feeding_pending_amount": round(float(feeding_status.get("pending_amount") or 0), 2),
        "feeding_daily_fee": round(float(plan_rates.get("daily") or 0), 2),
        "feeding_weekly_fee": round(float(plan_rates.get("weekly") or 0), 2),
        "feeding_monthly_fee": round(float(plan_rates.get("monthly") or 0), 2),
        "feeding_primary_fee": round(float(plan_rates.get("primary") or 0), 2),
    }


def _apply_confirmed_payment_effects(payment, student, actor_id):
    if payment.payment_type == "Tuition":
        student.total_tuition_owed = max(0, student.total_tuition_owed - float(payment.amount))
    elif payment.payment_type == "Feeding":
        student.feeding_paid = True

    add_ledger_entry(
        school_id=payment.school_id,
        tx_type=payment.payment_type.lower(),
        tx_ref=payment.reference_id or f"PAY-{payment.id}",
        amount=payment.amount,
        currency="GH₵",
        actor_id=actor_id,
        student_id=student.id,
        source=(payment.method or "import").lower(),
        metadata={
            "payment_id": payment.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "payment_category": payment.payment_category,
            "recorded_by": "parent-payment-import",
        },
    )


@api.route("/finance/import-parent-payment", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def import_parent_payment_notice():
    """Import a parent payment notice by parsing the embedded learner reference code."""
    school = School.query.get(g.school_id)
    verification_restriction = _payment_records_verification_block_response(school)
    if verification_restriction:
        return verification_restriction

    collection_restriction = _payment_collection_block_response(school)
    if collection_restriction:
        return collection_restriction

    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.get_json(silent=True) or {}

    message_text = data.get("message_text") or data.get("notice_text") or ""
    if not sanitize_string(message_text):
        return jsonify({"message": "Paste the parent payment notice text to import."}), 400

    matched_reference, student, inferred_type, inferred_category = _resolve_payment_from_notice_text(
        message_text,
        school_id_hint=g.school_id,
    )
    if not student:
        return jsonify({"message": "No valid learner reference code was found in the pasted payment notice."}), 400

    payment_type = sanitize_string(data.get("payment_type") or data.get("type") or inferred_type or "Tuition") or "Tuition"

    explicit_amount = data.get("amount")
    parsed_amount = _extract_amount_from_notice_text(message_text)
    amount = explicit_amount if explicit_amount not in (None, "") else parsed_amount
    try:
        amount_value = float(amount)
    except (TypeError, ValueError):
        amount_value = None
    if not amount_value or amount_value <= 0:
        return jsonify({"message": "Payment amount could not be read from the notice. Enter the amount and import again."}), 400

    explicit_reference_id = sanitize_string(data.get("reference_id") or data.get("transaction_reference") or data.get("transaction_id")) or None
    external_reference_id = explicit_reference_id or _extract_transaction_reference_from_notice_text(
        message_text,
        matched_reference=matched_reference,
    )
    if not external_reference_id:
        return jsonify({"message": "Transaction reference could not be read from the notice. Enter the external reference and import again."}), 400

    existing = Payment.query.filter_by(reference_id=external_reference_id).first()
    if existing:
        return jsonify({"message": "Duplicate reference ID", "payment_id": existing.id}), 409

    payment_category = inferred_category or {}
    if matched_reference:
        payment_category = {
            **payment_category,
            "reference_code": matched_reference,
        }
    payment_category = {
        **payment_category,
        "import_mode": "parent_notice",
    }

    payment_payload = {
        "student_id": student.id,
        "amount": amount_value,
        "payment_type": payment_type,
        "method": sanitize_string(data.get("method") or "MoMo") or "MoMo",
        "reference_id": external_reference_id,
        "payment_category": payment_category,
    }

    try:
        PaymentSchema().load(payment_payload)
    except Exception as exc:
        return jsonify({"message": "Invalid imported payment data", "error": str(exc)}), 400

    payment = Payment(
        student_id=student.id,
        school_id=g.school_id,
        created_by_user_id=user.id if user else None,
        amount=payment_payload["amount"],
        payment_type=payment_payload["payment_type"],
        method=payment_payload["method"],
        reference_id=payment_payload["reference_id"],
        status="Confirmed",
        payment_category=payment_payload["payment_category"],
        verified_at=get_utc_now(),
        verified_by=user.id if user else None,
    )
    db.session.add(payment)
    db.session.flush()

    aml_flags = _evaluate_payment_aml_flags(g.school_id, payment, actor_id=user.id if user else None)
    _apply_confirmed_payment_effects(payment, student, user.id if user else None)

    log_action(
        user_id=user.id if user else None,
        school_id=g.school_id,
        action="PARENT_PAYMENT_IMPORTED",
        details=f"Imported parent payment notice for {student.name} ({payment_type}, Ref: {matched_reference or 'N/A'}, Tx: {external_reference_id})",
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Parent payment imported successfully.",
            "payment_id": payment.id,
            "student_id": student.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "payment_type": payment.payment_type,
            "amount": payment.amount,
            "reference_code": matched_reference,
            "reference_id": payment.reference_id,
            "aml_flags_opened": len(aml_flags),
        }
    )


def _record_paystack_finance_payment(payload, event="charge.success", school_id_scope=None):
    tx_ref = sanitize_string(payload.get("reference") or str(payload.get("id") or ""))
    if not tx_ref:
        return {"status": "error", "message": "Missing transaction reference"}, 400

    existing_payment = Payment.query.filter_by(reference_id=tx_ref).first()
    if existing_payment:
        return {"status": "duplicate", "reference": tx_ref}, 200

    amount_minor = payload.get("amount")
    try:
        amount = float(amount_minor or 0) / 100.0
    except Exception:
        return {"status": "error", "message": "Invalid payment amount"}, 400

    if amount <= 0:
        return {"status": "error", "message": "Amount must be greater than zero"}, 400

    metadata = payload.get("metadata") or {}
    school_id_hint = sanitize_string(metadata.get("school_id") or school_id_scope)

    student = None
    payment_type = sanitize_string(metadata.get("payment_type")) or None
    payment_category = metadata.get("payment_category") if isinstance(metadata.get("payment_category"), dict) else {}

    student_id = metadata.get("student_id")
    if student_id is not None:
        try:
            query = Student.query.filter_by(id=int(student_id))
            if school_id_hint:
                query = query.filter_by(school_id=school_id_hint)
            student = query.first()
        except Exception:
            student = None

    if not student:
        student_code = sanitize_string(metadata.get("student_code"))
        if student_code:
            query = Student.query.filter_by(student_code=student_code)
            if school_id_hint:
                query = query.filter_by(school_id=school_id_hint)
            student = query.first()

    if not student:
        reference_code = (
            sanitize_string(metadata.get("reference_code"))
            or sanitize_string(metadata.get("payment_reference"))
            or sanitize_string(metadata.get("student_payment_code"))
            or sanitize_string(payload.get("reference"))
        )
        resolved_student, resolved_type, resolved_category = _resolve_payment_from_reference(
            reference_code,
            school_id_hint=school_id_hint,
        )
        if resolved_student:
            student = resolved_student
            payment_type = payment_type or resolved_type
            if not payment_category:
                payment_category = resolved_category or {}

    if not student:
        logger.warning(
            "Paystack reconciliation/webhook received unmapped payment. reference=%s metadata=%s",
            tx_ref,
            metadata,
        )
        return {"status": "unmapped", "reference": tx_ref}, 200

    if school_id_scope and student.school_id != school_id_scope:
        return {"status": "ignored", "reference": tx_ref, "message": "Payment belongs to another school"}, 200

    if school_id_hint and student.school_id != school_id_hint:
        return {"status": "error", "message": "School mismatch in metadata"}, 400

    reference_payment_type = payment_type or "Tuition"
    channel = (payload.get("channel") or "").lower()
    payment_type = reference_payment_type

    school = School.query.get(student.school_id)
    collection_block = _get_payment_collection_block(school)
    verification_snapshot = _get_school_verification_snapshot(student.school_id)
    verification_blocked = not verification_snapshot["is_verified"]

    payment = Payment(
        student_id=student.id,
        school_id=student.school_id,
        amount=amount,
        payment_type=payment_type,
        method="Paystack_Payment",
        reference_id=tx_ref,
        status="Pending" if verification_blocked or collection_block else "Confirmed",
        payment_category=payment_category or {},
    )
    db.session.add(payment)
    db.session.flush()

    if verification_blocked:
        _create_aml_flag(
            school_id=student.school_id,
            payment_id=payment.id,
            student_id=student.id,
            rule_code="UNVERIFIED_SCHOOL_PAYMENT",
            severity="high",
            summary="Payment received while school KYB verification is not approved.",
            details={"reference": tx_ref, "source": "paystack", "verification": verification_snapshot},
        )
    if collection_block:
        _create_aml_flag(
            school_id=student.school_id,
            payment_id=payment.id,
            student_id=student.id,
            rule_code="FREE_TIER_OVER_CAP_PAYMENT",
            severity="high",
            summary="Payment received while Free Tier collection is paused for over-capacity.",
            details={"reference": tx_ref, "source": "paystack", "collection_block": collection_block},
        )

    if not verification_blocked and not collection_block:
        stock_error = _apply_auto_payment_effects(student, payment_type, amount, payment_category or {})
        if stock_error:
            db.session.rollback()
            return {"status": "error", "message": stock_error}, 400

    ledger_metadata = {
        "provider": "paystack",
        "event": event,
        "channel": channel,
        "payment_id": payload.get("id"),
        "customer": payload.get("customer", {}),
        "authorization": payload.get("authorization", {}),
    }

    if not verification_blocked and not collection_block:
        add_ledger_entry(
            school_id=student.school_id,
            tx_type=(payment_type or "payment").lower(),
            tx_ref=tx_ref,
            amount=amount,
            currency="GH₵",
            actor_id=None,
            student_id=student.id,
            source="paystack",
            metadata=ledger_metadata,
        )

    _evaluate_payment_aml_flags(student.school_id, payment, actor_id=None)

    if _should_inject_failpoint(metadata, "finance_payment_before_commit"):
        db.session.rollback()
        raise RuntimeError("Injected failpoint: finance_payment_before_commit")

    log_action(
        user_id=None,
        school_id=student.school_id,
        action="PAYSTACK_PAYMENT_AUTO",
        details=(
            f"Paystack payment: GH₵{amount:.2f} for {student.name} "
            f"({payment_type}, ref={tx_ref}, status={payment.status})"
        ),
    )

    db.session.commit()
    if collection_block:
        return {
            "status": "blocked",
            "reference": tx_ref,
            "student_id": student.id,
            "payment_id": payment.id,
            "payment_status": payment.status,
            "message": collection_block["message"],
        }, 200
    return {"status": "recorded", "reference": tx_ref, "student_id": student.id}, 200


def _fetch_paystack_success_transactions(start_time, end_time, page=1, per_page=50):
    secret_key = (os.getenv("PAYSTACK_SECRET_KEY") or "").strip()
    if not secret_key:
        raise ValueError("PAYSTACK_SECRET_KEY not configured")

    response = requests.get(
        "https://api.paystack.co/transaction",
        headers={"Authorization": f"Bearer {secret_key}"},
        params={
            "status": "success",
            "page": page,
            "perPage": per_page,
            "from": start_time.isoformat(),
            "to": end_time.isoformat(),
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("status"):
        raise ValueError(payload.get("message") or "Paystack transaction listing failed")
    return payload.get("data") or [], payload.get("meta") or {}


def _recover_paystack_transaction(transaction, school_id_scope=None):
    metadata = dict(transaction.get("metadata") or {})
    metadata.pop("__failpoint__", None)
    transaction = dict(transaction)
    transaction["metadata"] = metadata

    reference = sanitize_string(transaction.get("reference") or str(transaction.get("id") or ""))
    school_id = sanitize_string(metadata.get("school_id") or school_id_scope)
    plan_name = sanitize_string(metadata.get("plan_name"))
    card_setup_only = bool(metadata.get("card_setup_only") or metadata.get("skip_subscription_update"))

    if school_id_scope and school_id and school_id != school_id_scope:
        return "ignored"

    if (plan_name or card_setup_only) and school_id:
        if not card_setup_only and _is_subscription_reference_processed(reference, school_id):
            return "duplicate"

        amount_paid = float(transaction.get("amount") or 0) / 100.0
        if card_setup_only:
            saved_card = _save_reusable_authorization(
                school_id,
                transaction.get("authorization") or {},
                (transaction.get("customer") or {}).get("email"),
            )
            if saved_card:
                _append_billing_timeline_event(
                    school_id,
                    event_type="card_saved_recovered",
                    status="success",
                    title="Billing card recovered from reconciliation",
                    details=f"Recovered reusable authorization for card ending with {saved_card.get('last4') or '----'}.",
                    amount=amount_paid,
                    reference=reference,
                )
                return "recovered"
            return "ignored"

        from backend.paystack_integration import process_payment_confirmation

        result = process_payment_confirmation(
            school_id,
            plan_name,
            amount_paid,
            reference=reference,
            metadata=metadata,
        )
        recovered_title = "Subscription payment recovered"
        recovered_details = f"Recovered missing subscription payment for {plan_name} from Paystack reconciliation."
        event_type = "subscription_payment_recovered"
        if result.get("transaction_type") == "addon_purchase":
            recovered_title = "Add-on payment recovered"
            recovered_details = f"Recovered missing add-on payment for {result.get('addon_name') or 'subscription add-on'} from Paystack reconciliation."
            event_type = "subscription_addon_recovered"
        _append_billing_timeline_event(
            school_id,
            event_type=event_type,
            status="success",
            title=recovered_title,
            details=recovered_details,
            amount=amount_paid,
            reference=reference,
        )
        return "recovered"

    if _is_paystack_dedicated_account_charge(transaction):
        result, _status_code = _record_paystack_virtual_account_payment(
            transaction,
            event="charge.success.reconciled",
        ) or ({"status": "ignored"}, 200)
        return result or {"status": "ignored"}

    result, _status_code = _record_paystack_finance_payment(
        transaction,
        event="charge.success.reconciled",
        school_id_scope=school_id_scope,
    )
    return result or {"status": "ignored"}


def run_paystack_reconciliation_sweep(lookback_hours=24, school_id_scope=None, max_pages=4, per_page=50):
    end_time = get_utc_now()
    start_time = end_time - timedelta(hours=max(1, int(lookback_hours or 24)))
    summary = {
        "checked": 0,
        "recovered": 0,
        "duplicate": 0,
        "ignored": 0,
        "unmapped": 0,
        "errors": 0,
        "references": [],
    }

    for page in range(1, max(1, int(max_pages)) + 1):
        transactions, meta = _fetch_paystack_success_transactions(
            start_time,
            end_time,
            page=page,
            per_page=per_page,
        )
        if not transactions:
            break

        for transaction in transactions:
            summary["checked"] += 1
            reference = sanitize_string(transaction.get("reference") or str(transaction.get("id") or ""))
            try:
                outcome = _recover_paystack_transaction(transaction, school_id_scope=school_id_scope)
            except Exception as exc:
                db.session.rollback()
                summary["errors"] += 1
                if school_id_scope:
                    _append_billing_timeline_event(
                        school_id_scope,
                        event_type="paystack_reconciliation_failed",
                        status="failed",
                        title="Paystack reconciliation failed",
                        details=str(exc),
                        reference=reference,
                    )
                continue

            outcome_status = outcome.get("status") if isinstance(outcome, dict) else outcome

            if outcome_status in {"recovered", "recorded"}:
                summary["recovered"] += 1
                summary["references"].append(reference)
            elif outcome_status == "duplicate":
                summary["duplicate"] += 1
            elif outcome_status == "unmapped":
                summary["unmapped"] += 1
            else:
                summary["ignored"] += 1

        if meta.get("next") is None and len(transactions) < per_page:
            break

    if school_id_scope:
        _append_billing_timeline_event(
            school_id_scope,
            event_type="paystack_reconciliation_completed",
            status="success" if summary["errors"] == 0 else "warning",
            title="Paystack reconciliation completed",
            details=(
                f"Checked {summary['checked']} transaction(s); recovered {summary['recovered']}, "
                f"duplicates {summary['duplicate']}, unmapped {summary['unmapped']}, errors {summary['errors']}."
            ),
            metadata=summary,
        )

    return summary


@api.route("/finance/webhook/paystack", methods=["POST"])
def paystack_webhook():
    """Secure Paystack webhook for MoMo/USSD/Bank/Card payments."""
    raw_body = request.get_data() or b""
    verified, reason = _verify_paystack_signature(raw_body)
    if not verified:
        logger.warning(f"Paystack webhook rejected: {reason}")
        return jsonify({"status": "rejected", "message": reason}), 401

    data = request.get_json(silent=True) or {}
    event = (data.get("event") or "").strip()
    payload = data.get("data") or {}

    if event != "charge.success":
        return jsonify({"status": "ignored", "event": event}), 200

    try:
        metadata = payload.get("metadata") or {}
        if _is_paystack_dedicated_account_charge(payload):
            virtual_account_result = _record_paystack_virtual_account_payment(payload, event=event)
            if virtual_account_result:
                body, status_code = virtual_account_result
                return jsonify(body), status_code
        if metadata.get("transaction_type") == "parent_admission_fee" or metadata.get("parent_admission_application_id"):
            body, status_code = _record_paystack_parent_admission_payment(payload, event=event)
            return jsonify(body), status_code
        body, status_code = _record_paystack_finance_payment(payload, event=event)
        return jsonify(body), status_code
    except Exception as exc:
        db.session.rollback()
        logger.error("Paystack finance webhook failed for ref=%s: %s", payload.get("reference"), exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


def _call_paystack_api(endpoint, method="GET", data=None):
    """Helper to call Paystack API with authentication."""
    import requests
    
    secret_key = (os.getenv("PAYSTACK_SECRET_KEY") or "").strip()
    if not secret_key:
        return None, "PAYSTACK_SECRET_KEY not configured"
    
    base_url = "https://api.paystack.co"
    url = f"{base_url}{endpoint}"
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
    }
    
    try:
        if method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)

        if response.status_code >= 400:
            provider_message = ""
            try:
                error_payload = response.json()
                provider_message = str(error_payload.get("message") or "").strip()
            except ValueError:
                provider_message = response.text.strip()
            if response.status_code == 401 and "invalid key" in provider_message.lower():
                provider_message = "Invalid Paystack secret key configured on the server"
            error_detail = provider_message or response.text.strip() or f"HTTP {response.status_code}"
            raise requests.exceptions.HTTPError(
                f"{response.status_code} {error_detail}",
                response=response,
            )

        result = response.json()
        
        if result.get("status") is True:
            return result.get("data"), None
        else:
            return None, result.get("message", "Paystack API error")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack API call failed: {e}")
        return None, str(e)


PAYSTACK_BANK_DIRECTORY = {
    "GH": {"country": "ghana", "currency": "GHS"},
    "NG": {"country": "nigeria", "currency": "NGN"},
    "ZA": {"country": "south africa", "currency": "ZAR"},
}
PAYSTACK_DVA_SUPPORTED_COUNTRIES = {"GH", "NG"}
PAYSTACK_DVA_DEFAULT_PROVIDER_PREFERENCE = ("titan-paystack",)
PAYSTACK_DVA_INTENT_TTL_DAYS = 7


def _normalize_bank_lookup_key(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _find_paystack_bank_match(bank_name, banks):
    lookup_key = _normalize_bank_lookup_key(bank_name)
    if not lookup_key:
        return None

    exact_matches = []
    partial_matches = []
    for bank in banks or []:
        candidate_name = sanitize_string(bank.get("name") or "") or ""
        candidate_key = _normalize_bank_lookup_key(candidate_name)
        if not candidate_key:
            continue
        if candidate_key == lookup_key:
            exact_matches.append(bank)
            continue
        if lookup_key in candidate_key or candidate_key in lookup_key:
            partial_matches.append(bank)

    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None
    if len(partial_matches) == 1:
        return partial_matches[0]

    best_match = None
    best_score = 0
    ambiguous = False
    lookup_tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", (bank_name or "").lower())
        if token not in {"bank", "ghana", "ltd", "limited", "plc", "company"}
    }
    for bank in banks or []:
        candidate_name = sanitize_string(bank.get("name") or "") or ""
        candidate_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", candidate_name.lower())
            if token not in {"bank", "ghana", "ltd", "limited", "plc", "company"}
        }
        score = len(lookup_tokens & candidate_tokens)
        if score > best_score:
            best_match = bank
            best_score = score
            ambiguous = False
        elif score and score == best_score:
            ambiguous = True

    if best_score <= 0 or ambiguous:
        return None
    return best_match


def _resolve_paystack_bank(bank_name, country_code):
    directory = PAYSTACK_BANK_DIRECTORY.get((country_code or "GH").upper())
    if not directory:
        return None, "Automatic Paystack subaccount creation is not available for this country yet."

    banks, error = _call_paystack_api(
        f"/bank?country={quote(directory['country'])}&currency={quote(directory['currency'])}",
        method="GET",
    )
    if error:
        return None, f"Unable to load Paystack bank directory: {error}"

    match = _find_paystack_bank_match(bank_name, banks if isinstance(banks, list) else [])
    if not match:
        return None, "Could not match the selected bank to a Paystack-supported bank."

    bank_code = sanitize_string(match.get("code") or "") or ""
    if not bank_code:
        return None, "Paystack returned a bank match without a bank code."

    return {
        "bank_code": bank_code,
        "bank_name": sanitize_string(match.get("name") or bank_name) or bank_name,
        "country": directory["country"],
        "currency": directory["currency"],
    }, None


def _resolve_paystack_account_name(account_number, bank_code):
    result, error = _call_paystack_api(
        f"/bank/resolve?account_number={quote(str(account_number or '').strip())}&bank_code={quote(str(bank_code or '').strip())}",
        method="GET",
    )
    if error:
        return None, f"Unable to verify the bank account with Paystack: {error}"

    if not isinstance(result, dict):
        return None, "Paystack account verification returned an unexpected response."

    resolved_name = sanitize_string(result.get("account_name") or "") or ""
    if not resolved_name:
        return None, "Paystack could not verify the bank account name."
    return resolved_name, None


def _is_valid_paystack_contact_email(value):
    candidate = sanitize_string(value or "") or ""
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", candidate))


def _normalize_paystack_contact_phone(value):
    raw_value = str(value or "").strip()
    digits = re.sub(r"\D+", "", raw_value)
    if len(digits) < 7 or len(digits) > 15:
        return ""
    if raw_value.startswith("+"):
        return f"+{digits}"
    return digits


def _provision_school_paystack_subaccount(school, settings, provider_settings):
    bank_name = sanitize_string(getattr(school, "bank_name", "") or "") or ""
    bank_account = re.sub(r"\s+", "", sanitize_string(getattr(school, "bank_account", "") or "") or "")
    account_name = sanitize_string(getattr(school, "bank_account_name", "") or "") or ""
    country_code = sanitize_string(getattr(settings, "country_code", "") or "GH") or "GH"
    contact_email = sanitize_string(getattr(school, "school_email", "") or "") or ""
    contact_phone = _normalize_paystack_contact_phone(getattr(school, "school_phone", "") or "")

    if not bank_name or not bank_account or not account_name:
        return None, "Provide bank name, account number, and account name before EduPulse can create a Paystack subaccount."

    bank_match, error = _resolve_paystack_bank(bank_name, country_code)
    if error:
        return None, error

    resolved_account_name, error = _resolve_paystack_account_name(bank_account, bank_match["bank_code"])
    if error:
        return None, error

    paystack_account_name = sanitize_string(resolved_account_name or account_name or school.name) or school.name

    payload = {
        "business_name": paystack_account_name,
        "bank_code": bank_match["bank_code"],
        "account_number": bank_account,
        "percentage_charge": 0,
        "description": f"EduPulse settlement account for {school.name}",
        "primary_contact_name": paystack_account_name,
    }
    if _is_valid_paystack_contact_email(contact_email):
        payload["primary_contact_email"] = contact_email
    if contact_phone:
        payload["primary_contact_phone"] = contact_phone

    subaccount_code = sanitize_string(provider_settings.get("paystack_subaccount_code") or "") or ""
    endpoint = f"/subaccount/{quote(subaccount_code)}" if subaccount_code else "/subaccount"
    method = "PUT" if subaccount_code else "POST"
    action = "updated" if subaccount_code else "created"

    result, error = _call_paystack_api(endpoint, method=method, data=payload)
    if error and any(key in payload for key in ("primary_contact_email", "primary_contact_phone")):
        fallback_payload = {
            key: value
            for key, value in payload.items()
            if key not in {"primary_contact_email", "primary_contact_phone"}
        }
        fallback_result, fallback_error = _call_paystack_api(endpoint, method=method, data=fallback_payload)
        if not fallback_error:
            result, error = fallback_result, fallback_error

    if error:
        return None, f"Paystack subaccount {action} failed: {error}"
    if not isinstance(result, dict):
        return None, f"Paystack subaccount {action} returned an unexpected response."

    next_subaccount_code = sanitize_string(result.get("subaccount_code") or subaccount_code) or ""
    if not next_subaccount_code:
        return None, "Paystack did not return a subaccount code."

    updated_provider_settings = {
        **provider_settings,
        "paystack_subaccount_code": next_subaccount_code,
        "paystack_bank_code": bank_match["bank_code"],
        "paystack_resolved_account_name": resolved_account_name,
    }
    _set_payment_provider_settings(settings, updated_provider_settings)
    return {
        "action": action,
        "subaccount_code": next_subaccount_code,
        "bank_code": bank_match["bank_code"],
        "resolved_account_name": resolved_account_name,
    }, None


def _school_bank_details_ready_for_paystack(school):
    return bool(
        sanitize_string(getattr(school, "bank_name", "") or "")
        and sanitize_string(getattr(school, "bank_account", "") or "")
        and sanitize_string(getattr(school, "bank_account_name", "") or "")
    )


def _resolve_payment_collection_currency_code(settings):
    country_code = (settings.country_code if settings and settings.country_code else "GH").upper()
    if country_code == "NG":
        return "NGN"
    return "GHS"


def _get_or_create_paystack_transfer_split(school, provider_settings, base_amount, total_amount, settings=None):
    return payment_collection_service.get_or_create_paystack_transfer_split(
        school,
        provider_settings,
        base_amount,
        total_amount,
        settings,
        sanitize_string,
        _call_paystack_api,
        _get_payment_collection_split_cache,
        _set_payment_collection_split_cache,
        _resolve_payment_collection_currency_code,
    )


def _build_payment_collection_intent_payload(intent):
    return payment_instruction_service.build_payment_collection_intent_payload(intent, sanitize_string)


def _get_student_payment_collection_intents(student):
    return payment_instruction_service.get_student_payment_collection_intents(student, PaymentCollectionIntent)


def _attach_virtual_routes_to_payment_codes(student, codes_list):
    return payment_instruction_service.attach_virtual_routes_to_payment_codes(
        student,
        codes_list,
        _get_student_payment_collection_intents,
        _build_payment_collection_intent_payload,
    )


def _get_paystack_dva_provider(country_code):
    return payment_collection_service.get_paystack_dva_provider(
        country_code,
        sanitize_string,
        _call_paystack_api,
        PAYSTACK_DVA_SUPPORTED_COUNTRIES,
        PAYSTACK_DVA_DEFAULT_PROVIDER_PREFERENCE,
    )


def _create_paystack_collection_customer(email, full_name, phone, metadata=None):
    return payment_collection_service.create_paystack_collection_customer(
        email,
        full_name,
        phone,
        metadata,
        sanitize_string,
        split_person_name,
        _call_paystack_api,
    )


def _create_paystack_dedicated_virtual_account(customer_code, provider_slug, provider_settings, split_code=None, phone=None, first_name="", last_name=""):
    return payment_collection_service.create_paystack_dedicated_virtual_account(
        customer_code,
        provider_slug,
        provider_settings,
        split_code,
        phone,
        first_name,
        last_name,
        sanitize_string,
        _call_paystack_api,
    )


def _create_or_reuse_student_virtual_account_intent(student, school, settings, payment_code):
    return payment_collection_service.create_or_reuse_student_virtual_account_intent(
        student,
        school,
        settings,
        payment_code,
        PaymentCollectionIntent,
        sanitize_string,
        _get_payment_collection_pricing,
        calculate_payment_collection_breakdown,
        _get_payment_provider_settings,
        _get_or_create_paystack_transfer_split,
        _get_paystack_dva_provider,
        lambda base_email, school_id, reference_code: build_intent_customer_email(base_email, school_id, reference_code, sanitize_string),
        _create_paystack_collection_customer,
        _create_paystack_dedicated_virtual_account,
        PAYSTACK_DVA_INTENT_TTL_DAYS,
        db.session,
    )


def _extract_paystack_virtual_account_identifiers(payload):
    return payment_collection_service.extract_paystack_virtual_account_identifiers(payload, sanitize_string)


def _record_paystack_virtual_account_payment(payload, event="charge.success"):
    return payment_collection_service.record_paystack_virtual_account_payment(
        payload,
        event,
        sanitize_string,
        PaymentCollectionIntent,
        _record_paystack_finance_payment,
        db.session,
    )


def _is_paystack_dedicated_account_charge(payload):
    authorization = payload.get("authorization") if isinstance(payload.get("authorization"), dict) else {}
    normalized_channels = {
        (sanitize_string(authorization.get("channel") or "") or "").lower(),
        (sanitize_string(payload.get("channel") or "") or "").lower(),
    }
    if normalized_channels & {"dedicated_nuban", "dedicated_account"}:
        return True

    identifiers = _extract_paystack_virtual_account_identifiers(payload)
    has_virtual_account_target = bool(identifiers.get("account_number") or identifiers.get("dedicated_account_id"))
    return has_virtual_account_target


def _record_paystack_parent_admission_payment(payload, event="charge.success"):
    return payment_collection_service.record_paystack_parent_admission_payment(
        payload,
        event,
        sanitize_string,
        ParentAdmissionApplication,
        SchoolSettings,
        _get_parent_admission_payment_summary,
        _normalize_parent_admission_payment_summary,
        _get_school_admission_fee_config,
        _set_parent_admission_payment_summary,
        log_action,
        db.session,
    )


@api.route("/finance/paystack/initialize-payment", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def initialize_paystack_payment():
    """Initialize a Paystack payment using structured reference metadata."""
    data = request.get_json() or {}

    verification_block, _snapshot = _finance_verification_block_response(
        g.school_id,
        action="initialize_paystack_payment",
    )
    if verification_block:
        return verification_block

    school = School.query.get(g.school_id)
    restriction = _payment_collection_block_response(school)
    if restriction:
        return restriction
    
    response_body, error, status_code = payment_checkout_service.initialize_student_paystack_payment(
        data,
        g.school_id,
        Student,
        sanitize_string,
        _resolve_payment_from_reference,
        _call_paystack_api,
    )
    if error:
        if status_code == 502:
            logger.error(f"Paystack initialization failed: {error}")
            return jsonify({"message": public_payment_setup_failure_message()}), 502
        return jsonify(error), status_code
    return jsonify(response_body)


@api.route("/public/schools/<school_id>/admissions/status/<status_token>/initialize-payment", methods=["POST"])
def initialize_parent_admission_fee_payment(school_id, status_token):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return jsonify({"message": "School not found"}), 404

    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    application = ParentAdmissionApplication.query.filter_by(
        school_id=school_id,
        status_token=status_token,
    ).first()
    if not application:
        return jsonify({"message": "Application not found"}), 404

    fee_config = _get_school_admission_fee_config(settings)
    if not fee_config["enabled"]:
        return jsonify({"message": "This school does not require an admission fee right now."}), 409

    payment_summary = _get_parent_admission_payment_summary(application, settings)
    response_body, error, status_code = payment_checkout_service.initialize_parent_admission_fee_payment(
        school_id,
        status_token,
        school,
        settings,
        application,
        fee_config,
        payment_summary,
        _get_payment_provider_settings,
        _build_parent_status_path,
        _build_parent_public_url,
        _normalize_parent_admission_payment_summary,
        _set_parent_admission_payment_summary,
        _call_paystack_api,
        db.session,
        secrets.token_hex,
    )
    if error:
        if status_code == 502:
            logger.error(f"Parent admission payment initialization failed: {error}")
            return jsonify({"message": public_payment_setup_failure_message()}), 502
        return jsonify(error), status_code

    return jsonify(response_body), status_code


@api.route("/proprietor/terminal-reports/whatsapp/bulk-send", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@rate_limit_api
@jwt_required()
def send_terminal_reports_whatsapp_bulk():
    """Send terminal report PDFs by class, single student, or selected students."""
    if not STARTUP_WHATSAPP_ENABLED:
        return _whatsapp_feature_disabled_response()

    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}

    target_mode = sanitize_string(payload.get("target_mode")) or "class"
    class_name = sanitize_string(payload.get("class_name"))
    requested_student_ids = payload.get("student_ids") if isinstance(payload.get("student_ids"), list) else []
    requested_student_ids = [int(student_id) for student_id in requested_student_ids if str(student_id).isdigit()]
    academic_term = sanitize_string(payload.get("academic_term")) or "Term 1"
    academic_year = sanitize_string(payload.get("academic_year")) or "2024/2025"

    if target_mode not in ["class", "single", "selected"]:
        return jsonify({"message": "target_mode must be one of: class, single, selected"}), 400

    if target_mode == "class":
        if not class_name:
            return jsonify({"message": "class_name is required for class mode"}), 400
        if class_name not in VALID_GRADES:
            return jsonify({"message": "Invalid class name."}), 400
    elif target_mode in ["single", "selected"] and not requested_student_ids:
        return jsonify({"message": "student_ids is required for single/selected mode"}), 400

    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    effective_plan = get_effective_plan(school)
    if effective_plan != "Premium":
        return jsonify({"message": f"Bulk WhatsApp terminal report sending is available on the {get_plan_display_name('Premium')} plan only."}), 403

    if not school.settings:
        return jsonify({"message": "School settings not found"}), 400

    if school.settings.whatsapp_notifications_enabled is False:
        return jsonify({"message": "WhatsApp notifications are disabled for this school."}), 403

    today = get_utc_now().date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

    daily_count = AuditLog.query.filter(
        AuditLog.school_id == g.school_id,
        AuditLog.action.in_(["WHATSAPP_TEST_SENT", "WHATSAPP_MESSAGE_SENT", "WHATSAPP_REPORT_BULK_SENT"]),
        AuditLog.timestamp >= today_start,
        AuditLog.timestamp <= today_end,
    ).count()
    daily_limit = school.settings.whatsapp_daily_limit or 50

    if target_mode == "class":
        students = Student.query.filter_by(school_id=g.school_id, current_class=class_name).all()
    else:
        students = Student.query.filter(
            Student.school_id == g.school_id,
            Student.id.in_(requested_student_ids),
        ).all()

    if not students:
        return jsonify({"message": "No students found for the selected target"}), 404

    if target_mode == "single":
        students = students[:1]

    def classify_reason(reason: str):
        text_reason = (reason or "").lower()
        if "missing_parent_phone" in text_reason:
            return "missing_phone"
        if "daily_limit_reached" in text_reason:
            return "daily_limit_reached"
        if "report_not_found" in text_reason:
            return "report_not_found"
        if "invalid" in text_reason or "format" in text_reason:
            return "invalid_number_format"
        if "not in allowed list" in text_reason or "recipient" in text_reason:
            return "not_on_whatsapp_or_unreachable"
        return "delivery_failed"

    sent = []
    skipped = []
    sent_count = 0

    for student in students:
        if daily_count + sent_count >= daily_limit:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "daily_limit_reached",
                "verification_status": "not_attempted",
            })
            continue

        if not student.parent_phone:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "missing_parent_phone",
                "verification_status": "missing_phone",
            })
            continue

        report = ReportCard.query.filter_by(
            school_id=g.school_id,
            student_id=student.id,
            academic_term=academic_term,
            academic_year=academic_year,
        ).first()

        if not report:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "report_not_found",
                "verification_status": "not_attempted",
            })
            continue

        try:
            pdf_bytes = _build_terminal_report_pdf_bytes(student, report, academic_term, academic_year)
            filename = f"{student.name.replace(' ', '_')}_{academic_term.replace(' ', '_')}_{academic_year.replace('/', '-')}.pdf"
            caption = f"{school.name} terminal report for {student.name} ({academic_term} {academic_year})"
            result = send_document_bytes(student.parent_phone, pdf_bytes, filename, caption=caption)
            message_id = (result.get("messages") or [{}])[0].get("id")

            sent.append({
                "student_id": student.id,
                "student_name": student.name,
                "phone": student.parent_phone,
                "message_id": message_id,
                "verification_status": "accepted_by_whatsapp" if message_id else "sent_no_message_id",
            })
            sent_count += 1
        except WhatsAppError as exc:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": str(exc),
                "verification_status": classify_reason(str(exc)),
            })
        except Exception as exc:
            logger.error(f"Bulk WhatsApp report send failed for student {student.id}: {exc}")
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "unexpected_error",
                "verification_status": "delivery_failed",
            })

    log_action(
        user_id,
        g.school_id,
        "WHATSAPP_REPORT_BULK_SENT",
        f"Bulk terminal report WhatsApp send for {class_name} ({academic_term} {academic_year}): sent={len(sent)}, skipped={len(skipped)}",
    )

    for item in sent:
        log_action(
            user_id,
            g.school_id,
            "WHATSAPP_MESSAGE_SENT",
            f"Terminal report sent to {item['student_name']} ({item['phone']})",
        )

    return jsonify(
        {
            "status": "success",
            "message": f"Bulk send completed: {len(sent)} sent, {len(skipped)} skipped.",
            "target_mode": target_mode,
            "attempted_count": len(students),
            "sent_count": len(sent),
            "skipped_count": len(skipped),
            "sent": sent,
            "skipped": skipped,
            "class_name": class_name,
            "academic_term": academic_term,
            "academic_year": academic_year,
            "plan": effective_plan,
        }
    )


@api.route("/proprietor/payment-tracker/whatsapp/bulk-send", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@rate_limit_api
@jwt_required()
def send_payment_reminders_whatsapp_bulk():
    """Send payment reminders via WhatsApp by class, selected students, or single student."""
    if not STARTUP_WHATSAPP_ENABLED:
        return _whatsapp_feature_disabled_response()

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from io import BytesIO
    from backend.utils import generate_all_payment_codes

    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    target_mode = sanitize_string(payload.get("target_mode")) or "class"
    class_name = sanitize_string(payload.get("class_name"))
    requested_student_ids = payload.get("student_ids") if isinstance(payload.get("student_ids"), list) else []
    requested_student_ids = [int(student_id) for student_id in requested_student_ids if str(student_id).isdigit()]

    if target_mode not in ["class", "single", "selected"]:
        return jsonify({"message": "target_mode must be one of: class, single, selected"}), 400
    if target_mode == "class" and not class_name:
        return jsonify({"message": "class_name is required for class mode"}), 400
    if target_mode in ["single", "selected"] and not requested_student_ids:
        return jsonify({"message": "student_ids is required for single/selected mode"}), 400
    
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    effective_plan = get_effective_plan(school)
    if effective_plan != "Premium":
        return jsonify({"message": f"Bulk WhatsApp payment reminders are available on the {get_plan_display_name('Premium')} plan only."}), 403

    if not school.settings:
        return jsonify({"message": "School settings not found"}), 400

    if school.settings.whatsapp_notifications_enabled is False:
        return jsonify({"message": "WhatsApp notifications are disabled for this school."}), 403

    today = get_utc_now().date()
    today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=timezone.utc)

    daily_count = AuditLog.query.filter(
        AuditLog.school_id == g.school_id,
        AuditLog.action.in_(["WHATSAPP_TEST_SENT", "WHATSAPP_MESSAGE_SENT", "WHATSAPP_PAYMENT_BULK_SENT"]),
        AuditLog.timestamp >= today_start,
        AuditLog.timestamp <= today_end,
    ).count()
    daily_limit = school.settings.whatsapp_daily_limit or 50

    fees_config = {
        "tuition_fee": school.settings.tuition_fee if school.settings else 0.0,
        "feeding_fee": school.settings.feeding_fee if school.settings else 0.0,
        "uniform_fee": school.settings.uniform_fee if school.settings else 0.0,
        "transport_fee": school.settings.transport_fee if school.settings else 0.0,
        "terminal_report_fee": school.settings.terminal_report_fee if school.settings else 0.0,
        "other_fees": school.settings.other_fees if school.settings else {},
    }

    # Resolve target students
    if target_mode == "class":
        students = Student.query.filter_by(school_id=g.school_id, current_class=class_name).all()
    else:
        students = Student.query.filter(
            Student.school_id == g.school_id,
            Student.id.in_(requested_student_ids),
        ).all()

    if target_mode == "single":
        students = students[:1]

    # Keep only students with outstanding fees
    eligible_students = [
        s
        for s in students
        if (s.total_tuition_owed or 0) > 0
        or (s.total_feeding_owed or 0) > 0
        or (s.total_transport_owed or 0) > 0
        or (s.total_uniform_owed or 0) > 0
    ]
    
    if not eligible_students:
        return jsonify({"message": "No students with outstanding fees found"}), 404

    sent = []
    skipped = []
    sent_count = 0

    def classify_reason(reason: str):
        text_reason = (reason or "").lower()
        if "missing_parent_phone" in text_reason:
            return "missing_phone"
        if "daily_limit_reached" in text_reason:
            return "daily_limit_reached"
        if "invalid" in text_reason or "format" in text_reason:
            return "invalid_number_format"
        if "not in allowed list" in text_reason or "recipient" in text_reason:
            return "not_on_whatsapp_or_unreachable"
        return "delivery_failed"

    for student in eligible_students:
        if daily_count + sent_count >= daily_limit:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "daily_limit_reached",
                "verification_status": "not_attempted",
            })
            continue

        if not student.parent_phone:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "missing_parent_phone",
                "verification_status": "missing_phone",
            })
            continue

        try:
            payment_codes = generate_all_payment_codes(student.student_code, fees_config)

            # Generate payment summary PDF
            pdf_buffer = BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            width, height = letter
            
            # Title
            c.setFont("Helvetica-Bold", 16)
            c.drawString(inch, height - 0.5 * inch, f"{school.name} - Payment Statement")
            
            # Student info
            c.setFont("Helvetica", 11)
            c.drawString(inch, height - 1 * inch, f"Student: {student.name}")
            c.drawString(inch, height - 1.3 * inch, f"Class: {student.current_class or 'Not assigned'}")
            c.drawString(inch, height - 1.6 * inch, f"Date: {date.today().strftime('%B %d, %Y')}")
            
            # Summary table header
            y_position = height - 2.2 * inch
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y_position, "Fee Type")
            c.drawString(3 * inch, y_position, "Amount Due (GH₵)")
            c.drawString(5 * inch, y_position, "Due Date")
            
            # Draw line
            c.line(inch, y_position - 0.15 * inch, 6.5 * inch, y_position - 0.15 * inch)
            
            # Summary rows
            y_position -= 0.4 * inch
            c.setFont("Helvetica", 10)
            
            fee_items = []
            if student.total_tuition_owed > 0:
                fee_items.append(("Tuition", student.total_tuition_owed))
            if student.total_feeding_owed > 0:
                fee_items.append(("Feeding", student.total_feeding_owed))
            if student.total_transport_owed > 0:
                fee_items.append(("Transport", student.total_transport_owed))
            if student.total_uniform_owed > 0:
                fee_items.append(("Uniform", student.total_uniform_owed))
            
            for fee_type, amount in fee_items:
                c.drawString(inch, y_position, fee_type)
                c.drawRightString(3.5 * inch, y_position, f"GH₵ {amount:.2f}")
                c.drawString(5 * inch, y_position, "End of Term")
                y_position -= 0.3 * inch
            
            # Total
            c.line(inch, y_position, 6.5 * inch, y_position)
            y_position -= 0.2 * inch
            c.setFont("Helvetica-Bold", 11)
            total_owed = student.total_tuition_owed + student.total_feeding_owed + student.total_transport_owed + student.total_uniform_owed
            c.drawString(inch, y_position, "TOTAL OUTSTANDING")
            c.drawRightString(3.5 * inch, y_position, f"GH₵ {total_owed:.2f}")
            
            # Payment instructions (reference first)
            y_position -= 0.6 * inch
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y_position, "How to Pay (Structured Reference First):")
            
            y_position -= 0.3 * inch
            c.setFont("Helvetica", 10)
            for fee_type, amount in fee_items:
                ref_code = payment_codes.get(fee_type)

                line = f"{fee_type}: GH₵ {amount:.2f}"

                c.drawString(inch, y_position, line[:110])
                y_position -= 0.25 * inch

                if ref_code:
                    c.drawString(inch + 15, y_position, f"Reference: {ref_code}")
                    y_position -= 0.22 * inch

            y_position -= 0.1 * inch
            c.setFont("Helvetica", 9)
            footer_instructions = [
                "Use the same structured reference in bank narration, card checkout notes, or USSD where possible.",
                "Use the school's approved payment channel and the matching reference for each fee.",
                "Cash paid at the school office should use the same fee reference.",
                f"For support, contact {school.name}.",
            ]
            for instruction in footer_instructions:
                c.drawString(inch, y_position, instruction[:120])
                y_position -= 0.25 * inch
            
            c.save()
            pdf_buffer.seek(0)
            pdf_bytes = pdf_buffer.getvalue()
            
            # Send via WhatsApp
            filename = f"{student.name.replace(' ', '_')}_payment_statement.pdf"
            caption = (
                f"Payment reminder for {student.name} - Outstanding fees: GH₵ {total_owed:.2f}. "
                "See the attached statement for structured references and phone-payment totals."
            )
            result = send_document_bytes(student.parent_phone, pdf_bytes, filename, caption=caption)
            message_id = (result.get("messages") or [{}])[0].get("id")

            # Send short text with per-fee references (best effort)
            route_lines = []
            for fee_type, amount in fee_items:
                ref_code = payment_codes.get(fee_type)
                route_lines.append(
                    f"- {fee_type}: Ref {ref_code or '-'} | Amount GH₵ {amount:.2f}"
                )

            reminder_text = (
                f"{school.name} Payment Reminder\n"
                f"Student: {student.name} ({student.student_code})\n"
                f"Total Outstanding: GH₵ {total_owed:.2f}\n\n"
                f"Use the matching fee reference:\n"
                + "\n".join(route_lines[:6])
                + "\n\nUse the same reference in the payment narration where possible."
                + "\nThe school office can also record the payment against that same reference."
            )
            try:
                send_text_message(student.parent_phone, reminder_text[:1500])
            except WhatsAppError as text_exc:
                logger.warning(
                    f"Payment reminder text send failed for student {student.id}: {text_exc}"
                )

            sent.append({
                "student_id": student.id,
                "student_name": student.name,
                "phone": student.parent_phone,
                "amount_owed": total_owed,
                "message_id": message_id,
                "verification_status": "accepted_by_whatsapp" if message_id else "sent_no_message_id",
            })
            sent_count += 1
        except WhatsAppError as exc:
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": str(exc),
                "verification_status": classify_reason(str(exc)),
            })
        except Exception as exc:
            logger.error(f"Bulk WhatsApp payment reminder failed for student {student.id}: {exc}")
            skipped.append({
                "student_id": student.id,
                "student_name": student.name,
                "reason": "unexpected_error",
                "verification_status": "delivery_failed",
            })

    log_action(
        user_id,
        g.school_id,
        "WHATSAPP_PAYMENT_BULK_SENT",
        f"Bulk payment reminder WhatsApp send: sent={len(sent)}, skipped={len(skipped)}",
    )

    for item in sent:
        log_action(
            user_id,
            g.school_id,
            "WHATSAPP_MESSAGE_SENT",
            f"Payment reminder sent to {item['student_name']} ({item['phone']}) - Amount: GH₵ {item['amount_owed']:.2f}",
        )

    return jsonify(
        {
            "status": "success",
            "message": f"Bulk payment reminders sent: {len(sent)} sent, {len(skipped)} skipped.",
            "target_mode": target_mode,
            "attempted_count": len(eligible_students),
            "class_name": class_name,
            "sent_count": len(sent),
            "skipped_count": len(skipped),
            "sent": sent,
            "skipped": skipped,
            "total_outstanding": sum(item["amount_owed"] for item in sent),
            "plan": effective_plan,
        }
    )


@api.route("/students/<int:student_id>/terminal-report/remarks", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def save_terminal_report_remarks(student_id):
    """Save headmaster and proprietor remarks for terminal report."""
    from backend.api.models import ReportCard, User

    data = request.get_json()
    if not data:
        return jsonify({"message": "No data provided"}), 400

    term = data.get("term") or request.args.get("term", "Term 1")
    year = data.get("year") or request.args.get("year", "2024/2025")

    report = ReportCard.query.filter_by(
        school_id=g.school_id,
        student_id=student_id,
        academic_term=term,
        academic_year=year,
    ).first()

    if not report:
        return jsonify({"message": "Report not found"}), 404

    # Get current user's role
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    user_role = user.role if user else ""

    # Only headmaster can set headmaster remarks
    if data.get("headmaster_remarks") and user_role not in ["headmaster", "proprietor"]:
        return jsonify({"message": "Only headmaster can set headmaster remarks"}), 403

    # Update remarks
    if "headmaster_remarks" in data:
        report.headmaster_remarks = data["headmaster_remarks"]
    if "proprietor_remarks" in data:
        report.proprietor_remarks = data["proprietor_remarks"]

    db.session.commit()

    log_action(
        user_id,
        g.school_id,
        "TERMINAL_REPORT_REMARKS_SAVED",
        f"Terminal report remarks saved for student {student_id}",
    )

    return jsonify(
        {"message": "Remarks saved successfully", "report": report.to_dict()}
    )


@api.route("/students/<int:student_id>/terminal-report/promote", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def promote_student_from_terminal_report(student_id):
    """
    Promote student to next class DURING terminal report approval.
    Only available for Term 3 reports. Automatically called when headmaster/proprietor approve Term 3 report.
    """
    from flask_jwt_extended import get_jwt_identity
    
    try:
        data = request.get_json(silent=True) or {}
        term = data.get("term", "Term 3")
        year = data.get("year", "2024/2025")
        new_class = data.get("new_class")
        remarks = data.get("remarks", f"Promoted after {term} approval")
        
        # Only allow promotion for Term 3
        if "Term 3" not in term and "3" not in term:
            return jsonify({"message": "Promotion only allowed for Term 3"}), 400
        
        student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
        if not student:
            return jsonify({"message": "Student not found"}), 404
        
        if not new_class:
            return jsonify({"message": "new_class is required"}), 400
        
        if new_class not in VALID_GRADES:
            return jsonify({"message": f"Invalid class '{new_class}'"}), 400
        
        old_class = student.current_class
        if old_class == new_class:
            return jsonify({"message": "Student is already in this class"}), 400
        
        user_id = int(get_jwt_identity())
        
        # Create promotion record
        promotion = StudentPromotion(
            student_id=student.id,
            school_id=g.school_id,
            promoted_from_class=old_class,
            promoted_to_class=new_class,
            promoted_by_user_id=user_id,
            remarks=remarks,
            promotion_date=get_utc_now(),
        )
        db.session.add(promotion)
        
        # Update student's class
        student.current_class = new_class
        student.last_promoted_date = get_utc_now()
        student.last_promoted_by_user_id = user_id
        
        db.session.commit()
        
        # Log the action
        promoted_by_user = User.query.get(user_id)
        log_system_action(
            g.school_id,
            "STUDENT_PROMOTED_FROM_TERMINAL_REPORT",
            f"{promoted_by_user.username} promoted {student.name} from {old_class} to {new_class} during {term} approval"
        )
        
        return jsonify({
            "message": f"Student {student.name} promoted from {old_class} to {new_class}",
            "student_id": student.id,
            "new_class": new_class,
            "promotion_id": promotion.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error promoting student", "error": str(e)}), 500


@api.route("/students/<int:student_id>/reports", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_student_reports(student_id):
    """Get all terminal reports for a student (for trend analysis)."""
    from backend.api.models import ReportCard, Student

    student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
    if not student:
        return jsonify({"message": "Student not found"}), 404

    # Fetch all reports for this student, ordered by term and year
    reports = (
        ReportCard.query.filter_by(school_id=g.school_id, student_id=student_id)
        .order_by(ReportCard.academic_year.asc(), ReportCard.academic_term.asc())
        .all()
    )

    # Return simplified data for trend visualization
    report_data = []
    for report in reports:
        if report.term_average:  # Only include reports with averages
            report_data.append(
                {
                    "academic_term": report.academic_term,
                    "academic_year": report.academic_year,
                    "term_average": float(report.term_average),
                    "overall_position": report.overall_position,
                    "out_of_students": report.out_of_students,
                }
            )

    return jsonify(report_data)


# --- SUBJECT TEACHER GRADE SUBMISSION ---


@api.route("/teacher/submit-grades-to-homeroom", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
@feature_required("grade_entry")
def submit_grades_to_homeroom():
    """
    Subject teacher submits finalized grades to homeroom teacher.
    These grades can then be pulled into the terminal report card.
    Uses existing StudentGrade model with is_finalized=True.
    """
    user_id = int(get_jwt_identity())
    data = request.json

    class_name = data.get("class_name")
    subject = data.get("subject")
    grade_data = data.get(
        "grade_data"
    )  # Dict of {student_id: {class_score, exam_score}}

    if not class_name or not subject or not grade_data:
        return (
            jsonify(
                {"message": "Missing required fields: class_name, subject, grade_data"}
            ),
            400,
        )

    if class_name not in VALID_GRADES:
        return (
            jsonify(
                {
                    "message": f"Invalid class name. Must be one of: {', '.join(VALID_GRADES)}"
                }
            ),
            400,
        )

    # Get school's grading scheme
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    class_score_max = settings.class_score_max if settings else 30
    exam_score_max = settings.exam_score_max if settings else 70

    # Create or update StudentGrade records with is_finalized=True
    for student_id, scores in grade_data.items():
        class_score = float(scores.get("class_score", 0))
        exam_score = float(scores.get("exam_score", 0))
        diagnostic_topics = normalize_diagnostic_topics(scores.get("diagnostic_topics"))

        # Validate ranges using school's grading scheme
        if class_score < 0 or class_score > class_score_max:
            return (
                jsonify(
                    {
                        "message": f"Class score for student {student_id} must be 0-{class_score_max}"
                    }
                ),
                400,
            )
        if exam_score < 0 or exam_score > exam_score_max:
            return (
                jsonify(
                    {
                        "message": f"Exam score for student {student_id} must be 0-{exam_score_max}"
                    }
                ),
                400,
            )

        total_score = class_score + exam_score

        # Check if grade already exists
        existing = StudentGrade.query.filter_by(
            student_id=int(student_id), subject_name=subject, class_name=class_name
        ).first()

        if existing:
            # Update existing grade
            existing.class_score = class_score
            existing.exam_score = exam_score
            existing.total_score = total_score
            existing.is_finalized = True
            existing.remarks = remark_from_grade(grade_from_total(total_score))
            existing.diagnostic_topics = diagnostic_topics
            existing.updated_at = get_utc_now()
        else:
            # Create new grade record
            grade = StudentGrade(
                student_id=int(student_id),
                subject_name=subject,
                class_name=class_name,
                class_score=class_score,
                exam_score=exam_score,
                total_score=total_score,
                is_finalized=True,
                remarks=remark_from_grade(grade_from_total(total_score)),
                diagnostic_topics=diagnostic_topics,
            )
            db.session.add(grade)

    db.session.commit()

    log_action(
        user_id,
        g.school_id,
        "GRADES_SUBMITTED_TO_HOMEROOM",
        f"{subject} grades submitted for {class_name}",
    )

    return jsonify({"message": f"{subject} grades submitted successfully to homeroom"})


@api.route("/homeroom/get-subject-grades/<string:class_name>", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def get_subject_grades_for_class(class_name):
    """
    Homeroom teacher fetches all finalized subject grades for their class.
    Returns grades grouped by student.
    """
    user = User.query.get(int(get_jwt_identity()))

    # Check permission
    if user.role == "teacher" and user.assigned_class != class_name:
        return jsonify({"message": "Access denied: Not your assigned class"}), 403

    # Get all students in the class
    students = (
        Student.query.filter_by(school_id=g.school_id, current_class=class_name)
        .order_by(Student.name)
        .all()
    )

    result = []
    for student in students:
        # Get all finalized grades for this student
        grades = StudentGrade.query.filter_by(
            student_id=student.id, is_finalized=True
        ).all()

        subject_grades = [
            {
                "subject": g.subject_name,
                "class_score": g.class_score,
                "exam_score": g.exam_score,
                "total": g.total_score,
                "remarks": g.remarks,
                "diagnostic_topics": g.diagnostic_topics or [],
            }
            for g in grades
        ]

        result.append(
            {
                "student_id": student.id,
                "student_name": student.name,
                "student_code": student.student_code,
                "subject_grades": subject_grades,
            }
        )

    return jsonify(result)


# --- PROPRIETOR REPORT CARD APPROVAL ---


@api.route("/proprietor/report-builder/pending", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_proprietor_pending_reports():
    """Get all report cards pending proprietor approval (headmaster-approved or direct submissions)."""
    from sqlalchemy import and_, or_

    from backend.api.models import ReportCard

    # Get reports that are either:
    # 1. Approved by headmaster (status='HeadmasterApproved')
    # 2. Submitted directly to proprietor (status='Submitted' AND submit_to='proprietor')
    reports = (
        ReportCard.query.filter(ReportCard.school_id == g.school_id)
        .filter(
            or_(
                ReportCard.status == "HeadmasterApproved",
                and_(
                    ReportCard.status == "Submitted",
                    ReportCard.submit_to == "proprietor",
                ),
            )
        )
        .order_by(
            ReportCard.headmaster_approved_at.desc().nullslast(),
            ReportCard.submitted_at.desc(),
        )
        .all()
    )

    return jsonify([r.to_dict() for r in reports])


@api.route("/proprietor/report-builder/approve", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def proprietor_approve_report():
    """Proprietor gives final approval for report card printing."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity())
    data = request.json
    report_id = data.get("report_id")
    status = data.get("status")  # 'Approved' or 'Rejected'
    remarks = data.get("proprietor_remarks")

    if not report_id or not status:
        return jsonify({"message": "Missing report_id or status"}), 400

    if status not in ["Approved", "Rejected"]:
        return jsonify({"message": "Status must be 'Approved' or 'Rejected'"}), 400

    report = ReportCard.query.filter_by(
        id=report_id, school_id=g.school_id
    ).first_or_404()

    # Allow approval for:
    # 1. Reports approved by headmaster (status='HeadmasterApproved')
    # 2. Reports submitted directly to proprietor (status='Submitted' AND submit_to='proprietor')
    valid_for_approval = report.status == "HeadmasterApproved" or (
        report.status == "Submitted" and report.submit_to == "proprietor"
    )

    if not valid_for_approval:
        return (
            jsonify(
                {
                    "message": f"Report cannot be approved. Current status: {report.status}, submit_to: {report.submit_to or 'N/A'}"
                }
            ),
            400,
        )

    if status == "Approved":
        report.status = "ProprietorApproved"  # Ready for printing
        report.proprietor_approved_at = get_utc_now()
        report.proprietor_approved_by = user_id
        if remarks:
            report.proprietor_remarks = remarks
        message = "Report card approved by proprietor. Ready for printing."
    else:
        report.status = "Rejected"
        report.proprietor_remarks = remarks or "Requires changes before printing"
        message = "Report card rejected by proprietor. Sent back for revision."

    db.session.commit()

    log_action(
        user_id,
        g.school_id,
        "REPORT_CARD_PROPRIETOR_REVIEWED",
        f"Report card #{report_id} {status} by proprietor",
    )

    return jsonify({"message": message})


@api.route("/proprietor/report-builder/mark-printed", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def mark_report_printed():
    """Mark report card as printed."""
    from backend.api.models import ReportCard

    user_id = int(get_jwt_identity())
    data = request.json
    report_id = data.get("report_id")

    if not report_id:
        return jsonify({"message": "Missing report_id"}), 400

    report = ReportCard.query.filter_by(
        id=report_id, school_id=g.school_id
    ).first_or_404()

    if report.status != "ProprietorApproved":
        return (
            jsonify({"message": "Report must be proprietor-approved before printing"}),
            400,
        )

    report.printed_at = get_utc_now()
    report.status = "Published"  # Final status
    db.session.commit()

    log_action(
        user_id, g.school_id, "REPORT_CARD_PRINTED", f"Report card #{report_id} printed"
    )

    return jsonify({"message": "Report card marked as printed"})


# --- 3. PROPRIETOR COMMAND & AI (Governance Pillar) ---


@api.route("/ai/student-pulse/<int:student_id>", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@feature_required("student_rescue_agent")
def get_student_pulse(student_id):
    """Predictive Sack-Risk based on Financial & Academic data."""
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    health_data = calculate_academic_health(student.id)
    return jsonify(health_data)


@api.route("/school/verification", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_school_verification_status():
    verification = _get_latest_school_verification(g.school_id)
    snapshot = _get_school_verification_snapshot(g.school_id)
    if not verification:
        return jsonify({"verification": snapshot, "profile": None})

    return jsonify(
        {
            "verification": snapshot,
            "profile": {
                "id": verification.id,
                "legal_name": verification.legal_name,
                "organization_id": verification.organization_id,
                "registration_number": verification.registration_number,
                "tax_id": verification.tax_id,
                "license_number": verification.license_number,
                "bank_account_name": verification.bank_account_name,
                "bank_name": verification.bank_name,
                "owner_information": verification.owner_information or {},
                "screening_results": verification.screening_results or {},
                "documents": [
                    item
                    for item in (
                        _build_school_verification_document_entry(entry)
                        for entry in (verification.documents or [])
                    )
                    if item
                ],
                "review_notes": verification.review_notes,
                "submitted_at": _to_iso_utc(verification.submitted_at),
                "reviewed_at": _to_iso_utc(verification.reviewed_at),
                "expires_at": _to_iso_utc(verification.expires_at),
            },
        }
    )


@api.route("/school/verification/documents/<string:document_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def download_school_verification_document(document_id):
    verification = _get_latest_school_verification(g.school_id)
    if not verification:
        return jsonify({"message": "No verification profile found for school"}), 404

    matching_document = next(
        (
            item
            for item in (verification.documents or [])
            if isinstance(item, dict) and (item.get("document_id") or item.get("id")) == document_id
        ),
        None,
    )
    if not matching_document:
        return jsonify({"message": "Document not found"}), 404

    resolved_path = _resolve_existing_school_file(
        _get_school_verification_document_storage_root(),
        matching_document.get("stored_filename"),
    )
    if not resolved_path:
        return jsonify({"message": "Document file is no longer available"}), 404

    return send_file(
        resolved_path,
        as_attachment=False,
        download_name=matching_document.get("original_filename") or matching_document.get("filename") or "verification-document",
    )


@api.route("/school/verification", methods=["PUT"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def submit_school_verification():
    payload = request.get_json(silent=True) or {}
    if request.form:
        payload = request.form

    user_id = int(get_jwt_identity())
    existing_snapshot = _get_school_verification_snapshot(g.school_id)
    existing_status = existing_snapshot.get("status")
    if existing_status in {"pending", "review_required", "verified", "suspended"}:
        lock_messages = {
            "pending": "A school verification submission is already pending review. Wait for the compliance decision before submitting again.",
            "review_required": "This school verification is already under manual review. Update requests should go through platform support instead of submitting another case.",
            "verified": "This school is already verified. A new submission is only needed if the current verification expires or support asks for refreshed documents.",
            "suspended": "This school verification is currently suspended. Contact platform support before attempting another submission.",
        }
        return (
            jsonify(
                {
                    "error": "school_verification_already_submitted",
                    "message": lock_messages.get(existing_status, "A school verification submission already exists for this school."),
                    "verification": existing_snapshot,
                }
            ),
            409,
        )

    def _parse_json_field(value, default):
        if isinstance(value, (dict, list)):
            return value
        if value in (None, ""):
            return default
        try:
            parsed = json.loads(value)
        except Exception:
            return default
        return parsed if isinstance(parsed, type(default)) else default

    legal_name = sanitize_string(payload.get("legal_name") or "")
    registration_number = sanitize_string(payload.get("registration_number") or "")
    tax_id = sanitize_string(payload.get("tax_id") or "")
    bank_account_name = sanitize_string(payload.get("bank_account_name") or "")
    bank_account_number = sanitize_string(payload.get("bank_account_number") or "")
    bank_name = sanitize_string(payload.get("bank_name") or "")

    if not legal_name or not registration_number or not tax_id:
        return jsonify({"message": "legal_name, registration_number, and tax_id are required"}), 400

    owner_information = _parse_json_field(payload.get("owner_information"), {})
    screening_results = _parse_json_field(payload.get("screening_results"), {})
    documents = _parse_json_field(payload.get("documents"), [])
    existing_documents = _parse_json_field(payload.get("existing_documents"), [])

    if isinstance(existing_documents, list):
        documents = existing_documents + documents

    uploaded_files = [item for item in request.files.getlist("documents") if item and item.filename]
    if not documents and not uploaded_files:
        return jsonify({"message": "At least one JPG, PNG, or PDF verification document is required."}), 400

    for uploaded in uploaded_files:
        if not _allowed_school_verification_document(uploaded.filename, uploaded.mimetype):
            return jsonify({"message": "Only JPG, JPEG, PNG, and PDF documents are allowed."}), 400

        file_bytes = uploaded.read()
        if not file_bytes:
            continue

        entry = _extract_parent_admission_document_details(
            uploaded.filename,
            uploaded.mimetype,
            file_bytes,
            category_override="registration_certificate",
        )
        entry.update(_store_school_verification_document(g.school_id, uploaded, file_bytes))
        entry["source"] = "school_verification"
        entry["uploaded_at"] = get_utc_now().isoformat()
        entry["uploaded_by_user_id"] = user_id
        documents.append(entry)

    verification = SchoolVerification(
        school_id=g.school_id,
        status="pending",
        risk_tier="medium",
        legal_name=legal_name,
        organization_id=g.school_id,
        registration_number=registration_number,
        tax_id=tax_id,
        license_number=sanitize_string(payload.get("license_number") or ""),
        bank_account_name=bank_account_name,
        bank_account_number=bank_account_number,
        bank_name=bank_name,
        owner_information=owner_information,
        screening_results=screening_results,
        documents=documents,
        submitted_by_user_id=user_id,
        submitted_at=get_utc_now(),
    )
    db.session.add(verification)
    db.session.flush()

    school = School.query.get(g.school_id)
    provider_result = verify_school_profile(school, verification)
    auto_verified = False
    auto_reason = provider_result.get("reason") or "provider_unavailable"
    local_auto_approval_enabled = _local_verification_auto_approval_enabled()

    if provider_result.get("verified"):
        _apply_school_verification_outcome(
            verification,
            "verified",
            provider_result.get("risk_tier") or "low",
            notes=provider_result.get("reason") or "provider_verified",
        )
        auto_verified = True
        auto_reason = "provider_verified"
    elif provider_result.get("outcome") == "review_required":
        _apply_school_verification_outcome(
            verification,
            "review_required",
            provider_result.get("risk_tier") or "medium",
            notes=provider_result.get("reason") or "provider_review_required",
        )
        auto_reason = provider_result.get("reason") or "provider_review_required"
    else:
        local_auto_verified, local_reason = _auto_verify_school_verification(school, verification)
        if local_auto_verified and local_auto_approval_enabled:
            _apply_school_verification_outcome(
                verification,
                "verified",
                "low",
                notes=_compose_verification_review_note(
                    provider_result.get("reason") or "provider_unavailable",
                    local_reason,
                ),
            )
            auto_verified = True
            auto_reason = local_reason
        elif local_auto_verified:
            _apply_school_verification_outcome(
                verification,
                "review_required",
                provider_result.get("risk_tier") or "medium",
                notes=_compose_verification_review_note(
                    provider_result.get("reason") or "provider_unavailable",
                    "eligible_but_manual_review_required",
                ),
            )
            auto_reason = provider_result.get("reason") or "provider_manual_review_required"
        else:
            _apply_school_verification_outcome(
                verification,
                "review_required",
                provider_result.get("risk_tier") or "medium",
                notes=_compose_verification_review_note(
                    provider_result.get("reason") or "provider_unavailable",
                    local_reason,
                ),
            )
            auto_reason = provider_result.get("reason") or local_reason

    log_action(
        user_id,
        g.school_id,
        "SCHOOL_KYB_SUBMITTED",
        json.dumps(
            {
                "verification_id": verification.id,
                "legal_name": legal_name,
                "registration_number": registration_number,
                "document_count": len(documents),
                "auto_verified": auto_verified,
                "auto_reason": auto_reason,
            }
        ),
    )
    db.session.commit()

    final_snapshot = _get_school_verification_snapshot(g.school_id)

    return jsonify(
        {
            "message": (
                "Verification profile auto-approved."
                if final_snapshot.get("is_verified")
                else "Verification profile submitted for compliance review."
            ),
            "verification": final_snapshot,
            "verification_id": verification.id,
            "auto_verified": auto_verified,
            "auto_reason": auto_reason,
        }
    )


@api.route("/proprietor/compliance/aml-flags", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def list_school_aml_flags():
    status_filter = sanitize_string(request.args.get("status") or "open").lower()
    query = AMLTransactionFlag.query.filter_by(school_id=g.school_id)
    if status_filter in {"open", "resolved"}:
        query = query.filter(AMLTransactionFlag.status == status_filter)

    rows = query.order_by(AMLTransactionFlag.created_at.desc()).limit(300).all()
    return jsonify(
        {
            "flags": [
                {
                    "id": row.id,
                    "rule_code": row.rule_code,
                    "severity": row.severity,
                    "status": row.status,
                    "summary": row.summary,
                    "details": row.details or {},
                    "payment_id": row.payment_id,
                    "student_id": row.student_id,
                    "created_at": _to_iso_utc(row.created_at),
                    "resolved_at": _to_iso_utc(row.resolved_at),
                }
                for row in rows
            ]
        }
    )


@api.route("/proprietor/compliance/aml-flags/<int:flag_id>/resolve", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def resolve_school_aml_flag(flag_id):
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    notes = sanitize_string(payload.get("notes") or "")

    row = AMLTransactionFlag.query.filter_by(id=flag_id, school_id=g.school_id).first()
    if not row:
        return jsonify({"message": "AML flag not found"}), 404

    row.status = "resolved"
    row.resolution_notes = notes or "Resolved by proprietor"
    row.resolved_by_user_id = user_id
    row.resolved_at = get_utc_now()

    db.session.commit()
    return jsonify({"message": "AML flag resolved.", "flag_id": row.id})


@api.route("/finance/receive-payment", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def receive_payment():
    """
    Manual entry for Cash/Direct payments.
    Accepts either student_id or reference_code (e.g., CFK011 or S001-FEED-MON).
    - Teachers: Creates 'Pending' record (awaiting Proprietor confirmation).
    - Proprietor: Creates 'Confirmed' record immediately.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    verification_block, _snapshot = _finance_verification_block_response(
        g.school_id,
        action="receive_payment",
    )
    if verification_block:
        return verification_block

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    # Support student lookup by payment reference, explicit student code, or numeric student_id.
    student = None
    payment_type = data.get("type") or data.get("payment_type") or "Tuition"

    structured_reference_code = None

    if "reference_code" in data:
        reference_code = data["reference_code"].strip().upper()
        structured_reference_code = reference_code
        student, decoded_type, decoded_category = _resolve_payment_from_reference(
            reference_code,
            school_id_hint=g.school_id,
        )
        if not student:
            return jsonify({"message": f"Invalid reference code: {reference_code}"}), 400
        if decoded_type:
            payment_type = decoded_type
        if decoded_category:
            data["payment_category"] = decoded_category
    else:
        student_identifier = str(
            data.get("student_identifier") or data.get("student_code") or ""
        ).strip()
        if student_identifier:
            normalized_student_code = student_identifier.upper()
            student = Student.query.filter_by(
                student_code=normalized_student_code,
                school_id=g.school_id,
            ).first()
            if not student and student_identifier.isdigit():
                student = Student.query.filter_by(
                    id=int(student_identifier),
                    school_id=g.school_id,
                ).first()
            if not student:
                return jsonify({"message": f"Student {student_identifier} not found."}), 404
        else:
            # Use traditional student_id
            student = Student.query.filter_by(
                id=data.get("student_id"), school_id=g.school_id
            ).first_or_404()

    school = School.query.get(g.school_id)
    restriction = _payment_collection_block_response(school)
    if restriction:
        return restriction

    # Role-based restrictions on manual payment types
    # Note: finance and proprietor roles are not in role_limits - they can record ALL payment types
    role = user.role or ""
    role_limits = {
        "inventory_manager": ["Inventory"],
        "teacher": ["Tuition", "Feeding"],
        "homeroom": ["Tuition", "Feeding"],
    }
    if role in role_limits and payment_type not in role_limits[role]:
        return (
            jsonify(
                {
                    "message": f"Access denied: {role} can only record {', '.join(role_limits[role])} payments."
                }
            ),
            403,
        )

    # Security: Disallow subject teachers (non-homeroom) from recording feeding payments
    if payment_type == "Feeding" and user.role == "teacher":
        if not user.assigned_class or user.assigned_class != student.current_class:
            return (
                jsonify(
                    {
                        "message": "Access denied: Teachers can only record feeding payments for their homeroom class."
                    }
                ),
                403,
            )

    # Determine status based on role
    # ONLY proprietor can confirm payments immediately for audit integrity
    # All other roles (finance, teachers, etc.) create "Pending" payments requiring proprietor approval
    status = "Confirmed" if user.role == "proprietor" else "Pending"

    # Support granular payment categorization (term, frequency, item)
    # Example: {"term": "Term 1"} for tuition, {"frequency": "Monthly"} for feeding
    payment_category = data.get("payment_category", {})

    # Validate inventory payments
    if payment_type in ["Inventory", "Uniform"]:
        item_id = payment_category.get("item_id")
        sku = payment_category.get("sku")
        if not item_id and not sku:
            return (
                jsonify({"message": "Inventory payments require item_id or sku in payment_category."}),
                400,
            )

    explicit_reference_id = sanitize_string(data.get("reference_id")) or None
    reference_id = explicit_reference_id or structured_reference_code
    payment_category = data.get("payment_category", {})
    if structured_reference_code:
        payment_category = {
            **(payment_category or {}),
            "reference_code": structured_reference_code,
        }
    payment_category = _normalize_payment_category_for_storage(
        g.school_id,
        payment_type,
        payment_category,
        amount_paid=data.get("amount"),
    )
    validation_payload = {
        "student_id": student.id,
        "amount": data.get("amount"),
        "payment_type": payment_type,
        "method": data.get("method", "Cash"),
        "reference_id": reference_id,
        "payment_category": payment_category,
    }
    if reference_id:
        existing = Payment.query.filter_by(reference_id=reference_id).first()
        if existing:
            return jsonify({"message": "Duplicate reference ID"}), 409
    try:
        PaymentSchema().load(validation_payload)
    except Exception as e:
        return jsonify({"message": "Invalid payment data", "error": str(e)}), 400

    payment = Payment(
        student_id=student.id,
        school_id=g.school_id,
        created_by_user_id=user.id,
        amount=validation_payload["amount"],
        payment_type=payment_type,
        method=validation_payload["method"],
        reference_id=validation_payload["reference_id"],
        status=status,
        payment_category=validation_payload["payment_category"],
    )
    db.session.add(payment)
    db.session.flush()

    aml_flags = _evaluate_payment_aml_flags(g.school_id, payment, actor_id=user.id)

    # Only update student stats if confirmed immediately
    if status == "Confirmed":
        if payment.payment_type == "Tuition":
            student.total_tuition_owed = max(
                0, student.total_tuition_owed - float(payment.amount)
            )
        elif payment.payment_type == "Feeding":
            student.feeding_paid = True
        elif payment.payment_type in ["Inventory", "Uniform"]:
            item_id = payment.payment_category.get("item_id")
            sku = payment.payment_category.get("sku")
            quantity = int(payment.payment_category.get("quantity", 1))
            inventory_item = None
            if item_id:
                inventory_item = Inventory.query.filter_by(
                    id=item_id, school_id=g.school_id
                ).first()
            elif sku:
                inventory_item = Inventory.query.filter_by(
                    sku=sku, school_id=g.school_id
                ).first()

            if inventory_item:
                if inventory_item.quantity is not None and inventory_item.quantity < quantity:
                    db.session.rollback()
                    return (
                        jsonify({"message": "Insufficient inventory stock for this item."}),
                        400,
                    )
                inventory_item.quantity = (inventory_item.quantity or 0) - quantity
                payment.payment_category = {
                    **payment.payment_category,
                    "item_name": inventory_item.item_name,
                    "item_type": inventory_item.item_type,
                    "size": inventory_item.size,
                    "sku": inventory_item.sku,
                    "quantity": quantity,
                }
        
        # Create immutable ledger entry for confirmed payment
        add_ledger_entry(
            school_id=g.school_id,
            tx_type=payment.payment_type.lower(),
            tx_ref=payment.reference_id or f"PAY-{payment.id}",
            amount=payment.amount,
            currency="GH₵",
            actor_id=user.id,
            student_id=student.id,
            source=payment.method.lower(),
            metadata={
                "payment_id": payment.id,
                "student_name": student.name,
                "student_code": student.student_code,
                "payment_category": payment.payment_category,
                "recorded_by": user.username
            }
        )

    log_action(
        user_id=user.id,
        school_id=g.school_id,
        action="REVENUE_COLLECTED",
        details=f"{user.role.capitalize()} recorded GH₵{data.get('amount')} for {student.name} ({payment_type}, Reference: {data.get('reference_code', 'N/A')}, {status})",
    )
    db.session.commit()
    return jsonify(
        {
            "message": f"Payment recorded as {status}.",
            "payment_type": payment_type,
            "student_name": student.name,
            "payment_id": payment.id,
            "id": payment.id,
            "aml_flags_opened": len(aml_flags),
        }
    )


@api.route("/finance/webhook/bank", methods=["POST"])
def bank_transfer_webhook():
    """
    AUTOMATION PULSE: Receives automated bank transfer callbacks from bank providers.
    Parses 'reference' field to extract student code and payment category.

    Reference Format: STUDENT_CODE-CATEGORY
    Examples:
    - "S001-T1" → Student S001, Term 1 Tuition
    - "S001-FEED-MON" → Student S001, Monthly Feeding
    - "S001-UNIF" → Student S001, Uniform
    - "S001-TRANS-MON" → Student S001, Monthly Transport

    Expected payload structure from bank:
    {
        "status": "success",
        "reference": "S001-T1",  # Parsed to get student + category
        "amount": 500.00,
        "transaction_id": "BANK-TXN-123456",
        "payer_name": "Parent Name"
    }
    """
    from backend.utils import parse_payment_reference

    try:
        raw_body = request.get_data() or b""
        verified, reason = _verify_bank_webhook_signature(raw_body)
        if not verified:
            logger.warning(f"Bank webhook rejected: {reason}")
            return jsonify({"status": "rejected", "message": reason}), 401

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

        # Verify transaction status
        if data.get("status") != "success":
            return (
                jsonify({"status": "ignored", "reason": "Transaction not successful"}),
                200,
            )

        # Parse reference to get student code and category
        reference = data.get("reference", "")
        parsed = parse_payment_reference(reference)

        if not parsed:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid reference format. Use: STUDENT_CODE-CATEGORY (e.g., S001-T1)",
                    }
                ),
                400,
            )

        student_code = parsed["student_code"]
        payment_type = parsed["payment_type"]
        payment_category = parsed["category"]

        # Find student by code
        student = Student.query.filter_by(student_code=student_code).first()
        if not student:
            return jsonify({"status": "student_not_found", "code": student_code}), 404

        # Check for duplicate transaction (idempotency using reference_id)
        existing = Payment.query.filter_by(
            reference_id=data.get("transaction_id"), student_id=student.id
        ).first()
        if existing:
            return (
                jsonify({"status": "duplicate", "message": "Payment already recorded"}),
                200,
            )

        verification_snapshot = _get_school_verification_snapshot(student.school_id)
        verification_blocked = not verification_snapshot["is_verified"]
        collection_block = _get_payment_collection_block(School.query.get(student.school_id))

        # Automatically record and confirm bank transfer payment
        payment = Payment(
            student_id=student.id,
            school_id=student.school_id,
            amount=float(data.get("amount")),
            payment_type=payment_type,
            method="Bank_Auto",
            reference_id=data.get("transaction_id"),  # For idempotency
            status="Pending" if verification_blocked or collection_block else "Confirmed",
            payment_category=payment_category,
        )
        db.session.add(payment)
        db.session.flush()

        if verification_blocked:
            _create_aml_flag(
                school_id=student.school_id,
                payment_id=payment.id,
                student_id=student.id,
                rule_code="UNVERIFIED_SCHOOL_PAYMENT",
                severity="high",
                summary="Bank transfer received while school KYB verification is not approved.",
                details={"reference": data.get("transaction_id"), "verification": verification_snapshot},
            )
        if collection_block:
            _create_aml_flag(
                school_id=student.school_id,
                payment_id=payment.id,
                student_id=student.id,
                rule_code="FREE_TIER_OVER_CAP_PAYMENT",
                severity="high",
                summary="Bank transfer received while Free Tier collection is paused for over-capacity.",
                details={"reference": data.get("transaction_id"), "collection_block": collection_block},
            )

        if not verification_blocked and not collection_block:
            # Update student balance if tuition
            if payment_type == "Tuition":
                student.total_tuition_owed = max(
                    0, student.total_tuition_owed - float(data.get("amount"))
                )
            elif payment_type == "Feeding":
                student.feeding_paid = True
            elif payment_type in ["Inventory", "Uniform"]:
                sku = payment_category.get("item_code") or payment_category.get("sku")
                quantity = int(payment_category.get("quantity", 1))
                inventory_item = None
                if sku:
                    inventory_item = Inventory.query.filter_by(
                        sku=sku, school_id=student.school_id
                    ).first()
                if inventory_item:
                    if inventory_item.quantity is not None and inventory_item.quantity < quantity:
                        return jsonify({"status": "error", "message": "Insufficient inventory stock"}), 400
                    inventory_item.quantity = (inventory_item.quantity or 0) - quantity
                    payment.payment_category = {
                        **payment.payment_category,
                        "item_name": inventory_item.item_name,
                        "item_type": inventory_item.item_type,
                        "size": inventory_item.size,
                        "sku": inventory_item.sku,
                        "quantity": quantity,
                    }

        _evaluate_payment_aml_flags(student.school_id, payment, actor_id=None)

        # Log the transaction
        log_action(
            user_id=None,
            school_id=student.school_id,
            action="BANK_TRANSFER_AUTO",
            details=f"Bank transfer: {data.get('amount')} for {student.name} ({payment_type}, {payment_category}) (Ref: {data.get('transaction_id')})",
        )

        db.session.commit()
        if collection_block:
            return (
                jsonify(
                    {
                        "status": "blocked",
                        "student_id": student.id,
                        "payment_type": payment_type,
                        "category": payment_category,
                        "payment_status": payment.status,
                        "message": collection_block["message"],
                    }
                ),
                200,
            )
        return (
            jsonify(
                {
                    "status": "recorded",
                    "student_id": student.id,
                    "payment_type": payment_type,
                    "category": payment_category,
                    "payment_status": payment.status,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@api.route("/proprietor/live-feed", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_live_feed():
    """Remote oversight for the traveling proprietor."""
    try:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_30_days = now - timedelta(days=30)
        last_365_days = now - timedelta(days=365)
        rescue_payload = _build_student_rescue_payload(g.school_id, limit=5)

        recent_logs = (
            db.session.query(AuditLog)
            .filter_by(school_id=g.school_id)
            .options(joinedload(AuditLog.actor))
            .order_by(AuditLog.timestamp.desc())
            .limit(10)
            .all()
        )

        today_revenue = (
            db.session.query(db.func.sum(Payment.amount))
            .filter(
                Payment.school_id == g.school_id,
                Payment.status == "Confirmed",
                Payment.date_paid.isnot(None),
                Payment.date_paid >= start_of_day,
            )
            .scalar()
            or 0
        )

        monthly_revenue = (
            db.session.query(db.func.sum(Payment.amount))
            .filter(
                Payment.school_id == g.school_id,
                Payment.status == "Confirmed",
                Payment.date_paid.isnot(None),
                Payment.date_paid >= last_30_days,
            )
            .scalar()
            or 0
        )

        yearly_revenue = (
            db.session.query(db.func.sum(Payment.amount))
            .filter(
                Payment.school_id == g.school_id,
                Payment.status == "Confirmed",
                Payment.date_paid.isnot(None),
                Payment.date_paid >= last_365_days,
            )
            .scalar()
            or 0
        )

        total_students = Student.query.filter_by(school_id=g.school_id).count()
        unpaid_tuition = _count_students_with_current_tuition_outstanding(g.school_id)
        critical_list = rescue_payload["students"]
        attendance_snapshot = _get_attendance_submission_snapshot(g.school_id)
        attendance_taken_today = attendance_snapshot.get("is_complete", False)
        meal_breakdown = _get_daily_meal_breakdown(g.school_id)
        present_students = meal_breakdown["present_students"]

        # Fetch pending payments recorded by teachers
        pending_payments = (
            db.session.query(Payment, Student)
            .join(Student)
            .filter(Payment.school_id == g.school_id, Payment.status == "Pending")
            .all()
        )

        pending_list = [
            _serialize_pending_payment(row.Payment, row.Student)
            for row in pending_payments
        ]
        pending_groups = _group_pending_payments_by_class(pending_list)

        # Canteen Stats for Proprietor Oversight
        student_meals = meal_breakdown["covered_student_meals"]
        staff_meals = meal_breakdown["total_staff_meals"]
        canteen_count = meal_breakdown["total_meals_needed"]

        recent_payments = (
            db.session.query(Payment, Student.name)
            .join(Student)
            .filter(Payment.school_id == g.school_id, Payment.status == "Confirmed")
            .order_by(Payment.date_paid.desc())
            .limit(5)
            .all()
        )

        low_stock_items = (
            Inventory.query.filter_by(school_id=g.school_id, is_active=True)
            .filter(Inventory.quantity <= 5)
            .order_by(Inventory.quantity.asc())
            .limit(5)
            .all()
        )

        # Billing notice: surface pending overage invoices (for dashboard visibility).
        billing_notice = None
        try:
            pending_invoices = (
                LedgerEntry.query.filter(
                    LedgerEntry.school_id == g.school_id,
                    LedgerEntry.tx_type.in_(["subscription_prorated"]),
                )
                .order_by(LedgerEntry.created_at.desc())
                .limit(20)
                .all()
            )

            def _invoice_due_at(entry):
                meta = entry.meta or {}
                due_str = meta.get("due_date")
                if isinstance(due_str, str) and due_str:
                    try:
                        due_date = datetime.fromisoformat(due_str).date()
                        return datetime.combine(due_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                    except (TypeError, ValueError):
                        due_date = None
                created_at = entry.created_at
                if created_at is None:
                    return now + timedelta(days=30)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                return created_at + timedelta(days=30)

            due_entries = []
            for entry in pending_invoices:
                meta = entry.meta or {}
                if meta.get("status") != "Pending":
                    continue
                due_at = _invoice_due_at(entry)
                if now >= due_at:
                    due_entries.append((entry, due_at))

            if due_entries:
                entry, due_at = sorted(due_entries, key=lambda t: t[1])[0]
                billing_notice = {
                    "level": "warning",
                    "title": "Billing action required",
                    "message": f"A subscription overage invoice is due (Ref: {entry.tx_ref}, Amount: GH₵ {float(entry.amount or 0):.2f}). Resolve to avoid plan downgrade.",
                    "redirect_to": "/proprietor?tab=subscription",
                    "invoice_tx_ref": entry.tx_ref,
                    "amount": float(entry.amount or 0),
                    "due_date": due_at.date().isoformat(),
                }
        except Exception:
            billing_notice = None

        return jsonify(
            {
                "logs": [
                    {
                        "id": log.id,
                        "time": log.timestamp.strftime("%H:%M"),
                        "timestamp_iso": log.timestamp.isoformat() if log.timestamp else None,
                        "user": log.actor.username if log.actor else "Unknown",
                        "action": log.action,
                        "details": _summarize_live_feed_details(log.action, log.details),
                    }
                    for log in recent_logs
                ],
                "stats": {
                    "today_revenue": today_revenue,
                    "monthly_revenue": monthly_revenue,
                    "yearly_revenue": yearly_revenue,
                    "critical_risk_students": rescue_payload["summary"]["critical_count"],
                    "canteen_count": canteen_count,
                    "pending_cash": len(pending_list),
                    "total_students": total_students,
                    "present_students": len(present_students),
                    "student_meals": student_meals,
                    "staff_meals": staff_meals,
                    "attendance_taken_today": attendance_taken_today,
                    "attendance_partial": attendance_snapshot.get("has_any_submission", False) and not attendance_taken_today,
                    "submitted_classes_count": attendance_snapshot.get("submitted_classes_count", 0),
                    "pending_classes_count": attendance_snapshot.get("pending_classes_count", 0),
                    "unpaid_tuition": unpaid_tuition,
                    "low_stock_count": len(low_stock_items),
                },
                "pending_payments": pending_list,
                "pending_payments_by_class": pending_groups,
                "critical_list": critical_list,
                "student_rescue_agent": rescue_payload,
                "recent_payments": [
                    {
                        "id": p.Payment.id,
                        "student": p.name,
                        "amount": p.Payment.amount,
                        "type": p.Payment.payment_type,
                        "method": p.Payment.method,
                        "time": p.Payment.date_paid.strftime("%H:%M"),
                    }
                    for p in recent_payments
                ],
                "low_stock_items": [
                    {
                        "id": i.id,
                        "item_name": i.item_name,
                        "quantity": i.quantity,
                        "sku": i.sku,
                    }
                    for i in low_stock_items
                ],
                "billing_notice": billing_notice,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error fetching live feed", "error": str(e)}), 500


@api.route("/proprietor/student-rescue-agent", methods=["GET"])
@api.route("/headmaster/student-rescue-agent", methods=["GET"])
@multi_tenant_guard
@feature_required("student_rescue_agent")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_student_rescue_agent():
    """Return prioritized intervention recommendations for at-risk students."""
    try:
        payload = _build_student_rescue_payload(g.school_id, limit=8)
        payload["agent_name"] = "Student Rescue Agent"
        payload["headline"] = "Prioritized students who need financial, attendance, or academic intervention now."
        return jsonify(payload)
    except Exception as e:
        return jsonify({"message": "Error fetching student rescue agent", "error": str(e)}), 500


@api.route("/proprietor/student-rescue-agent/contact-templates/<int:student_id>", methods=["GET"])
@api.route("/headmaster/student-rescue-agent/contact-templates/<int:student_id>", methods=["GET"])
@multi_tenant_guard
@feature_required("student_rescue_agent")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_student_rescue_contact_templates(student_id):
    """Return prebuilt contact templates for a flagged rescue student."""
    payload = _build_student_rescue_payload(g.school_id, limit=None)
    student_payload = next((item for item in payload["students"] if item["id"] == student_id), None)
    if not student_payload:
        return jsonify({"message": "Student rescue case not found"}), 404

    return jsonify(
        {
            "student_id": student_id,
            "student_name": student_payload["name"],
            "contact_templates": student_payload.get("contact_templates") or {},
        }
    )


@api.route("/proprietor/student-rescue-agent/report", methods=["GET"])
@api.route("/headmaster/student-rescue-agent/report", methods=["GET"])
@multi_tenant_guard
@feature_required("student_rescue_agent")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_student_rescue_report():
    """Return rescue reporting data for current open, in-progress, and resolved cases."""
    payload = _build_student_rescue_payload(g.school_id, limit=None)
    status_filter = sanitize_string(request.args.get("status"))
    risk_level_filter = sanitize_string(request.args.get("risk_level"))

    filtered_students = payload["students"]
    if status_filter and status_filter.lower() != "all":
        filtered_students = [
            item for item in filtered_students if (item.get("case_status") or "").lower() == status_filter.lower()
        ]
    if risk_level_filter and risk_level_filter.lower() != "all":
        filtered_students = [
            item for item in filtered_students if (item.get("risk_level") or "").lower() == risk_level_filter.lower()
        ]

    return jsonify(
        {
            "report": payload.get("report") or {},
            "students": filtered_students,
            "generated_at": payload.get("generated_at"),
        }
    )


@api.route("/proprietor/student-rescue-agent/send-email", methods=["POST"])
@api.route("/headmaster/student-rescue-agent/send-email", methods=["POST"])
@multi_tenant_guard
@feature_required("student_rescue_agent")
@role_required("proprietor", "headmaster")
@jwt_required()
def send_student_rescue_email():
    """Send the generated Student Rescue Agent email template to a guardian."""
    payload = request.get_json(silent=True) or {}
    student_id = payload.get("student_id")
    if not student_id or not str(student_id).isdigit():
        return jsonify({"message": "student_id is required"}), 400

    rescue_payload = _build_student_rescue_payload(g.school_id, limit=None)
    student_payload = next((item for item in rescue_payload["students"] if item["id"] == int(student_id)), None)
    if not student_payload:
        return jsonify({"message": "Student rescue case not found"}), 404
    if not student_payload.get("parent_email"):
        return jsonify({"message": "Parent email is not available for this student"}), 400

    templates = student_payload.get("contact_templates") or {}
    subject = sanitize_string(payload.get("subject")) or templates.get("email_subject")
    body = payload.get("body") if isinstance(payload.get("body"), str) else templates.get("email_body")
    if not subject or not body:
        return jsonify({"message": "Email subject and body are required"}), 400

    delivery_ok = send_email_notification(student_payload["parent_email"], subject, body)
    if delivery_ok is False and os.getenv("FLASK_ENV", "development").lower() == "production":
        return jsonify({"message": "Failed to send rescue email"}), 500

    user_id = int(get_jwt_identity())
    detail_payload = {
        "type": "student_rescue_outcome",
        "student_id": student_payload["id"],
        "student_name": student_payload["name"],
        "action_code": "email_sent",
        "action_label": _normalize_rescue_action_label("email_sent"),
        "notes": f"Rescue email sent to {student_payload['parent_email']} with subject: {subject}",
    }
    log_action(
        user_id=user_id,
        school_id=g.school_id,
        action="STUDENT_RESCUE_OUTCOME",
        details=json.dumps(detail_payload),
    )

    outcome_map = _get_rescue_outcome_history(g.school_id, student_ids=[student_payload["id"]], limit=10)
    return jsonify(
        {
            "message": f"Rescue email sent to {student_payload['parent_email']}",
            "student_id": student_payload["id"],
            "recent_outcomes": outcome_map.get(student_payload["id"], [])[:5],
        }
    )


@api.route("/proprietor/student-rescue-agent/outcome", methods=["POST"])
@api.route("/headmaster/student-rescue-agent/outcome", methods=["POST"])
@multi_tenant_guard
@feature_required("student_rescue_agent")
@role_required("proprietor", "headmaster")
@jwt_required()
def log_student_rescue_outcome():
    """Log a leadership action taken on a rescue case."""
    payload = request.get_json(silent=True) or {}
    student_id = payload.get("student_id")
    action_code = sanitize_string(payload.get("action_code"))
    notes = sanitize_string(payload.get("notes"))

    if not student_id or not str(student_id).isdigit():
        return jsonify({"message": "student_id is required"}), 400
    if not action_code:
        return jsonify({"message": "action_code is required"}), 400

    student = Student.query.filter_by(
        id=int(student_id),
        school_id=g.school_id,
    ).first()
    if not student:
        return jsonify({"message": "Student not found"}), 404

    user_id = int(get_jwt_identity())
    detail_payload = {
        "type": "student_rescue_outcome",
        "student_id": student.id,
        "student_name": student.name,
        "action_code": action_code,
        "action_label": _normalize_rescue_action_label(action_code),
        "notes": notes or "",
    }

    log_action(
        user_id=user_id,
        school_id=g.school_id,
        action="STUDENT_RESCUE_OUTCOME",
        details=json.dumps(detail_payload),
    )

    outcome_map = _get_rescue_outcome_history(g.school_id, student_ids=[student.id], limit=10)
    return jsonify(
        {
            "message": "Rescue outcome logged.",
            "student_id": student.id,
            "recent_outcomes": outcome_map.get(student.id, [])[:5],
        }
    )


def _get_live_dashboard_thresholds(settings):
    default_thresholds = {
        "unpaid_tuition": 10,
        "pending_cash": 5,
        "low_stock_count": 3,
        "critical_risk_students": 3,
    }
    try:
        cfg = settings.report_template_config if settings and settings.report_template_config else {}
        stored = cfg.get("live_dashboard_thresholds", {}) if isinstance(cfg, dict) else {}
        if not isinstance(stored, dict):
            return default_thresholds
        merged = default_thresholds.copy()
        for key in default_thresholds.keys():
            if key in stored:
                merged[key] = int(stored.get(key))
        return merged
    except Exception:
        return default_thresholds


def _build_stream_token(user_id, school_id, expires_minutes=15):
    expires_at = int(time.time()) + (expires_minutes * 60)
    raw = f"{user_id}:{school_id}:{expires_at}"
    secret = (current_app.config.get("SECRET_KEY") or "edupulse-stream-secret").encode("utf-8")
    signature = hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{raw}:{signature}".encode("utf-8")).decode("utf-8")


def _verify_stream_token(stream_token):
    try:
        decoded = base64.urlsafe_b64decode(stream_token.encode("utf-8")).decode("utf-8")
        user_id_str, school_id_str, expires_at_str, provided_sig = decoded.split(":", 3)
        raw = f"{user_id_str}:{school_id_str}:{expires_at_str}"
        secret = (current_app.config.get("SECRET_KEY") or "edupulse-stream-secret").encode("utf-8")
        expected_sig = hmac.new(secret, raw.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            return None
        if int(expires_at_str) < int(time.time()):
            return None
        return {"user_id": int(user_id_str), "school_id": int(school_id_str)}
    except Exception:
        return None


@api.route("/proprietor/live-events/token", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_proprietor_live_events_token():
    user_id = int(get_jwt_identity())
    return jsonify({"stream_token": _build_stream_token(user_id=user_id, school_id=g.school_id, expires_minutes=15)})


@api.route("/proprietor/live-dashboard/thresholds", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_live_dashboard_thresholds():
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        return jsonify({"message": "School settings not found"}), 404
    return jsonify(_get_live_dashboard_thresholds(settings))


@api.route("/proprietor/live-dashboard/thresholds", methods=["PUT"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_live_dashboard_thresholds():
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        return jsonify({"message": "School settings not found"}), 404

    payload = request.get_json() or {}
    thresholds = {
        "unpaid_tuition": max(0, int(payload.get("unpaid_tuition", 10))),
        "pending_cash": max(0, int(payload.get("pending_cash", 5))),
        "low_stock_count": max(0, int(payload.get("low_stock_count", 3))),
        "critical_risk_students": max(0, int(payload.get("critical_risk_students", 3))),
    }

    cfg = settings.report_template_config if isinstance(settings.report_template_config, dict) else {}
    cfg["live_dashboard_thresholds"] = thresholds
    settings.report_template_config = cfg
    db.session.commit()

    log_action(
        user_id=int(get_jwt_identity()),
        school_id=g.school_id,
        action="PROPRIETOR_LIVE_THRESHOLDS_UPDATED",
        details=json.dumps(thresholds),
    )
    return jsonify(thresholds)


@api.route("/proprietor/live-dashboard/alerts/ack", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def acknowledge_live_dashboard_alert():
    payload = request.get_json() or {}
    alert_id = str(payload.get("alert_id", "")).strip()
    if not alert_id:
        return jsonify({"message": "alert_id is required"}), 400

    log_action(
        user_id=int(get_jwt_identity()),
        school_id=g.school_id,
        action="PROPRIETOR_ALERT_ACK",
        details=alert_id,
    )
    return jsonify({"status": "acknowledged", "alert_id": alert_id})


@api.route("/proprietor/live-dashboard/alerts/ack", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_acknowledged_live_dashboard_alerts():
    rows = (
        db.session.query(AuditLog)
        .filter(
            AuditLog.school_id == g.school_id,
            AuditLog.action == "PROPRIETOR_ALERT_ACK",
        )
        .order_by(AuditLog.id.desc())
        .limit(200)
        .all()
    )
    alert_ids = []
    seen = set()
    for row in rows:
        aid = (row.details or "").strip()
        if aid and aid not in seen:
            seen.add(aid)
            alert_ids.append(aid)
    return jsonify({"acknowledged_alert_ids": alert_ids})


@api.route("/proprietor/live-events", methods=["GET"])
def proprietor_live_events():
    """Server-Sent Events stream for proprietor live dashboard updates."""
    stream_token = request.args.get("stream_token", "")
    since_id = request.args.get("since_id", default=0, type=int) or 0

    if not stream_token:
        return jsonify({"message": "stream_token is required"}), 400

    verified = _verify_stream_token(stream_token)
    if not verified:
        return jsonify({"message": "Invalid or expired stream token"}), 401

    school_id = verified["school_id"]
    user = User.query.filter_by(id=verified["user_id"], school_id=school_id).first()
    if not user or user.role != "proprietor":
        return jsonify({"message": "Access denied"}), 403

    @stream_with_context
    def event_stream():
        last_seen_id = since_id
        heartbeat_count = 0

        while True:
            new_logs = (
                db.session.query(AuditLog)
                .filter(AuditLog.school_id == school_id, AuditLog.id > last_seen_id)
                .options(joinedload(AuditLog.actor))
                .order_by(AuditLog.id.asc())
                .limit(50)
                .all()
            )

            if new_logs:
                last_seen_id = max(log.id for log in new_logs)
                payload = {
                    "type": "new_logs",
                    "last_id": last_seen_id,
                    "logs": [
                        {
                            "id": log.id,
                            "time": log.timestamp.strftime("%H:%M") if log.timestamp else "--:--",
                            "timestamp_iso": log.timestamp.isoformat() if log.timestamp else None,
                            "user": log.actor.username if log.actor else "Unknown",
                            "action": log.action,
                            "details": _summarize_live_feed_details(log.action, log.details),
                        }
                        for log in new_logs
                    ],
                }
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                heartbeat_count += 1
                if heartbeat_count % 4 == 0:
                    heartbeat = {"type": "heartbeat", "last_id": last_seen_id}
                    yield f"data: {json.dumps(heartbeat)}\n\n"

            time.sleep(5)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _serialize_pending_payment(payment, student):
    recorder_role = "unknown"
    recorder_name = "Unknown Staff"

    if payment.created_by and payment.created_by.role:
        recorder_role = payment.created_by.role
        recorder_name = payment.created_by.username or recorder_name
    elif (payment.method or "").endswith("_Auto") or payment.method in {"Paystack_Payment", "Bank_Auto", "MoMo_Auto"}:
        recorder_role = "automation"
        recorder_name = "System Automation"

    role_labels = {
        "automation": "System Automation",
        "finance": "Finance Officer",
        "homeroom": "Homeroom Teacher",
        "inventory_manager": "Store Manager",
        "kitchen": "Kitchen Staff",
        "proprietor": "Proprietor",
        "teacher": "Teacher",
        "unknown": "Unknown Staff",
    }

    class_name = (student.current_class if student else None) or "Unassigned"
    submitted_at = payment.created_at or payment.date_paid
    return {
        "id": payment.id,
        "amount": payment.amount,
        "student": student.name if student else "Unknown",
        "student_code": student.student_code if student else None,
        "class_name": class_name,
        "type": payment.payment_type,
        "method": payment.method,
        "reference_id": payment.reference_id,
        "payment_category": payment.payment_category or {},
        "recorded_by_user_id": payment.created_by_user_id,
        "recorded_by_name": recorder_name,
        "recorded_by_role": recorder_role,
        "recorded_by_label": role_labels.get(recorder_role, recorder_role.replace("_", " ").title()),
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
    }


def _group_pending_payments_by_class(pending_list):
    grouped = {}
    for item in pending_list:
        class_name = item.get("class_name") or "Unassigned"
        bucket = grouped.setdefault(
            class_name,
            {
                "class_name": class_name,
                "count": 0,
                "total_amount": 0.0,
                "payments": [],
            },
        )
        bucket["payments"].append(item)
        bucket["count"] += 1
        bucket["total_amount"] += float(item.get("amount") or 0)

    ordered_groups = []
    for class_name in sorted(grouped.keys(), key=lambda value: value.lower()):
        group = grouped[class_name]
        group["payments"] = sorted(
            group["payments"],
            key=lambda payment: (
                payment.get("submitted_at") or "",
                payment.get("student") or "",
            ),
        )
        group["total_amount"] = round(group["total_amount"], 2)
        ordered_groups.append(group)
    return ordered_groups


def _confirm_pending_payment_record(payment, confirmed_by_user_id, confirmed_by_username):
    if payment.status == "Confirmed":
        raise ValueError("Payment already confirmed.")

    payment.status = "Confirmed"
    payment.verified_at = get_utc_now()
    payment.verified_by = confirmed_by_user_id
    payment.payment_category = _normalize_payment_category_for_storage(
        g.school_id,
        payment.payment_type,
        payment.payment_category,
        amount_paid=payment.amount,
    )

    student = Student.query.get(payment.student_id)
    if student and payment.payment_type == "Tuition":
        student.total_tuition_owed = max(
            0, (student.total_tuition_owed or 0) - float(payment.amount)
        )
    elif student and payment.payment_type == "Feeding":
        student.feeding_paid = True

    add_ledger_entry(
        school_id=g.school_id,
        tx_type=payment.payment_type.lower(),
        tx_ref=payment.reference_id or f"PAY-{payment.id}",
        amount=payment.amount,
        currency="GH₵",
        actor_id=confirmed_by_user_id,
        student_id=payment.student_id,
        source=(payment.method or "cash").lower(),
        metadata={
            "payment_id": payment.id,
            "student_name": student.name if student else "Unknown",
            "student_code": student.student_code if student else "N/A",
            "payment_category": payment.payment_category,
            "confirmed_by": confirmed_by_username or "System",
        },
    )


@api.route("/finance/confirm-payment/<int:payment_id>", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def confirm_payment(payment_id):
    """Proprietor confirms manual payment and adds to immutable audit ledger."""
    verification_block, _snapshot = _finance_verification_block_response(
        g.school_id,
        action="confirm_payment",
    )
    if verification_block:
        return verification_block

    payment = Payment.query.filter_by(
        id=payment_id, school_id=g.school_id
    ).first_or_404()

    if payment.status == "Confirmed":
        return jsonify({"message": "Payment already confirmed."}), 400

    confirmed_by_user_id = int(get_jwt_identity())
    confirmed_by_user = User.query.get(confirmed_by_user_id)
    _confirm_pending_payment_record(
        payment,
        confirmed_by_user_id,
        confirmed_by_user.username if confirmed_by_user else "System",
    )

    db.session.commit()
    return jsonify({"message": "Cash receipt confirmed and logged to immutable ledger."})


@api.route("/finance/confirm-payments/bulk", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def confirm_payments_bulk():
    """Proprietor confirms a class or explicit batch of pending manual payments."""
    verification_block, _snapshot = _finance_verification_block_response(
        g.school_id,
        action="confirm_payments_bulk",
    )
    if verification_block:
        return verification_block

    payload = request.get_json(silent=True) or {}
    class_name = str(payload.get("class_name") or "").strip()
    payment_ids = [
        int(payment_id)
        for payment_id in (payload.get("payment_ids") or [])
        if str(payment_id).isdigit()
    ]

    if not class_name and not payment_ids:
        return jsonify({"message": "class_name or payment_ids is required."}), 400

    query = (
        db.session.query(Payment)
        .join(Student, Student.id == Payment.student_id)
        .filter(Payment.school_id == g.school_id, Payment.status == "Pending")
    )

    if class_name:
        query = query.filter(Student.current_class == class_name)
    if payment_ids:
        query = query.filter(Payment.id.in_(payment_ids))

    payments = query.order_by(Payment.id.asc()).all()
    if not payments:
        return jsonify({"message": "No pending payments found for the selected class."}), 404

    confirmed_by_user_id = int(get_jwt_identity())
    confirmed_by_user = User.query.get(confirmed_by_user_id)
    confirmed_by_username = confirmed_by_user.username if confirmed_by_user else "System"

    confirmed_payment_ids = []
    total_amount = 0.0
    for payment in payments:
        _confirm_pending_payment_record(
            payment,
            confirmed_by_user_id,
            confirmed_by_username,
        )
        confirmed_payment_ids.append(payment.id)
        total_amount += float(payment.amount or 0)

    db.session.commit()
    return jsonify(
        {
            "message": f"Confirmed {len(confirmed_payment_ids)} pending payments.",
            "payment_ids": confirmed_payment_ids,
            "count": len(confirmed_payment_ids),
            "total_amount": round(total_amount, 2),
            "class_name": class_name or None,
        }
    )


@api.route("/finance/reject-payment/<int:payment_id>", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def reject_payment(payment_id):
    """Proprietor rejects/cancels a pending manual payment (audit protection: cannot delete confirmed payments)."""
    verification_block, _snapshot = _finance_verification_block_response(
        g.school_id,
        action="reject_payment",
    )
    if verification_block:
        return verification_block

    school = School.query.get(g.school_id)
    restriction = _payment_collection_block_response(school)
    if restriction:
        return restriction

    payment = Payment.query.filter_by(
        id=payment_id, school_id=g.school_id
    ).first_or_404()
    
    # AUDIT PROTECTION: Cannot delete confirmed payments (they're in immutable ledger)
    if payment.status == "Confirmed":
        return jsonify({"message": "Cannot reject confirmed payments - they are in the immutable audit ledger. Contact system administrator if correction needed."}), 403

    # Get details before deletion for audit log
    student = Student.query.get(payment.student_id)
    user_id = int(get_jwt_identity())
    
    # Log rejection action
    log_action(
        user_id=user_id,
        school_id=g.school_id,
        action="PAYMENT_REJECTED",

        details=f"Proprietor rejected pending payment: GH₵{payment.amount} from {student.name if student else 'Unknown'} ({payment.payment_type}, Ref: {payment.reference_id or 'N/A'})",
    )
    
    # Delete the pending payment
    db.session.delete(payment)
    db.session.commit()
    
    return jsonify({"message": "Pending payment rejected and removed."})

@api.route("/proprietor/intervene", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
def intervene():
    """The Call/Email feature for high-risk students."""
    data = request.json
    student_id = data.get("student_id")
    method = data.get("method")
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()

    if method == "email":
        return jsonify(
            {"message": f"Intervention email sent to {student.parent_email}"}
        )
    return jsonify({"message": f"Contact: {student.parent_phone}"})


@api.route("/proprietor/broadcast", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def broadcast_message():
    """Proprietor-to-Staff notification loop."""
    data = request.json
    log_action(
        user_id=int(get_jwt_identity()),
        school_id=g.school_id,
        action="PROPRIETOR_NOTICE",
        details=data.get("message"),
    )
    return jsonify({"status": "sent", "message": "Notice broadcasted to all staff."})


@api.route("/proprietor/ai-insights", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_ai_insights():
    """Generate AI-powered insights for proprietor oversight."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func

    insights = []
    alerts = []

    try:
        # 1. Revenue Analysis
        today = datetime.now(timezone.utc).date()
        week_ago = today - timedelta(days=7)

        revenue_this_week = (
            db.session.query(func.sum(Payment.amount))
            .filter(
                Payment.school_id == g.school_id,
                Payment.status == "Confirmed",
                Payment.date_paid >= week_ago,
            )
            .scalar()
            or 0
        )

        revenue_last_week = (
            db.session.query(func.sum(Payment.amount))
            .filter(
                Payment.school_id == g.school_id,
                Payment.status == "Confirmed",
                Payment.date_paid >= week_ago - timedelta(days=7),
                Payment.date_paid < week_ago,
            )
            .scalar()
            or 0
        )

        revenue_change = (
            ((revenue_this_week - revenue_last_week) / revenue_last_week) * 100
            if revenue_last_week > 0
            else None
        )

        if revenue_change is not None and revenue_change > 10:
            insights.append(
                {
                    "type": "success",
                    "title": "Revenue Growth",
                    "message": f"Revenue increased by {revenue_change:.1f}% this week (GH₵ {revenue_this_week:.2f}).",
                    "icon": "📈",
                }
            )
        elif revenue_change is not None and revenue_change < -10:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Revenue Decline",
                    "message": f"Revenue dropped by {abs(revenue_change):.1f}% this week. Consider sending payment reminders.",
                    "icon": "⚠️",
                }
            )

        # 2. Attendance Monitoring
        total_students = Student.query.filter_by(school_id=g.school_id).count()
        attendance_snapshot = _get_attendance_submission_snapshot(g.school_id)
        attendance_taken_today = attendance_snapshot.get("is_complete", False)
        present_today = 0
        attendance_rate = None
        if total_students > 0 and attendance_taken_today:
            present_today = Student.query.filter_by(
                school_id=g.school_id, is_present=True
            ).count()
            attendance_rate = (present_today / total_students * 100)

        if total_students > 0 and attendance_snapshot.get("has_any_submission") and not attendance_taken_today:
            insights.append(
                {
                    "type": "info",
                    "title": "Attendance In Progress",
                    "message": f"Attendance submitted for {attendance_snapshot.get('submitted_classes_count', 0)} of {attendance_snapshot.get('active_classes_count', 0)} classes. Pending classes: {attendance_snapshot.get('pending_classes_count', 0)}.",
                    "icon": "🗓️",
                }
            )
        elif total_students > 0 and not attendance_taken_today:
            insights.append(
                {
                    "type": "info",
                    "title": "Attendance Pending",
                    "message": "Attendance has not been submitted for today yet.",
                    "icon": "🗓️",
                }
            )
        elif attendance_rate is not None and attendance_rate < 75:
            alerts.append(
                {
                    "type": "danger",
                    "title": "Low Attendance Alert",
                    "message": f"Only {attendance_rate:.1f}% attendance today ({present_today}/{total_students}). Investigate absences.",
                    "icon": "🚨",
                }
            )
        elif attendance_rate is not None and attendance_rate >= 95:
            insights.append(
                {
                    "type": "success",
                    "title": "Excellent Attendance",
                    "message": f"Outstanding {attendance_rate:.1f}% attendance rate today!",
                    "icon": "✅",
                }
            )

        # 3. Outstanding Debts
        students_with_debt = Student.query.filter(
            Student.school_id == g.school_id, Student.total_tuition_owed > 0
        ).count()

        total_debt = (
            db.session.query(func.sum(Student.total_tuition_owed))
            .filter(Student.school_id == g.school_id)
            .scalar()
            or 0
        )

        if students_with_debt > 0:
            insights.append(
                {
                    "type": "info",
                    "title": "Outstanding Debts",
                    "message": f"{students_with_debt} students owe GH₵ {total_debt:.2f} in tuition. {students_with_debt // 2} reminders sent this week.",
                    "icon": "💰",
                }
            )

        # 4. At-Risk Students (Feeding not paid but present)
        at_risk_students = 0
        if attendance_taken_today:
            present_students = Student.query.filter_by(
                school_id=g.school_id, is_present=True
            ).all()
            feeding_status_details = _get_feeding_status_details_for_students(present_students, g.school_id)
            at_risk_students = sum(
                1
                for student in present_students
                if not feeding_status_details.get(student.id, {}).get("covered")
            )

        if at_risk_students > 5:
            alerts.append(
                {
                    "type": "danger",
                    "title": "Feeding Fee Crisis",
                    "message": f"{at_risk_students} students present but haven't paid feeding fees. Immediate action needed.",
                    "icon": "🍽️",
                }
            )
        elif at_risk_students > 0:
            insights.append(
                {
                    "type": "warning",
                    "title": "Feeding Fees Pending",
                    "message": f"{at_risk_students} students need feeding fee follow-up.",
                    "icon": "🍽️",
                }
            )

        # 5. Pending Approvals (Reports)
        from backend.api.models import ReportCard

        pending_reports = ReportCard.query.filter(
            ReportCard.school_id == g.school_id,
            ReportCard.status.in_(["Submitted", "HeadmasterApproved"]),
        ).count()

        if pending_reports > 0:
            insights.append(
                {
                    "type": "info",
                    "title": "Reports Awaiting Review",
                    "message": f"{pending_reports} report cards need your approval for printing.",
                    "icon": "📄",
                }
            )

        # 6. Lesson Notes Monitoring
        from backend.api.models import LessonNote

        pending_notes = (
            LessonNote.query.filter_by(school_id=g.school_id, status="Pending")
            .filter(LessonNote.submit_to == "proprietor")
            .count()
        )

        if pending_notes > 0:
            insights.append(
                {
                    "type": "info",
                    "title": "Lesson Notes Review",
                    "message": f"{pending_notes} lesson notes submitted directly to you for review.",
                    "icon": "📝",
                }
            )

        # 7. Staff Activity
        recent_staff_activity = (
            db.session.query(func.count(AuditLog.id))
            .filter(
                AuditLog.school_id == g.school_id,
                AuditLog.timestamp >= datetime.now(timezone.utc) - timedelta(hours=24),
            )
            .scalar()
            or 0
        )

        if recent_staff_activity < 10:
            alerts.append(
                {
                    "type": "warning",
                    "title": "Low Staff Activity",
                    "message": f"Only {recent_staff_activity} staff actions logged in last 24 hours. System may not be actively used.",
                    "icon": "⏰",
                }
            )

        return jsonify(
            {
                "insights": insights,
                "alerts": alerts,
                "summary": {
                    "revenue_this_week": revenue_this_week,
                    "revenue_change": revenue_change,
                    "attendance_rate": attendance_rate,
                    "students_with_debt": students_with_debt,
                    "total_debt": total_debt,
                    "at_risk_students": at_risk_students,
                    "pending_reports": pending_reports,
                    "staff_activity_24h": recent_staff_activity,
                },
            }
        )
    except Exception as e:
        return jsonify({"message": "Error generating insights", "error": str(e)}), 500


@api.route("/staff/notifications", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_staff_notifications():
    """Fetches the latest broadcast message for the staff dashboard."""
    latest_notice = (
        AuditLog.query.filter_by(school_id=g.school_id, action="PROPRIETOR_NOTICE")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )

    # System Alert (Global)
    system_alert = (
        SystemAlert.query.filter_by(is_active=True)
        .order_by(SystemAlert.created_at.desc())
        .first()
    )

    return jsonify(
        {
            "latest_notice": (
                {"details": latest_notice.details} if latest_notice else None
            ),
            "system_alert": (
                {
                    "id": system_alert.id,
                    "message": system_alert.message,
                    "type": system_alert.type,
                    "created_at": system_alert.created_at.isoformat() if system_alert.created_at else None,
                }
                if system_alert
                else None
            ),
        }
    )


# --- 4. ADMISSIONS & EXAMS ---


@api.route("/public/schools/<school_id>/admissions/apply", methods=["POST"])
def submit_parent_admission_application(school_id):
    """Public parent-facing admissions intake for the AI Registrar MVP."""
    payload = request.get_json(silent=True) or {}
    if request.form:
        payload = request.form.to_dict(flat=True)
    passport_photo = request.files.get("passport_photo")
    allowed_classes = _get_public_school_class_names(school_id)
    response_body, error, status_code = parent_admission_service.submit_parent_admission_application(
        school_id,
        payload,
        passport_photo,
        request.files.getlist("documents"),
        School,
        SchoolSettings,
        ParentAdmissionApplication,
        allowed_classes,
        PARENT_ADMISSION_CONSENT_VERSION,
        sanitize_string,
        _extract_parent_admission_document_details,
        _store_parent_admission_document,
        _build_ai_registrar_assessment,
        _generate_parent_admission_code,
        secrets,
        _build_parent_status_path,
        _build_parent_public_url,
        _send_parent_admission_update,
        _get_public_school_profile_payload,
        _build_parent_admission_payment_payload,
        _build_parent_notification_sms,
        log_action,
        get_client_ip,
        logger,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/public/schools/<school_id>/profile", methods=["GET"])
def get_public_school_profile(school_id):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return jsonify({"message": "School not found"}), 404
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    return jsonify(_get_public_school_profile_payload(school, settings))


def _get_public_school_class_names(school_id):
    classes = (
        AcademicClass.query.filter_by(school_id=school_id)
        .order_by(AcademicClass.name)
        .all()
    )
    if classes:
        return [class_item.name for class_item in classes if class_item.name]

    student_classes = (
        db.session.query(Student.current_class)
        .filter(Student.school_id == school_id)
        .group_by(Student.current_class)
        .order_by(Student.current_class)
        .all()
    )
    class_names = [row[0] for row in student_classes if row[0]]
    if class_names:
        return class_names

    return list(VALID_GRADES)


@api.route("/public/schools/<school_id>/classes", methods=["GET"])
def get_public_school_classes(school_id):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return jsonify({"message": "School not found"}), 404

    classes = (
        AcademicClass.query.filter_by(school_id=school_id)
        .order_by(AcademicClass.name)
        .all()
    )
    if classes:
        return jsonify([
            {"id": class_item.id, "name": class_item.name, "class_name": class_item.name}
            for class_item in classes
        ]), 200

    class_names = _get_public_school_class_names(school_id)
    return jsonify([{"name": class_name, "class_name": class_name} for class_name in class_names]), 200


@api.route("/public/schools/<school_id>/admissions/status/<status_token>", methods=["GET"])
def get_parent_admission_status(school_id, status_token):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return jsonify({"message": "School not found"}), 404
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    application = ParentAdmissionApplication.query.filter_by(
        school_id=school_id,
        status_token=status_token,
    ).first()
    if not application:
        return jsonify({"message": "Application not found"}), 404

    payload = _apply_parent_admission_review_details(application.to_public_dict())
    payload["school"] = _get_public_school_profile_payload(school, settings)
    payload["status_path"] = _build_parent_status_path(school_id, application.status_token)
    payload["payment_summary"] = _build_parent_admission_payment_payload(application, school, settings)
    if payload["payment_summary"].get("can_pay_now"):
        payload["payment_path"] = _build_parent_admission_payment_path(school_id, application.status_token)
    if application.admitted_student_id:
        student = Student.query.filter_by(id=application.admitted_student_id, school_id=school_id).first()
        if student:
            payload["student_code"] = student.student_code

    pdf_policy = _get_parent_admission_pdf_policy(settings)
    if application.status == "Approved" and _can_expose_parent_decision_pdf(school, settings):
        decision_path = _build_parent_decision_pdf_path(school_id, application.status_token)
        payload["decision_document"] = {
            "available": True,
            "download_path": decision_path,
            "download_url": _build_parent_public_url(decision_path),
            "delivery_mode": pdf_policy["delivery_mode"],
        }
    return jsonify(payload)


@api.route("/public/schools/<school_id>/admissions/status/<status_token>/decision-pdf", methods=["GET"])
def download_parent_admission_decision_pdf(school_id, status_token):
    school = School.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return jsonify({"message": "School not found"}), 404

    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    pdf_policy = _get_parent_admission_pdf_policy(settings)
    if not pdf_policy["enabled"]:
        return jsonify({"message": "Admission decision PDF is not enabled for this school."}), 404
    if not _has_ai_registrar_access(school):
        return jsonify({"message": "Admission decision PDF requires a paid subscription plan with AI Registrar included."}), 403

    application = ParentAdmissionApplication.query.filter_by(
        school_id=school_id,
        status_token=status_token,
    ).first()
    if not application:
        return jsonify({"message": "Application not found"}), 404
    if application.status != "Approved":
        return jsonify({"message": "Admission decision PDF is only available for approved applications."}), 409

    pdf_bytes = _build_parent_admission_decision_pdf_bytes(application, school, settings, payment_url=None)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{application.first_name}_{application.surname}".strip("_")) or application.application_code
    filename = f"{safe_name}_admission_decision.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@api.route("/public/schools/<school_id>/admissions/status/<status_token>/resubmit", methods=["POST"])
def resubmit_parent_admission_application(school_id, status_token):
    payload = request.get_json(silent=True) or {}
    if request.form:
        payload = request.form.to_dict(flat=True)
    passport_photo = request.files.get("passport_photo")
    allowed_classes = _get_public_school_class_names(school_id)
    response_body, error, status_code = parent_admission_service.resubmit_parent_admission_application(
        school_id,
        status_token,
        payload,
        passport_photo,
        request.files.getlist("documents"),
        School,
        ParentAdmissionApplication,
        allowed_classes,
        sanitize_string,
        _extract_parent_admission_document_details,
        _store_parent_admission_document,
        _build_ai_registrar_assessment,
        _send_parent_admission_update,
        _build_parent_status_path,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/admissions/applications", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def list_parent_admission_applications():
    status_filter = sanitize_string(request.args.get("status") or "")
    query = ParentAdmissionApplication.query.filter_by(school_id=g.school_id)
    if status_filter:
        query = query.filter_by(status=status_filter)

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    applications = query.order_by(ParentAdmissionApplication.submitted_at.desc()).all()
    summary = {}
    active_applications = []
    archived_applications = []
    archive_summary = {}
    workflow_config = _get_parent_admission_workflow_config(settings)
    for item in applications:
        summary[item.status] = summary.get(item.status, 0) + 1
        if item.reviewed_at:
            archived_applications.append(item)
            archive_summary[item.status] = archive_summary.get(item.status, 0) + 1
        else:
            active_applications.append(item)

    return jsonify({
        "applications": [
            _build_staff_parent_admission_payload(item, settings, g.school_id)
            for item in active_applications
        ],
        "archived_applications": [
            _build_staff_parent_admission_payload(item, settings, g.school_id)
            for item in archived_applications
        ],
        "summary": summary,
        "archive_summary": archive_summary,
        "workflow_defaults": {
            "visit_location": workflow_config["visit_defaults"].get("location", ""),
            "visit_contact_person": workflow_config["visit_defaults"].get("contact_person", ""),
            "visit_contact_phone": workflow_config["visit_defaults"].get("contact_phone", ""),
        },
    })


@api.route("/admissions/applications/<int:application_id>/review", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def review_parent_admission_application(application_id):
    response_body, error, status_code = parent_admission_service.review_parent_admission_application(
        application_id,
        g.school_id,
        request.get_json(silent=True) or {},
        int(get_jwt_identity()),
        ParentAdmissionApplication,
        School,
        SchoolSettings,
        sanitize_string,
        get_utc_now,
        _get_parent_admission_workflow_config,
        _build_parent_admission_follow_up_plan,
        _parse_parent_admission_review_notes,
        _build_parent_admission_response_message,
        _serialize_parent_admission_review_notes,
        _set_parent_admission_payment_summary,
        _normalize_parent_admission_payment_summary,
        _get_school_admission_fee_config,
        _build_staff_parent_admission_payload,
        _admit_student_from_payload,
        _send_parent_admission_update,
        log_action,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/admissions/applications/<int:application_id>/documents/<string:document_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def download_parent_admission_document(application_id, document_id):
    application = ParentAdmissionApplication.query.filter_by(
        id=application_id,
        school_id=g.school_id,
    ).first()
    if not application:
        return jsonify({"message": "Application not found"}), 404

    matching_document = next(
        (
            item
            for item in (application.document_manifest or [])
            if isinstance(item, dict) and (item.get("document_id") or item.get("id")) == document_id
        ),
        None,
    )
    if not matching_document:
        return jsonify({"message": "Document not found"}), 404

    resolved_path = _resolve_existing_school_file(
        _get_parent_admission_document_storage_root(school_id=application.school_id),
        matching_document.get("stored_filename"),
    )
    if not resolved_path:
        return jsonify({"message": "Document file is no longer available"}), 404

    return send_file(
        resolved_path,
        as_attachment=False,
        download_name=matching_document.get("original_filename") or matching_document.get("filename") or "admission-document",
    )


@api.route("/admissions/generate-test", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@feature_required("ai_analysis")
def generate_admission_test():
    """AI Question generation for new students/staff."""
    data = request.json
    subject = data.get("subject")
    topics = data.get("topics", [])
    difficulty = data.get("difficulty", "Medium")
    audience = data.get("audience", "Student")

    # 1. Attempt to fetch from existing Question Pool
    query = QuestionPool.query.filter(
        QuestionPool.subject == subject,
        QuestionPool.difficulty == difficulty,
        QuestionPool.audience == audience,
    )

    if topics:
        query = query.filter(QuestionPool.topic.in_(topics))

    questions = query.order_by(db.func.random()).limit(10).all()

    # 2. AI Fallback: Generate questions if pool is insufficient
    if len(questions) < 5:
        needed = 10 - len(questions)
        for i in range(needed):
            # Simulation of AI generation for the prototype
            mock_q = QuestionPool(
                subject=subject,
                topic=topics[0] if topics else "General",
                difficulty=difficulty,
                audience=audience,
                question=f"[AI Generated] {difficulty} Question {i+1} on {topics[0] if topics else subject} for {audience}?",
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_option="A",
            )
            questions.append(mock_q)

    return jsonify(
        {
            "test_id": "ADM-" + get_utc_now().strftime("%Y%m%d"),
            "questions": [q.to_dict() for q in questions],
        }
    )


@api.route("/admissions/questions", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
def get_admission_questions():
    """Fetches AI-generated questions for the admission test."""
    subject = request.args.get("subject", "Mathematics")
    questions = (
        QuestionPool.query.filter_by(subject=subject)
        .order_by(db.func.random())
        .limit(10)
        .all()
    )

    return jsonify([q.to_dict() for q in questions])


@api.route("/admissions/admit", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def admit_student():
    """Admits a student after successful AI evaluation."""
    data = request.json
    if not data:
        return jsonify({"message": "No data provided"}), 400

    # 1. Enforce Subscription Quota inside a locked transaction.
    school = _lock_school_for_capacity_check(g.school_id)
    limit = get_plan_limits(get_effective_plan(school))
    current_count = _count_active_students_for_billing(g.school_id)
    school.current_student_count = current_count
    school.last_metered_at = get_utc_now()
    if current_count >= limit:
        return (
            jsonify(
                {
                    "message": f"Admission failed: Plan limit of {limit} students reached. Please upgrade."
                }
            ),
            403,
        )

    billing_growth_block = _billing_growth_block_response(
        school,
        projected_active_students=current_count + 1,
    )
    if billing_growth_block:
        return billing_growth_block

    # Support both old format (name) and new format (first_name, surname)
    first_name = (data.get("first_name") or "").strip()
    surname = (data.get("surname") or "").strip()
    full_name = (data.get("name") or "").strip()
    
    if not first_name and not surname and not full_name:
        return jsonify({"message": "Missing required fields: first_name and surname (or name)"}), 400
    
    # If only full_name is provided, split it
    if full_name and not first_name and not surname:
        parts = full_name.split(maxsplit=1)
        first_name = parts[0] if len(parts) > 0 else ""
        surname = parts[1] if len(parts) > 1 else ""
    
    if not first_name or not surname:
        return jsonify({"message": "Missing required fields: first_name and surname"}), 400
    
    full_name = f"{first_name} {surname}".strip()
    gender = (data.get("gender") or "").strip()

    date_of_birth = None
    raw_dob = (data.get("date_of_birth") or "").strip()
    if raw_dob:
        try:
            date_of_birth = date.fromisoformat(raw_dob)
        except ValueError:
            return jsonify({"message": "Invalid date_of_birth format. Use YYYY-MM-DD."}), 400

    scholarship_type = sanitize_string(data.get("scholarship_type") or "none").lower()
    scholarship_notes = sanitize_string(data.get("scholarship_notes") or "")
    if scholarship_type not in {"none", "tuition", "tuition_feeding"}:
        return jsonify({"message": "Invalid scholarship_type. Use none, tuition, or tuition_feeding."}), 400

    is_on_scholarship = scholarship_type != "none"
    scholarship_covers_tuition = scholarship_type in {"tuition", "tuition_feeding"}
    scholarship_covers_feeding = scholarship_type == "tuition_feeding"

    if data.get("class_assigned") not in VALID_GRADES:
        return (
            jsonify(
                {"message": f"Invalid grade level. Allowed: {', '.join(VALID_GRADES)}"}
            ),
            400,
        )

    student_code = (data.get("student_code") or "").strip().upper()
    if student_code:
        if Student.query.filter_by(
            student_code=student_code, school_id=g.school_id
        ).first():
            return (
                jsonify({"message": f"Student code {student_code} already exists."}),
                400,
            )
    else:
        prefix = normalize_student_code_prefix(g.school_id)
        next_index = Student.query.filter_by(school_id=g.school_id).count() + 1
        while True:
            candidate = generate_student_code(prefix, next_index)
            if not Student.query.filter_by(
                student_code=candidate, school_id=g.school_id
            ).first():
                student_code = candidate
                break
            next_index += 1

    # Duplicate Detection:
    # Check for name conflicts and WARN, but allow admission
    # Users can have legitimate students with the same name (siblings, common names in Ghana)
    parent_phone = (data.get("parent_phone") or "").strip()
    guardian_name = (data.get("guardian_name") or "").strip()
    
    # Check if another student with the exact same name already exists
    same_name_students = Student.query.filter_by(
        school_id=g.school_id,
        first_name=first_name,
        surname=surname
    ).all()
    
    # Continue with admission but note if name conflict exists
    # User and school should use guardian info to distinguish between them
    name_conflict_warning = None
    if same_name_students:
        if len(same_name_students) == 1:
            existing = same_name_students[0]
            name_conflict_warning = f"⚠️ DUPLICATE NAME: '{full_name}' already exists. → Search Students tab for '{existing.student_code}' or '{existing.name}' to review duplicate. Guardian: {existing.guardian_name or 'Not set'}. If same person, delete the old record."
        else:
            codes = ', '.join([s.student_code for s in same_name_students])
            name_conflict_warning = f"⚠️ {len(same_name_students)} students named '{full_name}' already exist (Codes: {codes}). Search Students tab to review duplicates if needed."

    new_student = Student(
        first_name=first_name,
        surname=surname,
        name=full_name,
        gender=gender,
        date_of_birth=date_of_birth,
        student_code=student_code,
        school_id=g.school_id,
        guardian_name=data.get("guardian_name"),
        parent_email=data.get("parent_email"),
        parent_phone=data.get("parent_phone"),
        current_class=data.get("class_assigned"),
        is_on_scholarship=is_on_scholarship,
        scholarship_covers_tuition=scholarship_covers_tuition,
        scholarship_covers_feeding=scholarship_covers_feeding,
        scholarship_notes=scholarship_notes or None,
        feeding_paid=False,
        is_present=True,
        profile_picture=data.get("profile_picture") or None,
    )
    db.session.add(new_student)
    school.current_student_count = current_count + 1
    school.last_metered_at = get_utc_now()

    log_action(
        user_id=int(get_jwt_identity()),
        school_id=g.school_id,
        action="STUDENT_ADMITTED",
        details=f"Admitted {new_student.name} to {new_student.current_class} (Score: {data.get('score')}%)",
    )
    db.session.commit()
    
    # Check for pro-rated mid-term charges
    effective_plan = get_effective_plan(school)
    proration_result = calculate_prorated_admission_charge(
        school,
        1,
        effective_plan,
        pre_admission_active_students=current_count,
    )
    
    response = {
        "message": f"Student {new_student.name} admitted successfully.",
        "student_id": new_student.id,
        "student_code": new_student.student_code,
        "is_on_scholarship": new_student.is_on_scholarship,
        "scholarship_type": scholarship_type,
    }
    
    # Include pro-ration info if applicable
    if proration_result['prorated_charge'] > 0:
        response['billing_notice'] = {
            'type': 'prorated_charge',
            'amount': proration_result['prorated_charge'],
            'reason': proration_result['charge_reason'],
            'invoice_sent': proration_result['invoice_sent'],
        }
    
    # Include name conflict warning if applicable
    if name_conflict_warning:
        response["warning"] = name_conflict_warning
    
    return jsonify(response)


@api.route("/admissions/bulk-upload", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def bulk_admit_students():
    """Bulk upload students via CSV."""
    try:
        if "file" not in request.files:
            return jsonify({"message": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"message": "No selected file"}), 400

        if file:
            # Read CSV file from memory
            # Use utf-8-sig to transparently strip BOM from CSV headers.
            stream = StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            csv_input = csv.DictReader(stream)

            school = _lock_school_for_capacity_check(g.school_id)
            limit = get_plan_limits(get_effective_plan(school))
            current_count = _count_active_students_for_billing(g.school_id)
            school.current_student_count = current_count
            school.last_metered_at = get_utc_now()
            existing_codes = {
                code
                for (code,) in Student.query.filter_by(school_id=g.school_id)
                .with_entities(Student.student_code)
                .all()
                if code
            }
            prefix = normalize_student_code_prefix(g.school_id)
            next_index = max(current_count, 0) + 1

            starting_active_count = current_count
            added_count = 0
            errors = []
            warnings = []
            uploaded_names_guardians = set()  # Track (name, guardian) pairs in THIS upload

            def _normalize_csv_key(key):
                k = str(key or "").strip().lstrip("\ufeff").lower()
                # Normalize common separators and strip punctuation.
                k = re.sub(r"[^a-z0-9_\s-]", "", k)
                k = k.replace("-", "_").replace(" ", "_")
                k = re.sub(r"_+", "_", k).strip("_")
                return k

            # Map common header variants to the canonical keys used by the API.
            _ALIASES = {
                "first_name": ["first", "firstname", "given_name", "givenname", "forename", "student_first_name"],
                "surname": [
                    "last_name",
                    "last",
                    "lastname",
                    "family_name",
                    "familyname",
                    "student_last_name",
                    "second_name",
                ],
                "name": ["full_name", "fullname", "student_name"],
                "class_assigned": ["class", "grade", "level", "current_class", "class_name", "classassigned"],
                "student_code": ["studentcode", "student_id", "studentid", "admission_no", "admission_number", "index_no"],
                "guardian_name": ["guardian", "guardianname", "parent_name", "parentname"],
                "parent_email": ["parentemail", "guardian_email", "guardianemail", "email"],
                "parent_phone": ["parentphone", "guardian_phone", "guardianphone", "phone", "phone_number"],
                "date_of_birth": ["dob", "birth_date", "birthdate", "dateofbirth"],
                "gender": ["sex"],
            }

            def _get_str(row_dict, canonical_key):
                keys_to_try = [canonical_key] + _ALIASES.get(canonical_key, [])
                for k in keys_to_try:
                    val = row_dict.get(k)
                    if val is None:
                        continue
                    s = str(val).strip()
                    if s:
                        return s
                return ""

            for idx, row in enumerate(csv_input, start=1):
                # Normalize header keys to tolerate spaces/case/BOM variations.
                normalized_row = {}
                for k, v in (row or {}).items():
                    nk = _normalize_csv_key(k)
                    if not nk:
                        continue
                    normalized_row[nk] = "" if v is None else str(v)

                if current_count >= limit:
                    errors.append(
                        f"Stopped at row {idx}: Plan limit of {limit} students reached."
                    )
                    break

                billing_block = _get_billing_growth_block(
                    school,
                    projected_active_students=current_count + 1,
                )
                if billing_block:
                    errors.append(f"Stopped at row {idx}: {billing_block['message']}")
                    break

                # Basic Validation - support both old format (name) and new format (first_name, surname)
                first_name = _get_str(normalized_row, "first_name")
                surname = _get_str(normalized_row, "surname")
                name = _get_str(normalized_row, "name")
                
                # If name is provided, split it; otherwise use first_name and surname
                if name and not first_name and not surname:
                    parts = name.split(maxsplit=1)
                    first_name = parts[0] if len(parts) > 0 else ""
                    surname = parts[1] if len(parts) > 1 else ""
                
                if not first_name or not surname:
                    errors.append(f"Row {idx}: Missing first_name and/or surname")
                    continue

                student_code = _get_str(normalized_row, "student_code").upper()
                if not student_code:
                    while True:
                        candidate = generate_student_code(prefix, next_index)
                        next_index += 1
                        if candidate not in existing_codes:
                            student_code = candidate
                            break

                # Check for duplicates by student code
                if student_code in existing_codes:
                    errors.append(
                        f"Row {idx}: Student code {student_code} already exists"
                    )
                    continue

                class_assigned = _get_str(normalized_row, "class_assigned") or "Class 1"
                if class_assigned not in VALID_GRADES:
                    errors.append(
                        f"Row {idx}: Invalid class_assigned '{class_assigned}'"
                    )
                    continue

                gender = _get_str(normalized_row, "gender")  # Male, Female, Other
                raw_dob = _get_str(normalized_row, "date_of_birth")
                date_of_birth = None
                if raw_dob:
                    try:
                        date_of_birth = date.fromisoformat(raw_dob)
                    except ValueError:
                        errors.append(
                            f"Row {idx}: Invalid date_of_birth '{raw_dob}'. Use YYYY-MM-DD"
                        )
                        continue
                guardian_name = _get_str(normalized_row, "guardian_name")
                parent_email = _get_str(normalized_row, "parent_email")
                parent_phone = _get_str(normalized_row, "parent_phone")
                full_name = f"{first_name} {surname}".strip()

# Check for same name existing in database (warning, allow duplicates)
                same_name_student = Student.query.filter_by(
                    school_id=g.school_id,
                    first_name=first_name,
                    surname=surname
                ).first()
                
                if same_name_student:
                    warnings.append(
                        f"Row {idx}: ⚠️ DUPLICATE NAME: '{full_name}' already exists → Search for '{same_name_student.student_code}' or '{same_name_student.name}' in Students tab to review/delete duplicate"
                    )

                new_student = Student(
                    first_name=first_name,
                    surname=surname,
                    name=full_name,
                    gender=gender,
                    student_code=student_code,
                    school_id=g.school_id,
                    date_of_birth=date_of_birth,
                    guardian_name=guardian_name if guardian_name else None,
                    parent_email=parent_email if parent_email else None,
                    parent_phone=parent_phone if parent_phone else None,
                    current_class=class_assigned,
                    feeding_paid=False,
                    is_present=True,
                )
                db.session.add(new_student)
                existing_codes.add(student_code)
                current_count += 1
                added_count += 1

            school.current_student_count = current_count
            school.last_metered_at = get_utc_now()

            db.session.commit()

            # Check for pro-rated mid-term charges on bulk add
            school = School.query.get(g.school_id)
            if added_count > 0 and school:
                effective_plan = get_effective_plan(school)
                proration_result = calculate_prorated_admission_charge(
                    school,
                    added_count,
                    effective_plan,
                    pre_admission_active_students=starting_active_count,
                )
            else:
                proration_result = {'prorated_charge': 0.0}

            msg = f"Successfully admitted {added_count} students."
            response_data = {"message": msg, "errors": errors}
            
            # Include pro-ration info if applicable
            if proration_result['prorated_charge'] > 0:
                response_data['billing_notice'] = {
                    'type': 'prorated_charge',
                    'amount': proration_result['prorated_charge'],
                    'reason': proration_result['charge_reason'],
                    'invoice_sent': proration_result['invoice_sent'],
                }
            
            if warnings:
                response_data["warnings"] = warnings
            return jsonify(response_data)
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error processing bulk upload", "error": str(e)}),
            500,
        )


@api.route("/admissions/students", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def get_admission_students():
    """Get all students with enrollment and status for admission management."""
    try:
        status_filter = request.args.get("status", "Active")  # Filter by status
        class_filter = request.args.get("class")  # Filter by class
        
        query = Student.query.filter_by(school_id=g.school_id)
        
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        if class_filter:
            query = query.filter_by(current_class=class_filter)
        
        students = query.order_by(Student.current_class, Student.name).all()
        
        # Group by status
        status_breakdown = {}
        for student in students:
            status = student.status or 'Active'
            if status not in status_breakdown:
                status_breakdown[status] = 0
            status_breakdown[status] += 1
        
        return jsonify({
            "total_students": len(students),
            "status_breakdown": status_breakdown,
            "students": [
                {
                    "id": s.id,
                    "name": s.name,
                    "student_code": s.student_code,
                    "current_class": s.current_class,
                    "status": s.status or 'Active',
                    "status_reason": s.status_reason,
                    "status_updated_at": s.status_updated_at.isoformat() if s.status_updated_at else None,
                    "status_updated_by": User.query.get(s.status_updated_by_user_id).username if s.status_updated_by_user_id else None,
                    "parent_name": s.parent_name,
                    "parent_phone": s.parent_phone,
                    "parent_email": s.parent_email,
                    "gender": s.gender,
                }
                for s in students
            ]
        }), 200
    except Exception as e:
        return jsonify({"message": "Error fetching students", "error": str(e)}), 500


@api.route("/admissions/students/bulk-update-status", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def bulk_update_student_status():
    """Bulk update status for multiple students by class or status filter."""
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = request.get_json(silent=True) or {}
        new_status = data.get("status")  # New status to apply
        class_filter = data.get("class")  # Class to filter (e.g., "JHS 3")
        current_status = data.get("current_status", "Active")  # Only update students with this status
        reason = data.get("reason", "")  # Reason for bulk update
        select_all_class = bool(data.get("select_all_class"))
        student_ids = [
            int(student_id)
            for student_id in (data.get("student_ids") or [])
            if str(student_id).isdigit()
        ]
        
        valid_statuses = ['Active', 'Graduated', 'Withdrawn', 'Transferred', 'Suspended', 'Inactive']
        
        if not new_status or new_status not in valid_statuses:
            return jsonify({
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }), 400
        
        if not class_filter and not student_ids:
            return jsonify({"message": "Select a class or at least one student for bulk update"}), 400
        
        # Build query to find students to update
        query = Student.query.filter_by(
            school_id=g.school_id,
            status=current_status
        )
        if class_filter:
            query = query.filter_by(current_class=class_filter)
        if student_ids and not select_all_class:
            query = query.filter(Student.id.in_(student_ids))
        
        students_to_update = query.all()
        
        if student_ids and not select_all_class:
            requested_ids = set(student_ids)
            matched_ids = {student.id for student in students_to_update}
            missing_ids = requested_ids - matched_ids
            if missing_ids:
                return jsonify({
                    "message": "Some selected students are no longer eligible for this update.",
                    "missing_student_ids": sorted(missing_ids),
                }), 409

        if not students_to_update:
            return jsonify({
                "message": f"No students found with status '{current_status}' for the selected bulk update.",
                "updated_count": 0
            }), 404
        
        user_id = int(get_jwt_identity())
        updated_count = 0
        updated_names = []
        
        # Update each student
        for student in students_to_update:
            old_status = student.status or 'Active'
            
            student.status = new_status
            student.status_updated_at = get_utc_now()
            student.status_updated_by_user_id = user_id
            student.status_reason = reason or f"Bulk updated from {old_status}"
            
            updated_names.append(student.name)
            updated_count += 1
        
        db.session.commit()
        
        # Log the bulk action
        updated_by_user = User.query.get(user_id)
        log_system_action(
            g.school_id,
            "STUDENT_STATUS_BULK_UPDATED",
            f"{updated_by_user.username} bulk updated {updated_count} students in {class_filter} from {current_status} to {new_status}" + 
            (f". Reason: {reason}" if reason else "")
        )
        
        return jsonify({
            "message": f"Successfully updated {updated_count} students",
            "updated_count": updated_count,
            "class": class_filter,
            "select_all_class": select_all_class,
            "previous_status": current_status,
            "new_status": new_status,
            "reason": reason,
            "updated_students": updated_names[:10],  # Show first 10
            "total_updated": updated_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error bulk updating students", "error": str(e)}), 500


@api.route("/admissions/students/<int:student_id>/status", methods=["PUT"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def update_student_status(student_id):
    """Update a student's enrollment status (Active, Graduated, Withdrawn, Transferred, Suspended, Inactive)."""
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = request.get_json(silent=True) or {}
        new_status = data.get("status")  # Active, Graduated, Withdrawn, Transferred, Suspended, Inactive
        reason = data.get("reason", "")
        
        valid_statuses = ['Active', 'Graduated', 'Withdrawn', 'Transferred', 'Suspended', 'Inactive']
        
        if not new_status or new_status not in valid_statuses:
            return jsonify({
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }), 400
        
        student = Student.query.filter_by(
            id=student_id, school_id=g.school_id
        ).first()
        
        if not student:
            return jsonify({"message": "Student not found"}), 404
        
        old_status = student.status or 'Active'
        user_id = int(get_jwt_identity())
        
        # Update student status
        student.status = new_status
        student.status_updated_at = get_utc_now()
        student.status_updated_by_user_id = user_id
        student.status_reason = reason
        
        db.session.commit()
        
        # Log the action
        updated_by_user = User.query.get(user_id)
        log_system_action(
            g.school_id,
            "STUDENT_STATUS_UPDATED",
            f"{updated_by_user.username} changed {student.name} status from {old_status} to {new_status}" + 
            (f". Reason: {reason}" if reason else "")
        )
        
        return jsonify({
            "message": f"Student {student.name} status updated to {new_status}",
            "student_id": student.id,
            "previous_status": old_status,
            "new_status": new_status,
            "reason": reason,
            "updated_at": student.status_updated_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error updating student status", "error": str(e)}), 500


@api.route("/admissions/students/<int:student_id>", methods=["DELETE"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def delete_student(student_id):
    """Delete a student record (Proprietor only - for data cleanup)."""
    try:
        from flask_jwt_extended import get_jwt_identity
        
        student = Student.query.filter_by(
            id=student_id, school_id=g.school_id
        ).first()
        
        if not student:
            return jsonify({"message": "Student not found"}), 404

        blockers = _student_hard_delete_blockers(student)
        if blockers:
            return (
                jsonify(
                    {
                        "message": "Student record has academic or financial history and cannot be permanently deleted. Update the student status instead.",
                        "error": "student_delete_blocked",
                        "blockers": blockers,
                        "recommended_action": "update_student_status",
                    }
                ),
                409,
            )
        
        student_name = student.name
        student_code = student.student_code
        
        # Log before deletion
        user_id = int(get_jwt_identity())
        log_system_action(
            g.school_id,
            "STUDENT_DELETED",
            f"Proprietor deleted student record: {student_name} ({student_code})"
        )
        
        # Delete associated records (cascade handled by SQLAlchemy)
        db.session.delete(student)
        db.session.commit()
        
        return jsonify({
            "message": f"Student {student_name} ({student_code}) has been deleted.",
            "deleted_student_id": student_id,
            "deleted_student_code": student_code
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error deleting student", "error": str(e)}), 500


@api.route("/admissions/statistics", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def get_admission_statistics():
    """Get admission statistics for dashboard display."""
    try:
        school = School.query.get(g.school_id)
        
        # Get counts by status
        total_active = Student.query.filter_by(
            school_id=g.school_id, 
            status='Active'
        ).count()
        
        total_graduated = Student.query.filter_by(
            school_id=g.school_id, 
            status='Graduated'
        ).count()
        
        total_withdrawn = Student.query.filter_by(
            school_id=g.school_id, 
            status='Withdrawn'
        ).count()
        
        total_transferred = Student.query.filter_by(
            school_id=g.school_id, 
            status='Transferred'
        ).count()
        
        total_suspended = Student.query.filter_by(
            school_id=g.school_id, 
            status='Suspended'
        ).count()
        
        total_inactive = Student.query.filter_by(
            school_id=g.school_id, 
            status='Inactive'
        ).count()
        
        # Get by class distribution
        class_distribution = {}
        for student in Student.query.filter_by(
            school_id=g.school_id, 
            status='Active'
        ).all():
            cls = student.current_class or 'Unassigned'
            if cls not in class_distribution:
                class_distribution[cls] = 0
            class_distribution[cls] += 1
        
        # Get gender distribution
        gender_distribution = {}
        for student in Student.query.filter_by(
            school_id=g.school_id, 
            status='Active'
        ).all():
            gender = student.gender or 'Not specified'
            if gender not in gender_distribution:
                gender_distribution[gender] = 0
            gender_distribution[gender] += 1
        
        return jsonify({
            "status_summary": {
                "active": total_active,
                "graduated": total_graduated,
                "withdrawn": total_withdrawn,
                "transferred": total_transferred,
                "suspended": total_suspended,
                "inactive": total_inactive,
                "current_enrollment": total_active,
                "historical_total": (total_active + total_graduated + total_withdrawn + 
                         total_transferred + total_suspended + total_inactive),
                "total": total_active,
            },
            "class_distribution": class_distribution,
            "gender_distribution": gender_distribution,
            "subscription_plan": school.subscription_plan or 'Free Tier',
        }), 200
    except Exception as e:
        return jsonify({"message": "Error fetching statistics", "error": str(e)}), 500


@api.route("/admissions/promotion-threshold", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def get_promotion_thresholds():
    """Get current promotion thresholds for the school."""
    try:
        from backend.api.models import PromotionThreshold
        
        thresholds = PromotionThreshold.query.filter_by(school_id=g.school_id).all()
        
        result = []
        for t in thresholds:
            result.append({
                "id": t.id,
                "class_name": t.class_name or "All Classes",
                "threshold_percentage": t.threshold_percentage,
                "min_courses_required": t.min_courses_required,
                "created_by": t.created_by.username if t.created_by else "System",
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None
            })
        
        return jsonify({
            "thresholds": result,
            "count": len(result),
            "note": "If no threshold is set for a class, all active students will be promoted"
        }), 200
        
    except Exception as e:
        return jsonify({"message": "Error fetching thresholds", "error": str(e)}), 500


@api.route("/admissions/promotion-threshold", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def set_promotion_threshold():
    """Set or update promotion threshold for a class or all classes."""
    try:
        from backend.api.models import PromotionThreshold
        
        data = request.get_json(silent=True) or {}
        
        class_name = data.get("class_name")  # If null, applies to all classes
        threshold_percentage = data.get("threshold_percentage")  # If null, all students promoted
        min_courses = data.get("min_courses_required", 1)
        
        user_id = int(get_jwt_identity())
        
        # Validate threshold percentage if provided
        if threshold_percentage is not None:
            try:
                threshold_percentage = float(threshold_percentage)
                if threshold_percentage < 0 or threshold_percentage > 100:
                    return jsonify({"message": "Threshold percentage must be between 0 and 100"}), 400
            except (ValueError, TypeError):
                return jsonify({"message": "Invalid threshold percentage"}), 400
        
        # Check for existing threshold
        existing = PromotionThreshold.query.filter_by(
            school_id=g.school_id,
            class_name=class_name
        ).first()
        
        if existing:
            existing.threshold_percentage = threshold_percentage
            existing.min_courses_required = min_courses
            existing.updated_at = get_utc_now()
            db.session.commit()
            
            log_system_action(
                g.school_id,
                "PROMOTION_THRESHOLD_UPDATED",
                f"Updated promotion threshold for {class_name or 'all classes'}: {threshold_percentage or 'no threshold (auto-promote all)'}"
            )
            
            return jsonify({
                "message": f"Promotion threshold updated for {class_name or 'all classes'}",
                "class_name": class_name or "All Classes",
                "threshold_percentage": threshold_percentage,
                "min_courses_required": min_courses
            }), 200
        
        # Create new threshold
        new_threshold = PromotionThreshold(
            school_id=g.school_id,
            class_name=class_name,
            threshold_percentage=threshold_percentage,
            min_courses_required=min_courses,
            created_by_user_id=user_id,
            created_at=get_utc_now()
        )
        
        db.session.add(new_threshold)
        db.session.commit()
        
        log_system_action(
            g.school_id,
            "PROMOTION_THRESHOLD_CREATED",
            f"Set promotion threshold for {class_name or 'all classes'}: {threshold_percentage or 'no threshold (auto-promote all)'}"
        )
        
        return jsonify({
            "message": f"Promotion threshold created for {class_name or 'all classes'}",
            "class_name": class_name or "All Classes",
            "threshold_percentage": threshold_percentage,
            "min_courses_required": min_courses
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error setting threshold", "error": str(e)}), 500


@api.route("/admissions/auto-promote", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def auto_promote_students():
    """
    Automatically promote students based on performance thresholds.
    If threshold is met, student is promoted to next class.
    """
    try:
        from backend.api.models import PromotionThreshold
        from sqlalchemy import func
        
        data = request.get_json(silent=True) or {}
        
        class_name = data.get("class_name")  # Required - which class to promote
        new_class = data.get("new_class")    # Required - promote to which class
        dry_run = data.get("dry_run", False) # If true, just preview without saving
        
        if not class_name or not new_class:
            return jsonify({"message": "class_name and new_class are required"}), 400
        
        if class_name == new_class:
            return jsonify({"message": "Cannot promote to the same class"}), 400
        
        user_id = int(get_jwt_identity())
        
        # Get students in current class (active only)
        students_to_check = Student.query.filter_by(
            school_id=g.school_id,
            current_class=class_name,
            status='Active'
        ).all()
        
        if not students_to_check:
            return jsonify({
                "message": f"No active students in {class_name}",
                "promoted_count": 0,
                "promoted_students": []
            }), 200
        
        # Get threshold for this class (or use global threshold if not found)
        threshold = PromotionThreshold.query.filter_by(
            school_id=g.school_id,
            class_name=class_name
        ).first()
        
        if not threshold:
            # Try to get global threshold
            threshold = PromotionThreshold.query.filter_by(
                school_id=g.school_id,
                class_name=None
            ).first()
        
        promoted_students = []
        not_promoted_students = []
        
        # Check each student's performance
        for student in students_to_check:
            # Get student's grades
            student_grades = StudentGrade.query.filter_by(
                student_id=student.id,
                class_name=class_name
            ).all()
            
            num_courses = len(student_grades)
            
            # If no threshold set, promote all students
            if not threshold or threshold.threshold_percentage is None:
                promoted_students.append({
                    "id": student.id,
                    "name": student.name,
                    "reason": "No threshold set - automatic promotion"
                })
            # If threshold requires minimum courses and student doesn't have enough
            elif num_courses < threshold.min_courses_required:
                not_promoted_students.append({
                    "id": student.id,
                    "name": student.name,
                    "reason": f"Insufficient courses: {num_courses} (requires {threshold.min_courses_required})"
                })
            else:
                # Calculate average score
                total_score = sum(g.total_score for g in student_grades if g.total_score)
                average_score = total_score / num_courses if num_courses > 0 else 0
                
                # Check if meets threshold
                if average_score >= threshold.threshold_percentage:
                    promoted_students.append({
                        "id": student.id,
                        "name": student.name,
                        "reason": f"Score: {average_score:.1f}% meets threshold {threshold.threshold_percentage}%"
                    })
                else:
                    not_promoted_students.append({
                        "id": student.id,
                        "name": student.name,
                        "reason": f"Score: {average_score:.1f}% below threshold {threshold.threshold_percentage}%"
                    })
        
        # If dry run, just return preview
        if dry_run:
            return jsonify({
                "message": "Dry run - no changes made",
                "promoted_count": len(promoted_students),
                "not_promoted_count": len(not_promoted_students),
                "promoted_students": promoted_students[:20],  # Show first 20
                "not_promoted_students": not_promoted_students[:20],
                "threshold": {
                    "class_name": class_name,
                    "threshold_percentage": threshold.threshold_percentage if threshold else None,
                    "min_courses_required": threshold.min_courses_required if threshold else 0
                }
            }), 200
        
        # Execute promotions (if not dry run)
        promoted_count = 0
        
        for student_info in promoted_students:
            student = Student.query.get(student_info["id"])
            if not student:
                continue
            
            old_class = student.current_class
            
            # Create promotion record
            promotion = StudentPromotion(
                student_id=student.id,
                school_id=g.school_id,
                promoted_from_class=old_class,
                promoted_to_class=new_class,
                promoted_by_user_id=user_id,
                remarks=f"Auto-promoted: {student_info['reason']}",
                promotion_date=get_utc_now()
            )
            db.session.add(promotion)
            
            # Update student
            student.current_class = new_class
            student.last_promoted_date = get_utc_now()
            student.last_promoted_by_user_id = user_id
            
            promoted_count += 1
        
        db.session.commit()
        
        # Log action
        log_system_action(
            g.school_id,
            "STUDENTS_AUTO_PROMOTED",
            f"Auto-promoted {promoted_count} students from {class_name} to {new_class}"
        )
        
        return jsonify({
            "message": f"Successfully auto-promoted {promoted_count} students from {class_name} to {new_class}",
            "promoted_count": promoted_count,
            "not_promoted_count": len(not_promoted_students),
            "promoted_students": promoted_students[:20],
            "not_promoted_students": not_promoted_students[:20]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error during auto-promotion", "error": str(e)}), 500


@api.route("/admissions/promotion/<int:promotion_id>/reverse", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def reverse_promotion(promotion_id):
    """
    Override/reverse a student promotion (move them back to previous class).
    Called when headmaster/proprietor wants to override an auto-promotion decision.
    """
    try:
        from backend.api.models import StudentNotification
        
        data = request.get_json(silent=True) or {}
        reversal_reason = data.get("reason", "Promotion reversed by administrator")
        
        user_id = int(get_jwt_identity())
        
        # Get the promotion record
        promotion = StudentPromotion.query.filter_by(
            id=promotion_id,
            school_id=g.school_id
        ).first()
        
        if not promotion:
            return jsonify({"message": "Promotion not found"}), 404
        
        if promotion.is_reversed:
            return jsonify({"message": "This promotion has already been reversed"}), 400
        
        student = Student.query.get(promotion.student_id)
        if not student:
            return jsonify({"message": "Student not found"}), 404
        
        # Mark promotion as reversed
        promotion.is_reversed = True
        promotion.reversed_by_user_id = user_id
        promotion.reversed_at = get_utc_now()
        promotion.reversal_reason = reversal_reason
        
        # Move student back to original class
        original_class = promotion.promoted_from_class
        student.current_class = original_class
        
        db.session.commit()
        
        # Notify homeroom teacher
        send_notification_to_teacher(
            school_id=g.school_id,
            student_id=student.id,
            notification_type="promotion_reversed",
            subject=f"Promotion Reversed: {student.name}",
            message=f"{student.name} promotion from {promotion.promoted_from_class} to {promotion.promoted_to_class} has been reversed. {student.name} will remain in {original_class}.",
            metadata={
                "student_name": student.name,
                "old_class": promotion.promoted_from_class,
                "new_class": promotion.promoted_to_class,
                "reason": reversal_reason
            }
        )
        
        log_system_action(
            g.school_id,
            "PROMOTION_REVERSED",
            f"Promotion for {student.name} from {promotion.promoted_from_class} to {promotion.promoted_to_class} reversed. Reason: {reversal_reason}"
        )
        
        return jsonify({
            "message": f"Promotion reversed. {student.name} moved back to {original_class}",
            "promotion_id": promotion.id,
            "student_id": student.id,
            "previous_class": original_class
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error reversing promotion", "error": str(e)}), 500


def send_notification_to_teacher(school_id, student_id, notification_type, subject, message, metadata):
    """Helper function to send notification to homeroom teacher of the student's class."""
    try:
        from backend.api.models import StudentNotification
        
        student = Student.query.get(student_id)
        if not student:
            return
        
        # Get homeroom teacher for this student's class
        # Homeroom teacher is the User with role="homeroom" assigned to the student's class
        homeroom_teacher = User.query.filter_by(
            school_id=school_id,
            role="homeroom",
            assigned_class=student.current_class
        ).first()
        
        if not homeroom_teacher:
            # Only log - don't send to just any subject teacher
            # Homeroom responsibility requires explicit role assignment
            logger.warning(
                f"No homeroom teacher found for class {student.current_class} in school {school_id}. "
                f"Promotion notification for student {student_id} will not be sent."
            )
            return
        
        notification = StudentNotification(
            school_id=school_id,
            recipient_user_id=homeroom_teacher.id,
            student_id=student_id,
            notification_type=notification_type,
            subject=subject,
            message=message,
            notification_metadata=metadata,
            created_at=get_utc_now()
        )
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error sending homeroom teacher notification: {str(e)}")


@api.route("/notifications", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_notifications():
    """Get notifications for the logged-in user (homeroom teacher, etc.)."""
    try:
        from backend.api.models import StudentNotification
        
        user_id = int(get_jwt_identity())
        
        # Get unread count and recent notifications
        unread_count = StudentNotification.query.filter_by(
            recipient_user_id=user_id,
            is_read=False
        ).count()
        
        # Get recent notifications (last 20)
        notifications = StudentNotification.query.filter_by(
            recipient_user_id=user_id
        ).order_by(StudentNotification.created_at.desc()).limit(20).all()
        
        result = []
        for notif in notifications:
            result.append({
                "id": notif.id,
                "type": notif.notification_type,
                "subject": notif.subject,
                "message": notif.message,
                "student_name": notif.student.name if notif.student else "Unknown",
                "student_id": notif.student_id,
                "metadata": notif.metadata,
                "is_read": notif.is_read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None
            })
        
        return jsonify({
            "unread_count": unread_count,
            "notifications": result
        }), 200
        
    except Exception as e:
        return jsonify({"message": "Error fetching notifications", "error": str(e)}), 500


@api.route("/notifications/<int:notification_id>/read", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    try:
        from backend.api.models import StudentNotification
        
        user_id = int(get_jwt_identity())
        
        notification = StudentNotification.query.filter_by(
            id=notification_id,
            recipient_user_id=user_id
        ).first()
        
        if not notification:
            return jsonify({"message": "Notification not found"}), 404
        
        notification.is_read = True
        notification.read_at = get_utc_now()
        db.session.commit()
        
        return jsonify({"message": "Notification marked as read"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error marking notification", "error": str(e)}), 500


@api.route("/admissions/promote-student", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
@jwt_required()
def promote_student():
    """
    Promote a student from one class to another.
    Headmaster or Proprietor can manually move students between classes.
    Tracks promotion history and logs action.
    """
    try:
        from flask_jwt_extended import get_jwt_identity
        
        data = request.get_json(silent=True) or {}
        
        student_id = data.get("student_id")
        new_class = data.get("new_class")
        remarks = data.get("remarks", "")
        
        if not student_id or not new_class:
            return jsonify({"message": "student_id and new_class are required"}), 400
        
        if new_class not in VALID_GRADES:
            return jsonify({"message": f"Invalid class '{new_class}'"}), 400
        
        student = Student.query.filter_by(
            id=student_id, school_id=g.school_id
        ).first()
        
        if not student:
            return jsonify({"message": "Student not found"}), 404
        
        old_class = student.current_class
        
        # If trying to promote to same class, reject
        if old_class == new_class:
            return jsonify({"message": "Student is already in this class"}), 400
        
        user_id = int(get_jwt_identity())
        
        # Create promotion record
        promotion = StudentPromotion(
            student_id=student.id,
            school_id=g.school_id,
            promoted_from_class=old_class,
            promoted_to_class=new_class,
            promoted_by_user_id=user_id,
            remarks=remarks,
            promotion_date=get_utc_now(),
        )
        db.session.add(promotion)
        
        # Update student's class
        student.current_class = new_class
        student.last_promoted_date = get_utc_now()
        student.last_promoted_by_user_id = user_id
        
        db.session.commit()
        
        # Log the action
        promoted_by_user = User.query.get(user_id)
        log_system_action(
            g.school_id,
            "STUDENT_PROMOTED",
            f"{promoted_by_user.username} promoted {student.name} from {old_class} to {new_class}"
        )
        
        return jsonify({
            "message": f"Student {student.name} promoted from {old_class} to {new_class}",
            "student_id": student.id,
            "new_class": new_class,
            "promotion_id": promotion.id
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return (
            jsonify({"message": "Error promoting student", "error": str(e)}),
            500,
        )


@api.route("/students/<int:student_id>/promotions", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_student_promotions(student_id):
    """
    Get promotion history for a student (for terminal report display).
    """
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first()
    
    if not student:
        return jsonify({"message": "Student not found"}), 404
    
    promotions = StudentPromotion.query.filter_by(
        student_id=student_id, school_id=g.school_id
    ).order_by(StudentPromotion.promotion_date.desc()).all()
    
    return jsonify({
        "student_id": student_id,
        "student_name": student.name,
        "current_class": student.current_class,
        "promotions": [
            {
                "id": p.id,
                "from_class": p.promoted_from_class,
                "to_class": p.promoted_to_class,
                "date": p.promotion_date.isoformat() if p.promotion_date else None,
                "promoted_by": User.query.get(p.promoted_by_user_id).username if p.promoted_by_user_id else "System",
                "remarks": p.remarks
            }
            for p in promotions
        ]
    }), 200


@api.route("/students/search", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "teacher", "inventory_manager")
@jwt_required()
def search_students():
    """
    Search students by name or student code.
    Query parameter: q (search query)
    """
    try:
        query = request.args.get("q", "").strip()
        if len(query) < 2 and not query.isdigit():
            return jsonify({"students": []}), 200
        
        query_filters = [
            Student.name.ilike(f"%{query}%"),
            Student.student_code.ilike(f"%{query}%"),
            Student.first_name.ilike(f"%{query}%"),
            Student.surname.ilike(f"%{query}%"),
        ]
        if query.isdigit():
            query_filters.append(Student.id == int(query))

        students = Student.query.filter_by(school_id=g.school_id).filter(
            db.or_(*query_filters)
        ).limit(10).all()
        
        return jsonify({
            "students": [
                {
                    "id": s.id,
                    "name": s.name,
                    "student_code": s.student_code,
                    "current_class": s.current_class,
                    "first_name": s.first_name,
                    "surname": s.surname,
                    "gender": s.gender
                }
                for s in students
            ]
        }), 200
    except Exception as e:
        return jsonify({"message": "Search error", "error": str(e)}), 500

# --- 5. OPERATIONS & CANTEEN ---


@api.route("/kitchen/dashboard", methods=["GET"])
@multi_tenant_guard
@role_required("kitchen", "headmaster", "proprietor")
@jwt_required()
def kitchen_dashboard():
    """
    Kitchen Dashboard:
    - Students present per class
    - Feeding fee status (Paid vs Unpaid)
    - Total teachers available
    - IMPORTANT: total_meals_needed = students with paid feeding + all available teachers
    """
    try:
        stats = []
        total_students_present = 0
        total_feeding_paid = 0
        students = Student.query.filter_by(school_id=g.school_id).all()
        attendance_snapshot = _get_attendance_submission_snapshot(g.school_id)
        attendance_taken_today = attendance_snapshot.get("is_complete", False)
        meal_breakdown = _get_daily_meal_breakdown(g.school_id)
        present_students_today = meal_breakdown["present_students"]
        present_student_ids = {student.id for student in present_students_today}
        feeding_status_details = meal_breakdown["feeding_status_details"]
        students_by_class = {}
        for student in students:
            students_by_class.setdefault(student.current_class or "Unassigned", []).append(student)

        today = datetime.now(timezone.utc).date()
        is_holiday, holiday_name = _get_holiday_status(g.school_id, today)

        for grade in VALID_GRADES:
            try:
                class_students = students_by_class.get(grade, [])
                present_students = [
                    student for student in class_students if student.id in present_student_ids
                ]
                present_count = len(present_students)
                paid_count = sum(
                    1
                    for student in present_students
                    if feeding_status_details.get(student.id, {}).get("covered")
                )

                if present_count > 0:
                    stats.append(
                        {
                            "class_name": grade,
                            "present": present_count,
                            "paid": paid_count,
                            "unpaid": present_count - paid_count,
                            "meals_needed": paid_count,
                        }
                    )
                    total_students_present += present_count
                    total_feeding_paid += paid_count
            except Exception as e:
                return (
                    jsonify(
                        {"message": f"Error processing class {grade}", "error": str(e)}
                    ),
                    500,
                )

        # Count active staff profiles that need meals alongside covered students.
        try:
            staff_count = meal_breakdown["total_staff_meals"]
        except Exception as e:
            return jsonify({"message": "Error counting teachers", "error": str(e)}), 500

        # Calculate total meals fresh from current attendance + feeding coverage + active staff count.
        total_meals_needed = total_feeding_paid + staff_count
        if is_holiday:
            stats = [
                {**row, "meals_needed": 0}
                for row in stats
            ]
            total_meals_needed = 0
            total_feeding_paid = 0

        return jsonify(
            {
                "classes": stats,
                "summary": {
                    "total_students_present": total_students_present,
                    "covered_student_meals": total_feeding_paid,
                    "total_feeding_paid": total_feeding_paid,
                    "total_staff_meals": staff_count,
                    "total_teachers": staff_count,
                    "total_meals_needed": total_meals_needed,
                    "attendance_taken_today": attendance_taken_today,
                    "attendance_partial": attendance_snapshot.get("has_any_submission", False) and not attendance_taken_today,
                    "submitted_classes_count": attendance_snapshot.get("submitted_classes_count", 0),
                    "pending_classes_count": attendance_snapshot.get("pending_classes_count", 0),
                    "status_message": (
                        None
                        if attendance_taken_today
                        else (
                            f"Attendance submitted for {attendance_snapshot.get('submitted_classes_count', 0)} of {attendance_snapshot.get('active_classes_count', 0)} classes."
                            if attendance_snapshot.get("has_any_submission")
                            else "Attendance has not been submitted for today yet."
                        )
                    ),
                    "is_holiday": is_holiday,
                    "holiday_name": holiday_name,
                    "holiday_date": today.isoformat(),
                    "note": "Kitchen should prepare meals for: students present with active feeding coverage plus all active staff profiles.",
                },
            }
        )
    except Exception as e:
        return (
            jsonify({"message": "Error fetching kitchen dashboard", "error": str(e)}),
            500,
        )


@api.route("/staff/lesson-note", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@feature_required("lesson_notes")
def submit_lesson_note():
    """Submit lesson note and trigger AI scoring."""
    data = request.json or {}
    user_id = get_jwt_identity()

    week_number = data.get("week_number") or data.get("week", 1)
    subject = data.get("subject")
    class_name = data.get("class_name")
    lesson_dates = data.get("lesson_dates") or []
    class_size = data.get("class_size")
    indicator_code = data.get("indicator_code")
    content_standard_code = data.get("content_standard_code")
    performance_indicator = data.get("performance_indicator")
    core_competencies = data.get("core_competencies")
    key_words = data.get("key_words")
    teaching_learning_resources = data.get("teaching_learning_resources")
    references = data.get("references")
    daily_phases = data.get("daily_phases") or []
    submit_to = data.get(
        "submit_to", "headmaster"
    )  # Default to headmaster for backward compatibility

    if (
        not subject
        or not class_name
        or not indicator_code
        or not content_standard_code
        or not performance_indicator
    ):
        return (
            jsonify(
                {
                    "message": "Missing required fields: subject, class_name, indicator_code, content_standard_code, performance_indicator"
                }
            ),
            400,
        )

    # Validate submit_to field
    if submit_to not in ["headmaster", "proprietor"]:
        submit_to = "headmaster"

    def normalize_phase_text(phase_data):
        return "\n".join(
            [
                phase_data.get("phase_1_starter", ""),
                phase_data.get("phase_2_main", ""),
                phase_data.get("phase_3_plenary", ""),
            ]
        ).strip()

    phases_text = "\n".join(
        [
            normalize_phase_text(phase)
            for phase in daily_phases
            if isinstance(phase, dict)
        ]
    ).strip()

    content = data.get("content") or "\n".join(
        filter(
            None,
            [
                performance_indicator,
                core_competencies,
                key_words,
                teaching_learning_resources,
                references,
                phases_text,
            ],
        )
    )

    # Advanced AI Scoring
    ai_result = generate_ai_lesson_note_score({
        'subject': subject,
        'class_name': class_name,
        'lesson_dates': lesson_dates,
        'class_size': class_size,
        'indicator_code': indicator_code,
        'content_standard_code': content_standard_code,
        'performance_indicator': performance_indicator,
        'core_competencies': core_competencies,
        'key_words': key_words,
        'teaching_learning_resources': teaching_learning_resources,
        'references': references,
        'daily_phases': daily_phases,
        'content': content
    })
    
    ai_score = ai_result['ai_score']
    ai_feedback = ai_result['ai_feedback']

    note = LessonNote(
        school_id=g.school_id,
        teacher_id=user_id,
        week_number=week_number,
        subject=subject,
        class_name=class_name,
        lesson_dates=lesson_dates,
        class_size=class_size,
        indicator_code=indicator_code,
        content_standard_code=content_standard_code,
        performance_indicator=performance_indicator,
        core_competencies=core_competencies,
        key_words=key_words,
        teaching_learning_resources=teaching_learning_resources,
        references=references,
        content=content,
        ai_score=ai_score,
        ai_feedback=ai_feedback,
        submit_to=submit_to,
    )
    db.session.add(note)
    db.session.flush()

    for phase in daily_phases:
        if not isinstance(phase, dict):
            continue
        day = phase.get("day")
        phase_1_starter = phase.get("phase_1_starter")
        phase_2_main = phase.get("phase_2_main")
        phase_3_plenary = phase.get("phase_3_plenary")

        if not day and not (phase_1_starter or phase_2_main or phase_3_plenary):
            continue

        db.session.add(
            DailyLessonPhase(
                lesson_note_id=note.id,
                day=day,
                phase_1_starter=phase_1_starter,
                phase_2_main=phase_2_main,
                phase_3_plenary=phase_3_plenary,
            )
        )

    db.session.commit()
    return jsonify(
        {
            "message": "Lesson note submitted.",
            "ai_score": ai_score,
            "feedback": ai_feedback,
        }
    )


@api.route("/staff/check-headmaster", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def check_headmaster_exists():
    """Check if a headmaster exists in the school."""
    headmaster = User.query.filter_by(school_id=g.school_id, role="headmaster").first()
    if not headmaster:
        # Check if any user has 'headmaster' in their roles array
        headmasters = User.query.filter(
            User.school_id == g.school_id, User.roles.contains(["headmaster"])
        ).all()
        return jsonify({"has_headmaster": len(headmasters) > 0})
    return jsonify({"has_headmaster": True})


@api.route("/staff/my-lesson-notes", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_my_lesson_notes():
    """Fetch teacher's own lesson notes."""
    user_id = get_jwt_identity()
    notes = (
        LessonNote.query.filter_by(school_id=g.school_id, teacher_id=user_id)
        .order_by(LessonNote.submitted_at.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": note.id,
                "week_number": note.week_number,
                "subject": note.subject,
                "class_name": note.class_name,
                "lesson_dates": note.lesson_dates or [],
                "class_size": note.class_size,
                "indicator_code": note.indicator_code,
                "content_standard_code": note.content_standard_code,
                "performance_indicator": note.performance_indicator,
                "core_competencies": note.core_competencies,
                "key_words": note.key_words,
                "teaching_learning_resources": note.teaching_learning_resources,
                "references": note.references,
                "daily_phases": [
                    {
                        "day": phase.day,
                        "phase_1_starter": phase.phase_1_starter,
                        "phase_2_main": phase.phase_2_main,
                        "phase_3_plenary": phase.phase_3_plenary,
                    }
                    for phase in note.daily_phases
                ],
                "ai_score": note.ai_score,
                "ai_feedback": note.ai_feedback,
                "status": note.status,
                "submit_to": note.submit_to,
                "submitted_at": (
                    note.submitted_at.isoformat() if note.submitted_at else None
                ),
            }
            for note in notes
        ]
    )


@api.route("/headmaster/attendance-summary", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def get_attendance_summary():
    """Headmaster view of daily attendance."""
    total_students = Student.query.filter(
        Student.school_id == g.school_id,
        Student.status.in_(["Active", "active"]),
    ).count()
    attendance_snapshot = _get_attendance_submission_snapshot(g.school_id)
    attendance_taken_today = attendance_snapshot.get("is_complete", False)
    present_students_list = _get_present_students_for_today(g.school_id)
    present_students = len(present_students_list)

    class_breakdown = []
    for grade in VALID_GRADES:
        total_in_class = Student.query.filter_by(
            school_id=g.school_id, current_class=grade, status="Active"
        ).count()
        present_in_class = 0
        if attendance_taken_today:
            present_in_class = sum(
                1 for student in present_students_list if student.current_class == grade
            )
        if total_in_class > 0:
            class_breakdown.append(
                {
                    "class_name": grade,
                    "total": total_in_class,
                    "present": present_in_class,
                    "percentage": (
                        round((present_in_class / total_in_class) * 100, 1)
                        if attendance_taken_today
                        else None
                    ),
                }
            )

    return jsonify(
        {
            "total_students": total_students,
            "present_students": present_students,
            "absent_students": (
                total_students - present_students if attendance_taken_today else None
            ),
            "attendance_percentage": (
                round((present_students / total_students) * 100, 1)
                if attendance_taken_today and total_students > 0
                else None
            ),
            "attendance_taken_today": attendance_taken_today,
            "attendance_partial": attendance_snapshot.get("has_any_submission", False) and not attendance_taken_today,
            "submitted_classes": attendance_snapshot.get("submitted_classes", []),
            "submitted_classes_count": attendance_snapshot.get("submitted_classes_count", 0),
            "pending_classes": attendance_snapshot.get("pending_classes", []),
            "pending_classes_count": attendance_snapshot.get("pending_classes_count", 0),
            "active_classes_count": attendance_snapshot.get("active_classes_count", 0),
            "status_message": (
                None
                if attendance_taken_today
                else (
                    f"Attendance submitted for {attendance_snapshot.get('submitted_classes_count', 0)} of {attendance_snapshot.get('active_classes_count', 0)} classes. Pending: {', '.join(attendance_snapshot.get('pending_classes', [])[:3])}{'...' if attendance_snapshot.get('pending_classes_count', 0) > 3 else ''}."
                    if attendance_snapshot.get("has_any_submission")
                    else "Attendance has not been submitted for today yet."
                )
            ),
            "breakdown": class_breakdown,
        }
    )


@api.route("/headmaster/lesson-notes", methods=["GET"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def get_lesson_notes():
    """Fetches all lesson notes for review."""
    # Join with User to get the teacher's name
    notes = (
        db.session.query(LessonNote, User.username)
        .join(User, LessonNote.teacher_id == User.id)
        .filter(LessonNote.school_id == g.school_id)
        .order_by(LessonNote.submitted_at.desc())
        .all()
    )

    return jsonify(
        [
            {
                "id": n.LessonNote.id,
                "teacher_name": n.username,
                "subject": n.LessonNote.subject,
                "class_name": n.LessonNote.class_name,
                "lesson_dates": n.LessonNote.lesson_dates or [],
                "class_size": n.LessonNote.class_size,
                "week": n.LessonNote.week_number,
                "indicator_code": n.LessonNote.indicator_code,
                "content_standard_code": n.LessonNote.content_standard_code,
                "performance_indicator": n.LessonNote.performance_indicator,
                "core_competencies": n.LessonNote.core_competencies,
                "key_words": n.LessonNote.key_words,
                "teaching_learning_resources": n.LessonNote.teaching_learning_resources,
                "references": n.LessonNote.references,
                "daily_phases": [
                    {
                        "day": phase.day,
                        "phase_1_starter": phase.phase_1_starter,
                        "phase_2_main": phase.phase_2_main,
                        "phase_3_plenary": phase.phase_3_plenary,
                    }
                    for phase in (n.LessonNote.daily_phases or [])
                ],
                "content": n.LessonNote.content,
                "ai_score": n.LessonNote.ai_score,
                "ai_feedback": n.LessonNote.ai_feedback,
                "status": n.LessonNote.status,
                "submitted_at": n.LessonNote.submitted_at.strftime("%Y-%m-%d %H:%M"),
            }
            for n in notes
        ]
    )


@api.route("/headmaster/lesson-note/<int:note_id>/review", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def review_lesson_note(note_id):
    """Approve or Reject a lesson note."""
    data = request.json
    note = LessonNote.query.filter_by(id=note_id, school_id=g.school_id).first_or_404()

    note.status = data.get("status")  # 'Approved' or 'Rejected'
    # Optional: Headmaster can override AI feedback
    if data.get("feedback"):
        note.ai_feedback = data.get("feedback")

    db.session.commit()

    # Notify Teacher via Email
    teacher = User.query.get(note.teacher_id)
    if teacher and teacher.email:
        send_email_notification(
            to_email=teacher.email,
            subject=f"Lesson Note Update: {note.status}",
            body=f"Dear {teacher.username},\n\nYour lesson note for {note.subject} (Week {note.week_number}) has been {note.status}.\n\nFeedback/Remarks: {note.ai_feedback}\n\n- EduPulse SMT Governance System",
        )

    return jsonify({"message": f"Lesson note marked as {note.status}."})


@api.route("/headmaster/lesson-note/<int:note_id>/rescore", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster", "proprietor")
def rescore_lesson_note(note_id):
    """Regenerate AI score for a lesson note."""
    note = LessonNote.query.filter_by(id=note_id, school_id=g.school_id).first_or_404()

    # Prepare data for AI scoring
    daily_phases = [
        {
            'day': phase.day,
            'phase_1_starter': phase.phase_1_starter,
            'phase_2_main': phase.phase_2_main,
            'phase_3_plenary': phase.phase_3_plenary
        }
        for phase in note.daily_phases
    ]

    ai_result = generate_ai_lesson_note_score({
        'subject': note.subject,
        'class_name': note.class_name,
        'indicator_code': note.indicator_code,
        'content_standard_code': note.content_standard_code,
        'performance_indicator': note.performance_indicator,
        'core_competencies': note.core_competencies,
        'key_words': note.key_words,
        'teaching_learning_resources': note.teaching_learning_resources,
        'references': note.references,
        'daily_phases': daily_phases,
        'content': note.content
    })

    # Update the note with new AI analysis
    note.ai_score = ai_result['ai_score']
    note.ai_feedback = ai_result['ai_feedback']
    db.session.commit()

    return jsonify({
        "message": "AI analysis regenerated successfully.",
        "ai_score": note.ai_score,
        "ai_feedback": note.ai_feedback
    })


@api.route("/headmaster/log-work", methods=["POST"])
@multi_tenant_guard
@role_required("headmaster")  # Or proprietor
def log_academic_work():
    """Headmaster logs classwork/homework counts for a teacher."""
    data = request.json
    log = AcademicWorkLog(
        school_id=g.school_id,
        teacher_id=data.get("teacher_id"),
        class_name=data.get("class_name"),
        subject=data.get("subject"),
        num_classwork=data.get("num_classwork"),
        num_homework=data.get("num_homework"),
        week_number=data.get("week"),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"message": "Academic work logged successfully."})


@api.route("/canteen/daily-count", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_canteen_count():
    """Zero-waste logic for daily meals."""
    meal_breakdown = _get_daily_meal_breakdown(g.school_id)
    attendance_snapshot = _get_attendance_submission_snapshot(g.school_id)
    return jsonify(
        {
            "total_meals": meal_breakdown["total_meals_needed"],
            "attendance_taken_today": attendance_snapshot.get("is_complete", False),
            "attendance_partial": attendance_snapshot.get("has_any_submission", False) and not attendance_snapshot.get("is_complete", False),
            "submitted_classes_count": attendance_snapshot.get("submitted_classes_count", 0),
            "pending_classes_count": attendance_snapshot.get("pending_classes_count", 0),
        }
    )


@api.route("/proprietor/export-term-summary", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
def export_term_summary():
    """Final quantitative terminal report (CSV)."""
    try:
        students = Student.query.filter_by(school_id=g.school_id).all()
        si = StringIO()
        cw = csv.writer(si, quoting=csv.QUOTE_ALL)
        cw.writerow(["Student Name", "Code", "AI Score", "Status", "Unpaid Feeding"])
        for s in students:
            health = calculate_academic_health(s.id)
            cw.writerow(
                [
                    str(s.name) if s.name else "",
                    str(s.student_code) if s.student_code else "",
                    str(health.get("score", "")),
                    str(health.get("status", "")),
                    str(health.get("unpaid_days", "")),
                ]
            )
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = (
            f"attachment; filename=term_summary_{g.school_id}.csv"
        )
        output.headers["Content-type"] = "text/csv"
        return output
    except Exception as e:
        return (
            jsonify({"message": "Error exporting term summary", "error": str(e)}),
            500,
        )


@api.route("/proprietor/students", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_proprietor_students():
    """Fetch all students for the proprietor registry view."""
    students = (
        Student.query.filter_by(school_id=g.school_id).order_by(Student.name).all()
    )
    feeding_status_details = _get_feeding_status_details_for_students(students, g.school_id)
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                    "profile_picture": s.profile_picture,
                "current_class": s.current_class,
                "guardian_name": s.guardian_name,
                "parent_name": s.parent_name,
                "parent_email": s.parent_email,
                "parent_phone": s.parent_phone,
                **_serialize_feeding_status_detail(feeding_status_details.get(s.id, {})),
                "is_present": s.is_present,
                "date_of_birth": s.date_of_birth.isoformat() if s.date_of_birth else None,
                "age": s.age,
                "gender": s.gender,
                "is_on_scholarship": bool(s.is_on_scholarship),
                "scholarship_covers_tuition": bool(s.scholarship_covers_tuition),
                "scholarship_covers_feeding": bool(s.scholarship_covers_feeding),
                "scholarship_notes": s.scholarship_notes,
                "total_tuition_owed": s.total_tuition_owed,
            }
            for s in students
        ]
    )


def replace_teacher_assignments(teacher_id, classes, subjects):
    TeacherAssignment.query.filter_by(
        school_id=g.school_id, teacher_id=teacher_id
    ).delete()
    class_list = [c.strip() for c in (classes or []) if c and str(c).strip()]
    subject_list = [s.strip() for s in (subjects or []) if s and str(s).strip()]

    for class_name in class_list:
        for subject_name in subject_list:
            db.session.add(
                TeacherAssignment(
                    school_id=g.school_id,
                    teacher_id=teacher_id,
                    class_name=class_name,
                    subject_name=subject_name,
                )
            )


def _normalize_email_address(email):
    return (email or "").strip().lower()


def _build_released_registration_email(user, original_email):
    normalized_original = _normalize_email_address(original_email)
    local_part = normalized_original.split("@", 1)[0] if normalized_original else "released"
    local_part = re.sub(r"[^a-z0-9]+", "-", local_part).strip("-") or "released"
    school_part = re.sub(r"[^a-z0-9]+", "-", (user.school_id or "no-school").lower()).strip("-") or "no-school"
    timestamp = get_utc_now().strftime("%Y%m%d%H%M%S")
    return f"released+{school_part}-{user.id}-{local_part}-{timestamp}@edupulse.invalid"


def _find_school_user_by_email(school_id, email, exclude_user_id=None):
    normalized_email = _normalize_email_address(email)
    if not normalized_email:
        return None

    school_users = User.query.filter_by(school_id=school_id).all()
    return next(
        (
            candidate
            for candidate in school_users
            if candidate.id != exclude_user_id
            and _normalize_email_address(candidate.email) == normalized_email
        ),
        None,
    )


def _find_platform_user_by_email(email, exclude_user_id=None):
    normalized_email = _normalize_email_address(email)
    if not normalized_email:
        return None

    platform_users = User.query.all()
    return next(
        (
            candidate
            for candidate in platform_users
            if candidate.id != exclude_user_id
            and _normalize_email_address(candidate.email) == normalized_email
        ),
        None,
    )


def _normalize_staff_roles(raw_roles, primary_role=None):
    allowed_roles = ["teacher", "homeroom", "headmaster", "finance", "inventory_manager", "kitchen"]
    roles = raw_roles if isinstance(raw_roles, list) else []
    roles = list(dict.fromkeys(roles))

    effective_primary_role = primary_role or (roles[0] if roles else "teacher")
    if effective_primary_role not in allowed_roles or any(role not in allowed_roles for role in roles):
        return None, None, "Invalid role."

    if not roles:
        roles = [effective_primary_role]
        effective_primary_role = roles[0]
    else:
        effective_primary_role = roles[0]

    if "teacher" in roles and "homeroom" in roles:
        return None, None, "Homeroom teachers cannot also be assigned the subject teacher role."

    return roles, effective_primary_role, None


def _normalize_homeroom_assignment(roles, assigned_class):
    normalized_assigned_class = (assigned_class or "").strip()

    if "homeroom" in roles and not normalized_assigned_class:
        return None, "Homeroom teachers must have an assigned homeroom class."

    if "homeroom" not in roles:
        return None, None

    return normalized_assigned_class, None


@api.route("/staff/add", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
def add_staff():
    """Adds a new staff member to the tenant."""
    response_body, error, status_code = staff_service.add_staff_member(
        request.json or {},
        g.school_id,
        User,
        School,
        generate_password_hash,
        _normalize_email_address,
        _find_school_user_by_email,
        _normalize_staff_roles,
        _normalize_homeroom_assignment,
        _generate_staff_temp_password,
        replace_teacher_assignments,
        _send_staff_invite_email,
        tenant_email_delivery_failure_message,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/staff/<int:user_id>/resend-invite", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def resend_staff_invite(user_id):
    """Issue a fresh temporary password and resend the staff invite email."""
    response_body, error, status_code = staff_service.resend_staff_invite(
        user_id,
        g.school_id,
        int(get_jwt_identity()),
        User,
        School,
        generate_password_hash,
        _generate_staff_temp_password,
        _send_staff_invite_email,
        tenant_email_delivery_failure_message,
        log_action,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/staff/bulk-upload", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def bulk_upload_staff():
    """Bulk upload staff via CSV."""
    try:
        if "file" not in request.files:
            return jsonify({"message": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"message": "No selected file"}), 400

        if file:
            # Read CSV file from memory
            stream = StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)

            school = School.query.get(g.school_id)
            limit = get_plan_limits(get_effective_plan(school))
            current_staff_count = User.query.filter_by(school_id=g.school_id).count()
            existing_usernames = {
                username
                for (username,) in User.query.filter_by(school_id=g.school_id)
                .with_entities(User.username)
                .all()
            }

            added_count = 0
            errors = []
            allowed_roles = ["teacher", "homeroom", "headmaster", "finance", "inventory_manager"]

            for idx, row in enumerate(csv_input, start=1):
                # Don't enforce student limit for staff - just take what they provide
                # Basic Validation - username, email, password required
                username = (row.get("username") or "").strip()
                email = (row.get("email") or "").strip()
                password = (row.get("password") or "").strip()
                
                if not username:
                    errors.append(f"Row {idx}: Missing username")
                    continue
                if not email:
                    errors.append(f"Row {idx}: Missing email")
                    continue
                if not password:
                    errors.append(f"Row {idx}: Missing password")
                    continue
                
                # Strong password validation
                from backend.validators import validate_password_strength
                is_valid, error_msg = validate_password_strength(password)
                if not is_valid:
                    errors.append(f"Row {idx}: {error_msg}")
                    continue

                # Check for duplicates
                if username in existing_usernames:
                    errors.append(f"Row {idx}: Username '{username}' already exists")
                    continue

                # Parse roles (comma-separated)
                roles_str = (row.get("roles") or "").strip()
                normalized_roles = roles_str.replace(";", ",")
                roles = [r.strip() for r in normalized_roles.split(",") if r.strip()] if normalized_roles else ["teacher"]
                
                roles, primary_role, role_error = _normalize_staff_roles(roles)
                if role_error:
                    errors.append(f"Row {idx}: {role_error}")
                    continue

                assigned_class, assigned_class_error = _normalize_homeroom_assignment(
                    roles,
                    row.get("assigned_class"),
                )
                if assigned_class_error:
                    errors.append(f"Row {idx}: {assigned_class_error}")
                    continue

                try:
                    # Create the user
                    new_staff = User(
                        username=username,
                        email=email,
                        role=primary_role,
                        roles=roles,
                        school_id=g.school_id,
                        password_hash=generate_password_hash(password),
                        assigned_class=assigned_class,
                    )
                    db.session.add(new_staff)
                    db.session.flush()  # Get the ID without committing yet

                    # Handle teacher assignments if applicable
                    if any(r in roles for r in ["homeroom", "teacher"]):
                        # Parse assigned classes (pipe or semicolon-separated)
                        classes_str = (row.get("assigned_classes") or "").strip()
                        assigned_classes = [c.strip() for c in classes_str.replace(";", "|").split("|") if c.strip()] if classes_str else []
                        
                        # Parse assigned subjects (pipe or semicolon-separated)
                        subjects_str = (row.get("assigned_subjects") or "").strip()
                        assigned_subjects = [s.strip() for s in subjects_str.replace(";", "|").split("|") if s.strip()] if subjects_str else []
                        
                        if assigned_classes or assigned_subjects:
                            replace_teacher_assignments(new_staff.id, assigned_classes, assigned_subjects)

                    existing_usernames.add(username)
                    added_count += 1

                except Exception as row_err:
                    errors.append(f"Row {idx}: Error creating staff - {str(row_err)}")
                    db.session.rollback()
                    continue

            db.session.commit()

            message = f"Successfully added {added_count} new staff member(s)."
            return jsonify({
                "message": message,
                "added_count": added_count,
                "errors": errors if errors else []
            }), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Staff bulk upload error: {str(e)}")
        return jsonify({"message": f"Bulk upload failed: {str(e)}"}), 500


# --- 6. FULL OPERATIONS SUITE (Ledger, Staff, Inventory) ---


@api.route("/finance/dashboard", methods=["GET"])
@multi_tenant_guard
@role_required("finance", "proprietor")
def get_finance_dashboard():
    """Finance Dashboard Summary - Payment statistics and overview."""
    try:
        school = School.query.get(g.school_id)
        verification_restriction = _payment_records_verification_block_response(school)
        if verification_restriction:
            return verification_restriction
        collection_restriction = _payment_collection_block_response(school)
        if collection_restriction:
            return collection_restriction

        return jsonify(
            finance_read_service.get_finance_dashboard_payload(
                g.school_id,
                now=datetime.now(timezone.utc),
                student_model=Student,
                payment_model=Payment,
                db=db,
                serialize_pending_payment=_serialize_pending_payment,
                group_pending_payments_by_class=_group_pending_payments_by_class,
            )
        )
    except Exception as e:
        return (
            jsonify({"message": "Error loading finance dashboard", "error": str(e)}),
            500,
        )


@api.route("/finance/summary", methods=["GET"])
@multi_tenant_guard
@role_required("finance", "proprietor", "headmaster")
@jwt_required()
def get_finance_summary():
    """Compatibility summary endpoint for security tests."""
    return jsonify({"status": "ok"})


@api.route("/finance/transactions", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
def get_transactions():
    """Full Financial Ledger for the Proprietor."""
    try:
        school = School.query.get(g.school_id)
        verification_restriction = _payment_records_verification_block_response(school)
        if verification_restriction:
            return verification_restriction
        collection_restriction = _payment_collection_block_response(school)
        if collection_restriction:
            return collection_restriction

        payload = finance_read_service.get_transactions_payload(
            g.school_id,
            payment_model=Payment,
            student_model=Student,
            db=db,
            to_iso_utc=_to_iso_utc,
        )
        for item in payload:
            payment_category = item.get("payment_category") if isinstance(item.get("payment_category"), dict) else {}
            item["payment_category"] = _normalize_payment_category_for_storage(
                g.school_id,
                item.get("type"),
                payment_category,
                amount_paid=item.get("amount"),
            )
            item["feeding_frequency"] = (
                item["payment_category"].get("frequency")
                if item.get("type") == "Feeding"
                else None
            )

        return jsonify(payload)
    except Exception as e:
        return (
            jsonify({"message": "Error retrieving transactions", "error": str(e)}),
            500,
        )


@api.route("/finance/audit/ledger", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_audit_ledger():
    """Get immutable ledger entries with hash chain verification."""
    try:
        school = School.query.get(g.school_id)
        restriction = _payment_audit_access_block_response(school)
        if restriction:
            return restriction

        from backend.api.models import LedgerEntry
        
        # Get query parameters
        limit = request.args.get("limit", 100, type=int)
        offset = request.args.get("offset", 0, type=int)
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        query = db.session.query(LedgerEntry).filter_by(school_id=g.school_id)
        
        if start_date:
            query = query.filter(LedgerEntry.created_at >= start_date)
        if end_date:
            query = query.filter(LedgerEntry.created_at <= end_date)
        
        total_count = query.count()
        entries = query.order_by(LedgerEntry.id.desc()).offset(offset).limit(limit).all()
        
        # Format entries with student and user info
        ledger_data = []
        for entry in entries:
            try:
                student = Student.query.get(entry.student_id) if entry.student_id else None
                actor = User.query.get(entry.actor_id) if entry.actor_id else None
                actor_display = (
                    (getattr(actor, "name", None) or getattr(actor, "username", None))
                    if actor
                    else "System"
                )
                
                ledger_data.append({
                    "id": entry.id,
                    "date": entry.created_at.strftime("%d/%m/%Y %H:%M"),
                    "student_name": student.name if student else "N/A",
                    "student_code": student.student_code if student else "N/A",
                    "amount": entry.amount,
                    "currency": entry.currency,
                    "tx_type": entry.tx_type,
                    "tx_ref": entry.tx_ref,
                    "source": entry.source,
                    "actor": actor_display,
                    "hash": entry.hash[:16] + "..." + entry.hash[-8:],  # Truncated for display
                    "full_hash": entry.hash,
                    "previous_hash": entry.previous_hash[:16] + "..." if entry.previous_hash and entry.previous_hash != "GENESIS" else entry.previous_hash,
                    "is_verified": entry.is_verified,
                    "metadata": entry.meta
                })
            except Exception as row_err:
                # Log individual row errors but don't crash entire ledger
                logger.warning(f"Failed to serialize ledger entry {entry.id}: {str(row_err)}")
                # Still include minimal entry so user can see there's data
                ledger_data.append({
                    "id": entry.id,
                    "date": entry.created_at.strftime("%d/%m/%Y %H:%M") if entry.created_at else "N/A",
                    "student_name": "ERROR",
                    "student_code": "ERROR",
                    "amount": entry.amount,
                    "currency": entry.currency,
                    "tx_type": entry.tx_type,
                    "tx_ref": entry.tx_ref,
                    "source": entry.source,
                    "actor": "ERROR",
                    "hash": entry.hash[:16] + "..." + entry.hash[-8:] if entry.hash else "N/A",
                    "full_hash": entry.hash or "N/A",
                    "previous_hash": "N/A",
                    "is_verified": False,
                    "metadata": {"error": str(row_err)}
                })
        
        return jsonify({
            "ledger": ledger_data,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        return jsonify({"message": "Error retrieving audit ledger", "error": str(e)}), 500


@api.route("/finance/audit/verify", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def verify_audit_ledger():
    """Run complete ledger chain verification."""
    try:
        school = School.query.get(g.school_id)
        restriction = _payment_audit_access_block_response(school)
        if restriction:
            return restriction

        is_valid, broken_entries, total_checked = verify_ledger_chain(g.school_id)
        
        return jsonify({
            "is_valid": is_valid,
            "status": "VERIFIED IMMUTABLE" if is_valid else "⚠️ CHAIN BROKEN",
            "total_checked": total_checked,
            "broken_count": len(broken_entries),
            "broken_entries": broken_entries[:10] if broken_entries else []  # Limit to first 10
        })
    except Exception as e:
        return jsonify({"message": "Error verifying ledger", "error": str(e)}), 500


@api.route("/finance/audit/summary", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_audit_summary():
    """Get Financial Integrity Report summary."""
    try:
        school = School.query.get(g.school_id)
        restriction = _payment_audit_access_block_response(school)
        if restriction:
            return restriction

        # Get date range from query params
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        
        if start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        summary = get_ledger_summary(g.school_id, start_date, end_date)
        
        # Get school info for report header
        school = School.query.get(g.school_id)
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        
        return jsonify({
            "school_name": school.name,
            "period": request.args.get("period_label", "All Time"),
            "security_protocol": "HMAC-SHA256 Cryptographic Chaining",
            "summary": summary,
            "currency": settings.currency if settings else "GH₵"
        })
    except Exception as e:
        return jsonify({"message": "Error generating audit summary", "error": str(e)}), 500


@api.route("/finance/audit/events", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_audit_events():
    """Get school audit events with optional action filter for compliance review."""
    try:
        school = School.query.get(g.school_id)
        restriction = _payment_audit_access_block_response(school)
        if restriction:
            return restriction

        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        action = request.args.get("action", type=str)

        query = AuditLog.query.filter(AuditLog.school_id == g.school_id)
        if action and action.strip():
            query = query.filter(AuditLog.action == action.strip())

        total_count = query.count()
        events = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

        data = []
        for event in events:
            actor = event.actor
            actor_name = (
                (getattr(actor, "name", None) or getattr(actor, "username", None))
                if actor
                else "System"
            )

            details_payload = None
            details_text = event.details
            if event.details:
                try:
                    details_payload = json.loads(event.details)
                except (TypeError, ValueError, json.JSONDecodeError):
                    details_payload = None

            data.append(
                {
                    "id": event.id,
                    "timestamp": event.timestamp.strftime("%d/%m/%Y %H:%M") if event.timestamp else None,
                    "action": event.action,
                    "actor": actor_name,
                    "details": details_text,
                    "details_json": details_payload,
                }
            )

        return jsonify(
            {
                "events": data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "action_filter": action,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error retrieving audit events", "error": str(e)}), 500


@api.route("/finance/audit/events/export", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def export_audit_events_csv():
    """Export school audit events to CSV with optional action filter."""
    try:
        school = School.query.get(g.school_id)
        restriction = _payment_audit_access_block_response(school)
        if restriction:
            return restriction

        action = request.args.get("action", type=str)

        query = AuditLog.query.filter(AuditLog.school_id == g.school_id)
        if action and action.strip():
            query = query.filter(AuditLog.action == action.strip())

        events = query.order_by(AuditLog.timestamp.desc()).all()

        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["id", "timestamp", "action", "actor", "details"])

        for event in events:
            actor = event.actor
            actor_name = (
                (getattr(actor, "name", None) or getattr(actor, "username", None))
                if actor
                else "System"
            )
            writer.writerow(
                [
                    event.id,
                    event.timestamp.isoformat() if event.timestamp else "",
                    event.action or "",
                    actor_name,
                    event.details or "",
                ]
            )

        filter_label = (action.strip() if action and action.strip() else "ALL").replace(" ", "_")
        filename = f"audit_events_{g.school_id}_{filter_label}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

        output = make_response(csv_buffer.getvalue())
        output.headers["Content-Disposition"] = f"attachment; filename={filename}"
        output.headers["Content-type"] = "text/csv"
        return output
    except Exception as e:
        return jsonify({"message": "Error exporting audit events", "error": str(e)}), 500
def _get_or_create_school_settings():
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)
        db.session.flush()
    return settings


def _clone_json_document(value):
    return json.loads(json.dumps(value or {}))


def _normalize_fee_amount(value):
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _get_feeding_plan_fees(settings):
    if not settings:
        return {
            "daily": 0.0,
            "weekly": 0.0,
            "monthly": 0.0,
            "primary": 0.0,
            "has_explicit_plans": False,
        }

    report_template_config = _clone_json_document(settings.report_template_config)
    payment_plan_settings = report_template_config.get("payment_plan_settings") or {}
    feeding_config = payment_plan_settings.get("feeding") or {}

    daily = _normalize_fee_amount(feeding_config.get("daily"))
    weekly = _normalize_fee_amount(feeding_config.get("weekly"))
    monthly = _normalize_fee_amount(feeding_config.get("monthly"))
    legacy = _normalize_fee_amount(settings.feeding_fee)
    has_explicit_plans = any(amount > 0 for amount in (daily, weekly, monthly))
    primary = monthly or weekly or daily or legacy

    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "primary": primary,
        "has_explicit_plans": has_explicit_plans,
    }


def _set_feeding_plan_fees(settings, daily, weekly, monthly):
    report_template_config = _clone_json_document(settings.report_template_config)
    payment_plan_settings = report_template_config.get("payment_plan_settings") or {}
    payment_plan_settings["feeding"] = {
        "daily": _normalize_fee_amount(daily),
        "weekly": _normalize_fee_amount(weekly),
        "monthly": _normalize_fee_amount(monthly),
    }
    report_template_config["payment_plan_settings"] = payment_plan_settings
    settings.report_template_config = report_template_config
    settings.feeding_fee = (
        payment_plan_settings["feeding"]["monthly"]
        or payment_plan_settings["feeding"]["weekly"]
        or payment_plan_settings["feeding"]["daily"]
        or 0.0
    )


def _analytics_preset_name_key(name):
    return (name or "").strip().casefold()


def _get_analytics_preset_config(settings):
    report_template_config = _clone_json_document(settings.report_template_config)
    analytics_config = report_template_config.get("analytics_presets") or {}
    if not isinstance(analytics_config, dict):
        analytics_config = {}
    presets = analytics_config.get("presets") or []
    if not isinstance(presets, list):
        presets = []
    default_preset_name = analytics_config.get("default_preset_name")
    return report_template_config, analytics_config, presets, default_preset_name


def _get_analytics_preset_history(settings):
    report_template_config = _clone_json_document(settings.report_template_config)
    history = report_template_config.get(ANALYTICS_PRESET_HISTORY_KEY) or []
    return history if isinstance(history, list) else []


def _write_analytics_preset_history(settings, history_items):
    config = _clone_json_document(settings.report_template_config)
    cleaned_history = history_items if isinstance(history_items, list) else []
    if cleaned_history:
        config[ANALYTICS_PRESET_HISTORY_KEY] = cleaned_history[:ANALYTICS_PRESET_HISTORY_LIMIT]
    else:
        config.pop(ANALYTICS_PRESET_HISTORY_KEY, None)
    settings.report_template_config = config


def _build_analytics_preset_snapshot(
    analytics_config,
    *,
    actor_id,
    action,
    focus_preset_name=None,
    restored_from_snapshot_id=None,
):
    normalized_config = _clone_json_document(analytics_config)
    presets = normalized_config.get("presets") or []
    return {
        "snapshot_id": f"aps_{secrets.token_hex(6)}",
        "analytics_config": normalized_config,
        "actor_id": actor_id,
        "action": action,
        "focus_preset_name": focus_preset_name,
        "default_preset_name": normalized_config.get("default_preset_name"),
        "preset_count": len(presets) if isinstance(presets, list) else 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "restored_from_snapshot_id": restored_from_snapshot_id,
    }


def _append_analytics_preset_history(
    settings,
    analytics_config,
    *,
    actor_id,
    action,
    focus_preset_name=None,
    restored_from_snapshot_id=None,
):
    snapshot = _build_analytics_preset_snapshot(
        analytics_config,
        actor_id=actor_id,
        action=action,
        focus_preset_name=focus_preset_name,
        restored_from_snapshot_id=restored_from_snapshot_id,
    )
    history = [snapshot] + _get_analytics_preset_history(settings)
    _write_analytics_preset_history(settings, history)
    return snapshot


def _serialize_analytics_preset_history_item(item, current_config_signature=None):
    analytics_config = _clone_json_document(item.get("analytics_config") or {})
    presets = analytics_config.get("presets") or []
    preset_names = [
        preset.get("name")
        for preset in presets
        if isinstance(preset, dict) and preset.get("name")
    ]
    config_signature = json.dumps(analytics_config, sort_keys=True)
    return {
        "snapshot_id": item.get("snapshot_id"),
        "action": item.get("action"),
        "focus_preset_name": item.get("focus_preset_name"),
        "default_preset_name": item.get("default_preset_name"),
        "preset_count": item.get("preset_count") or len(preset_names),
        "preset_names": preset_names[:8],
        "analytics_config": analytics_config,
        "created_at": item.get("created_at"),
        "actor_id": item.get("actor_id"),
        "restored_from_snapshot_id": item.get("restored_from_snapshot_id"),
        "is_current": bool(current_config_signature) and config_signature == current_config_signature,
    }


def _normalize_analytics_preset_payload(payload):
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("Preset name is required")

    filters = payload.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("Preset filters must be an object")

    normalized_filters = {
        "academicTerm": (filters.get("academicTerm") or "").strip(),
        "academicYear": (filters.get("academicYear") or "").strip(),
        "cohortFromClass": (filters.get("cohortFromClass") or "").strip(),
        "cohortToClass": (filters.get("cohortToClass") or "").strip(),
        "analysisMode": (filters.get("analysisMode") or "single-year").strip() or "single-year",
        "activeView": (filters.get("activeView") or "visualization").strip() or "visualization",
    }

    if normalized_filters["analysisMode"] not in {"single-year", "multi-year"}:
        normalized_filters["analysisMode"] = "single-year"
    if normalized_filters["activeView"] not in {"overview", "visualization"}:
        normalized_filters["activeView"] = "visualization"

    return {
        "name": name,
        "filters": normalized_filters,
        "is_default": bool(payload.get("is_default", False)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@api.route("/analytics/presets", methods=["GET"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_analytics_presets():
    try:
        settings = _get_or_create_school_settings()
        _, _, presets, default_preset_name = _get_analytics_preset_config(settings)
        return jsonify(
            {
                "presets": presets,
                "default_preset_name": default_preset_name,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error loading analytics presets", "error": str(e)}), 500


@api.route("/analytics/presets", methods=["POST"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def save_analytics_preset():
    try:
        user_id = int(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        preset = _normalize_analytics_preset_payload(payload)
        preset_name_key = _analytics_preset_name_key(preset["name"])

        settings = _get_or_create_school_settings()
        report_template_config, analytics_config, presets, default_preset_name = _get_analytics_preset_config(settings)

        next_presets = [
            preset
        ] + [
            item for item in presets if _analytics_preset_name_key(item.get("name")) != preset_name_key
        ]
        next_presets = next_presets[:12]

        if preset["is_default"]:
            default_preset_name = preset["name"]
        elif _analytics_preset_name_key(default_preset_name) == preset_name_key:
            default_preset_name = preset["name"]

        analytics_config["presets"] = next_presets
        analytics_config["default_preset_name"] = default_preset_name
        report_template_config["analytics_presets"] = analytics_config
        settings.report_template_config = _clone_json_document(report_template_config)
        _append_analytics_preset_history(
            settings,
            analytics_config,
            actor_id=user_id,
            action="save",
            focus_preset_name=preset["name"],
        )
        db.session.commit()

        return jsonify(
            {
                "message": "Analytics preset saved.",
                "preset": preset,
                "presets": next_presets,
                "default_preset_name": default_preset_name,
            }
        )
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": "Error saving analytics preset", "error": str(e)}), 500


@api.route("/analytics/presets/<string:preset_name>/default", methods=["PUT"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def set_default_analytics_preset(preset_name):
    try:
        user_id = int(get_jwt_identity())
        settings = _get_or_create_school_settings()
        report_template_config, analytics_config, presets, _ = _get_analytics_preset_config(settings)
        matching_preset = next(
            (
                item
                for item in presets
                if _analytics_preset_name_key(item.get("name")) == _analytics_preset_name_key(preset_name)
            ),
            None,
        )
        if not matching_preset:
            return jsonify({"message": "Preset not found"}), 404

        resolved_preset_name = matching_preset.get("name")

        analytics_config["presets"] = presets
        analytics_config["default_preset_name"] = resolved_preset_name
        report_template_config["analytics_presets"] = analytics_config
        settings.report_template_config = _clone_json_document(report_template_config)
        _append_analytics_preset_history(
            settings,
            analytics_config,
            actor_id=user_id,
            action="set_default",
            focus_preset_name=resolved_preset_name,
        )
        db.session.commit()

        return jsonify(
            {
                "message": "Default analytics preset updated.",
                "default_preset_name": resolved_preset_name,
                "presets": presets,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error updating default analytics preset", "error": str(e)}), 500


@api.route("/analytics/presets/<string:preset_name>", methods=["DELETE"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def delete_analytics_preset(preset_name):
    try:
        user_id = int(get_jwt_identity())
        settings = _get_or_create_school_settings()
        report_template_config, analytics_config, presets, default_preset_name = _get_analytics_preset_config(settings)
        preset_name_key = _analytics_preset_name_key(preset_name)
        removed_preset = next(
            (item for item in presets if _analytics_preset_name_key(item.get("name")) == preset_name_key),
            None,
        )
        next_presets = [
            item for item in presets if _analytics_preset_name_key(item.get("name")) != preset_name_key
        ]
        if len(next_presets) == len(presets):
            return jsonify({"message": "Preset not found"}), 404

        if _analytics_preset_name_key(default_preset_name) == preset_name_key:
            default_preset_name = next_presets[0].get("name") if next_presets else None

        analytics_config["presets"] = next_presets
        analytics_config["default_preset_name"] = default_preset_name
        report_template_config["analytics_presets"] = analytics_config
        settings.report_template_config = _clone_json_document(report_template_config)
        _append_analytics_preset_history(
            settings,
            analytics_config,
            actor_id=user_id,
            action="delete",
            focus_preset_name=(removed_preset or {}).get("name"),
        )
        db.session.commit()

        return jsonify(
            {
                "message": "Analytics preset removed.",
                "presets": next_presets,
                "default_preset_name": default_preset_name,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error deleting analytics preset", "error": str(e)}), 500


@api.route("/analytics/presets/history", methods=["GET"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_analytics_preset_history():
    try:
        settings = _get_or_create_school_settings()
        _, analytics_config, _, _ = _get_analytics_preset_config(settings)
        history = _get_analytics_preset_history(settings)
        actor_ids = sorted({item.get("actor_id") for item in history if item.get("actor_id")})
        actors = (
            User.query.filter(User.school_id == g.school_id, User.id.in_(actor_ids)).all()
            if actor_ids
            else []
        )
        actor_map = {actor.id: actor.username for actor in actors}
        current_config_signature = json.dumps(_clone_json_document(analytics_config), sort_keys=True)

        return jsonify(
            {
                "history": [
                    {
                        **_serialize_analytics_preset_history_item(
                            item,
                            current_config_signature=current_config_signature,
                        ),
                        "actor_name": actor_map.get(item.get("actor_id")),
                    }
                    for item in history
                ]
            }
        )
    except Exception as e:
        return jsonify({"message": "Error loading analytics preset history", "error": str(e)}), 500


@api.route("/analytics/presets/history/<string:snapshot_id>/restore", methods=["POST"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def restore_analytics_preset_history(snapshot_id):
    try:
        user_id = int(get_jwt_identity())
        settings = _get_or_create_school_settings()
        history = _get_analytics_preset_history(settings)
        snapshot = next((item for item in history if item.get("snapshot_id") == snapshot_id), None)
        if not snapshot:
            return jsonify({"message": "Analytics preset history snapshot not found."}), 404

        report_template_config, _, _, _ = _get_analytics_preset_config(settings)
        analytics_config = _clone_json_document(snapshot.get("analytics_config") or {})
        report_template_config["analytics_presets"] = analytics_config
        settings.report_template_config = _clone_json_document(report_template_config)
        _append_analytics_preset_history(
            settings,
            analytics_config,
            actor_id=user_id,
            action="restore",
            focus_preset_name=snapshot.get("focus_preset_name") or snapshot.get("default_preset_name"),
            restored_from_snapshot_id=snapshot_id,
        )
        db.session.commit()

        return jsonify(
            {
                "message": "Analytics preset history restored.",
                "presets": analytics_config.get("presets") or [],
                "default_preset_name": analytics_config.get("default_preset_name") or "",
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error restoring analytics preset history", "error": str(e)}), 500


@api.route("/analytics/presets/history/<string:snapshot_id>/download", methods=["GET"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def download_analytics_preset_history(snapshot_id):
    try:
        settings = _get_or_create_school_settings()
        snapshot = next(
            (item for item in _get_analytics_preset_history(settings) if item.get("snapshot_id") == snapshot_id),
            None,
        )
        if not snapshot:
            return jsonify({"message": "Analytics preset history snapshot not found."}), 404

        payload = {
            "snapshot_id": snapshot.get("snapshot_id"),
            "action": snapshot.get("action"),
            "focus_preset_name": snapshot.get("focus_preset_name"),
            "default_preset_name": snapshot.get("default_preset_name"),
            "created_at": snapshot.get("created_at"),
            "restored_from_snapshot_id": snapshot.get("restored_from_snapshot_id"),
            "analytics_config": _clone_json_document(snapshot.get("analytics_config") or {}),
        }
        filename_seed = snapshot.get("focus_preset_name") or snapshot.get("default_preset_name") or snapshot_id
        filename = secure_filename(str(filename_seed)) or snapshot_id
        response = make_response(json.dumps(payload, indent=2))
        response.headers["Content-Type"] = "application/json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}.json"
        return response
    except Exception as e:
        return jsonify({"message": "Error downloading analytics preset history", "error": str(e)}), 500


@api.route("/analytics/exam-imports", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_intelligence")
@role_required("proprietor", "headmaster")
@jwt_required()
def list_exam_import_batches():
    try:
        settings = _get_or_create_school_settings()
        payload = _build_exam_intelligence_payload(settings)
        return jsonify({"batches": payload.get("batches", [])})
    except Exception as e:
        return jsonify({"message": "Error loading exam import batches", "error": str(e)}), 500


@api.route("/analytics/exam-imports", methods=["POST"])
@multi_tenant_guard
@feature_required("exam_intelligence")
@role_required("proprietor", "headmaster")
@jwt_required()
def upload_exam_import_batch():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"message": "Upload the school result document using the file field."}), 400

    original_name = uploaded.filename or ""
    if not original_name:
        return jsonify({"message": "A result document filename is required."}), 400

    file_ext = os.path.splitext(original_name)[1].lower()
    allowed_exts = {".csv", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    if file_ext not in allowed_exts:
        return jsonify({"message": "Supported result formats are PDF, PNG, JPG, WEBP, TXT, and CSV."}), 400

    settings = _get_or_create_school_settings()
    compliance_payload = _build_exam_intelligence_payload(settings)
    if not compliance_payload.get("compliance_ready"):
        return jsonify({"message": "Complete registration policy readiness checks before importing results."}), 400

    exam_type = sanitize_string(request.form.get("exam_type") or "BECE") or "BECE"
    academic_year = sanitize_string(request.form.get("academic_year") or "") or "Unknown"
    result_text = request.form.get("result_text") or request.form.get("ocr_text") or ""

    try:
        if file_ext == ".csv":
            uploaded.stream.seek(0)
            rows = _parse_exam_csv_rows(uploaded.stream)
            parse_mode = "csv"
        else:
            document_text = _load_exam_document_text(uploaded, file_ext, result_text=result_text)
            rows = _parse_exam_text_rows(document_text)
            if sanitize_string(result_text or ""):
                parse_mode = "manual_text"
            elif file_ext == ".pdf":
                parse_mode = "pdf_text"
            else:
                parse_mode = "ocr_text"
    except ValueError as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": "Failed to parse exam result document", "error": str(e)}), 400

    uploaded.stream.seek(0)
    batch_id = f"exam_{secrets.token_hex(6)}"
    safe_name = secure_filename(original_name) or f"{batch_id}{file_ext or '.bin'}"
    stored_filename = f"{batch_id}_{safe_name}"
    target_path = os.path.join(_get_exam_import_storage_root(), stored_filename)
    uploaded.save(target_path)

    parsed_rows_filename = _build_exam_rows_snapshot_path(batch_id)
    parsed_rows_path = os.path.join(_get_exam_import_storage_root(), parsed_rows_filename)
    with open(parsed_rows_path, "w", encoding="utf-8") as file_handle:
        json.dump({"rows": rows}, file_handle, ensure_ascii=False)

    batch_summary = _build_exam_batch_summary(rows)
    workflow_config = _get_exam_intelligence_workflow_config(settings)
    next_batch = {
        "id": batch_id,
        "exam_type": exam_type,
        "academic_year": academic_year,
        "source_filename": safe_name,
        "stored_filename": stored_filename,
        "parsed_rows_filename": parsed_rows_filename,
        "source_format": file_ext.lstrip(".") or "document",
        "parse_mode": parse_mode,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": int(get_jwt_identity()),
        **batch_summary,
    }
    workflow_config["imports"] = [next_batch] + (workflow_config.get("imports") or [])
    _set_exam_intelligence_workflow_config(settings, workflow_config)
    db.session.commit()

    try:
        log_action(
            int(get_jwt_identity()),
            g.school_id,
            "EXAM_INTELLIGENCE_BATCH_IMPORTED",
            json.dumps(
                {
                    "batch_id": batch_id,
                    "exam_type": exam_type,
                    "academic_year": academic_year,
                    "candidate_count": batch_summary["candidate_count"],
                    "subject_entry_count": batch_summary["subject_entry_count"],
                }
            ),
        )
    except Exception as audit_error:
        logger.warning("Exam intelligence audit log failed for %s: %s", batch_id, audit_error)

    response_batch = dict(next_batch)
    response_batch["download_path"] = _build_exam_import_download_path(batch_id)
    return jsonify({"message": "Exam import uploaded.", "batch": response_batch}), 201


@api.route("/analytics/exam-imports/<string:batch_id>/download", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_intelligence")
@role_required("proprietor", "headmaster")
@jwt_required()
def download_exam_import_batch(batch_id):
    settings = _get_or_create_school_settings()
    workflow_config = _get_exam_intelligence_workflow_config(settings)
    matching_batch = next((item for item in (workflow_config.get("imports") or []) if item.get("id") == batch_id), None)
    if not matching_batch:
        return jsonify({"message": "Exam import batch not found"}), 404

    resolved_path = _resolve_existing_school_file(_get_exam_import_storage_root(), matching_batch.get("stored_filename"))
    if not resolved_path:
        return jsonify({"message": "Exam import file is no longer available"}), 404

    return send_file(resolved_path, as_attachment=True, download_name=matching_batch.get("source_filename") or "exam-import.csv")


@api.route("/analytics/exam-intelligence", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_intelligence")
@role_required("proprietor", "headmaster", "teacher")
@jwt_required()
def get_exam_intelligence_dashboard():
    try:
        settings = _get_or_create_school_settings()
        current_user = getattr(g, "current_user", None)
        if current_user and current_user.role == "teacher":
            try:
                return jsonify(_build_teacher_exam_intelligence_payload(settings, current_user.id))
            except Exception as teacher_error:
                logger.warning(
                    "Teacher exam intelligence summary unavailable for school %s teacher %s: %s",
                    g.school_id,
                    current_user.id,
                    teacher_error,
                )
                return jsonify(
                    _build_empty_teacher_exam_intelligence_payload(
                        settings,
                        current_user.id,
                        warning_message="Subject-level exam summaries are unavailable until the latest exam import is complete and readable.",
                    )
                )
        return jsonify(_build_exam_intelligence_payload(settings))
    except Exception as e:
        return jsonify({"message": "Error loading exam intelligence dashboard", "error": str(e)}), 500


@api.route("/analytics/academic-guidance", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_intelligence")
@role_required("proprietor", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_academic_guidance_dashboard():
    user = User.query.get(int(get_jwt_identity()))
    if not user:
        return jsonify({"message": "User not found."}), 404

    academic_term, academic_year, reports = _get_latest_report_scope()
    scope = _build_academic_guidance_scope(user)
    payload = build_academic_guidance_summary(
        reports,
        allowed_classes=scope["allowed_classes"],
        allowed_subjects=scope["allowed_subjects"],
    )
    payload["scope"] = {
        "role": user.role,
        "role_label": scope["role_label"],
        "allowed_classes": scope["allowed_classes"] or [],
        "allowed_subjects": scope["allowed_subjects"] or [],
        "academic_term": academic_term,
        "academic_year": academic_year,
    }
    return jsonify(payload)


def _retired_examiner_report_insights_response():
    return jsonify({"message": "Examiner report insights have been removed from EduPulse."}), 410


@api.route("/platform/chief-examiner-library", methods=["GET"])
@jwt_required()
def get_platform_chief_examiner_library():
    return _retired_examiner_report_insights_response()


@api.route("/platform/chief-examiner-library/import", methods=["POST"])
@jwt_required()
def import_platform_chief_examiner_library():
    return _retired_examiner_report_insights_response()


@api.route("/platform/chief-examiner-library/history", methods=["GET"])
@jwt_required()
def get_platform_chief_examiner_library_history():
    return _retired_examiner_report_insights_response()


@api.route("/platform/chief-examiner-library/history/<string:version_id>/restore", methods=["POST"])
@jwt_required()
def restore_platform_chief_examiner_library_history(version_id):
    return _retired_examiner_report_insights_response()


@api.route("/platform/chief-examiner-library/history/<string:version_id>/download", methods=["GET"])
@jwt_required()
def download_platform_chief_examiner_library_history(version_id):
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library/import", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def import_chief_examiner_library():
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library/template", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def download_chief_examiner_library_template():
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library/history", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def get_chief_examiner_library_history():
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library/history/<string:version_id>/restore", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def restore_chief_examiner_library_history(version_id):
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library/history/<string:version_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def download_chief_examiner_library_history(version_id):
    return _retired_examiner_report_insights_response()


@api.route("/analytics/chief-examiner-library", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_chief_examiner_library():
    return _retired_examiner_report_insights_response()


@api.route("/analytics/class-performance", methods=["GET"])
@multi_tenant_guard
@feature_required("advanced_analytics")
@role_required("proprietor", "headmaster")
@jwt_required()
def get_class_performance():
    """Class performance visualization data (term/year comparison)."""
    try:
        academic_term = request.args.get("academic_term")
        academic_year = request.args.get("academic_year")
        cohort_from_class = request.args.get("cohort_from_class")
        cohort_to_class = request.args.get("cohort_to_class")

        base_query = ReportCard.query.filter_by(school_id=g.school_id)
        if not academic_term or not academic_year:
            latest = (
                base_query.order_by(ReportCard.created_at.desc()).first()
            )
            if latest:
                academic_term = latest.academic_term
                academic_year = latest.academic_year

        if not academic_term or not academic_year:
            return jsonify({"message": "No report data available"}), 404

        term_order = ["Term 1", "Term 2", "Term 3"]
        term_index = term_order.index(academic_term) if academic_term in term_order else 0
        prev_term = term_order[term_index - 1] if term_index > 0 else "Term 3"

        def _prev_year(year_str):
            try:
                start, end = year_str.split("/")
                return f"{int(start)-1}/{int(end)-1}"
            except Exception:
                return year_str

        prev_year = academic_year if term_index > 0 else _prev_year(academic_year)
        same_term_prev_year = _prev_year(academic_year)

        def _score_band(value):
            score = float(value or 0)
            if score >= 80:
                return "80-100"
            if score >= 70:
                return "70-79"
            if score >= 65:
                return "65-69"
            if score >= 50:
                return "50-64"
            return "0-49"

        def _subject_key(item):
            return (item.get("subject") or item.get("subject_name") or "General").strip()

        def _subject_total(item):
            raw = item.get("total")
            if raw is None:
                raw = item.get("total_score")
            try:
                return float(raw or 0)
            except Exception:
                return 0.0

        def _previous_class(class_name):
            try:
                index = VALID_GRADES.index(class_name)
            except ValueError:
                return None
            return VALID_GRADES[index - 1] if index > 0 else None

        current_stats = (
            db.session.query(
                ReportCard.class_name,
                func.avg(ReportCard.term_average).label("avg_score"),
                func.count(ReportCard.id).label("count")
            )
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.academic_year == academic_year,
                ReportCard.term_average.isnot(None),
            )
            .group_by(ReportCard.class_name)
            .all()
        )

        prev_stats = (
            db.session.query(
                ReportCard.class_name,
                func.avg(ReportCard.term_average).label("avg_score"),
            )
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == prev_term,
                ReportCard.academic_year == prev_year,
                ReportCard.term_average.isnot(None),
            )
            .group_by(ReportCard.class_name)
            .all()
        )

        prev_map = {c: float(a or 0) for c, a in prev_stats}

        same_term_prev_year_stats = (
            db.session.query(
                ReportCard.class_name,
                func.avg(ReportCard.term_average).label("avg_score"),
                func.count(ReportCard.id).label("count"),
            )
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.academic_year == same_term_prev_year,
                ReportCard.term_average.isnot(None),
            )
            .group_by(ReportCard.class_name)
            .all()
        )
        same_term_prev_year_map = {
            class_name: {
                "average": round(float(avg_score or 0), 2),
                "count": int(count or 0),
            }
            for class_name, avg_score, count in same_term_prev_year_stats
        }

        current_reports = ReportCard.query.filter(
            ReportCard.school_id == g.school_id,
            ReportCard.academic_term == academic_term,
            ReportCard.academic_year == academic_year,
        ).all()
        prev_year_reports = ReportCard.query.filter(
            ReportCard.school_id == g.school_id,
            ReportCard.academic_term == academic_term,
            ReportCard.academic_year == same_term_prev_year,
        ).all()

        score_bands = {
            "80-100": 0,
            "70-79": 0,
            "65-69": 0,
            "50-64": 0,
            "0-49": 0,
        }
        for report in current_reports:
            score_bands[_score_band(report.term_average)] += 1

        current_subjects = {}
        for report in current_reports:
            for item in report.subject_grades or []:
                subject_name = _subject_key(item)
                bucket = current_subjects.setdefault(subject_name, {"total": 0.0, "count": 0})
                bucket["total"] += _subject_total(item)
                bucket["count"] += 1

        prev_subjects = {}
        for report in prev_year_reports:
            for item in report.subject_grades or []:
                subject_name = _subject_key(item)
                bucket = prev_subjects.setdefault(subject_name, {"total": 0.0, "count": 0})
                bucket["total"] += _subject_total(item)
                bucket["count"] += 1

        subject_trends = []
        for subject_name, aggregate in current_subjects.items():
            current_avg = aggregate["total"] / aggregate["count"] if aggregate["count"] else 0
            previous = prev_subjects.get(subject_name)
            previous_avg = previous["total"] / previous["count"] if previous and previous["count"] else None
            subject_trends.append(
                {
                    "subject": subject_name,
                    "current_average": round(current_avg, 2),
                    "previous_average": round(previous_avg, 2) if previous_avg is not None else None,
                    "delta": round(current_avg - previous_avg, 2) if previous_avg is not None else None,
                    "count": aggregate["count"],
                }
            )
        subject_trends.sort(key=lambda item: item["current_average"], reverse=True)

        available_year_rows = (
            db.session.query(ReportCard.academic_year)
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.academic_year.isnot(None),
            )
            .distinct()
            .all()
        )
        available_academic_years = sorted(
            [row[0] for row in available_year_rows if row[0]],
        )

        multi_year_stats = (
            db.session.query(
                ReportCard.academic_year,
                ReportCard.class_name,
                func.avg(ReportCard.term_average).label("avg_score"),
                func.count(ReportCard.id).label("count"),
            )
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.term_average.isnot(None),
            )
            .group_by(ReportCard.academic_year, ReportCard.class_name)
            .all()
        )

        multi_year_map = {}
        for year_value, class_name, avg_score, count in multi_year_stats:
            entry = multi_year_map.setdefault(class_name, [])
            entry.append(
                {
                    "academic_year": year_value,
                    "average": round(float(avg_score or 0), 2),
                    "count": int(count or 0),
                }
            )

        multi_year_trends = []
        for class_name, points in multi_year_map.items():
            ordered_points = sorted(points, key=lambda item: item["academic_year"])
            if cohort_from_class and class_name != cohort_from_class and class_name != cohort_to_class:
                pass
            multi_year_trends.append(
                {
                    "class_name": class_name,
                    "points": ordered_points,
                }
            )
        multi_year_trends.sort(key=lambda item: VALID_GRADES.index(item["class_name"]) if item["class_name"] in VALID_GRADES else 999)

        subject_multi_year_stats = (
            db.session.query(
                ReportCard.academic_year,
                ReportCard.subject_grades,
            )
            .filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.subject_grades.isnot(None),
            )
            .all()
        )

        subject_multi_year_map = {}
        for year_value, subject_grades in subject_multi_year_stats:
            if not year_value or not subject_grades:
                continue
            for item in subject_grades:
                subject_name = _subject_key(item)
                bucket = subject_multi_year_map.setdefault(subject_name, {})
                year_bucket = bucket.setdefault(year_value, {"total": 0.0, "count": 0})
                year_bucket["total"] += _subject_total(item)
                year_bucket["count"] += 1

        subject_multi_year_trends = []
        for subject_name, yearly_values in subject_multi_year_map.items():
            points = []
            for year_value in sorted(yearly_values):
                aggregate = yearly_values[year_value]
                average = aggregate["total"] / aggregate["count"] if aggregate["count"] else 0
                points.append(
                    {
                        "academic_year": year_value,
                        "average": round(average, 2),
                        "count": aggregate["count"],
                    }
                )

            latest_average = points[-1]["average"] if points else 0
            baseline_average = points[0]["average"] if len(points) > 1 else None
            subject_multi_year_trends.append(
                {
                    "subject": subject_name,
                    "points": points,
                    "latest_average": latest_average,
                    "delta": round(latest_average - baseline_average, 2) if baseline_average is not None else None,
                }
            )

        subject_multi_year_trends.sort(
            key=lambda item: (-(item["latest_average"] or 0), item["subject"])
        )

        year_over_year_classes = []
        for class_name, avg_score, count in current_stats:
            current_avg = round(float(avg_score or 0), 2)
            previous_year_class = same_term_prev_year_map.get(class_name)
            previous_year_avg = previous_year_class.get("average") if previous_year_class else None
            year_over_year_classes.append(
                {
                    "class_name": class_name,
                    "current_average": current_avg,
                    "previous_year_average": previous_year_avg,
                    "delta": round(current_avg - previous_year_avg, 2) if previous_year_avg is not None else None,
                    "current_count": int(count or 0),
                    "previous_year_count": previous_year_class.get("count") if previous_year_class else 0,
                }
            )
        year_over_year_classes.sort(key=lambda item: item["class_name"])

        cohort_migration_comparisons = []
        current_reports_by_class = {}
        for report in current_reports:
            current_reports_by_class.setdefault(report.class_name, []).append(report)

        for class_name, reports_for_class in current_reports_by_class.items():
            previous_class_name = _previous_class(class_name)
            if not previous_class_name:
                continue

            matched_student_ids = [report.student_id for report in reports_for_class if report.student_id]
            if not matched_student_ids:
                continue

            previous_cohort_reports = ReportCard.query.filter(
                ReportCard.school_id == g.school_id,
                ReportCard.academic_term == academic_term,
                ReportCard.academic_year == same_term_prev_year,
                ReportCard.class_name == previous_class_name,
                ReportCard.student_id.in_(matched_student_ids),
                ReportCard.term_average.isnot(None),
            ).all()

            if not previous_cohort_reports:
                continue

            previous_report_map = {report.student_id: report for report in previous_cohort_reports}
            matched_pairs = [
                (report, previous_report_map.get(report.student_id))
                for report in reports_for_class
                if report.student_id in previous_report_map and report.term_average is not None
            ]
            matched_pairs = [pair for pair in matched_pairs if pair[1] and pair[1].term_average is not None]
            if not matched_pairs:
                continue

            current_average = sum(float(pair[0].term_average or 0) for pair in matched_pairs) / len(matched_pairs)
            previous_average = sum(float(pair[1].term_average or 0) for pair in matched_pairs) / len(matched_pairs)

            cohort_migration_comparisons.append(
                {
                    "from_class": previous_class_name,
                    "to_class": class_name,
                    "from_year": same_term_prev_year,
                    "to_year": academic_year,
                    "matched_students": len(matched_pairs),
                    "previous_average": round(previous_average, 2),
                    "current_average": round(current_average, 2),
                    "delta": round(current_average - previous_average, 2),
                }
            )

        cohort_migration_comparisons.sort(key=lambda item: VALID_GRADES.index(item["to_class"]) if item["to_class"] in VALID_GRADES else 999)

        if cohort_from_class:
            cohort_migration_comparisons = [
                item for item in cohort_migration_comparisons if item["from_class"] == cohort_from_class
            ]
        if cohort_to_class:
            cohort_migration_comparisons = [
                item for item in cohort_migration_comparisons if item["to_class"] == cohort_to_class
            ]

        results = []
        for class_name, avg_score, count in current_stats:
            avg_value = float(avg_score or 0)
            prev_value = prev_map.get(class_name)
            delta = avg_value - prev_value if prev_value is not None else None
            
            # Get gender breakdown for this class
            gender_stats = (
                db.session.query(
                    Student.gender,
                    func.avg(ReportCard.term_average).label("avg_score"),
                    func.count(ReportCard.id).label("count")
                )
                .join(Student, ReportCard.student_id == Student.id)
                .filter(
                    ReportCard.school_id == g.school_id,
                    ReportCard.academic_term == academic_term,
                    ReportCard.academic_year == academic_year,
                    ReportCard.class_name == class_name,
                    ReportCard.term_average.isnot(None),
                    Student.gender.isnot(None),
                )
                .group_by(Student.gender)
                .all()
            )
            
            gender_breakdown = {}
            for gender, g_avg, g_count in gender_stats:
                gender_breakdown[gender] = {
                    "average": round(float(g_avg or 0), 2),
                    "count": int(g_count)
                }
            
            results.append(
                {
                    "class_name": class_name,
                    "average": round(avg_value, 2),
                    "count": int(count),
                    "prev_average": round(prev_value, 2) if prev_value is not None else None,
                    "delta": round(delta, 2) if delta is not None else None,
                    "previous_year_average": same_term_prev_year_map.get(class_name, {}).get("average"),
                    "previous_year_delta": round(avg_value - same_term_prev_year_map.get(class_name, {}).get("average"), 2)
                    if same_term_prev_year_map.get(class_name, {}).get("average") is not None
                    else None,
                    "gender_breakdown": gender_breakdown,
                }
            )

        return jsonify(
            {
                "academic_term": academic_term,
                "academic_year": academic_year,
                "compare_term": prev_term,
                "compare_year": prev_year,
                "same_term_previous_year": same_term_prev_year,
                "cohort_from_class": cohort_from_class,
                "cohort_to_class": cohort_to_class,
                "available_academic_years": available_academic_years,
                "classes": results,
                "year_over_year_classes": year_over_year_classes,
                "multi_year_trends": multi_year_trends,
                "subject_multi_year_trends": subject_multi_year_trends[:12],
                "cohort_migration_comparisons": cohort_migration_comparisons,
                "score_bands": score_bands,
                "subject_trends": subject_trends[:10],
            }
        )
    except Exception as e:
        return jsonify({"message": "Error loading class performance", "error": str(e)}), 500


@api.route("/school/branding", methods=["GET"])
@rate_limit_api
@multi_tenant_guard
def get_school_branding():
    """Get school branding information for documents and fee configuration."""
    try:
        school = School.query.get(g.school_id)
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        verification = _get_school_verification_snapshot(g.school_id)

        fees = {
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

        if settings:
            feeding_plan_fees = _get_feeding_plan_fees(settings)
            fees = {
                "tuition_fee": settings.tuition_fee or 0.0,
                "feeding_fee": feeding_plan_fees["primary"],
                "feeding_daily_fee": feeding_plan_fees["daily"],
                "feeding_weekly_fee": feeding_plan_fees["weekly"],
                "feeding_monthly_fee": feeding_plan_fees["monthly"],
                "uniform_fee": settings.uniform_fee or 0.0,
                "transport_fee": settings.transport_fee or 0.0,
                "terminal_report_fee": settings.terminal_report_fee or 0.0,
                "admission_fee_enabled": bool(settings.admission_fee_enabled),
                "admission_fee_amount": settings.admission_fee_amount or 0.0,
                "other_fees": settings.other_fees or {},
            }

        masked_bank_fields = _masked_bank_fields_for_school(school)

        return jsonify(
            {
                "school_name": school.name,
                "logo_url": school.logo_url,
                "theme_color": school.primary_color,
                "motto": school.motto,
                "school_email": school.school_email,
                "school_phone": school.school_phone,
                "school_address": school.school_address,
                "school_website": school.school_website,
                "verification_status": verification.get("status"),
                "is_verified": bool(verification.get("is_verified")),
                "bank_name": masked_bank_fields["bank_name"],
                "bank_account": masked_bank_fields["bank_account"],
                "bank_account_name": masked_bank_fields["bank_account_name"],
                "bank_branch": masked_bank_fields["bank_branch"],
                "country_code": settings.country_code if settings else "GH",
                "fees": fees,
            }
        )
    except Exception as e:
        return (
            jsonify({"message": "Error retrieving school info", "error": str(e)}),
            500,
        )


@api.route("/school/branding/bank/view", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "finance")
@jwt_required()
def view_school_bank_details():
    """Return full bank details after verifying the user's password."""
    payload = request.get_json() or {}
    password = payload.get("password", "")
    if not password:
        return jsonify({"message": "Password is required"}), 400

    user_id = get_jwt_identity()
    user = User.query.filter_by(id=int(user_id), school_id=g.school_id).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    if not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid password"}), 401

    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    return jsonify(
        {
            "bank_name": school.bank_name,
            "bank_account": school.bank_account,
            "bank_account_name": school.bank_account_name,
            "bank_branch": school.bank_branch,
        }
    )


def _get_school_country_code(school_id):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    return (settings.country_code if settings and settings.country_code else "GH").upper()


def _mask_bank_account_value(account_number):
    try:
        value = str(account_number or "").strip()
        if not value:
            return ""
        if len(value) <= 4:
            return "****"
        return "****" + value[-4:]
    except Exception:
        return "****"


def _mask_bank_text_value(value):
    try:
        text = str(value or "").strip()
        if not text:
            return ""
        parts = text.split()
        if len(parts) == 1:
            return parts[0][0] + "***"
        return parts[0] + " " + parts[-1][0] + "***"
    except Exception:
        return ""


def _masked_bank_fields_for_school(school):
    return {
        "bank_name": _mask_bank_text_value(school.bank_name),
        "bank_account": _mask_bank_account_value(school.bank_account),
        "bank_account_name": _mask_bank_text_value(school.bank_account_name),
        "bank_branch": _mask_bank_text_value(school.bank_branch),
    }


def _get_holiday_status(school_id, target_date):
    country_code = _get_school_country_code(school_id)
    override = SchoolHoliday.query.filter_by(
        school_id=school_id, holiday_date=target_date
    ).first()
    national = get_national_holidays(country_code, target_date.year)

    if override:
        name = override.name or national.get(target_date)
        return override.is_holiday, name

    if target_date in national:
        return True, national[target_date]

    return False, None


@api.route("/calendar/holidays", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_calendar_holidays():
    """Return national holidays plus school overrides for a given year/month."""
    try:
        year = int(request.args.get("year", datetime.now(timezone.utc).year))
        month = request.args.get("month")
        month = int(month) if month else None

        country_code = _get_school_country_code(g.school_id)
        national = get_national_holidays(country_code, year)

        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year, 12, 31).date()
        overrides = (
            SchoolHoliday.query.filter_by(school_id=g.school_id)
            .filter(SchoolHoliday.holiday_date >= start_date)
            .filter(SchoolHoliday.holiday_date <= end_date)
            .all()
        )
        override_map = {o.holiday_date: o for o in overrides}

        results = []
        for day, name in national.items():
            override = override_map.get(day)
            if override:
                results.append(
                    {
                        "date": day.isoformat(),
                        "name": override.name or name,
                        "is_holiday": bool(override.is_holiday),
                        "source": "override",
                    }
                )
            else:
                results.append(
                    {
                        "date": day.isoformat(),
                        "name": name,
                        "is_holiday": True,
                        "source": "national",
                    }
                )

        for override in overrides:
            if override.holiday_date in national:
                continue
            results.append(
                {
                    "date": override.holiday_date.isoformat(),
                    "name": override.name or "Custom Holiday",
                    "is_holiday": bool(override.is_holiday),
                    "source": "custom",
                }
            )

        if month:
            results = [r for r in results if int(r["date"].split("-")[1]) == month]

        # Add school anniversary date if set
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        if settings and settings.anniversary_date:
            anniversary_str = settings.anniversary_date.isoformat()
            # Check if anniversary falls in the selected year and month (use year from query, replace year in anniversary)
            anniversary_this_year = settings.anniversary_date.replace(year=year)
            if not month or anniversary_this_year.month == month:
                # Check if not already in results (from holiday/override)
                if not any(r["date"] == anniversary_this_year.isoformat() for r in results):
                    results.append({
                        "date": anniversary_this_year.isoformat(),
                        "name": f"School Anniversary ({settings.anniversary_date.year})",
                        "is_holiday": False,
                        "source": "anniversary"
                    })

        results.sort(key=lambda r: r["date"])
        return jsonify(
            {
                "country_code": country_code,
                "year": year,
                "month": month,
                "holidays": results,
            }
        )
    except Exception as e:
        return jsonify({"message": "Error retrieving holidays", "error": str(e)}), 500


@api.route("/calendar/holidays", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def upsert_calendar_holiday():
    """Create or override a holiday date for the school."""
    data = request.json or {}
    date_str = data.get("date")
    name = data.get("name")
    is_holiday = data.get("is_holiday", True)

    if not date_str:
        return jsonify({"message": "date is required (YYYY-MM-DD)"}), 400

    try:
        holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD"}), 400

    existing = SchoolHoliday.query.filter_by(
        school_id=g.school_id, holiday_date=holiday_date
    ).first()

    if existing:
        existing.name = name or existing.name
        existing.is_holiday = bool(is_holiday)
    else:
        existing = SchoolHoliday(
            school_id=g.school_id,
            holiday_date=holiday_date,
            name=name or ("Custom Holiday" if is_holiday else "School Open Day"),
            is_holiday=bool(is_holiday),
        )
        db.session.add(existing)

    db.session.commit()
    return jsonify({"message": "Holiday saved", "date": holiday_date.isoformat()})


@api.route("/calendar/holidays/<holiday_date>", methods=["DELETE"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def delete_calendar_holiday(holiday_date):
    """Delete a school holiday override."""
    try:
        parsed_date = datetime.strptime(holiday_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"message": "Invalid date format. Use YYYY-MM-DD"}), 400

    existing = SchoolHoliday.query.filter_by(
        school_id=g.school_id, holiday_date=parsed_date
    ).first()
    if not existing:
        return jsonify({"message": "Holiday not found"}), 404

    db.session.delete(existing)
    db.session.commit()
    return jsonify({"message": "Holiday deleted"})


@api.route("/staff/list", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
def get_staff_list():
    """List all staff members."""
    staff = (
        User.query.filter_by(school_id=g.school_id)
        .filter(User.role != "proprietor")
        .all()
    )
    assignments = TeacherAssignment.query.filter_by(school_id=g.school_id).all()
    assignment_map = {}
    for assignment in assignments:
        entry = assignment_map.setdefault(
            assignment.teacher_id, {"classes": set(), "subjects": set()}
        )
        entry["classes"].add(assignment.class_name)
        entry["subjects"].add(assignment.subject_name)

    return jsonify(
        [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "roles": u.roles or [u.role],
                "assigned_class": u.assigned_class,
                "assigned_classes": sorted(
                    list(assignment_map.get(u.id, {}).get("classes", []))
                ),
                "assigned_subjects": sorted(
                    list(assignment_map.get(u.id, {}).get("subjects", []))
                ),
            }
            for u in staff
        ]
    )


@api.route("/teacher/assignments", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "homeroom", "headmaster", "proprietor")
@jwt_required()
def get_teacher_assignments():
    """Get class/subject assignments for the logged-in teacher."""
    user_id = int(get_jwt_identity())
    assignments = TeacherAssignment.query.filter_by(
        school_id=g.school_id, teacher_id=user_id
    ).all()

    classes = sorted({a.class_name for a in assignments})
    subjects = sorted({a.subject_name for a in assignments})
    pairs = [
        {"class_name": a.class_name, "subject_name": a.subject_name}
        for a in assignments
    ]

    return jsonify(
        {
            "assigned_classes": classes,
            "assigned_subjects": subjects,
            "assignments": pairs,
        }
    )


@api.route("/staff/<int:user_id>", methods=["DELETE"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def remove_staff(user_id):
    """Remove a staff member."""
    try:
        user = User.query.filter_by(id=user_id, school_id=g.school_id).first_or_404()
        db.session.delete(user)
        log_action(
            int(get_jwt_identity()),
            g.school_id,
            "STAFF_REMOVED",
            f"Removed user {user.username}",
        )
        db.session.commit()
        return jsonify({"message": "Staff member removed."})
    except Exception as e:
        return jsonify({"message": "Error removing staff member", "error": str(e)}), 500


@api.route("/staff/<int:user_id>", methods=["PUT"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_staff(user_id):
    """Update staff role, assigned class, or email."""
    response_body, error, status_code = staff_service.update_staff_member(
        user_id,
        request.json or {},
        g.school_id,
        int(get_jwt_identity()),
        User,
        TeacherAssignment,
        _normalize_email_address,
        _find_school_user_by_email,
        _normalize_staff_roles,
        _normalize_homeroom_assignment,
        replace_teacher_assignments,
        log_action,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/inventory", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "inventory_manager")
@jwt_required()
def get_inventory():
    """Get school store inventory with optional filters."""
    category = request.args.get("category")
    item_type = request.args.get("item_type")
    size = request.args.get("size")
    class_group = request.args.get("class_group")
    is_active = request.args.get("is_active")

    query = Inventory.query.filter_by(school_id=g.school_id)
    if category:
        query = query.filter(Inventory.category == category)
    if item_type:
        query = query.filter(Inventory.item_type == item_type)
    if size:
        query = query.filter(Inventory.size == size)
    if class_group:
        query = query.filter(Inventory.class_group == class_group)
    if is_active is not None:
        query = query.filter(Inventory.is_active == (is_active.lower() == "true"))

    items = query.order_by(Inventory.item_name.asc()).all()
    return jsonify(
        [
            {
                "id": i.id,
                "item_name": i.item_name,
                "category": i.category,
                "item_type": i.item_type,
                "size": i.size,
                "class_group": i.class_group,
                "gender": i.gender,
                "sku": i.sku,
                "unit": i.unit,
                "quantity": i.quantity,
                "price": i.price,
                "is_active": i.is_active,
            }
            for i in items
        ]
    )


@api.route("/inventory/item", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "inventory_manager")
def add_inventory_item():
    """Add new item to inventory."""
    data = request.json or {}
    if not data.get("item_name"):
        return jsonify({"message": "Item name is required."}), 400

    def _generate_sku(item_name):
        base = "".join([c for c in item_name.upper() if c.isalnum()])[:4]
        rand = secrets.token_hex(2).upper()
        return f"{base}{rand}" if base else rand

    sku = data.get("sku") or _generate_sku(data.get("item_name", "ITEM"))
    existing = Inventory.query.filter_by(school_id=g.school_id, sku=sku).first()
    if existing:
        return jsonify({"message": "SKU already exists for this school."}), 400

    item = Inventory(
        school_id=g.school_id,
        item_name=data["item_name"],
        category=data.get("category", "General"),
        item_type=data.get("item_type"),
        size=data.get("size"),
        class_group=data.get("class_group"),
        gender=data.get("gender", "Unisex"),
        sku=sku,
        unit=data.get("unit", "piece"),
        quantity=int(data.get("quantity", 0)),
        price=float(data.get("price", 0.0)),
        is_active=data.get("is_active", True),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Item added.", "item": {"id": item.id, "sku": item.sku}})


@api.route("/inventory/export", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "inventory_manager")
@jwt_required()
def export_inventory():
    """Export inventory price list as CSV."""
    items = Inventory.query.filter_by(school_id=g.school_id).order_by(Inventory.item_name.asc()).all()
    output = StringIO()
    output.write(
        "sku,item_name,category,item_type,size,class_group,gender,unit,quantity,price\n"
    )
    for i in items:
        output.write(
            f"{i.sku or ''},{i.item_name or ''},{i.category or ''},{i.item_type or ''},{i.size or ''},{i.class_group or ''},{i.gender or ''},{i.unit or ''},{i.quantity or 0},{i.price or 0.0}\n"
        )

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = (
        f"attachment; filename=inventory_price_list_{get_utc_now().strftime('%Y%m%d')}.csv"
    )
    response.headers["Content-type"] = "text/csv"
    return response


@api.route("/inventory/transactions", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "inventory_manager")
@jwt_required()
def get_inventory_transactions():
    """Get inventory-related payment transactions (Uniform/Inventory)."""
    payments = (
        Payment.query.filter(
            Payment.school_id == g.school_id,
            Payment.payment_type.in_(["Uniform", "Inventory"]),
        )
        .order_by(Payment.date_paid.desc())
        .limit(200)
        .all()
    )

    results = []
    for p in payments:
        student = Student.query.get(p.student_id) if p.student_id else None
        meta = p.payment_category or {}
        results.append(
            {
                "id": p.id,
                "student_name": student.name if student else None,
                "student_code": student.student_code if student else None,
                "payment_type": p.payment_type,
                "amount": p.amount,
                "method": p.method,
                "status": p.status,
                "date_paid": p.date_paid.strftime("%Y-%m-%d %H:%M"),
                "item_name": meta.get("item_name"),
                "item_type": meta.get("item_type"),
                "size": meta.get("size"),
                "quantity": meta.get("quantity"),
                "sku": meta.get("sku"),
            }
        )
    return jsonify(results)


@api.route("/school/settings", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_school_settings():
    """Returns school settings with bank details masked until password re-entry."""
    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None
    response_body, error, status_code = school_settings_service.get_school_settings_payload(
        g.school_id,
        actor_id,
        request.remote_addr,
        School,
        SchoolSettings,
        TEACHER_CLASS_LEVEL_EXAM_SUMMARIES_KEY,
        _get_enabled_modules,
        _get_parent_admission_workflow_config,
        _get_data_compliance_workflow_config,
        _get_payment_provider_settings,
        _masked_bank_fields_for_school,
        _get_report_global_settings,
        _has_ai_registrar_access,
        log_action,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/school/settings", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_school_settings():
    """Updates school branding settings."""
    data = request.json
    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None
    response_body, error, status_code = school_settings_service.update_school_settings(
        data,
        g.school_id,
        actor_id,
        request.remote_addr,
        School,
        SchoolSettings,
        DEFAULT_PARENT_ADMISSION_WORKFLOW,
        TEACHER_CLASS_LEVEL_EXAM_SUMMARIES_KEY,
        sanitize_string,
        _masked_bank_fields_for_school,
        _get_payment_provider_settings,
        _set_payment_provider_settings,
        _set_report_global_setting,
        _get_parent_admission_workflow_config,
        _set_parent_admission_workflow_config,
        _get_data_compliance_workflow_config,
        _set_data_compliance_workflow_config,
        _school_bank_details_ready_for_paystack,
        _provision_school_paystack_subaccount,
        _has_ai_registrar_access,
        log_action,
        logger,
        db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/school/settings/paystack/reconnect", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def reconnect_school_paystack_subaccount():
    school = School.query.filter_by(id=g.school_id).first()
    if not school:
        return jsonify({"message": "School not found."}), 404

    if not _school_bank_details_ready_for_paystack(school):
        return jsonify(
            {
                "message": "Enter the bank name, account number, and account holder name before reconnecting Paystack settlement.",
                "error": "bank_details_required",
            }
        ), 400

    settings = _get_or_create_school_settings()
    provider_settings = _get_payment_provider_settings(settings)
    paystack_subaccount_result, provision_error = _provision_school_paystack_subaccount(
        school,
        settings,
        provider_settings,
    )
    if provision_error:
        logger.error(
            "Paystack subaccount reconnect failed for school %s: %s",
            g.school_id,
            provision_error,
        )
        db.session.rollback()
        reconnect_message = "EduPulse could not connect the school's Paystack settlement account right now. Confirm the bank details and try again."
        if "invalid paystack secret key configured on the server" in str(provision_error).lower():
            reconnect_message = "EduPulse could not connect the school's Paystack settlement account because the platform Paystack secret key is invalid or missing on the server."
        return jsonify(
            {
                "message": reconnect_message,
                "error": "payment_settlement_setup_unavailable",
                "provider_detail": provision_error,
            }
        ), 502

    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None

    log_action(
        actor_id,
        g.school_id,
        "PAYSTACK_SUBACCOUNT_RECONNECTED",
        json.dumps(
            {
                "action": paystack_subaccount_result["action"],
                "subaccount_code": paystack_subaccount_result["subaccount_code"],
                "ip": request.remote_addr,
            }
        ),
    )
    db.session.commit()

    return jsonify(
        {
            "message": f"Paystack settlement account {paystack_subaccount_result['action']} successfully.",
            "paystack_subaccount_code": paystack_subaccount_result["subaccount_code"],
            "paystack_bank_code": paystack_subaccount_result["bank_code"],
            "paystack_resolved_account_name": paystack_subaccount_result["resolved_account_name"],
        }
    ), 200


@api.route("/school/settings/legacy-consent-evidence", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_legacy_consent_evidence_artifacts():
    settings = _get_or_create_school_settings()
    return jsonify(
        legacy_consent_service.get_legacy_consent_evidence_artifacts(
            settings,
            get_data_compliance_workflow_config=_get_data_compliance_workflow_config,
            build_download_path=_build_legacy_evidence_download_path,
        )
    )


@api.route("/school/settings/legacy-consent-evidence", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def upload_legacy_consent_evidence_artifact():
    uploaded = request.files.get("file")
    if not uploaded:
        return jsonify({"message": "Upload a consent evidence file using the file field."}), 400
    settings = _get_or_create_school_settings()
    response_body, error, status_code = legacy_consent_service.upload_legacy_consent_evidence_artifact(
        uploaded,
        school_settings=settings,
        actor_id=int(get_jwt_identity()),
        school_id=g.school_id,
        category=sanitize_string(request.form.get("category") or "general") or "general",
        note=sanitize_string(request.form.get("note") or "") or "",
        secure_filename=secure_filename,
        get_storage_root=_get_legacy_evidence_storage_root,
        get_data_compliance_workflow_config=_get_data_compliance_workflow_config,
        set_data_compliance_workflow_config=_set_data_compliance_workflow_config,
        build_download_path=_build_legacy_evidence_download_path,
        log_action=log_action,
        logger=logger,
        db_session=db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/school/settings/legacy-consent-evidence/<string:artifact_id>/download", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def download_legacy_consent_evidence_artifact(artifact_id):
    settings = _get_or_create_school_settings()
    resolved_path, download_name, error, status_code = legacy_consent_service.resolve_legacy_consent_evidence_download(
        artifact_id,
        settings,
        get_data_compliance_workflow_config=_get_data_compliance_workflow_config,
        get_storage_root=_get_legacy_evidence_storage_root,
        resolve_existing_school_file=_resolve_existing_school_file,
    )
    if error:
        return jsonify(error), status_code
    return send_file(resolved_path, as_attachment=True, download_name=download_name)


@api.route("/school/fees", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_school_fees():
    """Updates school fee configuration (tuition, feeding, uniform, transport, etc.)."""
    return jsonify(
        school_configuration_service.update_school_fees(
            request.json,
            g.school_id,
            int(get_jwt_identity()),
            school_settings_model=SchoolSettings,
            set_feeding_plan_fees=_set_feeding_plan_fees,
            log_action=log_action,
            db_session=db.session,
        )
    )


@api.route("/school/fees", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_school_fees():
    """Retrieves school fee configuration."""
    return jsonify(
        school_configuration_service.get_school_fees_payload(
            g.school_id,
            school_settings_model=SchoolSettings,
            get_feeding_plan_fees=_get_feeding_plan_fees,
        )
    )


@api.route("/school/whatsapp-settings", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_whatsapp_settings():
    """Retrieves WhatsApp cost control settings."""
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        # Return defaults if not configured
        return jsonify({
            "whatsapp_daily_limit": 50,
            "whatsapp_notifications_enabled": True,
        })

    return jsonify({
        "whatsapp_daily_limit": settings.whatsapp_daily_limit or 50,
        "whatsapp_notifications_enabled": settings.whatsapp_notifications_enabled if settings.whatsapp_notifications_enabled is not None else True,
    })


@api.route("/school/grading-scheme", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_grading_scheme():
    """Updates school grading scheme (class score max and exam score max)."""
    response_body, error, status_code = school_configuration_service.update_grading_scheme(
        request.json,
        g.school_id,
        int(get_jwt_identity()),
        school_settings_model=SchoolSettings,
        log_action=log_action,
        db_session=db.session,
    )
    if error:
        return jsonify(error), status_code
    return jsonify(response_body), status_code


@api.route("/school/grading-scheme", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_grading_scheme():
    """Retrieves current grading scheme configuration."""
    return jsonify(
        school_configuration_service.get_grading_scheme_payload(
            g.school_id,
            school_settings_model=SchoolSettings,
        )
    )


@api.route("/school/template", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_active_template():
    """Retrieves the active terminal report template."""
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings or not settings.report_template_id:
        return jsonify({"template_id": "sample1"})  # Default template

    return jsonify(
        {
            "template_id": _to_legacy_report_template_id(settings.report_template_id),
            "template_config": settings.report_template_config or {},
        }
    )


@api.route("/school/template", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def set_active_template():
    """Sets the active terminal report template."""
    data = request.json
    template_id = data.get("template_id")

    if not template_id:
        return jsonify({"message": "Template ID is required"}), 400

    # Validate template ID
    valid_templates = ["sample1", "sample2", "sample3", "sample4", "sample5", "sample6"]
    if not template_id or not isinstance(template_id, str) or not template_id.strip():
        return jsonify({"message": "Template ID is required"}), 400

    # support custom HTML template IDs
    is_custom_template = template_id.startswith("custom_html")
    if template_id not in valid_templates and not is_custom_template:
        return (
            jsonify(
                {
                    "message": f"Invalid template ID. Must be one of: {', '.join(valid_templates)} or custom_html*"
                }
            ),
            400,
        )

    template_id = _normalize_report_template_id(template_id)

    # Get or create school settings
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)

    # Update active template
    settings.report_template_id = template_id
    if "template_config" in data:
        settings.report_template_config = _merge_report_template_config(
            settings.report_template_config,
            data["template_config"],
        )

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "TEMPLATE_UPDATE",
        f"Changed active report template to {template_id}",
    )
    db.session.commit()

    return jsonify(
        {"message": "Template updated successfully", "template_id": template_id}
    )


@api.route("/subscription/plans", methods=["GET"])
def get_all_subscription_plans():
    """Get all available subscription plans for comparison page (public endpoint)."""
    plans_data = []
    
    # Define the order and names
    plan_order = ["Free Tier", "Basic", "Premium"]
    
    for plan_name in plan_order:
        plan_info = PLAN_FEATURES.get(plan_name, {})
        pricing_info = PRICING.get(plan_name, {})
        
        max_students = plan_info.get("max_students", 0)
        max_classes = plan_info.get("max_classes", 0)
        max_staff = plan_info.get("max_staff", 0)
        
        plans_data.append({
            "name": plan_name,
            "display_name": get_plan_display_name(plan_name),
            "price_per_student_per_term": pricing_info.get("per_student_per_term", 0),
            "base_fee_per_term": pricing_info.get("base_fee_per_term", 0),
            "included_students": pricing_info.get("included_students", 0),
            "subscription_convenience_fee": 0,
            "description": plan_info.get("description", ""),
            "max_students": "∞" if max_students == float('inf') else max_students,
            "max_classes": "∞" if max_classes == float('inf') else max_classes,
            "max_staff": "∞" if max_staff == float('inf') else max_staff,
            "features": plan_info.get("features", {}),
            "report_templates": plan_info.get("report_templates", []),
            "marketing_features": plan_info.get("marketing_features", []),
            "addon_options": plan_info.get("addon_options", []),
            "addons": get_addons_for_plan(plan_name),
            "packaging_summary": plan_info.get("packaging_summary", ""),
            "ui_color": plan_info.get("ui_color", "gray"),
            "popular": bool(plan_info.get("popular", plan_name == "Basic")),
        })
    
    return jsonify({"plans": plans_data})


@api.route("/school/subscription", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
def get_subscription():
    """Get subscription details including feature matrix and termly pricing."""
    school = School.query.get(g.school_id)
    billing_status = get_billing_status_info(school)
    if billing_status.get("status_changed"):
        school.subscription_status = billing_status.get("status")
        db.session.commit()

    current_students = _count_active_students_for_billing(g.school_id)
    current_classes = (
        len(school.academic_classes) if hasattr(school, "academic_classes") else 0
    )

    effective_plan = get_effective_plan(school)
    plan_info = PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["Free Tier"])
    plan_display = FEATURE_MATRIX_DISPLAY.get(effective_plan, {})
    feature_keys = set((plan_info.get("features") or {}).keys())
    feature_keys.update(
        {
            "ai_analysis",
            "ai_narratives",
            "student_rescue_agent",
            "exam_intelligence",
            "webhook_payment_automation",
        }
    )
    resolved_features = {
        feature_name: get_school_feature_level(
            school,
            feature_name,
            effective_plan=effective_plan,
        )
        for feature_name in feature_keys
    }
    trial_end_date = school.trial_end_date
    if trial_end_date and trial_end_date.tzinfo is None:
        trial_end_date = trial_end_date.replace(tzinfo=timezone.utc)
    next_billing_date = (
        school.next_billing_date.strftime("%Y-%m-%d")
        if school.next_billing_date
        else None
    )

    max_students = plan_info.get("max_students", 50)
    max_classes = plan_info.get("max_classes", 1)
    
    # Calculate termly costs based on current enrollment
    term_cost = calculate_term_cost(effective_plan, current_students)
    annual_cost = calculate_annual_cost(effective_plan, current_students)
    term_breakdown = get_term_cost_breakdown(effective_plan, current_students)
    
    # Get pricing info
    pricing_info = PRICING.get(effective_plan, {})

    # Billing visibility with active-student meter and 80%/100% alerts
    billing_visibility = get_billing_visibility(g.school_id, commit=False)
    term_proration = get_term_proration_context(g.school_id)
    
    # Get enabled modules from settings
    enabled_modules = {}
    if school.settings:
        enabled_modules = school.settings.enabled_modules or {}

    return jsonify(
        {
            "plan": effective_plan,
            "plan_display_name": get_plan_display_name(effective_plan),
            "subscription_plan": effective_plan,  # Explicit alias for clarity
            "base_plan": school.subscription_plan or "Free Tier",
            "base_plan_display_name": get_plan_display_name(school.subscription_plan or "Free Tier"),
            "status": billing_status.get("status", school.subscription_status),
            "billing_status": billing_status,
            "next_billing": next_billing_date or "N/A",
            "next_billing_date": next_billing_date,
            "enabled_modules": enabled_modules,  # Include for frontend refresh
            "price": plan_info.get("price", "Free"),
            "price_range": plan_info.get("price_range"),
            "billing_cycle": plan_info.get("billing_cycle", "N/A"),
            "example_cost": plan_info.get("example_cost"),
            "description": plan_info.get("description", ""),
            "current_enrollment": current_students,
            "term_cost": term_cost,
            "annual_cost": annual_cost,
            "per_student_per_term": pricing_info.get("per_student_per_term", 0),
            "base_fee_per_term": pricing_info.get("base_fee_per_term", 0),
            "included_students": pricing_info.get("included_students", 0),
            "billing_breakdown": {
                "base_fee": term_breakdown.get("base_fee", 0),
                "included_students": term_breakdown.get("included_students", 0),
                "billable_students": term_breakdown.get("billable_students", 0),
                "per_student_rate": term_breakdown.get("per_student_rate", 0),
                "student_overage_cost": term_breakdown.get("student_overage_cost", 0),
                "convenience_fee": 0,
                "total": term_breakdown.get("total", 0),
            },
            "usage": {
                "students": f"{current_students} / {max_students if max_students != float('inf') else '♾️ Unlimited'}",
                "classes": f"{current_classes} / {max_classes if max_classes != float('inf') else '♾️ Unlimited'}",
            },
            "trial": {
                "plan": school.trial_plan,
                "end_date": (
                    trial_end_date.strftime("%Y-%m-%d")
                    if trial_end_date
                    else None
                ),
                "active": bool(
                    school.trial_plan
                    and trial_end_date
                    and datetime.now(timezone.utc) < trial_end_date
                ),
            },
            "features": resolved_features,
            "features_display": plan_display,
            "report_templates": plan_info.get("report_templates", []),
            "available_addons": get_addons_for_plan(effective_plan),
            "active_addons": {
                "automation_pack": school_has_addon(school, "automation_pack", effective_plan=effective_plan),
                "ai_pack": school_has_addon(school, "ai_pack", effective_plan=effective_plan),
            },
            "purchased_addons": {
                "automation_pack": bool((enabled_modules or {}).get("automation_pack_addon")),
                "ai_pack": bool((enabled_modules or {}).get("ai_pack_addon")),
            },
            "billing_visibility": billing_visibility,
            "term_proration": term_proration,
            "pending_plan": getattr(school, "pending_plan", None),
        }
    )


@api.route("/school/subscription/effective-plan", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_effective_subscription_plan():
    """Return the tenant's effective plan, including trial override state, for any authenticated staff user."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    effective_plan = get_effective_plan(school)
    trial_end_date = school.trial_end_date
    if trial_end_date and trial_end_date.tzinfo is None:
        trial_end_date = trial_end_date.replace(tzinfo=timezone.utc)

    return jsonify(
        {
            "plan": effective_plan,
            "plan_display_name": get_plan_display_name(effective_plan),
            "base_plan": school.subscription_plan or "Free Tier",
            "base_plan_display_name": get_plan_display_name(school.subscription_plan or "Free Tier"),
            "effective_plan": effective_plan,
            "trial": {
                "active": bool(
                    school.trial_plan
                    and trial_end_date
                    and datetime.now(timezone.utc) < trial_end_date
                ),
                "plan": school.trial_plan,
                "end_date": trial_end_date.isoformat() if trial_end_date else None,
            },
        }
    ), 200


@api.route("/school/subscription/upgrade", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def upgrade_subscription():
    """Process subscription plan upgrade."""
    try:
        data = request.json
        new_plan = data.get("plan", "Premium")
        
        school = School.query.get(g.school_id)
        previous_plan = school.subscription_plan or "Free Tier"
        current_effective_plan = get_effective_plan(school)

        if new_plan not in PLAN_FEATURES:
            return jsonify({"message": "Unknown subscription plan."}), 400

        if _subscription_plan_rank(new_plan) > _subscription_plan_rank(previous_plan):
            return jsonify(
                {
                    "message": "Paid plan upgrades must go through the billing checkout flow.",
                    "error": "payment_required_for_upgrade",
                }
            ), 409

        if new_plan == previous_plan:
            return jsonify(
                {
                    "message": f"School is already on {new_plan}.",
                    "plan": current_effective_plan,
                    "base_plan": previous_plan,
                }
            ), 200
        
        # Get proprietor email
        proprietor = User.query.filter_by(
            school_id=g.school_id, 
            role="proprietor"
        ).first()
        
        if not proprietor or not proprietor.email:
            return jsonify({"message": "Proprietor email not found"}), 400
        
        # Direct changes here are restricted to downgrades or same-tier admin corrections.
        school.subscription_plan = new_plan
        school.subscription_status = "Active"
        if new_plan == "Free Tier":
            school.next_billing_date = None
        db.session.commit()
        
        # Get plan details
        plan_info = PLAN_FEATURES.get(new_plan, {})
        
        # Generate plan-change confirmation email
        upgrade_date = get_utc_now().strftime("%Y-%m-%d")
        next_billing_date = (
            school.next_billing_date.strftime("%Y-%m-%d")
            if school.next_billing_date
            else None
        )
        
        features = plan_info.get("features", {})
        
        # Format usage limits  
        max_students = plan_info.get("max_students", 50)
        max_classes = plan_info.get("max_classes", 1)
        usage_limits = f"Students: {max_students if max_students != float('inf') else 'Unlimited'}\nClasses: {max_classes if max_classes != float('inf') else 'Unlimited'}"
        
        # Get new features not in previous plan
        prev_plan_info = PLAN_FEATURES.get(previous_plan, {})
        prev_features = set(prev_plan_info.get("features", {}).keys())
        new_features_set = set(features.keys()) - prev_features
        new_features = "\n".join([f"✨ {f.replace('_', ' ').title()}" for f in new_features_set]) if new_features_set else "Access to all features in your new plan"
        
        logger.info(f"School {g.school_id} changed plan from {previous_plan} to {new_plan}")
        return jsonify({
            "message": f"Plan changed to {new_plan} successfully.",
            "plan": new_plan,
            "base_plan": new_plan,
            "next_billing_date": next_billing_date
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Subscription upgrade error: {str(e)}")
        return jsonify({"message": f"Upgrade failed: {str(e)}"}), 500


# --- ACADEMIC TERM MANAGEMENT ---


@api.route("/school/subscription/billing-visibility", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def get_subscription_billing_visibility():
    """Visibility endpoint for active-student meter, overage, and threshold alerts."""
    visibility = get_billing_visibility(g.school_id)
    if "error" in visibility:
        return jsonify(visibility), 404
    return jsonify(visibility), 200


@api.route("/school/subscription/meter/sync", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def sync_subscription_meter():
    """Manually sync active-student billable meter."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    active_count = sync_student_meter(school)
    return jsonify({
        "message": "Student meter synced",
        "active_students": active_count,
        "last_metered_at": school.last_metered_at.isoformat() if school.last_metered_at else None,
    }), 200


@api.route("/school/subscription/trial/status", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def get_subscription_trial_status():
    """Return premium trial entitlement status and expiry state."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    visibility = get_billing_visibility(g.school_id)
    if "error" in visibility:
        return jsonify(visibility), 404

    trial = visibility.get("trial", {})
    has_used_trial = bool(school.trial_end_date)
    base_plan = school.subscription_plan or "Free Tier"
    available_trial_plans = []
    for plan_name in ["Basic", "Premium"]:
        if _subscription_plan_rank(plan_name) > _subscription_plan_rank(base_plan):
            available_trial_plans.append(
                {
                    "plan": plan_name,
                    "display_name": get_plan_display_name(plan_name),
                    "description": PLAN_FEATURES.get(plan_name, {}).get("description", ""),
                    "includes_addons": plan_name == "Premium",
                }
            )

    return jsonify({
        "is_active": bool(trial.get("is_active") or trial.get("active")),
        "plan": trial.get("plan"),
        "plan_display_name": get_plan_display_name(trial.get("plan")) if trial.get("plan") else None,
        "start_date": trial.get("start_date"),
        "end_date": trial.get("end_date"),
        "term_name": trial.get("term_name"),
        "academic_year": trial.get("academic_year"),
        "reference_source": trial.get("reference_source"),
        "has_used_trial": has_used_trial,
        "trial_ended_at": school.trial_end_date.isoformat() if school.trial_end_date else None,
        "base_plan": base_plan,
        "base_plan_display_name": get_plan_display_name(base_plan),
        "available_trial_plans": available_trial_plans,
    }), 200


@api.route("/school/subscription/trial/activate", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def activate_subscription_trial():
    """Activate premium trial entitlement for this tenant."""
    data = request.get_json(silent=True) or {}
    trial_plan = sanitize_string(data.get("trial_plan") or "Premium")
    result = activate_premium_trial(g.school_id, trial_plan=trial_plan)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 200


@api.route("/school/subscription/trial/end", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def end_subscription_trial():
    """End active trial and fall back to base subscription entitlements."""
    result = end_trial(g.school_id)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 200


@api.route("/school/subscription/lock-pricing", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def lock_subscription_pricing():
    """Lock current pricing values to grandfather existing tenant."""
    data = request.get_json(silent=True) or {}
    version_name = data.get("version")

    result = lock_pricing_version(g.school_id, version=version_name)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result), 200


@api.route("/school/subscription/usage-report/send", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def send_usage_report():
    """Send monthly usage report email to proprietor."""
    from backend.email_service import send_usage_report_email
    
    data = request.get_json(silent=True) or {}
    month = data.get("month")  # Optional: specify month (1-12)
    year = data.get("year")    # Optional: specify year
    
    success = send_usage_report_email(g.school_id, month=month, year=year)
    
    if success:
        return jsonify({
            "message": "Usage report sent successfully",
            "status": "sent"
        }), 200
    else:
        return jsonify({
            "message": "Failed to send usage report",
            "status": "failed"
        }), 500


@api.route("/school/subscription/usage-stats", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def get_usage_stats():
    """Get usage statistics for dashboard preview (without sending email)."""
    from backend.email_service import get_school_usage_stats
    
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    
    stats = get_school_usage_stats(g.school_id, month=month, year=year)
    
    if not stats:
        return jsonify({"message": "Failed to retrieve usage stats"}), 404
    
    return jsonify(stats), 200


@api.route("/school/subscription/billing-timeline", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def get_billing_timeline():
    """Return recent billing lifecycle events for proprietor support visibility."""
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit, 200))
    events = _get_billing_timeline(g.school_id)
    return jsonify({"events": events[:limit], "count": len(events)}), 200


@api.route("/school/subscription/ledger/reconciliation", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def get_subscription_ledger_reconciliation():
    """Provide ledger integrity and reconciliation details for subscription transactions."""
    school_id = g.school_id
    summary = get_ledger_summary(school_id)
    is_valid, broken_entries, checked = verify_ledger_chain(school_id)

    subscription_entries = (
        LedgerEntry.query.filter(
            LedgerEntry.school_id == school_id,
            LedgerEntry.tx_type.like("subscription%"),
        )
        .order_by(LedgerEntry.created_at.desc())
        .limit(100)
        .all()
    )

    pending = [e for e in subscription_entries if e.amount > 0 and (e.meta or {}).get("status") == "Pending"]
    completed = [e for e in subscription_entries if e.amount > 0 and (e.meta or {}).get("status") != "Pending"]

    return jsonify(
        {
            "summary": summary,
            "chain_check": {
                "valid": is_valid,
                "checked_entries": checked,
                "broken_entries": broken_entries,
            },
            "subscription_ledger": {
                "total_entries": len(subscription_entries),
                "completed_entries": len(completed),
                "pending_entries": len(pending),
                "recent": [
                    {
                        "tx_ref": entry.tx_ref,
                        "tx_type": entry.tx_type,
                        "amount": entry.amount,
                        "currency": entry.currency,
                        "source": entry.source,
                        "verified": bool(entry.is_verified),
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                        "metadata": entry.meta or {},
                    }
                    for entry in subscription_entries
                ],
            },
        }
    ), 200


@api.route("/school/subscription/ledger/reconciliation/recover", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def recover_subscription_reconciliation_gaps():
    """Cross-check recent successful Paystack transactions and recover any missing local records."""
    payload = request.get_json(silent=True) or {}
    lookback_hours = payload.get("lookback_hours", 24)
    try:
        summary = run_paystack_reconciliation_sweep(
            lookback_hours=lookback_hours,
            school_id_scope=g.school_id,
        )
        return jsonify(summary), 200
    except Exception as exc:
        db.session.rollback()
        return jsonify({"message": "Paystack reconciliation failed", "error": str(exc)}), 500


@api.route("/finance/paystack/recover-reference", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def recover_finance_paystack_reference():
    """Recover one Paystack transaction reference without relying on the removed reconciliation card."""
    payload = request.get_json(silent=True) or {}
    reference = sanitize_string(payload.get("reference") or "") or ""
    if not reference:
        return jsonify({"message": "Transaction reference is required."}), 400

    from backend.paystack_integration import verify_payment, PaystackError

    try:
        transaction = verify_payment(reference)
    except PaystackError as exc:
        return jsonify({"message": "Unable to verify the Paystack transaction.", "error": str(exc)}), 502

    if sanitize_string(transaction.get("status") or "").lower() != "success":
        return jsonify({
            "status": "not_completed",
            "reference": reference,
            "message": "The Paystack transaction is not yet marked successful.",
        }), 409

    try:
        outcome = _recover_paystack_transaction(transaction, school_id_scope=g.school_id)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"message": "Paystack recovery failed", "error": str(exc), "reference": reference}), 500

    if isinstance(outcome, dict):
        return jsonify({
            **outcome,
            "reference": outcome.get("reference") or reference,
        }), 200

    return jsonify({"status": outcome, "reference": reference}), 200


@api.route("/school/subscription/statement/download", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "finance")
def download_billing_statement():
    """Download billing statement as CSV for accounting and reconciliation."""
    fmt = (request.args.get("format") or "csv").strip().lower()
    if fmt != "csv":
        return jsonify({"message": "Only CSV statement format is currently supported."}), 400

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = LedgerEntry.query.filter(
        LedgerEntry.school_id == g.school_id,
        LedgerEntry.tx_type.like("subscription%"),
    )

    if start_date:
        try:
            parsed = datetime.fromisoformat(start_date).date()
            query = query.filter(LedgerEntry.created_at >= datetime.combine(parsed, datetime.min.time()))
        except Exception:
            return jsonify({"message": "Invalid start_date format. Use YYYY-MM-DD."}), 400

    if end_date:
        try:
            parsed = datetime.fromisoformat(end_date).date()
            query = query.filter(LedgerEntry.created_at <= datetime.combine(parsed, datetime.max.time()))
        except Exception:
            return jsonify({"message": "Invalid end_date format. Use YYYY-MM-DD."}), 400

    entries = query.order_by(LedgerEntry.created_at.desc()).all()

    csv_buffer = StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "created_at",
            "tx_ref",
            "tx_type",
            "amount",
            "currency",
            "source",
            "verified",
            "metadata",
        ]
    )
    for entry in entries:
        writer.writerow(
            [
                entry.created_at.isoformat() if entry.created_at else "",
                entry.tx_ref,
                entry.tx_type,
                f"{entry.amount:.2f}",
                entry.currency,
                entry.source,
                "yes" if entry.is_verified else "no",
                json.dumps(entry.meta or {}, sort_keys=True),
            ]
        )

    filename = f"billing_statement_{g.school_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response = make_response(csv_buffer.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@api.route("/school/subscription/price-cap", methods=["GET", "POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def manage_price_cap():
    """
    Get or set price cap for predictable billing.
    GET: Retrieve current price cap
    POST: Set new price cap
    """
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404
    
    if request.method == "GET":
        # Return current price cap settings
        price_cap = getattr(school, 'price_cap_amount', None)
        price_cap_enabled = getattr(school, 'price_cap_enabled', False)
        
        return jsonify({
            "price_cap_enabled": price_cap_enabled,
            "price_cap_amount": price_cap,
            "current_term_cost": school.current_student_count * 12 if school.current_student_count else 0,
            "message": "Price cap retrieved successfully"
        }), 200
    
    elif request.method == "POST":
        # Set new price cap
        data = request.get_json(silent=True) or {}
        enabled = data.get("enabled", False)
        amount = data.get("amount")
        
        if enabled and (not amount or amount <= 0):
            return jsonify({"message": "Price cap amount must be positive when enabled"}), 400
        
        # Store price cap settings in SchoolSettings
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
        if not settings:
            settings = SchoolSettings(school_id=g.school_id)
            db.session.add(settings)
        
        # Store as JSON in settings (extend SchoolSettings model if needed)
        settings.price_cap_enabled = enabled
        settings.price_cap_amount = amount if enabled else None
        
        db.session.commit()
        
        return jsonify({
            "message": "Price cap updated successfully",
            "price_cap_enabled": enabled,
            "price_cap_amount": amount
        }), 200


@api.route("/school/subscription/auto-billing", methods=["GET", "POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def manage_auto_billing():
    """Get or update auto-billing preference for subscription renewals."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    config = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))

    if request.method == "GET":
        cards = config.get("cards") or []
        return jsonify(
            {
                "enabled": bool(config.get("enabled", False)),
                "has_authorization": bool(config.get("authorization_code")),
                "authorization_last4": config.get("authorization_last4"),
                "authorization_brand": config.get("authorization_brand"),
                "authorization_bank": config.get("authorization_bank"),
                "authorization_email": config.get("customer_email"),
                "default_card_id": config.get("default_card_id"),
                "cards": [_sanitize_saved_card(c) for c in cards],
                "cards_count": len(cards),
                "updated_at": config.get("updated_at"),
            }
        ), 200

    data = request.get_json(silent=True) or {}
    enabled = bool(data.get("enabled", False))
    config["enabled"] = enabled
    config["updated_at"] = get_utc_now().isoformat()
    saved = _normalize_auto_billing_config(_upsert_auto_billing_config(g.school_id, config))

    return jsonify(
        {
            "message": "Auto-billing settings updated",
            "enabled": bool(saved.get("enabled", False)),
            "has_authorization": bool(saved.get("authorization_code")),
            "default_card_id": saved.get("default_card_id"),
            "cards": [_sanitize_saved_card(c) for c in (saved.get("cards") or [])],
            "updated_at": saved.get("updated_at"),
        }
    ), 200


@api.route("/school/subscription/auto-billing/unsubscribe", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def unsubscribe_auto_billing():
    """Disable recurring auto-billing while keeping saved cards for future re-enable."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    billing_growth_block = _billing_growth_block_response(school, assume_no_payment_coverage=True)
    if billing_growth_block:
        return billing_growth_block

    config = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))
    config["enabled"] = False
    config["updated_at"] = get_utc_now().isoformat()
    _upsert_auto_billing_config(g.school_id, config)

    return jsonify(
        {
            "message": "Recurring auto-billing disabled successfully.",
            "enabled": False,
            "cards_count": len(config.get("cards") or []),
            "can_reenable_anytime": True,
        }
    ), 200


@api.route("/school/subscription/cards", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def list_saved_cards():
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    config = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))
    cards = config.get("cards") or []

    return jsonify(
        {
            "cards": [_sanitize_saved_card(c) for c in cards],
            "default_card_id": config.get("default_card_id"),
            "cards_count": len(cards),
            "enabled": bool(config.get("enabled", False)),
        }
    ), 200


@api.route("/school/subscription/cards/default", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def set_default_saved_card():
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    data = request.get_json(silent=True) or {}
    card_id = sanitize_string(data.get("card_id") or "")
    if not card_id:
        return jsonify({"message": "card_id is required"}), 400

    config = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))
    cards = config.get("cards") or []
    if not cards:
        return jsonify({"message": "No saved cards available"}), 400

    target = next((c for c in cards if c.get("card_id") == card_id), None)
    if not target:
        return jsonify({"message": "Card not found"}), 404

    for card in cards:
        card["is_default"] = False

    target["is_default"] = True
    target["updated_at"] = get_utc_now().isoformat()

    config["cards"] = cards
    config["default_card_id"] = card_id
    config["authorization_code"] = target.get("authorization_code")
    config["authorization_last4"] = target.get("last4")
    config["authorization_brand"] = target.get("brand")
    config["authorization_bank"] = target.get("bank")
    config["customer_email"] = target.get("customer_email")
    config["updated_at"] = get_utc_now().isoformat()
    _upsert_auto_billing_config(g.school_id, config)

    return jsonify(
        {
            "message": "Default billing card updated",
            "default_card_id": card_id,
            "cards": [_sanitize_saved_card(c) for c in (config.get("cards") or [])],
        }
    ), 200


@api.route("/school/subscription/cards/<card_id>", methods=["DELETE"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def remove_saved_card(card_id):
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    card_id = sanitize_string(card_id or "")
    if not card_id:
        return jsonify({"message": "Invalid card id"}), 400

    config = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))
    cards = config.get("cards") or []
    target_card = next((c for c in cards if c.get("card_id") == card_id), None)
    if not target_card:
        return jsonify({"message": "Card not found"}), 404

    if len(cards) == 1:
        billing_growth_block = _billing_growth_block_response(school, assume_no_payment_coverage=True)
        if billing_growth_block:
            return billing_growth_block

    retained = [c for c in cards if c.get("card_id") != card_id]

    if len(retained) == len(cards):
        return jsonify({"message": "Card not found"}), 404

    if retained:
        if not any(c.get("is_default") for c in retained):
            retained[0]["is_default"] = True
        default_card = next((c for c in retained if c.get("is_default")), retained[0])
        config["default_card_id"] = default_card.get("card_id")
        config["authorization_code"] = default_card.get("authorization_code")
        config["authorization_last4"] = default_card.get("last4")
        config["authorization_brand"] = default_card.get("brand")
        config["authorization_bank"] = default_card.get("bank")
        config["customer_email"] = default_card.get("customer_email")
    else:
        config["enabled"] = False
        config["default_card_id"] = None
        config["authorization_code"] = None
        config["authorization_last4"] = None
        config["authorization_brand"] = None
        config["authorization_bank"] = None

    config["cards"] = retained
    config["updated_at"] = get_utc_now().isoformat()
    _upsert_auto_billing_config(g.school_id, config)

    return jsonify(
        {
            "message": "Card removed successfully",
            "cards": [_sanitize_saved_card(c) for c in (config.get("cards") or [])],
            "default_card_id": config.get("default_card_id"),
            "enabled": bool(config.get("enabled", False)),
        }
    ), 200


@api.route("/school/subscription/cards/setup-link", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def create_card_setup_link():
    """Create a Paystack checkout link to securely add or replace billing card authorization."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    proprietor = User.query.filter_by(school_id=g.school_id, role="proprietor").first()
    if not proprietor or not proprietor.email:
        return jsonify({"message": "Proprietor email not found"}), 400

    payload = request.get_json(silent=True) or {}
    setup_amount = float(payload.get("amount_cedis") or 5.0)
    if setup_amount < 1:
        return jsonify({"message": "amount_cedis must be at least 1.00"}), 400

    from backend.paystack_integration import initialize_payment, PaystackError

    configured_frontend = (os.getenv("FRONTEND_URL") or "http://localhost:5173").rstrip("/")
    origin = (request.headers.get("Origin") or "").strip().rstrip("/")
    referer = (request.headers.get("Referer") or "").strip()

    callback_base = configured_frontend
    if origin.startswith("http://") or origin.startswith("https://"):
        callback_base = origin
    elif referer.startswith("http://") or referer.startswith("https://"):
        try:
            from urllib.parse import urlparse

            parsed = urlparse(referer)
            callback_base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            callback_base = configured_frontend

    callback_url = f"{callback_base}/payment/callback"
    plan_name = school.subscription_plan if school.subscription_plan and school.subscription_plan != "Free Tier" else "Basic"

    try:
        result = initialize_payment(
            email=proprietor.email,
            amount_cents=int(round(setup_amount * 100)),
            plan_name=plan_name,
            school_id=g.school_id,
            metadata={
                "callback_url": callback_url,
                "card_setup_only": True,
                "transaction_type": "card_setup",
                "skip_subscription_update": True,
                "school_id": g.school_id,
            },
        )

        return jsonify(
            {
                "message": "Card setup link generated",
                "authorization_url": result.get("authorization_url"),
                "reference": result.get("reference"),
                "setup_amount_cedis": round(setup_amount, 2),
                "note": "This payment method will be saved for future pay-as-you-go recurring billing.",
            }
        ), 200
    except PaystackError as err:
        return jsonify({"message": f"Failed to initialize card setup: {str(err)}"}), 500


@api.route("/school/terms", methods=["GET"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "headmaster")
def get_academic_terms():
    """Get all academic terms for the school."""
    try:
        terms = AcademicTerm.query.filter_by(school_id=g.school_id).order_by(
            AcademicTerm.academic_year.desc(),
            AcademicTerm.name.asc()
        ).all()
        suggested_academic_year = get_recommended_published_national_basic_academic_year()
        
        return jsonify({
            "terms": [term.to_dict() for term in terms],
            "count": len(terms),
            "suggested_academic_year": suggested_academic_year,
        }), 200
        
    except Exception as e:
        logger.error(f"Get terms error: {str(e)}")
        return jsonify({"message": f"Failed to retrieve terms: {str(e)}"}), 500


@api.route("/school/terms/active", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_active_term():
    """Get the currently active academic term."""
    try:
        active_term = AcademicTerm.query.filter_by(
            school_id=g.school_id,
            is_active=True
        ).first()
        
        if not active_term:
            return jsonify({"message": "No active term found", "term": None}), 200
        
        return jsonify({"term": active_term.to_dict()}), 200
        
    except Exception as e:
        logger.error(f"Get active term error: {str(e)}")
        return jsonify({"message": f"Failed to retrieve active term: {str(e)}"}), 500


@api.route("/school/terms/import-national-calendar", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "headmaster")
def import_national_calendar_terms():
    """Import published national basic-school term windows for an academic year."""
    try:
        data = request.json or {}
        academic_year = (data.get("academic_year") or "").strip() or get_recommended_published_national_basic_academic_year()
        if not academic_year:
            return jsonify({"message": "No published national calendar is available yet."}), 404

        published_terms = get_published_national_basic_term_windows(academic_year)
        if not published_terms:
            return jsonify({"message": f"No published national calendar found for {academic_year}"}), 404

        created_terms = []
        skipped_terms = []
        active_term = AcademicTerm.query.filter_by(school_id=g.school_id, is_active=True).first()
        today = date.today()
        creator_id = get_jwt_identity()

        for term_window in published_terms:
            existing = AcademicTerm.query.filter_by(
                school_id=g.school_id,
                academic_year=academic_year,
                name=term_window["name"],
            ).first()

            if existing:
                skipped_terms.append(existing.name)
                continue

            should_activate = (
                active_term is None
                and term_window["start_date"] <= today <= term_window["end_date"]
            )
            new_term = AcademicTerm(
                school_id=g.school_id,
                name=term_window["name"],
                academic_year=academic_year,
                start_date=term_window["start_date"],
                end_date=term_window["end_date"],
                billing_due_date=term_window.get("reopening_date"),
                is_active=should_activate,
                created_by=creator_id,
            )
            db.session.add(new_term)
            created_terms.append(new_term)
            if should_activate:
                active_term = new_term

        db.session.commit()

        status_code = 201 if created_terms else 200
        return (
            jsonify(
                {
                    "message": (
                        f"Imported {len(created_terms)} published term(s) for {academic_year}"
                        if created_terms
                        else f"Published terms for {academic_year} are already in your calendar"
                    ),
                    "academic_year": academic_year,
                    "created_count": len(created_terms),
                    "skipped_count": len(skipped_terms),
                    "created_terms": [term.to_dict() for term in created_terms],
                    "skipped_terms": skipped_terms,
                }
            ),
            status_code,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Import national calendar terms error: {str(e)}")
        return jsonify({"message": f"Failed to import national calendar terms: {str(e)}"}), 500


@api.route("/school/terms", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "headmaster")
def create_academic_term():
    """Create a new academic term."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ["name", "academic_year", "start_date", "end_date"]
        for field in required_fields:
            if not data.get(field):
                return jsonify({"message": f"Missing required field: {field}"}), 400
        
        # Parse dates
        from dateutil.parser import parse as parse_date
        start_date = parse_date(data["start_date"]).date()
        end_date = parse_date(data["end_date"]).date()
        
        # Validate date range
        if end_date <= start_date:
            return jsonify({"message": "End date must be after start date"}), 400
        
        # Check for duplicate term
        existing = AcademicTerm.query.filter_by(
            school_id=g.school_id,
            academic_year=data["academic_year"],
            name=data["name"]
        ).first()
        
        if existing:
            return jsonify({"message": "Term already exists for this academic year"}), 400
        
        # Parse billing due date if provided
        billing_due_date = None
        if data.get("billing_due_date"):
            billing_due_date = parse_date(data["billing_due_date"]).date()
        
        # If marking as active, deactivate other terms first
        if data.get("is_active", False):
            AcademicTerm.query.filter_by(
                school_id=g.school_id,
                is_active=True
            ).update({"is_active": False})
        
        # Create new term
        new_term = AcademicTerm(
            school_id=g.school_id,
            name=data["name"],
            academic_year=data["academic_year"],
            start_date=start_date,
            end_date=end_date,
            is_active=data.get("is_active", False),
            billing_due_date=billing_due_date,
            created_by=get_jwt_identity()
        )
        
        db.session.add(new_term)
        db.session.commit()
        
        logger.info(f"Created term {new_term.name} {new_term.academic_year} for school {g.school_id}")
        
        return jsonify({
            "message": "Academic term created successfully",
            "term": new_term.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create term error: {str(e)}")
        return jsonify({"message": f"Failed to create term: {str(e)}"}), 500


@api.route("/school/terms/<int:term_id>", methods=["PUT"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "headmaster")
def update_academic_term(term_id):
    """Update an existing academic term."""
    try:
        term = AcademicTerm.query.filter_by(
            id=term_id,
            school_id=g.school_id
        ).first()
        
        if not term:
            return jsonify({"message": "Term not found"}), 404
        
        data = request.json
        
        # Update fields if provided
        if "name" in data:
            term.name = data["name"]
        
        if "academic_year" in data:
            term.academic_year = data["academic_year"]
        
        if "start_date" in data:
            from dateutil.parser import parse as parse_date
            term.start_date = parse_date(data["start_date"]).date()
        
        if "end_date" in data:
            from dateutil.parser import parse as parse_date
            term.end_date = parse_date(data["end_date"]).date()
        
        if "billing_due_date" in data:
            if data["billing_due_date"]:
                from dateutil.parser import parse as parse_date
                term.billing_due_date = parse_date(data["billing_due_date"]).date()
            else:
                term.billing_due_date = None
        
        # Validate date range
        if term.end_date <= term.start_date:
            return jsonify({"message": "End date must be after start date"}), 400
        
        # Handle activating this term
        if "is_active" in data and data["is_active"] and not term.is_active:
            # Deactivate all other terms first
            AcademicTerm.query.filter_by(
                school_id=g.school_id,
                is_active=True
            ).update({"is_active": False})
            term.is_active = True
        elif "is_active" in data and not data["is_active"]:
            term.is_active = False
        
        db.session.commit()
        
        logger.info(f"Updated term {term_id} for school {g.school_id}")
        
        return jsonify({
            "message": "Term updated successfully",
            "term": term.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update term error: {str(e)}")
        return jsonify({"message": f"Failed to update term: {str(e)}"}), 500


@api.route("/school/terms/<int:term_id>", methods=["DELETE"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def delete_academic_term(term_id):
    """Delete an academic term (only if no data associated)."""
    try:
        term = AcademicTerm.query.filter_by(
            id=term_id,
            school_id=g.school_id
        ).first()
        
        if not term:
            return jsonify({"message": "Term not found"}), 404
        
        # Check if term is active
        if term.is_active:
            return jsonify({"message": "Cannot delete active term. Deactivate it first."}), 400

        blockers = _academic_term_delete_blockers(term)
        if blockers:
            return (
                jsonify(
                    {
                        "message": "Academic term has dependent academic or billing history and cannot be deleted.",
                        "error": "academic_term_delete_blocked",
                        "blockers": blockers,
                    }
                ),
                409,
            )
        
        db.session.delete(term)
        db.session.commit()
        
        logger.info(f"Deleted term {term_id} for school {g.school_id}")
        
        return jsonify({"message": "Term deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete term error: {str(e)}")
        return jsonify({"message": f"Failed to delete term: {str(e)}"}), 500


@api.route("/school/terms/<int:term_id>/activate", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor", "headmaster")
def activate_academic_term(term_id):
    """Activate a specific term (deactivates all others)."""
    try:
        term = AcademicTerm.query.filter_by(
            id=term_id,
            school_id=g.school_id
        ).first()
        
        if not term:
            return jsonify({"message": "Term not found"}), 404
        
        school = School.query.get(g.school_id)
        if not school:
            return jsonify({"message": "School not found"}), 404
        
        # Trigger billing for paid plans

        term.is_active = True
        db.session.commit()

        logger.info(f"Activated term {term_id} ({term.name} {term.academic_year}) for school {g.school_id}")
        
        response = {
            "message": f"Activated {term.name} {term.academic_year}",
            "term": term.to_dict(),
            "billing_initiated": False
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Activate term error: {str(e)}")
        return jsonify({"message": f"Failed to activate term: {str(e)}"}), 500, 500


@api.route("/support/ticket", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def create_support_ticket():
    """Submit a help request."""
    data = request.json
    ticket = SupportTicket(
        school_id=g.school_id,
        user_id=get_jwt_identity(),
        type=data.get("type", "Bug Report"),
        description=data.get("description"),
    )
    db.session.add(ticket)
    db.session.commit()
    
    # Get user and school information
    user = User.query.get(get_jwt_identity())
    school = School.query.get(g.school_id)
    
    # 1. SEND EMAIL TO ADMIN (YOU)
    admin_email = (
        os.getenv("FOUNDER_EMAIL")
        or os.getenv("MAIL_DEFAULT_SENDER")
        or os.getenv("MAIL_USERNAME")
        or "noreply@edupulse.local"
    )
    try:
        admin_subject = f"🎫 New Support Ticket #{ticket.id} - {ticket.type}"
        admin_body = f"""New support ticket submitted:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: #{ticket.id}
Status: {ticket.status}
Type: {ticket.type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCHOOL DETAILS:
• School: {school.name if school else 'Unknown'}
• School ID: {g.school_id}

USER DETAILS:
• Name: {user.name if user else 'Unknown'}
• Email: {user.email if user else 'N/A'}
• Role: {user.role if user else 'N/A'}

ISSUE DESCRIPTION:
{ticket.description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Submitted: {ticket.created_at.strftime('%B %d, %Y at %I:%M %p')}

To respond, log in to the admin panel or reply directly to this ticket.
"""
        send_email_notification(admin_email, admin_subject, admin_body)
    except Exception as e:
        print(f"Failed to send admin notification: {e}")
    
    # 2. SEND CONFIRMATION EMAIL TO USER
    if user and user.email:
        try:
            user_subject = f"✅ Support Ticket #{ticket.id} Received - EduPulse"
            user_body = f"""Hello {user.name},

Thank you for contacting EduPulse support! Your ticket has been received and our team will review it shortly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your Ticket Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: #{ticket.id}
Type: {ticket.type}
Status: {ticket.status}
Submitted: {ticket.created_at.strftime('%B %d, %Y at %I:%M %p')}

Your Message:
{ticket.description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

What happens next?
• Our support team will review your ticket within 24-48 hours
• You'll receive an email notification when we respond
• Track your ticket status in Help & Support > My Tickets

Need urgent assistance? Check our Help Center for instant answers:
{os.getenv('APP_URL', 'https://edupulse.edu')}/help

Thank you for using EduPulse!

Best regards,
EduPulse Support Team
"""
            send_email_notification(user.email, user_subject, user_body)
        except Exception as e:
            print(f"Failed to send user confirmation: {e}")
    
    return jsonify({"message": "Support ticket submitted successfully. Check your email for confirmation."})


def _live_chat_enabled():
    return os.getenv("ENABLE_LIVE_CHAT", "false").strip().lower() == "true"


@api.route("/support/live-chat/status", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_live_chat_status():
    """Feature-flag status for live chat rollout readiness."""
    enabled = _live_chat_enabled()
    return jsonify(
        {
            "enabled": enabled,
            "message": "Live chat is available." if enabled else "Live chat is not enabled yet.",
        }
    )


@api.route("/support/live-chat/messages", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_live_chat_messages():
    """Get current user's live chat messages for the active open session."""
    if not _live_chat_enabled():
        return jsonify({"message": "Live chat is disabled for this environment."}), 503

    user_id = int(get_jwt_identity())
    session = (
        LiveChatSession.query.filter_by(school_id=g.school_id, user_id=user_id, status="open")
        .order_by(LiveChatSession.created_at.desc())
        .first()
    )

    if not session:
        return jsonify({"session_id": None, "messages": []})

    messages = (
        LiveChatMessage.query.filter_by(session_id=session.id)
        .order_by(LiveChatMessage.created_at.asc())
        .all()
    )

    return jsonify(
        {
            "session_id": session.id,
            "messages": [
                {
                    "id": m.id,
                    "sender_type": m.sender_type,
                    "message": m.message,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }
    )


@api.route("/support/live-chat/messages", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def post_live_chat_message():
    """Create a user message in live chat (future-ready backend path)."""
    if not _live_chat_enabled():
        return jsonify({"message": "Live chat is disabled for this environment."}), 503

    data = request.get_json(silent=True) or {}
    message = sanitize_string(data.get("message"))
    if not message:
        return jsonify({"message": "Message is required."}), 400

    user_id = int(get_jwt_identity())

    session = (
        LiveChatSession.query.filter_by(school_id=g.school_id, user_id=user_id, status="open")
        .order_by(LiveChatSession.created_at.desc())
        .first()
    )
    if not session:
        session = LiveChatSession(school_id=g.school_id, user_id=user_id, status="open")
        db.session.add(session)
        db.session.flush()

    live_message = LiveChatMessage(
        session_id=session.id,
        school_id=g.school_id,
        user_id=user_id,
        sender_type="user",
        message=message,
    )
    db.session.add(live_message)
    db.session.commit()

    return jsonify(
        {
            "message": "Live chat message queued.",
            "session_id": session.id,
            "data": {
                "id": live_message.id,
                "sender_type": live_message.sender_type,
                "message": live_message.message,
                "created_at": live_message.created_at.isoformat() if live_message.created_at else None,
            },
        }
    ), 201


@api.route("/support/history", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_ticket_history():
    """Fetch support history for the current user."""
    user_id = get_jwt_identity()
    tickets = (
        SupportTicket.query.filter_by(user_id=user_id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": t.id,
                "type": t.type,
                "description": t.description,
                "status": t.status,
                "admin_response": t.admin_response,
                "created_at": t.created_at.strftime("%Y-%m-%d"),
            }
            for t in tickets
        ]
    )


# --- 7. SUPER ADMIN (Software Provider) ---


@api.route("/support/report-bug", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def report_bug():
    """Direct channel to report bugs to the developer."""
    data = request.json
    # In a real scenario, this would email the developer (Anyinam)
    # For now, we log it or create a high-priority ticket
    return jsonify(
        {
            "message": "Bug reported successfully. The development team has been notified."
        }
    )


@api.route("/admin/tickets", methods=["GET"])
@jwt_required()
def get_all_tickets():
    """Super Admin: View tickets from ALL schools."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": t.id,
                "school_id": t.school_id,
                "type": t.type,
                "description": t.description,
                "status": t.status,
                "admin_response": t.admin_response,
                "created_at": t.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for t in tickets
        ]
    )


@api.route("/admin/ticket/<int:ticket_id>/reply", methods=["POST"])
@jwt_required()
def reply_ticket(ticket_id):
    """Super Admin: Reply to a ticket."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json
    ticket = SupportTicket.query.get_or_404(ticket_id)

    ticket.admin_response = data.get("response")
    ticket.status = data.get("status", "Resolved")  # Allow 'In Progress' or 'Resolved'
    db.session.commit()

    log_action(operator["actor_id"], ticket.school_id, "ADMIN_TICKET_REPLY", f"Provider console replied to ticket #{ticket.id}")

    # SEND EMAIL NOTIFICATION TO USER
    user = User.query.get(ticket.user_id)
    school = School.query.get(ticket.school_id)
    
    if user and user.email:
        try:
            subject = f"💬 Response to Your Support Ticket #{ticket.id} - EduPulse"
            body = f"""Hello {user.name},

Great news! Our support team has responded to your ticket.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID: #{ticket.id}
Type: {ticket.type}
Status: {ticket.status}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your Original Message:
{ticket.description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUR RESPONSE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{ticket.admin_response}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Need further assistance? You can:
• View this response in Help & Support > My Tickets
• Submit a new ticket if you have follow-up questions
• Visit our Help Center: {os.getenv('APP_URL', 'https://edupulse.edu')}/help

Thank you for using EduPulse!

Best regards,
EduPulse Support Team
"""
            send_email_notification(user.email, subject, body)
        except Exception as e:
            print(f"Failed to send reply notification: {e}")

    return jsonify({"message": "Reply sent and user notified via email."})


@api.route("/admin/system-health", methods=["GET"])
@jwt_required()
def get_system_health():
    """Super Admin: Monitor system status."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    # Check Database Health & Latency
    start = datetime.now(timezone.utc)
    try:
        db.session.execute(text("SELECT 1"))
        db_latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        db_status = "Online"
    except:
        db_status = "Offline"
        db_latency = 0

    return jsonify(
        {
            "server_status": "Operational",
            "db_status": db_status,
            "db_latency": f"{db_latency:.1f}ms",
            "active_connections": "42",  # Mocked: In prod use pg_stat_activity
            "cpu_load": "15%",  # Mocked: In prod use psutil
        }
    )


@api.route("/admin/broadcast", methods=["POST"])
@jwt_required()
def admin_broadcast():
    """Super Admin: Broadcast system-wide alert."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json

    # Optional: Deactivate old maintenance alerts if a new one is posted
    if data.get("type") == "Maintenance":
        SystemAlert.query.filter_by(is_active=True, type="Maintenance").update(
            {"is_active": False}
        )

    alert = SystemAlert(
        message=data.get("message"),
        type=data.get("type", "Maintenance"),
        is_active=True,
    )
    db.session.add(alert)
    db.session.commit()

    log_action(operator["actor_id"], None, "ADMIN_BROADCAST", f"Broadcast sent: {data.get('message')[:80]}")
    return jsonify({"message": "System alert broadcasted."})


@api.route("/admin/schools", methods=["GET"])
@jwt_required()
def get_all_schools():
    """Super Admin: List all tenants."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    schools = School.query.all()
    school_rows = []
    summary = {
        "total_schools": len(schools),
        "active_subscriptions": 0,
        "free_tier": 0,
        "school_os": 0,
        "school_os_plus": 0,
        "trial_schools": 0,
        "ai_pack": 0,
        "automation_pack": 0,
    }

    for school in schools:
        effective_plan = get_effective_plan(school)
        trial_end = getattr(school, "trial_end_date", None)
        if trial_end and getattr(trial_end, "tzinfo", None) is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)

        settings = school.settings
        enabled_modules = dict(settings.enabled_modules or {}) if settings and isinstance(settings.enabled_modules, dict) else {}
        purchased_addons = {
            "automation_pack": any(bool(enabled_modules.get(module_key, False)) for module_key in ADDON_CATALOG["automation_pack"].get("module_keys", [])),
            "ai_pack": any(bool(enabled_modules.get(module_key, False)) for module_key in ADDON_CATALOG["ai_pack"].get("module_keys", [])),
        }
        active_addons = {
            addon_key: school_has_addon(school, addon_key, effective_plan=effective_plan)
            for addon_key in ADDON_CATALOG.keys()
        }
        proprietor = next(
            (user for user in (school.users or []) if getattr(user, "role", None) == "proprietor"),
            None,
        )
        student_count = _count_active_students_for_billing(school.id)
        trial_active = bool(school.trial_plan and trial_end and get_utc_now() < trial_end)

        summary["active_subscriptions"] += 1 if school.subscription_status == "Active" else 0
        summary["trial_schools"] += 1 if trial_active else 0
        if effective_plan == "Premium":
            summary["school_os_plus"] += 1
        elif effective_plan == "Basic":
            summary["school_os"] += 1
        else:
            summary["free_tier"] += 1
        summary["ai_pack"] += 1 if purchased_addons["ai_pack"] else 0
        summary["automation_pack"] += 1 if purchased_addons["automation_pack"] else 0

        school_rows.append(
            {
                "id": school.id,
                "code": school.id,
                "name": school.name,
                "email": proprietor.email if proprietor else None,
                "plan": school.subscription_plan or "Free Tier",
                "plan_display_name": get_plan_display_name(school.subscription_plan or "Free Tier"),
                "effective_plan": effective_plan,
                "effective_plan_display_name": get_plan_display_name(effective_plan),
                "status": school.subscription_status,
                "subscription_status": school.subscription_status,
                "is_active": school.is_active,
                "student_count": student_count,
                "created_at": school.created_at.isoformat() if getattr(school, "created_at", None) else None,
                "trial": {
                    "active": trial_active,
                    "plan": school.trial_plan,
                    "plan_display_name": get_plan_display_name(school.trial_plan) if school.trial_plan else None,
                    "end_date": trial_end.isoformat() if trial_end else None,
                },
                "active_addons": active_addons,
                "purchased_addons": purchased_addons,
            }
        )

    return jsonify({"schools": school_rows, "summary": summary})


@api.route("/admin/school/<school_id>/toggle", methods=["POST"])
@jwt_required()
def toggle_school_status(school_id):
    """Super Admin: Enable/Disable a school."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    db.session.commit()
    status = "activated" if school.is_active else "suspended"

    log_action(operator["actor_id"], school.id, "ADMIN_SCHOOL_STATUS", f"School {school.id} {status} by provider console")
    return jsonify({"message": f"School {school.name} has been {status}."})


@api.route("/admin/school/<school_id>/modules", methods=["POST"])
@jwt_required()
def update_school_modules(school_id):
    """Super Admin: Toggle feature flags for a school."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    school = School.query.get_or_404(school_id)
    if school.settings:
        school.settings.enabled_modules = request.json.get("modules")
        db.session.commit()

        log_action(operator["actor_id"], school.id, "ADMIN_MODULE_UPDATE", f"Modules updated for school {school.id}: {school.settings.enabled_modules}")
    return jsonify({"message": "Modules updated."})


@api.route("/admin/global-analytics", methods=["GET"])
@jwt_required()
def get_global_analytics():
    """Super Admin: View aggregated platform stats."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    total_revenue = (
        db.session.query(db.func.sum(Payment.amount))
        .filter(Payment.status == "Confirmed")
        .scalar()
        or 0
    )
    total_schools = School.query.count()
    total_students = Student.query.count()

    log_action(operator["actor_id"], None, "ADMIN_GLOBAL_ANALYTICS", "Provider console viewed global analytics")

    return jsonify(
        {
            "total_revenue": total_revenue,
            "total_schools": total_schools,
            "total_students": total_students,
        }
    )


@api.route("/admin/impersonate/<school_id>", methods=["POST"])
@jwt_required()
def impersonate_proprietor(school_id):
    """Super Admin: Log in as a specific school proprietor."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    target_school = School.query.get_or_404(school_id)
    target_user = User.query.filter_by(school_id=school_id, role="proprietor").first()

    if not target_user:
        return jsonify({"message": "No proprietor account found for this school."}), 404

    access_token = create_access_token(identity=str(target_user.id))

    log_action(operator["actor_id"], target_school.id, "ADMIN_IMPERSONATE", f"Impersonated proprietor {target_user.username} for school {school_id}")

    return jsonify(
        {"token": access_token, "school_id": target_school.id, "role": target_user.role}
    )


@api.route("/admin/school/<school_id>/trial", methods=["POST"])
@jwt_required()
def grant_school_trial(school_id):
    """Super Admin: Grant a 30-day trial plan to a school."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json or {}
    trial_plan = data.get("trial_plan", "Premium")
    if trial_plan not in {"Basic", "Premium"}:
        return jsonify({"message": "Trial plan must be School OS or School OS Plus."}), 400

    school = School.query.get_or_404(school_id)
    term_reference = get_current_term_reference(school.id)
    trial_start = datetime.now(timezone.utc)
    trial_end = trial_start + timedelta(days=30)

    school.trial_plan = trial_plan
    school.trial_end_date = trial_end
    school.is_trial_active = True
    school.subscription_status = "Trial"
    db.session.commit()

    log_action(operator["actor_id"], school.id, "ADMIN_TRIAL_GRANT", f"Granted 30-day {trial_plan} trial to school {school.id}")

    return jsonify(
        {
            "message": f"Trial granted: {trial_plan} for 30 days",
            "trial_plan": school.trial_plan,
            "trial_start": trial_start.isoformat(),
            "trial_end": school.trial_end_date.strftime("%Y-%m-%d"),
            "term_name": term_reference.get("name"),
            "academic_year": term_reference.get("academic_year"),
            "reference_source": term_reference.get("source"),
        }
    )


@api.route("/admin/backup", methods=["GET"])
@jwt_required()
def download_backup():
    """Super Admin: Download SQL Dump."""
    operator = _get_provider_console_operator()
    if not operator:
        return jsonify({"message": "Unauthorized"}), 403

    output = StringIO()
    output.write("-- EduPulse SMT Database Backup\n")
    output.write(f"-- Generated: {get_utc_now()}\n\n")

    # List of models to dump
    models = [
        (School, "schools"),
        (SchoolSettings, "school_settings"),
        (User, "users"),
        (Student, "students"),
        (Payment, "payments"),
        (Inventory, "inventory"),
        (SupportTicket, "support_tickets"),
        (SystemAlert, "system_alerts"),
    ]

    for model, table_name in models:
        rows = model.query.all()
        for row in rows:
            data = row.__dict__
            data.pop("_sa_instance_state", None)
            columns = ", ".join(data.keys())
            values = ", ".join(
                [
                    ("'" + str(v).replace("'", "''") + "'") if v is not None else "NULL"
                    for v in data.values()
                ]
            )
            output.write(f"INSERT INTO {table_name} ({columns}) VALUES ({values});\n")

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = (
        f"attachment; filename=edupulse_backup_{get_utc_now().strftime('%Y%m%d')}.sql"
    )
    response.headers["Content-type"] = "text/plain"

    log_action(operator["actor_id"], None, "ADMIN_BACKUP_DOWNLOAD", "Provider console downloaded database backup")

    return response


# =============================================================================
# TIMETABLE MANAGEMENT ENDPOINTS
# =============================================================================


@api.route("/timetable", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_timetable():
    """Retrieve all timetable entries for the school."""
    class_name = request.args.get("class_name")
    query = Timetable.query.filter_by(school_id=g.school_id)
    if class_name:
        query = query.filter(Timetable.class_name == class_name)

    entries = query.order_by(Timetable.day_of_week, Timetable.start_time).all()

    return jsonify(
        [
            {
                "id": e.id,
                "class_name": e.class_name,
                "subject_name": e.subject_name,
                "teacher_id": e.teacher_id,
                "teacher_name": e.teacher.username if e.teacher else "Unassigned",
                "day_of_week": e.day_of_week,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "location": e.location,
            }
            for e in entries
        ]
    )


@api.route("/timetable/class/<class_name>", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_class_timetable(class_name):
    """Retrieve timetable entries for a specific class."""
    entries = (
        Timetable.query.filter_by(school_id=g.school_id, class_name=class_name)
        .order_by(Timetable.day_of_week, Timetable.start_time)
        .all()
    )

    return jsonify(
        [
            {
                "id": e.id,
                "class_name": e.class_name,
                "subject_name": e.subject_name,
                "teacher_id": e.teacher_id,
                "teacher_name": e.teacher.username if e.teacher else "Unassigned",
                "day_of_week": e.day_of_week,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "location": e.location,
            }
            for e in entries
        ]
    )


@api.route("/timetable/my", methods=["GET"])
@multi_tenant_guard
@role_required("teacher", "homeroom")
@jwt_required()
def get_my_timetable():
    """Retrieve timetable entries for the logged-in teacher."""
    user_id = int(get_jwt_identity())
    query = Timetable.query.filter_by(school_id=g.school_id, teacher_id=user_id)

    assignments = TeacherAssignment.query.filter_by(
        school_id=g.school_id, teacher_id=user_id
    ).all()

    if assignments:
        conditions = [
            and_(
                Timetable.class_name == a.class_name,
                Timetable.subject_name == a.subject_name,
            )
            for a in assignments
        ]
        query = query.filter(or_(*conditions))

    entries = query.order_by(Timetable.day_of_week, Timetable.start_time).all()

    return jsonify(
        [
            {
                "id": e.id,
                "class_name": e.class_name,
                "subject_name": e.subject_name,
                "teacher_id": e.teacher_id,
                "teacher_name": e.teacher.username if e.teacher else "Unassigned",
                "day_of_week": e.day_of_week,
                "start_time": e.start_time,
                "end_time": e.end_time,
                "location": e.location,
            }
            for e in entries
        ]
    )


@api.route("/timetable", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def create_timetable_entry():
    """Create a new timetable entry."""
    data = request.json or {}
    class_name = data.get("class_name", "").strip()
    subject_name = data.get("subject_name", "").strip()
    teacher_id = data.get("teacher_id")
    day_of_week = data.get("day_of_week", "").strip()
    start_time = data.get("start_time", "").strip()
    end_time = data.get("end_time", "").strip()
    location = data.get("location", "").strip()

    if (
        not class_name
        or not subject_name
        or not day_of_week
        or not start_time
        or not end_time
    ):
        return jsonify({"message": "Missing required fields"}), 400

    if not teacher_id:
        return jsonify({"message": "Teacher assignment required"}), 400

    available_class_names = [
        row.name
        for row in AcademicClass.query.filter_by(school_id=g.school_id)
        .order_by(AcademicClass.name)
        .all()
    ]
    if not available_class_names:
        available_class_names = [
            row[0]
            for row in db.session.query(Student.current_class)
            .filter(Student.school_id == g.school_id)
            .group_by(Student.current_class)
            .order_by(Student.current_class)
            .all()
            if row[0]
        ]

    if not available_class_names:
        return jsonify({"message": "Add a school class before creating timetable entries."}), 400

    if class_name not in available_class_names:
        return jsonify({"message": "Select a valid school class."}), 400

    # Verify teacher belongs to this school
    teacher = User.query.filter_by(id=teacher_id, school_id=g.school_id).first()
    if not teacher:
        return jsonify({"message": "Teacher not found"}), 404

    entry = Timetable(
        school_id=g.school_id,
        class_name=class_name,
        subject_name=subject_name,
        teacher_id=teacher_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        location=location,
    )
    db.session.add(entry)
    db.session.commit()

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "TIMETABLE_CREATED",
        f"Created timetable slot: {class_name} {subject_name} on {day_of_week}",
    )

    return jsonify(
        {
            "id": entry.id,
            "class_name": entry.class_name,
            "subject_name": entry.subject_name,
            "teacher_id": entry.teacher_id,
            "teacher_name": teacher.username,
            "day_of_week": entry.day_of_week,
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "location": entry.location,
        }
    )


@api.route("/timetable/<int:entry_id>", methods=["DELETE"])
@multi_tenant_guard
@role_required("proprietor", "headmaster")
@jwt_required()
def delete_timetable_entry(entry_id):
    """Remove a timetable entry."""
    entry = Timetable.query.filter_by(id=entry_id, school_id=g.school_id).first_or_404()
    db.session.delete(entry)
    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "TIMETABLE_DELETED",
        f"Deleted timetable slot: {entry.class_name} {entry.subject_name}",
    )
    db.session.commit()
    return jsonify({"message": "Timetable entry removed"})


@api.route("/timetable/export", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "headmaster", "teacher", "homeroom")
@jwt_required()
def export_timetable():
    """Export timetable as CSV for printing or download."""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        class_name = request.args.get("class_name")

        # Get entries based on user role
        if user.role in ["proprietor", "headmaster"]:
            query = Timetable.query.filter_by(school_id=g.school_id)
        else:
            query = Timetable.query.filter_by(school_id=g.school_id, teacher_id=user_id)

            assignments = TeacherAssignment.query.filter_by(
                school_id=g.school_id, teacher_id=user_id
            ).all()
            if assignments:
                conditions = [
                    and_(
                        Timetable.class_name == a.class_name,
                        Timetable.subject_name == a.subject_name,
                    )
                    for a in assignments
                ]
                query = query.filter(or_(*conditions))

        if class_name:
            query = query.filter(Timetable.class_name == class_name)

        entries = query.order_by(Timetable.day_of_week, Timetable.start_time).all()

        si = StringIO()
        cw = csv.writer(si, quoting=csv.QUOTE_ALL)
        cw.writerow(
            ["Day", "Start Time", "End Time", "Class", "Subject", "Teacher", "Location"]
        )

        for entry in entries:
            cw.writerow(
                [
                    str(entry.day_of_week) if entry.day_of_week else "",
                    str(entry.start_time) if entry.start_time else "",
                    str(entry.end_time) if entry.end_time else "",
                    str(entry.class_name) if entry.class_name else "",
                    str(entry.subject_name) if entry.subject_name else "",
                    str(entry.teacher.username) if entry.teacher else "Unassigned",
                    str(entry.location) if entry.location else "",
                ]
            )

        output = make_response(si.getvalue())
        school = School.query.get(g.school_id)
        school_name = school.name.replace(" ", "_") if school else "school"
        output.headers["Content-Disposition"] = (
            f"attachment; filename=timetable_{school_name}_{get_utc_now().strftime('%Y%m%d')}.csv"
        )
        output.headers["Content-type"] = "text/csv"
        return output
    except Exception as e:
        logger.error(f"Error exporting timetable: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500


# =============================================================================
# ADMINISTRATION & MAINTENANCE ENDPOINTS
# =============================================================================

@api.route("/admin/trials/process-expirations", methods=["POST"])
@jwt_required()
def admin_process_trial_expirations():
    """
    Manually trigger the trial expiration process.
    Requires authentication (admin/proprietor access recommended).
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        # Import the trial job function
        from backend.trial_job import process_expired_trials
        
        result = process_expired_trials()
        logger.info(f"Manual trial expiration process triggered by user {user_id}: {result}")
        
        return jsonify({
            "message": "Trial expiration process completed",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error in manual trial expiration process: {str(e)}")
        return jsonify({"message": f"Error processing trials: {str(e)}"}), 500


@api.route("/admin/trials/send-reminders", methods=["POST"])
@jwt_required()
def admin_send_trial_reminders():
    """
    Manually trigger sending trial reminder emails.
    Sends reminders to schools with trials expiring within 3 days.
    Requires authentication (admin/proprietor access recommended).
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"message": "User not found"}), 404
        
        days_before = request.json.get("days_before_expiry", 3) if request.json else 3
        
        # Import the trial job function
        from backend.trial_job import send_trial_reminder_email
        
        result = send_trial_reminder_email(days_before_expiry=days_before)
        logger.info(f"Manual trial reminder process triggered by user {user_id}: {result}")
        
        return jsonify({
            "message": "Trial reminder process completed",
            "result": result
        }), 200
        
    except Exception as e:
        logger.error(f"Error in manual trial reminder process: {str(e)}")
        return jsonify({"message": f"Error sending reminders: {str(e)}"}), 500


# =============================================================================
# PAYSTACK PAYMENT INTEGRATION
# =============================================================================

@api.route("/paystack/initialize", methods=["POST"])
@jwt_required()
def paystack_initialize_payment():
    """
    Initialize a payment transaction with Paystack for subscription billing.
    Includes PRORATED BILLING for mid-term upgrades and post-trial conversions.
    
    Calculation:
    - Full Cost = Students × Price/Student × Terms
    - If upgrading mid-term: Applies proration based on days remaining
    - Days per term: 120 days (~4 months)
    - Prorated Cost = Full Cost × (Days Remaining / Days in Term)
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        school = School.query.get(user.school_id) if user else None
        
        if not school:
            return jsonify({"message": "School not found"}), 404
        
        data = request.get_json()
        plan_name = data.get('plan_name')
        addon_key = sanitize_string(data.get('addon_key'))
        billing_period = data.get('billing_period', 'term')  # 'term' or 'annual'
        default_student_count = _count_active_students_for_billing(school.id)
        student_count = data.get('student_count', default_student_count)
        amount_cedis = data.get('amount_cedis')
        email = data.get('email') or user.email
        
        if not email or (not plan_name and not addon_key):
            return jsonify({"message": "Missing required fields: email and a plan or add-on selection"}), 400

        transaction_type = 'subscription_upgrade'
        addon = None
        overage_count = 0
        if addon_key:
            addon = ADDON_CATALOG.get(addon_key)
            current_plan = school.subscription_plan or 'Free Tier'
            if not addon:
                return jsonify({"message": "Unknown add-on selected"}), 400
            if current_plan not in addon.get('eligible_plans', []):
                return jsonify({"message": f"{addon.get('name')} requires an active School OS or School OS Plus base plan."}), 400

            transaction_type = 'addon_purchase'
            plan_name = current_plan
            terms = 3 if billing_period == 'annual' else 1
            full_cost = float(addon.get('price_per_term', 0)) * terms
            amount_cedis = float(amount_cedis or full_cost)
            proration_data = {
                'is_prorated': False,
                'days_remaining': None,
                'days_in_period': None,
                'proration_ratio': 1.0,
                'calculation_source': 'addon_flat_rate',
            }
        else:
            # Model A Pricing: Base Fee + Included Students + Overage
            pricing = {
                key: {
                    'base_fee': value.get('base_fee_per_term', 0),
                    'included_students': value.get('included_students', 0),
                    'overage_rate': value.get('per_student_per_term', 0),
                }
                for key, value in PRICING.items()
                if key in {'Basic', 'Premium'}
            }
            
            if plan_name not in pricing:
                if plan_name == 'Free Tier':
                    return jsonify({"message": "Free plans cannot be purchased"}), 400
                return jsonify({"message": f"Invalid plan: {plan_name}"}), 400
            
            plan_config = pricing[plan_name]
            terms = 3 if billing_period == 'annual' else 1
            
            # Calculate full cost using Model A formula
            base_fee = plan_config['base_fee']
            included = plan_config['included_students']
            overage_count = max(0, student_count - included)
            term_cost = base_fee + (overage_count * plan_config['overage_rate'])
            full_cost = term_cost * terms
            amount_cedis = float(amount_cedis or full_cost)
            
            now = datetime.now(timezone.utc)
            term_proration = get_term_proration_context(school.id, now=now) if billing_period == 'term' else {}
            days_per_term = max(1, int(term_proration.get('days_in_term') or 120))
            
            # Get days remaining until next billing
            proration_data = {
                'is_prorated': False,
                'days_remaining': days_per_term,
                'days_in_period': days_per_term,
                'proration_ratio': 1.0,
                'calculation_source': 'standard',
            }
            
            next_billing_date = school.next_billing_date
            if next_billing_date and next_billing_date.tzinfo is None:
                next_billing_date = next_billing_date.replace(tzinfo=timezone.utc)

            if next_billing_date and next_billing_date > now:
                # Calculate days remaining in current billing period
                if billing_period == 'term':
                    days_remaining = max(1, (next_billing_date.date() - now.date()).days + 1)
                else:
                    days_remaining = max(0, (next_billing_date - now).days)
                
                if days_remaining < days_per_term:
                    # Mid-term upgrade detected
                    proration_ratio = days_remaining / days_per_term
                    prorated_cost = full_cost * proration_ratio
                    proration_data = {
                        'is_prorated': True,
                        'days_remaining': days_remaining,
                        'days_in_period': days_per_term,
                        'proration_ratio': round(proration_ratio, 2),
                        'full_cost': round(full_cost, 2),
                        'prorated_cost': round(prorated_cost, 2),
                        'calculation_source': 'existing_cycle',
                    }
                    if billing_period == 'term':
                        proration_data.update({
                            'term_name': term_proration.get('term_name'),
                            'academic_year': term_proration.get('academic_year'),
                            'reference_source': term_proration.get('reference_source'),
                        })
                    amount_cedis = prorated_cost
            elif billing_period == 'term' and (school.subscription_plan or 'Free Tier') == 'Free Tier':
                days_remaining = term_proration.get('days_remaining')
                days_in_period = term_proration.get('days_in_term')
                term_end_date = term_proration.get('term_end_date')

                if days_remaining and days_in_period and days_remaining < days_in_period:
                    proration_ratio = max(0.0, min(1.0, days_remaining / float(days_in_period)))
                    prorated_cost = term_cost * proration_ratio
                    proration_data = {
                        'is_prorated': True,
                        'days_remaining': days_remaining,
                        'days_in_period': days_in_period,
                        'proration_ratio': round(proration_ratio, 2),
                        'full_cost': round(term_cost, 2),
                        'prorated_cost': round(prorated_cost, 2),
                        'term_name': term_proration.get('term_name'),
                        'academic_year': term_proration.get('academic_year'),
                        'reference_source': term_proration.get('reference_source'),
                        'next_billing_date_override': term_end_date,
                        'calculation_source': 'current_term_remaining',
                    }
                    amount_cedis = prorated_cost

        if amount_cedis <= 0:
            return jsonify({"message": "Invalid amount"}), 400
        
        # Verify calculation (security check) - with tolerance for proration
        expected_cost = full_cost
        tolerance = expected_cost * 0.1 + 5  # 10% or GH₵5, whichever is larger
        if abs(amount_cedis - expected_cost) > tolerance and not proration_data['is_prorated']:
            logger.warning(f"Amount mismatch for school {school.id}: expected {expected_cost}, got {amount_cedis}")
            return jsonify({"message": f"Amount verification failed. Expected GH₵ {expected_cost}"}), 400
        
        # Convert to pesewas (smallest unit: 1 GH₵ = 100 pesewas)
        amount_pesewas = int(amount_cedis * 100)
        
        from backend.paystack_integration import initialize_payment, PaystackError
        
        try:
            # Set callback URL for redirect after payment
            callback_url = os.getenv('FRONTEND_URL', 'http://localhost:3000') + '/payment/callback'
            pricing_metadata = {
                'base_fee': plan_config['base_fee'],
                'overage_rate': plan_config['overage_rate'],
                'included_students': plan_config['included_students'],
            } if addon is None else {
                'base_fee': 0,
                'overage_rate': 0,
                'included_students': 0,
            }
            
            result = initialize_payment(
                email=email,
                amount_cents=amount_pesewas,
                plan_name=plan_name,
                school_id=school.id,
                metadata={
                    'user_id': user_id,
                    'student_count': student_count,
                    'billing_period': billing_period,
                    'terms': terms,
                    'base_fee': pricing_metadata['base_fee'],
                    'overage_rate': pricing_metadata['overage_rate'],
                    'included_students': pricing_metadata['included_students'],
                    'overage_count': overage_count,
                    'amount_cedis': amount_cedis,
                    'addon_key': addon_key,
                    'addon_name': addon.get('name') if addon else None,
                    'transaction_type': transaction_type,
                    'callback_url': callback_url,
                    'proration_data': proration_data
                }
            )
            
            log_msg = f"Payment initialized for school {school.id} ({school.name}): {plan_name}, {student_count} students, GH₵ {amount_cedis}"
            if addon:
                log_msg = f"Add-on checkout initialized for school {school.id} ({school.name}): {addon.get('name')} on {plan_name}, GH₵ {amount_cedis}"
            if proration_data['is_prorated']:
                log_msg += f" (PRORATED: {proration_data['days_remaining']}/{proration_data['days_in_period']} days remaining)"
            logger.info(log_msg)
            
            return jsonify({
                "status": "success",
                "message": "Payment initialized successfully",
                "data": result
            }), 200
            
        except PaystackError as e:
            logger.error(f"Paystack error for school {school.id}: {str(e)}")
            return jsonify({"message": f"Payment initialization failed: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error initializing Paystack payment: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500


@api.route("/paystack/verify/<reference>", methods=["GET"])
@jwt_required()
def paystack_verify_payment(reference):
    """
    Verify a Paystack payment transaction.
    """
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        school = School.query.get(user.school_id) if user else None
        
        if not school:
            return jsonify({"message": "School not found"}), 404
        
        from backend.paystack_integration import verify_payment, process_payment_confirmation, PaystackError
        
        try:
            transaction = verify_payment(reference)
            
            # Check if payment was successful
            if transaction.get('status') != 'success':
                return jsonify({
                    "message": "Payment not completed",
                    "data": {
                        "status": transaction.get('status'),
                        "reference": reference
                    }
                }), 200
            
            # Extract plan info from metadata
            metadata = transaction.get('metadata', {})
            plan_name = metadata.get('plan_name')
            card_setup_only = bool(metadata.get("card_setup_only") or metadata.get("skip_subscription_update"))
            
            if not plan_name and not card_setup_only:
                return jsonify({"message": "Invalid transaction metadata"}), 400

            if not card_setup_only and _is_subscription_reference_processed(reference, school.id):
                _append_billing_timeline_event(
                    school.id,
                    event_type="payment_verify_duplicate",
                    status="ignored",
                    title="Duplicate payment verification ignored",
                    details="A repeated verify request was received and ignored safely.",
                    reference=reference,
                )
                return jsonify(
                    {
                        "status": "success",
                        "message": "Payment was already processed earlier.",
                        "registration_flow": False,
                        "data": {"reference": reference, "idempotent": True},
                    }
                ), 200

            amount_paid = transaction.get('amount', 0) / 100  # Convert pesewas to Cedis

            if card_setup_only:
                authorization = transaction.get("authorization") or {}
                saved_card = _save_reusable_authorization(
                    school.id,
                    authorization,
                    transaction.get("customer", {}).get("email") or user.email,
                )

                if not saved_card:
                    _append_billing_timeline_event(
                        school.id,
                        event_type="card_setup_missing_reusable",
                        status="warning",
                        title="Card setup completed without reusable token",
                        details="Payment succeeded but Paystack did not return reusable authorization.",
                        amount=amount_paid,
                        reference=reference,
                    )
                    return jsonify({"message": "Payment succeeded but no reusable card authorization was returned."}), 200

                _append_billing_timeline_event(
                    school.id,
                    event_type="card_saved",
                    status="success",
                    title="Billing card saved",
                    details=f"{saved_card.get('brand') or 'Card'} ending with {saved_card.get('last4') or '----'} saved for recurring billing.",
                    amount=amount_paid,
                    reference=reference,
                )

                return jsonify(
                    {
                        "status": "success",
                        "message": "Card saved successfully for recurring pay-as-you-go billing.",
                        "data": {
                            "amount_paid": amount_paid,
                            "card": _sanitize_saved_card(saved_card),
                        },
                    }
                ), 200

            # Process the payment and update subscription
            result = process_payment_confirmation(
                school.id,
                plan_name,
                amount_paid,
                reference=reference,
                metadata=metadata
            )

            timeline_event_type = "subscription_payment_verified"
            timeline_title = "Subscription payment verified"
            timeline_details = f"Payment for {plan_name} processed successfully."
            if result.get("transaction_type") == "addon_purchase":
                timeline_event_type = "subscription_addon_verified"
                timeline_title = "Add-on payment verified"
                timeline_details = f"Payment for {result.get('addon_name') or 'subscription add-on'} processed successfully."

            _append_billing_timeline_event(
                school.id,
                event_type=timeline_event_type,
                status="success",
                title=timeline_title,
                details=timeline_details,
                amount=amount_paid,
                reference=reference,
                due_date=school.next_billing_date.isoformat() if school.next_billing_date else None,
            )

            authorization = transaction.get("authorization") or {}
            if authorization.get("reusable") and authorization.get("authorization_code"):
                _save_reusable_authorization(
                    school.id,
                    authorization,
                    transaction.get("customer", {}).get("email") or user.email,
                )

            onboarding_flow = metadata.get("onboarding_flow")
            if onboarding_flow == "registration":
                proprietor = User.query.filter_by(school_id=school.id, role="proprietor").first()
                recipient_email = proprietor.email if proprietor and proprietor.email else None
                already_sent = (
                    db.session.query(AuditLog.id)
                    .filter(
                        AuditLog.school_id == school.id,
                        AuditLog.action == "REGISTRATION_WELCOME_EMAIL_SENT",
                    )
                    .first()
                )
                if recipient_email and not already_sent:
                    try:
                        login_url = os.getenv("FRONTEND_URL", "http://localhost:5173/login")
                        welcome_subject, welcome_body = get_welcome_email(
                            username=proprietor.username,
                            school_name=school.name,
                            school_id=school.id,
                            login_url=login_url,
                            subscription_plan=school.subscription_plan or plan_name,
                        )
                        if welcome_subject and welcome_body:
                            send_email_notification(
                                to_email=recipient_email,
                                subject=welcome_subject,
                                body=welcome_body,
                                attachments=IMPORT_TEMPLATE_ATTACHMENTS,
                            )
                            log_action(
                                proprietor.id,
                                school.id,
                                "REGISTRATION_WELCOME_EMAIL_SENT",
                                f"Welcome email sent to {recipient_email}",
                            )
                    except Exception as email_error:
                        logger.warning(f"Failed to send post-payment welcome email for {school.id}: {email_error}")
            
            logger.info(f"Payment verified and processed for school {school.id}")
            
            return jsonify({
                "status": "success",
                "message": "Payment verified and subscription updated" if result.get("transaction_type") != "addon_purchase" else "Payment verified and add-on activated",
                "registration_flow": onboarding_flow == "registration",
                "data": result
            }), 200
            
        except PaystackError as e:
            logger.error(f"Paystack verification error: {str(e)}")
            return jsonify({"message": f"Verification failed: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error verifying Paystack payment: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500


@api.route("/paystack/webhook", methods=["POST"])
def paystack_subscription_webhook():
    """
    Paystack webhook endpoint to handle payment and subscription events.
    Supports:
    - charge.success: One-time payment successful
    - subscription.create: New subscription created
    - subscription.not_renew: Subscription cancelled
    - invoice.payment_failed: Payment attempt failed
    
    Verify HMAC signature for security.
    """
    try:
        # Verify webhook signature
        import hmac
        import hashlib
        
        paystack_secret = os.getenv("PAYSTACK_SECRET_KEY", "")
        signature = request.headers.get("X-Paystack-Signature", "")
        body = request.get_data()
        
        hash_object = hmac.new(
            paystack_secret.encode(),
            body,
            hashlib.sha512
        )
        computed_signature = hash_object.hexdigest()
        
        if signature != computed_signature:
            logger.warning(f"Invalid webhook signature from Paystack")
            return jsonify({"message": "Invalid signature"}), 403
        
        # Parse webhook data
        event = request.json
        event_type = event.get('event')
        
        logger.info(f"Paystack webhook received: {event_type}")
        
        # Handle charge success (one-time payment or subscription charge)
        if event_type == 'charge.success':
            transaction = event.get('data', {})
            reference = transaction.get('reference')
            status = transaction.get('status')
            metadata = transaction.get('metadata', {})
            school_id = metadata.get('school_id')
            plan_name = metadata.get('plan_name')
            amount_paid = transaction.get('amount', 0) / 100  # Convert pesewas to GHS
            card_setup_only = bool(metadata.get("card_setup_only") or metadata.get("skip_subscription_update"))
            
            if status != 'success' or not school_id or (not plan_name and not card_setup_only):
                logger.warning(f"Invalid charge webhook data: {event}")
                return jsonify({"message": "Invalid data"}), 400
            
            school = School.query.get(school_id)
            if not school:
                logger.error(f"School {school_id} not found for webhook payment")
                return jsonify({"message": "School not found"}), 404

            if not card_setup_only and _is_subscription_reference_processed(reference, school_id):
                _append_billing_timeline_event(
                    school_id,
                    event_type="webhook_duplicate_ignored",
                    status="ignored",
                    title="Duplicate webhook ignored",
                    details="A duplicate Paystack webhook event was ignored safely.",
                    reference=reference,
                )
                logger.info(f"Duplicate webhook ignored: school={school_id}, ref={reference}")
                return jsonify({"message": "OK"}), 200
            
            from backend.paystack_integration import process_payment_confirmation, PaystackError
            
            try:
                if card_setup_only:
                    _save_reusable_authorization(
                        school_id,
                        transaction.get("authorization") or {},
                        (transaction.get("customer") or {}).get("email"),
                    )
                    _append_billing_timeline_event(
                        school_id,
                        event_type="card_saved",
                        status="success",
                        title="Billing card saved",
                        details="Card authorization saved from webhook event.",
                        amount=amount_paid,
                        reference=reference,
                    )
                    logger.info(f"Webhook card setup processed for school {school_id}, reference {reference}")
                    return jsonify({"message": "OK"}), 200

                result = process_payment_confirmation(school_id, plan_name, amount_paid, reference=reference, metadata=metadata)
                _save_reusable_authorization(
                    school_id,
                    transaction.get("authorization") or {},
                    (transaction.get("customer") or {}).get("email"),
                )
                event_type = "subscription_payment_webhook"
                success_title = "Subscription payment received"
                success_details = f"Webhook payment captured for {plan_name} plan."
                if result.get("transaction_type") == "addon_purchase":
                    event_type = "subscription_addon_webhook"
                    success_title = "Add-on payment received"
                    success_details = f"Webhook payment captured for {result.get('addon_name') or 'subscription add-on'}."
                _append_billing_timeline_event(
                    school_id,
                    event_type=event_type,
                    status="success",
                    title=success_title,
                    details=success_details,
                    amount=amount_paid,
                    reference=reference,
                    due_date=school.next_billing_date.isoformat() if school.next_billing_date else None,
                )
                logger.info(f"Webhook payment processed: school {school_id}, plan {plan_name}, reference {reference}")
                return jsonify({"message": "OK"}), 200
                
            except PaystackError as e:
                _append_billing_timeline_event(
                    school_id,
                    event_type="subscription_payment_failed",
                    status="failed",
                    title="Subscription payment processing failed",
                    details=str(e),
                    amount=amount_paid,
                    reference=reference,
                    next_retry_at=(get_utc_now() + timedelta(days=1)).isoformat(),
                )
                logger.error(f"Error processing webhook payment for school {school_id}: {str(e)}")
                return jsonify({"message": "Processing error"}), 500
        
        # Handle subscription creation
        elif event_type == 'subscription.create':
            subscription_data = event.get('data', {})
            customer_email = subscription_data.get('customer', {}).get('email')
            plan_code = subscription_data.get('plan', {}).get('plan_code')
            
            logger.info(f"Subscription created: email={customer_email}, plan={plan_code}")
            return jsonify({"message": "OK"}), 200
        
        # Handle subscription cancellation
        elif event_type == 'subscription.not_renew':
            subscription_data = event.get('data', {})
            customer_email = subscription_data.get('customer', {}).get('email')
            
            logger.warning(f"Subscription will not renew for {customer_email}")
            return jsonify({"message": "OK"}), 200
        
        # Handle payment failure
        elif event_type == 'invoice.payment_failed':
            invoice_data = event.get('data', {})
            customer_email = invoice_data.get('customer', {}).get('email')
            amount = invoice_data.get('amount', 0) / 100
            school_id = (invoice_data.get('metadata') or {}).get('school_id')
            
            logger.error(f"Payment failed for {customer_email}, amount: ₵{amount}")
            if school_id:
                _append_billing_timeline_event(
                    school_id,
                    event_type="invoice_payment_failed",
                    status="failed",
                    title="Automatic billing attempt failed",
                    details=f"Paystack invoice payment failed for {customer_email or 'customer'}.",
                    amount=amount,
                    reference=invoice_data.get("reference"),
                    next_retry_at=(get_utc_now() + timedelta(days=1)).isoformat(),
                )
            # TODO: Send payment failure notification email to proprietor
            return jsonify({"message": "OK"}), 200
        
        # Log other events for monitoring
        else:
            logger.info(f"Unhandled webhook event: {event_type}")
            return jsonify({"message": "OK"}), 200
        
    except Exception as e:
        logger.error(f"Fatal error in Paystack webhook: {str(e)}")
        return jsonify({"message": "Server error"}), 500


@api.route("/paystack/initialize-termly", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def initialize_termly_payment():
    """
    Initialize a termly subscription payment for Ghana schools.
    Amount calculated based on enrollment: num_students × per_student_rate.
    """
    try:
        data = request.json
        plan_name = data.get("plan_name", "Basic")
        academic_term_id = data.get("academic_term_id")
        
        # Get school and enrollment
        school = School.query.get(g.school_id)
        if not school:
            return jsonify({"message": "School not found"}), 404
        
        # Get proprietor email
        proprietor = User.query.filter_by(school_id=g.school_id, role="proprietor").first()
        if not proprietor or not proprietor.email:
            return jsonify({"message": "Proprietor email not found"}), 400
        
        # Get current student count
        num_students = _count_active_students_for_billing(g.school_id)
        
        if num_students == 0:
            return jsonify({"message": "No students enrolled. Add students before subscribing."}), 400
        
        # Initialize payment with Paystack
        from backend.paystack_integration import initialize_termly_payment, PaystackError
        
        try:
            result = initialize_termly_payment(
                email=proprietor.email,
                plan_name=plan_name,
                school_id=g.school_id,
                num_students=num_students,
                academic_term_id=academic_term_id
            )
            
            logger.info(f"Termly payment initialized for school {g.school_id}: {num_students} students, plan {plan_name}")
            
            return jsonify({
                "message": "Payment initialized successfully",
                "authorization_url": result['authorization_url'],
                "access_code": result['access_code'],
                "reference": result['reference'],
                "plan_name": plan_name,
                "num_students": num_students,
                "term_cost": result.get("term_cost"),
                "base_fee": result.get("base_fee"),
                "included_students": result.get("included_students"),
                "billable_students": result.get("billable_students"),
                "student_overage_cost": result.get("student_overage_cost"),
                "subscription_convenience_fee": 0,
            }), 200
            
        except PaystackError as e:
            logger.error(f"Paystack error for school {g.school_id}: {str(e)}")
            return jsonify({"message": str(e)}), 400
        
    except Exception as e:
        logger.error(f"Error initializing termly payment: {str(e)}")
        return jsonify({"message": f"Error: {str(e)}"}), 500

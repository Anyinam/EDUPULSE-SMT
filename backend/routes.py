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
from urllib.parse import quote
from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO

from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, stream_with_context
from flask_jwt_extended import (
    create_access_token,
    decode_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from backend.api.models import (
    VALID_GRADES,
    AcademicClass,
    AcademicTerm,
    AcademicWorkLog,
    AuditLog,
    ClassGradingPolicy,
    DailyLessonPhase,
    ExamPaper,
    Inventory,
    LedgerEntry,
    LessonNote,
    LiveChatMessage,
    LiveChatSession,
    LoginAttempt,
    PasswordReset,
    Payment,
    PaystackSubAccount,
    PlatformSetting,
    PlatformUser,
    QuestionPool,
    ReportCard,
    ReportCardStatus,
    School,
    SchoolSettings,
    Student,
    StudentAssignment,
    StudentGrade,
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
from backend.report_card_parser import parse_report_card_image_bytes
from backend.settings import (
    AUTH_LOCKOUT_ATTEMPTS,
    AUTH_LOCKOUT_DURATION_MIN,
    AUTH_LOCKOUT_WINDOW_MIN,
    MFA_REQUIRED,
)
from backend.subscription_features import (
    FEATURE_MATRIX_DISPLAY,
    PLAN_FEATURES,
    PRICING,
    calculate_annual_cost,
    calculate_term_cost,
    can_access_report_template,
    get_all_accessible_templates,
    get_feature_level,
    get_plan_limit,
    get_term_cost_breakdown,
    has_feature,
)
from backend.lesson_note_ai import generate_ai_lesson_note_score, generate_quick_feedback
from backend.exam_ai import generate_exam_questions
from backend.email_templates import (
    get_welcome_email, 
    get_password_reset_email, 
    get_staff_welcome_email,
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
    get_billing_visibility,
    lock_pricing_version,
    sync_student_meter,
)
from backend.utils import (
    calculate_academic_health,
    generate_descriptive_analysis,
    get_utc_now,
    send_email_notification,
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
            and_(Student.is_present == True, Student.feeding_paid == False),
        ),
    ).order_by(Student.total_tuition_owed.desc(), Student.name.asc())
    if candidate_limit is not None:
        candidate_query = candidate_query.limit(candidate_limit)
    candidate_students = candidate_query.all()

    flagged_students = []

    for student in candidate_students:
        reasons = []
        recommended_actions = []
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
        feeding_issue = bool(student.is_present and not student.feeding_paid)
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

        if student.is_present and not student.feeding_paid:
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
                "feeding_paid": bool(student.feeding_paid),
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


def _lock_school_for_capacity_check(school_id):
    bind = db.session.get_bind()
    dialect_name = bind.dialect.name if bind and bind.dialect else ""

    if dialect_name == "sqlite":
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


def calculate_prorated_admission_charge(school, num_new_students, effective_plan):
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
    
    # Get current (pre-admission) student count with Active status
    current_active_students = Student.query.filter_by(
        school_id=school.id,
        status='Active'
    ).count()
    
    # Post-admission count
    new_total = current_active_students + num_new_students
    
    # Check if new students push over included threshold
    old_billable = max(0, current_active_students - included_students)
    new_billable = max(0, new_total - included_students)
    students_over_included = max(0, new_billable - old_billable)
    
    if students_over_included <= 0:
        # All new students fall within included threshold
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
            details=f"Invoice {invoice_number}: {students_over_included} student(s) above included threshold (pro-rated).",
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
        return jsonify({"message": "WhatsApp messaging is available for Premium plan only."}), 403
    
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


def get_effective_plan(school):
    """Returns active plan, honoring trial overrides when present."""
    if school and school.trial_plan and school.trial_end_date:
        trial_end = school.trial_end_date
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < trial_end:
            return school.trial_plan
    return school.subscription_plan if school else "Free Tier"


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


@api.route("/public/help-content", methods=["GET"])
def get_public_help_content():
    """Get global login FAQ/tutorial content for all tenants."""
    setting = PlatformSetting.query.filter_by(setting_key="login_help_content").first()
    if not setting:
        return jsonify(DEFAULT_LOGIN_HELP_CONTENT)
    return jsonify(_normalize_help_content(setting.setting_value))


@api.route("/platform/help-content", methods=["GET"])
def get_platform_help_content():
    """Get global help content for platform owner editing."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

    setting = PlatformSetting.query.filter_by(setting_key="login_help_content").first()
    if not setting:
        return jsonify(DEFAULT_LOGIN_HELP_CONTENT)
    return jsonify(_normalize_help_content(setting.setting_value))


@api.route("/platform/help-content", methods=["PUT"])
def update_platform_help_content():
    """Update global login FAQ/tutorial content (platform owner only)."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

    data = request.get_json(silent=True) or {}
    normalized = _normalize_help_content(
        {
            "faqs": data.get("faqs", []),
            "tutorials": data.get("tutorials", []),
        }
    )

    setting = PlatformSetting.query.filter_by(setting_key="login_help_content").first()
    if not setting:
        setting = PlatformSetting(setting_key="login_help_content", setting_value=normalized)
        db.session.add(setting)
    else:
        setting.setting_value = normalized

    db.session.commit()
    return jsonify({"message": "Global help content updated successfully.", **normalized})


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
    """Add new platform admin user (owner key required)."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

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
def remove_platform_user(user_id):
    """Remove platform admin user (owner key required)."""
    if not _is_platform_owner_request():
        return jsonify({"message": "Access denied: Platform owner credentials required."}), 403

    try:
        user = PlatformUser.query.get(user_id)
        if not user:
            return jsonify({"message": "User not found"}), 404

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
                    "user_id": row.user_id,
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

    incoming_globals = merged.get(GLOBAL_REPORT_SETTINGS_KEY)
    if isinstance(incoming_globals, dict):
        existing_globals.update(incoming_globals)

    if existing_globals:
        merged[GLOBAL_REPORT_SETTINGS_KEY] = existing_globals

    return merged


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


def _get_frontend_login_url():
    configured_url = (os.getenv("FRONTEND_URL") or "").strip()
    origin_url = (request.headers.get("Origin") or "").strip()

    base_url = configured_url
    if origin_url and (
        not base_url
        or "localhost" in base_url.lower()
        or "127.0.0.1" in base_url.lower()
    ):
        base_url = origin_url

    if not base_url:
        base_url = request.host_url.rstrip("/")

    return f"{base_url.rstrip('/')}/login"


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
            or "support@edupulse.com"
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
            send_email_notification(user.email, template_subject, template_body)
            email_sent = True
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
    selected_plan = sanitize_string(data.get("selectedPlan", "Free"))  # Get selected plan, default to Free
    client_ip = get_client_ip()

    if not terms_accepted:
        return jsonify({"message": "Terms of Service must be accepted"}), 400
    if not policy_accepted:
        return jsonify({"message": "Privacy and Data Retention policies must be accepted"}), 400
    
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
                login_url = os.getenv("FRONTEND_URL", "http://localhost:5173/login")
                subscription_plan = subscription_plan_override or new_school.subscription_plan or "Free Tier"
                welcome_subject, welcome_body = get_welcome_email(
                    username=username,
                    school_name=school_name,
                    school_id=school_id,
                    login_url=login_url,
                    subscription_plan=subscription_plan,
                )
                if welcome_subject and welcome_body:
                    send_email_notification(
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
        callback_url = os.getenv("FRONTEND_URL", "http://localhost:3000") + "/payment/callback?onboarding=registration"

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

        return jsonify(
            {
                "school_id": school.id,
                "school_name": school.name,
                "support_email": school.school_email or "support@edupulse.com",
                "support_phone": school.school_phone or "+233 552 141 384",
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
        school = School.query.get(g.school_id)
        if school.subscription_plan != "Premium":
            return (
                jsonify(
                    {"message": "HTML template uploads require Premium subscription."}
                ),
                403,
            )

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

    return jsonify(
        {
            "message": "Report template uploaded",
            "report_template_id": settings.report_template_id,
            "report_template_config": settings.report_template_config,
        }
    )


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
            db.session.query(Student.class_name)
            .filter(Student.school_id == g.school_id)
            .group_by(Student.class_name)
            .order_by(Student.class_name)
            .all()
        )

        class_names = [c[0] for c in student_classes if c[0]]

        if class_names:
            return jsonify([{"name": c, "class_name": c} for c in class_names])

        # Final fallback to default classes
        default_classes = ["JHS 1", "JHS 2", "JHS 3", "Class 6", "Class 5"]
        return jsonify([{"name": c, "class_name": c} for c in default_classes])

    except Exception as e:
        print(f"Error fetching classes: {e}", flush=True)
        default_classes = ["JHS 1", "JHS 2", "JHS 3", "Class 6", "Class 5"]
        return jsonify([{"name": c, "class_name": c} for c in default_classes])


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

    results = []
    for s in students:
        payment_method = None
        if s.feeding_paid:
            last_payment = (
                Payment.query.filter_by(
                    student_id=s.id,
                    school_id=g.school_id,
                    payment_type="Feeding",
                    status="Confirmed",
                )
                .order_by(Payment.date_paid.desc())
                .first()
            )
            if last_payment:
                payment_method = last_payment.method

        results.append(
            {
                "id": s.id,
                "name": s.name,
                "student_code": s.student_code,
                "current_class": s.current_class,
                "parent_email": s.parent_email,
                "feeding_paid": s.feeding_paid,
                "payment_method": payment_method,
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

    Primary flow: Paystack virtual subaccounts per payment type.
    - Parents pay to virtual account / shortcode for Tuition, Feeding, etc.
    - Paystack auto-detects payment type from the virtual route used.

    Backward compatibility: legacy reference codes are still returned.
    """
    from backend.utils import generate_all_payment_codes

    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    school = School.query.filter_by(id=g.school_id).first()

    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None

    # Get school fees configuration
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    fees_config = {
        "tuition_fee": settings.tuition_fee if settings else 0.0,
        "feeding_fee": settings.feeding_fee if settings else 0.0,
        "uniform_fee": settings.uniform_fee if settings else 0.0,
        "transport_fee": settings.transport_fee if settings else 0.0,
        "terminal_report_fee": settings.terminal_report_fee if settings else 0.0,
        "other_fees": settings.other_fees if settings else {},
    }

    # Generate payment codes based on student code
    payment_codes = generate_all_payment_codes(student.student_code, fees_config)

    # Virtual routing map by payment type (Paystack fee route accounts)
    subaccounts = PaystackSubAccount.query.filter_by(
        school_id=g.school_id, is_active=True
    ).all()
    subaccount_map = {
        (entry.payment_type or "").strip(): entry for entry in subaccounts
    }

    # Format for frontend display
    codes_list = []
    for fee_type, code in payment_codes.items():
        base_amount = 0.0
        if fee_type == "Tuition":
            # Tuition now includes terminal report fee
            base_amount = fees_config["tuition_fee"] + fees_config["terminal_report_fee"]
        elif fee_type == "Feeding":
            base_amount = fees_config["feeding_fee"]
        elif fee_type == "Uniform":
            base_amount = fees_config["uniform_fee"]
        elif fee_type == "Transport":
            base_amount = fees_config["transport_fee"]
        else:
            base_amount = fees_config["other_fees"].get(fee_type, 0.0)

        # Scholarship overrides
        if student.is_on_scholarship:
            if fee_type == "Tuition" and student.scholarship_covers_tuition:
                base_amount = 0.0
            if fee_type == "Feeding" and student.scholarship_covers_feeding:
                base_amount = 0.0
        
        # Calculate convenience fee (default 2.0% or from fee route account)
        route = subaccount_map.get(fee_type)
        convenience_fee_percent = route.percentage_charge if route else DEFAULT_PAYMENT_CONVENIENCE_FEE_PERCENT
        convenience_fee_amount = base_amount * (convenience_fee_percent / 100)
        total_amount = base_amount + convenience_fee_amount

        # Display name for tuition includes terminal report reference
        display_name = fee_type
        if fee_type == "Tuition":
            display_name = "Tuition + Terminal Report"

        virtual_bank_account = route.virtual_bank_account if route else None
        virtual_bank_name = route.virtual_bank_name if route else None
        momo_shortcode = route.momo_shortcode if route else None
        has_virtual_route = bool(virtual_bank_account or momo_shortcode)

        codes_list.append(
            {
                "fee_type": display_name,
                "code": code,
                "reference_code": code,
                "base_amount": base_amount,
                "cash_amount": round(base_amount, 2),
                "convenience_fee_percent": convenience_fee_percent,
                "convenience_fee_amount": round(convenience_fee_amount, 2),
                "total_amount": round(total_amount, 2),
                "amount": round(total_amount, 2),
                "virtual_bank_account": virtual_bank_account,
                "virtual_bank_name": virtual_bank_name,
                "momo_shortcode": momo_shortcode,
                "subaccount_code": route.subaccount_code if route else None,
                "has_virtual_route": has_virtual_route,
                "is_scholarship_fee": bool(
                    (fee_type == "Tuition" and student.scholarship_covers_tuition)
                    or (fee_type == "Feeding" and student.scholarship_covers_feeding)
                ),
                "instructions": (
                    f"Pay GH₵ {base_amount:.2f} school fee + {convenience_fee_percent}% convenience fee (GH₵ {convenience_fee_amount:.2f}) = GH₵ {total_amount:.2f} total by virtual route for {display_name}. "
                    + (
                        "Use the dedicated Paystack virtual account for automatic processing. "
                        if has_virtual_route
                        else "Virtual route pending setup. Pay cash at the school office or use the school's approved manual payment instructions. "
                    )
                    + f"Reference code ({code}) remains optional backup. Cash at the school office remains GH₵ {base_amount:.2f} without the convenience fee."
                ),
            }
        )

    log_action(
        actor_id,
        g.school_id,
        "PAYMENT_CODES_GENERATED",
        json.dumps(
            {
                "student_id": student.id,
                "student_code": student.student_code,
                "student_class": student.current_class,
                "routes_count": len(codes_list),
                "has_virtual_route": any(
                    bool(code.get("has_virtual_route")) for code in codes_list
                ),
                "ip": request.remote_addr,
            }
        ),
    )

    return jsonify(
        {
            "student_id": student.id,
            "student_name": student.name,
            "student_code": student.student_code,
            "class": student.current_class,
            "parent_name": student.parent_name,
            "parent_phone": student.parent_phone,
            "parent_email": student.parent_email,
            "payment_codes": codes_list,
            "note": "Use the payment-type virtual account or shortcode where available. Virtual-route totals include the convenience fee. If a virtual route is unavailable, parents may pay cash at the school office or use the school's approved manual payment instructions.",
        }
    )


@api.route("/students", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "teacher", "homeroom")
@jwt_required()
def get_students():
    """Fetch all students - accessible by proprietor, finance, and teaching staff."""
    try:
        students = (
            Student.query.filter_by(school_id=g.school_id).order_by(Student.name).all()
        )
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
                    "feeding_paid": s.feeding_paid,
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
        db.session.commit()
        return response
    except Exception as e:
        return jsonify({"message": "Error retrieving students", "error": str(e)}), 500


@api.route("/students/<int:student_id>/payments", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor", "finance", "headmaster", "homeroom", "teacher")
@jwt_required()
def get_student_payments(student_id):
    """Fetch payment history for a specific student."""
    try:
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
            convenience_fee_percent = DEFAULT_PAYMENT_CONVENIENCE_FEE_PERCENT
            gross_amount = float(payment.amount or 0)
            base_amount = round(
                gross_amount / (1 + (convenience_fee_percent / 100)), 2
            ) if gross_amount > 0 else 0.0
            convenience_fee_amount = round(gross_amount - base_amount, 2)

            payment_list.append(
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "base_amount": base_amount,
                    "convenience_fee_percent": convenience_fee_percent,
                    "convenience_fee_amount": convenience_fee_amount,
                    "total_amount": gross_amount,
                    "payment_type": payment.payment_type,
                    "method": payment.method,
                    "status": payment.status,
                    "date_paid": payment.date_paid.strftime("%Y-%m-%d %H:%M"),
                    "reference_id": payment.reference_id,
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


@api.route("/homeroom/attendance", methods=["POST"])
@multi_tenant_guard
@role_required("teacher", "headmaster", "proprietor")
@jwt_required()
def update_attendance():
    """Updates attendance status for a student."""
    data = request.json
    student_id = data.get("student_id")
    status = data.get("status")  # True/False

    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    student.is_present = status
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

    updated_count = 0
    for record in attendance_records:
        student_id = record.get("student_id")
        status = record.get("status")

        if student_id is None or status is None:
            continue

        student = Student.query.filter_by(id=student_id, school_id=g.school_id).first()
        if student:
            student.is_present = status
            updated_count += 1

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

    updated_count = 0
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

    return jsonify(
        {
            "message": "Report card saved successfully",
            "report_id": report.id,
            "report": report.to_dict(),
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

    return None, None, None


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
    subaccount_data = payload.get("subaccount") or {}
    subaccount_code = subaccount_data.get("subaccount_code") if isinstance(subaccount_data, dict) else None

    actual_payment_type = None
    route_mismatch = False
    if subaccount_code:
        dva_route = PaystackSubAccount.query.filter_by(
            school_id=student.school_id,
            subaccount_code=subaccount_code,
            is_active=True,
        ).first()
        if dva_route:
            actual_payment_type = dva_route.payment_type
            if reference_payment_type != actual_payment_type:
                route_mismatch = True

    payment_type = actual_payment_type or reference_payment_type

    payment = Payment(
        student_id=student.id,
        school_id=student.school_id,
        amount=amount,
        payment_type=payment_type,
        method="Paystack_Payment",
        reference_id=tx_ref,
        status="Confirmed",
        payment_category=payment_category or {},
    )
    db.session.add(payment)

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
    if subaccount_code:
        ledger_metadata["subaccount"] = {
            "code": subaccount_code,
            "settlement_amount": subaccount_data.get("settlement_amount", 0) / 100.0,
            "commission": subaccount_data.get("subaccount_share", 0) / 100.0,
        }
    if route_mismatch:
        ledger_metadata["routing_mismatch"] = {
            "detected": True,
            "reference_indicated": reference_payment_type,
            "actual_account_used": actual_payment_type,
            "resolution": "Used actual account type (DVA routing is authoritative)",
            "requires_review": True,
        }

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

    if _should_inject_failpoint(metadata, "finance_payment_before_commit"):
        db.session.rollback()
        raise RuntimeError("Injected failpoint: finance_payment_before_commit")

    log_action(
        user_id=None,
        school_id=student.school_id,
        action="PAYSTACK_PAYMENT_AUTO",
        details=f"Paystack payment: GH₵{amount:.2f} for {student.name} ({payment_type}, ref={tx_ref})",
    )

    db.session.commit()
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
    metadata = transaction.get("metadata") or {}
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

        process_payment_confirmation(
            school_id,
            plan_name,
            amount_paid,
            reference=reference,
            metadata=metadata,
        )
        _append_billing_timeline_event(
            school_id,
            event_type="subscription_payment_recovered",
            status="success",
            title="Subscription payment recovered",
            details=f"Recovered missing subscription payment for {plan_name} from Paystack reconciliation.",
            amount=amount_paid,
            reference=reference,
        )
        return "recovered"

    result, _status_code = _record_paystack_finance_payment(
        transaction,
        event="charge.success.reconciled",
        school_id_scope=school_id_scope,
    )
    return result.get("status") or "ignored"


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

            if outcome in {"recovered", "recorded"}:
                summary["recovered"] += 1
                summary["references"].append(reference)
            elif outcome == "duplicate":
                summary["duplicate"] += 1
            elif outcome == "unmapped":
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
        body, status_code = _record_paystack_finance_payment(payload, event=event)
        return jsonify(body), status_code
    except Exception as exc:
        db.session.rollback()
        logger.error("Paystack finance webhook failed for ref=%s: %s", payload.get("reference"), exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


# --- PAYSTACK FEE ROUTE ACCOUNT MANAGEMENT ---

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
        
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") is True:
            return result.get("data"), None
        else:
            return None, result.get("message", "Paystack API error")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Paystack API call failed: {e}")
        return None, str(e)


def _get_paystack_secret_key_mode():
    secret_key = (os.getenv("PAYSTACK_SECRET_KEY") or "").strip().lower()
    if secret_key.startswith("sk_test_"):
        return "test"
    if secret_key.startswith("sk_live_"):
        return "live"
    if secret_key:
        return "unknown"
    return "unconfigured"


def _get_subaccount_for_payment(school_id, payment_type):
    """Resolve a valid Paystack split route code for a given payment type.

    Dedicated virtual account identifiers are stored in the same table for routing,
    but must not be sent as `subaccount` during transaction initialization.
    """
    subaccount = PaystackSubAccount.query.filter_by(
        school_id=school_id,
        payment_type=payment_type,
        is_active=True
    ).first()
    if not subaccount or not subaccount.subaccount_code:
        return None

    code = (subaccount.subaccount_code or "").strip()
    return code if code.startswith("ACCT_") else None


def _resolve_or_create_paystack_customer_for_school(school):
    """Resolve or create a single Paystack customer profile for a school.

    Returns: (customer_code, email, source, error)
    """
    if not school:
        return None, None, None, "School not found"

    school_email = sanitize_string(school.school_email or "")
    fallback_email = f"{(school.id or 'school').lower()}@edupulse.local"
    email = school_email or fallback_email

    first_name = sanitize_string((school.name or "School").split(" ")[0]) or "School"
    last_name = "Admin"
    phone = sanitize_string(school.school_phone or "")

    existing_customer, fetch_error = _call_paystack_api(f"/customer/{quote(email, safe='')}")
    if isinstance(existing_customer, dict) and existing_customer.get("customer_code"):
        return existing_customer.get("customer_code"), email, "existing", None

    create_payload = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
    }
    if phone:
        create_payload["phone"] = phone

    created_customer, create_error = _call_paystack_api("/customer", method="POST", data=create_payload)
    if create_error:
        logger.error(
            f"Paystack school-customer resolve/create failed for school {school.id}: "
            f"fetch_error={fetch_error}, create_error={create_error}"
        )
        return None, email, None, create_error

    customer_code = created_customer.get("customer_code") if isinstance(created_customer, dict) else None
    if not customer_code:
        return None, email, None, "Customer created but customer_code missing in Paystack response"

    return customer_code, email, "created", None


@api.route("/proprietor/paystack/subaccounts", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_paystack_subaccounts():
    """List all Paystack fee route accounts for the school."""
    subaccounts = PaystackSubAccount.query.filter_by(
        school_id=g.school_id
    ).order_by(PaystackSubAccount.payment_type).all()
    
    return jsonify([s.to_dict() for s in subaccounts])


@api.route("/proprietor/paystack/subaccounts/create", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def create_paystack_subaccount():
    """Create a Paystack dedicated virtual account for a specific payment type.

    Uses Paystack `/dedicated_account` so each payment type gets a dedicated
    virtual account route (fee route account). This route is then shared with parents/guardians.
    """
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    
    payment_type = sanitize_string(data.get("payment_type"))
    percentage_charge = data.get("percentage_charge", DEFAULT_PAYMENT_CONVENIENCE_FEE_PERCENT)  # Default 2.0% platform fee
    customer_code = sanitize_string(data.get("customer_code") or data.get("customer"))
    preferred_bank = sanitize_string(data.get("preferred_bank") or data.get("provider"))
    key_mode = _get_paystack_secret_key_mode()
    
    # Validate required fields
    if not payment_type or payment_type not in ["Tuition", "Feeding", "Uniform", "Transport", "Other"]:
        return jsonify({"error": "Invalid payment_type. Must be: Tuition, Feeding, Uniform, Transport, or Other"}), 400

    if not preferred_bank:
        preferred_bank = "titan-paystack"
    
    # Get school for naming and audit context
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"error": "School not found"}), 404

    if not customer_code:
        resolved_customer_code, _, _, customer_error = _resolve_or_create_paystack_customer_for_school(school)
        if customer_error or not resolved_customer_code:
            customer_code = None
        else:
            customer_code = resolved_customer_code
    
    # Check if fee route account already exists for this payment type
    existing = PaystackSubAccount.query.filter_by(
        school_id=g.school_id,
        payment_type=payment_type
    ).first()
    
    if existing and existing.is_active:
        return jsonify({"error": f"Active fee route account already exists for {payment_type}"}), 409
    
    business_name = f"{school.name} - {payment_type}"

    # Call Paystack API to create dedicated virtual account
    paystack_data = {
        "customer": customer_code,
        "preferred_bank": preferred_bank,
    }

    result, error = _call_paystack_api("/dedicated_account", method="POST", data=paystack_data)
    
    if error:
        logger.warning(f"Paystack dedicated account creation unavailable, using manual fallback route: {error}")

        fallback_code = f"MANUAL_{payment_type[:3].upper()}_{school.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        fallback_route = PaystackSubAccount(
            school_id=g.school_id,
            payment_type=payment_type,
            subaccount_code=fallback_code,
            business_name=business_name,
            virtual_bank_account=None,
            virtual_bank_name=school.bank_name or "School Bank Account",
            momo_shortcode=None,
            momo_provider=preferred_bank,
            percentage_charge=percentage_charge,
            is_active=True,
            is_verified=False,
            created_by=user_id,
        )

        db.session.add(fallback_route)
        log_action(
            user_id,
            g.school_id,
            "PAYSTACK_ROUTE_FALLBACK_CREATED",
            f"Created manual fallback payment route for {payment_type} while gateway was unavailable.",
        )
        db.session.commit()

        fallback_message = "Payment route created. Virtual account setup is pending; parents can use the school's saved bank account meanwhile."
        if key_mode == "test":
            fallback_message = "Payment route saved in fallback mode. Paystack test keys do not provide a usable live virtual account number here, so parents should pay cash at the school office or use the school's approved manual instructions until live keys are configured."

        return jsonify({
            "message": fallback_message,
            "subaccount": fallback_route.to_dict(),
            "fee_route_account": fallback_route.to_dict(),
            "mode": "manual_fallback",
            "gateway_mode": key_mode,
        }), 201

    account_data = result.get("dedicated_account") if isinstance(result, dict) and isinstance(result.get("dedicated_account"), dict) else result
    if not isinstance(account_data, dict):
        account_data = {}

    assigned_bank = account_data.get("assigned_bank") or {}
    account_number = account_data.get("account_number") or account_data.get("account")
    bank_name = account_data.get("bank_name") or account_data.get("bank") or assigned_bank.get("name")
    dedicated_account_id = account_data.get("id") or result.get("id") if isinstance(result, dict) else None

    if not account_number:
        logger.warning("Paystack returned success without account number; creating manual fallback route.")

        fallback_code = f"MANUAL_{payment_type[:3].upper()}_{school.id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        fallback_route = PaystackSubAccount(
            school_id=g.school_id,
            payment_type=payment_type,
            subaccount_code=fallback_code,
            business_name=business_name,
            virtual_bank_account=None,
            virtual_bank_name=school.bank_name or bank_name or "School Bank Account",
            momo_shortcode=None,
            momo_provider=preferred_bank,
            percentage_charge=percentage_charge,
            is_active=True,
            is_verified=False,
            created_by=user_id,
        )

        db.session.add(fallback_route)
        log_action(
            user_id,
            g.school_id,
            "PAYSTACK_ROUTE_FALLBACK_CREATED",
            f"Created manual fallback payment route for {payment_type} due to missing virtual account number.",
        )
        db.session.commit()

        fallback_message = "Payment route created. Virtual account setup is pending; parents can use the school's saved bank account meanwhile."
        if key_mode == "test":
            fallback_message = "Payment route saved in fallback mode. Paystack test keys do not provide a usable live virtual account number here, so parents should pay cash at the school office or use the school's approved manual instructions until live keys are configured."

        return jsonify({
            "message": fallback_message,
            "subaccount": fallback_route.to_dict(),
            "fee_route_account": fallback_route.to_dict(),
            "mode": "manual_fallback",
            "gateway_mode": key_mode,
        }), 201

    # Keep legacy table compatibility: store deterministic route identifier in subaccount_code field (historical name).
    stored_route_code = f"DVA_{dedicated_account_id}" if dedicated_account_id else f"DVA_{payment_type[:3].upper()}_{account_number[-6:]}"
    
    # Create database record
    subaccount = PaystackSubAccount(
        school_id=g.school_id,
        payment_type=payment_type,
        subaccount_code=stored_route_code,
        business_name=business_name,
        virtual_bank_account=account_number,
        virtual_bank_name=bank_name,
        momo_shortcode=None,  # Not auto-populated in current integration
        momo_provider=preferred_bank,
        percentage_charge=percentage_charge,
        is_active=True,
        is_verified=bool(account_data.get("active", True)),
        created_by=user_id
    )
    
    db.session.add(subaccount)
    
    log_action(
        user_id,
        g.school_id,
        "PAYSTACK_DEDICATED_ACCOUNT_CREATED",
        f"Created Paystack dedicated virtual account for {payment_type}: {subaccount.virtual_bank_account} ({subaccount.virtual_bank_name or preferred_bank})"
    )
    
    db.session.commit()
    
    return jsonify({
        "message": f"Dedicated virtual account created for {payment_type}. Parents can pay to this virtual account.",
        "subaccount": subaccount.to_dict(),
        "fee_route_account": subaccount.to_dict(),
        "gateway_mode": key_mode,
        "dedicated_account": {
            "customer": customer_code,
            "preferred_bank": preferred_bank,
            "dedicated_account_id": dedicated_account_id,
            "account_number": account_number,
            "bank_name": bank_name,
        }
    }), 201


@api.route("/proprietor/paystack/customers/resolve", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def resolve_paystack_customer_code_for_school():
    """Resolve or create the school-level Paystack customer and return customer code."""
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"error": "School not found"}), 404

    customer_code, email, source, error = _resolve_or_create_paystack_customer_for_school(school)
    if error or not customer_code:
        fallback_code = f"LOCAL_{school.id}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
        return jsonify(
            {
                "message": "Customer profile is being prepared in the background.",
                "customer_code": fallback_code,
                "email": school.school_email,
                "school_id": school.id,
                "school_name": school.name,
                "source": "fallback",
            }
        ), 200

    return jsonify(
        {
            "message": "Paystack school customer resolved",
            "customer_code": customer_code,
            "email": email,
            "school_id": school.id,
            "school_name": school.name,
            "source": source,
        }
    )


@api.route("/proprietor/paystack/providers", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_paystack_dedicated_account_providers():
    """Get supported dedicated-account providers from Paystack."""
    country = sanitize_string(request.args.get("country") or "ghana").lower()
    endpoint = f"/dedicated_account/available_providers?country={country}"
    key_mode = _get_paystack_secret_key_mode()

    result, error = _call_paystack_api(endpoint)
    if error:
        warning = "Provider list is temporarily unavailable. Using default provider options."
        if key_mode == "test":
            warning += " Paystack test keys usually do not return real dedicated virtual account numbers, so fallback mode is expected until live keys are configured."
        fallback_providers = [
            {
                "name": "Titan Paystack",
                "slug": "titan-paystack",
                "id": None,
                "bank_id": None,
                "type": "fallback",
            }
        ]
        return jsonify(
            {
                "providers": fallback_providers,
                "warning": warning,
                "gateway_mode": key_mode,
            }
        ), 200

    providers = []
    for provider in (result or []):
        if not isinstance(provider, dict):
            continue
        providers.append({
            "name": provider.get("name"),
            "slug": provider.get("slug") or provider.get("provider_slug"),
            "id": provider.get("id"),
            "bank_id": provider.get("bank_id"),
            "type": provider.get("type"),
        })

    return jsonify(providers)


@api.route("/proprietor/paystack/subaccounts/<int:subaccount_id>", methods=["DELETE"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def deactivate_paystack_subaccount(subaccount_id):
    """Deactivate a Paystack fee route account (soft delete)."""
    user_id = int(get_jwt_identity())
    
    subaccount = PaystackSubAccount.query.filter_by(
        id=subaccount_id,
        school_id=g.school_id
    ).first_or_404()
    
    subaccount.is_active = False
    
    log_action(
        user_id,
        g.school_id,
        "PAYSTACK_SUBACCOUNT_DEACTIVATED",
        f"Deactivated Paystack fee route account: {subaccount.subaccount_code} ({subaccount.payment_type})"
    )
    
    db.session.commit()
    
    return jsonify({"message": "Fee route account deactivated"}), 200


@api.route("/proprietor/paystack/banks", methods=["GET"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def get_paystack_banks():
    """Get list of supported banks for subaccount creation."""
    result, error = _call_paystack_api("/bank?country=ghana")
    
    if error:
        return jsonify({"error": f"Failed to fetch banks: {error}"}), 500
    
    # Return simplified list
    banks = [
        {
            "name": bank.get("name"),
            "code": bank.get("code"),
            "slug": bank.get("slug")
        }
        for bank in (result or [])
    ]
    
    return jsonify(banks)


@api.route("/finance/paystack/initialize-payment", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def initialize_paystack_payment():
    """Initialize a Paystack payment with automatic split to school's subaccount.
    
    This generates a payment link or returns transaction data for frontend checkout.
    Payment automatically splits to the school's designated subaccount based on payment type.
    """
    data = request.get_json() or {}
    
    student_id = data.get("student_id")
    payment_type = sanitize_string(data.get("payment_type", "Tuition"))
    amount = data.get("amount")
    
    if not student_id or not amount:
        return jsonify({"error": "student_id and amount required"}), 400
    
    student = Student.query.filter_by(
        id=student_id,
        school_id=g.school_id
    ).first_or_404()
    
    # Get fee route account for this payment type
    subaccount_code = _get_subaccount_for_payment(g.school_id, payment_type)
    
    # Generate unique reference
    import uuid
    reference = f"PS-{student.student_code}-{payment_type[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"
    
    # Prepare Paystack initialization payload
    paystack_payload = {
        "email": student.parent_email or f"{student.student_code}@temp.edupulse.gh",
        "amount": int(amount * 100),  # Convert to pesewas
        "reference": reference,
        "currency": "GHS",
        "metadata": {
            "student_id": student.id,
            "student_code": student.student_code,
            "student_name": student.name,
            "school_id": g.school_id,
            "payment_type": payment_type,
            "payment_category": data.get("payment_category", {}),
        },
        "callback_url": data.get("callback_url", "https://edupulse.com/payment-complete"),
    }
    
    # Add fee route account for split payment if exists
    if subaccount_code:
        paystack_payload["subaccount"] = subaccount_code
        paystack_payload["transaction_charge"] = 0  # School pays all Paystack fees
    
    # Call Paystack API to initialize transaction
    result, error = _call_paystack_api("/transaction/initialize", method="POST", data=paystack_payload)
    
    if error:
        logger.error(f"Paystack initialization failed: {error}")
        return jsonify({"error": f"Payment initialization failed: {error}"}), 500
    
    return jsonify({
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
        "payment_type": payment_type,
        "subaccount_code": subaccount_code,
        "message": f"Payment link generated for {student.name}"
    })


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
        return jsonify({"message": "Bulk WhatsApp terminal report sending is available for Premium plan only."}), 403

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
        return jsonify({"message": "Bulk WhatsApp payment reminders are available for Premium plan only."}), 403

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

    # School-wide virtual routing map (same for all students in this school)
    subaccounts = PaystackSubAccount.query.filter_by(
        school_id=g.school_id, is_active=True
    ).all()
    subaccount_map = {
        (entry.payment_type or "").strip(): entry for entry in subaccounts
    }

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
            
            # Payment instructions (virtual routes first)
            y_position -= 0.6 * inch
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y_position, "How to Pay (Per Fee Type Virtual Route):")
            
            y_position -= 0.3 * inch
            c.setFont("Helvetica", 10)
            for fee_type, amount in fee_items:
                route = subaccount_map.get(fee_type)
                ref_code = payment_codes.get(fee_type)

                if route and route.virtual_bank_account:
                    route_bank = route.virtual_bank_name or "Bank shown for this virtual account"
                    route_text = f"{route_bank} Acct {route.virtual_bank_account}"
                    line = f"{fee_type}: GH₵ {amount:.2f} via {route_text}"
                else:
                    line = f"{fee_type}: GH₵ {amount:.2f} (virtual route not configured)"

                c.drawString(inch, y_position, line[:110])
                y_position -= 0.25 * inch

                if ref_code:
                    c.drawString(inch + 15, y_position, f"Backup Ref: {ref_code}")
                    y_position -= 0.22 * inch

            y_position -= 0.1 * inch
            c.setFont("Helvetica", 9)
            footer_instructions = [
                "For USSD wallet-to-bank, select the bank shown with each virtual account.",
                "Then enter the same virtual account number, confirm, and complete payment.",
                "Paystack auto-detects payment type from the virtual route used.",
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
                "See virtual payment routes in attached statement. "
                "USSD wallet-to-bank: select the bank shown with each virtual account."
            )
            result = send_document_bytes(student.parent_phone, pdf_bytes, filename, caption=caption)
            message_id = (result.get("messages") or [{}])[0].get("id")

            # Send short text with per-fee routes (best effort)
            route_lines = []
            for fee_type, amount in fee_items:
                route = subaccount_map.get(fee_type)
                ref_code = payment_codes.get(fee_type)
                route_value = None
                if route and route.virtual_bank_account:
                    route_bank = route.virtual_bank_name or "Bank shown"
                    route_value = f"{route_bank} Acct {route.virtual_bank_account}"

                if route_value:
                    route_lines.append(f"- {fee_type}: GH₵ {amount:.2f} via {route_value} (Ref {ref_code or '-'})")
                else:
                    route_lines.append(f"- {fee_type}: GH₵ {amount:.2f} (route not configured, Ref {ref_code or '-'})")

            reminder_text = (
                f"{school.name} Payment Reminder\n"
                f"Student: {student.name} ({student.student_code})\n"
                f"Total Outstanding: GH₵ {total_owed:.2f}\n\n"
                f"Use the matching fee route:\n"
                + "\n".join(route_lines[:6])
                + "\n\nUSSD wallet-to-bank: select the bank shown with the virtual account, then enter that virtual account number."
                + "\nPaystack auto-detects payment type from the route used."
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
@subscription_required("Premium")
def get_student_pulse(student_id):
    """Predictive Sack-Risk based on Financial & Academic data."""
    student = Student.query.filter_by(
        id=student_id, school_id=g.school_id
    ).first_or_404()
    health_data = calculate_academic_health(student.id)
    return jsonify(health_data)


@api.route("/finance/receive-payment", methods=["POST"])
@multi_tenant_guard
@jwt_required()
def receive_payment():
    """
    Manual entry for Cash/Direct payments.
    Accepts either student_id or reference_code (e.g., CFK011 for Tuition).
    - Teachers: Creates 'Pending' record (awaiting Proprietor confirmation).
    - Proprietor: Creates 'Confirmed' record immediately.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"message": "Invalid request body"}), 400

    # Support both student_id and reference_code
    student = None
    payment_type = data.get("type") or data.get("payment_type") or "Tuition"

    if "reference_code" in data:
        # Parse reference code: CFK011 = Student CFK01, Type 1 (Tuition)
        reference_code = data["reference_code"].strip().upper()
        try:
            from backend.utils import parse_payment_code

            student_code, decoded_type = parse_payment_code(reference_code)
            if decoded_type:
                payment_type = decoded_type
            student = Student.query.filter_by(
                student_code=student_code, school_id=g.school_id
            ).first()
            if not student:
                return (
                    jsonify(
                        {"message": f"Student with code {student_code} not found."}
                    ),
                    404,
                )
        except ValueError as e:
            return jsonify({"message": f"Invalid reference code: {str(e)}"}), 400
    else:
        # Use traditional student_id
        student = Student.query.filter_by(
            id=data.get("student_id"), school_id=g.school_id
        ).first_or_404()

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

    reference_id = data.get("reference_code") or data.get("reference_id")
    validation_payload = {
        "student_id": student.id,
        "amount": data.get("amount"),
        "payment_type": payment_type,
        "method": data.get("method", "Cash"),
        "reference_id": reference_id,
        "payment_category": data.get("payment_category", {}),
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
        amount=validation_payload["amount"],
        payment_type=payment_type,
        method=validation_payload["method"],
        reference_id=validation_payload["reference_id"],
        status=status,
        payment_category=validation_payload["payment_category"],
    )
    db.session.add(payment)

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
        data = request.json

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

        # Automatically record and confirm bank transfer payment
        payment = Payment(
            student_id=student.id,
            school_id=student.school_id,
            amount=float(data.get("amount")),
            payment_type=payment_type,
            method="Bank_Auto",
            reference_id=data.get("transaction_id"),  # For idempotency
            status="Confirmed",
            payment_category=payment_category,
        )
        db.session.add(payment)

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

        # Log the transaction
        log_action(
            user_id=None,
            school_id=student.school_id,
            action="BANK_TRANSFER_AUTO",
            details=f"Bank transfer: {data.get('amount')} for {student.name} ({payment_type}, {payment_category}) (Ref: {data.get('transaction_id')})",
        )

        db.session.commit()
        return (
            jsonify(
                {
                    "status": "recorded",
                    "student_id": student.id,
                    "payment_type": payment_type,
                    "category": payment_category,
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
        unpaid_tuition = Student.query.filter(
            Student.school_id == g.school_id, Student.total_tuition_owed > 0
        ).count()
        critical_list = rescue_payload["students"]

        # Fetch pending payments recorded by teachers
        pending_payments = (
            db.session.query(Payment, Student.name)
            .join(Student)
            .filter(Payment.school_id == g.school_id, Payment.status == "Pending")
            .all()
        )

        pending_list = [
            {
                "id": p.Payment.id,
                "amount": p.Payment.amount,
                "student": p.name,
                "type": p.Payment.payment_type,
            }
            for p in pending_payments
        ]

        # Canteen Stats for Proprietor Oversight
        student_meals = Student.query.filter_by(
            school_id=g.school_id, is_present=True, feeding_paid=True
        ).count()
        staff_meals = (
            User.query.filter_by(school_id=g.school_id)
            .filter(User.role.in_(["teacher", "headmaster", "proprietor"]))
            .count()
        )
        canteen_count = student_meals + staff_meals

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
                    except Exception:
                        pass
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
                        "details": log.details,
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
                    "unpaid_tuition": unpaid_tuition,
                    "low_stock_count": len(low_stock_items),
                },
                "pending_payments": pending_list,
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
@multi_tenant_guard
@role_required("proprietor")
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
@multi_tenant_guard
@role_required("proprietor")
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
@multi_tenant_guard
@role_required("proprietor")
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
@multi_tenant_guard
@role_required("proprietor")
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
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def log_student_rescue_outcome():
    """Log a proprietor action taken on a rescue case."""
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
                            "details": log.details,
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


@api.route("/finance/confirm-payment/<int:payment_id>", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def confirm_payment(payment_id):
    """Proprietor confirms manual payment and adds to immutable audit ledger."""
    payment = Payment.query.filter_by(
        id=payment_id, school_id=g.school_id
    ).first_or_404()
    
    if payment.status == "Confirmed":
        return jsonify({"message": "Payment already confirmed."}), 400
    
    payment.status = "Confirmed"
    payment.verified_at = datetime.now(timezone.utc)
    payment.verified_by = int(get_jwt_identity())
    
    # Update student stats
    student = Student.query.get(payment.student_id)
    if student and payment.payment_type == "Tuition":
        student.total_tuition_owed = max(
            0, student.total_tuition_owed - float(payment.amount)
        )
    elif student and payment.payment_type == "Feeding":
        student.feeding_paid = True
    
    # Create immutable ledger entry
    add_ledger_entry(
        school_id=g.school_id,
        tx_type=payment.payment_type.lower(),
        tx_ref=payment.reference_id or f"PAY-{payment.id}",
        amount=payment.amount,
        currency="GH₵",
        actor_id=payment.verified_by,
        student_id=payment.student_id,
        source=payment.method.lower(),
        metadata={
            "payment_id": payment.id,
            "student_name": student.name if student else "Unknown",
            "student_code": student.student_code if student else "N/A",
            "payment_category": payment.payment_category,
            "confirmed_by": User.query.get(payment.verified_by).username if payment.verified_by else "System"
        }
    )
    
    db.session.commit()
    return jsonify({"message": "Cash receipt confirmed and logged to immutable ledger."})


@api.route("/finance/reject-payment/<int:payment_id>", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def reject_payment(payment_id):
    """Proprietor rejects/cancels a pending manual payment (audit protection: cannot delete confirmed payments)."""
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
            or 1
        )  # Avoid division by zero

        revenue_change = (
            ((revenue_this_week - revenue_last_week) / revenue_last_week) * 100
            if revenue_last_week > 0
            else 0
        )

        if revenue_change > 10:
            insights.append(
                {
                    "type": "success",
                    "title": "Revenue Growth",
                    "message": f"Revenue increased by {revenue_change:.1f}% this week (GH₵ {revenue_this_week:.2f}).",
                    "icon": "📈",
                }
            )
        elif revenue_change < -10:
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
        present_today = Student.query.filter_by(
            school_id=g.school_id, is_present=True
        ).count()
        attendance_rate = (
            (present_today / total_students * 100) if total_students > 0 else 0
        )

        if attendance_rate < 75:
            alerts.append(
                {
                    "type": "danger",
                    "title": "Low Attendance Alert",
                    "message": f"Only {attendance_rate:.1f}% attendance today ({present_today}/{total_students}). Investigate absences.",
                    "icon": "🚨",
                }
            )
        elif attendance_rate >= 95:
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
        at_risk_students = Student.query.filter_by(
            school_id=g.school_id, is_present=True, feeding_paid=False
        ).count()

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
                {"message": system_alert.message, "type": system_alert.type}
                if system_alert
                else None
            ),
        }
    )


# --- 4. ADMISSIONS & EXAMS ---


@api.route("/admissions/generate-test", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@subscription_required("Premium")
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
    proration_result = calculate_prorated_admission_charge(school, 1, effective_plan)
    
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
                proration_result = calculate_prorated_admission_charge(school, added_count, effective_plan)
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
        
        valid_statuses = ['Active', 'Graduated', 'Withdrawn', 'Transferred', 'Suspended', 'Inactive']
        
        if not new_status or new_status not in valid_statuses:
            return jsonify({
                "message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            }), 400
        
        if not class_filter:
            return jsonify({"message": "class is required for bulk update"}), 400
        
        # Build query to find students to update
        query = Student.query.filter_by(
            school_id=g.school_id,
            current_class=class_filter,
            status=current_status
        )
        
        students_to_update = query.all()
        
        if not students_to_update:
            return jsonify({
                "message": f"No students found with status '{current_status}' in class '{class_filter}'",
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
                "total": (total_active + total_graduated + total_withdrawn + 
                         total_transferred + total_suspended + total_inactive)
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
@role_required("proprietor", "headmaster", "teacher")
@jwt_required()
def search_students():
    """
    Search students by name or student code.
    Query parameter: q (search query)
    """
    try:
        query = request.args.get("q", "").strip()
        if len(query) < 2:
            return jsonify({"students": []}), 200
        
        # Search by name or student code (case-insensitive)
        students = Student.query.filter_by(school_id=g.school_id).filter(
            db.or_(
                Student.name.ilike(f"%{query}%"),
                Student.student_code.ilike(f"%{query}%"),
                Student.first_name.ilike(f"%{query}%"),
                Student.surname.ilike(f"%{query}%")
            )
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

        today = datetime.now(timezone.utc).date()
        is_holiday, holiday_name = _get_holiday_status(g.school_id, today)

        for grade in VALID_GRADES:
            try:
                # Count present students in this class
                present_count = Student.query.filter_by(
                    school_id=g.school_id, current_class=grade, is_present=True
                ).count()

                # Count how many of those present have paid feeding
                paid_count = Student.query.filter_by(
                    school_id=g.school_id,
                    current_class=grade,
                    is_present=True,
                    feeding_paid=True,
                ).count()

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

        # Count Teachers (All teaching staff who also need meals)
        try:
            teacher_count = (
                User.query.filter_by(school_id=g.school_id)
                .filter(User.role.in_(["teacher", "headmaster"]))
                .count()
            )
        except Exception as e:
            return jsonify({"message": "Error counting teachers", "error": str(e)}), 500

        # Calculate total meals: students who PAID for feeding + all available teachers
        total_meals_needed = total_feeding_paid + teacher_count
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
                    "total_feeding_paid": total_feeding_paid,
                    "total_teachers": teacher_count,
                    "total_meals_needed": total_meals_needed,
                    "is_holiday": is_holiday,
                    "holiday_name": holiday_name,
                    "holiday_date": today.isoformat(),
                    "note": "Kitchen should prepare meals for: paying students + all available teachers",
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
    total_students = Student.query.filter_by(school_id=g.school_id).count()
    present_students = Student.query.filter_by(
        school_id=g.school_id, is_present=True
    ).count()

    class_breakdown = []
    for grade in VALID_GRADES:
        total_in_class = Student.query.filter_by(
            school_id=g.school_id, current_class=grade
        ).count()
        present_in_class = Student.query.filter_by(
            school_id=g.school_id, current_class=grade, is_present=True
        ).count()
        if total_in_class > 0:
            class_breakdown.append(
                {
                    "class_name": grade,
                    "total": total_in_class,
                    "present": present_in_class,
                    "percentage": round((present_in_class / total_in_class) * 100, 1),
                }
            )

    return jsonify(
        {
            "total_students": total_students,
            "present_students": present_students,
            "absent_students": total_students - present_students,
            "attendance_percentage": (
                round((present_students / total_students) * 100, 1)
                if total_students > 0
                else 0
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
    student_meals = Student.query.filter_by(
        school_id=g.school_id, is_present=True, feeding_paid=True
    ).count()
    staff_meals = (
        User.query.filter_by(school_id=g.school_id)
        .filter(User.role.in_(["teacher", "headmaster", "proprietor"]))
        .count()
    )
    return jsonify({"total_meals": student_meals + staff_meals})


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
    return jsonify(
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
                "feeding_paid": s.feeding_paid,
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


@api.route("/staff/add", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
def add_staff():
    """Adds a new staff member to the tenant."""
    data = request.json

    # Email is now required for staff accounts
    email = _normalize_email_address(data.get("email"))
    if not email:
        return jsonify({"message": "Email is required for staff accounts."}), 400

    if User.query.filter_by(username=data["username"], school_id=g.school_id).first():
        return jsonify({"message": "Username already exists in this school."}), 400

    if _find_school_user_by_email(g.school_id, email):
        return jsonify({"message": "Email address is already assigned to another staff member in this school."}), 400

    roles = data.get("roles") if isinstance(data.get("roles"), list) else []
    primary_role = data.get("role") or (roles[0] if roles else "teacher")
    allowed_roles = ["teacher", "homeroom", "headmaster", "finance", "inventory_manager"]
    if primary_role not in allowed_roles or any(r not in allowed_roles for r in roles):
        return jsonify({"message": "Invalid role."}), 400

    if not roles:
        roles = [primary_role]

    temp_password = _generate_staff_temp_password()

    # Set temp password expiry to 30 days from now
    temp_expires = datetime.now(timezone.utc) + timedelta(days=30)

    new_user = User(
        username=data["username"],
        email=email,
        role=primary_role,
        roles=roles,
        school_id=g.school_id,
        password_hash=generate_password_hash(temp_password),
        is_temp_password=True,
        temp_password_expires_at=temp_expires,
        assigned_class=(
            data.get("assigned_class")
            if "homeroom" in roles or "teacher" in roles
            else None
        ),
    )
    db.session.add(new_user)
    db.session.commit()

    if "homeroom" in roles or "teacher" in roles:
        replace_teacher_assignments(
            new_user.id,
            data.get("assigned_classes", []),
            data.get("assigned_subjects", []),
        )
        db.session.commit()

    school = School.query.get(g.school_id)
    email_sent, email_error = _send_staff_invite_email(
        new_user,
        school,
        temp_password,
        expiry_days=30,
    )

    status_message = "Staff member added successfully."
    if email_sent:
        status_message += " Welcome email sent with login credentials."
    else:
        status_message += " Failed to send welcome email. Please verify SMTP configuration."

    return jsonify(
        {
            "message": status_message,
            "username": data["username"],
            "email": email,
            "password_expires_in_days": 30,
            "email_sent": email_sent,
            "email_error": email_error,
        }
    )


@api.route("/staff/<int:user_id>/resend-invite", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def resend_staff_invite(user_id):
    """Issue a fresh temporary password and resend the staff invite email."""
    user = User.query.filter_by(id=user_id, school_id=g.school_id).first_or_404()
    if user.role == "proprietor":
        return jsonify({"message": "Cannot resend invite for proprietor accounts."}), 400

    if not user.email:
        return jsonify({"message": "This staff account has no email address on file."}), 400

    temp_password = _generate_staff_temp_password()
    user.password_hash = generate_password_hash(temp_password)
    user.is_temp_password = True
    user.temp_password_expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    school = School.query.get(g.school_id)
    email_sent, email_error = _send_staff_invite_email(
        user,
        school,
        temp_password,
        expiry_days=30,
    )

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "STAFF_INVITE_RESENT",
        f"Resent invite to user {user.username}",
    )
    db.session.commit()

    status_message = "Staff invite resent successfully."
    if email_sent:
        status_message += " A fresh temporary password was emailed to the staff member."
    else:
        status_message += " Failed to send welcome email. Please verify SMTP configuration."

    return jsonify(
        {
            "message": status_message,
            "username": user.username,
            "email": user.email,
            "password_expires_in_days": 30,
            "email_sent": email_sent,
            "email_error": email_error,
        }
    )


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
                
                # Validate roles
                for role in roles:
                    if role not in allowed_roles:
                        errors.append(f"Row {idx}: Invalid role '{role}'. Allowed: {', '.join(allowed_roles)}")
                        continue
                
                primary_role = roles[0] if roles else "teacher"

                try:
                    # Create the user
                    new_staff = User(
                        username=username,
                        email=email,
                        role=primary_role,
                        roles=roles,
                        school_id=g.school_id,
                        password_hash=generate_password_hash(password),
                        assigned_class=(
                            (row.get("assigned_class") or "").strip()
                            if any(r in roles for r in ["homeroom", "teacher"])
                            else None
                        ),
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
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_30_days = now - timedelta(days=30)
        last_365_days = now - timedelta(days=365)

        # Get all students for the school
        students = Student.query.filter_by(school_id=g.school_id).all()

        # Get all payments for the school
        payments = Payment.query.filter_by(
            school_id=g.school_id, status="Confirmed"
        ).all()

        # Calculate statistics
        total_collected = sum(p.amount for p in payments) if payments else 0
        outstanding_balance = (
            sum(s.total_tuition_owed for s in students) if students else 0
        )

        daily_revenue = (
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

        # Count students with paid vs unpaid balances
        paid_count = sum(1 for s in students if s.total_tuition_owed == 0)
        unpaid_count = len(students) - paid_count

        # Get recent transactions (last 10)
        recent_payments = (
            Payment.query.filter_by(school_id=g.school_id, status="Confirmed")
            .order_by(Payment.date_paid.desc())
            .limit(10)
            .all()
        )

        recent_transactions = []
        for payment in recent_payments:
            student = Student.query.get(payment.student_id)
            recent_transactions.append(
                {
                    "id": payment.id,
                    "date": payment.date_paid.strftime("%Y-%m-%d"),
                    "student_name": student.name if student else "Unknown",
                    "amount": payment.amount,
                    "type": payment.payment_type,
                    "method": payment.method,
                }
            )

        # Pending payments recorded by teachers
        pending_payments = (
            db.session.query(Payment, Student.name)
            .join(Student)
            .filter(Payment.school_id == g.school_id, Payment.status == "Pending")
            .all()
        )
        pending_list = [
            {
                "id": p.Payment.id,
                "amount": p.Payment.amount,
                "student": p.name,
                "type": p.Payment.payment_type,
            }
            for p in pending_payments
        ]

        return jsonify(
            {
                "daily_revenue": daily_revenue,
                "monthly_revenue": monthly_revenue,
                "yearly_revenue": yearly_revenue,
                "total_collected": total_collected,
                "outstanding_balance": outstanding_balance,
                "paid_count": paid_count,
                "unpaid_count": unpaid_count,
                "recent_transactions": recent_transactions,
                "pending_payments": pending_list,
            }
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
        from sqlalchemy.orm import joinedload

        payments = (
            db.session.query(Payment, Student.name)
            .join(Student)
            .filter(Payment.school_id == g.school_id)
            .order_by(Payment.date_paid.desc())
            .all()
        )
        return jsonify(
            [
                {
                    "id": p.Payment.id,
                    "student_name": p.name,
                    "amount": p.Payment.amount,
                    "type": p.Payment.payment_type,
                    "method": p.Payment.method,
                    "status": p.Payment.status,
                    "date": p.Payment.date_paid.strftime("%Y-%m-%d %H:%M"),
                }
                for p in payments
            ]
        )
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
@role_required("proprietor", "headmaster")
@jwt_required()
def save_analytics_preset():
    try:
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
@role_required("proprietor", "headmaster")
@jwt_required()
def set_default_analytics_preset(preset_name):
    try:
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
@role_required("proprietor", "headmaster")
@jwt_required()
def delete_analytics_preset(preset_name):
    try:
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


@api.route("/analytics/class-performance", methods=["GET"])
@multi_tenant_guard
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
@multi_tenant_guard
def get_school_branding():
    """Get school branding information for documents and fee configuration."""
    try:
        school = School.query.get(g.school_id)
        settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

        fees = {
            "tuition_fee": 0.0,
            "feeding_fee": 0.0,
            "uniform_fee": 0.0,
            "transport_fee": 0.0,
            "terminal_report_fee": 0.0,
            "other_fees": {},
        }

        if settings:
            fees = {
                "tuition_fee": settings.tuition_fee or 0.0,
                "feeding_fee": settings.feeding_fee or 0.0,
                "uniform_fee": settings.uniform_fee or 0.0,
                "transport_fee": settings.transport_fee or 0.0,
                "terminal_report_fee": settings.terminal_report_fee or 0.0,
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


DEFAULT_PAYMENT_CONVENIENCE_FEE_PERCENT = 2.0


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


# ============================================================
# EXAM PAPER APIs - For Teachers to Create Question Papers
# ============================================================

@api.route("/exams/papers", methods=["POST"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def create_exam_paper():
    """Create a new exam question paper."""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()
        
        # Validate required fields
        if not data.get("title") or not data.get("class_name") or not data.get("subject_name"):
            return jsonify({"message": "Missing required fields: title, class_name, subject_name"}), 400
        
        # Validate questions is a list
        questions = data.get("questions", [])
        if not isinstance(questions, list):
            return jsonify({"message": "questions must be a list"}), 400
        
        paper = ExamPaper(
            school_id=g.school_id,
            teacher_id=user_id,
            class_name=data["class_name"],
            subject_name=data["subject_name"],
            title=data["title"],
            academic_term=data.get("academic_term"),
            academic_year=data.get("academic_year"),
            exam_type=data.get("exam_type"),
            instructions=data.get("instructions"),
            total_marks=data.get("total_marks"),
            duration_minutes=data.get("duration_minutes"),
            questions=questions,
            status=data.get("status", "draft")
        )
        
        db.session.add(paper)
        db.session.commit()
        
        log_action(user_id, g.school_id, "EXAM_PAPER_CREATED", 
                  f"Created exam paper: {paper.title} for {paper.class_name} {paper.subject_name}")
        
        return jsonify({
            "message": "Exam paper created successfully",
            "paper_id": paper.id
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error creating exam paper", "error": str(e)}), 500


@api.route("/exams/papers", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def get_exam_papers():
    """Get all exam papers created by the teacher."""
    try:
        user_id = int(get_jwt_identity())
        
        # Query parameters for filtering
        class_name = request.args.get("class_name")
        subject_name = request.args.get("subject_name")
        status = request.args.get("status")
        
        query = ExamPaper.query.filter_by(school_id=g.school_id, teacher_id=user_id)
        
        if class_name:
            query = query.filter_by(class_name=class_name)
        if subject_name:
            query = query.filter_by(subject_name=subject_name)
        if status:
            query = query.filter_by(status=status)
        
        papers = query.order_by(ExamPaper.created_at.desc()).all()

        return jsonify([
            {
                "id": p.id,
                "title": p.title,
                "class_name": p.class_name,
                "subject_name": p.subject_name,
                "academic_term": p.academic_term,
                "academic_year": p.academic_year,
                "exam_type": p.exam_type,
                "total_marks": p.total_marks,
                "duration_minutes": p.duration_minutes,
                "status": p.status,
                "question_count": len(p.questions) if p.questions else 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                "finalized_at": p.finalized_at.isoformat() if p.finalized_at else None,
            }
            for p in papers
        ])
    except Exception as e:
        return jsonify({"message": "Error fetching exam papers", "error": str(e)}), 500


@api.route("/exams/papers/<int:paper_id>", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def get_exam_paper(paper_id):
    """Get a specific exam paper with full details."""
    try:
        user_id = int(get_jwt_identity())
        paper = ExamPaper.query.filter_by(
            id=paper_id,
            school_id=g.school_id,
        ).first_or_404()

        user = User.query.filter_by(id=user_id, school_id=g.school_id).first()
        role_set = set((user.roles or []) + [user.role or ""]) if user else set()
        can_view = (
            paper.teacher_id == user_id
            or "headmaster" in role_set
            or "proprietor" in role_set
        )
        if not can_view:
            return jsonify({"message": "Access denied to this exam paper."}), 403
        
        return jsonify({
            "id": paper.id,
            "title": paper.title,
            "class_name": paper.class_name,
            "subject_name": paper.subject_name,
            "academic_term": paper.academic_term,
            "academic_year": paper.academic_year,
            "exam_type": paper.exam_type,
            "instructions": paper.instructions,
            "total_marks": paper.total_marks,
            "duration_minutes": paper.duration_minutes,
            "questions": paper.questions,
            "status": paper.status,
            "created_at": paper.created_at.isoformat() if paper.created_at else None,
            "updated_at": paper.updated_at.isoformat() if paper.updated_at else None,
            "finalized_at": paper.finalized_at.isoformat() if paper.finalized_at else None
        })
    except Exception as e:
        return jsonify({"message": "Error fetching exam paper", "error": str(e)}), 500


@api.route("/exams/papers/<int:paper_id>", methods=["PUT"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def update_exam_paper(paper_id):
    """Update an exam paper."""
    try:
        user_id = int(get_jwt_identity())
        paper = ExamPaper.query.filter_by(
            id=paper_id,
            school_id=g.school_id,
            teacher_id=user_id,
        ).first_or_404()

        data = request.get_json() or {}

        if "title" in data:
            paper.title = data["title"]
        if "class_name" in data:
            paper.class_name = data["class_name"]
        if "subject_name" in data:
            paper.subject_name = data["subject_name"]
        if "academic_term" in data:
            paper.academic_term = data["academic_term"]
        if "academic_year" in data:
            paper.academic_year = data["academic_year"]
        if "exam_type" in data:
            paper.exam_type = data["exam_type"]
        if "instructions" in data:
            paper.instructions = data["instructions"]
        if "total_marks" in data:
            paper.total_marks = data["total_marks"]
        if "duration_minutes" in data:
            paper.duration_minutes = data["duration_minutes"]
        if "questions" in data:
            paper.questions = data["questions"]
        if "status" in data:
            paper.status = data["status"]
            if data["status"] == "finalized" and not paper.finalized_at:
                paper.finalized_at = datetime.now(timezone.utc)

        paper.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action(
            user_id,
            g.school_id,
            "EXAM_PAPER_UPDATED",
            f"Updated exam paper: {paper.title}",
        )

        return jsonify({"message": "Exam paper updated successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error updating exam paper", "error": str(e)}), 500


@api.route("/exams/papers/<int:paper_id>", methods=["DELETE"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def delete_exam_paper(paper_id):
    """Delete an exam paper."""
    try:
        user_id = int(get_jwt_identity())
        paper = ExamPaper.query.filter_by(
            id=paper_id,
            school_id=g.school_id,
            teacher_id=user_id,
        ).first_or_404()

        title = paper.title
        db.session.delete(paper)
        db.session.commit()

        log_action(
            user_id,
            g.school_id,
            "EXAM_PAPER_DELETED",
            f"Deleted exam paper: {title}",
        )

        return jsonify({"message": "Exam paper deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error deleting exam paper", "error": str(e)}), 500


@api.route("/exams/papers/<int:paper_id>/submit", methods=["POST"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def submit_exam_paper(paper_id):
    """Submit an exam paper to headmaster or proprietor for review/approval flow."""
    try:
        user_id = int(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        submit_to = sanitize_string(payload.get("submit_to"))

        if submit_to not in ["headmaster", "proprietor"]:
            return jsonify({"message": "submit_to must be 'headmaster' or 'proprietor'"}), 400

        paper = ExamPaper.query.filter_by(
            id=paper_id,
            school_id=g.school_id,
            teacher_id=user_id,
        ).first_or_404()

        school_users = User.query.filter(User.school_id == g.school_id).all()
        receiver_exists = next(
            (
                record
                for record in school_users
                if (record.role == submit_to)
                or (isinstance(record.roles, list) and submit_to in record.roles)
            ),
            None,
        )
        if not receiver_exists:
            return jsonify({"message": f"No {submit_to} user found for this school."}), 400

        paper.status = f"submitted_{submit_to}"
        paper.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action(
            user_id,
            g.school_id,
            "EXAM_PAPER_SUBMITTED",
            f"Submitted exam paper '{paper.title}' to {submit_to}",
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Exam paper submitted to {submit_to}.",
                "paper_id": paper.id,
                "paper_status": paper.status,
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error submitting exam paper", "error": str(e)}), 500


@api.route("/exams/papers/inbox", methods=["GET"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("headmaster", "proprietor")
@jwt_required()
def get_exam_papers_inbox():
    """Review inbox for submitted exam papers (headmaster/proprietor)."""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.filter_by(id=user_id, school_id=g.school_id).first()
        if not user:
            return jsonify({"message": "User not found"}), 404

        role_set = set((user.roles or []) + [user.role or ""])
        target_statuses = []
        if "headmaster" in role_set:
            target_statuses.append("submitted_headmaster")
        if "proprietor" in role_set:
            target_statuses.append("submitted_proprietor")

        if not target_statuses:
            return jsonify([])

        class_name = sanitize_string(request.args.get("class_name"))
        subject_name = sanitize_string(request.args.get("subject_name"))

        query = ExamPaper.query.filter(
            ExamPaper.school_id == g.school_id,
            ExamPaper.status.in_(target_statuses),
        )

        if class_name:
            query = query.filter(ExamPaper.class_name == class_name)
        if subject_name:
            query = query.filter(ExamPaper.subject_name == subject_name)

        papers = query.order_by(ExamPaper.updated_at.desc(), ExamPaper.created_at.desc()).all()

        teacher_ids = sorted({p.teacher_id for p in papers})
        teachers = (
            User.query.filter(User.school_id == g.school_id, User.id.in_(teacher_ids)).all()
            if teacher_ids
            else []
        )
        teacher_map = {teacher.id: teacher.username for teacher in teachers}

        return jsonify(
            [
                {
                    "id": p.id,
                    "title": p.title,
                    "class_name": p.class_name,
                    "subject_name": p.subject_name,
                    "academic_term": p.academic_term,
                    "academic_year": p.academic_year,
                    "exam_type": p.exam_type,
                    "status": p.status,
                    "question_count": len(p.questions) if p.questions else 0,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "teacher_id": p.teacher_id,
                    "teacher_name": teacher_map.get(p.teacher_id),
                }
                for p in papers
            ]
        )
    except Exception as e:
        return jsonify({"message": "Error fetching exam inbox", "error": str(e)}), 500


@api.route("/exams/papers/<int:paper_id>/review", methods=["POST"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("headmaster", "proprietor")
@jwt_required()
def review_exam_paper(paper_id):
    """Review submitted exam paper: approve/forward or reject/return."""
    try:
        user_id = int(get_jwt_identity())
        payload = request.get_json(silent=True) or {}
        action = sanitize_string(payload.get("action"))
        feedback = sanitize_string(payload.get("feedback"))

        if action not in ["approve", "reject"]:
            return jsonify({"message": "action must be 'approve' or 'reject'"}), 400

        reviewer = User.query.filter_by(id=user_id, school_id=g.school_id).first()
        if not reviewer:
            return jsonify({"message": "Reviewer not found"}), 404

        role_set = set((reviewer.roles or []) + [reviewer.role or ""])
        paper = ExamPaper.query.filter_by(id=paper_id, school_id=g.school_id).first_or_404()

        if paper.status == "submitted_headmaster" and "headmaster" in role_set:
            if action == "approve":
                paper.status = "submitted_proprietor"
            else:
                paper.status = "returned_by_headmaster"
        elif paper.status == "submitted_proprietor" and "proprietor" in role_set:
            if action == "approve":
                paper.status = "finalized"
                if not paper.finalized_at:
                    paper.finalized_at = datetime.now(timezone.utc)
            else:
                paper.status = "returned_by_proprietor"
        else:
            return jsonify({"message": "This exam paper is not in your review queue."}), 403

        paper.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        review_details = (
            f"Exam paper '{paper.title}' reviewed by {reviewer.username}: action={action}, "
            f"new_status={paper.status}"
        )
        if feedback:
            review_details += f", feedback={feedback}"

        log_action(
            user_id,
            g.school_id,
            "EXAM_PAPER_REVIEWED",
            review_details,
        )

        return jsonify(
            {
                "status": "success",
                "message": "Exam paper review completed.",
                "paper_id": paper.id,
                "paper_status": paper.status,
            }
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Error reviewing exam paper", "error": str(e)}), 500


@api.route("/exams/generate-questions", methods=["POST"])
@multi_tenant_guard
@feature_required("exam_papers")
@role_required("teacher", "homeroom", "headmaster")
@jwt_required()
def generate_exam_questions_ai():
    """Generate exam questions with AI (with fallback when provider is unavailable)."""
    try:
        school = School.query.get(g.school_id)
        effective_plan = get_effective_plan(school)
        if effective_plan != "Premium":
            return (
                jsonify(
                    {
                        "message": "AI Exam Assistant is available for Premium plan only.",
                        "required_plan": "Premium",
                        "current_plan": effective_plan,
                    }
                ),
                403,
            )

        payload = request.get_json(silent=True) or {}
        payload["school_id"] = g.school_id
        result = generate_exam_questions(payload)

        log_action(
            int(get_jwt_identity()),
            g.school_id,
            "EXAM_AI_GENERATE_QUESTIONS",
            f"AI question generation used provider={result.get('provider')} status={result.get('status')}",
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({"message": "Error generating questions", "error": str(e)}), 500


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
    data = request.json or {}
    user = User.query.filter_by(id=user_id, school_id=g.school_id).first_or_404()

    if "email" in data:
        email = _normalize_email_address(data.get("email"))
        if not email:
            return jsonify({"message": "Email is required for staff accounts."}), 400
        if _find_school_user_by_email(g.school_id, email, exclude_user_id=user.id):
            return jsonify({"message": "Email address is already assigned to another staff member in this school."}), 400
        user.email = email

    roles = (
        data.get("roles")
        if isinstance(data.get("roles"), list)
        else (user.roles or [user.role])
    )
    primary_role = data.get("role", user.role)
    if roles:
        primary_role = roles[0]

    allowed_roles = ["teacher", "homeroom", "headmaster", "finance", "inventory_manager"]
    if primary_role not in allowed_roles or any(r not in allowed_roles for r in roles):
        return jsonify({"message": "Invalid role."}), 400

    user.role = primary_role
    user.roles = roles
    assigned_class = data.get("assigned_class", user.assigned_class)
    user.assigned_class = (
        assigned_class if "homeroom" in roles or "teacher" in roles else None
    )

    if "homeroom" in roles or "teacher" in roles:
        if "assigned_classes" in data or "assigned_subjects" in data:
            replace_teacher_assignments(
                user.id,
                data.get("assigned_classes", []),
                data.get("assigned_subjects", []),
            )
    else:
        TeacherAssignment.query.filter_by(
            school_id=g.school_id, teacher_id=user.id
        ).delete()

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "STAFF_UPDATED",
        f"Updated user {user.username} to roles {', '.join(roles)}",
    )
    db.session.commit()
    return jsonify({"message": "Staff member updated."})


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
    school = School.query.get(g.school_id)
    if not school:
        return jsonify({"message": "School not found"}), 404

    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None

    log_action(
        actor_id,
        g.school_id,
        "SETTINGS_VIEWED",
        json.dumps(
            {
                "module": "school_settings",
                "contains_bank_fields": True,
                "ip": request.remote_addr,
            }
        ),
    )

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    masked_bank_fields = _masked_bank_fields_for_school(school)

    return jsonify(
        {
            "name": school.name,
            "motto": school.motto,
            "logo_url": school.logo_url,
            "primary_color": school.primary_color,
            "school_email": school.school_email,
            "school_phone": school.school_phone,
            "school_address": school.school_address,
            "school_website": school.school_website,
            "bank_name": masked_bank_fields["bank_name"],
            "bank_account": masked_bank_fields["bank_account"],
            "bank_account_name": masked_bank_fields["bank_account_name"],
            "bank_branch": masked_bank_fields["bank_branch"],
            "bank_details_masked": True,
            "country_code": settings.country_code if settings and settings.country_code else "GH",
            "anniversary_date": settings.anniversary_date.isoformat() if settings and settings.anniversary_date else None,
            "next_term_reopen_date": _get_report_global_settings(settings).get("next_term_reopen_date") if settings else None,
        }
    ), 200


@api.route("/school/settings", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_school_settings():
    """Updates school branding settings."""
    data = request.json
    school = School.query.get(g.school_id)
    actor_id = get_jwt_identity()
    try:
        actor_id = int(actor_id) if actor_id is not None else None
    except (TypeError, ValueError):
        actor_id = None

    changed_fields = []

    if "name" in data:
        school.name = data["name"]
        changed_fields.append("name")
    if "logo_url" in data:
        school.logo_url = data["logo_url"]
        changed_fields.append("logo_url")
    if "primary_color" in data:
        school.primary_color = data["primary_color"]
        changed_fields.append("primary_color")
    if "motto" in data:
        school.motto = data["motto"]
        changed_fields.append("motto")
    if "school_email" in data:
        school.school_email = data["school_email"]
        changed_fields.append("school_email")
    if "school_phone" in data:
        school.school_phone = data["school_phone"]
        changed_fields.append("school_phone")
    if "school_address" in data:
        school.school_address = data["school_address"]
        changed_fields.append("school_address")
    if "school_website" in data:
        school.school_website = data["school_website"]
        changed_fields.append("school_website")

    masked_bank_fields = _masked_bank_fields_for_school(school)

    # Payment account details
    bank_fields_changed = []
    if "bank_name" in data:
        incoming_bank_name = data["bank_name"]
        if incoming_bank_name != masked_bank_fields["bank_name"]:
            school.bank_name = incoming_bank_name
            changed_fields.append("bank_name")
            bank_fields_changed.append("bank_name")
    if "bank_account" in data:
        incoming_bank_account = data["bank_account"]
        if incoming_bank_account != masked_bank_fields["bank_account"]:
            school.bank_account = incoming_bank_account
            changed_fields.append("bank_account")
            bank_fields_changed.append("bank_account")
    if "bank_account_name" in data:
        incoming_account_name = data["bank_account_name"]
        if incoming_account_name != masked_bank_fields["bank_account_name"]:
            school.bank_account_name = incoming_account_name
            changed_fields.append("bank_account_name")
            bank_fields_changed.append("bank_account_name")
    if "bank_branch" in data:
        incoming_bank_branch = data["bank_branch"]
        if incoming_bank_branch != masked_bank_fields["bank_branch"]:
            school.bank_branch = incoming_bank_branch
            changed_fields.append("bank_branch")
            bank_fields_changed.append("bank_branch")

    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()
    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)
    if "country_code" in data:
        settings.country_code = (data["country_code"] or "GH").upper()
        changed_fields.append("country_code")
    if "anniversary_date" in data:
        from datetime import datetime as dt
        if data["anniversary_date"]:
            # Parse date string to date object
            settings.anniversary_date = dt.strptime(data["anniversary_date"], "%Y-%m-%d").date()
        else:
            settings.anniversary_date = None
        changed_fields.append("anniversary_date")
    if "next_term_reopen_date" in data:
        next_term_reopen_date = (data.get("next_term_reopen_date") or "").strip()
        if next_term_reopen_date:
            from datetime import datetime as dt
            try:
                dt.strptime(next_term_reopen_date, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"message": "Invalid next_term_reopen_date format. Use YYYY-MM-DD."}), 400
        _set_report_global_setting(settings, "next_term_reopen_date", next_term_reopen_date or None)
        changed_fields.append("next_term_reopen_date")
    if "whatsapp_daily_limit" in data:
        settings.whatsapp_daily_limit = max(5, int(data.get("whatsapp_daily_limit") or 50))
        changed_fields.append("whatsapp_daily_limit")
    if "whatsapp_notifications_enabled" in data:
        settings.whatsapp_notifications_enabled = bool(data.get("whatsapp_notifications_enabled", True))
        changed_fields.append("whatsapp_notifications_enabled")

    log_action(
        actor_id,
        g.school_id,
        "SETTINGS_UPDATE",
        json.dumps(
            {
                "updated_fields": changed_fields,
                "ip": request.remote_addr,
            }
        ),
    )

    if bank_fields_changed:
        log_action(
            actor_id,
            g.school_id,
            "BANK_DETAILS_UPDATED",
            json.dumps(
                {
                    "updated_fields": bank_fields_changed,
                    "contains_sensitive_data": True,
                    "ip": request.remote_addr,
                }
            ),
        )
    db.session.commit()
    return jsonify({"message": "Settings updated."})


@api.route("/school/fees", methods=["POST"])
@multi_tenant_guard
@role_required("proprietor")
@jwt_required()
def update_school_fees():
    """Updates school fee configuration (tuition, feeding, uniform, transport, etc.)."""
    data = request.json
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)

    if "tuition_fee" in data:
        settings.tuition_fee = (
            float(data["tuition_fee"]) if data["tuition_fee"] else 0.0
        )
    if "feeding_fee" in data:
        settings.feeding_fee = (
            float(data["feeding_fee"]) if data["feeding_fee"] else 0.0
        )
    # Uniform fee is now managed through inventory pricing, not school fee settings.
    settings.uniform_fee = 0.0
    if "transport_fee" in data:
        settings.transport_fee = (
            float(data["transport_fee"]) if data["transport_fee"] else 0.0
        )
    if "terminal_report_fee" in data:
        settings.terminal_report_fee = (
            float(data["terminal_report_fee"]) if data["terminal_report_fee"] else 0.0
        )
    if "other_fees" in data:
        settings.other_fees = (
            data["other_fees"] if isinstance(data["other_fees"], dict) else {}
        )

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "FEES_UPDATE",
        f"Updated school fees: Tuition={settings.tuition_fee}, Feeding={settings.feeding_fee}, Transport={settings.transport_fee}",
    )
    db.session.commit()
    return jsonify({"message": "Fees updated successfully."})


@api.route("/school/fees", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_school_fees():
    """Retrieves school fee configuration."""
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        # Return default fees if not configured
        return jsonify(
            {
                "tuition_fee": 0.0,
                "feeding_fee": 0.0,
                "uniform_fee": 0.0,
                "transport_fee": 0.0,
                "terminal_report_fee": 0.0,
                "other_fees": {},
            }
        )

    return jsonify(
        {
            "tuition_fee": settings.tuition_fee or 0.0,
            "feeding_fee": settings.feeding_fee or 0.0,
            "uniform_fee": 0.0,
            "transport_fee": settings.transport_fee or 0.0,
            "terminal_report_fee": settings.terminal_report_fee or 0.0,
            "other_fees": settings.other_fees or {},
        }
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
    data = request.json

    # Validate input
    class_score_max = data.get("class_score_max")
    exam_score_max = data.get("exam_score_max")

    if class_score_max is None or exam_score_max is None:
        return (
            jsonify(
                {"message": "Both class_score_max and exam_score_max are required"}
            ),
            400,
        )

    # Ensure they're integers
    try:
        class_score_max = int(class_score_max)
        exam_score_max = int(exam_score_max)
    except (ValueError, TypeError):
        return jsonify({"message": "Scores must be valid integers"}), 400

    # Validate that they add up to 100
    if class_score_max + exam_score_max != 100:
        return (
            jsonify({"message": "Class score and exam score must add up to 100"}),
            400,
        )

    # Validate positive values
    if class_score_max < 0 or exam_score_max < 0:
        return jsonify({"message": "Scores must be positive"}), 400

    # Get or create school settings
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        settings = SchoolSettings(school_id=g.school_id)
        db.session.add(settings)

    # Update grading scheme
    settings.class_score_max = class_score_max
    settings.exam_score_max = exam_score_max

    log_action(
        int(get_jwt_identity()),
        g.school_id,
        "GRADING_SCHEME_UPDATE",
        f"Updated grading scheme to {class_score_max}/{exam_score_max}",
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Grading scheme updated successfully",
            "class_score_max": class_score_max,
            "exam_score_max": exam_score_max,
        }
    )


@api.route("/school/grading-scheme", methods=["GET"])
@multi_tenant_guard
@jwt_required()
def get_grading_scheme():
    """Retrieves current grading scheme configuration."""
    settings = SchoolSettings.query.filter_by(school_id=g.school_id).first()

    if not settings:
        # Return default values
        return jsonify({"class_score_max": 30, "exam_score_max": 70})

    return jsonify(
        {
            "class_score_max": settings.class_score_max or 30,
            "exam_score_max": settings.exam_score_max or 70,
        }
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
            "display_name": plan_name.replace(" Tier", "").replace("Basic", "Basic"),
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
            "popular": plan_name == "Basic",  # Mark Basic as most popular
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

    current_students = Student.query.filter_by(school_id=g.school_id, status='Active').count()
    current_classes = (
        len(school.academic_classes) if hasattr(school, "academic_classes") else 0
    )

    effective_plan = get_effective_plan(school)
    plan_info = PLAN_FEATURES.get(effective_plan, PLAN_FEATURES["Free Tier"])
    plan_display = FEATURE_MATRIX_DISPLAY.get(effective_plan, {})
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
    
    # Get enabled modules from settings
    enabled_modules = {}
    if school.settings:
        enabled_modules = school.settings.enabled_modules or {}

    return jsonify(
        {
            "plan": effective_plan,
            "subscription_plan": effective_plan,  # Explicit alias for clarity
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
            "features": plan_info.get("features", {}),
            "features_display": plan_display,
            "report_templates": plan_info.get("report_templates", []),
            "billing_visibility": billing_visibility,
            "pending_plan": getattr(school, "pending_plan", None),
        }
    )


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
        
        # Get proprietor email
        proprietor = User.query.filter_by(
            school_id=g.school_id, 
            role="proprietor"
        ).first()
        
        if not proprietor or not proprietor.email:
            return jsonify({"message": "Proprietor email not found"}), 400
        
        # Update subscription
        school.subscription_plan = new_plan
        school.subscription_status = "Active"
        school.next_billing_date = get_utc_now() + timedelta(days=30)
        db.session.commit()
        
        # Get plan details
        from backend.subscription_features import PLAN_FEATURES
        plan_info = PLAN_FEATURES.get(new_plan, {})
        
        # Generate upgrade confirmation email
        upgrade_date = get_utc_now().strftime("%Y-%m-%d")
        next_billing_date = school.next_billing_date.strftime("%Y-%m-%d")
        
        # Format features list
        features = plan_info.get("features", {})
        features_list = "\n".join([f"✅ {key.replace('_', ' ').title()}" for key in features.keys()])
        
        # Format usage limits  
        max_students = plan_info.get("max_students", 50)
        max_classes = plan_info.get("max_classes", 1)
        usage_limits = f"Students: {max_students if max_students != float('inf') else 'Unlimited'}\nClasses: {max_classes if max_classes != float('inf') else 'Unlimited'}"
        
        # Get new features not in previous plan
        prev_plan_info = PLAN_FEATURES.get(previous_plan, {})
        prev_features = set(prev_plan_info.get("features", {}).keys())
        new_features_set = set(features.keys()) - prev_features
        new_features = "\n".join([f"✨ {f.replace('_', ' ').title()}" for f in new_features_set]) if new_features_set else "Access to all features in your new plan"
        
        upgrade_subject, upgrade_body = get_subscription_upgrade_email(
            school_name=school.name,
            previous_plan=previous_plan,
            plan_name=new_plan,
            upgrade_date=upgrade_date,
            price=plan_info.get("price", "Contact Sales"),
            billing_cycle="month",
            new_features=new_features or "Enhanced features and capabilities",
            removed_limitations="Increased student and staff limits",
            new_usage_limits=usage_limits,
            new_resources="Check dashboard for training materials",
            feature_highlights="Your school can now do more with EduPulse SMT",
            support_email="support@edupulse.com",
            support_phone="+233-XXX-XXX-XXXX",
            next_billing_date=next_billing_date,
            invoice_url=f"{os.getenv('FRONTEND_URL', 'http://localhost:5173')}/billing/invoices"
        )
        
        if upgrade_subject and upgrade_body:
            send_email_notification(
                to_email=proprietor.email,
                subject=upgrade_subject,
                body=upgrade_body,
                attachments=IMPORT_TEMPLATE_ATTACHMENTS,
            )
        
        logger.info(f"School {g.school_id} upgraded from {previous_plan} to {new_plan}")
        return jsonify({
            "message": f"Upgraded to {new_plan} successfully.",
            "plan": new_plan,
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

    return jsonify({
        "is_active": bool(trial.get("is_active") or trial.get("active")),
        "plan": trial.get("plan"),
        "start_date": trial.get("start_date"),
        "end_date": trial.get("end_date"),
        "has_used_trial": has_used_trial,
        "trial_ended_at": school.trial_end_date.isoformat() if school.trial_end_date else None,
    }), 200


@api.route("/school/subscription/trial/activate", methods=["POST"])
@multi_tenant_guard
@jwt_required()
@role_required("proprietor")
def activate_subscription_trial():
    """Activate premium trial entitlement for this tenant."""
    data = request.get_json(silent=True) or {}
    days = int(data.get("days", 30) or 30)

    result = activate_premium_trial(g.school_id, days=days)
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
        
        return jsonify({
            "terms": [term.to_dict() for term in terms],
            "count": len(terms)
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
        
        # TODO: Add checks for associated data (grades, attendance, etc.)
        # For now, allow deletion
        
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
    """Activate a specific term (deactivates all others) and trigger billing if applicable."""
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
        
        # Deactivate all other terms
        AcademicTerm.query.filter_by(
            school_id=g.school_id,
            is_active=True
        ).update({"is_active": False})
        
        # Activate this term
        term.is_active = True
        db.session.commit()
        
        logger.info(f"Activated term {term_id} ({term.name} {term.academic_year}) for school {g.school_id}")
        
        # Trigger billing for paid plans
        billing_initiated = False
        payment_link = None
        
        effective_plan = get_effective_plan(school)
        if effective_plan != "Free Tier":
            try:
                # Count active students
                num_students = Student.query.filter_by(
                    school_id=g.school_id,
                    status='Active'
                ).count()
                
                if num_students > 0:
                    # Calculate term cost
                    term_cost = calculate_term_cost(effective_plan, num_students)
                    
                    if term_cost > 0:
                        # Get proprietor for email
                        proprietor = User.query.filter_by(
                            school_id=g.school_id,
                            role="proprietor"
                        ).first()
                        
                        if proprietor and proprietor.email:
                            # Generate invoice number
                            from datetime import datetime
                            invoice_number = f"INV-{g.school_id}-{term.id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            
                            # Attempt auto-charge first; fallback to payment link.
                            from backend.paystack_integration import (
                                initialize_termly_payment,
                                charge_authorization,
                                PaystackError,
                            )
                            
                            try:
                                billing_due_date = term.billing_due_date or (term.end_date if term.end_date else None)
                                auto_cfg = _normalize_auto_billing_config(_get_auto_billing_config(g.school_id))
                                auto_enabled = bool(auto_cfg.get("enabled", False))
                                default_card = _get_default_saved_card(auto_cfg)
                                auto_auth_code = (default_card or {}).get("authorization_code")
                                auto_email = (default_card or {}).get("customer_email") or proprietor.email

                                if auto_enabled and auto_auth_code and auto_email:
                                    auto_result = charge_authorization(
                                        email=auto_email,
                                        amount_cents=int(round(term_cost * 100)),
                                        authorization_code=auto_auth_code,
                                        metadata={
                                            "school_id": g.school_id,
                                            "plan_name": effective_plan,
                                            "billing_type": "termly_auto",
                                            "academic_term_id": term.id,
                                            "num_students": num_students,
                                            "term_name": term.name,
                                            "academic_year": term.academic_year,
                                        },
                                    )

                                    reference = auto_result.get("reference") or f"AUTO-{g.school_id}-{term.id}-{int(time.time())}"
                                    ledger_entry = LedgerEntry(
                                        school_id=g.school_id,
                                        tx_type="subscription",
                                        tx_ref=reference,
                                        description=f"Auto-billed subscription for {term.name} {term.academic_year}",
                                        amount=term_cost,
                                        status="Completed",
                                    )
                                    db.session.add(ledger_entry)
                                    payment_link = None
                                    billing_initiated = True
                                    logger.info(
                                        f"Auto-billing successful for school {g.school_id}: ₵{term_cost} ({reference})"
                                    )
                                    _append_billing_timeline_event(
                                        g.school_id,
                                        event_type="auto_charge_success",
                                        status="success",
                                        title="Automatic term billing succeeded",
                                        details=f"Charged saved card for {term.name} {term.academic_year}.",
                                        amount=term_cost,
                                        reference=reference,
                                        due_date=billing_due_date.isoformat() if billing_due_date else None,
                                    )
                                else:
                                    payment_result = initialize_termly_payment(
                                        email=proprietor.email,
                                        plan_name=effective_plan,
                                        school_id=g.school_id,
                                        num_students=num_students,
                                        academic_term_id=term.id
                                    )

                                    payment_link = payment_result['authorization_url']
                                    reference = payment_result['reference']

                                    ledger_entry = LedgerEntry(
                                        school_id=g.school_id,
                                        tx_type="subscription",
                                        tx_ref=reference,
                                        description=f"Subscription fee for {term.name} {term.academic_year}",
                                        amount=term_cost,
                                        status="Pending"
                                    )
                                    db.session.add(ledger_entry)
                                    _append_billing_timeline_event(
                                        g.school_id,
                                        event_type="manual_payment_link_created",
                                        status="pending",
                                        title="Manual payment required",
                                        details="No active auto-billing card was available. Payment link generated.",
                                        amount=term_cost,
                                        reference=reference,
                                        due_date=billing_due_date.isoformat() if billing_due_date else None,
                                        next_retry_at=(get_utc_now() + timedelta(days=1)).isoformat(),
                                        metadata={"payment_link": payment_link},
                                    )
                                
                                # Update school next_billing_date
                                if billing_due_date:
                                    school.next_billing_date = datetime.combine(
                                        billing_due_date,
                                        datetime.min.time()
                                    )
                                
                                db.session.commit()
                                
                                # Send billing notification email
                                # Get pricing info
                                pricing_info = PRICING.get(effective_plan, {})
                                rate_per_student = pricing_info.get("per_student_per_term", 0)
                                base_fee = pricing_info.get("base_fee_per_term", 0)
                                included_students = pricing_info.get("included_students", 0)
                                
                                # Build features list
                                plan_info = PLAN_FEATURES.get(effective_plan, {})
                                features = plan_info.get("features", {})
                                features_list = "\n".join([
                                    f"• {k.replace('_', ' ').title()}: {v}" 
                                    for k, v in features.items() 
                                    if v not in [False, None]
                                ][:8])  # Top 8 features
                                
                                # Calculate breakdown
                                billable_stu = max(0, num_students - included_students)
                                student_overage = billable_stu * rate_per_student
                                
                                subject, body = get_term_billing_notification_email(
                                    school_name=school.school_name,
                                    proprietor_name=proprietor.username,
                                    term_name=term.name,
                                    academic_year=term.academic_year,
                                    invoice_number=invoice_number,
                                    billing_date=datetime.now().strftime("%B %d, %Y"),
                                    due_date=billing_due_date.strftime("%B %d, %Y") if billing_due_date else "TBD",
                                    plan_name=effective_plan,
                                    num_students=num_students,
                                    rate_per_student=f"{rate_per_student:.2f}",
                                    term_cost=f"{term_cost:.2f}",
                                    term_start_date=term.start_date.strftime("%B %d, %Y") if term.start_date else "TBD",
                                    vacation_date=term.end_date.strftime("%B %d, %Y") if term.end_date else "TBD",
                                    reopening_date=billing_due_date.strftime("%B %d, %Y") if billing_due_date else "TBD",
                                    payment_link=payment_link,
                                    features_list=features_list,
                                    support_email="support@edupulse.com",
                                    support_phone="+233 XX XXX XXXX",
                                    dashboard_url=f"{request.host_url}proprietor",
                                    base_fee=f"{base_fee:.2f}",
                                    included_students=included_students,
                                    billable_students=billable_stu,
                                    student_overage_cost=f"{student_overage:.2f}"
                                )
                                
                                if subject and body:
                                    send_email_notification(
                                        to_email=proprietor.email,
                                        subject=subject,
                                        body=body
                                    )
                                
                                billing_initiated = True
                                logger.info(f"Billing initiated for term {term_id}: ₵{term_cost} for {num_students} students")
                            
                            except PaystackError as e:
                                logger.error(f"Paystack error during term activation billing: {str(e)}")
                                safe_due = locals().get("billing_due_date")
                                _append_billing_timeline_event(
                                    g.school_id,
                                    event_type="auto_charge_failed",
                                    status="failed",
                                    title="Automatic term billing failed",
                                    details=str(e),
                                    amount=term_cost,
                                    due_date=safe_due.isoformat() if safe_due else None,
                                    next_retry_at=(get_utc_now() + timedelta(days=1)).isoformat(),
                                )
                                # Continue anyway - activation succeeds even if billing fails
                            except Exception as e:
                                logger.error(f"Error processing billing for term activation: {str(e)}")
                                safe_due = locals().get("billing_due_date")
                                _append_billing_timeline_event(
                                    g.school_id,
                                    event_type="billing_processing_error",
                                    status="failed",
                                    title="Billing processing error",
                                    details=str(e),
                                    amount=term_cost,
                                    due_date=safe_due.isoformat() if safe_due else None,
                                    next_retry_at=(get_utc_now() + timedelta(days=1)).isoformat(),
                                )
                                # Continue anyway
                        else:
                            logger.warning(f"No proprietor email found for billing notification")
                    else:
                        logger.info(f"Term cost is 0, skipping billing")
                else:
                    logger.info(f"No active students, skipping billing")
            except Exception as e:
                logger.error(f"Error in billing logic: {str(e)}")
                # Continue anyway - activation succeeds even if billing fails
        
        response = {
            "message": f"Activated {term.name} {term.academic_year}",
            "term": term.to_dict(),
            "billing_initiated": billing_initiated
        }
        
        if payment_link:
            response["payment_link"] = payment_link
            response["billing_message"] = f"Invoice generated for ₵{term_cost:.2f}. Payment link sent to proprietor email."
        
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
    admin_email = os.getenv("FOUNDER_EMAIL", "danielasareanyinam2020@gmail.com")
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
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
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
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json
    ticket = SupportTicket.query.get_or_404(ticket_id)

    ticket.admin_response = data.get("response")
    ticket.status = data.get("status", "Resolved")  # Allow 'In Progress' or 'Resolved'
    db.session.commit()

    log_action(user.id, ticket.school_id, "ADMIN_TICKET_REPLY", f"Super admin replied to ticket #{ticket.id}")

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
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
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
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
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

    log_action(user.id, None, "ADMIN_BROADCAST", f"Broadcast sent: {data.get('message')[:80]}")
    return jsonify({"message": "System alert broadcasted."})


@api.route("/admin/schools", methods=["GET"])
@jwt_required()
def get_all_schools():
    """Super Admin: List all tenants."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    schools = School.query.all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "plan": s.subscription_plan,
                "status": s.subscription_status,
                "is_active": s.is_active,
            }
            for s in schools
        ]
    )


@api.route("/admin/school/<school_id>/toggle", methods=["POST"])
@jwt_required()
def toggle_school_status(school_id):
    """Super Admin: Enable/Disable a school."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    db.session.commit()
    status = "activated" if school.is_active else "suspended"

    log_action(user.id, school.id, "ADMIN_SCHOOL_STATUS", f"School {school.id} {status} by super-admin")
    return jsonify({"message": f"School {school.name} has been {status}."})


@api.route("/admin/school/<school_id>/modules", methods=["POST"])
@jwt_required()
def update_school_modules(school_id):
    """Super Admin: Toggle feature flags for a school."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    school = School.query.get_or_404(school_id)
    if school.settings:
        school.settings.enabled_modules = request.json.get("modules")
        db.session.commit()

        log_action(user.id, school.id, "ADMIN_MODULE_UPDATE", f"Modules updated for school {school.id}: {school.settings.enabled_modules}")
    return jsonify({"message": "Modules updated."})


@api.route("/admin/global-analytics", methods=["GET"])
@jwt_required()
def get_global_analytics():
    """Super Admin: View aggregated platform stats."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    total_revenue = (
        db.session.query(db.func.sum(Payment.amount))
        .filter(Payment.status == "Confirmed")
        .scalar()
        or 0
    )
    total_schools = School.query.count()
    total_students = Student.query.count()

    log_action(user.id, None, "ADMIN_GLOBAL_ANALYTICS", "Super admin viewed global analytics")

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
    user_id = get_jwt_identity()
    admin_user = User.query.get(user_id)
    if admin_user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    target_school = School.query.get_or_404(school_id)
    target_user = User.query.filter_by(school_id=school_id, role="proprietor").first()

    if not target_user:
        return jsonify({"message": "No proprietor account found for this school."}), 404

    access_token = create_access_token(identity=str(target_user.id))

    log_action(admin_user.id, target_school.id, "ADMIN_IMPERSONATE", f"Impersonated proprietor {target_user.username} for school {school_id}")

    return jsonify(
        {"token": access_token, "school_id": target_school.id, "role": target_user.role}
    )


@api.route("/admin/school/<school_id>/trial", methods=["POST"])
@jwt_required()
def grant_school_trial(school_id):
    """Super Admin: Grant a time-bound trial plan to a school."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
        return jsonify({"message": "Unauthorized"}), 403

    data = request.json or {}
    trial_plan = data.get("trial_plan", "Premium")
    months = int(data.get("trial_months", 6))

    school = School.query.get_or_404(school_id)
    school.trial_plan = trial_plan
    school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=30 * months)
    school.subscription_status = "Trial"
    db.session.commit()

    log_action(user.id, school.id, "ADMIN_TRIAL_GRANT", f"Granted {trial_plan} trial for {months} months to school {school.id}")

    return jsonify(
        {
            "message": f"Trial granted: {trial_plan} for {months} months",
            "trial_plan": school.trial_plan,
            "trial_end": school.trial_end_date.strftime("%Y-%m-%d"),
        }
    )


@api.route("/admin/backup", methods=["GET"])
@jwt_required()
def download_backup():
    """Super Admin: Download SQL Dump."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.role != "super_admin":
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

    log_action(user.id, None, "ADMIN_BACKUP_DOWNLOAD", "Super admin downloaded database backup")

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
    Includes PRORATED BILLING for mid-term upgrades!
    
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
        billing_period = data.get('billing_period', 'term')  # 'term' or 'annual'
        default_student_count = Student.query.filter_by(school_id=school.id).count()
        student_count = data.get('student_count', default_student_count)
        amount_cedis = data.get('amount_cedis')
        email = data.get('email') or user.email
        
        if not plan_name or not email:
            return jsonify({"message": "Missing required fields: plan_name, email"}), 400
        
        if not amount_cedis or amount_cedis <= 0:
            return jsonify({"message": "Invalid amount"}), 400
        
        # Model A Pricing: Base Fee + Included Students + Overage
        pricing = {
            'Basic': {
                'base_fee': 360,          # GH₵ 360 base per term
                'included_students': 30,  # 30 students included
                'overage_rate': 12        # GH₵ 12 per extra student
            },
            'Premium': {
                'base_fee': 510,          # GH₵ 510 base per term
                'included_students': 30,  # 30 students included
                'overage_rate': 17        # GH₵ 17 per extra student
            }
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
        
        # ===== PRORATION LOGIC FOR MID-TERM UPGRADES =====
        # Calculate remaining days in current billing period
        days_per_term = 120  # ~4 months
        now = datetime.now(timezone.utc)
        
        # Get days remaining until next billing
        proration_data = {
            'is_prorated': False,
            'days_remaining': days_per_term,
            'days_in_period': days_per_term,
            'proration_ratio': 1.0
        }
        
        next_billing_date = school.next_billing_date
        if next_billing_date and next_billing_date.tzinfo is None:
            next_billing_date = next_billing_date.replace(tzinfo=timezone.utc)

        if next_billing_date and next_billing_date > now:
            # Calculate days remaining in current billing period
            days_remaining = (next_billing_date - now).days
            
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
                    'prorated_cost': round(prorated_cost, 2)
                }
                amount_cedis = prorated_cost
        
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
                    'base_fee': plan_config['base_fee'],
                    'overage_rate': plan_config['overage_rate'],
                    'included_students': plan_config['included_students'],
                    'overage_count': overage_count,
                    'amount_cedis': amount_cedis,
                    'callback_url': callback_url,
                    'proration_data': proration_data
                }
            )
            
            log_msg = f"Payment initialized for school {school.id} ({school.name}): {plan_name}, {student_count} students, GH₵ {amount_cedis}"
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

            _append_billing_timeline_event(
                school.id,
                event_type="subscription_payment_verified",
                status="success",
                title="Subscription payment verified",
                details=f"Payment for {plan_name} processed successfully.",
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
                "message": "Payment verified and subscription updated",
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

                result = process_payment_confirmation(school_id, plan_name, amount_paid, reference=reference)
                _save_reusable_authorization(
                    school_id,
                    transaction.get("authorization") or {},
                    (transaction.get("customer") or {}).get("email"),
                )
                _append_billing_timeline_event(
                    school_id,
                    event_type="subscription_payment_webhook",
                    status="success",
                    title="Subscription payment received",
                    details=f"Webhook payment captured for {plan_name} plan.",
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
        from backend.api.models import Student
        num_students = Student.query.filter_by(school_id=g.school_id, status='Active').count()
        
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

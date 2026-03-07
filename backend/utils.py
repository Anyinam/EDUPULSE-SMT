import logging
import mimetypes
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def send_email_notification(to_email, subject, body, attachments=None):
    """Send actual email notification to staff via Flask-Mail."""
    try:
        from flask_mail import Message
        from backend.api.api import mail

        msg = Message(subject=subject, recipients=[to_email], body=body)

        if attachments:
            for file_path in attachments:
                try:
                    if not os.path.exists(file_path):
                        logger.warning(f"Attachment not found: {file_path}")
                        continue
                    filename = os.path.basename(file_path)
                    mime_type, _ = mimetypes.guess_type(filename)
                    content_type = mime_type or "application/octet-stream"
                    with open(file_path, "rb") as f:
                        msg.attach(filename=filename, content_type=content_type, data=f.read())
                except Exception as attachment_err:
                    logger.error(f"Failed to attach file {file_path}: {str(attachment_err)}")

        mail.send(msg)
        logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        logger.error(
            f"Email config - Server: {logger.manager.loggerDict}, Port: {os.getenv('MAIL_PORT')}"
        )
        # Fall back to console in development
        print(f"[EMAIL] To: {to_email} | Subject: {subject}\nBody: {body}\n")
        raise


def get_utc_now():
    """Returns current UTC time."""
    return datetime.now(timezone.utc)


def calculate_academic_health(student_id):
    """
    Real logic for Sack-Risk based on Financial & Academic data.
    Weighted Algorithm: 60% Financial (Revenue Protection), 40% Academic.
    """
    from backend.api.models import Student, StudentGrade

    student = Student.query.get(student_id)
    if not student:
        return {"score": 0, "status": "Unknown", "unpaid_days": 0}

    # 1. Financial Health (60% weight)
    financial_score = 100
    if student.total_tuition_owed > 0:
        financial_score -= 40  # Immediate penalty for outstanding debt
        if student.total_tuition_owed > 500:
            financial_score -= 30  # Heavy debt penalty

    if not student.feeding_paid:
        financial_score -= 10

    # 2. Academic Health (40% weight)
    grades = StudentGrade.query.filter_by(
        student_id=student.id, is_finalized=True
    ).all()
    if grades:
        avg_score = sum(g.total_score for g in grades) / len(grades)
        academic_score = avg_score
    else:
        academic_score = 50  # Neutral start if no grades yet

    # Combined Risk Score (0-100, where 100 is Safe)
    total_risk_score = (financial_score * 0.6) + (academic_score * 0.4)

    status = "Safe"
    if total_risk_score < 50:
        status = "Critical"
    elif total_risk_score < 70:
        status = "At Risk"

    return {
        "score": int(total_risk_score),
        "status": status,
        "unpaid_days": 30 if student.total_tuition_owed > 0 else 0,  # Estimated days
    }


def generate_descriptive_analysis(student_id):
    """
    Generate comprehensive performance analysis including multi-term trends.
    Analyzes current performance + trends from previous terms.
    """
    from backend.api.models import ReportCard, Student, StudentGrade

    student = Student.query.get(student_id)
    if not student:
        return "Student not found."

    # Get all reports for this student (all terms/years)
    all_reports = (
        ReportCard.query.filter_by(student_id=student_id)
        .order_by(ReportCard.academic_year.asc(), ReportCard.academic_term.asc())
        .all()
    )

    if not all_reports:
        return f"{student.name} has no finalized reports yet."

    # Get current (latest) report
    current_report = all_reports[-1]

    # Extract term averages across all reports
    term_history = []
    for report in all_reports:
        if report.term_average is not None:
            term_history.append(
                {
                    "term": report.academic_term,
                    "year": report.academic_year,
                    "average": float(report.term_average),
                    "position": report.overall_position,
                    "out_of": report.out_of_students,
                }
            )

    # Keep only distinct term-year snapshots (latest saved report wins per term-year)
    distinct_term_map = {}
    for snapshot in term_history:
        key = (snapshot["year"], snapshot["term"])
        distinct_term_map[key] = snapshot
    distinct_term_history = sorted(
        distinct_term_map.values(), key=lambda item: (item["year"], item["term"])
    )

    # Calculate trend
    trend = "stable"
    trend_text = ""
    if len(distinct_term_history) >= 2:
        last_avg = distinct_term_history[-1]["average"]
        previous_avg = distinct_term_history[-2]["average"]
        diff = last_avg - previous_avg

        if diff > 5:
            trend = "improving"
            trend_text = f"showing improvement of {diff:.1f}% from last term"
        elif diff < -5:
            trend = "declining"
            trend_text = f"showing decline of {abs(diff):.1f}% from last term"
        else:
            trend = "stable"
            trend_text = "maintaining consistent performance"

    # Analyze current strengths/weaknesses
    current_grades = current_report.subject_grades or []
    strengths = [
        g.get("subject") for g in current_grades if float(g.get("total", 0)) >= 70
    ]
    weaknesses = [
        g.get("subject") for g in current_grades if float(g.get("total", 0)) < 50
    ]

    # Build comprehensive narrative
    narrative_parts = []

    # Main performance statement
    current_avg = current_report.term_average or 0
    position_text = f"ranked {current_report.overall_position} out of {current_report.out_of_students}"
    narrative_parts.append(
        f"{student.name} achieved an average of {current_avg:.1f}% in {current_report.academic_term} "
        f"{current_report.academic_year}, {position_text}."
    )

    # Trend analysis
    if len(distinct_term_history) >= 2:
        narrative_parts.append(f"Trend: {trend_text}.")

        # History summary
        if len(distinct_term_history) >= 3:
            early_avg = distinct_term_history[0]["average"]
            change = current_avg - early_avg
            if change > 0:
                narrative_parts.append(
                    f"Overall growth from {early_avg:.1f}% ({distinct_term_history[0]['term']} {distinct_term_history[0]['year']}) "
                    f"to {current_avg:.1f}% shows positive academic trajectory."
                )
            elif change < 0:
                narrative_parts.append(
                    f"Performance declined from {early_avg:.1f}% ({distinct_term_history[0]['term']} {distinct_term_history[0]['year']}) "
                    f"to {current_avg:.1f}%. Additional support may be beneficial."
                )

    # Subject-specific insights
    if strengths:
        narrative_parts.append(f"Excels in {', '.join(strengths)}.")

    if weaknesses:
        narrative_parts.append(f"Requires improvement in {', '.join(weaknesses)}.")
    elif strengths:
        narrative_parts.append("Demonstrates consistent strength across most subjects.")

    # Attendance impact
    if current_report.attendance_percentage:
        attendance = float(current_report.attendance_percentage)
        if attendance >= 95:
            narrative_parts.append(
                f"Excellent attendance ({attendance:.0f}%) reflects strong commitment."
            )
        elif attendance >= 80:
            narrative_parts.append(
                f"Good attendance ({attendance:.0f}%) supports learning continuity."
            )
        elif attendance < 70:
            narrative_parts.append(
                f"Low attendance ({attendance:.0f}%) may be impacting academic progress."
            )

    # Recommendations
    if trend == "declining":
        narrative_parts.append(
            "Recommend intervention and academic support to reverse downward trend."
        )
    elif trend == "improving":
        narrative_parts.append(
            "Continue current efforts to maintain positive momentum."
        )
    else:
        if strengths:
            narrative_parts.append(
                "Build on existing strengths while addressing weaker areas."
            )
        else:
            narrative_parts.append(
                "Focus on consistent effort across all subjects for improvement."
            )

    return " ".join(narrative_parts)


def parse_payment_reference(reference_string):
    """
    Parse payment reference to extract student code and payment category.

    Reference Format: STUDENT_CODE-CATEGORY
    Valid Categories:
    - T1, T2, T3 → Tuition (Term 1, 2, 3)
    - FEED-DAY, FEED-WEK, FEED-MON → Feeding (Daily, Weekly, Monthly)
    - UNIF → Uniform
    - INV-ITEMCODE[-SIZE][-TYPE] → Inventory item
    - TRANS-MON, TRANS-REG → Transport

    Examples:
    - "S001-T1" → {"student_code": "S001", "payment_type": "Tuition", "category": {"term": "Term 1"}}
    - "S001-FEED-MON" → {"student_code": "S001", "payment_type": "Feeding", "category": {"frequency": "Monthly"}}
    - "S001-UNIF" → {"student_code": "S001", "payment_type": "Uniform", "category": {"item": "School Uniform"}}
    - "S001-TRANS-MON" → {"student_code": "S001", "payment_type": "Transport", "category": {"frequency": "Monthly"}}
    """
    if not reference_string or "-" not in reference_string:
        return None

    parts = reference_string.upper().strip().split("-")
    student_code = parts[0]

    if len(parts) < 2:
        return None

    category_code = parts[1]

    # Map category codes to payment types and categories
    category_map = {
        "T1": ("Tuition", {"term": "Term 1"}),
        "T2": ("Tuition", {"term": "Term 2"}),
        "T3": ("Tuition", {"term": "Term 3"}),
        "FEED": ("Feeding", {"frequency": "General"}),  # Default if not specified
    }

    # Feeding with frequency
    if category_code == "FEED":
        if len(parts) >= 3:
            freq_code = parts[2]
            freq_map = {"DAY": "Daily", "WEK": "Weekly", "MON": "Monthly"}
            frequency = freq_map.get(freq_code, "Monthly")
            return {
                "student_code": student_code,
                "payment_type": "Feeding",
                "category": {"frequency": frequency},
            }
        else:
            return {
                "student_code": student_code,
                "payment_type": "Feeding",
                "category": {"frequency": "Monthly"},  # Default to monthly
            }

    # Uniform
    if category_code == "UNIF":
        return {
            "student_code": student_code,
            "payment_type": "Uniform",
            "category": {"item": "School Uniform"},
        }

    # Inventory item
    if category_code == "INV":
        item_code = parts[2] if len(parts) >= 3 else None
        size = parts[3] if len(parts) >= 4 else None
        item_type = parts[4] if len(parts) >= 5 else None
        category = {"item_code": item_code} if item_code else {}
        if size:
            category["size"] = size
        if item_type:
            category["item_type"] = item_type
        return {
            "student_code": student_code,
            "payment_type": "Inventory",
            "category": category,
        }

    # Transport
    if category_code == "TRANS":
        if len(parts) >= 3:
            freq_code = parts[2]
            freq_map = {"DAY": "Daily", "WEK": "Weekly", "MON": "Monthly"}
            frequency = freq_map.get(freq_code, "Monthly")
            return {
                "student_code": student_code,
                "payment_type": "Transport",
                "category": {"frequency": frequency},
            }
        else:
            return {
                "student_code": student_code,
                "payment_type": "Transport",
                "category": {"frequency": "Monthly"},
            }

    # Tuition codes
    if category_code in category_map:
        payment_type, category = category_map[category_code]
        return {
            "student_code": student_code,
            "payment_type": payment_type,
            "category": category,
        }

    # Unknown category, return just student code
    return {
        "student_code": student_code,
        "payment_type": "Tuition",
        "category": {"term": "General"},
    }


# ============================================================================
# PAYMENT REFERENCE CODE SYSTEM
# Format: {STUDENT_ID}{INDEX}
# Examples: CFK011 (Tuition + Terminal Report), CFK012 (Feeding), CFK013 (Uniform), CFK014 (Transport)
# Note: Terminal Report fee is now combined with Tuition fee since it's a small amount
# ============================================================================

PAYMENT_TYPE_INDEX = {
    "Tuition": 1,
    "Feeding": 2,
    "Uniform": 3,
    "Transport": 4,
}

INDEX_TO_PAYMENT_TYPE = {v: k for k, v in PAYMENT_TYPE_INDEX.items()}


def generate_payment_code(student_id, payment_type):
    """
    Generate a unique payment reference code.

    Args:
        student_id (str): Student ID (e.g., "CFK01")
        payment_type (str): Payment type (Tuition, Feeding, Uniform, Transport)

    Returns:
        str: Reference code (e.g., "CFK011")

    Example:
        >>> generate_payment_code("CFK01", "Tuition")
        "CFK011"
    """
    if payment_type not in PAYMENT_TYPE_INDEX:
        raise ValueError(
            f"Invalid payment type: {payment_type}. Must be one of {list(PAYMENT_TYPE_INDEX.keys())}"
        )

    index = PAYMENT_TYPE_INDEX[payment_type]
    return f"{student_id}{index}"


def generate_all_payment_codes(student_id, fees_config):
    """
    Generate all payment codes for a student based on school fees.

    Args:
        student_id (str): Student ID
        fees_config (dict): School fees configuration
            {
                "tuition_fee": 5000,
                "feeding_fee": 500,
                "uniform_fee": 300,
                "transport_fee": 200,
                "terminal_report_fee": 100,  # Combined with tuition
                "other_fees": {"Sports": 100, "Library": 50}
            }

    Returns:
        dict: Payment codes mapped to fee types with amounts
            {
                "Tuition": "CFK011",  # Includes terminal report fee
                "Feeding": "CFK012",
                "Uniform": "CFK013",
                "Transport": "CFK014",
                "Sports": "CFK015",
                "Library": "CFK016"
            }
    """
    codes = {}

    # Combine tuition and terminal report fees
    tuition_amount = fees_config.get("tuition_fee", 0) + fees_config.get("terminal_report_fee", 0)

    # Standard fees (terminal report is now combined with tuition)
    standard_fees = [
        ("Tuition", tuition_amount),
        ("Feeding", fees_config.get("feeding_fee", 0)),
        ("Uniform", fees_config.get("uniform_fee", 0)),
        ("Transport", fees_config.get("transport_fee", 0)),
    ]

    for fee_type, amount in standard_fees:
        if amount > 0:
            codes[fee_type] = generate_payment_code(student_id, fee_type)

    # Custom fees (starting from index 5 since Terminal Report was removed)
    other_fees = fees_config.get("other_fees", {})
    if isinstance(other_fees, dict):
        custom_index = 5
        for fee_name, amount in other_fees.items():
            if amount > 0:
                codes[fee_name] = f"{student_id}{custom_index}"
                custom_index += 1

    return codes


def parse_payment_code(reference_code):
    """
    Parse a payment reference code to extract student ID and payment type.

    Args:
        reference_code (str): Payment code (e.g., "CFK011")

    Returns:
        tuple: (student_id, payment_type)
            - student_id (str): e.g., "CFK01"
            - payment_type (str): e.g., "Tuition"

    Raises:
        ValueError: If code format is invalid

    Example:
        >>> parse_payment_code("CFK011")
        ("CFK01", "Tuition")
        >>> parse_payment_code("CFK012")
        ("CFK01", "Feeding")
    """
    if not isinstance(reference_code, str) or len(reference_code) < 2:
        raise ValueError(f"Invalid reference code format: {reference_code}")

    # Last character is the index
    last_char = reference_code[-1]
    student_id = reference_code[:-1]

    try:
        index = int(last_char)
    except ValueError:
        raise ValueError(f"Reference code must end with a digit. Got: {reference_code}")

    # Standard types use indices 1-5
    if index in INDEX_TO_PAYMENT_TYPE:
        payment_type = INDEX_TO_PAYMENT_TYPE[index]
        return student_id, payment_type
    elif index >= 6:
        # Custom fees are tracked differently
        # We need to query the school's fee configuration to map the index
        return student_id, None
    else:
        raise ValueError(f"Invalid payment type index: {index}")


def validate_payment_code(reference_code, student_id):
    """
    Validate that a reference code matches a student ID.

    Args:
        reference_code (str): Payment code
        student_id (str): Student ID to validate against

    Returns:
        bool: True if valid, False otherwise

    Example:
        >>> validate_payment_code("CFK011", "CFK01")
        True
        >>> validate_payment_code("CFK011", "ABC02")
        False
    """
    try:
        extracted_id, _ = parse_payment_code(reference_code)
        return extracted_id == student_id
    except ValueError:
        return False

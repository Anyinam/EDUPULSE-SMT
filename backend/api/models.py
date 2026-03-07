import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, select
from werkzeug.security import check_password_hash, generate_password_hash

from backend.security.crypto import EncryptedString

db = SQLAlchemy()

VALID_GRADES = [
    "Nursery",
    "KG",
    "Class 1",
    "Class 2",
    "Class 3",
    "Class 4",
    "Class 5",
    "Class 6",
    "JHS 1",
    "JHS 2",
    "JHS 3",
]


# ---------------------------------------------------------
# 1. THE TENANT (The School Business)
# Handles Branding & Business Rules from your notes
# ---------------------------------------------------------
class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.String(20), primary_key=True)  # e.g., 'CCA-OFK'
    name = db.Column(db.String(100), nullable=False)

    # Pillar 2: Branding (UI Configurability)
    logo_url = db.Column(
        db.Text
    )  # Changed from String(255) to Text to support base64-encoded images
    primary_color = db.Column(db.String(10), default="#1e3a8a")  # Hex Code
    motto = db.Column(db.String(255))

    # Contact Details for all documents
    school_email = db.Column(db.String(100))
    school_phone = db.Column(db.String(20))
    school_address = db.Column(db.String(255))
    school_website = db.Column(db.String(100))

    # Payment Account Details (optional for manual transfers)
    bank_name = db.Column(EncryptedString)  # Bank name (e.g., Fidelity Bank)
    bank_account = db.Column(EncryptedString)  # Bank account number
    bank_account_name = db.Column(EncryptedString)  # Account holder name
    bank_branch = db.Column(EncryptedString)  # Bank branch name

    # Subscription & Billing
    subscription_plan = db.Column(
        db.String(20), default="Free Tier"
    )  # Free, Basic, Premium
    subscription_status = db.Column(db.String(20), default="Active")
    next_billing_date = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    trial_plan = db.Column(db.String(20))
    trial_end_date = db.Column(db.DateTime)
    is_trial_active = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # Usage-based billing meter
    current_student_count = db.Column(db.Integer, default=0)
    last_metered_at = db.Column(db.DateTime)

    # Pricing versioning / grandfathering
    plan_version = db.Column(db.String(40))
    pricing_locked_at = db.Column(db.DateTime)
    custom_base_fee = db.Column(db.Float)
    custom_included_students = db.Column(db.Integer)
    custom_overage_rate = db.Column(db.Float)

    # Pillar 3: Business Rules (Custom Workflows)
    settings = db.relationship("SchoolSettings", backref="school", uselist=False)

    # Relationships
    users = db.relationship("User", backref="school", lazy=True)
    students = db.relationship("Student", backref="school", lazy=True)


class SchoolSettings(db.Model):
    __tablename__ = "school_settings"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    country_code = db.Column(db.String(2), default="GH")
    anniversary_date = db.Column(db.Date)  # School founding/anniversary date

    # Customizable Logic Thresholds
    sack_risk_threshold = db.Column(db.Integer, default=3)
    canteen_cutoff_time = db.Column(db.String(5), default="09:30")
    currency = db.Column(db.String(5), default="GH₵")
    enabled_modules = db.Column(
        db.JSON,
        default={
            "canteen": True,
            "admissions": True,
            "finance": True,
            "hr": True,
            "inventory": True,
        },
    )
    # Report template selection per tenant
    report_template_id = db.Column(db.String(50), default="gradman_v1")
    report_template_config = db.Column(db.JSON, default={})
    # Grading scheme configuration (flexible class/exam score split)
    class_score_max = db.Column(db.Integer, default=30)  # Max score for class work
    exam_score_max = db.Column(db.Integer, default=70)  # Max score for exam

    # Financial Fee Configuration (Proprietor-settable fees)
    tuition_fee = db.Column(db.Float, default=0.0)  # Annual or per-term tuition
    feeding_fee = db.Column(db.Float, default=0.0)  # Daily/monthly feeding allowance
    uniform_fee = db.Column(db.Float, default=0.0)  # Uniform cost per student
    transport_fee = db.Column(db.Float, default=0.0)  # Transport/transport allowance
    terminal_report_fee = db.Column(db.Float, default=0.0)  # Per-term report printing fee
    other_fees = db.Column(
        db.JSON, default={}
    )  # Flexible: {"Sports": 50.0, "Library": 25.0, etc.}
    
    # WhatsApp Cost Control
    whatsapp_daily_limit = db.Column(db.Integer, default=50)  # Max messages per day per school
    whatsapp_notifications_enabled = db.Column(db.Boolean, default=True)  # Master toggle for all WhatsApp sends


class SchoolHoliday(db.Model):
    __tablename__ = "school_holidays"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(100))
    is_holiday = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint(
            "school_id", "holiday_date", name="uq_school_holiday_date"
        ),
    )


class AcademicTerm(db.Model):
    """Academic Term Management - Foundation for Termly Billing.
    
    Ghana's typical academic calendar:
    - Term 1: September - December
    - Term 2: January - April
    - Term 3: May - July/August
    """
    __tablename__ = "academic_terms"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)  # "Term 1", "Term 2", "Term 3"
    academic_year = db.Column(db.String(20), nullable=False)  # "2025/2026"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)  # Only one active term per school
    billing_due_date = db.Column(db.Date)  # When subscription fees are due
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    
    # Relationships
    school = db.relationship("School", backref="academic_terms")
    creator = db.relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        db.UniqueConstraint(
            "school_id", "academic_year", "name", name="uq_school_term_year"
        ),
        db.CheckConstraint("end_date > start_date", name="ck_term_dates_valid"),
    )
    
    def to_dict(self):
        """Convert term to dictionary for API responses."""
        return {
            "id": self.id,
            "school_id": self.school_id,
            "name": self.name,
            "academic_year": self.academic_year,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "billing_due_date": self.billing_due_date.isoformat() if self.billing_due_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------
# 2. AUTHENTICATION (Business Credentials)
# Uses Staff/Business IDs rather than global provider IDs
# ---------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))

    # Pillar 1: Authentication
    username = db.Column(db.String(50), nullable=False)  # The Staff ID
    password_hash = db.Column(db.String(255), nullable=False)

    # Pillar 5: Multi-level Access Control
    role = db.Column(
        db.String(20), default="teacher"
    )  # proprietor, headmaster, finance, teacher
    roles = db.Column(db.JSON, default=list)
    assigned_class = db.Column(db.String(20))  # For Homeroom Teachers
    email = db.Column(EncryptedString)
    profile_picture = db.Column(db.Text())  # Base64 encoded image
    two_fa_enabled = db.Column(db.Boolean, default=False)
    two_fa_method = db.Column(db.String(20), default="email")
    last_login_at = db.Column(db.DateTime)
    terms_accepted_at = db.Column(db.DateTime)
    terms_version = db.Column(db.String(50))
    terms_accepted_ip = db.Column(db.String(64))
    
    # Temporary password tracking (for new staff accounts)
    is_temp_password = db.Column(db.Boolean, default=False)
    temp_password_expires_at = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)


class TeacherAssignment(db.Model):
    __tablename__ = "teacher_assignments"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship("User", backref="teaching_assignments")

    __table_args__ = (
        db.UniqueConstraint(
            "school_id",
            "teacher_id",
            "class_name",
            "subject_name",
            name="uq_teacher_assignment",
        ),
    )


# ---------------------------------------------------------
# 3. DATA SCHEMA ADAPTATION (Flexible Schemas)
# Includes "Custom Attributes" as requested in your notes
# ---------------------------------------------------------
class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))

    # Student name fields
    first_name = db.Column(db.String(50), nullable=False)
    surname = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # Full name (auto-generated from first_name + surname)
    gender = db.Column(db.String(10))  # Male, Female, Other
    date_of_birth = db.Column(db.Date)  # Student's date of birth
    
    student_code = db.Column(db.String(20), unique=True)
    is_present = db.Column(db.Boolean, default=False)
    feeding_paid = db.Column(db.Boolean, default=False)

    current_class = db.Column(db.String(20))
    guardian_name = db.Column(EncryptedString)
    # Added contact fields for proprietor communication
    parent_name = db.Column(EncryptedString)
    parent_phone = db.Column(EncryptedString)
    parent_email = db.Column(EncryptedString)

    # Financial Deadline Tracking
    total_tuition_owed = db.Column(db.Float, default=0.0)
    tuition_deadline = db.Column(db.DateTime)  # The "Installment Threshold"
    
    # Scholarship support
    is_on_scholarship = db.Column(db.Boolean, default=False)
    scholarship_covers_tuition = db.Column(db.Boolean, default=False)
    scholarship_covers_feeding = db.Column(db.Boolean, default=False)
    scholarship_notes = db.Column(db.String(255))

    # Class Promotion Tracking
    last_promoted_date = db.Column(db.DateTime)  # When student was last promoted to next class
    last_promoted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # Who approved promotion

    # Student Status Tracking (for subscription billing and enrollment management)
    status = db.Column(db.String(20), default='Active')  # Active, Graduated, Withdrawn, Transferred, Suspended, Inactive
    status_updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status_updated_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # Who changed status (proprietor/headmaster)
    status_reason = db.Column(db.String(255))  # Reason for status change (graduation, withdrawal reason, etc)

    # Pillar 4: Data Schema Adaptation
    # Allows schools to add their own fields (e.g., 'House Color', 'Medical Info')
    custom_attributes = db.Column(db.JSON, default={})

    grades = db.relationship(
        "StudentGrade", backref="student", lazy=True, cascade="all, delete-orphan"
    )
    payments = db.relationship(
        "Payment", backref="student", lazy=True, cascade="all, delete-orphan"
    )
    
    @property
    def age(self):
        """Calculate age from date of birth."""
        if not self.date_of_birth:
            return None
        today = datetime.now().date()
        age = today.year - self.date_of_birth.year
        # Adjust if birthday hasn't occurred yet this year
        if today.month < self.date_of_birth.month or (
            today.month == self.date_of_birth.month and today.day < self.date_of_birth.day
        ):
            age -= 1
        return age


class StudentGrade(db.Model):
    __tablename__ = "student_grades"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    # Generic Subject Model (Supports any curriculum)
    subject_name = db.Column(db.String(50), nullable=False, default="General")
    # Record which class the student belonged to when the grade was entered
    class_name = db.Column(db.String(20))
    class_score = db.Column(db.Float, default=0.0)  # 30% - 0-30 range
    exam_score = db.Column(db.Float, default=0.0)  # 70% - 0-70 range
    total_score = db.Column(db.Float)  # Calculated: 0-100 range
    is_finalized = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.String(255))
    ai_narrative = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Constraints on score ranges
    __table_args__ = (
        db.CheckConstraint(
            "class_score >= 0 AND class_score <= 30", name="check_class_score_range"
        ),
        db.CheckConstraint(
            "exam_score >= 0 AND exam_score <= 70", name="check_exam_score_range"
        ),
        db.CheckConstraint(
            "total_score >= 0 AND total_score <= 100", name="check_total_score_range"
        ),
    )


# ---------------------------------------------------------
# Class Promotion Tracking
# ---------------------------------------------------------
class StudentPromotion(db.Model):
    __tablename__ = "student_promotions"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    
    # What class was the student promoted FROM and TO
    promoted_from_class = db.Column(db.String(20), nullable=False)
    promoted_to_class = db.Column(db.String(20), nullable=False)
    
    # Who approved the promotion and when
    promoted_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    promotion_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Optional remarks about why promoted (if not promoted, reason for retention)
    remarks = db.Column(db.String(500))
    
    # Reversal tracking (if promotion was overridden)
    is_reversed = db.Column(db.Boolean, default=False)
    reversed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reversed_at = db.Column(db.DateTime, nullable=True)
    reversal_reason = db.Column(db.String(500), nullable=True)
    
    #  Relationship for display
    student = db.relationship("Student", backref="promotions")
    promoted_by = db.relationship("User", backref="promotions_approved", foreign_keys=[promoted_by_user_id])
    reversed_by = db.relationship("User", backref="promotions_reversed", foreign_keys=[reversed_by_user_id])


# ---------------------------------------------------------
# Student Notifications (Alerts for Teachers & Admins)
# ---------------------------------------------------------
class StudentNotification(db.Model):
    __tablename__ = "student_notifications"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    
    # Notification type: promotion, repetition, status_change, performance_alert, etc.
    notification_type = db.Column(db.String(50), nullable=False)
    
    # Subject and message
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    
    # Metadata for the notification (JSON)
    # e.g., {"old_class": "JHS 2", "new_class": "JHS 3", "performance": "55.5%"}
    notification_metadata = db.Column(db.JSON, default={})
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    read_at = db.Column(db.DateTime, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    
    # Relationships
    school = db.relationship("School", backref="notifications")
    recipient = db.relationship("User", backref="notifications_received", foreign_keys=[recipient_user_id])
    student = db.relationship("Student", backref="notifications")


# ---------------------------------------------------------
# 4. FINANCIALS & AUDIT (Access Control & Encryption)
# ---------------------------------------------------------
class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    payment_type = db.Column(
        db.String(20), nullable=False
    )  # Tuition, Feeding, Uniform, Transport
    method = db.Column(db.String(20), nullable=False)  # MoMo, Cash, Bank, Cheque
    reference_id = db.Column(
        db.String(50), unique=True
    )  # The unique MoMo Ref (idempotency)
    status = db.Column(db.String(20), default="Pending")
    date_paid = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    verified_at = db.Column(db.DateTime)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    # Pillar 4: Granular Payment Categorization (Not tied to payment provider)
    # This allows tracking of specific terms, frequencies, and items
    payment_category = db.Column(
        db.JSON, default={}
    )  # {"term": "Term 1", "frequency": "Monthly", "item": "Uniform - Large"}
    # Examples:
    # Tuition: {"term": "Term 1"} or {"term": "Term 2"} or {"term": "Term 3"}
    # Feeding: {"frequency": "Daily"} or {"frequency": "Weekly"} or {"frequency": "Monthly"}
    # Uniform: {"item": "School Uniform - Size Large", "quantity": 2}
    # Transport: {"route": "Ashongman", "frequency": "Monthly"}

    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            "amount > 0 AND amount <= 100000", name="check_payment_amount"
        ),
    )


class PaystackSubAccount(db.Model):
    """Paystack Fee Route Account - One virtual account per payment type per school.
    
    Paystack generates VIRTUAL account numbers (bank + MoMo shortcodes) for each payment type.
    Parents pay to these virtual accounts → Paystack knows payment type automatically.
    All funds settle to school's ONE actual bank account registered with Paystack.
    
    Flow:
    1. School registers ONE bank account with Paystack
    2. System creates fee route account for each payment type (Tuition, Feeding, etc.)
    3. Paystack returns virtual account numbers + MoMo codes for each fee route account
    4. Parents pay to virtual accounts (auto-tagged with payment type)
    5. Webhook receives payment with route code → knows payment type
    6. All funds settle to school's single bank account
    """
    __tablename__ = "paystack_subaccounts"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    
    # Payment type this fee route account handles
    payment_type = db.Column(db.String(20), nullable=False)  # Tuition, Feeding, Uniform, Transport, Other
    
    # Paystack fee route account details
    subaccount_code = db.Column(db.String(50), unique=True, nullable=False)  # Route code from Paystack API response
    business_name = db.Column(db.String(100), nullable=False)  # e.g., "ABC School - Tuition"
    
    # Virtual account details generated by Paystack
    virtual_bank_account = db.Column(db.String(50))  # Virtual account number for bank transfers
    virtual_bank_name = db.Column(db.String(100))  # Bank name for virtual account
    momo_shortcode = db.Column(db.String(20))  # Mobile Money shortcode (e.g., *920*123#)
    momo_provider = db.Column(db.String(20))  # MTN, Vodafone, AirtelTigo
    
    # Split configuration
    percentage_charge = db.Column(db.Float, default=0.0)  # Platform commission % (e.g., 2.5)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)  # Virtual account activated by Paystack
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # Audit trail
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    
    # Relationships
    school = db.relationship("School", backref="paystack_subaccounts")
    creator = db.relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        db.UniqueConstraint("school_id", "payment_type", name="uq_school_payment_subaccount"),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "school_id": self.school_id,
            "payment_type": self.payment_type,
            "subaccount_code": self.subaccount_code,
            "business_name": self.business_name,
            "virtual_bank_account": self.virtual_bank_account,
            "virtual_bank_name": self.virtual_bank_name,
            "momo_shortcode": self.momo_shortcode,
            "momo_provider": self.momo_provider,
            "percentage_charge": self.percentage_charge,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    tx_type = db.Column(db.String(30), nullable=False)  # tuition, feeding, refund, subscription
    tx_ref = db.Column(db.String(80), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="GH₵")
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    source = db.Column(db.String(30), default="payment")
    meta = db.Column("metadata", db.JSON, default={})
    previous_hash = db.Column(db.String(64))
    hash = db.Column(db.String(64), nullable=False)
    is_verified = db.Column(db.Boolean, default=True)  # Chain integrity status
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


def _ledger_payload(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _get_ledger_secret():
    """Get the HMAC secret key from environment with production enforcement."""
    secret = (os.getenv("LEDGER_SECRET_KEY") or "").strip()
    if not secret:
        if os.getenv("FLASK_ENV", "development").lower() == "production":
            raise RuntimeError(
                "Startup blocked: LEDGER_SECRET_KEY must be set in production."
            )
        secret = "edupulse-dev-secret-key-change-in-production"
    return secret.encode("utf-8")


def _ledger_hash(previous_hash, payload_str):
    """Generate HMAC-SHA256 hash for cryptographic ledger chaining."""
    secret = _get_ledger_secret()
    message = f"{previous_hash}|{payload_str}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _get_last_ledger_hash(connection, school_id):
    last_hash = connection.execute(
        select(LedgerEntry.hash)
        .where(LedgerEntry.school_id == school_id)
        .order_by(LedgerEntry.id.desc())
        .limit(1)
    ).scalar()
    return last_hash or "GENESIS"


def add_ledger_entry(
    school_id,
    tx_type,
    tx_ref,
    amount,
    currency="GH₵",
    actor_id=None,
    student_id=None,
    source="manual",
    metadata=None,
    created_at=None,
):
    """Create a tamper-evident ledger entry using the latest chain hash."""
    created_at = created_at or datetime.now(timezone.utc)
    metadata = metadata or {}

    last_hash = (
        db.session.query(LedgerEntry.hash)
        .filter_by(school_id=school_id)
        .order_by(LedgerEntry.id.desc())
        .first()
    )
    previous_hash = last_hash[0] if last_hash else "GENESIS"

    # Ensure created_at is timezone-aware for consistent hashing
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    payload = {
        "school_id": school_id,
        "tx_type": tx_type,
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,
        "actor_id": actor_id,
        "student_id": student_id,
        "source": source,
        "metadata": metadata,
        "created_at": created_at.isoformat(),
    }
    payload_str = _ledger_payload(payload)
    hash_value = _ledger_hash(previous_hash, payload_str)

    entry = LedgerEntry(
        school_id=school_id,
        tx_type=tx_type,
        tx_ref=tx_ref,
        amount=amount,
        currency=currency,
        actor_id=actor_id,
        student_id=student_id,
        source=source,
        meta=metadata,
        previous_hash=previous_hash,
        hash=hash_value,
        created_at=created_at,
    )
    db.session.add(entry)
    return entry


def verify_ledger_chain(school_id, limit=None):
    """
    Verify the integrity of the ledger chain for a school.
    Returns (is_valid, broken_entries, total_checked).
    """
    query = (
        db.session.query(LedgerEntry)
        .filter_by(school_id=school_id)
        .order_by(LedgerEntry.id.asc())
    )
    if limit:
        query = query.limit(limit)
    
    entries = query.all()
    if not entries:
        return True, [], 0
    
    broken_entries = []
    expected_previous_hash = "GENESIS"
    
    for entry in entries:
        # Check if previous_hash matches expected
        if entry.previous_hash != expected_previous_hash:
            broken_entries.append({
                "id": entry.id,
                "tx_ref": entry.tx_ref,
                "issue": "broken_chain",
                "expected_prev": expected_previous_hash,
                "actual_prev": entry.previous_hash
            })
        
        # Verify the hash itself
        # Ensure created_at is timezone-aware for consistent verification
        created_at = entry.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        payload = {
            "school_id": entry.school_id,
            "tx_type": entry.tx_type,
            "tx_ref": entry.tx_ref,
            "amount": entry.amount,
            "currency": entry.currency,
            "actor_id": entry.actor_id,
            "student_id": entry.student_id,
            "source": entry.source,
            "metadata": entry.meta,
            "created_at": created_at.isoformat(),
        }
        payload_str = _ledger_payload(payload)
        expected_hash = _ledger_hash(entry.previous_hash, payload_str)
        
        if entry.hash != expected_hash:
            broken_entries.append({
                "id": entry.id,
                "tx_ref": entry.tx_ref,
                "issue": "invalid_hash",
                "expected_hash": expected_hash,
                "actual_hash": entry.hash
            })
        
        # Update verification status
        entry.is_verified = (entry.hash == expected_hash and entry.previous_hash == expected_previous_hash)
        expected_previous_hash = entry.hash
    
    db.session.commit()
    is_valid = len(broken_entries) == 0
    return is_valid, broken_entries, len(entries)


def get_ledger_summary(school_id, start_date=None, end_date=None):
    """
    Get financial summary from the immutable ledger.
    Returns transaction count, total value, and verification status.
    """
    query = db.session.query(LedgerEntry).filter_by(school_id=school_id)
    
    if start_date:
        query = query.filter(LedgerEntry.created_at >= start_date)
    if end_date:
        query = query.filter(LedgerEntry.created_at <= end_date)
    
    entries = query.all()
    
    total_transactions = len(entries)
    total_value = sum(entry.amount for entry in entries if entry.amount > 0)
    verified_count = sum(1 for entry in entries if entry.is_verified)
    
    # Run quick integrity check on latest entries
    is_chain_valid, broken, checked = verify_ledger_chain(school_id, limit=100)
    
    return {
        "total_transactions": total_transactions,
        "total_value": total_value,
        "verified_count": verified_count,
        "is_chain_valid": is_chain_valid,
        "broken_entries": len(broken),
        "integrity_status": "VERIFIED IMMUTABLE" if is_chain_valid else "⚠️ CHAIN BROKEN"
    }


class PasswordReset(db.Model):
    __tablename__ = "password_resets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class LoginAttempt(db.Model):
    __tablename__ = "login_attempts"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    username = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(64))
    attempts = db.Column(db.Integer, default=0)
    last_attempt_at = db.Column(db.DateTime)
    locked_until = db.Column(db.DateTime)


class TwoFactorToken(db.Model):
    __tablename__ = "two_factor_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    token_hash = db.Column(db.String(255), nullable=False)
    delivery = db.Column(db.String(20), default="email")
    attempts = db.Column(db.Integer, default=0)
    consumed = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


@event.listens_for(StudentGrade, "before_insert")
@event.listens_for(StudentGrade, "before_update")
def set_grade_total(mapper, connection, target):
    if target.class_score is not None and target.exam_score is not None:
        target.total_score = float(target.class_score) + float(target.exam_score)


@event.listens_for(Payment, "after_insert")
def add_payment_to_ledger(mapper, connection, target):
    """
    Append a payment transaction to the immutable ledger chain.
    
    NOTE: This listener is DISABLED because ledger entries are created explicitly
    via add_ledger_entry() in routes.py to ensure consistent metadata structure.
    Keeping this enabled would create duplicate entries and hash mismatches.
    """
    # Disabled - ledger entries are created manually in API endpoints
    return
    
    # Original implementation commented out below:
    # try:
    #     tx_ref = target.reference_id or f"PAY-{target.id}"
    #     created_at = target.date_paid or datetime.now(timezone.utc)
    #     previous_hash = _get_last_ledger_hash(connection, target.school_id)
    #     payload = {
    #         "school_id": target.school_id,
    #         "tx_type": (target.payment_type or "payment").lower(),
    #         "tx_ref": tx_ref,
    #         "amount": float(target.amount),
    #         "currency": "GH₵",
    #         "actor_id": target.verified_by,
    #         "student_id": target.student_id,
    #         "source": "payment",
    #         "metadata": {
    #             "method": target.method,
    #             "status": target.status,
    #             "category": target.payment_category or {},
    #         },
    #         "created_at": created_at.isoformat(),
    #     }
    #     payload_str = _ledger_payload(payload)
    #     hash_value = _ledger_hash(previous_hash, payload_str)
    #
    #     connection.execute(
    #         LedgerEntry.__table__.insert().values(
    #             school_id=target.school_id,
    #             tx_type=(target.payment_type or "payment").lower(),
    #             tx_ref=tx_ref,
    #             amount=float(target.amount),
    #             currency="GH₵",
    #             actor_id=target.verified_by,
    #             student_id=target.student_id,
    #             source="payment",
    #             metadata={
    #                 "method": target.method,
    #                 "status": target.status,
    #                 "category": target.payment_category or {},
    #             },
    #             previous_hash=previous_hash,
    #             hash=hash_value,
    #             created_at=created_at,
    #         )
    #     )
    # except Exception:
    #     # Avoid blocking writes if ledger insert fails
    #     pass


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor = db.relationship("User")

    action = db.Column(db.String(50))  # e.g., 'CLASS_LOCKED', 'PAYMENT_VERIFIED'
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Inventory(db.Model):
    __tablename__ = "inventory"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(30), default="General")
    item_type = db.Column(db.String(50))
    size = db.Column(db.String(20))
    class_group = db.Column(db.String(30))  # e.g., "JHS", "Class 1-6"
    gender = db.Column(db.String(10), default="Unisex")
    sku = db.Column(db.String(30))  # Reference code for payments
    unit = db.Column(db.String(20), default="piece")
    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("school_id", "sku", name="uq_inventory_sku"),
    )


class QuestionPool(db.Model):
    __tablename__ = "question_pool"
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50))
    topic = db.Column(db.String(100))
    difficulty = db.Column(db.String(20), default="Medium")  # Easy, Medium, Hard
    audience = db.Column(db.String(20), default="Student")  # Student, Teacher
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200))
    option_b = db.Column(db.String(200))
    option_c = db.Column(db.String(200))
    option_d = db.Column(db.String(200))
    correct_option = db.Column(db.String(1), nullable=False)  # 'A', 'B', 'C', 'D'

    def to_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "audience": self.audience,
            "question": self.question,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
            "correct_option": self.correct_option,
        }


class LessonNote(db.Model):
    __tablename__ = "lesson_notes"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    staff_id = db.Column(db.Integer, nullable=False, default=0)  # Legacy: defaults to 0

    # Basic Information
    week_number = db.Column(db.Integer)  # e.g., 3 for "3rd week"
    subject = db.Column(db.String(100))
    class_name = db.Column(db.String(50))
    lesson_dates = db.Column(db.JSON, default=list)  # List of ISO date strings
    class_size = db.Column(db.Integer)

    # Curriculum Standards
    indicator_code = db.Column(db.String(50))  # Indicator code
    content_standard_code = db.Column(db.String(50))  # Content standard code
    performance_indicator = db.Column(db.Text)
    core_competencies = db.Column(db.Text)  # Can be comma-separated or JSON

    # Teaching Resources
    key_words = db.Column(db.Text)  # Comma-separated keywords
    teaching_learning_resources = db.Column(db.Text)  # T.L.R(s)
    references = db.Column(db.Text)  # References

    # Legacy field for backward compatibility
    content = db.Column(db.Text)

    # AI Review
    ai_score = db.Column(db.Integer)  # 0-100
    ai_feedback = db.Column(db.Text)

    # Approval Workflow
    status = db.Column(db.String(20), default="Pending")  # Pending, Approved, Rejected
    submit_to = db.Column(
        db.String(20), default="headmaster"
    )  # headmaster or proprietor
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to daily phases
    daily_phases = db.relationship(
        "DailyLessonPhase",
        backref="lesson_note",
        cascade="all, delete-orphan",
        lazy=True,
    )


class DailyLessonPhase(db.Model):
    __tablename__ = "daily_lesson_phases"
    id = db.Column(db.Integer, primary_key=True)
    lesson_note_id = db.Column(
        db.Integer, db.ForeignKey("lesson_notes.id"), nullable=False
    )

    day = db.Column(db.String(20))  # e.g., "Monday", "Day 1", "Week 3 - Monday"

    # Three phases of lesson delivery
    phase_1_starter = db.Column(db.Text)  # Preparing the brain for learning
    phase_2_main = db.Column(db.Text)  # New learning including assessment
    phase_3_plenary = db.Column(db.Text)  # Plenary/Reflections

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class StudentAssignment(db.Model):
    __tablename__ = "student_assignments"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    subject = db.Column(db.String(50))
    score = db.Column(db.Float, nullable=False)  # 0-100
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ClassGradingPolicy(db.Model):
    __tablename__ = "class_grading_policies"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    class_name = db.Column(db.String(20))
    # percentage to allocate to assignments when >= min_assignments (30 or 40)
    assignment_weight = db.Column(db.Integer, default=30)
    # minimum number of assignments required to consider aggregation
    min_assignments = db.Column(db.Integer, default=5)


class AcademicClass(db.Model):
    __tablename__ = "academic_classes"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20))  # e.g., Primary, JHS, SHS
    stream = db.Column(db.String(20))  # e.g., A, B, Gold
    class_teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    class_teacher = db.relationship("User", backref="managed_classes")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint(
            "school_id", "name", "stream", name="uq_academic_class_identity"
        ),
    )


class AcademicWorkLog(db.Model):
    __tablename__ = "academic_work_logs"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    class_name = db.Column(db.String(20))
    subject = db.Column(db.String(50))

    num_classwork = db.Column(db.Integer, default=0)
    num_homework = db.Column(db.Integer, default=0)

    week_number = db.Column(db.Integer)
    logged_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ReportCard(db.Model):
    """Full terminal report card for a student in a specific term/year"""

    __tablename__ = "report_cards"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    # Term/Year Context
    academic_term = db.Column(
        db.String(20), nullable=False
    )  # e.g., "Term 1", "Term 2", "Term 3"
    academic_year = db.Column(db.String(20), nullable=False)  # e.g., "2024/2025"
    class_name = db.Column(db.String(20))  # Which class the student was in
    
    # Promotion Status (populated after end-of-term promotions)
    # e.g., "PROMOTED_TO_JHS_2", "RETAINED_IN_CLASS_5", "GRADUATED", None (not yet determined)
    promotion_status = db.Column(db.String(50), nullable=True)  # e.g., PROMOTED_TO_JHS_2, RETAINED, GRADUATED
    promotion_details = db.Column(db.JSON, default={})  # e.g., {"old_class": "JHS 1", "new_class": "JHS 2", "reason": "Auto-promoted", "promotion_date": "2026-02-28"}

    # Subject Grades (JSON array of subject entries)
    # Example: [{"subject": "Mathematics", "class_score": 25, "exam_score": 65, "total": 90, "position": "1st", "grade": "A", "remarks": "Excellent"}]
    subject_grades = db.Column(db.JSON, default=[])

    # Performance Summary
    total_marks_obtained = db.Column(db.Float)  # Sum of all subject totals
    total_possible_marks = db.Column(db.Float)  # Number of subjects * 100
    term_average = db.Column(db.Float)  # Percentage average
    overall_position = db.Column(db.String(10))  # e.g., "3rd"
    out_of_students = db.Column(db.Integer)  # Total students in class

    # Performance Stats (Optional - from sample_report.jpg structure)
    attendance_percentage = db.Column(db.Float)
    total_attendance = db.Column(db.Integer)

    # Remarks & Comments
    homeroom_teacher_remarks = db.Column(db.Text)
    headmaster_remarks = db.Column(db.Text)
    proprietor_remarks = db.Column(db.Text())

    # AI-Generated Analysis
    ai_performance_analysis = db.Column(
        db.Text()
    )  # AI descriptive analysis of student performance trend

    # Status & Metadata
    status = db.Column(
        db.String(20), default="Draft"
    )  # Draft, Submitted, HeadmasterApproved, ProprietorApproved, Published
    submit_to = db.Column(
        db.String(20), default="headmaster"
    )  # headmaster or proprietor
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id")
    )  # Homeroom teacher who created it
    submitted_at = db.Column(db.DateTime)
    headmaster_approved_at = db.Column(db.DateTime)
    headmaster_approved_by = db.Column(
        db.Integer, db.ForeignKey("users.id")
    )  # Headmaster who approved
    proprietor_approved_at = db.Column(db.DateTime)
    proprietor_approved_by = db.Column(
        db.Integer, db.ForeignKey("users.id")
    )  # Proprietor who approved
    printed_at = db.Column(db.DateTime)  # When report was printed

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    student = db.relationship("Student", backref="report_cards")

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_name": self.student.name if self.student else None,
            "student_code": self.student.student_code if self.student else None,
            "academic_term": self.academic_term,
            "academic_year": self.academic_year,
            "class_name": self.class_name,
            "subject_grades": self.subject_grades,
            "total_marks_obtained": self.total_marks_obtained,
            "total_possible_marks": self.total_possible_marks,
            "term_average": self.term_average,
            "overall_position": self.overall_position,
            "out_of_students": self.out_of_students,
            "attendance_percentage": self.attendance_percentage,
            "total_attendance": self.total_attendance,
            "homeroom_teacher_remarks": self.homeroom_teacher_remarks,
            "headmaster_remarks": self.headmaster_remarks,
            "proprietor_remarks": self.proprietor_remarks,
            "ai_performance_analysis": self.ai_performance_analysis,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_at": (
                self.submitted_at.isoformat() if self.submitted_at else None
            ),
            "headmaster_approved_at": (
                self.headmaster_approved_at.isoformat()
                if self.headmaster_approved_at
                else None
            ),
            "proprietor_approved_at": (
                self.proprietor_approved_at.isoformat()
                if self.proprietor_approved_at
                else None
            ),
            "printed_at": self.printed_at.isoformat() if self.printed_at else None,
        }


class ReportCardStatus(db.Model):
    __tablename__ = "report_card_status"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    class_name = db.Column(db.String(20))
    status = db.Column(db.String(20), default="Pending")  # Pending, Approved, Rejected
    headmaster_feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    type = db.Column(db.String(20))  # 'Bug Report', 'Feature Request', 'General'
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="Open")
    admin_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))


class LiveChatSession(db.Model):
    __tablename__ = "live_chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default="open")  # open, closed
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))


class LiveChatMessage(db.Model):
    __tablename__ = "live_chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("live_chat_sessions.id"), nullable=False)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sender_type = db.Column(db.String(20), default="user")  # user, support_agent, system
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SystemAlert(db.Model):
    __tablename__ = "system_alerts"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default="Maintenance")  # Maintenance, Info
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Timetable(db.Model):
    __tablename__ = "timetable"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    class_name = db.Column(db.String(20), nullable=False)
    subject_name = db.Column(db.String(50), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    teacher = db.relationship("User", backref="timetable_slots")
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday, Tuesday, etc.
    start_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    end_time = db.Column(db.String(5), nullable=False)  # HH:MM format
    location = db.Column(db.String(50))  # Room/location info
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))


class PromotionThreshold(db.Model):
    """Auto-promotion threshold settings - allows proprietor to set performance criteria"""
    __tablename__ = "promotion_thresholds"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.String(20), db.ForeignKey("schools.id"), nullable=False)
    
    # If class_name is NULL, applies to all classes
    class_name = db.Column(db.String(20), nullable=True)
    
    # Threshold can be set as percentage (e.g., 55.5) or absolute score (e.g., 500/900)
    # If NULL, all students in the class are automatically promoted
    threshold_percentage = db.Column(db.Float, nullable=True)  # e.g., 55.5 means 55.5%
    
    # Minimum number of courses a student must have grades in to qualify
    min_courses_required = db.Column(db.Integer, default=0, nullable=False)
    
    # Who set this threshold and when
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    created_by = db.relationship("User", backref="promotion_thresholds")
    school = db.relationship("School", backref="promotion_thresholds")
    
    __table_args__ = (
        db.UniqueConstraint('school_id', 'class_name', name='uq_school_class_threshold'),
    )


class Subscription(db.Model):
    """School subscription management - tracks SaaS plans and billing"""

    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(
        db.String(20), db.ForeignKey("schools.id"), nullable=False, unique=True
    )
    school = db.relationship("School", backref="subscription", uselist=False)

    plan = db.Column(db.String(20), nullable=False, default="free")
    status = db.Column(db.String(20), nullable=False, default="active")

    start_date = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    end_date = db.Column(db.DateTime)
    trial_end_date = db.Column(db.DateTime)

    last_payment_date = db.Column(db.DateTime)
    next_billing_date = db.Column(db.DateTime)
    auto_renew = db.Column(db.Boolean, default=True)
    billing_email = db.Column(db.String(120))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    def days_remaining(self):
        if not self.end_date:
            return None
        remaining = (self.end_date - datetime.now(timezone.utc)).days
        return max(0, remaining)

    def is_expired(self):
        if not self.end_date:
            return False
        return datetime.now(timezone.utc) > self.end_date


class PlatformSetting(db.Model):
    """Global platform settings controlled by software owner (not tenant-scoped)."""

    __tablename__ = "platform_settings"

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    setting_value = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PlatformUser(db.Model):
    """Platform admin users with access to owner console (not tenant-scoped)."""

    __tablename__ = "platform_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

"""
Input validation and sanitization utilities for EduPulse API.
Ensures all user inputs are properly validated before processing.
"""

import re

from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class LoginSchema(Schema):
    """Validates login credentials."""

    schoolCode = fields.Str(
        required=True,
        validate=[validate.Length(min=3, max=20), validate.Regexp(r"^[A-Za-z0-9_-]+$")],
    )
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r"^[A-Za-z0-9_.-]+$"),
        ],
    )
    password = fields.Str(required=True, validate=validate.Length(min=6, max=128))


class RegisterSchema(Schema):
    """Validates school registration."""

    schoolCode = fields.Str(
        required=True,
        validate=[validate.Length(min=3, max=20), validate.Regexp(r"^[A-Za-z0-9_-]+$")],
    )
    schoolName = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r"^[A-Za-z0-9_.-]+$"),
        ],
    )
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    email = fields.Str(required=True, validate=validate.Email())
    termsAccepted = fields.Bool(required=True)
    termsVersion = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    selectedPlan = fields.Str(
        required=False,
        validate=validate.OneOf(["Free", "Basic", "Premium"]),
        load_default="Free"
    )

    @validates_schema
    def validate_password_and_terms(self, data, **kwargs):
        """Ensures password meets security requirements and terms are accepted."""
        password = data.get("password", "")
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValidationError(error_msg)
        if data.get("termsAccepted") is not True:
            raise ValidationError("Terms must be accepted")


class StudentGradeSchema(Schema):
    """Validates grade entry."""

    student_id = fields.Int(required=True)
    subject_name = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    class_score = fields.Float(required=True, validate=validate.Range(min=0, max=30))
    exam_score = fields.Float(required=True, validate=validate.Range(min=0, max=70))
    remarks = fields.Str(allow_none=True, validate=validate.Length(max=255))


class PaymentSchema(Schema):
    """Validates payment records with granular categorization."""

    student_id = fields.Int(required=True)
    amount = fields.Float(required=True, validate=validate.Range(min=0.01, max=100000))
    payment_type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["Tuition", "Feeding", "Uniform", "Transport", "Inventory", "Terminal Report"]
        ),
    )
    method = fields.Str(
        required=True, validate=validate.OneOf(["MoMo", "Cash", "Bank", "Cheque"])
    )
    reference_id = fields.Str(allow_none=True, validate=validate.Length(max=50))
    payment_category = fields.Dict(
        allow_none=True
    )  # Supports {"term": "Term 1"}, {"frequency": "Monthly"}, {"item": "..."}, etc.


class AttendanceSchema(Schema):
    """Validates attendance records."""

    class_name = fields.Str(required=True, validate=validate.Length(min=3, max=20))
    student_id = fields.Int(required=True)
    is_present = fields.Bool(required=True)
    feeding_paid = fields.Bool(required=True)


class LessonNoteSchema(Schema):
    """Validates lesson notes."""

    week_number = fields.Int(required=True, validate=validate.Range(min=1, max=52))
    subject = fields.Str(required=True, validate=validate.Length(min=2, max=100))
    class_name = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    lesson_dates = fields.List(fields.Str(), required=False)
    class_size = fields.Int(allow_none=True, validate=validate.Range(min=1, max=2000))
    indicator_code = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    content_standard_code = fields.Str(
        required=True, validate=validate.Length(min=2, max=50)
    )
    performance_indicator = fields.Str(
        required=True, validate=validate.Length(min=5, max=5000)
    )
    core_competencies = fields.Str(allow_none=True, validate=validate.Length(max=5000))
    key_words = fields.Str(allow_none=True, validate=validate.Length(max=2000))
    teaching_learning_resources = fields.Str(
        allow_none=True, validate=validate.Length(max=5000)
    )
    references = fields.Str(allow_none=True, validate=validate.Length(max=5000))
    content = fields.Str(allow_none=True, validate=validate.Length(max=10000))
    daily_phases = fields.List(fields.Dict(), required=False)


class SettingsUpdateSchema(Schema):
    """Validates school settings updates."""

    sack_risk_threshold = fields.Int(
        allow_none=True, validate=validate.Range(min=1, max=100)
    )
    canteen_cutoff_time = fields.Str(
        allow_none=True, validate=validate.Regexp(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    )
    currency = fields.Str(allow_none=True, validate=validate.Length(min=1, max=5))


def validate_request(schema_class):
    """Decorator for automatic request validation."""

    def decorator(f):
        def wrapper(*args, **kwargs):
            from flask import jsonify, request

            schema = schema_class()
            try:
                data = schema.load(request.json)
                request.validated_data = data
            except ValidationError as err:
                return (
                    jsonify({"message": "Validation error", "errors": err.messages}),
                    400,
                )
            return f(*args, **kwargs)

        wrapper.__name__ = f.__name__
        return wrapper

    return decorator


def sanitize_string(s):
    """Remove potentially dangerous characters from strings."""
    if not isinstance(s, str):
        return s
    # Remove null bytes and very long strings
    s = s.replace("\x00", "")
    if len(s) > 10000:
        s = s[:10000]
    return s


def validate_email(email):
    """Validates email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def validate_phone(phone):
    """Validates Ghanaian phone number format."""
    pattern = r"^(\+233|0)[0-9]{9}$"
    return re.match(pattern, phone) is not None


def validate_password_strength(password):
    """Validates password meets security requirements.
    
    Requirements:
    - At least 8 characters
    - At least one lowercase letter
    - At least one uppercase letter
    - At least one digit
    - At least one special character (!@#$%^&*)
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character (!@#$%^&*)"
    return True, None


class StaffSchema(Schema):
    """Validates staff member creation."""

    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r"^[A-Za-z0-9_.-]+$"),
        ],
    )
    email = fields.Str(required=True, validate=validate.Email())
    password = fields.Str(required=True, validate=validate.Length(min=8, max=128))
    role = fields.Str(
        allow_none=True,
        validate=validate.OneOf(["teacher", "homeroom", "headmaster", "finance", "inventory_manager"]),
    )
    roles = fields.List(
        fields.Str(validate=validate.OneOf(["teacher", "homeroom", "headmaster", "finance", "inventory_manager"])),
        allow_none=True,
    )
    assigned_class = fields.Str(allow_none=True, validate=validate.Length(max=50))
    assigned_classes = fields.List(fields.Str(), allow_none=True)
    assigned_subjects = fields.List(fields.Str(), allow_none=True)

    @validates_schema
    def validate_password_and_roles(self, data, **kwargs):
        """Ensures password meets security requirements and roles are valid."""
        password = data.get("password", "")
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValidationError(error_msg)

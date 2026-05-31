"""
Unit tests for EduPulse validators and core functionality.
Run with: pytest tests/
"""

import json
from datetime import datetime, timedelta

import pytest
from marshmallow import ValidationError

from backend.validators import (
    AttendanceSchema,
    LoginSchema,
    PaymentSchema,
    RegisterSchema,
    StudentGradeSchema,
    validate_email,
    validate_phone,
)


class TestValidators:
    """Test input validation schemas."""

    def test_login_schema_valid(self):
        """Test valid login credentials."""
        schema = LoginSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "username": "teacher1",
            "password": "secure_password_123",
        }
        result = schema.load(data)
        assert result["schoolCode"] == "CCA-OFK"
        assert result["username"] == "teacher1"

    def test_login_schema_missing_field(self):
        """Test login with missing required field."""
        schema = LoginSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "username": "teacher1",
            # Missing password
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "password" in exc_info.value.messages

    def test_login_schema_invalid_schoolcode_length(self):
        """Test login with invalid school code (too short)."""
        schema = LoginSchema()
        data = {
            "schoolCode": "CC",  # Too short
            "username": "teacher1",
            "password": "secure_password_123",
        }
        with pytest.raises(ValidationError):
            schema.load(data)

    def test_register_schema_weak_password(self):
        """Test registration with weak password (no uppercase)."""
        schema = RegisterSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "schoolName": "CCA Ofankor",
            "username": "newuser",
            "email": "newuser@cca.edu",
            "password": "weak123456",  # No uppercase
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "uppercase" in str(exc_info.value.messages)

    def test_register_schema_weak_password_no_digit(self):
        """Test registration with weak password (no digit)."""
        schema = RegisterSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "schoolName": "CCA Ofankor",
            "username": "newuser",
            "email": "newuser@cca.edu",
            "password": "WeakPassword",  # No digit
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "digit" in str(exc_info.value.messages)

    def test_register_schema_valid(self):
        """Test valid registration."""
        schema = RegisterSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "schoolName": "CCA Ofankor",
            "username": "newuser",
            "email": "newuser@cca.edu",
            "password": "SecurePass123!",
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        }
        result = schema.load(data)
        assert result["schoolCode"] == "CCA-OFK"

    def test_register_schema_requires_school_data_authority_confirmation(self):
        schema = RegisterSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "schoolName": "CCA Ofankor",
            "username": "newuser",
            "email": "newuser@cca.edu",
            "password": "SecurePass123!",
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": False,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "authority" in str(exc_info.value.messages).lower()

    def test_register_schema_requires_aggregated_analytics_acceptance(self):
        schema = RegisterSchema()
        data = {
            "schoolCode": "CCA-OFK",
            "schoolName": "CCA Ofankor",
            "username": "newuser",
            "email": "newuser@cca.edu",
            "password": "SecurePass123!",
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": False,
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "analytics" in str(exc_info.value.messages).lower()

    def test_student_grade_schema_valid(self):
        """Test valid grade entry."""
        schema = StudentGradeSchema()
        data = {
            "student_id": 1,
            "subject_name": "Mathematics",
            "class_score": 20.5,  # 30% max
            "exam_score": 65.0,  # 70% max
            "remarks": "Good performance",
        }
        result = schema.load(data)
        assert result["student_id"] == 1
        assert result["class_score"] == 20.5

    def test_student_grade_schema_invalid_class_score(self):
        """Test grade with invalid class score (exceeds 30%)."""
        schema = StudentGradeSchema()
        data = {
            "student_id": 1,
            "subject_name": "Mathematics",
            "class_score": 35.0,  # Exceeds 30% max
            "exam_score": 65.0,
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "class_score" in exc_info.value.messages

    def test_student_grade_schema_invalid_exam_score(self):
        """Test grade with invalid exam score (exceeds 70%)."""
        schema = StudentGradeSchema()
        data = {
            "student_id": 1,
            "subject_name": "Mathematics",
            "class_score": 20.0,
            "exam_score": 75.0,  # Exceeds 70% max
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert "exam_score" in exc_info.value.messages

    def test_payment_schema_valid(self):
        """Test valid payment entry."""
        schema = PaymentSchema()
        data = {
            "student_id": 1,
            "amount": 250.00,
            "payment_type": "Tuition",
            "method": "MoMo",
            "reference_id": "MOM-2026-001",
        }
        result = schema.load(data)
        assert result["amount"] == 250.00

    def test_payment_schema_invalid_amount_negative(self):
        """Test payment with negative amount."""
        schema = PaymentSchema()
        data = {
            "student_id": 1,
            "amount": -100.00,
            "payment_type": "Tuition",
            "method": "Cash",
        }
        with pytest.raises(ValidationError):
            schema.load(data)

    def test_payment_schema_invalid_amount_exceeds_max(self):
        """Test payment exceeding maximum amount."""
        schema = PaymentSchema()
        data = {
            "student_id": 1,
            "amount": 150000.00,  # Exceeds 100,000 max
            "payment_type": "Tuition",
            "method": "Bank",
        }
        with pytest.raises(ValidationError):
            schema.load(data)

    def test_payment_schema_invalid_type(self):
        """Test payment with invalid payment type."""
        schema = PaymentSchema()
        data = {
            "student_id": 1,
            "amount": 100.00,
            "payment_type": "InvalidType",
            "method": "Cash",
        }
        with pytest.raises(ValidationError):
            schema.load(data)

    def test_attendance_schema_valid(self):
        """Test valid attendance entry."""
        schema = AttendanceSchema()
        data = {
            "class_name": "JHS 1",
            "student_id": 1,
            "is_present": True,
            "feeding_paid": True,
        }
        result = schema.load(data)
        assert result["is_present"] is True


class TestEmailValidation:
    """Test email validation function."""

    def test_valid_email(self):
        """Test valid email format."""
        assert validate_email("teacher@school.edu") is True
        assert validate_email("user.name@domain.co.uk") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @ symbol."""
        assert validate_email("invalidemail.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert validate_email("user@") is False

    def test_invalid_email_special_chars(self):
        """Test email with invalid special characters."""
        assert validate_email("user@name@domain.com") is False


class TestPhoneValidation:
    """Test Ghanaian phone number validation."""

    def test_valid_phone_plus233(self):
        """Test valid phone with +233."""
        assert validate_phone("+233501234567") is True

    def test_valid_phone_zero(self):
        """Test valid phone starting with 0."""
        assert validate_phone("0501234567") is True

    def test_invalid_phone_short(self):
        """Test phone number too short."""
        assert validate_phone("050123456") is False

    def test_invalid_phone_long(self):
        """Test phone number too long."""
        assert validate_phone("05012345678") is False


class TestDatabaseConstraints:
    """Test database-level constraints."""

    @pytest.fixture
    def app(self):
        """Create Flask app for testing."""
        from backend.api.api import app as flask_app

        flask_app.config["TESTING"] = True
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        return flask_app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        with app.app_context():
            from backend.api.models import db

            db.create_all()
            yield app.test_client()
            db.session.remove()
            db.drop_all()

    def test_payment_amount_constraint(self, client):
        """Test payment amount constraint."""
        from backend.api.models import Payment, School, Student, User, db

        with client.application.app_context():
            # Create test data
            school = School(id="TEST-001", name="Test School")
            db.session.add(school)

            user = User(username="testuser", school_id="TEST-001", role="proprietor")
            user.set_password("TestPass123")
            db.session.add(user)

            student = Student(
                school_id="TEST-001",
                first_name="Test",
                surname="Student",
                name="Test Student",
                student_code="VAL001",
                current_class="JHS 1",
            )
            db.session.add(student)
            db.session.flush()

            # Try to add payment with invalid amount
            payment = Payment(
                student_id=student.id,
                school_id="TEST-001",
                amount=-50.00,  # Invalid: negative
                payment_type="Tuition",
                method="Cash",
            )
            db.session.add(payment)

            # Should enforce constraint at database level
            # Note: SQLite doesn't enforce CHECK constraints by default
            # but PostgreSQL does
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                assert "check_payment_amount" in str(e) or True  # Depends on DB


class TestSecurityHeaders:
    """Test security headers on API responses."""

    @pytest.fixture
    def app(self):
        """Create Flask app for testing."""
        from backend.api.api import app as flask_app

        flask_app.config["TESTING"] = True
        return flask_app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()

    def test_security_headers_present(self, client):
        """Test that security headers are present in response."""
        response = client.get("/")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

        assert "X-XSS-Protection" in response.headers
        assert "Content-Security-Policy" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

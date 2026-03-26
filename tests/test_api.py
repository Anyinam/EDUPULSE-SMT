"""
Unit tests for EduPulse API endpoints.
Tests authentication, grade entry, and payment functionality.
"""

import io
import json
from datetime import datetime

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create Flask app for testing."""
    from backend.api.api import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["JWT_SECRET_KEY"] = "test-secret-key"
    return flask_app


@pytest.fixture
def client(app):
    """Create test client and initialize database."""
    with app.app_context():
        from backend.api.models import School, Student, StudentGrade, User, db

        db.create_all()

        # Create test school
        school = School(id="TEST-001", name="Test School", primary_color="#1e3a8a")
        db.session.add(school)

        # Create test users
        teacher = User(
            username="teacher1",
            school_id="TEST-001",
            role="teacher",
            email="teacher@test.edu",
        )
        teacher.set_password("TeacherPass123")
        db.session.add(teacher)

        proprietor = User(
            username="proprietor1",
            school_id="TEST-001",
            role="proprietor",
            email="proprietor@test.edu",
        )
        proprietor.set_password("PropPass123")
        db.session.add(proprietor)

        # Create test students
        for i in range(3):
            student = Student(
                school_id="TEST-001",
                first_name=f"Student{i+1}",
                surname="API",
                name=f"Student {i+1}",
                student_code=f"S{i+1:03d}",
                current_class="JHS 1",
                total_tuition_owed=0.0,
            )
            db.session.add(student)

        db.session.commit()

        yield app.test_client()

        db.session.remove()
        db.drop_all()


class TestAuthenticationEndpoints:
    """Test authentication endpoints."""

    def test_login_valid_credentials(self, client, app):
        """Test login with valid credentials."""
        response = client.post(
            "/api/login",
            json={
                "schoolCode": "TEST-001",
                "username": "teacher1",
                "password": "TeacherPass123",
            },
            headers={"X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert data["role"] == "teacher"
        assert data["school_id"] == "TEST-001"

    def test_login_accepts_registered_email(self, client):
        """Users should be able to log in with their saved email address."""
        response = client.post(
            "/api/login",
            json={
                "schoolCode": "TEST-001",
                "username": "teacher@test.edu",
                "password": "TeacherPass123",
            },
            headers={"X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert data["role"] == "teacher"
        assert data["school_id"] == "TEST-001"

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        response = client.post(
            "/api/login",
            json={
                "schoolCode": "TEST-001",
                "username": "teacher1",
                "password": "WrongPassword123",
            },
        )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert "Invalid" in data["message"]

    def test_login_invalid_school(self, client):
        """Test login with non-existent school."""
        response = client.post(
            "/api/login",
            json={
                "schoolCode": "FAKE-001",
                "username": "teacher1",
                "password": "TeacherPass123",
            },
        )

        assert response.status_code == 401

    def test_login_missing_fields(self, client):
        """Test login with missing fields."""
        response = client.post(
            "/api/login",
            json={
                "schoolCode": "TEST-001",
                "username": "teacher1",
                # Missing password
            },
        )

        # Should return 400 for validation error
        assert response.status_code in [400, 401]

    def test_register_valid_new_school(self, client):
        """Test registration of new school."""
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "NEW-SCHOOL",
                "schoolName": "New Test School",
                "username": "proprietor",
                "email": "proprietor@new-school.edu",
                "password": "NewSchoolPass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "successfully" in data["message"]

    def test_register_duplicate_school(self, client):
        """Test registration with duplicate school code."""
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "TEST-001",  # Already exists
                "schoolName": "Duplicate School",
                "username": "user",
                "email": "user@duplicate.edu",
                "password": "DuplicatePass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "already taken" in data["message"]

    def test_register_duplicate_proprietor_email(self, client):
        """Test registration with duplicate proprietor email."""
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "NEW-EMAIL",
                "schoolName": "Duplicate Email School",
                "username": "freshowner",
                "email": "TEACHER@TEST.EDU",
                "password": "DuplicatePass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "email already exists" in data["message"].lower()

    def test_register_duplicate_proprietor_username(self, client):
        """Test registration with duplicate proprietor username."""
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "NEW-USER",
                "schoolName": "Duplicate Username School",
                "username": "teacher1",
                "email": "fresh-owner@example.com",
                "password": "DuplicatePass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "username already taken" in data["message"].lower()

    def test_register_paid_plan_sends_welcome_email_before_payment(self, client, mocker, mock_email):
        """Premium registrations should still receive the welcome/credential email immediately."""
        paystack_mock = mocker.patch("backend.paystack_integration.initialize_payment")
        paystack_mock.return_value = {
            "authorization_url": "https://paystack.example/checkout",
            "reference": "pay_ref_123",
        }

        response = client.post(
            "/api/register",
            json={
                "schoolCode": "PREM-001",
                "schoolName": "Premium Test School",
                "username": "proprietor",
                "email": "proprietor@premium.edu",
                "password": "PremiumPass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
                "selectedPlan": "Premium",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["requires_payment"] is True
        assert data["payment_url"] == "https://paystack.example/checkout"
        mock_email.assert_called_once()
        paystack_mock.assert_called_once()

    def test_register_weak_password(self, client):
        """Test registration with weak password."""
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "WEAK-PASS",
                "schoolName": "Weak Password School",
                "username": "user",
                "email": "user@weakpass.edu",
                "password": "weak",  # Too weak
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
            },
        )

        assert response.status_code == 400


class TestGradeEntryEndpoints:
    """Test grade entry endpoints."""

    def test_finalize_class_valid(self, client, app):
        """Test grade finalization with valid data."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            # Get first student ID
            student = Student.query.filter_by(school_id="TEST-001").first()
            assert student is not None

            # Get auth token
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

            response = client.post(
                "/api/homeroom/finalize-class",
                json={
                    "class_name": "JHS 1",
                    "subject": "Mathematics",
                    "grade_data": {str(student.id): 85.5},
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert "saved" in data["message"]

    def test_finalize_class_invalid_score_range(self, client, app):
        """Test grade finalization with out-of-range score."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student.query.filter_by(school_id="TEST-001").first()
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

            response = client.post(
                "/api/homeroom/finalize-class",
                json={
                    "class_name": "JHS 1",
                    "subject": "Mathematics",
                    "grade_data": {str(student.id): 105.0},  # Invalid: > 100
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 400
            data = json.loads(response.data)
            assert "Invalid score" in data["message"]

    def test_finalize_class_negative_score(self, client, app):
        """Test grade finalization with negative score."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student.query.filter_by(school_id="TEST-001").first()
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

            response = client.post(
                "/api/homeroom/finalize-class",
                json={
                    "class_name": "JHS 1",
                    "subject": "Mathematics",
                    "grade_data": {str(student.id): -10.0},  # Invalid: < 0
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 400

    def test_finalize_class_invalid_class_name(self, client, app):
        """Test grade finalization with invalid class name."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student.query.filter_by(school_id="TEST-001").first()
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

            response = client.post(
                "/api/homeroom/finalize-class",
                json={
                    "class_name": "INVALID-CLASS",
                    "subject": "Mathematics",
                    "grade_data": {str(student.id): 85.0},
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 400


class TestPaymentEndpoints:
    """Test payment endpoints."""

    def test_receive_payment_valid(self, client, app):
        """Test valid payment recording."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student.query.filter_by(school_id="TEST-001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

            response = client.post(
                "/api/finance/receive-payment",
                json={
                    "student_id": student.id,
                    "amount": 50.0,
                    "type": "Feeding",
                    "method": "Cash",
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert "recorded" in data["message"]

    def test_receive_payment_invalid_amount(self, client, app):
        """Test payment with invalid amount."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student.query.filter_by(school_id="TEST-001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

            response = client.post(
                "/api/finance/receive-payment",
                json={
                    "student_id": student.id,
                    "amount": -50.0,  # Invalid: negative
                    "type": "Feeding",
                    "method": "Cash",
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            # Should be rejected by validation or database constraint
            assert response.status_code in [400, 500]


class TestAdmissionsEndpoints:
    """Test admissions endpoints."""

    def test_bulk_admit_header_variants(self, client, app):
        """Accept common human-readable CSV headers in bulk admissions."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import User

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        csv_content = (
            "First Name,Surname,Class Assigned,Gender,Guardian Name,Parent Email\n"
            "Ada,Lovelace,JHS 1,Female,Charles Babbage,ada.parent@example.com\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "students.csv")}
        response = client.post(
            "/api/admissions/bulk-upload",
            data=data,
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )
        assert response.status_code == 200
        payload = json.loads(response.data)
        assert "Successfully admitted" in payload.get("message", "")
        assert "1" in payload.get("message", "")
        assert not payload.get("errors")

    def test_bulk_admit_invalid_class(self, client, app):
        """Reject invalid class_assigned in bulk admissions."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import User

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        csv_content = (
            "name,student_code,class_assigned,guardian_name,parent_email\n"
            "John Doe,,INVALID-CLASS,Jane Doe,jane@example.com\n"
        )
        data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "students.csv")}
        response = client.post(
            "/api/admissions/bulk-upload",
            data=data,
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )
        assert response.status_code == 200
        payload = json.loads(response.data)
        assert any("Invalid class_assigned" in err for err in payload.get("errors", []))

    def test_receive_payment_missing_student(self, client, app):
        """Test payment for non-existent student."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import User

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

            response = client.post(
                "/api/finance/receive-payment",
                json={
                    "student_id": 9999,  # Non-existent
                    "amount": 50.0,
                    "type": "Tuition",
                    "method": "Cash",
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 404


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation."""

    def test_cannot_access_other_school_data(self, client, app):
        """Test that users cannot access data from other schools."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import School, User, db

            # Create another school
            school2 = School(id="OTHER-SCHOOL", name="Other School")
            db.session.add(school2)

            # Create user for first school
            user = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(user.id))

            # Try to access with X-School-ID pointing to other school
            response = client.get(
                "/api/students/by-class/JHS 1",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-School-ID": "OTHER-SCHOOL",  # Different school
                },
            )

            # Should fail due to tenant isolation
            assert response.status_code in [403, 404]


class TestAttendanceEndpoints:
    """Test attendance endpoints."""

    def test_record_attendance_valid(self, client, app):
        """Test recording valid attendance."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User

            student = Student.query.filter_by(school_id="TEST-001").first()
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

            response = client.post(
                "/api/homeroom/attendance",
                json={"student_id": student.id, "status": True},
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

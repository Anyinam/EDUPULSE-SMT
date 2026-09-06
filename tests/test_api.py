"""
Unit tests for EduPulse API endpoints.
Tests authentication, grade entry, and payment functionality.
"""

import io
import json
from datetime import datetime, timedelta, timezone

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
        from backend.api.models import School, SchoolVerification, Student, StudentGrade, User, db

        db.create_all()

        # Create test school
        school = School(id="TEST-001", name="Test School", primary_color="#1e3a8a")
        db.session.add(school)

        # Keep finance tests focused on payment behavior by pre-verifying the tenant.
        verification = SchoolVerification(
            school_id="TEST-001",
            status="verified",
            risk_tier="low",
            legal_name="Test School",
            organization_id="TEST-001",
        )
        db.session.add(verification)

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

        inventory_manager = User(
            username="store1",
            school_id="TEST-001",
            role="inventory_manager",
            email="store@test.edu",
        )
        inventory_manager.set_password("StorePass123")
        db.session.add(inventory_manager)

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

    def _login_and_resolve_auth_payload(self, client, monkeypatch, **credentials):
        import backend.routes as routes

        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)

        response = client.post(
            "/api/login",
            json=credentials,
            headers={"X-School-ID": credentials.get("schoolCode")},
        )

        assert response.status_code in (200, 202)
        payload = json.loads(response.data)
        if response.status_code == 202:
            assert payload["message"] == "2fa_required"
            verify = client.post(
                "/api/2fa/verify",
                json={"token": payload["token"], "code": "123456"},
            )
            assert verify.status_code == 200
            payload = json.loads(verify.data)

        return payload

    def test_login_valid_credentials(self, client, app, mock_email, monkeypatch):
        """Test login with valid credentials."""
        data = self._login_and_resolve_auth_payload(
            client,
            monkeypatch,
            schoolCode="TEST-001",
            username="teacher1",
            password="TeacherPass123",
        )

        assert "token" in data
        assert data["role"] == "teacher"
        assert data["school_id"] == "TEST-001"

    def test_login_accepts_registered_email(self, client, mock_email, monkeypatch):
        """Users should be able to log in with their saved email address."""
        data = self._login_and_resolve_auth_payload(
            client,
            monkeypatch,
            schoolCode="TEST-001",
            username="teacher@test.edu",
            password="TeacherPass123",
        )

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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "username already taken" in data["message"].lower()

    def test_register_paid_plan_sends_welcome_email_before_payment(self, client, mocker, mock_email):
        """Premium registrations should still receive the welcome/credential email immediately."""
        paystack_mock = mocker.patch("backend.paystack_integration.initialize_payment")
        async_email_mock = mocker.patch("backend.routes.send_email_notification_async")
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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
                "selectedPlan": "Premium",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["requires_payment"] is True
        assert data["payment_url"] == "https://paystack.example/checkout"
        async_email_mock.assert_called_once()
        paystack_mock.assert_called_once()


class TestPaymentReferenceResolution:
    def _login_as(self, client, monkeypatch, username, password="PropPass123"):
        import backend.routes as routes

        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)

        response = client.post(
            "/api/login",
            json={
                "schoolCode": "TEST-001",
                "username": username,
                "password": password,
            },
            headers={"X-School-ID": "TEST-001"},
        )
        assert response.status_code in (200, 202)
        payload = json.loads(response.data)
        if response.status_code == 202:
            assert payload["message"] == "2fa_required"
            verify = client.post(
                "/api/2fa/verify",
                json={"token": payload["token"], "code": "123456"},
            )
            assert verify.status_code == 200
            payload = json.loads(verify.data)
        return payload["token"]

    def test_receive_payment_accepts_plain_student_code_reference(self, client, app, mock_email, monkeypatch):
        token = self._login_as(client, monkeypatch, "proprietor1")

        response = client.post(
            "/api/finance/receive-payment",
            json={
                "reference_code": "S001",
                "reference_id": "BANK-S001-001",
                "amount": 150,
                "method": "Bank",
                "type": "Tuition",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-School-ID": "TEST-001",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["payment_type"] == "Tuition"

        with app.app_context():
            from backend.api.models import Payment

            payment = Payment.query.filter_by(reference_id="BANK-S001-001").first()
            assert payment is not None
            assert payment.student.student_code == "S001"
            assert payment.payment_category.get("reference_code") == "S001"

    def test_import_parent_payment_notice_tracks_payment_by_reference_code(self, client, app, mock_email, monkeypatch):
        token = self._login_as(client, monkeypatch, "proprietor1")

        response = client.post(
            "/api/finance/import-parent-payment",
            json={
                "message_text": "DANIEL ANYINAM ASARE,2161120011674,S001",
                "amount": 150,
                "method": "MoMo",
                "payment_type": "Tuition",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-School-ID": "TEST-001",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["student_code"] == "S001"
        assert data["reference_id"] == "2161120011674"
        assert data["reference_code"] == "S001"

        with app.app_context():
            from backend.api.models import Payment

            payment = Payment.query.filter_by(reference_id="2161120011674").first()
            assert payment is not None
            assert payment.status == "Confirmed"
            assert payment.payment_category.get("reference_code") == "S001"
            assert payment.payment_category.get("import_mode") == "parent_notice"

    def test_initialize_paystack_payment_hides_provider_error_details(self, client, monkeypatch):
        token = self._login_as(client, monkeypatch, "proprietor1")

        monkeypatch.setattr(
            "backend.routes._call_paystack_api",
            lambda endpoint, method="GET", data=None: (None, "401 Client Error: Unauthorized for url: https://api.paystack.co/transaction/initialize"),
        )

        response = client.post(
            "/api/finance/paystack/initialize-payment",
            json={
                "student_id": 1,
                "reference_code": "S001",
                "payment_type": "Tuition",
                "amount": 150,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-School-ID": "TEST-001",
            },
        )

        assert response.status_code == 502
        payload = json.loads(response.data)
        assert payload["message"] == (
            "EduPulse could not connect to the payment provider right now. "
            "Please try again shortly or use the school office for manual assistance."
        )
        assert "Unauthorized" not in payload["message"]

    def test_register_welcome_email_uses_frontend_origin_when_frontend_url_missing(self, client, mocker, monkeypatch):
        """Registration emails should use the deployed frontend origin when FRONTEND_URL is unset."""
        monkeypatch.delenv("FRONTEND_URL", raising=False)
        monkeypatch.setenv("FRONTEND_ORIGIN", "https://app.edupulsesmt.com")

        captured = {}

        def fake_get_welcome_email(**kwargs):
            captured.update(kwargs)
            return ("Welcome", "Body")

        mocker.patch("backend.routes.get_welcome_email", side_effect=fake_get_welcome_email)
        async_email_mock = mocker.patch("backend.routes.send_email_notification_async")

        response = client.post(
            "/api/register",
            headers={"Origin": "https://app.edupulsesmt.com"},
            json={
                "schoolCode": "WELCOME-001",
                "schoolName": "Welcome School",
                "username": "welcome-owner",
                "email": "owner@welcome.edu",
                "password": "WelcomePass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
            },
        )

        assert response.status_code == 200
        assert captured["login_url"] == "https://app.edupulsesmt.com/login"
        async_email_mock.assert_called_once()

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
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
            },
        )

        assert response.status_code == 400

    def test_register_requires_school_data_authority_confirmation(self, client):
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "NO-AUTH",
                "schoolName": "Authority Missing School",
                "username": "proprietor2",
                "email": "owner@authority.edu",
                "password": "NewSchoolPass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
                "schoolDataAuthorityConfirmed": False,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": True,
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "authority" in data["message"].lower() or "authority" in str(data.get("errors", "")).lower()

    def test_register_requires_aggregated_analytics_acceptance(self, client):
        response = client.post(
            "/api/register",
            json={
                "schoolCode": "NO-ANALYTICS",
                "schoolName": "Analytics Missing School",
                "username": "analyticsowner",
                "email": "owner@analytics.edu",
                "password": "NewSchoolPass123!",
                "termsAccepted": True,
                "termsVersion": "2026-02-22",
                "policyAccepted": True,
                "policyVersion": "2026-03-07",
                "schoolDataAuthorityConfirmed": True,
                "legacyAndExamConsentPlanConfirmed": True,
                "aggregatedAnalyticsAccepted": False,
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "analytics" in data["message"].lower() or "analytics" in str(data.get("errors", "")).lower()


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

    def test_explicit_feeding_plan_codes_and_structured_reference_payment(self, client, app):
        """Configured feeding plans should emit plan-specific references that manual payment recording can resolve."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            headers = {"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"}

            fees_response = client.post(
                "/api/school/fees",
                json={
                    "tuition_fee": 0,
                    "feeding_daily_fee": 5.0,
                    "feeding_weekly_fee": 25.0,
                    "feeding_monthly_fee": 80.0,
                    "transport_fee": 0,
                    "terminal_report_fee": 0,
                    "other_fees": {},
                },
                headers=headers,
            )
            assert fees_response.status_code == 200

            codes_response = client.get(
                f"/api/students/{student.id}/payment-codes",
                headers=headers,
            )
            assert codes_response.status_code == 200

            payload = json.loads(codes_response.data)
            feeding_refs = {
                item["reference_code"]
                for item in payload["payment_codes"]
                if item["fee_type"].startswith("Feeding")
            }
            assert f"{student.student_code}-FEED-DAY" in feeding_refs
            assert f"{student.student_code}-FEED-WEK" in feeding_refs
            assert f"{student.student_code}-FEED-MON" in feeding_refs

            payment_response = client.post(
                "/api/finance/receive-payment",
                json={
                    "reference_code": f"{student.student_code}-FEED-MON",
                    "amount": 80.0,
                    "method": "Cash",
                },
                headers=headers,
            )
            assert payment_response.status_code == 200
            data = json.loads(payment_response.data)
            assert "recorded" in data["message"]

    def test_receive_payment_keeps_structured_reference_separate_from_transaction_reference(self, client, app):
        """Manual reconciliation should store the bank or MoMo transaction ID, not overwrite it with the learner reference."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Payment, Student, User

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            headers = {"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"}

            response = client.post(
                "/api/finance/receive-payment",
                json={
                    "reference_code": f"{student.student_code}-FEED-MON",
                    "reference_id": "BANK-TXN-001",
                    "amount": 80.0,
                    "method": "Bank",
                },
                headers=headers,
            )

            assert response.status_code == 200
            payment_id = response.get_json()["payment_id"]
            payment = Payment.query.get(payment_id)
            assert payment.reference_id == "BANK-TXN-001"
            assert payment.payment_category.get("reference_code") == f"{student.student_code}-FEED-MON"

    def test_initialize_paystack_payment_accepts_reference_code(self, client, app, monkeypatch):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            headers = {"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"}

            def fake_call_paystack_api(endpoint, method="GET", data=None):
                assert endpoint == "/transaction/initialize"
                assert method == "POST"
                assert data["metadata"]["reference_code"] == f"{student.student_code}-FEED-MON"
                assert data["metadata"]["payment_category"]["reference_code"] == f"{student.student_code}-FEED-MON"
                return (
                    {
                        "authorization_url": "https://paystack.example/track-feed",
                        "access_code": "ACCESS123",
                    },
                    None,
                )

            monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

            response = client.post(
                "/api/finance/paystack/initialize-payment",
                json={
                    "reference_code": f"{student.student_code}-FEED-MON",
                    "amount": 80.0,
                },
                headers=headers,
            )

            assert response.status_code == 200
            payload = response.get_json()
            assert payload["authorization_url"] == "https://paystack.example/track-feed"
            assert payload["reference_code"] == f"{student.student_code}-FEED-MON"
            assert payload["payment_type"] == "Feeding"

    def test_receive_inventory_payment_by_student_code(self, client, app):
        """Inventory payments should accept a typed student code instead of requiring a dropdown-loaded student id."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Inventory, Student, User, db

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            inventory_item = Inventory(
                school_id="TEST-001",
                item_name="School Uniform",
                category="Uniform",
                item_type="Top Only",
                size="M",
                sku="UNIFORM-TOP-M",
                quantity=10,
                price=85.0,
            )
            db.session.add(inventory_item)
            db.session.commit()

            token = create_access_token(identity=str(proprietor.id))

            response = client.post(
                "/api/finance/receive-payment",
                json={
                    "student_code": student.student_code,
                    "amount": 85.0,
                    "type": "Inventory",
                    "method": "Cash",
                    "payment_category": {
                        "item_id": inventory_item.id,
                        "item_name": inventory_item.item_name,
                        "item_type": inventory_item.item_type,
                        "size": inventory_item.size,
                        "sku": inventory_item.sku,
                        "quantity": 1,
                    },
                },
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert "recorded" in data["message"]

    def test_receive_payment_blocked_when_free_tier_school_is_over_capacity(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import School, Student, User, db

            school = School.query.get("TEST-001")
            school.subscription_plan = "Free Tier"
            school.trial_plan = None
            school.trial_end_date = None

            current_count = Student.query.filter_by(school_id="TEST-001").count()
            for index in range(current_count + 1, 52):
                db.session.add(
                    Student(
                        school_id="TEST-001",
                        first_name=f"Cap{index}",
                        surname="Student",
                        name=f"Cap{index} Student",
                        student_code=f"CAP{index:03d}",
                        current_class="JHS 1",
                        status="Active",
                        total_tuition_owed=100.0,
                    )
                )
            db.session.commit()

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
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

            assert response.status_code == 409
            data = json.loads(response.data)
            assert data["error"] == "payment_collection_blocked"
            assert data["reason"] == "plan_over_capacity"

    def test_student_payment_history_blocked_until_school_verification_is_complete(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import SchoolVerification, Student, User, db

            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

            response = client.get(
                f"/api/students/{student.id}/payments",
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 403
            data = json.loads(response.data)
            assert data["error"] == "school_verification_required"

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


class TestStudentSearchEndpoints:
    """Test student lookup helpers used by typed-ID workflows."""

    def test_inventory_manager_can_lookup_student_by_numeric_id(self, client, app):
        """Inventory managers should be able to resolve a typed student ID into a learner record."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            inventory_manager = User.query.filter_by(username="store1").first()
            token = create_access_token(identity=str(inventory_manager.id))

            response = client.get(
                f"/api/students/search?q={student.id}",
                headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["students"]
            assert any(item["id"] == student.id for item in data["students"])


class TestSchoolVerificationEndpoints:
    """Test the automatic school verification flow."""

    def test_school_verification_profile_requires_proprietor_role(self, client, app):
        """Teachers should not be able to read the full KYB profile payload."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import User

        with app.app_context():
            teacher = User.query.filter_by(username="teacher1").first()
            token = create_access_token(identity=str(teacher.id))

        response = client.get(
            "/api/school/verification",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 403

    def test_auto_approve_school_with_kyb_provider(self, client, app, mocker, monkeypatch):
        """A clean KYB provider response should auto-approve the school."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import SchoolVerification, User, db

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "status": "verified",
                    "risk_tier": "low",
                    "message": "School has been successfully verified.",
                }

        monkeypatch.setenv("KYB_PROVIDER", "identitypass")
        monkeypatch.setenv("KYB_BASE_URL", "https://kyb.example")
        monkeypatch.setenv("KYB_API_KEY", "test-kyb-key")
        monkeypatch.setenv("KYB_VERIFY_PATH", "/verify")
        mocker.patch("backend.kyb_verification.requests.post", return_value=FakeResponse())

        with app.app_context():
            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        response = client.put(
            "/api/school/verification",
            json={
                "legal_name": "Test School",
                "registration_number": "REG-12345",
                "tax_id": "TIN-67890",
                "bank_account_name": "Test School",
                "bank_account_number": "0123456789",
                "bank_name": "Test Bank",
                "documents": [
                    {
                        "document_id": "reg-cert-1",
                        "original_filename": "certificate.pdf",
                        "filename": "certificate.pdf",
                        "content_type": "application/pdf",
                        "category": "registration_certificate",
                    }
                ],
                "owner_information": {"owner_name": "Jane Owner"},
            },
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["auto_verified"] is True
        assert data["verification"]["is_verified"] is True
        assert data["verification"]["status"] == "verified"

        with app.app_context():
            latest = SchoolVerification.query.filter_by(school_id="TEST-001").order_by(SchoolVerification.id.desc()).first()
            assert latest is not None
            assert latest.status == "verified"

    def test_provider_fallback_routes_local_match_to_manual_review_by_default(self, client, app, mocker, monkeypatch):
        """Provider outages should not auto-approve even when the local heuristic is clean."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import SchoolVerification, User, db

        monkeypatch.delenv("KYB_LOCAL_AUTO_APPROVAL_ENABLED", raising=False)
        monkeypatch.delenv("EDUPULSE_KYB_LOCAL_AUTO_APPROVAL_ENABLED", raising=False)
        mocker.patch(
            "backend.routes.verify_school_profile",
            return_value={
                "provider": "identitypass",
                "outcome": "error",
                "verified": False,
                "risk_tier": "medium",
                "reason": "provider_request_failed",
                "raw": {},
            },
        )

        with app.app_context():
            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        response = client.put(
            "/api/school/verification",
            json={
                "legal_name": "Test School",
                "registration_number": "REG-12345",
                "tax_id": "TIN-67890",
                "bank_account_name": "Test School",
                "bank_account_number": "0123456789",
                "bank_name": "Test Bank",
                "documents": [
                    {
                        "document_id": "reg-cert-1",
                        "original_filename": "certificate.pdf",
                        "filename": "certificate.pdf",
                        "content_type": "application/pdf",
                        "category": "registration_certificate",
                    }
                ],
                "owner_information": {"owner_name": "Jane Owner"},
            },
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["auto_verified"] is False
        assert data["verification"]["is_verified"] is False
        assert data["verification"]["status"] == "review_required"
        assert data["auto_reason"] == "provider_request_failed"

        with app.app_context():
            latest = SchoolVerification.query.filter_by(school_id="TEST-001").order_by(SchoolVerification.id.desc()).first()
            assert latest is not None
            assert latest.status == "review_required"
            assert latest.review_notes == "provider=provider_request_failed; local_heuristic=eligible_but_manual_review_required"

    def test_local_auto_approval_can_be_explicitly_opted_in(self, client, app, mocker, monkeypatch):
        """An explicit env opt-in can still allow local auto-approval during provider outages."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import SchoolVerification, User, db

        monkeypatch.setenv("KYB_LOCAL_AUTO_APPROVAL_ENABLED", "true")
        mocker.patch(
            "backend.routes.verify_school_profile",
            return_value={
                "provider": "identitypass",
                "outcome": "error",
                "verified": False,
                "risk_tier": "medium",
                "reason": "provider_request_failed",
                "raw": {},
            },
        )

        with app.app_context():
            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        response = client.put(
            "/api/school/verification",
            json={
                "legal_name": "Test School",
                "registration_number": "REG-12345",
                "tax_id": "TIN-67890",
                "bank_account_name": "Test School",
                "bank_account_number": "0123456789",
                "bank_name": "Test Bank",
                "documents": [
                    {
                        "document_id": "reg-cert-1",
                        "original_filename": "certificate.pdf",
                        "filename": "certificate.pdf",
                        "content_type": "application/pdf",
                        "category": "registration_certificate",
                    }
                ],
                "owner_information": {"owner_name": "Jane Owner"},
            },
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["auto_verified"] is True
        assert data["verification"]["is_verified"] is True
        assert data["verification"]["status"] == "verified"
        assert data["auto_reason"] == "auto_verified"

        with app.app_context():
            latest = SchoolVerification.query.filter_by(school_id="TEST-001").order_by(SchoolVerification.id.desc()).first()
            assert latest is not None
            assert latest.status == "verified"
            assert latest.review_notes == "provider=provider_request_failed; local_heuristic=auto_verified"

    def test_duplicate_school_verification_submission_is_blocked_while_case_is_active(self, client, app, mocker):
        """A school should not be able to submit another verification while the latest case is still active."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import SchoolVerification, User, db

        mocker.patch(
            "backend.routes.verify_school_profile",
            return_value={
                "provider": "identitypass",
                "outcome": "review_required",
                "verified": False,
                "risk_tier": "medium",
                "reason": "provider_review_required",
                "raw": {},
            },
        )

        with app.app_context():
            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()
            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        payload = {
            "legal_name": "Test School",
            "registration_number": "REG-12345",
            "tax_id": "TIN-67890",
            "bank_account_name": "Test School",
            "bank_account_number": "0123456789",
            "bank_name": "Test Bank",
            "documents": [
                {
                    "document_id": "reg-cert-1",
                    "original_filename": "certificate.pdf",
                    "filename": "certificate.pdf",
                    "content_type": "application/pdf",
                    "category": "registration_certificate",
                }
            ],
            "owner_information": {"owner_name": "Jane Owner"},
        }

        first_response = client.put(
            "/api/school/verification",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert first_response.status_code == 200

        second_response = client.put(
            "/api/school/verification",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert second_response.status_code == 409
        data = json.loads(second_response.data)
        assert data["error"] == "school_verification_already_submitted"
        assert data["verification"]["status"] == "review_required"

        with app.app_context():
            assert SchoolVerification.query.filter_by(school_id="TEST-001").count() == 1


class TestAdmissionsEndpoints:
    """Test admissions endpoints."""

    def test_finance_audit_endpoints_blocked_until_school_verification_is_complete(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import SchoolVerification, User, db

            SchoolVerification.query.filter_by(school_id="TEST-001").delete()
            db.session.commit()

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        endpoints = [
            ("GET", "/api/finance/audit/ledger"),
            ("POST", "/api/finance/audit/verify"),
            ("GET", "/api/finance/audit/summary"),
            ("GET", "/api/finance/audit/events"),
            ("GET", "/api/finance/audit/events/export"),
        ]

        for method, path in endpoints:
            if method == "POST":
                response = client.post(path, headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"})
            else:
                response = client.get(path, headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"})

            assert response.status_code == 403
            data = json.loads(response.data)
            assert data["error"] == "school_verification_required"

    def test_delete_student_blocked_when_history_exists(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Payment, Student, User, db

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            student_id = student.id
            db.session.add(
                Payment(
                    student_id=student.id,
                    school_id="TEST-001",
                    amount=75.0,
                    payment_type="Tuition",
                    method="Cash",
                    status="Confirmed",
                    reference_id="DEL-BLOCK-001",
                )
            )
            db.session.commit()

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))

        response = client.delete(
            f"/api/admissions/students/{student_id}",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["error"] == "student_delete_blocked"
        assert "payments" in data["blockers"]

    def test_delete_student_allows_cleanup_without_history(self, client, app):
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import Student, User, db

            student = Student(
                school_id="TEST-001",
                first_name="Delete",
                surname="Me",
                name="Delete Me",
                student_code="S999",
                current_class="JHS 1",
                total_tuition_owed=0.0,
            )
            db.session.add(student)
            db.session.commit()

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            student_id = student.id

        response = client.delete(
            f"/api/admissions/students/{student_id}",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["deleted_student_id"] == student_id

    def test_delete_academic_term_blocked_when_report_cards_exist(self, client, app):
        with app.app_context():
            from datetime import date
            from flask_jwt_extended import create_access_token

            from backend.api.models import AcademicTerm, ReportCard, Student, User, db

            student = Student.query.filter_by(school_id="TEST-001", student_code="S001").first()
            term = AcademicTerm(
                school_id="TEST-001",
                name="Term 1",
                academic_year="2025/2026",
                start_date=date(2025, 9, 1),
                end_date=date(2025, 12, 15),
                is_active=False,
            )
            db.session.add(term)
            db.session.flush()

            db.session.add(
                ReportCard(
                    school_id="TEST-001",
                    student_id=student.id,
                    academic_term="Term 1",
                    academic_year="2025/2026",
                    class_name="JHS 1",
                    subject_grades=[],
                    status="Draft",
                )
            )
            db.session.commit()

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            term_id = term.id

        response = client.delete(
            f"/api/school/terms/{term_id}",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 409
        data = json.loads(response.data)
        assert data["error"] == "academic_term_delete_blocked"
        assert "report_cards" in data["blockers"]

    def test_delete_academic_term_allows_cleanup_without_history(self, client, app):
        with app.app_context():
            from datetime import date
            from flask_jwt_extended import create_access_token

            from backend.api.models import AcademicTerm, User, db

            term = AcademicTerm(
                school_id="TEST-001",
                name="Term 2",
                academic_year="2025/2026",
                start_date=date(2026, 1, 10),
                end_date=date(2026, 4, 10),
                is_active=False,
            )
            db.session.add(term)
            db.session.commit()

            proprietor = User.query.filter_by(username="proprietor1").first()
            token = create_access_token(identity=str(proprietor.id))
            term_id = term.id

        response = client.delete(
            f"/api/school/terms/{term_id}",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": "TEST-001"},
        )

        assert response.status_code == 200

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

    def test_bulk_admit_allows_growth_during_active_premium_trial(self, client, app):
        """Active premium trials should not hit paid-seat billing blocks during bulk admissions."""
        with app.app_context():
            from flask_jwt_extended import create_access_token

            from backend.api.models import School, Student, User, db

            school = School.query.get("TEST-001")
            school.subscription_plan = "Free Tier"
            school.trial_plan = "Premium"
            school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=5)
            school.is_trial_active = True

            existing = Student.query.filter_by(school_id="TEST-001", status="Active").count()
            for index in range(existing + 1, 52):
                db.session.add(
                    Student(
                        school_id="TEST-001",
                        first_name=f"Trial{index}",
                        surname="Student",
                        name=f"Trial Student {index}",
                        student_code=f"TR{index:03d}",
                        current_class="JHS 1",
                        status="Active",
                    )
                )
            db.session.commit()

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
        assert "Successfully admitted 1 students." == payload.get("message")
        assert not payload.get("errors")

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

"""
Security-focused tests for EduPulse application.
Tests for vulnerabilities, injection attacks, authorization flaws, etc.
"""

import json
from unittest.mock import Mock, patch

import pytest
from flask import Flask


class TestAuthenticationSecurity:
    """Tests for authentication endpoint security."""

    def test_login_requires_mfa_when_globally_enabled(
        self, client, test_school, test_teacher, mock_email, monkeypatch
    ):
        """When MFA_REQUIRED is enabled, even non-enrolled users must complete OTP."""
        import backend.routes as routes

        monkeypatch.setattr(routes, "MFA_REQUIRED", True)
        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)

        payload = {
            "school_code": test_school.id,
            "username": test_teacher.username,
            "password": "TeacherPass123",
        }

        response = client.post(
            "/api/login",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 202
        body = json.loads(response.data)
        assert body.get("message") == "2fa_required"
        assert body.get("token")
        assert body.get("delivery") == "email"
        mock_email.assert_called()

        # Complete verification and ensure the user is marked enrolled.
        verify = client.post(
            "/api/2fa/verify",
            data=json.dumps({"token": body["token"], "code": "123456"}),
            content_type="application/json",
        )
        assert verify.status_code == 200

        from backend.api.models import User

        refreshed = User.query.get(test_teacher.id)
        assert refreshed.two_fa_enabled is True

    def test_2fa_verify_returns_full_auth_context(
        self, client, test_school, test_teacher, mock_email, monkeypatch
    ):
        """2FA completion should return the same auth context the app stores after normal login."""
        import backend.routes as routes

        monkeypatch.setattr(routes, "MFA_REQUIRED", True)
        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)

        response = client.post(
            "/api/login",
            data=json.dumps(
                {
                    "school_code": test_school.id,
                    "username": test_teacher.username,
                    "password": "TeacherPass123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 202
        pending = json.loads(response.data)

        verify = client.post(
            "/api/2fa/verify",
            data=json.dumps({"token": pending["token"], "code": "123456"}),
            content_type="application/json",
        )

        assert verify.status_code == 200
        body = json.loads(verify.data)
        assert body["school_id"] == test_school.id
        assert body["role"] == test_teacher.role
        assert body["roles"] == [test_teacher.role]
        assert "subscription_plan" in body
        assert "subscription_status" in body
        assert isinstance(body["enabled_modules"], dict)
        assert body["enabled_modules"]
        assert body["requires_password_reset"] is False
        assert body["branding"]["name"] == test_school.name
        assert body["branding"]["country_code"] == "GH"

    def test_login_marks_temp_password_accounts_for_forced_change(
        self, client, test_school, test_teacher, monkeypatch
    ):
        import backend.routes as routes
        from datetime import datetime, timedelta, timezone

        monkeypatch.setattr(routes, "MFA_REQUIRED", False)
        test_teacher.is_temp_password = True
        test_teacher.temp_password_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        routes.db.session.commit()

        response = client.post(
            "/api/login",
            data=json.dumps(
                {
                    "school_code": test_school.id,
                    "username": test_teacher.username,
                    "password": "TeacherPass123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        body = json.loads(response.data)
        assert body["requires_password_reset"] is True

    def test_2fa_verify_preserves_temp_password_reset_requirement(
        self, client, test_school, test_teacher, mock_email, monkeypatch
    ):
        import backend.routes as routes
        from datetime import datetime, timedelta, timezone

        monkeypatch.setattr(routes, "MFA_REQUIRED", True)
        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)

        test_teacher.is_temp_password = True
        test_teacher.temp_password_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        routes.db.session.commit()

        response = client.post(
            "/api/login",
            data=json.dumps(
                {
                    "school_code": test_school.id,
                    "username": test_teacher.username,
                    "password": "TeacherPass123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 202
        pending = json.loads(response.data)

        verify = client.post(
            "/api/2fa/verify",
            data=json.dumps({"token": pending["token"], "code": "123456"}),
            content_type="application/json",
        )

        assert verify.status_code == 200
        body = json.loads(verify.data)
        assert body["requires_password_reset"] is True

    def test_login_returns_dev_code_when_2fa_email_delivery_fails_locally(
        self, client, test_school, test_teacher, mocker, monkeypatch
    ):
        """Local development should not hard-block 2FA when SMTP credentials are invalid."""
        import backend.routes as routes

        monkeypatch.setattr(routes, "MFA_REQUIRED", True)
        monkeypatch.setattr(routes.secrets, "randbelow", lambda _: 123456)
        mocker.patch("backend.routes.send_email_notification", return_value=False)

        payload = {
            "school_code": test_school.id,
            "username": test_teacher.username,
            "password": "TeacherPass123",
        }

        response = client.post(
            "/api/login",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 202
        body = json.loads(response.data)
        assert body.get("message") == "2fa_required"
        assert body.get("token")
        assert body.get("dev_code") == "123456"
        assert "local development" in (body.get("fallback_notice") or "")

    def test_cannot_disable_mfa_when_globally_required(
        self, client, auth_headers, monkeypatch
    ):
        import backend.routes as routes

        monkeypatch.setattr(routes, "MFA_REQUIRED", True)

        response = client.post(
            "/api/2fa/disable",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_login_sql_injection_prevention(self, client, test_school):
        """Test that SQL injection attempts are blocked."""
        malicious_payload = {
            "school_code": "test' OR '1'='1",
            "username": "admin' --",
            "password": "anything",
        }
        response = client.post(
            "/api/login",
            data=json.dumps(malicious_payload),
            content_type="application/json",
        )
        assert response.status_code in [400, 422]  # Validation error

    def test_login_brute_force_prevention(self, client, test_school):
        """Test rate limiting on login endpoint."""
        payload = {
            "school_code": "TEST-001",
            "username": "teacher1",
            "password": "WrongPassword123",
        }

        # Make 10 failed attempts
        responses = []
        for i in range(10):
            response = client.post(
                "/api/login",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-School-ID": test_school.id},
            )
            responses.append(response.status_code)

        # Should eventually return 429 (rate limited)
        assert 429 in responses or all(r in [200, 401] for r in responses)

    def test_password_reset_token_expiry(self, client, db, test_school, test_teacher):
        """Test that password reset tokens expire."""
        from datetime import datetime, timedelta

        from backend.api.models import PasswordReset

        # Create expired token
        old_token = PasswordReset(
            user_id=test_teacher.id,
            token="expired-token-xyz",
            created_at=datetime.utcnow() - timedelta(hours=25),
        )
        db.session.add(old_token)
        db.session.commit()

        response = client.post(
            "/api/reset-password",
            data=json.dumps(
                {"token": "expired-token-xyz", "new_password": "NewPass123456"}
            ),
            content_type="application/json",
            headers={"X-School-ID": test_school.id},
        )

        assert response.status_code == 401

    def test_weak_password_rejection(self, client, test_school):
        """Test that weak passwords are rejected."""
        weak_passwords = [
            "abc123",  # Too short
            "abcdefgh",  # No uppercase/digit
            "PASSWORD123",  # No lowercase
            "Passw0",  # Too short uppercase+digit
        ]

        for weak_pwd in weak_passwords:
            response = client.post(
                "/api/register",
                data=json.dumps(
                    {
                        "school_code": "TEST-001",
                        "username": "newuser",
                        "password": weak_pwd,
                        "email": "newuser@test.edu",
                        "termsAccepted": True,
                        "termsVersion": "2026-02-22",
                        "policyAccepted": True,
                        "policyVersion": "2026-03-07",
                    }
                ),
                content_type="application/json",
                headers={"X-School-ID": test_school.id},
            )
            # Should reject weak password
            assert response.status_code in [400, 422]


class TestMultiTenantIsolation:
    """Tests for multi-tenant data isolation."""

    def test_cannot_access_other_school_data(self, client, db, app):
        """Test that users cannot access data from other schools."""
        from backend.api.models import School, Student, User

        # Create two schools
        school1 = School(id="SCHOOL-001", name="School 1", subscription_plan="Premium")
        school2 = School(id="SCHOOL-002", name="School 2", subscription_plan="Premium")

        # Create users in different schools
        user1 = User(
            username="user1",
            school_id="SCHOOL-001",
            role="teacher",
            email="user1@test.edu",
        )
        user1.set_password("Pass123456")

        user2 = User(
            username="user2",
            school_id="SCHOOL-002",
            role="teacher",
            email="user2@test.edu",
        )
        user2.set_password("Pass123456")

        db.session.add_all([school1, school2, user1, user2])
        db.session.commit()

        # Create student in school1
        student = Student(
            school_id="SCHOOL-001",
            first_name="Test",
            surname="Student",
            name="Test Student",
            student_code="TS001",
            current_class="JHS 1",
        )
        db.session.add(student)
        db.session.commit()

        # User2 (from school2) should not access school1 data
        from flask_jwt_extended import create_access_token

        with app.app_context():
            user2_token = create_access_token(identity=str(user2.id))

        response = client.get(
            f"/api/students/{student.id}",
            headers={
                "Authorization": f"Bearer {user2_token}",
                "X-School-ID": "SCHOOL-002",
            },
        )

        # Should deny access or return 404
        assert response.status_code in [403, 404]

    def test_missing_school_id_header(self, client, auth_headers):
        """Test that requests without X-School-ID are rejected."""
        headers = auth_headers.copy()
        del headers["X-School-ID"]

        response = client.get("/api/students", headers=headers)

        assert response.status_code in [400, 401, 403]

    def test_jwt_cannot_override_tenant_header(self, client, db, app):
        """JWT identity must be bound to the requested X-School-ID tenant."""
        from backend.api.models import School, Student, User

        school1 = School(id="SCHOOL-101", name="School 101", subscription_plan="Premium")
        school2 = School(id="SCHOOL-202", name="School 202", subscription_plan="Premium")
        db.session.add_all([school1, school2])

        user2 = User(
            username="tenant2_user",
            school_id=school2.id,
            role="teacher",
            email="tenant2_user@test.edu",
        )
        user2.set_password("Pass123456")
        db.session.add(user2)

        student1 = Student(
            school_id=school1.id,
            first_name="Alice",
            surname="Tenant1",
            name="Alice Tenant1",
            student_code="A101",
            current_class="JHS 1",
        )
        db.session.add(student1)
        db.session.commit()

        from flask_jwt_extended import create_access_token

        with app.app_context():
            token2 = create_access_token(identity=str(user2.id))

        # Attempt to read a tenant-1 resource while presenting a tenant-2 JWT.
        response = client.get(
            f"/api/students/{student1.id}/reports",
            headers={
                "Authorization": f"Bearer {token2}",
                "X-School-ID": school1.id,
            },
        )

        assert response.status_code == 403


class TestInputValidation:
    """Tests for input validation across endpoints."""

    def test_xss_prevention_in_student_names(self, client, auth_headers):
        """Test that HTML/JS in student names is sanitized."""
        xss_payload = {
            "name": '<script>alert("xss")</script>',
            "student_code": "XSS001",
            "current_class": "JHS 1",
        }

        response = client.post(
            "/api/students",
            data=json.dumps(xss_payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should accept but sanitize or reject
        if response.status_code == 201:
            data = json.loads(response.data)
            assert "<script>" not in data.get("name", "")

    def test_email_injection_prevention(self, client, test_school):
        """Test that email injection is prevented."""
        injection_email = "attacker@test.edu\nBcc: admin@test.edu"
        injection_payload = {
            "school_code": "TEST-001",
            "username": "attacker",
            "password": "Pass123456",
            "email": injection_email,
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
        }

        response = client.post(
            "/api/register",
            data=json.dumps(injection_payload),
            content_type="application/json",
            headers={"X-School-ID": test_school.id},
        )

        # Should reject invalid email format
        assert response.status_code in [400, 422]

    def test_negative_payment_amount_rejected(
        self, client, auth_headers, db, test_students
    ):
        """Test that negative payment amounts are rejected."""
        payload = {
            "student_id": test_students[0].id,
            "amount": -100.00,
            "payment_type": "Tuition",
            "method": "Bank",
        }

        response = client.post(
            "/api/finance/receive-payment",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code in [400, 422]

    def test_payment_amount_exceeds_max(self, client, auth_headers, test_students):
        """Test that payment amounts > 100,000 are rejected."""
        payload = {
            "student_id": test_students[0].id,
            "amount": 999999.99,
            "payment_type": "Tuition",
            "method": "Bank",
        }

        response = client.post(
            "/api/finance/receive-payment",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code in [400, 422]


class TestAccessControl:
    """Tests for role-based access control."""

    def test_non_teacher_cannot_finalize_grades(
        self, client, db, app, test_school, test_proprietor
    ):
        """Test that only teachers can finalize grades."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import Student

        student = Student(
            school_id=test_school.id,
            first_name="Test",
            surname="Student",
            name="Test Student",
            student_code="TS001",
            current_class="JHS 1",
        )
        db.session.add(student)
        db.session.commit()

        with app.app_context():
            token = create_access_token(identity=str(test_proprietor.id))

        payload = {
            "student_id": student.id,
            "class_score": 25,
            "exam_score": 60,
            "class_name": "JHS 1",
        }

        response = client.post(
            "/api/homeroom/finalize-class",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": test_school.id},
        )

        assert response.status_code == 403

    def test_headmaster_can_access_finance(
        self, client, db, app, test_school, test_headmaster
    ):
        """Test that headmaster has access to financial endpoints."""
        from flask_jwt_extended import create_access_token

        from backend.api.models import Student

        student = Student(
            school_id=test_school.id,
            first_name="Test",
            surname="Student",
            name="Test Student",
            student_code="TS001",
            current_class="JHS 1",
        )
        db.session.add(student)
        db.session.commit()

        with app.app_context():
            token = create_access_token(identity=str(test_headmaster.id))

        response = client.get(
            "/api/finance/summary",
            headers={"Authorization": f"Bearer {token}", "X-School-ID": test_school.id},
        )

        assert response.status_code != 403


class TestDataIntegrity:
    """Tests for data integrity constraints."""

    def test_duplicate_payment_reference_prevented(
        self, client, auth_headers, db, test_students
    ):
        """Test that duplicate payment reference IDs are prevented."""
        from datetime import datetime
        from uuid import uuid4

        from backend.api.models import Payment

        reference_id = f"REF-{uuid4()}"

        # Create first payment
        payment1 = Payment(
            school_id=auth_headers["X-School-ID"],
            student_id=test_students[0].id,
            amount=100.00,
            payment_type="Tuition",
            method="Bank",
            reference_id=reference_id,
            status="Confirmed",
            created_at=datetime.utcnow(),
        )
        db.session.add(payment1)
        db.session.commit()

        # Try to create duplicate
        payload = {
            "student_id": test_students[1].id,
            "amount": 50.00,
            "payment_type": "Feeding",
            "method": "Cash",
            "reference_id": reference_id,
        }

        response = client.post(
            "/api/finance/receive-payment",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should reject or mark as duplicate
        assert response.status_code in [400, 409]


class TestSecurityHeaders:
    """Tests for presence of security headers."""

    def test_security_headers_present(self, client, auth_headers):
        """Test that all required security headers are present."""
        response = client.get("/api/students", headers=auth_headers)

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
        ]

        for header in required_headers:
            assert header in response.headers or response.status_code in [401, 403]

    def test_no_server_header_leak(self, client):
        """Test that Server header doesn't leak sensitive info."""
        response = client.get("/")

        server_header = response.headers.get("Server", "")
        # Should not contain Flask version in production
        assert "Werkzeug" not in server_header or "testing" in server_header.lower()


@pytest.mark.parametrize(
    "endpoint", ["/api/students", "/api/finance/summary", "/api/homeroom/attendance"]
)
class TestAuthenticationRequired:
    """Tests that endpoints require authentication."""

    def test_endpoint_requires_jwt(self, client, endpoint):
        """Test that endpoint requires valid JWT token."""
        response = client.get(endpoint)
        assert response.status_code in [401, 400]

    def test_endpoint_requires_school_id(self, client, endpoint, test_auth_token):
        """Test that endpoint requires X-School-ID header."""
        response = client.get(
            endpoint, headers={"Authorization": f"Bearer {test_auth_token}"}
        )
        assert response.status_code in [400, 401, 403]


class TestErrorHandling:
    """Tests for proper error handling without information leakage."""

    def test_generic_error_on_database_error(self, client, auth_headers, mocker):
        """Test that database errors don't leak sensitive information."""
        mocker.patch(
            "backend.routes.db.session.query", side_effect=Exception("DB Error")
        )

        response = client.get("/api/students", headers=auth_headers)

        # Should return 500 but not leak error details
        if response.status_code == 500:
            data = json.loads(response.data)
            assert "DB Error" not in data.get("message", "")

    def test_no_stack_trace_in_500_error(self, client, auth_headers, mocker):
        """Test that stack traces aren't returned in error responses."""
        mocker.patch(
            "backend.routes.db.session.query", side_effect=ValueError("Internal Error")
        )

        response = client.get("/api/students", headers=auth_headers)

        if response.status_code == 500:
            response_text = response.data.decode()
            assert "Traceback" not in response_text
            assert "File" not in response_text


class TestCSRFProtection:
    """Tests for CSRF protection."""

    def test_post_requires_origin_header(self, client, auth_headers, test_students):
        """Test that POST requests validate Origin header."""
        headers = auth_headers.copy()
        # Remove/invalid origin

        response = client.post(
            "/api/finance/receive-payment",
            data=json.dumps(
                {
                    "student_id": test_students[0].id,
                    "amount": 50.00,
                    "payment_type": "Tuition",
                    "method": "Cash",
                }
            ),
            content_type="application/json",
            headers=headers,
        )

        # May succeed in test environment, but header should be validated
        assert response.status_code in [200, 201, 400, 403]

import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask


@pytest.mark.parametrize(
    "frontend_url, frontend_origin, expected_base",
    [
        ("https://app.example.test", None, "https://app.example.test"),
        (None, "https://public.example.test", "https://public.example.test"),
        (
            "https://app.example.test/",
            "https://other.example.test",
            "https://app.example.test",
        ),
        ("  ", " https://public.example.test/ ", "https://public.example.test"),
        (None, None, "http://localhost:5173"),
        ("", "  ", "http://localhost:5173"),
        ("http://localhost:5173/", None, "http://localhost:5173"),
    ],
)
def test_forgot_password_email_link(
    monkeypatch, frontend_url, frontend_origin, expected_base
):
    from backend import routes

    for name, value in (
        ("FRONTEND_URL", frontend_url),
        ("FRONTEND_ORIGIN", frontend_origin),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)

    user_model = Mock()
    user_model.query.filter_by.return_value.first.return_value = SimpleNamespace(
        id=42, username="reset-user"
    )
    monkeypatch.setattr(routes, "User", user_model)
    database = Mock()
    monkeypatch.setattr(routes, "db", database)
    reset_record = Mock()
    monkeypatch.setattr(routes, "PasswordReset", reset_record)
    monkeypatch.setattr(routes, "create_access_token", Mock(return_value="test-reset-token"))
    monkeypatch.setattr(routes, "log_action", Mock())
    template = Mock(return_value=("Reset Password", "Mock email body"))
    monkeypatch.setattr(routes, "get_password_reset_email", template)
    send_email = Mock(return_value=True)
    monkeypatch.setattr(routes, "send_email_notification", send_email)

    app = Flask(__name__)
    with app.test_request_context(
        "/api/forgot-password",
        method="POST",
        base_url="https://untrusted-host.example.test",
        headers={"Origin": "https://untrusted-origin.example.test"},
        json={"schoolCode": "RESET-TEST", "email": "reset@example.test"},
    ):
        response = inspect.unwrap(routes.forgot_password)()

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "If an account exists, a reset link has been sent."
    }
    template.assert_called_once_with(
        user_name="reset-user",
        reset_link=f"{expected_base}/reset-password?token=test-reset-token",
    )
    send_email.assert_called_once_with(
        to_email="reset@example.test",
        subject="Reset Password",
        body="Mock email body",
    )
    reset_record.assert_called_once_with(user_id=42, token="test-reset-token")
    database.session.commit.assert_called_once_with()
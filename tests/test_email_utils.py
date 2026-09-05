import sys
from types import SimpleNamespace


def test_send_email_notification_uses_ses_provider(mocker, monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "ses")
    monkeypatch.setenv("SES_REGION", "us-east-1")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "info@edupulsesmt.com")

    ses_client = mocker.Mock()
    boto3_module = SimpleNamespace(client=mocker.Mock(return_value=ses_client))
    mocker.patch.dict(sys.modules, {"boto3": boto3_module})

    from backend.utils import send_email_notification

    result = send_email_notification(
        to_email="owner@example.com",
        subject="Welcome",
        body="Hello from SES",
    )

    assert result is True
    boto3_module.client.assert_called_once_with("ses", region_name="us-east-1")
    ses_client.send_email.assert_called_once()


def test_send_usage_report_email_uses_shared_mailer(mocker):
    fake_stats = {
        "school_name": "Testing School",
        "report_month": "September 2026",
        "proprietor_email": "owner@example.com",
    }

    mocker.patch("backend.email_service.get_school_usage_stats", return_value=fake_stats)
    mocker.patch("backend.email_service.render_usage_report_html", return_value="<p>Hello report</p>")
    mailer = mocker.patch("backend.email_service.send_email_notification", return_value=True)

    from backend.email_service import send_usage_report_email

    result = send_usage_report_email("TEST-001")

    assert result is True
    mailer.assert_called_once()
    args, kwargs = mailer.call_args
    assert args[0] == "owner@example.com"
    assert "Testing School" in args[1]
    assert kwargs["html_body"]


def test_send_usage_report_email_fails_without_recipient(mocker):
    mocker.patch("backend.email_service.get_school_usage_stats", return_value={"school_name": "Testing School"})

    from backend.email_service import send_usage_report_email

    assert send_usage_report_email("TEST-001") is False
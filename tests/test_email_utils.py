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
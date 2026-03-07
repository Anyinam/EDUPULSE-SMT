from flask_mail import Message

from backend.api.api import app, mail


def test_connection():
    with app.app_context():
        try:
            msg = Message(
                subject="🚀 EduPulse System Check",
                recipients=["your-personal-email@gmail.com"],  # Send to yourself
                body="If you see this, the Gmail App Password is working perfectly!",
            )
            mail.send(msg)
            print("✅ Success! Email sent.")
        except Exception as e:
            print(f"❌ Failed: {e}")


if __name__ == "__main__":
    test_connection()

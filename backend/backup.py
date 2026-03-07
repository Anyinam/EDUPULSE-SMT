import os
import subprocess
from datetime import datetime

from api.api import app, mail
from flask_mail import Message


def backup_database():
    with app.app_context():
        filename = f"backup_{datetime.now().strftime('%Y%m%d')}.sql"
        # Command to dump PostgreSQL from inside Docker
        dump_cmd = f"pg_dump -U postgres edupulse_db > {filename}"

        try:
            subprocess.run(dump_cmd, shell=True, check=True)

            # Email the backup to yourself
            msg = Message(
                subject=f"📦 EduPulse Weekly Backup: {datetime.now().date()}",
                recipients=["your-email@gmail.com"],
                body="Find attached the full SQL dump for all schools.",
            )
            with app.open_resource(filename) as fp:
                msg.attach(filename, "application/sql", fp.read())

            mail.send(msg)
            os.remove(filename)  # Clean up local file
            print("✅ Weekly backup sent successfully!")
        except Exception as e:
            print(f"❌ Backup failed: {e}")


if __name__ == "__main__":
    backup_database()

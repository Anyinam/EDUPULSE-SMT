import os
import subprocess
from datetime import datetime

from api.api import app, mail
from flask_mail import Message


def backup_database():
    with app.app_context():
        filename = f"backup_{datetime.now().strftime('%Y%m%d')}.sql"
        dump_cmd = ["pg_dump", "-U", "postgres", "edupulse_db"]

        try:
            with open(filename, "wb") as dump_file:
                subprocess.run(dump_cmd, stdout=dump_file, check=True)

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
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"❌ Backup failed: {e}")


if __name__ == "__main__":
    backup_database()

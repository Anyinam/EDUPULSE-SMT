from werkzeug.security import generate_password_hash

from backend import School, SchoolSettings, User, db
from backend.api import create_app

app = create_app()


def onboard_new_school(id, name, logo_url, color, admin_user, admin_pass):
    with app.app_context():
        # 1. Create the Business Entity (Tenant)
        new_school = School(id=id, name=name, logo_url=logo_url, primary_color=color)

        # 2. Initialize Business Rules (Custom Settings)
        # As per notes: To define their own business rules & workflow
        settings = SchoolSettings(school_id=id, sack_risk_threshold=3)

        # 3. Create Business Credentials (Admin User)
        # As per notes: Use business credentials rather than account set up by provider
        admin = User(username=admin_user, role="proprietor", school_id=id)
        admin.password_hash = generate_password_hash(admin_pass)

        db.session.add(new_school)
        db.session.add(settings)
        db.session.add(admin)
        db.session.commit()

        print(f"✅ Successfully onboarded {name} ({id})")


if __name__ == "__main__":
    # Example: Onboarding CCA Ofankor
    onboard_new_school(
        id="CCA-OFK",
        name="Christian Centre Academy",
        logo_url="https://example.com/cca_logo.png",
        color="#1e3a8a",
        admin_user="proprietor_cca",
        admin_pass="cca2026",
    )

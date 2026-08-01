import os

from werkzeug.security import generate_password_hash

from backend.api.api import app
from backend.api.models import School, SchoolSettings, Student, User, db


DEMO_SCHOOL_ID = "CCA-OFK"
DEMO_USERNAME = "proprietor_cca"
DEMO_PASSWORD = "cca2026"

DEMO_STUDENTS = [
    {
        "first_name": "Ama",
        "surname": "Mensah",
        "name": "Ama Mensah",
        "gender": "Female",
        "student_code": "CCA-NUR-001",
        "current_class": "Nursery",
        "guardian_name": "Rose Mensah",
        "parent_name": "Rose Mensah",
        "parent_phone": "0240001001",
        "parent_email": "rose.mensah@example.com",
        "total_tuition_owed": 450.0,
    },
    {
        "first_name": "Kojo",
        "surname": "Asare",
        "name": "Kojo Asare",
        "gender": "Male",
        "student_code": "CCA-PRI-001",
        "current_class": "Primary 3",
        "guardian_name": "Daniel Asare",
        "parent_name": "Daniel Asare",
        "parent_phone": "0240001002",
        "parent_email": "daniel.asare@example.com",
        "total_tuition_owed": 0.0,
    },
    {
        "first_name": "Efua",
        "surname": "Owusu",
        "name": "Efua Owusu",
        "gender": "Female",
        "student_code": "CCA-JHS-001",
        "current_class": "JHS 1",
        "guardian_name": "Michael Owusu",
        "parent_name": "Michael Owusu",
        "parent_phone": "0240001003",
        "parent_email": "michael.owusu@example.com",
        "total_tuition_owed": 300.0,
    },
]


def _ensure_demo_students() -> None:
    existing_count = Student.query.filter_by(school_id=DEMO_SCHOOL_ID).count()
    if existing_count > 0:
        return

    for payload in DEMO_STUDENTS:
        db.session.add(Student(school_id=DEMO_SCHOOL_ID, **payload))


def _ensure_demo_school() -> School | None:
    school = db.session.get(School, DEMO_SCHOOL_ID)
    if school:
        return school

    if School.query.count() > 0:
        print("⏭️  Demo bootstrap skipped: non-demo schools already exist")
        return None

    school = School(
        id=DEMO_SCHOOL_ID,
        name="Christian Centre Academy - Ofankor",
        primary_color="#1e3a8a",
        school_email="info@cca-ofankor.edu.gh",
        school_phone="0302123456",
        school_address="Plot 45, Ofankor Estates, Accra",
        school_website="www.cca-ofankor.edu.gh",
        is_active=True,
    )
    db.session.add(school)
    return school


def _ensure_demo_settings() -> None:
    settings = SchoolSettings.query.filter_by(school_id=DEMO_SCHOOL_ID).first()
    if settings:
        return

    db.session.add(
        SchoolSettings(
            school_id=DEMO_SCHOOL_ID,
            tuition_fee=1000.0,
            feeding_fee=200.0,
            uniform_fee=150.0,
            transport_fee=100.0,
            terminal_report_fee=50.0,
            currency="GH₵",
        )
    )


def _ensure_demo_proprietor() -> None:
    proprietor = User.query.filter_by(username=DEMO_USERNAME).first()
    if proprietor:
        return

    proprietor_email = os.getenv("SEED_PROPRIETOR_EMAIL") or os.getenv("MAIL_USERNAME") or None
    db.session.add(
        User(
            username=DEMO_USERNAME,
            password_hash=generate_password_hash(DEMO_PASSWORD),
            role="proprietor",
            school_id=DEMO_SCHOOL_ID,
            email=proprietor_email,
            is_temp_password=False,
        )
    )


def bootstrap_demo_if_empty() -> None:
    with app.app_context():
        school = _ensure_demo_school()
        if school is None:
            return

        print("🌱 Ensuring local demo tenant data...")
        _ensure_demo_settings()
        _ensure_demo_proprietor()
        _ensure_demo_students()

        db.session.commit()
        print(f"✅ Demo tenant ready: {DEMO_SCHOOL_ID} / {DEMO_USERNAME}")


if __name__ == "__main__":
    bootstrap_demo_if_empty()
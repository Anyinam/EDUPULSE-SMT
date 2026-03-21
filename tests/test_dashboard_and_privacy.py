import json
from datetime import datetime, timedelta, timezone

from flask_jwt_extended import create_access_token

from backend.api.models import School, Student, User, db
from backend.api.models import ReportCard


def _proprietor_headers(app, school_id, proprietor_id):
    with app.app_context():
        token = create_access_token(identity=str(proprietor_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def test_live_feed_includes_students_overdue_more_than_30_days(client, app, test_school, test_proprietor):
    overdue_student = Student(
        school_id=test_school.id,
        first_name="Kwame",
        surname="Mensah",
        name="Kwame Mensah",
        student_code="S900",
        current_class="JHS 2",
        total_tuition_owed=450.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=31),
        parent_name="Ama Mensah",
        parent_phone="+233501111111",
        parent_email="ama@example.com",
        is_present=False,
        feeding_paid=True,
    )
    db.session.add(overdue_student)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/proprietor/live-feed", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    critical_names = [item["name"] for item in payload["critical_list"]]
    assert "Kwame Mensah" in critical_names

    student_payload = next(item for item in payload["critical_list"] if item["name"] == "Kwame Mensah")
    assert student_payload["parent_name"] == "Ama Mensah"
    assert student_payload["parent_phone"] == "+233501111111"
    assert student_payload["parent_email"] == "ama@example.com"
    assert student_payload["total_tuition_owed"] == 450.0



def test_subscription_returns_pending_plan_for_scheduled_downgrade(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Premium"
    test_school.pending_plan = "Free Tier"
    test_school.next_billing_date = datetime.now(timezone.utc) + timedelta(days=10)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/school/subscription", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["subscription_plan"] == "Premium"
    assert payload["pending_plan"] == "Free Tier"



def test_bank_details_are_masked_and_password_reveal_returns_full_values(client, app, test_school, test_proprietor):
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    test_school.bank_branch = "Kumasi Main"
    db.session.commit()

    branding_response = client.get("/api/school/branding", headers={"X-School-ID": test_school.id})
    assert branding_response.status_code == 200
    branding_payload = branding_response.get_json()
    assert branding_payload["bank_account"].endswith("7890")
    assert branding_payload["bank_account"].startswith("****")
    assert "EduPulse School Account" != branding_payload["bank_account_name"]

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    bad_response = client.post(
        "/api/school/branding/bank/view",
        headers=headers,
        data=json.dumps({"password": "WrongPass123"}),
    )
    assert bad_response.status_code == 401

    good_response = client.post(
        "/api/school/branding/bank/view",
        headers=headers,
        data=json.dumps({"password": "PropPass123"}),
    )
    assert good_response.status_code == 200
    revealed = good_response.get_json()
    assert revealed["bank_name"] == "Fidelity Bank Ghana"
    assert revealed["bank_account"] == "1234567890"
    assert revealed["bank_account_name"] == "EduPulse School Account"
    assert revealed["bank_branch"] == "Kumasi Main"


def test_class_performance_returns_cohort_migration_comparison(client, app, test_school, test_proprietor):
    student = Student(
        school_id=test_school.id,
        first_name="Yaw",
        surname="Boateng",
        name="Yaw Boateng",
        student_code="S901",
        current_class="JHS 2",
    )
    db.session.add(student)
    db.session.flush()

    previous_report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 1",
        academic_year="2024/2025",
        class_name="JHS 1",
        term_average=68.0,
        subject_grades=[],
        status="Approved",
    )
    current_report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 1",
        academic_year="2025/2026",
        class_name="JHS 2",
        term_average=74.0,
        subject_grades=[{"subject": "Mathematics", "total": 74}],
        status="Approved",
    )
    db.session.add(previous_report)
    db.session.add(current_report)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(
        "/api/analytics/class-performance?academic_term=Term 1&academic_year=2025/2026",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    cohorts = payload.get("cohort_migration_comparisons", [])
    assert any(item["from_class"] == "JHS 1" and item["to_class"] == "JHS 2" for item in cohorts)

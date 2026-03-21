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
        subject_grades=[{"subject": "Mathematics", "total": 68}, {"subject": "Science", "total": 70}],
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
    historical_report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 1",
        academic_year="2023/2024",
        class_name="JHS 1",
        term_average=63.0,
        subject_grades=[{"subject": "Mathematics", "total": 63}],
        status="Approved",
    )
    db.session.add(previous_report)
    db.session.add(current_report)
    db.session.add(historical_report)
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
    assert "2023/2024" in payload.get("available_academic_years", [])
    assert "2024/2025" in payload.get("available_academic_years", [])
    assert any(item["class_name"] == "JHS 2" for item in payload.get("multi_year_trends", []))
    subject_trends = payload.get("subject_multi_year_trends", [])
    math_trend = next(item for item in subject_trends if item["subject"] == "Mathematics")
    assert [point["academic_year"] for point in math_trend["points"]] == ["2023/2024", "2024/2025", "2025/2026"]
    assert math_trend["delta"] == 11.0


def test_analytics_presets_can_be_saved_defaulted_and_deleted(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    save_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        data=json.dumps(
            {
                "name": "Board View",
                "filters": {
                    "academicTerm": "Term 2",
                    "academicYear": "2025/2026",
                    "cohortFromClass": "JHS 1",
                    "cohortToClass": "JHS 2",
                    "analysisMode": "multi-year",
                    "activeView": "visualization",
                },
                "is_default": True,
            }
        ),
    )

    assert save_response.status_code == 200
    save_payload = save_response.get_json()
    assert save_payload["default_preset_name"] == "Board View"
    assert save_payload["preset"]["filters"]["analysisMode"] == "multi-year"

    list_response = client.get("/api/analytics/presets", headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload["default_preset_name"] == "Board View"
    assert any(item["name"] == "Board View" for item in list_payload["presets"])

    second_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        data=json.dumps(
            {
                "name": "Overview Quick Check",
                "filters": {
                    "academicTerm": "Term 1",
                    "academicYear": "2025/2026",
                    "analysisMode": "single-year",
                    "activeView": "overview",
                },
            }
        ),
    )
    assert second_response.status_code == 200

    default_response = client.put(
        "/api/analytics/presets/Overview Quick Check/default",
        headers=headers,
    )
    assert default_response.status_code == 200
    assert default_response.get_json()["default_preset_name"] == "Overview Quick Check"

    delete_response = client.delete(
        "/api/analytics/presets/Overview Quick Check",
        headers=headers,
    )
    assert delete_response.status_code == 200
    delete_payload = delete_response.get_json()
    assert delete_payload["default_preset_name"] == "Board View"
    assert all(item["name"] != "Overview Quick Check" for item in delete_payload["presets"])


def test_analytics_presets_treat_duplicate_names_case_insensitively(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    first_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        data=json.dumps(
            {
                "name": "Board View",
                "filters": {
                    "academicTerm": "Term 1",
                    "academicYear": "2025/2026",
                    "analysisMode": "single-year",
                    "activeView": "overview",
                },
            }
        ),
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        data=json.dumps(
            {
                "name": "board view",
                "filters": {
                    "academicTerm": "Term 2",
                    "academicYear": "2026/2027",
                    "analysisMode": "multi-year",
                    "activeView": "visualization",
                },
                "is_default": True,
            }
        ),
    )
    assert second_response.status_code == 200
    payload = second_response.get_json()
    assert len(payload["presets"]) == 1
    assert payload["presets"][0]["name"] == "board view"
    assert payload["presets"][0]["filters"]["analysisMode"] == "multi-year"
    assert payload["default_preset_name"] == "board view"

    default_response = client.put(
        "/api/analytics/presets/BOARD%20VIEW/default",
        headers=headers,
    )
    assert default_response.status_code == 200
    assert default_response.get_json()["default_preset_name"] == "board view"

    delete_response = client.delete(
        "/api/analytics/presets/Board%20View",
        headers=headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.get_json()["presets"] == []

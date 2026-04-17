import json
from datetime import datetime, timedelta, timezone

from flask_jwt_extended import create_access_token

from backend.api.models import AcademicTerm, Payment, School, SchoolSettings, Student, User, db
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
        is_present=True,
        feeding_paid=False,
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
    assert any(reason["code"] == "overdue_tuition" for reason in student_payload["intervention_reasons"])
    tuition_reason = next(reason for reason in student_payload["intervention_reasons"] if reason["code"] == "overdue_tuition")
    assert "31 day" in tuition_reason["detail"]
    assert student_payload["risk_level"] in ["High", "Critical"]
    assert student_payload["risk_score"] >= 45
    assert student_payload["recommended_actions"]
    assert payload["student_rescue_agent"]["summary"]["total_flagged_students"] >= 1


def test_student_rescue_agent_does_not_flag_tuition_just_after_reopening_without_other_behaviour_signals(client, app, test_school, test_proprietor):
    active_term = AcademicTerm(
        school_id=test_school.id,
        name="Term 2",
        academic_year="2025/2026",
        start_date=datetime.now(timezone.utc).date() - timedelta(days=3),
        end_date=datetime.now(timezone.utc).date() + timedelta(days=80),
        is_active=True,
    )
    db.session.add(active_term)
    db.session.flush()

    calm_student = Student(
        school_id=test_school.id,
        first_name="Nii",
        surname="Laryea",
        name="Nii Laryea",
        student_code="S908",
        current_class="JHS 1",
        total_tuition_owed=600.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=35),
        parent_name="Abena Laryea",
        parent_phone="+233505555555",
        parent_email="abena@example.com",
        is_present=False,
        feeding_paid=True,
    )
    db.session.add(calm_student)
    db.session.flush()

    stable_report = ReportCard(
        school_id=test_school.id,
        student_id=calm_student.id,
        academic_term="Term 1",
        academic_year="2025/2026",
        class_name="JHS 1",
        term_average=82.0,
        attendance_percentage=96.0,
        overall_position="3rd",
        out_of_students=25,
        subject_grades=[{"subject": "Mathematics", "total": 84}],
        status="Approved",
    )
    recent_payment = Payment(
        student_id=calm_student.id,
        school_id=test_school.id,
        amount=150.0,
        payment_type="Tuition",
        method="Cash",
        reference_id="RECENT-TUITION-1",
        status="Confirmed",
        date_paid=datetime.now(timezone.utc) - timedelta(days=5),
    )
    db.session.add_all([stable_report, recent_payment])
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/proprietor/student-rescue-agent", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    flagged_names = [item["name"] for item in payload["students"]]
    assert "Nii Laryea" not in flagged_names


def test_student_rescue_agent_returns_prioritized_actions(client, app, test_school, test_proprietor):
    rescue_student = Student(
        school_id=test_school.id,
        first_name="Efua",
        surname="Owusu",
        name="Efua Owusu",
        student_code="S902",
        current_class="JHS 1",
        total_tuition_owed=650.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=40),
        parent_name="Kojo Owusu",
        parent_phone="+233502222222",
        parent_email="kojo@example.com",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(rescue_student)
    db.session.flush()

    current_report = ReportCard(
        school_id=test_school.id,
        student_id=rescue_student.id,
        academic_term="Term 2",
        academic_year="2025/2026",
        class_name="JHS 1",
        term_average=48.0,
        attendance_percentage=66.0,
        overall_position="18th",
        out_of_students=25,
        subject_grades=[{"subject": "Mathematics", "total": 44}],
        status="Approved",
    )
    previous_report = ReportCard(
        school_id=test_school.id,
        student_id=rescue_student.id,
        academic_term="Term 1",
        academic_year="2025/2026",
        class_name="JHS 1",
        term_average=61.0,
        attendance_percentage=74.0,
        overall_position="12th",
        out_of_students=25,
        subject_grades=[{"subject": "Mathematics", "total": 60}],
        status="Approved",
    )
    db.session.add_all([current_report, previous_report])
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/proprietor/student-rescue-agent", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["agent_name"] == "Student Rescue Agent"
    assert payload["summary"]["total_flagged_students"] >= 1

    student_payload = next(item for item in payload["students"] if item["name"] == "Efua Owusu")
    assert student_payload["priority_rank"] >= 1
    assert student_payload["risk_level"] == "Critical"
    assert student_payload["risk_score"] >= 70
    assert any(reason["code"] == "overdue_tuition" for reason in student_payload["intervention_reasons"])
    assert any(reason["code"] == "unpaid_feeding" for reason in student_payload["intervention_reasons"])
    assert any(reason["code"] == "low_academic_average" for reason in student_payload["intervention_reasons"])
    assert any(action["code"] == "call_guardian" for action in student_payload["recommended_actions"])
    assert student_payload["latest_report"]["trend_direction"] == "declining"
    assert "Efua Owusu" in student_payload["contact_templates"]["email_subject"]
    assert "Kojo Owusu" in student_payload["contact_templates"]["email_body"]
    assert "contact the school today" in student_payload["contact_templates"]["sms_body"].lower()


def test_student_rescue_outcome_logging_returns_recent_history(client, app, test_school, test_proprietor):
    rescue_student = Student(
        school_id=test_school.id,
        first_name="Abena",
        surname="Asare",
        name="Abena Asare",
        student_code="S903",
        current_class="Class 6",
        total_tuition_owed=520.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=34),
        parent_name="Yaw Asare",
        parent_phone="+233503333333",
        parent_email="yaw@example.com",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(rescue_student)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    log_response = client.post(
        "/api/proprietor/student-rescue-agent/outcome",
        headers=headers,
        data=json.dumps(
            {
                "student_id": rescue_student.id,
                "action_code": "guardian_called",
                "notes": "Guardian promised to visit the school tomorrow.",
            }
        ),
    )

    assert log_response.status_code == 200
    log_payload = log_response.get_json()
    assert log_payload["message"] == "Rescue outcome logged."
    assert log_payload["recent_outcomes"][0]["action_code"] == "guardian_called"
    assert "promised to visit" in log_payload["recent_outcomes"][0]["notes"]

    rescue_response = client.get("/api/proprietor/student-rescue-agent", headers=headers)
    assert rescue_response.status_code == 200
    rescue_payload = rescue_response.get_json()
    student_payload = next(item for item in rescue_payload["students"] if item["name"] == "Abena Asare")
    assert student_payload["last_outcome"]["action_code"] == "guardian_called"
    assert student_payload["recent_outcomes"][0]["actor_name"] == test_proprietor.username


def test_student_rescue_email_send_logs_outcome(client, app, test_school, test_proprietor, monkeypatch):
    sent_messages = []

    def fake_email(to_email, subject, body, attachments=None):
        sent_messages.append({"to": to_email, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("backend.routes.send_email_notification", fake_email)

    rescue_student = Student(
        school_id=test_school.id,
        first_name="Mansa",
        surname="Aidoo",
        name="Mansa Aidoo",
        student_code="S904",
        current_class="Class 5",
        total_tuition_owed=540.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=36),
        parent_name="Esi Aidoo",
        parent_phone="+233504444444",
        parent_email="esi@example.com",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(rescue_student)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/proprietor/student-rescue-agent/send-email",
        headers=headers,
        data=json.dumps({"student_id": rescue_student.id}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Rescue email sent to esi@example.com"
    assert sent_messages[0]["to"] == "esi@example.com"
    assert "Mansa Aidoo" in sent_messages[0]["subject"]
    assert payload["recent_outcomes"][0]["action_code"] == "email_sent"


def test_student_rescue_report_groups_open_in_progress_and_resolved_cases(client, app, test_school, test_proprietor):
    open_case = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Poku",
        name="Kojo Poku",
        student_code="S905",
        current_class="JHS 1",
        total_tuition_owed=400.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=31),
        parent_email="kojo.parent@example.com",
        is_present=True,
        feeding_paid=False,
    )
    in_progress_case = Student(
        school_id=test_school.id,
        first_name="Akosua",
        surname="Badu",
        name="Akosua Badu",
        student_code="S906",
        current_class="JHS 2",
        total_tuition_owed=620.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=39),
        parent_email="akosua.parent@example.com",
        is_present=True,
        feeding_paid=False,
    )
    resolved_case = Student(
        school_id=test_school.id,
        first_name="Yaw",
        surname="Kusi",
        name="Yaw Kusi",
        student_code="S907",
        current_class="JHS 3",
        total_tuition_owed=580.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=42),
        parent_email="yaw.parent@example.com",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add_all([open_case, in_progress_case, resolved_case])
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    client.post(
        "/api/proprietor/student-rescue-agent/outcome",
        headers=headers,
        data=json.dumps({"student_id": in_progress_case.id, "action_code": "guardian_called", "notes": "Guardian reached."}),
    )
    client.post(
        "/api/proprietor/student-rescue-agent/outcome",
        headers=headers,
        data=json.dumps({"student_id": resolved_case.id, "action_code": "resolved", "notes": "Fees settled."}),
    )

    report_response = client.get("/api/proprietor/student-rescue-agent/report", headers=headers)
    assert report_response.status_code == 200
    report_payload = report_response.get_json()
    assert report_payload["report"]["open_cases"] >= 1
    assert report_payload["report"]["in_progress_cases"] >= 1
    assert report_payload["report"]["resolved_cases"] >= 1

    open_only_response = client.get("/api/proprietor/student-rescue-agent/report?status=Open", headers=headers)
    assert open_only_response.status_code == 200
    open_students = open_only_response.get_json()["students"]
    assert any(student["name"] == "Kojo Poku" for student in open_students)
    assert all(student["case_status"] == "Open" for student in open_students)



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
    assert payload["next_billing_date"] == test_school.next_billing_date.strftime("%Y-%m-%d")


def test_subscription_handles_naive_trial_date_and_returns_alias(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Premium"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.utcnow() + timedelta(days=5)
    test_school.next_billing_date = datetime.now(timezone.utc) + timedelta(days=7)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/school/subscription", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["next_billing_date"] == test_school.next_billing_date.strftime("%Y-%m-%d")
    assert payload["trial"]["active"] is True



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
    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.get_json()
    assert settings_payload["bank_details_masked"] is True
    assert settings_payload["bank_account"].startswith("****")
    assert settings_payload["bank_name"] != "Fidelity Bank Ghana"

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


def test_payment_codes_include_convenience_fee_breakdown_and_cash_alternative(client, app, test_school, test_proprietor, test_students):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if not settings:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)

    settings.tuition_fee = 100.0
    settings.terminal_report_fee = 0.0
    settings.feeding_fee = 0.0
    settings.transport_fee = 0.0
    settings.other_fees = {}
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(f"/api/students/{test_students[0].id}/payment-codes", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    tuition_code = next(item for item in payload["payment_codes"] if item["fee_type"] == "Tuition + Terminal Report")
    assert tuition_code["base_amount"] == 100.0
    assert tuition_code["cash_amount"] == 100.0
    assert tuition_code["convenience_fee_percent"] == 2.0
    assert tuition_code["convenience_fee_amount"] == 2.0
    assert tuition_code["total_amount"] == 102.0
    assert "cash at the school office" in tuition_code["instructions"].lower()
    assert "convenience fee" in payload["note"].lower()


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

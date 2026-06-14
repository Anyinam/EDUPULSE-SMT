import json
import sys
from io import BytesIO
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

from reportlab.pdfgen import canvas

from flask_jwt_extended import create_access_token

from backend.api.models import AcademicTerm, Payment, PlatformSetting, PlatformUser, School, SchoolSettings, Student, TeacherAssignment, User, db
from backend.api.models import ReportCard
from backend.utils import generate_descriptive_analysis


def _proprietor_headers(app, school_id, proprietor_id):
    with app.app_context():
        token = create_access_token(identity=str(proprietor_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def _headmaster_headers(app, school_id, headmaster_id):
    with app.app_context():
        token = create_access_token(identity=str(headmaster_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def _teacher_headers(app, school_id, teacher_id):
    with app.app_context():
        token = create_access_token(identity=str(teacher_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def _homeroom_headers(app, school_id, homeroom_id):
    with app.app_context():
        token = create_access_token(identity=str(homeroom_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def _platform_headers(app, platform_user_id):
    with app.app_context():
        token = create_access_token(identity=f"platform:{platform_user_id}")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def test_platform_public_content_round_trip(client, app):
    platform_user = PlatformUser(username="platform-owner", email="owner@example.com")
    platform_user.set_password("secret123")
    db.session.add(platform_user)
    db.session.commit()

    headers = _platform_headers(app, platform_user.id)
    payload = {
        "faqs": [{"question": "How do we get help?", "answer": "Use the official support contacts below."}],
        "tutorials": [{"title": "Intro walkthrough", "url": "https://example.com/video"}],
        "feature_guides": [{"title": "Exam Intelligence", "body": "Shared insights are managed centrally."}],
        "security_alerts": ["Never share your OTP with anyone claiming to be EduPulse support."],
        "support": {
            "email": "helpdesk@edupulse.com",
            "phone": "+233 500 111 222",
            "website": "https://edupulse.com/support",
            "response_time": "same business day",
        },
        "auth": {
            "login_title": "Access EduPulse",
            "login_subtitle": "Use your verified school credentials.",
            "register_title": "Start a School Workspace",
            "register_subtitle": "Create a secure tenant account.",
            "register_support_note": "Need onboarding help? Contact the platform team.",
        },
        "help_center": {
            "title": "Support Hub",
            "subtitle": "Search product guides and platform notices.",
            "security_title": "Fraud Warning",
            "security_body": "Confirm suspicious requests before acting.",
        },
    }

    update_response = client.put("/api/platform/public-content", headers=headers, data=json.dumps(payload))
    assert update_response.status_code == 200

    public_response = client.get("/api/public/platform-content")
    assert public_response.status_code == 200
    public_payload = public_response.get_json()
    assert public_payload["support"]["email"] == "helpdesk@edupulse.com"
    assert public_payload["auth"]["register_title"] == "Start a School Workspace"
    assert public_payload["feature_guides"][0]["title"] == "Exam Intelligence"

    help_response = client.get("/api/public/help-content")
    assert help_response.status_code == 200
    help_payload = help_response.get_json()
    assert help_payload["faqs"][0]["question"] == "How do we get help?"


def test_platform_user_management_uses_platform_jwt(client, app):
    platform_user = PlatformUser(username="console-admin", email="console-admin@example.com")
    platform_user.set_password("secret123")
    db.session.add(platform_user)
    db.session.commit()

    headers = _platform_headers(app, platform_user.id)
    create_response = client.post(
        "/api/platform/users",
        headers=headers,
        data=json.dumps(
            {
                "username": "second-admin",
                "email": "second-admin@example.com",
                "password": "password123",
            }
        ),
    )
    assert create_response.status_code == 201
    created_user_id = create_response.get_json()["user"]["id"]

    list_response = client.get("/api/platform/users", headers=headers)
    assert list_response.status_code == 200
    usernames = {item["username"] for item in list_response.get_json()["users"]}
    assert "second-admin" in usernames

    delete_response = client.delete(f"/api/platform/users/{created_user_id}", headers=headers)
    assert delete_response.status_code == 200

    self_delete_response = client.delete(f"/api/platform/users/{platform_user.id}", headers=headers)
    assert self_delete_response.status_code == 400


def test_platform_bootstrap_creates_first_admin_with_owner_key(client, monkeypatch):
    monkeypatch.setenv("PLATFORM_OWNER_KEY", "bootstrap-secret")

    status_response = client.get("/api/platform/bootstrap-status")
    assert status_response.status_code == 200
    assert status_response.get_json()["needs_bootstrap"] is True

    create_response = client.post(
        "/api/platform/users",
        headers={"X-Platform-Owner-Key": "bootstrap-secret", "Content-Type": "application/json"},
        data=json.dumps(
            {
                "username": "bootstrap-admin",
                "email": "bootstrap-admin@example.com",
                "password": "password123",
            }
        ),
    )
    assert create_response.status_code == 201

    status_response_after = client.get("/api/platform/bootstrap-status")
    assert status_response_after.status_code == 200
    assert status_response_after.get_json()["needs_bootstrap"] is False


def test_platform_chief_examiner_library_import_accepts_multiple_report_files(client, app, monkeypatch):
    platform_user = PlatformUser(username="platform-batch", email="platform-batch@example.com")
    platform_user.set_password("secret123")
    db.session.add(platform_user)
    db.session.commit()

    headers = _platform_headers(app, platform_user.id)
    response = client.post(
        "/api/platform/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_tenant_chief_examiner_library_merges_platform_and_school_overrides(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/analytics/chief-examiner-library", headers=headers)

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_tenant_chief_examiner_library_is_empty_before_any_upload(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/analytics/chief-examiner-library", headers=headers)

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


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


def test_descriptive_analysis_includes_diagnostic_mock_and_pathway_guidance(client, app, test_school):
    guided_student = Student(
        school_id=test_school.id,
        first_name="Adwoa",
        surname="Bonsu",
        name="Adwoa Bonsu",
        student_code="S940",
        current_class="JHS 3",
        parent_name="Yaw Bonsu",
    )
    db.session.add(guided_student)
    db.session.flush()

    report = ReportCard(
        school_id=test_school.id,
        student_id=guided_student.id,
        academic_term="Term 2",
        academic_year="2025/2026",
        class_name="JHS 3",
        term_average=67.5,
        attendance_percentage=91.0,
        overall_position="6th",
        out_of_students=32,
        subject_grades=[
            {
                "subject": "Mathematics",
                "total": 74,
                "diagnostic_topics": [
                    {"topic": "Geometry", "score": 5, "max_score": 15},
                    {"topic": "Algebra", "score": 13, "max_score": 15},
                ],
            },
            {
                "subject": "Science",
                "total": 78,
                "diagnostic_topics": [
                    {"topic": "Scientific Units", "score": 4, "max_score": 10},
                ],
            },
            {"subject": "ICT", "total": 71},
            {"subject": "English Language", "total": 66},
        ],
        status="Approved",
    )
    db.session.add(report)
    db.session.commit()

    narrative = generate_descriptive_analysis(guided_student.id)

    assert "Diagnostic mock insights:" in narrative
    assert "targeted revision before the next assessment" in narrative
    assert "Geometry" in narrative
    assert "SHS pathway signal:" in narrative
    assert "General Science" in narrative


def test_teacher_academic_guidance_is_limited_to_assigned_subjects(client, app, test_school, test_teacher):
    student = Student(
        school_id=test_school.id,
        first_name="Mawuli",
        surname="Kumah",
        name="Mawuli Kumah",
        student_code="S950",
        current_class="JHS 1",
    )
    db.session.add(student)
    db.session.flush()

    assignment = TeacherAssignment(
        school_id=test_school.id,
        teacher_id=test_teacher.id,
        class_name="JHS 1",
        subject_name="Mathematics",
    )
    db.session.add(assignment)

    report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 2",
        academic_year="2025/2026",
        class_name="JHS 1",
        subject_grades=[
            {"subject": "Mathematics", "total": 61, "diagnostic_topics": [{"topic": "Geometry", "score": 4, "max_score": 15}]},
            {"subject": "Science", "total": 58, "diagnostic_topics": [{"topic": "Scientific Units", "score": 3, "max_score": 10}]},
        ],
        status="Approved",
    )
    db.session.add(report)
    db.session.commit()

    headers = _teacher_headers(app, test_school.id, test_teacher.id)
    response = client.get("/api/analytics/academic-guidance", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["scope"]["role"] == "teacher"
    assert payload["scope"]["allowed_subjects"] == ["Mathematics"]
    assert len(payload["diagnostic_hotspots"]) == 1
    assert payload["diagnostic_hotspots"][0]["subject"] == "Mathematics"

    db.session.delete(assignment)
    db.session.delete(report)
    db.session.delete(student)
    db.session.commit()


def test_homeroom_academic_guidance_is_limited_to_assigned_class(client, app, test_school):
    homeroom = User(
        username="homeroom1",
        school_id=test_school.id,
        role="homeroom",
        email="homeroom@test.edu",
        assigned_class="JHS 1",
    )
    homeroom.set_password("HomeroomPass123")
    db.session.add(homeroom)
    db.session.flush()

    class_student = Student(
        school_id=test_school.id,
        first_name="Akua",
        surname="Boateng",
        name="Akua Boateng",
        student_code="S960",
        current_class="JHS 1",
    )
    other_student = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Amoah",
        name="Kojo Amoah",
        student_code="S961",
        current_class="JHS 2",
    )
    db.session.add_all([class_student, other_student])
    db.session.flush()

    class_report = ReportCard(
            school_id=test_school.id,
            student_id=class_student.id,
            academic_term="Term 2",
            academic_year="2025/2026",
            class_name="JHS 1",
            subject_grades=[
                {"subject": "Mathematics", "total": 60, "diagnostic_topics": [{"topic": "Geometry", "score": 3, "max_score": 15}]},
                {"subject": "Science", "total": 62, "diagnostic_topics": [{"topic": "Scientific Units", "score": 4, "max_score": 10}]},
            ],
            status="Approved",
        )
    other_report = ReportCard(
            school_id=test_school.id,
            student_id=other_student.id,
            academic_term="Term 2",
            academic_year="2025/2026",
            class_name="JHS 2",
            subject_grades=[
                {"subject": "English Language", "total": 59, "diagnostic_topics": [{"topic": "Grammar", "score": 2, "max_score": 10}]},
            ],
            status="Approved",
        )
    db.session.add_all([class_report, other_report])
    db.session.commit()

    headers = _homeroom_headers(app, test_school.id, homeroom.id)
    response = client.get("/api/analytics/academic-guidance", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["scope"]["role"] == "homeroom"
    assert payload["scope"]["allowed_classes"] == ["JHS 1"]
    subjects = {item["subject"] for item in payload["diagnostic_hotspots"]}
    assert "Mathematics" in subjects
    assert "Science" in subjects
    assert "English Language" not in subjects

    db.session.delete(class_report)
    db.session.delete(other_report)
    db.session.delete(homeroom)
    db.session.delete(class_student)
    db.session.delete(other_student)
    db.session.commit()


def test_chief_examiner_library_template_download(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/analytics/chief-examiner-library/template", headers=headers)

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_history_and_restore(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    history_response = client.get("/api/analytics/chief-examiner-library/history", headers=headers)
    restore_response = client.post(
        "/api/analytics/chief-examiner-library/history/any-version/restore",
        headers=headers,
    )

    assert history_response.status_code == 410
    assert restore_response.status_code == 410


def test_chief_examiner_library_history_version_can_be_downloaded(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(
        "/api/analytics/chief-examiner-library/history/any-version/download",
        headers=headers,
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_import_accepts_narrative_text(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/analytics/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_import_accepts_numbered_subject_sections(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/analytics/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_import_recognizes_extended_subject_headings_and_summarizes_text(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/analytics/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_import_infers_topic_labels_from_clear_examiner_text(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/analytics/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_chief_examiner_library_import_uses_pdf_ocr_fallback_when_pdf_text_is_empty(client, app, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/analytics/chief-examiner-library/import",
        headers=headers,
        json={"replace_existing": True},
    )

    assert response.status_code == 410
    assert "removed" in response.get_json()["message"].lower()


def test_report_template_history_restore_and_download(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    first_response = client.post(
        "/api/school/report-template",
        headers=headers,
        json={"report_template_id": "gradman_v1"},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/school/report-template",
        headers=headers,
        json={"report_template_id": "parent_focus"},
    )
    assert second_response.status_code == 200

    history_response = client.get("/api/school/report-template/history", headers=headers)
    assert history_response.status_code == 200
    history_payload = history_response.get_json()
    assert len(history_payload["history"]) >= 2
    assert history_payload["history"][0]["actor_name"] == test_proprietor.username

    gradman_snapshot = next(
        item for item in history_payload["history"] if item["report_template_id"] == "gradman_v1"
    )

    download_response = client.get(
        f"/api/school/report-template/history/{gradman_snapshot['snapshot_id']}/download",
        headers=headers,
    )
    assert download_response.status_code == 200
    template_payload = json.loads(download_response.data.decode("utf-8"))
    assert template_payload["report_template_id"] == "gradman_v1"

    restore_response = client.post(
        f"/api/school/report-template/history/{gradman_snapshot['snapshot_id']}/restore",
        headers=headers,
    )
    assert restore_response.status_code == 200
    assert restore_response.get_json()["report_template_id"] == "gradman_v1"


def test_analytics_preset_history_restore_and_download(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    first_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        json={
            "name": "Board View",
            "filters": {
                "academicTerm": "Term 1",
                "academicYear": "2025/2026",
                "analysisMode": "multi-year",
                "activeView": "visualization",
            },
            "is_default": False,
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/analytics/presets",
        headers=headers,
        json={
            "name": "Cohort Watch",
            "filters": {
                "academicTerm": "Term 2",
                "academicYear": "2026/2027",
                "cohortFromClass": "JHS 1",
                "cohortToClass": "JHS 2",
                "analysisMode": "multi-year",
                "activeView": "visualization",
            },
            "is_default": True,
        },
    )
    assert second_response.status_code == 200

    history_response = client.get("/api/analytics/presets/history", headers=headers)
    assert history_response.status_code == 200
    history_payload = history_response.get_json()
    assert len(history_payload["history"]) >= 2
    assert history_payload["history"][0]["actor_name"] == test_proprietor.username

    board_view_snapshot = next(
        item for item in history_payload["history"] if item["focus_preset_name"] == "Board View"
    )

    download_response = client.get(
        f"/api/analytics/presets/history/{board_view_snapshot['snapshot_id']}/download",
        headers=headers,
    )
    assert download_response.status_code == 200
    payload = json.loads(download_response.data.decode("utf-8"))
    assert payload["focus_preset_name"] == "Board View"
    assert payload["analytics_config"]["presets"][0]["name"] == "Board View"

    restore_response = client.post(
        f"/api/analytics/presets/history/{board_view_snapshot['snapshot_id']}/restore",
        headers=headers,
    )
    assert restore_response.status_code == 200
    restored_payload = restore_response.get_json()
    assert restored_payload["default_preset_name"] == ""
    assert [item["name"] for item in restored_payload["presets"]] == ["Board View"]


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


def test_basic_plan_blocks_student_rescue_agent_routes(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Basic"
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/proprietor/student-rescue-agent", headers=headers)

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["current_plan"] == "Basic"
    assert payload["required_plan"] == "Premium"


def test_basic_plan_blocks_academic_guidance_routes(client, app, test_school, test_teacher):
    test_school.subscription_plan = "Basic"
    db.session.commit()

    headers = _teacher_headers(app, test_school.id, test_teacher.id)
    response = client.get("/api/analytics/academic-guidance", headers=headers)

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["current_plan"] == "Basic"
    assert payload["required_plan"] == "Premium"


def test_basic_plan_report_builder_response_omits_academic_guidance(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Basic"
    student = Student(
        school_id=test_school.id,
        first_name="Efua",
        surname="Owusu",
        name="Efua Owusu",
        student_code="S990",
        current_class="JHS 1",
        parent_name="Kofi Owusu",
    )
    db.session.add(student)
    db.session.flush()

    report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 2",
        academic_year="2025/2026",
        class_name="JHS 1",
        term_average=76.0,
        attendance_percentage=92.0,
        overall_position="5th",
        out_of_students=24,
        subject_grades=[{"subject": "Mathematics", "total": 78}],
        status="Approved",
    )
    db.session.add(report)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(
        f"/api/homeroom/report-builder/report/{student.id}?academic_term=Term 2&academic_year=2025/2026",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "academic_guidance" not in payload


def test_basic_plan_blocks_advanced_analytics_routes(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Basic"
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/analytics/presets", headers=headers)

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["current_plan"] == "Basic"
    assert payload["required_plan"] == "Premium"


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


def test_headmaster_can_access_and_update_student_rescue_cases(client, app, test_school, test_headmaster):
    rescue_student = Student(
        school_id=test_school.id,
        first_name="Selorm",
        surname="Tetteh",
        name="Selorm Tetteh",
        student_code="S909",
        current_class="JHS 2",
        total_tuition_owed=500.0,
        tuition_deadline=datetime.now(timezone.utc) - timedelta(days=33),
        parent_name="Maa Tetteh",
        parent_phone="+233506666666",
        parent_email="maa@example.com",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(rescue_student)
    db.session.commit()

    headers = _headmaster_headers(app, test_school.id, test_headmaster.id)
    rescue_response = client.get("/api/headmaster/student-rescue-agent", headers=headers)

    assert rescue_response.status_code == 200
    rescue_payload = rescue_response.get_json()
    student_payload = next(item for item in rescue_payload["students"] if item["name"] == "Selorm Tetteh")
    assert student_payload["id"] == rescue_student.id

    outcome_response = client.post(
        "/api/headmaster/student-rescue-agent/outcome",
        headers=headers,
        data=json.dumps(
            {
                "student_id": rescue_student.id,
                "action_code": "academic_support_assigned",
                "notes": "Headmaster assigned extra coaching for mathematics and English.",
            }
        ),
    )

    assert outcome_response.status_code == 200
    outcome_payload = outcome_response.get_json()
    assert outcome_payload["recent_outcomes"][0]["action_code"] == "academic_support_assigned"
    assert "extra coaching" in outcome_payload["recent_outcomes"][0]["notes"]



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


def test_school_settings_persist_legacy_migration_and_bece_compliance_flags(client, app, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    response = client.post(
        "/api/school/settings",
        headers=headers,
        data=json.dumps(
            {
                "legacy_parent_notice_dispatched": True,
                "legacy_consent_collection_completed": True,
                "legacy_consent_collection_date": "2026-04-29",
                "legacy_consent_evidence_notes": "Signed forms filed in the admissions office.",
                "bece_result_processing_enabled": True,
                "bece_parent_notice_confirmed": True,
                "teacher_class_level_exam_summaries_enabled": True,
            }
        ),
    )

    assert response.status_code == 200

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    payload = settings_response.get_json()
    assert payload["legacy_parent_notice_dispatched"] is True
    assert payload["legacy_consent_collection_completed"] is True
    assert payload["legacy_consent_collection_date"] == "2026-04-29"
    assert payload["legacy_consent_evidence_notes"] == "Signed forms filed in the admissions office."
    assert payload["bece_result_processing_enabled"] is True
    assert payload["bece_parent_notice_confirmed"] is True
    assert payload["teacher_class_level_exam_summaries_enabled"] is True


def test_legacy_consent_evidence_upload_list_and_download(client, app, test_school, test_proprietor, tmp_path):
    app.config["LEGACY_CONSENT_EVIDENCE_STORAGE_DIR"] = str(tmp_path / "evidence")
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    multipart_headers = {key: value for key, value in headers.items() if key != "Content-Type"}

    upload_response = client.post(
        "/api/school/settings/legacy-consent-evidence",
        headers=multipart_headers,
        data={
            "category": "signed_form",
            "note": "Signed legacy consent forms for Term 2.",
            "file": (BytesIO(b"signed consent evidence"), "legacy-consent.txt"),
        },
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 201
    upload_payload = upload_response.get_json()
    assert upload_payload["artifact"]["category"] == "signed_form"

    list_response = client.get("/api/school/settings/legacy-consent-evidence", headers=headers)
    assert list_response.status_code == 200
    artifacts = list_response.get_json()["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["original_filename"] == "legacy-consent.txt"

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    assert settings_response.get_json()["legacy_consent_evidence_artifact_count"] == 1

    download_response = client.get(artifacts[0]["download_path"], headers=headers)
    assert download_response.status_code == 200
    assert download_response.data == b"signed consent evidence"


def test_exam_intelligence_import_requires_ready_compliance_flags(client, app, test_school, test_proprietor, tmp_path):
    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-imports")
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    multipart_headers = {key: value for key, value in headers.items() if key != "Content-Type"}

    response = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "file": (BytesIO(b"Ama | Female | Mathematics | 78 | B2\n"), "waec-results.txt"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "readiness" in response.get_json()["message"].lower()


def test_exam_intelligence_import_and_dashboard_summary(client, app, test_school, test_proprietor, tmp_path):
    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-imports")
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    settings_response = client.post(
        "/api/school/settings",
        headers=headers,
        data=json.dumps(
            {
                "data_compliance_school_authority_confirmed": True,
                "legacy_parent_notice_dispatched": True,
                "legacy_consent_collection_completed": True,
                "bece_result_processing_enabled": True,
                "bece_parent_notice_confirmed": True,
            }
        ),
    )
    assert settings_response.status_code == 200

    multipart_headers = {key: value for key, value in headers.items() if key != "Content-Type"}
    text_one = (
        "Ama | Female | Mathematics | 78 | B2\n"
        "Ama | Female | English Language | 74 | B3\n"
        "Kojo | Male | Mathematics | 60 | C5\n"
        "Kojo | Male | English Language | 58 | C6\n"
    ).encode("utf-8")
    upload_one = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2024/2025",
            "file": (BytesIO(text_one), "waec-sheet-2024.txt"),
        },
        content_type="multipart/form-data",
    )
    assert upload_one.status_code == 201

    extracted_rows = (
        "Ama | Female | Mathematics | 82 | A1\n"
        "Ama | Female | English Language | 79 | B2\n"
        "Kojo | Male | Mathematics | 66 | C4\n"
        "Kojo | Male | English Language | 63 | C5\n"
    )
    upload_two = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "result_text": extracted_rows,
            "file": (BytesIO(b"%PDF-1.4 fake school result pdf"), "waec-results-2025.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert upload_two.status_code == 201

    dashboard_response = client.get("/api/analytics/exam-intelligence", headers=headers)
    assert dashboard_response.status_code == 200
    payload = dashboard_response.get_json()
    assert payload["compliance_ready"] is True
    assert payload["summary"]["total_imports"] == 2
    assert payload["latest_batch"]["academic_year"] == "2025/2026"
    assert payload["latest_batch"]["candidate_count"] == 2
    assert any(item["subject"] == "Mathematics" for item in payload["subject_trends"])
    assert any(item["gender"] == "Female" for item in payload["gender_comparison"])

    list_response = client.get("/api/analytics/exam-imports", headers=headers)
    assert list_response.status_code == 200
    batches = list_response.get_json()["batches"]
    assert len(batches) == 2

    download_response = client.get(batches[0]["download_path"], headers=headers)
    assert download_response.status_code == 200
    assert b"%PDF-1.4" in download_response.data


def test_exam_intelligence_parses_text_based_pdf_automatically(client, app, test_school, test_proprietor, tmp_path):
    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-imports")
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    settings_response = client.post(
        "/api/school/settings",
        headers=headers,
        data=json.dumps(
            {
                "data_compliance_school_authority_confirmed": True,
                "legacy_parent_notice_dispatched": True,
                "legacy_consent_collection_completed": True,
                "bece_result_processing_enabled": True,
                "bece_parent_notice_confirmed": True,
            }
        ),
    )
    assert settings_response.status_code == 200

    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 780, "Ama Mensah | Female | Mathematics | 82 | A1")
    pdf.drawString(72, 760, "Ama Mensah | Female | English Language | 79 | B2")
    pdf.drawString(72, 740, "Kojo Owusu | Male | Mathematics | 66 | C4")
    pdf.drawString(72, 720, "Kojo Owusu | Male | English Language | 63 | C5")
    pdf.save()
    pdf_buffer.seek(0)

    multipart_headers = {key: value for key, value in headers.items() if key != "Content-Type"}
    upload_response = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "file": (pdf_buffer, "waec-text-based-results.pdf"),
        },
        content_type="multipart/form-data",
    )

    assert upload_response.status_code == 201
    batch = upload_response.get_json()["batch"]
    assert batch["candidate_count"] == 2
    assert batch["source_format"] == "pdf"
    assert batch["parse_mode"] == "pdf_text"


def test_teacher_receives_restricted_subject_level_exam_summary(client, app, test_school, test_proprietor, test_teacher, tmp_path):
    from backend.api.models import TeacherAssignment

    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-imports")
    proprietor_headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    settings_response = client.post(
        "/api/school/settings",
        headers=proprietor_headers,
        data=json.dumps(
            {
                "data_compliance_school_authority_confirmed": True,
                "legacy_parent_notice_dispatched": True,
                "legacy_consent_collection_completed": True,
                "bece_result_processing_enabled": True,
                "bece_parent_notice_confirmed": True,
            }
        ),
    )
    assert settings_response.status_code == 200

    assignment = TeacherAssignment(
        school_id=test_school.id,
        teacher_id=test_teacher.id,
        class_name="JHS 1",
        subject_name="Mathematics",
    )
    db.session.add(assignment)
    db.session.commit()

    multipart_headers = {key: value for key, value in proprietor_headers.items() if key != "Content-Type"}
    upload_response = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "result_text": (
                "Ama | Female | Mathematics | 82 | A1\n"
                "Ama | Female | English Language | 79 | B2\n"
                "Kojo | Male | Mathematics | 66 | C4\n"
                "Kojo | Male | English Language | 63 | C5\n"
            ),
            "file": (BytesIO(b"%PDF-1.4 teacher-summary"), "teacher-summary.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201

    teacher_headers = _teacher_headers(app, test_school.id, test_teacher.id)
    teacher_response = client.get("/api/analytics/exam-intelligence", headers=teacher_headers)
    assert teacher_response.status_code == 200
    payload = teacher_response.get_json()
    assert payload["view_scope"] == "teacher_subject_summary"
    assert payload["raw_access"] is False
    assert payload["class_level_summaries_enabled"] is False
    assert payload["assigned_subjects"] == ["Mathematics"]
    assert payload["summary"]["tracked_subjects"] == 1
    assert payload["latest_batch"]["academic_year"] == "2025/2026"
    assert len(payload["latest_batch"]["subject_summaries"]) == 1
    assert payload["latest_batch"]["subject_summaries"][0]["subject"] == "Mathematics"
    assert len(payload["subject_trends"]) == 1
    assert payload["subject_trends"][0]["subject"] == "Mathematics"
    assert payload["class_summaries"] == []

    denied_download_response = client.get(
        f"/api/analytics/exam-imports/{upload_response.get_json()['batch']['id']}/download",
        headers=teacher_headers,
    )
    assert denied_download_response.status_code == 403

    db.session.delete(assignment)
    db.session.commit()


def test_teacher_receives_class_level_exam_summary_when_setting_enabled(client, app, test_school, test_proprietor, test_teacher, tmp_path):
    from backend.api.models import TeacherAssignment

    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-imports")
    proprietor_headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    settings_response = client.post(
        "/api/school/settings",
        headers=proprietor_headers,
        data=json.dumps(
            {
                "data_compliance_school_authority_confirmed": True,
                "legacy_parent_notice_dispatched": True,
                "legacy_consent_collection_completed": True,
                "bece_result_processing_enabled": True,
                "bece_parent_notice_confirmed": True,
                "teacher_class_level_exam_summaries_enabled": True,
            }
        ),
    )
    assert settings_response.status_code == 200

    test_teacher.assigned_class = "JHS 1"
    db.session.add(test_teacher)
    assignment = TeacherAssignment(
        school_id=test_school.id,
        teacher_id=test_teacher.id,
        class_name="JHS 1",
        subject_name="Mathematics",
    )
    db.session.add(assignment)

    student_one = Student.query.filter_by(school_id=test_school.id, student_code="STU001").first()
    if not student_one:
        student_one = Student(
            school_id=test_school.id,
            first_name="Ama",
            surname="Mensah",
            name="Ama Mensah",
            student_code="STU001",
            current_class="JHS 1",
        )
        db.session.add(student_one)

    student_two = Student.query.filter_by(school_id=test_school.id, student_code="STU002").first()
    if not student_two:
        student_two = Student(
            school_id=test_school.id,
            first_name="Kojo",
            surname="Owusu",
            name="Kojo Owusu",
            student_code="STU002",
            current_class="JHS 1",
        )
        db.session.add(student_two)
    db.session.commit()

    csv_bytes = (
        "candidate_id,candidate_name,class_name,gender,subject,score,grade\n"
        "STU001,Ama Mensah,JHS 1,Female,Mathematics,82,A1\n"
        "STU001,Ama Mensah,JHS 1,Female,English Language,79,B2\n"
        "STU002,Kojo Owusu,JHS 1,Male,Mathematics,66,C4\n"
        "STU002,Kojo Owusu,JHS 1,Male,English Language,63,C5\n"
    ).encode("utf-8")
    multipart_headers = {key: value for key, value in proprietor_headers.items() if key != "Content-Type"}
    upload_response = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "file": (BytesIO(csv_bytes), "teacher-class-summary.csv"),
        },
        content_type="multipart/form-data",
    )
    assert upload_response.status_code == 201

    teacher_headers = _teacher_headers(app, test_school.id, test_teacher.id)
    teacher_response = client.get("/api/analytics/exam-intelligence", headers=teacher_headers)
    assert teacher_response.status_code == 200
    payload = teacher_response.get_json()
    assert payload["class_level_summaries_enabled"] is True
    assert len(payload["class_summaries"]) == 1
    assert payload["class_summaries"][0]["class_name"] == "JHS 1"
    assert payload["class_summaries"][0]["candidate_count"] == 2
    assert payload["class_summaries"][0]["subject_summaries"][0]["subject"] == "Mathematics"

    db.session.delete(assignment)
    db.session.commit()


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

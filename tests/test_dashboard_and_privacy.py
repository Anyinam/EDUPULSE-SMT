import json
import os
import sys
import hashlib
import hmac
from io import BytesIO
from types import SimpleNamespace
from datetime import date, datetime, timedelta, timezone

from reportlab.pdfgen import canvas

from flask_jwt_extended import create_access_token

from backend.api.models import AcademicTerm, Payment, PaymentCollectionIntent, PlatformSetting, PlatformUser, School, SchoolSettings, SchoolVerification, Student, StudentGrade, TeacherAssignment, User, db
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


def _finance_headers(app, school_id, finance_id):
    with app.app_context():
        token = create_access_token(identity=str(finance_id))
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


def _enable_ai_pack_for_school(school_id):
    settings = SchoolSettings.query.filter_by(school_id=school_id).first()
    if settings is None:
        settings = SchoolSettings(school_id=school_id)
        db.session.add(settings)
        db.session.flush()

    enabled_modules = dict(settings.enabled_modules or {})
    enabled_modules["ai_pack_addon"] = True
    settings.enabled_modules = enabled_modules
    db.session.commit()


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


def test_platform_can_release_registration_email(client, app):
    platform_user = PlatformUser(username="release-admin", email="release-admin@example.com")
    platform_user.set_password("secret123")
    school = School(id="REL-001", name="Release School")
    proprietor = User(
        username="release-owner",
        school_id=school.id,
        role="proprietor",
        email="owner@release.edu",
    )
    proprietor.set_password("secret123")

    db.session.add_all([platform_user, school, proprietor])
    db.session.commit()

    headers = _platform_headers(app, platform_user.id)
    release_response = client.post(
        "/api/platform/registration-email-release",
        headers=headers,
        data=json.dumps({"school_id": school.id}),
    )

    assert release_response.status_code == 200
    payload = release_response.get_json()
    assert payload["released"][0]["old_email"] == "owner@release.edu"
    assert payload["released"][0]["new_email"].endswith("@edupulse.invalid")

    db.session.refresh(proprietor)
    assert proprietor.email.endswith("@edupulse.invalid")

    trace_response = client.get(f"/api/platform/registration-email-trace?school_id={school.id}", headers=headers)
    assert trace_response.status_code == 200
    actions = [row["action"] for row in trace_response.get_json()["events"]]
    assert "REGISTRATION_EMAIL_RELEASED" in actions


def test_platform_release_allows_reregistration_with_original_email(client, app):
    platform_user = PlatformUser(username="reuse-admin", email="reuse-admin@example.com")
    platform_user.set_password("secret123")
    school = School(id="OLD-EMAIL", name="Legacy Test School")
    proprietor = User(
        username="legacy-owner",
        school_id=school.id,
        role="proprietor",
        email="owner@legacy.edu",
    )
    proprietor.set_password("secret123")

    db.session.add_all([platform_user, school, proprietor])
    db.session.commit()

    blocked_response = client.post(
        "/api/register",
        json={
            "schoolCode": "NEW-EMAIL2",
            "schoolName": "Fresh School",
            "username": "fresh-owner",
            "email": "OWNER@LEGACY.EDU",
            "password": "NewSchoolPass123!",
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        },
    )
    assert blocked_response.status_code == 400

    headers = _platform_headers(app, platform_user.id)
    release_response = client.post(
        "/api/platform/registration-email-release",
        headers=headers,
        data=json.dumps({"emails": "owner@legacy.edu", "school_id": school.id}),
    )
    assert release_response.status_code == 200

    success_response = client.post(
        "/api/register",
        json={
            "schoolCode": "NEW-EMAIL2",
            "schoolName": "Fresh School",
            "username": "fresh-owner",
            "email": "owner@legacy.edu",
            "password": "NewSchoolPass123!",
            "termsAccepted": True,
            "termsVersion": "2026-02-22",
            "policyAccepted": True,
            "policyVersion": "2026-03-07",
            "schoolDataAuthorityConfirmed": True,
            "legacyAndExamConsentPlanConfirmed": True,
            "aggregatedAnalyticsAccepted": True,
        },
    )

    assert success_response.status_code == 200
    assert "successfully" in success_response.get_json()["message"].lower()


def test_platform_compliance_queue_hides_placeholder_cases(client, app):
    platform_user = PlatformUser(username="compliance-admin", email="compliance-admin@example.com")
    platform_user.set_password("secret123")
    db.session.add(platform_user)

    placeholder_school = School(id="PEND1", name="Placeholder School")
    submitted_school = School(id="REAL1", name="Submitted School")
    db.session.add_all([placeholder_school, submitted_school])
    db.session.flush()

    placeholder_case = SchoolVerification(
        school_id=placeholder_school.id,
        status="pending",
        risk_tier="medium",
        legal_name="Placeholder School",
        organization_id=placeholder_school.id,
    )
    submitted_case = SchoolVerification(
        school_id=submitted_school.id,
        status="pending",
        risk_tier="medium",
        legal_name="Submitted School",
        organization_id=submitted_school.id,
        documents=[{"document_id": "doc-1", "original_filename": "certificate.pdf"}],
        submitted_by_user_id=1,
    )
    db.session.add_all([placeholder_case, submitted_case])
    db.session.commit()

    headers = _platform_headers(app, platform_user.id)
    response = client.get("/api/platform/compliance/schools?status=all", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    school_ids = {item["school_id"] for item in payload["cases"]}
    assert "REAL1" in school_ids
    assert "PEND1" not in school_ids


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


def test_platform_can_download_school_verification_document_from_legacy_storage_root(client, app, tmp_path):
    platform_user = PlatformUser(username="platform-reviewer", email="reviewer@example.com")
    platform_user.set_password("secret123")

    school = School(id="DLG1", name="Download Test School")
    stored_filename = "school_verification_doc_test_certificate.pdf"
    verification = SchoolVerification(
        school_id=school.id,
        status="pending",
        risk_tier="medium",
        legal_name="Download Test School",
        organization_id=school.id,
        documents=[
            {
                "document_id": "doc-download-1",
                "stored_filename": stored_filename,
                "original_filename": "certificate.pdf",
            }
        ],
        submitted_by_user_id=1,
    )

    db.session.add_all([platform_user, school, verification])
    db.session.commit()

    legacy_root = tmp_path / "school-verification-documents"
    legacy_root.mkdir(parents=True, exist_ok=True)
    expected_bytes = b"legacy verification document"
    with open(legacy_root / stored_filename, "wb") as handle:
        handle.write(expected_bytes)

    app.config["SCHOOL_VERIFICATION_DOCUMENT_STORAGE_DIR"] = str(legacy_root)

    response = client.get(
        f"/api/platform/compliance/schools/{school.id}/documents/doc-download-1/download",
        headers=_platform_headers(app, platform_user.id),
    )

    assert response.status_code == 200
    assert response.data == expected_bytes


def test_platform_can_download_document_from_older_verification_record(client, app, tmp_path):
    platform_user = PlatformUser(username="platform-reviewer-2", email="reviewer-2@example.com")
    platform_user.set_password("secret123")

    school = School(id="DLG2", name="Older Verification Download School")
    stored_filename = "older_verification_certificate.pdf"
    older_verification = SchoolVerification(
        school_id=school.id,
        status="pending",
        risk_tier="medium",
        legal_name="Older Verification Download School",
        organization_id=school.id,
        documents=[
            {
                "document_id": "doc-older-1",
                "stored_filename": stored_filename,
                "original_filename": "certificate.pdf",
            }
        ],
        submitted_by_user_id=1,
    )
    newer_verification = SchoolVerification(
        school_id=school.id,
        status="verified",
        risk_tier="low",
        legal_name="Older Verification Download School",
        organization_id=school.id,
        documents=[],
        submitted_by_user_id=1,
    )

    db.session.add_all([platform_user, school, older_verification, newer_verification])
    db.session.commit()

    legacy_root = tmp_path / "school-verification-documents"
    legacy_root.mkdir(parents=True, exist_ok=True)
    expected_bytes = b"older verification document"
    with open(legacy_root / stored_filename, "wb") as handle:
        handle.write(expected_bytes)

    app.config["SCHOOL_VERIFICATION_DOCUMENT_STORAGE_DIR"] = str(legacy_root)

    response = client.get(
        f"/api/platform/compliance/schools/{school.id}/documents/doc-older-1/download",
        headers=_platform_headers(app, platform_user.id),
    )

    assert response.status_code == 200
    assert response.data == expected_bytes


def test_attendance_summary_reports_pending_until_attendance_is_marked(client, app, test_school, test_proprietor, test_students):
    response = client.get(
        "/api/headmaster/attendance-summary",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["attendance_taken_today"] is False
    assert payload["present_students"] == 0
    assert payload["absent_students"] is None
    assert payload["attendance_percentage"] is None
    assert payload["status_message"] == "Attendance has not been submitted for today yet."


def test_marking_attendance_updates_daily_summary_state(client, app, test_school, test_proprietor, test_students):
    mark_response = client.post(
        "/api/homeroom/attendance/batch",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
        data=json.dumps(
            {
                "attendance_records": [
                    {"student_id": test_students[0].id, "status": True},
                    {"student_id": test_students[1].id, "status": True},
                ]
            }
        ),
    )

    assert mark_response.status_code == 200

    response = client.get(
        "/api/headmaster/attendance-summary",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["attendance_taken_today"] is True
    assert payload["present_students"] == 2
    assert payload["absent_students"] == 3
    assert payload["attendance_percentage"] == 40.0


def test_first_attendance_submission_of_new_day_resets_stale_present_flags(client, app, db, test_school, test_proprietor, test_students):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    for student in test_students:
        student.is_present = True
    settings.attendance_last_marked_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()

    mark_response = client.post(
        "/api/homeroom/attendance/batch",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
        data=json.dumps(
            {
                "attendance_records": [
                    {"student_id": test_students[0].id, "status": True},
                ]
            }
        ),
    )

    assert mark_response.status_code == 200

    response = client.get(
        "/api/headmaster/attendance-summary",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["attendance_taken_today"] is True
    assert payload["present_students"] == 1
    assert payload["absent_students"] == len(test_students) - 1


def test_partial_attendance_counts_only_submitted_classes(client, app, db, test_school, test_proprietor, test_students):
    other_class_student = Student(
        school_id=test_school.id,
        first_name="Akua",
        surname="Other",
        name="Akua Other",
        student_code="S919",
        current_class="JHS 2",
        is_present=False,
    )
    db.session.add(other_class_student)
    db.session.commit()

    mark_response = client.post(
        "/api/homeroom/attendance/batch",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
        data=json.dumps(
            {
                "attendance_records": [
                    {"student_id": test_students[0].id, "status": True},
                ],
                "class_name": "JHS 1",
            }
        ),
    )
    assert mark_response.status_code == 200

    other_class_student.is_present = True
    db.session.add(other_class_student)
    db.session.commit()

    response = client.get(
        "/api/headmaster/attendance-summary",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["attendance_taken_today"] is False
    assert payload["attendance_partial"] is True
    assert payload["present_students"] == 1
    assert payload["submitted_classes_count"] == 1


def test_ai_insights_avoid_misleading_new_school_alerts_before_attendance_or_payment_baseline(client, app, test_school, test_proprietor, test_students):
    response = client.get(
        "/api/proprietor/ai-insights",
        headers=_proprietor_headers(app, test_school.id, test_proprietor.id),
    )

    assert response.status_code == 200
    payload = response.get_json()
    insight_titles = {item["title"] for item in payload["insights"]}
    alert_titles = {item["title"] for item in payload["alerts"]}

    assert "Attendance Pending" in insight_titles
    assert "Excellent Attendance" not in insight_titles
    assert "Feeding Fees Pending" not in insight_titles
    assert "Revenue Decline" not in alert_titles


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


def test_live_feed_groups_pending_payments_by_class(client, app, test_school, test_proprietor):
    jhs_student = Student(
        school_id=test_school.id,
        first_name="Efia",
        surname="Owusu",
        name="Efia Owusu",
        student_code="S920",
        current_class="JHS 1",
        total_tuition_owed=300.0,
        parent_name="Mansa Owusu",
        parent_phone="+233500000001",
        is_present=True,
        feeding_paid=False,
    )
    primary_student = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Baah",
        name="Kojo Baah",
        student_code="S921",
        current_class="Primary 4",
        total_tuition_owed=250.0,
        parent_name="Akosua Baah",
        parent_phone="+233500000002",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add_all([jhs_student, primary_student])
    db.session.flush()

    db.session.add_all(
        [
            Payment(
                student_id=jhs_student.id,
                school_id=test_school.id,
                amount=120.0,
                payment_type="Tuition",
                method="Cash",
                status="Pending",
            ),
            Payment(
                student_id=primary_student.id,
                school_id=test_school.id,
                amount=15.0,
                payment_type="Feeding",
                method="Cash",
                status="Pending",
            ),
        ]
    )
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/proprietor/live-feed", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["pending_payments"]) == 2
    assert {item["class_name"] for item in payload["pending_payments"]} == {"JHS 1", "Primary 4"}

    grouped = {group["class_name"]: group for group in payload["pending_payments_by_class"]}
    assert grouped["JHS 1"]["count"] == 1
    assert grouped["JHS 1"]["total_amount"] == 120.0
    assert grouped["JHS 1"]["payments"][0]["student"] == "Efia Owusu"
    assert grouped["Primary 4"]["payments"][0]["type"] == "Feeding"


def test_proprietor_can_bulk_confirm_pending_payments_for_class(client, app, test_school, test_proprietor):
    student_one = Student(
        school_id=test_school.id,
        first_name="Yaw",
        surname="Mills",
        name="Yaw Mills",
        student_code="S930",
        current_class="JHS 2",
        total_tuition_owed=500.0,
        parent_name="Martha Mills",
        parent_phone="+233500000003",
        is_present=True,
        feeding_paid=False,
    )
    student_two = Student(
        school_id=test_school.id,
        first_name="Adjoa",
        surname="Kumi",
        name="Adjoa Kumi",
        student_code="S931",
        current_class="JHS 2",
        total_tuition_owed=200.0,
        parent_name="Kwesi Kumi",
        parent_phone="+233500000004",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add_all([student_one, student_two])
    db.session.flush()

    payment_one = Payment(
        student_id=student_one.id,
        school_id=test_school.id,
        amount=150.0,
        payment_type="Tuition",
        method="Cash",
        status="Pending",
    )
    payment_two = Payment(
        student_id=student_two.id,
        school_id=test_school.id,
        amount=20.0,
        payment_type="Feeding",
        method="Cash",
        status="Pending",
    )
    db.session.add_all([payment_one, payment_two])
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.post(
        "/api/finance/confirm-payments/bulk",
        headers=headers,
        data=json.dumps(
            {
                "class_name": "JHS 2",
                "payment_ids": [payment_one.id, payment_two.id],
            }
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 2
    assert payload["class_name"] == "JHS 2"
    assert payload["total_amount"] == 170.0

    refreshed_one = Payment.query.get(payment_one.id)
    refreshed_two = Payment.query.get(payment_two.id)
    updated_student_one = Student.query.get(student_one.id)
    updated_student_two = Student.query.get(student_two.id)

    assert refreshed_one.status == "Confirmed"
    assert refreshed_two.status == "Confirmed"
    assert refreshed_one.verified_by == test_proprietor.id
    assert refreshed_two.verified_by == test_proprietor.id
    assert updated_student_one.total_tuition_owed == 350.0
    assert updated_student_two.feeding_paid is True


def test_students_by_class_treat_pending_daily_feeding_cash_as_paid(client, app, test_school):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    homeroom_teacher = User(
        username="homeroom_feed_pending",
        school_id=test_school.id,
        role="homeroom",
        roles=["homeroom"],
        email="homeroom-feed-pending@test.edu",
        assigned_class="JHS 1",
    )
    homeroom_teacher.set_password("HomeroomPass123")
    student = Student(
        school_id=test_school.id,
        first_name="Ama",
        surname="Pending",
        name="Ama Pending",
        student_code="S940",
        current_class="JHS 1",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add_all([homeroom_teacher, student])
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 5.0,
                "weekly": 20.0,
                "monthly": 80.0,
            }
        }
    }
    db.session.add(
        Payment(
            student_id=student.id,
            school_id=test_school.id,
            created_by_user_id=homeroom_teacher.id,
            amount=5.0,
            payment_type="Feeding",
            method="Cash",
            status="Pending",
            payment_category={"frequency": "Daily"},
            date_paid=datetime.now(timezone.utc),
        )
    )
    db.session.commit()

    headers = _homeroom_headers(app, test_school.id, homeroom_teacher.id)
    response = client.get("/api/students/by-class/JHS 1", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    target = next(item for item in payload if item["student_code"] == "S940")
    assert target["feeding_paid"] is False
    assert target["payment_method"] is None
    assert target["feeding_frequency"] is None
    assert target["feeding_pending_approval"] is True
    assert target["feeding_pending_amount"] == 5.0


def test_students_by_class_expires_daily_feeding_once_coverage_is_used(client, app, test_school):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    homeroom_teacher = User(
        username="homeroom_feed_expired",
        school_id=test_school.id,
        role="homeroom",
        roles=["homeroom"],
        email="homeroom-feed-expired@test.edu",
        assigned_class="JHS 1",
    )
    homeroom_teacher.set_password("HomeroomPass123")
    student = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Expired",
        name="Kojo Expired",
        student_code="S941",
        current_class="JHS 1",
        is_present=True,
        feeding_paid=True,
    )
    db.session.add_all([homeroom_teacher, student])
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 5.0,
            }
        }
    }
    db.session.add(
        Payment(
            student_id=student.id,
            school_id=test_school.id,
            created_by_user_id=homeroom_teacher.id,
            amount=5.0,
            payment_type="Feeding",
            method="Bank_Auto",
            status="Confirmed",
            payment_category={"frequency": "Daily"},
            date_paid=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db.session.commit()

    headers = _homeroom_headers(app, test_school.id, homeroom_teacher.id)
    response = client.get("/api/students/by-class/JHS 1", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    target = next(item for item in payload if item["student_code"] == "S941")
    assert target["feeding_paid"] is False


def test_students_by_class_monthly_feeding_uses_calendar_month_boundaries(client, app, test_school):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    homeroom_teacher = User(
        username="homeroom_feed_month_boundary",
        school_id=test_school.id,
        role="homeroom",
        roles=["homeroom"],
        email="homeroom-feed-month-boundary@test.edu",
        assigned_class="JHS 1",
    )
    homeroom_teacher.set_password("HomeroomPass123")
    student = Student(
        school_id=test_school.id,
        first_name="Akua",
        surname="MonthBoundary",
        name="Akua MonthBoundary",
        student_code="S942",
        current_class="JHS 1",
        is_present=True,
        feeding_paid=True,
    )
    db.session.add_all([homeroom_teacher, student])
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "monthly": 80.0,
            }
        }
    }

    today = datetime.now(timezone.utc).date()
    if today.month == 1:
        payment_date = date(today.year - 1, 12, 15)
    else:
        payment_date = date(today.year, today.month - 1, 15)

    db.session.add(
        Payment(
            student_id=student.id,
            school_id=test_school.id,
            created_by_user_id=homeroom_teacher.id,
            amount=80.0,
            payment_type="Feeding",
            method="Bank_Auto",
            status="Confirmed",
            payment_category={"frequency": "Monthly"},
            date_paid=datetime.combine(payment_date, datetime.min.time(), tzinfo=timezone.utc),
        )
    )
    db.session.commit()

    headers = _homeroom_headers(app, test_school.id, homeroom_teacher.id)
    response = client.get("/api/students/by-class/JHS 1", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    target = next(item for item in payload if item["student_code"] == "S942")
    assert target["feeding_paid"] is False


def test_students_index_uses_derived_feeding_status(client, app, db, test_school, test_proprietor):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    student = Student(
        school_id=test_school.id,
        first_name="Abena",
        surname="Registry",
        name="Abena Registry",
        student_code="S943",
        current_class="JHS 2",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(student)
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 5.0,
            }
        }
    }
    db.session.add(
        Payment(
            student_id=student.id,
            school_id=test_school.id,
            created_by_user_id=test_proprietor.id,
            amount=5.0,
            payment_type="Feeding",
            method="Cash",
            status="Pending",
            payment_category={"frequency": "Daily"},
            date_paid=datetime.now(timezone.utc),
        )
    )
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/students", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    target = next(item for item in payload if item["student_code"] == "S943")
    assert target["feeding_paid"] is False
    assert target["payment_method"] is None
    assert target["feeding_frequency"] is None
    assert target["feeding_pending_approval"] is True
    assert target["feeding_pending_amount"] == 5.0


def test_transaction_history_shows_derived_feeding_frequency_for_cash_payments(client, app, db, test_school, test_proprietor):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    student = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Frequency",
        name="Kojo Frequency",
        student_code="S944",
        current_class="JHS 2",
        is_present=True,
    )
    db.session.add(student)
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 20.0,
                "weekly": 100.0,
                "monthly": 400.0,
            }
        }
    }
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    record_response = client.post(
        "/api/finance/receive-payment",
        headers=headers,
        data=json.dumps(
            {
                "student_id": student.id,
                "amount": 100.0,
                "type": "Feeding",
                "method": "Cash",
                "payment_category": {},
            }
        ),
    )
    assert record_response.status_code == 200

    history_response = client.get("/api/finance/transactions", headers=headers)
    assert history_response.status_code == 200
    transactions = history_response.get_json()
    target = next(item for item in transactions if item["student_code"] == "S944")
    assert target["type"] == "Feeding"
    assert target["feeding_frequency"] == "Weekly"
    assert target["payment_category"]["frequency"] == "Weekly"


def test_canteen_count_includes_pending_or_confirmed_feeding_coverage(client, app, test_school, test_proprietor, monkeypatch):
    from backend.routes import _mark_attendance_activity

    monkeypatch.setattr("backend.routes._is_school_instruction_day", lambda _school_id, _target_date: True)

    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    covered_student = Student(
        school_id=test_school.id,
        first_name="Efua",
        surname="Covered",
        name="Efua Covered",
        student_code="S950",
        current_class="Primary 4",
        is_present=True,
        feeding_paid=False,
    )
    unpaid_student = Student(
        school_id=test_school.id,
        first_name="Yaw",
        surname="Unpaid",
        name="Yaw Unpaid",
        student_code="S951",
        current_class="Primary 4",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add_all([covered_student, unpaid_student])
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 5.0,
                "weekly": 20.0,
                "monthly": 80.0,
            }
        }
    }
    db.session.add(
        Payment(
            student_id=covered_student.id,
            school_id=test_school.id,
            created_by_user_id=test_proprietor.id,
            amount=20.0,
            payment_type="Feeding",
            method="USSD_Auto",
            status="Confirmed",
            payment_category={"frequency": "Weekly"},
            date_paid=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    _mark_attendance_activity(test_school.id, submitted_classes=["Primary 4"])

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/canteen/daily-count", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    staff_meals = (
        User.query.filter_by(school_id=test_school.id)
        .filter(User.role.in_(["teacher", "homeroom", "headmaster", "proprietor"]))
        .count()
    )
    assert payload["total_meals"] == staff_meals + 1


def test_canteen_count_includes_homeroom_staff_meals(client, app, test_school, test_proprietor, monkeypatch):
    from backend.routes import _mark_attendance_activity

    monkeypatch.setattr("backend.routes._is_school_instruction_day", lambda _school_id, _target_date: True)

    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    homeroom_user = User(
        username="homeroom_meals_case",
        school_id=test_school.id,
        role="homeroom",
        roles=["homeroom"],
        email="homeroom-meals@test.edu",
        assigned_class="Primary 3",
    )
    homeroom_user.set_password("HomeroomPass123")
    db.session.add(homeroom_user)
    db.session.flush()

    covered_student = Student(
        school_id=test_school.id,
        first_name="Esi",
        surname="Coverage",
        name="Esi Coverage",
        student_code="S953",
        current_class="Primary 3",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(covered_student)
    db.session.flush()

    settings.report_template_config = {
        "payment_plan_settings": {
            "feeding": {
                "daily": 5.0,
            }
        }
    }
    db.session.add(
        Payment(
            student_id=covered_student.id,
            school_id=test_school.id,
            created_by_user_id=test_proprietor.id,
            amount=5.0,
            payment_type="Feeding",
            method="Cash",
            status="Confirmed",
            payment_category={"frequency": "Daily"},
            date_paid=datetime.now(timezone.utc),
        )
    )
    db.session.commit()
    _mark_attendance_activity(test_school.id, submitted_classes=["Primary 3"])

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/canteen/daily-count", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    staff_meals = (
        User.query.filter_by(school_id=test_school.id)
        .filter(User.role.in_(["teacher", "homeroom", "headmaster", "proprietor"]))
        .count()
    )
    assert payload["total_meals"] == staff_meals + 1


def test_canteen_count_ignores_stale_present_flags_until_attendance_is_marked_today(client, app, db, test_school, test_proprietor):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if settings is None:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)
        db.session.flush()

    covered_student = Student(
        school_id=test_school.id,
        first_name="Adjoa",
        surname="Stale",
        name="Adjoa Stale",
        student_code="S952",
        current_class="Primary 5",
        is_present=True,
        feeding_paid=True,
    )
    db.session.add(covered_student)
    settings.attendance_last_marked_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/canteen/daily-count", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    staff_meals = (
        User.query.filter_by(school_id=test_school.id)
        .filter(User.role.in_(["teacher", "homeroom", "headmaster", "proprietor"]))
        .count()
    )
    assert payload["total_meals"] == staff_meals


def test_finance_dashboard_groups_pending_payments_and_exposes_recorder_metadata(client, app, test_school):
    finance_user = User(
        username="finance_case",
        school_id=test_school.id,
        role="finance",
        email="finance@test.edu",
    )
    homeroom_user = User(
        username="homeroom_case",
        school_id=test_school.id,
        role="homeroom",
        email="homeroom@test.edu",
        assigned_class="JHS 1",
    )
    finance_user.set_password("FinancePass123")
    homeroom_user.set_password("HomeroomPass123")
    db.session.add_all([finance_user, homeroom_user])
    db.session.flush()

    student = Student(
        school_id=test_school.id,
        first_name="Akua",
        surname="Mensima",
        name="Akua Mensima",
        student_code="S940",
        current_class="JHS 1",
        total_tuition_owed=420.0,
        parent_name="Yaa Mensima",
        parent_phone="+233500000005",
        is_present=True,
        feeding_paid=False,
    )
    db.session.add(student)
    db.session.flush()

    pending_payment = Payment(
        student_id=student.id,
        school_id=test_school.id,
        created_by_user_id=homeroom_user.id,
        amount=25.0,
        payment_type="Feeding",
        method="Cash",
        status="Pending",
    )
    db.session.add(pending_payment)
    db.session.commit()

    headers = _finance_headers(app, test_school.id, finance_user.id)
    response = client.get("/api/finance/dashboard", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["pending_payments"]) == 1
    assert payload["pending_payments"][0]["recorded_by_role"] == "homeroom"
    assert payload["pending_payments"][0]["recorded_by_label"] == "Homeroom Teacher"
    assert payload["pending_payments"][0]["recorded_by_name"] == "homeroom_case"

    grouped = payload["pending_payments_by_class"]
    assert len(grouped) == 1
    assert grouped[0]["class_name"] == "JHS 1"
    assert grouped[0]["payments"][0]["recorded_by_role"] == "homeroom"


def test_student_rescue_agent_does_not_flag_tuition_just_after_reopening_without_other_behaviour_signals(client, app, test_school, test_proprietor):
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    assert payload["required_plan"] == "School OS + AI Pack"


def test_subscription_payload_exposes_trial_addon_features(client, app, test_school, test_proprietor):
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=14)
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get("/api/school/subscription", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["plan"] == "Premium"
    assert payload["base_plan"] == "Free Tier"
    assert payload["active_addons"]["ai_pack"] is True
    assert payload["active_addons"]["automation_pack"] is True
    assert payload["features"]["student_rescue_agent"] is True
    assert payload["features"]["exam_intelligence"] is True
    assert payload["features"]["webhook_payment_automation"] is True


def test_basic_plan_blocks_academic_guidance_routes(client, app, test_school, test_teacher):
    test_school.subscription_plan = "Basic"
    db.session.commit()

    headers = _teacher_headers(app, test_school.id, test_teacher.id)
    response = client.get("/api/analytics/academic-guidance", headers=headers)

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["current_plan"] == "Basic"
    assert payload["required_plan"] == "School OS + AI Pack"


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
    assert payload["required_plan"] == "School OS Plus"


def test_student_rescue_email_send_logs_outcome(client, app, test_school, test_proprietor, monkeypatch):
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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


def test_school_settings_auto_create_paystack_subaccount_from_bank_details(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    captured_calls = []

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured_calls.append((endpoint, method, data))
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            assert data["bank_code"] == "070100"
            assert data["account_number"] == "1234567890"
            return ({"subaccount_code": "SUB_test123"}, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings",
        headers=headers,
        data=json.dumps(
            {
                "bank_name": "Fidelity Bank Ghana",
                "bank_account": "1234567890",
                "bank_account_name": "EduPulse School Account",
                "bank_branch": "Kumasi Main",
            }
        ),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["paystack_subaccount_code"] == "SUB_test123"
    assert payload["paystack_bank_code"] == "070100"
    assert payload["paystack_resolved_account_name"] == "EDUPULSE SCHOOL ACCOUNT"
    assert "Paystack subaccount created automatically" in payload["message"]

    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    assert settings is not None

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.get_json()
    assert settings_payload["paystack_subaccount_code"] == "SUB_test123"
    assert settings_payload["paystack_bank_code"] == "070100"
    assert settings_payload["paystack_resolved_account_name"] == "EDUPULSE SCHOOL ACCOUNT"

    assert [call[0] for call in captured_calls] == [
        "/bank?country=ghana&currency=GHS",
        "/bank/resolve?account_number=1234567890&bank_code=070100",
        "/subaccount",
    ]


def test_school_settings_save_can_create_missing_paystack_subaccount_from_existing_bank_details(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    test_school.bank_branch = "Kumasi Main"
    db.session.commit()

    captured_calls = []

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured_calls.append((endpoint, method, data))
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            return ({"subaccount_code": "SUB_existing123"}, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings",
        headers=headers,
        data=json.dumps({"school_phone": "+233200000000"}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["paystack_subaccount_code"] == "SUB_existing123"
    assert "Paystack subaccount created automatically" in payload["message"]

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.get_json()
    assert settings_payload["paystack_subaccount_code"] == "SUB_existing123"
    assert settings_payload["paystack_bank_code"] == "070100"
    assert settings_payload["paystack_resolved_account_name"] == "EDUPULSE SCHOOL ACCOUNT"
    assert [call[0] for call in captured_calls] == [
        "/bank?country=ghana&currency=GHS",
        "/bank/resolve?account_number=1234567890&bank_code=070100",
        "/subaccount",
    ]


def test_school_settings_can_reconnect_missing_paystack_subaccount_without_full_save(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    db.session.commit()

    captured_calls = []

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured_calls.append((endpoint, method, data))
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            return ({"subaccount_code": "SUB_retry123"}, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings/paystack/reconnect",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "Paystack settlement account created successfully."
    assert payload["paystack_subaccount_code"] == "SUB_retry123"
    assert payload["paystack_bank_code"] == "070100"
    assert payload["paystack_resolved_account_name"] == "EDUPULSE SCHOOL ACCOUNT"

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    settings_payload = settings_response.get_json()
    assert settings_payload["paystack_subaccount_code"] == "SUB_retry123"

    assert [call[0] for call in captured_calls] == [
        "/bank?country=ghana&currency=GHS",
        "/bank/resolve?account_number=1234567890&bank_code=070100",
        "/subaccount",
    ]


def test_school_settings_reconnect_retries_without_optional_contact_fields_when_provider_rejects_them(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    test_school.school_email = "owner@example.com"
    test_school.school_phone = "+233501234567"
    db.session.commit()

    captured_calls = []

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured_calls.append((endpoint, method, data))
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            if data.get("primary_contact_email"):
                return (None, "Invalid value for primary_contact_email")
            assert "primary_contact_email" not in data
            assert "primary_contact_phone" not in data
            return ({"subaccount_code": "SUB_retry_no_optional"}, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings/paystack/reconnect",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["paystack_subaccount_code"] == "SUB_retry_no_optional"
    subaccount_calls = [call for call in captured_calls if call[0] == "/subaccount"]
    assert len(subaccount_calls) == 2


def test_school_settings_subaccount_creation_omits_blank_optional_contact_fields(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    test_school.school_email = None
    test_school.school_phone = ""
    db.session.commit()

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            assert "primary_contact_email" not in data
            assert "primary_contact_phone" not in data
            assert data["primary_contact_name"] == "EduPulse School Account"
            return ({"subaccount_code": "SUB_optional001"}, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings/paystack/reconnect",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["paystack_subaccount_code"] == "SUB_optional001"


def test_school_settings_reconnect_returns_provider_detail_on_failure(client, app, db, test_school, test_proprietor, monkeypatch):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    db.session.commit()

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        if endpoint == "/bank?country=ghana&currency=GHS" and method == "GET":
            return ([{"name": "Fidelity Bank Ghana Ltd", "code": "070100"}], None)
        if endpoint == "/bank/resolve?account_number=1234567890&bank_code=070100" and method == "GET":
            return ({"account_name": "EDUPULSE SCHOOL ACCOUNT", "account_number": "1234567890"}, None)
        if endpoint == "/subaccount" and method == "POST":
            return (None, "Invalid value for primary_contact_email")
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        "/api/school/settings/paystack/reconnect",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 502
    payload = response.get_json()
    assert payload["error"] == "payment_settlement_setup_unavailable"
    assert payload["provider_detail"] == "Paystack subaccount created failed: Invalid value for primary_contact_email"


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


def test_school_settings_ai_registrar_enabled_for_active_premium_trial(client, app, db, test_school, test_proprietor):
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=7)
    db.session.commit()

    settings_response = client.get("/api/school/settings", headers=headers)
    assert settings_response.status_code == 200
    payload = settings_response.get_json()
    assert payload["ai_registrar_enabled"] is True
    assert payload["ai_registrar_addon_enabled"] is True

    plan_response = client.get("/api/school/subscription/effective-plan", headers=headers)
    assert plan_response.status_code == 200
    plan_payload = plan_response.get_json()
    assert plan_payload["effective_plan"] == "Premium"
    assert plan_payload["trial"]["active"] is True
    assert plan_payload["trial"]["plan"] == "Premium"


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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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
    _enable_ai_pack_for_school(test_school.id)

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

    _enable_ai_pack_for_school(test_school.id)

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

    _enable_ai_pack_for_school(test_school.id)

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


def test_teacher_demo_exam_summary_and_academic_guidance_payloads_are_populated(client, app, test_school, test_proprietor, test_teacher, tmp_path):
    _enable_ai_pack_for_school(test_school.id)

    app.config["EXAM_INTELLIGENCE_STORAGE_DIR"] = str(tmp_path / "exam-intelligence")

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

    student_one = Student(
        school_id=test_school.id,
        first_name="Ama",
        surname="Mensah",
        name="Ama Mensah",
        student_code="STU101",
        current_class="JHS 1",
    )
    student_two = Student(
        school_id=test_school.id,
        first_name="Kojo",
        surname="Owusu",
        name="Kojo Owusu",
        student_code="STU102",
        current_class="JHS 1",
    )
    db.session.add_all([student_one, student_two])
    db.session.flush()

    db.session.add_all(
        [
            TeacherAssignment(
                school_id=test_school.id,
                teacher_id=test_teacher.id,
                class_name="JHS 1",
                subject_name="Mathematics",
            ),
            TeacherAssignment(
                school_id=test_school.id,
                teacher_id=test_teacher.id,
                class_name="JHS 1",
                subject_name="Science",
            ),
        ]
    )

    latest_reports = [
        ReportCard(
            school_id=test_school.id,
            student_id=student_one.id,
            academic_term="Term 3",
            academic_year="2025/2026",
            class_name="JHS 1",
            subject_grades=[
                {"subject": "Mathematics", "total": 84, "diagnostic_topics": [{"topic": "Geometry", "score": 6, "max_score": 15}]},
                {"subject": "Science", "total": 76, "diagnostic_topics": [{"topic": "Scientific Units", "score": 6, "max_score": 10}]},
            ],
            status="Approved",
        ),
        ReportCard(
            school_id=test_school.id,
            student_id=student_two.id,
            academic_term="Term 3",
            academic_year="2025/2026",
            class_name="JHS 1",
            subject_grades=[
                {"subject": "Mathematics", "total": 62, "diagnostic_topics": [{"topic": "Geometry", "score": 4, "max_score": 15}]},
                {"subject": "Science", "total": 58, "diagnostic_topics": [{"topic": "Scientific Units", "score": 3, "max_score": 10}]},
            ],
            status="Approved",
        ),
    ]
    db.session.add_all(latest_reports)
    db.session.commit()

    multipart_headers = {key: value for key, value in proprietor_headers.items() if key != "Content-Type"}
    upload_latest = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2025/2026",
            "file": (
                BytesIO(
                    (
                        "candidate_id,candidate_name,class_name,gender,subject,score,grade\n"
                        "STU101,Ama Mensah,JHS 1,Female,Mathematics,84,A1\n"
                        "STU101,Ama Mensah,JHS 1,Female,Science,76,B2\n"
                        "STU102,Kojo Owusu,JHS 1,Male,Mathematics,62,C4\n"
                        "STU102,Kojo Owusu,JHS 1,Male,Science,58,C5\n"
                    ).encode("utf-8")
                ),
                "demo-bece-2025-2026.csv",
            ),
        },
        content_type="multipart/form-data",
    )
    assert upload_latest.status_code == 201

    upload_previous = client.post(
        "/api/analytics/exam-imports",
        headers=multipart_headers,
        data={
            "exam_type": "BECE",
            "academic_year": "2024/2025",
            "file": (
                BytesIO(
                    (
                        "candidate_id,candidate_name,class_name,gender,subject,score,grade\n"
                        "STU101,Ama Mensah,JHS 1,Female,Mathematics,79,B2\n"
                        "STU101,Ama Mensah,JHS 1,Female,Science,71,B3\n"
                        "STU102,Kojo Owusu,JHS 1,Male,Mathematics,57,C5\n"
                        "STU102,Kojo Owusu,JHS 1,Male,Science,54,C6\n"
                    ).encode("utf-8")
                ),
                "demo-bece-2024-2025.csv",
            ),
        },
        content_type="multipart/form-data",
    )
    assert upload_previous.status_code == 201

    headers = _teacher_headers(app, test_school.id, test_teacher.id)
    exam_response = client.get("/api/analytics/exam-intelligence", headers=headers)
    guidance_response = client.get("/api/analytics/academic-guidance", headers=headers)

    assert exam_response.status_code == 200
    exam_payload = exam_response.get_json()
    assert exam_payload["view_scope"] == "teacher_subject_summary"
    assert exam_payload["summary"]["tracked_subjects"] == 2
    assert exam_payload["summary"]["latest_subject_count"] == 2
    assert exam_payload["latest_batch"]["academic_year"] == "2025/2026"
    assert {item["subject"] for item in exam_payload["latest_batch"]["subject_summaries"]} == {"Mathematics", "Science"}
    assert len(exam_payload["class_summaries"]) == 1
    assert exam_payload["class_summaries"][0]["class_name"] == "JHS 1"

    assert guidance_response.status_code == 200
    guidance_payload = guidance_response.get_json()
    assert guidance_payload["summary"]["reports_analyzed"] == 2
    assert guidance_payload["summary"]["tracked_subjects"] == 2
    assert guidance_payload["summary"]["classes_in_scope"] == 1
    assert guidance_payload["scope"]["allowed_subjects"] == ["Mathematics", "Science"]
    assert any(item["subject"] == "Mathematics" and item["topic"] == "Geometry" for item in guidance_payload["diagnostic_hotspots"])
    assert guidance_payload["pathway_distribution"]
    business_signal = next(item for item in guidance_payload["pathway_distribution"] if item["pathway"] == "Business")
    assert [learner["student_name"] for learner in business_signal["learners"]] == ["Ama Mensah", "Kojo Owusu"]
    assert [learner["student_code"] for learner in business_signal["learners"]] == ["STU101", "STU102"]
    assert all(learner["class_name"] == "JHS 1" for learner in business_signal["learners"])


def test_subject_teacher_diagnostics_flow_into_homeroom_report_builder(client, app, test_school):
    subject_teacher = User(
        username="diag_subject_teacher",
        password_hash="hash",
        role="teacher",
        school_id=test_school.id,
    )
    homeroom_teacher = User(
        username="diag_homeroom_teacher",
        password_hash="hash",
        role="teacher",
        school_id=test_school.id,
        assigned_class="JHS 1",
    )
    student = Student(
        school_id=test_school.id,
        first_name="Yaw",
        surname="Mensah",
        name="Yaw Mensah",
        student_code="DG001",
        current_class="JHS 1",
    )
    db.session.add_all([
        subject_teacher,
        homeroom_teacher,
        student,
    ])
    db.session.flush()
    db.session.add(
        TeacherAssignment(
            school_id=test_school.id,
            teacher_id=subject_teacher.id,
            class_name="JHS 1",
            subject_name="Mathematics",
        )
    )
    db.session.commit()

    try:
        subject_headers = _teacher_headers(app, test_school.id, subject_teacher.id)
        homeroom_headers = _homeroom_headers(app, test_school.id, homeroom_teacher.id)

        submit_response = client.post(
            "/api/teacher/submit-grades-to-homeroom",
            headers=subject_headers,
            data=json.dumps(
                {
                    "class_name": "JHS 1",
                    "subject": "Mathematics",
                    "grade_data": {
                        str(student.id): {
                            "class_score": 24,
                            "exam_score": 52,
                            "diagnostic_topics": [
                                {"topic": "Geometry", "score": 6, "max_score": 15},
                                {"topic": "Algebra", "score": 5, "max_score": 12},
                            ],
                        }
                    },
                }
            ),
        )
        assert submit_response.status_code == 200

        stored_grade = StudentGrade.query.filter_by(student_id=student.id, subject_name="Mathematics", class_name="JHS 1").first()
        assert stored_grade is not None
        assert stored_grade.diagnostic_topics == [
            {"topic": "Geometry", "score": 6.0, "max_score": 15.0},
            {"topic": "Algebra", "score": 5.0, "max_score": 12.0},
        ]

        autofill_response = client.get(
            f"/api/homeroom/report-builder/auto-fill/{student.id}?class_name=JHS%201&academic_term=Term%203&academic_year=2025/2026",
            headers=homeroom_headers,
        )
        assert autofill_response.status_code == 200
        autofill_payload = autofill_response.get_json()
        assert autofill_payload["subject_grades"][0]["diagnostic_topics"] == [
            {"topic": "Geometry", "score": 6.0, "max_score": 15.0},
            {"topic": "Algebra", "score": 5.0, "max_score": 12.0},
        ]

        save_response = client.post(
            "/api/homeroom/report-builder/report",
            headers=homeroom_headers,
            data=json.dumps(
                {
                    "student_id": student.id,
                    "academic_term": "Term 3",
                    "academic_year": "2025/2026",
                    "subject_grades": autofill_payload["subject_grades"],
                    "overall_position": "1st",
                    "out_of_students": 1,
                    "attendance_percentage": 95,
                    "total_attendance": 68,
                    "homeroom_teacher_remarks": "Good diagnostic data captured.",
                }
            ),
        )
        assert save_response.status_code == 200
        saved_payload = save_response.get_json()
        assert saved_payload["report"]["subject_grades"][0]["diagnostic_topics"] == [
            {"topic": "Geometry", "score": 6.0, "max_score": 15.0},
            {"topic": "Algebra", "score": 5.0, "max_score": 12.0},
        ]
    finally:
        TeacherAssignment.query.filter_by(teacher_id=subject_teacher.id).delete()
        StudentGrade.query.filter_by(student_id=student.id).delete()
        ReportCard.query.filter_by(student_id=student.id).delete()
        db.session.delete(student)
        db.session.delete(subject_teacher)
        db.session.delete(homeroom_teacher)
        db.session.commit()


def test_payment_codes_return_reference_first_amounts_without_convenience_fee(client, app, test_school, test_proprietor, test_students):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    if not settings:
        settings = SchoolSettings(school_id=test_school.id)
        db.session.add(settings)

    settings.tuition_fee = 100.0
    settings.terminal_report_fee = 0.0
    settings.feeding_fee = 0.0
    settings.transport_fee = 0.0
    settings.other_fees = {}
    test_school.bank_name = "Fidelity Bank Ghana"
    test_school.bank_account = "1234567890"
    test_school.bank_account_name = "EduPulse School Account"
    test_school.bank_branch = "Kumasi Main"
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(f"/api/students/{test_students[0].id}/payment-codes", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    tuition_code = next(item for item in payload["payment_codes"] if item["fee_type"] == "Tuition + Terminal Report")
    assert tuition_code["base_amount"] == 100.0
    assert tuition_code["cash_amount"] == 100.0
    assert tuition_code["total_amount"] == 100.0
    assert tuition_code["amount"] == 100.0
    assert payload["school_payment_account"]["bank_name"] == "Fidelity Bank Ghana"
    assert payload["school_payment_account"]["bank_account"] == "1234567890"
    assert payload["school_payment_account"]["bank_account_name"] == "EduPulse School Account"
    assert payload["school_payment_account"]["bank_branch"] == "Kumasi Main"
    assert "amount to pay for this fee is gh₵ 100.00" in tuition_code["instructions"].lower()
    assert "structured reference" in payload["note"].lower()


def test_student_payment_code_can_generate_tracked_transfer_account(client, app, test_school, test_proprietor, test_students, monkeypatch):
    from backend.routes import GLOBAL_REPORT_SETTINGS_KEY, PAYMENT_PROVIDER_SETTINGS_KEY

    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.tuition_fee = 100.0
    settings.terminal_report_fee = 0.0
    settings.report_template_config = {
        GLOBAL_REPORT_SETTINGS_KEY: {
            PAYMENT_PROVIDER_SETTINGS_KEY: {
                "paystack_subaccount_code": "SUB_school001",
                "paystack_bank_code": "070100",
                "paystack_resolved_account_name": "EduPulse School Account",
            }
        }
    }
    db.session.add(
        PlatformSetting(
            setting_key="payment_collection_pricing",
            setting_value={
                "charge_parent_convenience_fee": True,
                "estimated_provider_fee_rate_pct": 2.0,
                "estimated_provider_fee_flat": 1.0,
                "platform_fee_flat": 3.0,
                "platform_fee_label": "EduPulse Convenience Fee",
            },
        )
    )
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    student = test_students[0]
    captured = []

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured.append((endpoint, method, data))
        if endpoint == "/split" and method == "POST":
            return ({"id": 501, "split_code": "SPLIT_school001_10000"}, None)
        if endpoint == "/dedicated_account/available_providers" and method == "GET":
            return ([{"provider_slug": "titan-paystack", "bank_name": "Paystack-Titan"}], None)
        if endpoint == "/customer" and method == "POST":
            return ({"customer_code": "CUS_ROUTE_001"}, None)
        if endpoint == "/dedicated_account" and method == "POST":
            return ({
                "id": 915,
                "account_name": "EDUPULSE / AMA MENSAH",
                "account_number": "0192837465",
                "bank": {"name": "Paystack-Titan", "slug": "titan-paystack"},
            }, None)
        raise AssertionError(f"Unexpected Paystack call: {method} {endpoint}")

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    codes_response = client.get(f"/api/students/{student.id}/payment-codes", headers=headers)
    assert codes_response.status_code == 200
    tuition_code = next(item for item in codes_response.get_json()["payment_codes"] if item["fee_type"] == "Tuition + Terminal Report")

    response = client.post(
        f"/api/students/{student.id}/payment-codes/{tuition_code['reference_code']}/virtual-account",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["virtual_route"]["account_number"] == "0192837465"
    assert payload["virtual_route"]["bank_name"] == "Paystack-Titan"
    assert payload["virtual_route"]["base_amount"] == 100.0
    assert payload["virtual_route"]["convenience_fee_amount"] == 6.0
    assert payload["virtual_route"]["total_amount"] == 106.0
    assert payload["virtual_route"]["split_code"] == "SPLIT_school001_10000"
    assert payload["virtual_route"]["settlement_mode"] == "paystack_flat_split"
    assert payload["virtual_route"]["school_settlement_amount"] == 100.0
    assert payload["virtual_route"]["platform_settlement_amount"] == 6.0

    intent = PaymentCollectionIntent.query.filter_by(student_id=student.id, reference_code=tuition_code["reference_code"]).first()
    assert intent is not None
    assert intent.provider_customer_code == "CUS_ROUTE_001"
    assert intent.provider_account_number == "0192837465"
    assert intent.meta["split_config"]["split_code"] == "SPLIT_school001_10000"

    assert [call[0] for call in captured] == [
        "/split",
        "/dedicated_account/available_providers",
        "/customer",
        "/dedicated_account",
    ]
    assert captured[0][2]["type"] == "flat"
    assert captured[0][2]["subaccounts"][0]["subaccount"] == "SUB_school001"
    assert captured[0][2]["subaccounts"][0]["share"] == 10000
    assert captured[3][2]["split_code"] == "SPLIT_school001_10000"


def test_student_payment_code_requires_school_settlement_before_tracked_transfer_account(client, app, test_school, test_proprietor, test_students):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.tuition_fee = 100.0
    settings.terminal_report_fee = 0.0
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    student = test_students[0]
    codes_response = client.get(f"/api/students/{student.id}/payment-codes", headers=headers)
    assert codes_response.status_code == 200
    tuition_code = next(item for item in codes_response.get_json()["payment_codes"] if item["fee_type"] == "Tuition + Terminal Report")

    response = client.post(
        f"/api/students/{student.id}/payment-codes/{tuition_code['reference_code']}/virtual-account",
        headers=headers,
        data=json.dumps({}),
    )

    assert response.status_code == 400
    assert "save verified bank details first" in response.get_json()["message"].lower()


def test_paystack_dedicated_virtual_account_webhook_records_student_payment(client, app, test_school, test_proprietor, test_students):
    student = test_students[0]
    student.total_tuition_owed = 500.0
    intent = PaymentCollectionIntent(
        school_id=test_school.id,
        student_id=student.id,
        provider="paystack",
        collection_channel="dedicated_virtual_account",
        intent_status="assigned",
        reference_code=f"{student.student_code}-TUIT",
        payment_type="Tuition",
        payment_category={"fee_type": "Tuition", "term": "Term 1"},
        base_amount=100.0,
        convenience_fee_amount=6.0,
        estimated_provider_fee_amount=3.0,
        platform_fee_amount=3.0,
        total_amount=106.0,
        provider_customer_code="CUS_ROUTE_002",
        provider_dedicated_account_id="915",
        provider_bank_slug="titan-paystack",
        provider_bank_name="Paystack-Titan",
        provider_account_name="EDUPULSE / AMA MENSAH",
        provider_account_number="0192837465",
        provider_subaccount_code="SUB_school001",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        meta={
            "split_config": {
                "split_code": "SPLIT_school001_10000",
                "settlement_mode": "paystack_flat_split",
                "school_settlement_amount": 100.0,
                "platform_settlement_amount": 6.0,
            }
        },
    )
    db.session.add(intent)
    db.session.commit()

    os.environ["PAYSTACK_SECRET_KEY"] = "dva-paystack-secret"
    body = {
        "event": "charge.success",
        "data": {
            "id": 443322,
            "reference": "PS-DVA-443322",
            "amount": 10600,
            "customer": {
                "customer_code": "CUS_ROUTE_002",
            },
            "authorization": {
                "channel": "dedicated_nuban",
                "sender_name": "DANIEL ANYINAM",
                "sender_bank": "Some Bank",
                "receiver_account_number": "0192837465",
            },
        },
    }
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(b"dva-paystack-secret", raw, hashlib.sha512).hexdigest()

    response = client.post(
        "/api/finance/webhook/paystack",
        data=raw,
        headers={"Content-Type": "application/json", "X-Paystack-Signature": signature},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "recorded"
    assert payload["transfer_total_amount"] == 106.0

    payment = Payment.query.filter_by(reference_id="PS-DVA-443322").first()
    assert payment is not None
    assert payment.amount == 100.0
    assert payment.payment_category["transfer_total_amount"] == 106.0
    assert payment.payment_category["convenience_fee_amount"] == 6.0
    assert payment.payment_category["split_code"] == "SPLIT_school001_10000"
    assert payment.payment_category["settlement_mode"] == "paystack_flat_split"
    assert payment.payment_category["school_settlement_amount"] == 100.0
    assert payment.payment_category["platform_settlement_amount"] == 6.0

    db.session.refresh(student)
    assert student.total_tuition_owed == 400.0

    db.session.refresh(intent)
    assert intent.intent_status == "paid"
    assert intent.provider_reference == "PS-DVA-443322"


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

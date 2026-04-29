import io
import json

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import ParentAdmissionApplication, SchoolSettings, Student


def _proprietor_headers(app, school_id, proprietor_id):
    with app.app_context():
        token = create_access_token(identity=str(proprietor_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": school_id,
        "Content-Type": "application/json",
    }


def _submit_parent_application(client, school_id, **overrides):
    payload = {
        "first_name": "Ama",
        "surname": "Boadu",
        "preferred_class": "JHS 1",
        "guardian_name": "Kojo Boadu",
        "parent_email": "ama.parent@example.com",
        "desired_test_mode": "online",
        "internet_quality": "stable",
    }
    payload.update(overrides)
    return client.post(
        f"/api/public/schools/{school_id}/admissions/apply",
        data=payload,
        content_type="multipart/form-data",
    )


@pytest.fixture(autouse=True)
def mock_parent_admission_emails(monkeypatch):
    monkeypatch.setattr("backend.routes.send_email_notification", lambda *args, **kwargs: True)


def test_parent_admission_application_submission_and_status_tracking(client, test_school):
    response = _submit_parent_application(
        client,
        test_school.id,
        documents=(io.BytesIO(b"report content"), "previous-report.pdf"),
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["application"]["status"] == "TestReady"
    assert payload["application"]["ai_recommendation"] == "invite_online_test"

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}"
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["application_code"] == payload["application"]["application_code"]
    assert status_payload["status"] == "TestReady"


def test_public_school_profile_exposes_branding_and_admission_fee(client, db, test_school):
    test_school.logo_url = "https://example.com/logo.png"
    test_school.primary_color = "#0f766e"
    test_school.motto = "Learning with purpose"
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.admission_fee_enabled = True
    settings.admission_fee_amount = 150.0
    db.session.commit()

    response = client.get(f"/api/public/schools/{test_school.id}/profile")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["school_name"] == test_school.name
    assert payload["logo_url"] == test_school.logo_url
    assert payload["theme_color"] == "#0f766e"
    assert payload["admission_fee"]["enabled"] is True
    assert payload["admission_fee"]["amount"] == 150.0


def test_school_can_review_parent_application_and_admit_student(client, app, db, test_school, test_proprietor):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.approval_pdf_enabled = True
    settings.approval_pdf_required_items = "Bring two passport photos\nBring prior report card"
    db.session.commit()

    submit_response = _submit_parent_application(
        client,
        test_school.id,
        first_name="Yaw",
        surname="Mensah",
        preferred_class="JHS 2",
        guardian_name="Esi Mensah",
        parent_phone="+233501111111",
        internet_quality="limited",
        desired_test_mode="in_person",
    )
    application_id = submit_response.get_json()["application"]["id"]

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    list_response = client.get("/api/admissions/applications", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == application_id for item in list_response.get_json()["applications"])

    review_response = client.post(
        f"/api/admissions/applications/{application_id}/review",
        headers=headers,
        data=json.dumps({
            "action": "approve",
            "class_assigned": "JHS 2",
            "notes": "Approved after AI Registrar review.",
        }),
    )
    assert review_response.status_code == 200
    review_payload = review_response.get_json()
    assert review_payload["student_code"]

    application = ParentAdmissionApplication.query.get(application_id)
    assert application.admitted_student_id is not None
    admitted_student = Student.query.get(application.admitted_student_id)
    assert admitted_student is not None
    assert admitted_student.name == "Yaw Mensah"
    assert admitted_student.current_class == "JHS 2"

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}"
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["decision_document"]["available"] is True

    list_after_review_response = client.get("/api/admissions/applications", headers=headers)
    assert list_after_review_response.status_code == 200
    listed_application = next(
        item
        for item in list_after_review_response.get_json()["applications"]
        if item["id"] == application_id
    )
    assert listed_application["decision_document"]["available"] is True
    assert listed_application["decision_document"]["download_url"].endswith(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}/decision-pdf"
    )

    pdf_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}/decision-pdf"
    )
    assert pdf_response.status_code == 200
    assert pdf_response.headers["Content-Type"] == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [
        ("invite_test", "TestReady"),
        ("schedule_visit", "VisitRequired"),
        ("request_correction", "NeedsCorrection"),
        ("reject", "Rejected"),
    ],
)
def test_school_review_actions_update_application_status(
    client, app, test_school, test_proprietor, action, expected_status
):
    submit_response = _submit_parent_application(
        client,
        test_school.id,
        first_name="Efua",
        surname=f"{action.title()} Case",
    )
    payload = submit_response.get_json()
    application_id = payload["application"]["id"]
    status_token = payload["status_token"]

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    review_response = client.post(
        f"/api/admissions/applications/{application_id}/review",
        headers=headers,
        data=json.dumps(
            {
                "action": action,
                "notes": f"Handled with {action}",
            }
        ),
    )

    assert review_response.status_code == 200
    review_payload = review_response.get_json()
    assert review_payload["application"]["status"] == expected_status
    assert review_payload["application"]["reviewer_notes"] == f"Handled with {action}"
    assert "student_code" not in review_payload

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{status_token}"
    )
    assert status_response.status_code == 200
    public_payload = status_response.get_json()
    assert public_payload["status"] == expected_status
    assert public_payload["reviewer_notes"] == f"Handled with {action}"


def test_parent_admission_review_rejects_invalid_action(client, app, test_school, test_proprietor):
    submit_response = _submit_parent_application(client, test_school.id)
    application_id = submit_response.get_json()["application"]["id"]

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    review_response = client.post(
        f"/api/admissions/applications/{application_id}/review",
        headers=headers,
        data=json.dumps({"action": "escalate"}),
    )

    assert review_response.status_code == 400
    assert review_response.get_json()["message"] == "Invalid review action"


def test_payment_codes_expose_stable_payment_identity_for_staff_and_public(client, app, db, test_school, test_proprietor, test_students):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.tuition_fee = 120.0
    settings.terminal_report_fee = 10.0
    settings.admission_fee_enabled = True
    settings.admission_fee_amount = 55.0
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    staff_response = client.get(f"/api/students/{test_students[0].id}/payment-codes", headers=headers)
    assert staff_response.status_code == 200
    staff_payload = staff_response.get_json()
    assert staff_payload["payment_identity"]["model"] == "reference_first"
    assert staff_payload["payment_identity"]["stable_payment_identity"] == test_students[0].student_code
    assert staff_payload["payment_codes"][0]["payment_identity_base"] == test_students[0].student_code
    assert staff_payload["admission_fee"]["enabled"] is True
    assert any(item["fee_type"] == "Admission Fee" for item in staff_payload["payment_codes"])

    public_response = client.get(
        f"/api/public/schools/{test_school.id}/payments/{test_students[0].student_code}"
    )
    assert public_response.status_code == 200
    public_payload = public_response.get_json()
    assert public_payload["payment_identity"]["stable_payment_identity"] == test_students[0].student_code
    assert "parent_email" not in public_payload
    assert public_payload["admission_fee"]["amount"] == 55.0


def test_parent_admission_ocr_enriches_previous_report_scoring(client, test_school, monkeypatch):
    def fake_parse_report_card_image_bytes(image_bytes=None, ocr_text=None, template_config=None):
        return {
            "student_code": "2026001",
            "term": "Term 2",
            "year": "2025/2026",
            "subjects": [
                {"subject": "Mathematics", "total_score": 82.0, "grade": "A"},
                {"subject": "English Language", "total_score": 76.0, "grade": "B"},
                {"subject": "Science", "total_score": 79.0, "grade": "B"},
                {"subject": "History", "total_score": 74.0, "grade": "B"},
                {"subject": "Computing", "total_score": 84.0, "grade": "A"},
            ],
            "term_average": 79.5,
            "overall_performance": 78.0,
            "parse_confidence": 0.93,
        }

    monkeypatch.setattr(
        "backend.routes.parse_report_card_image_bytes",
        fake_parse_report_card_image_bytes,
    )

    response = _submit_parent_application(
        client,
        test_school.id,
        documents=(io.BytesIO(b"fake image bytes"), "previous-report.jpg"),
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["application"]["ai_readiness_score"] >= 90
    assert "OCR extracted 5 subject entries" in payload["application"]["ai_summary"]

    application = ParentAdmissionApplication.query.get(payload["application"]["id"])
    report_entry = next(
        item for item in application.document_manifest if item.get("category") == "previous_report"
    )
    assert report_entry["ocr_status"] == "parsed"
    assert report_entry["ocr_confidence"] == 0.93
    assert report_entry["ocr_subject_count"] == 5
    assert report_entry["ocr_term_average"] == 79.5


def test_parent_admission_ocr_unavailable_sets_flag_without_failing_submission(client, test_school, monkeypatch):
    def fail_parse_report_card_image_bytes(image_bytes=None, ocr_text=None, template_config=None):
        raise RuntimeError("pytesseract and Pillow required for OCR. Install pytesseract pillow.")

    monkeypatch.setattr(
        "backend.routes.parse_report_card_image_bytes",
        fail_parse_report_card_image_bytes,
    )

    response = _submit_parent_application(
        client,
        test_school.id,
        documents=(io.BytesIO(b"fake image bytes"), "previous-report.jpg"),
    )

    assert response.status_code == 201
    payload = response.get_json()

    application = ParentAdmissionApplication.query.get(payload["application"]["id"])
    assert "previous_report_uploaded_but_not_parsed" in (application.ai_flags or [])
    report_entry = next(
        item for item in application.document_manifest if item.get("category") == "previous_report"
    )
    assert report_entry["ocr_status"] == "unavailable"


def test_parent_can_resubmit_missing_documents_and_application_reassesses(client, app, test_school, test_proprietor):
    submit_response = _submit_parent_application(
        client,
        test_school.id,
        parent_email='',
        parent_phone='+233501234567',
        desired_test_mode='either',
        internet_quality='unknown',
    )
    status_token = submit_response.get_json()["status_token"]

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    application_id = submit_response.get_json()["application"]["id"]
    review_response = client.post(
        f"/api/admissions/applications/{application_id}/review",
        headers=headers,
        data=json.dumps({"action": "request_correction", "notes": "Please add an email and a report card."}),
    )
    assert review_response.status_code == 200

    resubmit_response = client.post(
        f"/api/public/schools/{test_school.id}/admissions/status/{status_token}/resubmit",
        data={
            "guardian_name": "Kojo Boadu",
            "parent_email": "ama.parent@example.com",
            "parent_phone": "+233501234567",
            "preferred_class": "JHS 1",
            "desired_test_mode": "online",
            "internet_quality": "stable",
            "parent_notes": "Added the missing report card and email.",
            "documents": (io.BytesIO(b"updated report"), "previous-report.jpg"),
        },
        content_type="multipart/form-data",
    )
    assert resubmit_response.status_code == 200
    payload = resubmit_response.get_json()
    assert payload["application"]["status"] in {"TestReady", "ReviewReady"}

    application = ParentAdmissionApplication.query.get(application_id)
    assert application.parent_email == "ama.parent@example.com"
    assert any(item.get("submitted_in_correction") for item in (application.document_manifest or []))


def test_decision_pdf_is_not_available_for_rejected_application(client, app, test_school, test_proprietor, db):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.approval_pdf_enabled = True
    db.session.commit()

    submit_response = _submit_parent_application(client, test_school.id)
    payload = submit_response.get_json()
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    review_response = client.post(
        f"/api/admissions/applications/{payload['application']['id']}/review",
        headers=headers,
        data=json.dumps({"action": "reject", "notes": "Not approved."}),
    )
    assert review_response.status_code == 200

    pdf_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}/decision-pdf"
    )
    assert pdf_response.status_code == 409


def test_decision_pdf_requires_paid_subscription_ai_registrar_access(client, app, test_school, test_proprietor, db):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    test_school.subscription_plan = "Free Tier"
    settings.approval_pdf_enabled = True
    db.session.commit()

    submit_response = _submit_parent_application(client, test_school.id)
    payload = submit_response.get_json()
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    review_response = client.post(
        f"/api/admissions/applications/{payload['application']['id']}/review",
        headers=headers,
        data=json.dumps({"action": "approve", "class_assigned": "JHS 1", "notes": "Approved."}),
    )
    assert review_response.status_code == 200

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}"
    )
    assert status_response.status_code == 200
    assert "decision_document" not in status_response.get_json()

    pdf_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}/decision-pdf"
    )
    assert pdf_response.status_code == 403
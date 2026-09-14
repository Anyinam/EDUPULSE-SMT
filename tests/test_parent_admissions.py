import io
import json
import hashlib
import hmac

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import AcademicClass, ParentAdmissionApplication, SchoolSettings, Student


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
        "consent_confirmed": "true",
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
    assert payload["consent_recorded"] is True

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}"
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["application_code"] == payload["application"]["application_code"]
    assert status_payload["status"] == "TestReady"


def test_parent_admission_fee_payment_initializes_from_public_status_token(client, db, test_school, monkeypatch):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.admission_fee_enabled = True
    settings.admission_fee_amount = 175.0
    db.session.commit()

    submit_response = _submit_parent_application(client, test_school.id)
    submit_payload = submit_response.get_json()
    captured = {}

    def fake_call_paystack_api(endpoint, method="GET", data=None):
        captured["endpoint"] = endpoint
        captured["method"] = method
        captured["data"] = data
        return {
            "authorization_url": "https://paystack.test/checkout/admission",
            "access_code": "ACCESS123",
        }, None

    monkeypatch.setattr("backend.routes._call_paystack_api", fake_call_paystack_api)

    response = client.post(
        f"/api/public/schools/{test_school.id}/admissions/status/{submit_payload['status_token']}/initialize-payment"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["authorization_url"] == "https://paystack.test/checkout/admission"
    assert payload["payment_summary"]["status"] == "initiated"
    assert captured["endpoint"] == "/transaction/initialize"
    assert captured["data"]["metadata"]["transaction_type"] == "parent_admission_fee"
    assert captured["data"]["metadata"]["application_code"] == submit_payload["application"]["application_code"]


def test_parent_admission_fee_webhook_marks_application_paid(client, db, test_school, monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "paystack-test-secret")
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.admission_fee_enabled = True
    settings.admission_fee_amount = 175.0
    db.session.commit()

    submit_response = _submit_parent_application(client, test_school.id)
    submit_payload = submit_response.get_json()
    application = ParentAdmissionApplication.query.get(submit_payload["application"]["id"])

    body = {
        "event": "charge.success",
        "data": {
            "id": 998877,
            "reference": "PADM-TEST-1234",
            "amount": 17500,
            "paid_at": "2026-09-05T12:00:00+00:00",
            "metadata": {
                "transaction_type": "parent_admission_fee",
                "school_id": test_school.id,
                "parent_admission_application_id": application.id,
                "application_code": application.application_code,
                "status_token": application.status_token,
            },
        },
    }
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(b"paystack-test-secret", raw, hashlib.sha512).hexdigest()

    response = client.post(
        "/api/finance/webhook/paystack",
        data=raw,
        headers={"Content-Type": "application/json", "X-Paystack-Signature": signature},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "recorded"

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}"
    )
    assert status_response.status_code == 200
    payment_summary = status_response.get_json()["payment_summary"]
    assert payment_summary["status"] == "paid"
    assert payment_summary["reference"] == "PADM-TEST-1234"


def test_parent_admission_review_preserves_payment_summary(client, app, db, test_school, test_proprietor):
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).first()
    settings.admission_fee_enabled = True
    settings.admission_fee_amount = 150.0
    db.session.commit()

    submit_response = _submit_parent_application(client, test_school.id)
    payload = submit_response.get_json()
    application = ParentAdmissionApplication.query.get(payload["application"]["id"])

    from backend.routes import _get_school_admission_fee_config, _normalize_parent_admission_payment_summary, _set_parent_admission_payment_summary

    _set_parent_admission_payment_summary(
        application,
        _normalize_parent_admission_payment_summary(
            {"status": "initiated", "reference": "PADM-INIT-1111", "amount": 150.0},
            fee_config=_get_school_admission_fee_config(settings),
        ),
    )
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    review_response = client.post(
        f"/api/admissions/applications/{application.id}/review",
        headers=headers,
        data=json.dumps({"action": "invite_test", "notes": "Proceed to online test."}),
    )

    assert review_response.status_code == 200
    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}"
    )
    assert status_response.status_code == 200
    payment_summary = status_response.get_json()["payment_summary"]
    assert payment_summary["status"] == "initiated"
    assert payment_summary["reference"] == "PADM-INIT-1111"


def test_parent_admission_accepts_more_than_two_supporting_documents(client, test_school):
    response = _submit_parent_application(
        client,
        test_school.id,
        documents=[
            (io.BytesIO(b"report content"), "previous-report.pdf"),
            (io.BytesIO(b"birth certificate"), "birth-certificate.pdf"),
            (io.BytesIO(b"guardian id"), "guardian-id.jpg"),
        ],
    )

    assert response.status_code == 201
    payload = response.get_json()

    application = ParentAdmissionApplication.query.get(payload["application"]["id"])
    assert len(application.document_manifest or []) == 3
    assert {item.get("filename") for item in (application.document_manifest or [])} == {
        "previous-report.pdf",
        "birth-certificate.pdf",
        "guardian-id.jpg",
    }


def test_parent_admission_requires_guardian_consent_confirmation(client, test_school):
    response = _submit_parent_application(
        client,
        test_school.id,
        consent_confirmed="false",
    )

    assert response.status_code == 400
    assert "consent" in response.get_json()["message"].lower()


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


def test_public_school_classes_use_school_defined_or_student_classes(client, db, test_school):
    academic_class = AcademicClass(
        school_id=test_school.id,
        name="Creche A",
    )
    db.session.add(academic_class)
    db.session.commit()

    response = client.get(f"/api/public/schools/{test_school.id}/classes")

    assert response.status_code == 200
    assert response.get_json() == [
        {"id": academic_class.id, "name": "Creche A", "class_name": "Creche A"}
    ]


def test_parent_admission_accepts_school_defined_class_names(client, db, test_school):
    db.session.add(AcademicClass(school_id=test_school.id, name="Creche A"))
    db.session.commit()

    response = _submit_parent_application(
        client,
        test_school.id,
        preferred_class="Creche A",
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["application"]["preferred_class"] == "Creche A"


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


def test_payment_codes_expose_stable_payment_identity_for_staff_only(client, app, db, test_school, test_proprietor, test_students):
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
    assert staff_payload["admission_fee"]["amount"] == 55.0
    assert not any(item["fee_type"] == "Admission Fee" for item in staff_payload["payment_codes"])

    public_response = client.get(
        f"/api/public/schools/{test_school.id}/payments/{test_students[0].student_code}"
    )
    assert public_response.status_code == 404


def test_payment_codes_blocked_when_free_tier_school_is_over_capacity(client, app, db, test_school, test_proprietor, test_students):
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = None
    test_school.trial_end_date = None

    current_count = Student.query.filter_by(school_id=test_school.id).count()
    for index in range(current_count + 1, 52):
        db.session.add(
            Student(
                school_id=test_school.id,
                first_name=f"Cap{index}",
                surname="Student",
                name=f"Cap{index} Student",
                student_code=f"CAP{index:03d}",
                current_class="JHS 1",
                status="Active",
                total_tuition_owed=100.0,
            )
        )
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    staff_response = client.get(f"/api/students/{test_students[0].id}/payment-codes", headers=headers)
    assert staff_response.status_code == 409
    staff_payload = staff_response.get_json()
    assert staff_payload["error"] == "payment_collection_blocked"
    assert staff_payload["reason"] == "plan_over_capacity"

    public_response = client.get(
        f"/api/public/schools/{test_school.id}/payments/{test_students[0].student_code}"
    )
    assert public_response.status_code == 404


def test_payment_codes_blocked_until_school_verification_is_complete(client, app, db, test_school, test_proprietor, test_students):
    from backend.api.models import SchoolVerification

    SchoolVerification.query.filter_by(school_id=test_school.id).delete()
    db.session.commit()

    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)
    response = client.get(f"/api/students/{test_students[0].id}/payment-codes", headers=headers)

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["error"] == "school_verification_required"


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


def test_school_visit_plan_is_exposed_to_staff_and_parent_status(client, app, test_school, test_proprietor):
    submit_response = _submit_parent_application(
        client,
        test_school.id,
        desired_test_mode="in_person",
        internet_quality="limited",
    )
    payload = submit_response.get_json()
    headers = _proprietor_headers(app, test_school.id, test_proprietor.id)

    review_response = client.post(
        f"/api/admissions/applications/{payload['application']['id']}/review",
        headers=headers,
        data=json.dumps(
            {
                "action": "schedule_visit",
                "notes": "Please arrive 15 minutes early and bring the learner.",
                "visit_date": "2026-05-04",
                "visit_time": "09:30",
                "visit_location": "Admissions Office",
                "visit_contact_person": "Mrs. Asante",
                "visit_contact_phone": "+233501234567",
            }
        ),
    )

    assert review_response.status_code == 200
    review_payload = review_response.get_json()
    assert review_payload["application"]["status"] == "VisitRequired"
    assert review_payload["application"]["reviewer_notes"] == "Please arrive 15 minutes early and bring the learner."
    assert review_payload["application"]["follow_up_plan"]["type"] == "school_visit"
    assert review_payload["application"]["follow_up_plan"]["date"] == "2026-05-04"
    assert review_payload["application"]["follow_up_plan"]["location"] == "Admissions Office"
    assert "Please visit" in review_payload["application"]["parent_response_message"]

    status_response = client.get(
        f"/api/public/schools/{test_school.id}/admissions/status/{payload['status_token']}"
    )
    assert status_response.status_code == 200
    status_payload = status_response.get_json()
    assert status_payload["follow_up_plan"]["contact_person"] == "Mrs. Asante"
    assert status_payload["follow_up_plan"]["contact_phone"] == "+233501234567"
    assert status_payload["reviewer_notes"] == "Please arrive 15 minutes early and bring the learner."


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
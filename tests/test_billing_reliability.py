import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from copy import deepcopy

import pytest
from flask_jwt_extended import create_access_token

from backend.middleware import get_billing_status_info


@pytest.fixture()
def proprietor_headers(app, test_school, test_proprietor):
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": test_school.id,
        "Content-Type": "application/json",
    }


def test_paystack_verify_idempotent(client, app, db, test_school, test_proprietor, proprietor_headers, monkeypatch):
    from backend.api.models import add_ledger_entry

    reference = "PSK-VERIFY-001"

    def fake_verify_payment(ref):
        return {
            "status": "success",
            "amount": 25000,
            "reference": ref,
            "metadata": {
                "plan_name": "Basic",
                "school_id": test_school.id,
            },
            "authorization": {
                "reusable": True,
                "authorization_code": "AUTH_test_001",
                "last4": "4242",
                "brand": "visa",
                "bank": "TEST",
                "signature": "sig-001",
            },
            "customer": {"email": test_proprietor.email},
        }

    def fake_process_payment_confirmation(school_id, plan_name, amount_paid_cedis, reference=None, metadata=None):
        add_ledger_entry(
            school_id=school_id,
            tx_type="subscription",
            tx_ref=reference,
            amount=float(amount_paid_cedis),
            source="paystack",
            metadata={"status": "Completed", "plan_name": plan_name},
        )
        db.session.commit()
        return {
            "plan_name": plan_name,
            "amount": amount_paid_cedis,
            "reference": reference,
        }

    monkeypatch.setattr("backend.paystack_integration.verify_payment", fake_verify_payment)
    monkeypatch.setattr(
        "backend.paystack_integration.process_payment_confirmation",
        fake_process_payment_confirmation,
    )

    first = client.get(f"/api/paystack/verify/{reference}", headers=proprietor_headers)
    assert first.status_code == 200
    first_data = first.get_json()
    assert first_data["status"] == "success"

    second = client.get(f"/api/paystack/verify/{reference}", headers=proprietor_headers)
    assert second.status_code == 200
    second_data = second.get_json()
    assert second_data["status"] == "success"
    assert second_data["data"].get("idempotent") is True


def test_card_management_flow(client, db, test_school, proprietor_headers):
    from backend.api.models import PlatformSetting

    setting = PlatformSetting(
        setting_key=f"auto_billing:{test_school.id}",
        setting_value={
            "enabled": True,
            "cards": [
                {
                    "card_id": "card-1",
                    "authorization_code": "AUTH_A",
                    "last4": "1111",
                    "brand": "visa",
                    "bank": "BANK-A",
                    "customer_email": "owner@test.edu",
                    "is_default": True,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "card_id": "card-2",
                    "authorization_code": "AUTH_B",
                    "last4": "2222",
                    "brand": "mastercard",
                    "bank": "BANK-B",
                    "customer_email": "owner@test.edu",
                    "is_default": False,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            ],
        },
    )
    db.session.add(setting)
    db.session.commit()

    listed = client.get("/api/school/subscription/cards", headers=proprietor_headers)
    assert listed.status_code == 200
    listed_payload = listed.get_json()
    assert listed_payload["cards_count"] == 2
    target_card_id = listed_payload["cards"][1]["card_id"]

    updated = client.post(
        "/api/school/subscription/cards/default",
        data=json.dumps({"card_id": target_card_id}),
        headers=proprietor_headers,
    )
    assert updated.status_code == 200
    updated_payload = updated.get_json()
    assert updated_payload["default_card_id"] == target_card_id
    assert any(c["card_id"] == target_card_id and c.get("is_default") for c in updated_payload["cards"])

    remove_card_id = listed_payload["cards"][0]["card_id"]
    removed = client.delete(f"/api/school/subscription/cards/{remove_card_id}", headers=proprietor_headers)
    assert removed.status_code == 200
    assert len(removed.get_json()["cards"]) == 1

    unsubscribed = client.post(
        "/api/school/subscription/auto-billing/unsubscribe",
        data=json.dumps({}),
        headers=proprietor_headers,
    )
    assert unsubscribed.status_code == 200
    assert unsubscribed.get_json()["enabled"] is False


def test_overdue_transition_and_restricted_write_access(client, db, test_school, proprietor_headers):
    test_school.subscription_plan = "Basic"
    test_school.next_billing_date = datetime.now(timezone.utc) - timedelta(days=10)
    test_school.subscription_status = "Active"
    db.session.commit()

    status_info = get_billing_status_info(test_school)
    assert status_info["status"] == "Overdue"

    # Overdue schools still have read-only access.
    readonly = client.get("/api/school/fees", headers=proprietor_headers)
    assert readonly.status_code in [200, 404]

    # Overdue schools cannot perform write operations on protected business routes.
    blocked = client.post(
        "/api/school/fees",
        data=json.dumps({"tuition_fee": 100}),
        headers=proprietor_headers,
    )
    assert blocked.status_code == 402
    payload = blocked.get_json()
    assert payload["error"] == "billing_restriction"


def test_paystack_webhook_duplicate_event_protection(client, db, test_school, monkeypatch):
    from backend.api.models import add_ledger_entry

    secret = "test-secret-paystack"
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", secret)

    call_counter = {"count": 0}

    def fake_process_payment_confirmation(school_id, plan_name, amount_paid_cedis, reference=None, metadata=None):
        call_counter["count"] += 1
        add_ledger_entry(
            school_id=school_id,
            tx_type="subscription",
            tx_ref=reference,
            amount=float(amount_paid_cedis),
            source="paystack",
            metadata={"status": "Completed", "plan_name": plan_name},
        )
        db.session.commit()
        return {"status": "success", "reference": reference}

    monkeypatch.setattr(
        "backend.paystack_integration.process_payment_confirmation",
        fake_process_payment_confirmation,
    )

    payload = {
        "event": "charge.success",
        "data": {
            "reference": "PSK-WEBHOOK-001",
            "status": "success",
            "amount": 30000,
            "metadata": {
                "school_id": test_school.id,
                "plan_name": "Basic",
            },
            "customer": {"email": "proprietor@test.edu"},
            "authorization": {
                "reusable": True,
                "authorization_code": "AUTH_webhook",
                "signature": "sig-webhook",
                "last4": "1234",
                "brand": "visa",
            },
        },
    }

    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()

    first = client.post(
        "/api/paystack/webhook",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Paystack-Signature": signature,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/api/paystack/webhook",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Paystack-Signature": signature,
        },
    )
    assert second.status_code == 200
    assert call_counter["count"] == 1


def test_bank_webhook_requires_valid_signature(client, db, test_school, monkeypatch):
    from backend.api.models import Student

    monkeypatch.setenv("BANK_WEBHOOK_SECRET", "test-bank-webhook-secret-0123456789")

    student = Student(
        school_id=test_school.id,
        first_name="Kwame",
        surname="Boateng",
        name="Kwame Boateng",
        student_code="BANK001",
        current_class="JHS 1",
        total_tuition_owed=250.0,
    )
    db.session.add(student)
    db.session.commit()

    payload = {
        "status": "success",
        "reference": "BANK001-TUITION-T1",
        "amount": 50.0,
        "transaction_id": "BANK-WEBHOOK-REJECT-001",
        "payer_name": "Parent One",
    }

    raw = json.dumps(payload).encode("utf-8")

    missing = client.post(
        "/api/finance/webhook/bank",
        data=raw,
        headers={"Content-Type": "application/json"},
    )
    assert missing.status_code == 401
    assert missing.get_json()["message"] == "Missing bank webhook signature"

    invalid = client.post(
        "/api/finance/webhook/bank",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Bank-Signature": "bad-signature",
        },
    )
    assert invalid.status_code == 401
    assert invalid.get_json()["message"] == "Invalid bank webhook signature"


def test_bank_webhook_records_payment_with_valid_signature(client, db, test_school, monkeypatch):
    from backend.api.models import Payment, Student

    secret = "test-bank-webhook-secret-0123456789"
    monkeypatch.setenv("BANK_WEBHOOK_SECRET", secret)

    student = Student(
        school_id=test_school.id,
        first_name="Ama",
        surname="Mensah",
        name="Ama Mensah",
        student_code="BANK002",
        current_class="JHS 2",
        total_tuition_owed=300.0,
    )
    db.session.add(student)
    db.session.commit()

    payload = {
        "status": "success",
        "reference": "BANK002-TUITION-T1",
        "amount": 120.0,
        "transaction_id": "BANK-WEBHOOK-OK-001",
        "payer_name": "Parent Two",
    }

    raw = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/finance/webhook/bank",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Bank-Signature": signature,
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "recorded"
    assert body["payment_type"] == "Tuition"

    payment = Payment.query.filter_by(reference_id="BANK-WEBHOOK-OK-001").first()
    assert payment is not None
    assert payment.method == "Bank_Auto"

    db.session.refresh(student)
    assert student.total_tuition_owed == 180.0


def test_billing_timeline_and_statement_endpoints(client, db, test_school, proprietor_headers):
    from backend.api.models import add_ledger_entry

    add_ledger_entry(
        school_id=test_school.id,
        tx_type="subscription",
        tx_ref="STMT-001",
        amount=120.0,
        source="paystack",
        metadata={"status": "Completed", "plan_name": "Basic"},
    )
    db.session.commit()

    timeline = client.get("/api/school/subscription/billing-timeline", headers=proprietor_headers)
    assert timeline.status_code == 200
    assert "events" in timeline.get_json()

    recon = client.get("/api/school/subscription/ledger/reconciliation", headers=proprietor_headers)
    assert recon.status_code == 200
    recon_payload = recon.get_json()
    assert "chain_check" in recon_payload

    statement = client.get("/api/school/subscription/statement/download?format=csv", headers=proprietor_headers)
    assert statement.status_code == 200
    assert statement.headers.get("Content-Type", "").startswith("text/csv")
    assert b"tx_ref" in statement.data


def test_paystack_reconciliation_recovers_finance_payment_after_injected_failure(
    client,
    db,
    test_school,
    test_proprietor,
    proprietor_headers,
    monkeypatch,
):
    from backend.api.models import Payment, Student

    secret = "test-secret-paystack"
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", secret)

    student = Student(
        school_id=test_school.id,
        first_name="Ama",
        surname="Owusu",
        name="Ama Owusu",
        student_code="SREC001",
        current_class="JHS 1",
        total_tuition_owed=50.0,
    )
    db.session.add(student)
    db.session.commit()

    webhook_payload = {
        "event": "charge.success",
        "data": {
            "id": 9001,
            "reference": "PAY-REC-FIN-001",
            "status": "success",
            "amount": 5000,
            "channel": "mobile_money",
            "metadata": {
                "school_id": test_school.id,
                "student_id": student.id,
                "payment_type": "Tuition",
                "__failpoint__": "finance_payment_before_commit",
            },
            "customer": {"email": test_proprietor.email},
            "authorization": {"reusable": False},
        },
    }

    raw = json.dumps(webhook_payload).encode("utf-8")
    signature = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()

    failed = client.post(
        "/api/finance/webhook/paystack",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Paystack-Signature": signature,
        },
    )
    assert failed.status_code == 500
    assert Payment.query.filter_by(reference_id="PAY-REC-FIN-001").first() is None

    recovered_transaction = deepcopy(webhook_payload["data"])
    recovered_transaction["metadata"].pop("__failpoint__", None)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": True, "data": [recovered_transaction], "meta": {}}

    monkeypatch.setattr("backend.routes.requests.get", lambda *args, **kwargs: FakeResponse())

    recovery = client.post(
        "/api/school/subscription/ledger/reconciliation/recover",
        headers=proprietor_headers,
        data=json.dumps({"lookback_hours": 24}),
    )
    assert recovery.status_code == 200
    summary = recovery.get_json()
    assert summary["recovered"] == 1
    assert "PAY-REC-FIN-001" in summary["references"]

    payment = Payment.query.filter_by(reference_id="PAY-REC-FIN-001").first()
    assert payment is not None
    db.session.refresh(student)
    assert student.total_tuition_owed == 0.0


def test_paystack_reconciliation_recovers_subscription_after_injected_failure(
    client,
    app,
    db,
    test_school,
    test_proprietor,
    proprietor_headers,
    monkeypatch,
):
    from backend.api.models import LedgerEntry

    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "test-secret-paystack")

    transaction = {
        "status": "success",
        "reference": "PAY-REC-SUB-001",
        "amount": 36000,
        "metadata": {
            "school_id": test_school.id,
            "plan_name": "Basic",
            "billing_period": "term",
            "terms": 1,
            "student_count": 10,
            "__failpoint__": "subscription_payment_before_commit",
        },
        "customer": {"email": test_proprietor.email},
        "authorization": {"reusable": True, "authorization_code": "AUTH_REC_001", "signature": "sig-rec-001", "last4": "7788", "brand": "visa", "bank": "TEST"},
    }

    monkeypatch.setattr("backend.paystack_integration.verify_payment", lambda reference: deepcopy(transaction))

    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))

    verify_response = client.get(
        "/api/paystack/verify/PAY-REC-SUB-001",
        headers={"Authorization": f"Bearer {token}", "X-School-ID": test_school.id},
    )
    assert verify_response.status_code == 500
    assert LedgerEntry.query.filter_by(tx_ref="PAY-REC-SUB-001").first() is None

    recovered_transaction = deepcopy(transaction)
    recovered_transaction["metadata"].pop("__failpoint__", None)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": True, "data": [recovered_transaction], "meta": {}}

    monkeypatch.setattr("backend.routes.requests.get", lambda *args, **kwargs: FakeResponse())

    recovery = client.post(
        "/api/school/subscription/ledger/reconciliation/recover",
        headers=proprietor_headers,
        data=json.dumps({"lookback_hours": 24}),
    )
    assert recovery.status_code == 200
    summary = recovery.get_json()
    assert summary["recovered"] == 1
    assert "PAY-REC-SUB-001" in summary["references"]

    db.session.refresh(test_school)
    assert test_school.subscription_plan == "Basic"
    assert LedgerEntry.query.filter_by(tx_ref="PAY-REC-SUB-001").first() is not None


def test_admission_blocks_when_actual_active_count_hits_limit_even_if_meter_is_stale(
    client,
    db,
    test_school,
    proprietor_headers,
    monkeypatch,
):
    from backend.api.models import Student

    monkeypatch.setattr("backend.routes.get_plan_limits", lambda _plan_name: 25)

    for index in range(25):
        db.session.add(
            Student(
                school_id=test_school.id,
                first_name=f"Existing{index}",
                surname="Student",
                name=f"Existing{index} Student",
                student_code=f"EXIST{index:03d}",
                current_class="JHS 1",
                status="Active",
            )
        )
    test_school.current_student_count = 24
    db.session.commit()

    response = client.post(
        "/api/admissions/admit",
        headers=proprietor_headers,
        data=json.dumps(
            {
                "first_name": "Late",
                "surname": "Applicant",
                "class_assigned": "JHS 1",
                "score": 84,
            }
        ),
    )

    assert response.status_code == 403
    assert "Plan limit of 25 students reached" in response.get_json()["message"]


def test_prorated_admission_charge_uses_fixed_120_days(client, app, db, test_school, test_proprietor):
    from datetime import date

    from backend.api.models import AcademicTerm, LedgerEntry, Student
    from backend.routes import calculate_prorated_admission_charge

    with app.app_context():
        today = date.today()
        term = AcademicTerm(
            school_id=test_school.id,
            name="Term 1",
            academic_year="2025/2026",
            start_date=today - timedelta(days=60),
            end_date=today + timedelta(days=60),
            is_active=True,
            created_by=test_proprietor.id,
        )
        db.session.add(term)

        # Ensure exactly 30 active students so the 31st triggers overage.
        existing = Student.query.filter_by(school_id=test_school.id, status="Active").count()
        to_add = max(0, 30 - existing)
        for idx in range(to_add):
            db.session.add(
                Student(
                    school_id=test_school.id,
                    first_name=f"Extra{idx}",
                    surname="Test",
                    name=f"Extra {idx}",
                    student_code=f"EX{idx:04d}",
                    current_class="JHS 1",
                )
            )
        db.session.commit()

        result = calculate_prorated_admission_charge(test_school, 1, "Basic")
        assert result["prorated_charge"] > 0

        entry = (
            LedgerEntry.query.filter_by(school_id=test_school.id, tx_type="subscription_prorated")
            .order_by(LedgerEntry.id.desc())
            .first()
        )
        assert entry is not None
        meta = entry.meta or {}
        assert meta.get("status") == "Pending"
        assert meta.get("days_in_term") == 121

        # remaining_days = 61 (inclusive) when end_date = today+60
        days_in_term = meta.get("days_in_term")
        expected = round((61 / float(days_in_term)) * 12, 2)
        assert entry.amount == expected


def test_prorated_admission_charge_uses_actual_term_length(client, app, db, test_school, test_proprietor):
    from datetime import date

    from backend.api.models import AcademicTerm, LedgerEntry, Student
    from backend.routes import calculate_prorated_admission_charge

    with app.app_context():
        today = date.today()
        term = AcademicTerm(
            school_id=test_school.id,
            name="Term 1",
            academic_year="2025/2026",
            start_date=today - timedelta(days=45),
            end_date=today + timedelta(days=75),
            is_active=True,
            created_by=test_proprietor.id,
        )
        db.session.add(term)

        # Set exactly 30 students so first overage scenario can be checked
        existing = Student.query.filter_by(school_id=test_school.id, status="Active").count()
        to_add = max(0, 30 - existing)
        for idx in range(to_add):
            db.session.add(
                Student(
                    school_id=test_school.id,
                    first_name=f"Extra{idx}",
                    surname="Test",
                    name=f"Extra {idx}",
                    student_code=f"EX{idx:04d}",
                    current_class="JHS 1",
                )
            )
        db.session.commit()

        result = calculate_prorated_admission_charge(test_school, 1, "Premium")
        assert result["prorated_charge"] > 0

        # verify days_in_term is taken from actual term dates not fixed 120
        entry = (
            LedgerEntry.query.filter_by(school_id=test_school.id, tx_type="subscription_prorated")
            .order_by(LedgerEntry.id.desc())
            .first()
        )
        assert entry is not None
        meta = entry.meta or {}
        assert meta.get("days_in_term") == 121


def test_profile_has_two_factor_status(client, app, db, test_school, test_proprietor, proprietor_headers):
    response = client.get("/api/profile", headers=proprietor_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert "two_fa_enabled" in data
    assert "two_fa_method" in data
    assert "mfa_required" in data


def test_school_fees_uniform_status_is_zero(client, app, db, test_school, test_proprietor, proprietor_headers):
    response = client.get("/api/school/fees", headers=proprietor_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("uniform_fee") == 0.0


def test_staff_add_includes_email_sent_fallback(client, app, db, test_school, test_proprietor, proprietor_headers, monkeypatch):
    def fake_email(*args, **kwargs):
        raise Exception("SMTP connection failed")

    monkeypatch.setattr("backend.routes.send_email_notification", fake_email)

    payload = {
        "username": "teacher_x",
        "email": "teacherx@example.com",
        "role": "teacher"
    }
    response = client.post("/api/staff/add", json=payload, headers=proprietor_headers)
    assert response.status_code == 200
    result = response.get_json()
    assert result.get("email_sent") is False
    assert "Failed to send welcome email" in result.get("message", "")


def test_staff_add_welcome_email_includes_school_id_and_support_details(
    client, app, db, test_school, test_proprietor, proprietor_headers, monkeypatch
):
    captured = {}

    def fake_email(recipient, subject, body):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["body"] = body
        return True

    monkeypatch.setattr("backend.routes.send_email_notification", fake_email)

    payload = {
        "username": "teacher_mail",
        "email": "teachermail@example.com",
        "role": "teacher"
    }
    headers = {**proprietor_headers, "Origin": "https://school.edupulse.test"}
    response = client.post("/api/staff/add", json=payload, headers=headers)

    assert response.status_code == 200
    assert captured["recipient"] == payload["email"]
    assert test_school.id in captured["body"]
    assert "Organization ID" in captured["body"]
    assert "School Support" in captured["body"]
    assert "school.edupulse.test/login" in captured["body"]
    assert "Record subject scores" in captured["body"]
    assert "{{school_id}}" not in captured["body"]


def test_staff_add_rejects_duplicate_email_in_same_school(
    client, app, db, test_school, test_proprietor, proprietor_headers
):
    from backend.api.models import User

    existing_staff = User(
        username="anyinam111",
        school_id=test_school.id,
        role="teacher",
        roles=["teacher"],
        email="DaniYinam11@gmail.com",
    )
    existing_staff.set_password("ExistingPass123")
    db.session.add(existing_staff)
    db.session.commit()

    payload = {
        "username": "daniel2",
        "email": "  daniyinam11@gmail.com  ",
        "role": "teacher",
    }

    response = client.post("/api/staff/add", json=payload, headers=proprietor_headers)

    assert response.status_code == 400
    assert response.get_json()["message"] == "Email address is already assigned to another staff member in this school."


def test_resend_staff_invite_rotates_temp_password_and_sends_email(
    client, app, db, test_school, test_proprietor, proprietor_headers, monkeypatch
):
    from backend.api.models import User

    staff = User(
        username="teacher_resend",
        school_id=test_school.id,
        role="teacher",
        roles=["teacher"],
        email="teacherresend@example.com",
        is_temp_password=False,
    )
    staff.set_password("ExistingPass123")
    db.session.add(staff)
    db.session.commit()

    old_hash = staff.password_hash
    captured = {}

    def fake_email(recipient, subject, body):
        captured["recipient"] = recipient
        captured["subject"] = subject
        captured["body"] = body
        return True

    monkeypatch.setattr("backend.routes.send_email_notification", fake_email)

    headers = {**proprietor_headers, "Origin": "https://school.edupulse.test"}
    response = client.post(f"/api/staff/{staff.id}/resend-invite", json={}, headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["email_sent"] is True

    refreshed = User.query.get(staff.id)
    assert refreshed.is_temp_password is True
    assert refreshed.password_hash != old_hash
    assert refreshed.temp_password_expires_at is not None
    assert captured["recipient"] == staff.email
    assert test_school.id in captured["body"]
    assert "Temporary Password" in captured["body"]


def test_overage_auto_charge_creates_settlement_entry(client, app, db, test_school, monkeypatch):
    from datetime import date

    from backend.api.models import LedgerEntry, PlatformSetting
    from backend.overage_billing_job import process_pending_overage_invoices, SETTLEMENT_TYPE
    from backend.api.models import add_ledger_entry

    with app.app_context():
        db.session.add(
            PlatformSetting(
                setting_key=f"auto_billing:{test_school.id}",
                setting_value={
                    "enabled": True,
                    "cards": [
                        {
                            "card_id": "card-1",
                            "authorization_code": "AUTH_TEST",
                            "customer_email": "owner@test.edu",
                            "is_default": True,
                            "added_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                },
            )
        )
        db.session.commit()

        invoice_ref = "PRO-TEST-INV-001"
        add_ledger_entry(
            school_id=test_school.id,
            tx_type="subscription_prorated",
            tx_ref=invoice_ref,
            amount=25.0,
            source="system",
            metadata={
                "status": "Pending",
                "kind": "admission_overage_proration",
                "due_date": (date.today() - timedelta(days=1)).isoformat(),
            },
        )
        db.session.commit()

        def fake_charge_authorization(email, amount_cents, authorization_code, metadata=None):
            assert email
            assert amount_cents == 2500
            assert authorization_code == "AUTH_TEST"
            return {
                "status": "success",
                "reference": "PSK-CHG-001",
                "authorization": {"last4": "4242"},
            }

        monkeypatch.setattr("backend.paystack_integration.charge_authorization", fake_charge_authorization)

        result = process_pending_overage_invoices(now=datetime.now(timezone.utc))
        assert result["charged"] == 1

        settlement = (
            LedgerEntry.query.filter_by(school_id=test_school.id, tx_type=SETTLEMENT_TYPE)
            .order_by(LedgerEntry.id.desc())
            .first()
        )
        assert settlement is not None
        assert (settlement.meta or {}).get("invoice_tx_ref") == invoice_ref

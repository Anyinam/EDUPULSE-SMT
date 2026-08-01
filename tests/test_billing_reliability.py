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


def test_paystack_initialize_prorates_post_trial_free_tier_conversion(
    client, app, db, test_school, test_proprietor, proprietor_headers, monkeypatch
):
    from datetime import date

    from backend.api.models import AcademicTerm, Student

    today = date.today()
    term = AcademicTerm(
        school_id=test_school.id,
        name="Term 3",
        academic_year="2025/2026",
        start_date=today - timedelta(days=44),
        end_date=today + timedelta(days=15),
        is_active=True,
        created_by=test_proprietor.id,
    )
    db.session.add(term)

    existing = Student.query.filter_by(school_id=test_school.id, status="Active").count()
    to_add = max(0, 35 - existing)
    for idx in range(to_add):
        db.session.add(
            Student(
                school_id=test_school.id,
                first_name=f"Paid{idx}",
                surname="Student",
                name=f"Paid Student {idx}",
                student_code=f"PD{idx:04d}",
                current_class="JHS 1",
                status="Active",
            )
        )

    test_school.subscription_plan = "Free Tier"
    test_school.subscription_status = "Active"
    test_school.next_billing_date = None
    test_school.trial_plan = None
    test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    test_school.is_trial_active = False
    db.session.commit()

    captured = {}

    def fake_initialize_payment(email, amount_cents, plan_name, school_id, metadata=None):
        captured["email"] = email
        captured["amount_cents"] = amount_cents
        captured["plan_name"] = plan_name
        captured["school_id"] = school_id
        captured["metadata"] = metadata or {}
        return {
            "status": "success",
            "authorization_url": "https://paystack.test/authorize",
            "access_code": "ACCESS-123",
            "reference": "PSK-INIT-001",
        }

    monkeypatch.setattr("backend.paystack_integration.initialize_payment", fake_initialize_payment)

    response = client.post(
        "/api/paystack/initialize",
        headers=proprietor_headers,
        data=json.dumps({"plan_name": "Basic", "billing_period": "term"}),
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["data"]["reference"] == "PSK-INIT-001"

    metadata = captured["metadata"]
    proration_data = metadata.get("proration_data") or {}
    assert captured["plan_name"] == "Basic"
    assert captured["school_id"] == test_school.id
    assert metadata.get("student_count") == 35
    assert metadata.get("billing_period") == "term"
    assert proration_data.get("is_prorated") is True
    assert proration_data.get("calculation_source") == "current_term_remaining"
    assert proration_data.get("days_remaining") == 16
    assert proration_data.get("days_in_period") == 60
    assert proration_data.get("next_billing_date_override")

    expected_term_cost = 360 + (5 * 12)
    expected_prorated_cost = expected_term_cost * (16 / 60)
    assert metadata.get("amount_cedis") == pytest.approx(expected_prorated_cost, rel=0, abs=0.01)
    assert captured["amount_cents"] == int(expected_prorated_cost * 100)


def test_direct_subscription_upgrade_blocks_unpaid_paid_plan_changes(
    client, db, test_school, proprietor_headers
):
    test_school.subscription_plan = "Free Tier"
    test_school.subscription_status = "Active"
    db.session.commit()

    response = client.post(
        "/api/school/subscription/upgrade",
        headers=proprietor_headers,
        data=json.dumps({"plan": "Basic"}),
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload["error"] == "payment_required_for_upgrade"

    db.session.refresh(test_school)
    assert test_school.subscription_plan == "Free Tier"


def test_subscription_reads_use_effective_plan_and_shared_active_student_count(
    client, db, test_school, test_proprietor, proprietor_headers
):
    from backend.api.models import Student

    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=5)
    test_school.is_trial_active = True
    db.session.add(
        Student(
            school_id=test_school.id,
            first_name="Lower",
            surname="Case",
            name="Lower Case",
            student_code="LC001",
            current_class="JHS 1",
            status="active",
        )
    )
    db.session.commit()

    subscription_response = client.get("/api/school/subscription", headers=proprietor_headers)
    assert subscription_response.status_code == 200
    subscription_payload = subscription_response.get_json()
    assert subscription_payload["plan"] == "Premium"
    assert subscription_payload["subscription_plan"] == "Premium"
    assert subscription_payload["base_plan"] == "Free Tier"
    assert subscription_payload["billing_visibility"]["plan"] == "Premium"
    assert subscription_payload["billing_visibility"]["base_plan"] == "Free Tier"
    assert subscription_payload["current_enrollment"] == 1

    effective_plan_response = client.get(
        "/api/school/subscription/effective-plan",
        headers=proprietor_headers,
    )
    assert effective_plan_response.status_code == 200
    effective_plan_payload = effective_plan_response.get_json()
    assert effective_plan_payload["plan"] == "Premium"
    assert effective_plan_payload["base_plan"] == "Free Tier"
    assert effective_plan_payload["effective_plan"] == "Premium"


def test_paystack_initialize_uses_active_students_for_default_billing_count(
    client, db, test_school, test_proprietor, proprietor_headers, monkeypatch
):
    from backend.api.models import Student

    db.session.add_all(
        [
            Student(
                school_id=test_school.id,
                first_name="Active",
                surname="Learner",
                name="Active Learner",
                student_code="ACT001",
                current_class="JHS 1",
                status="Active",
            ),
            Student(
                school_id=test_school.id,
                first_name="Inactive",
                surname="Learner",
                name="Inactive Learner",
                student_code="INA001",
                current_class="JHS 1",
                status="Withdrawn",
            ),
        ]
    )
    db.session.commit()

    captured = {}

    def fake_initialize_payment(email, amount_cents, plan_name, school_id, metadata=None):
        captured["email"] = email
        captured["amount_cents"] = amount_cents
        captured["plan_name"] = plan_name
        captured["school_id"] = school_id
        captured["metadata"] = metadata or {}
        return {
            "status": "success",
            "authorization_url": "https://paystack.test/authorize",
            "access_code": "ACCESS-456",
            "reference": "PSK-INIT-COUNT-001",
        }

    monkeypatch.setattr("backend.paystack_integration.initialize_payment", fake_initialize_payment)

    response = client.post(
        "/api/paystack/initialize",
        headers=proprietor_headers,
        data=json.dumps({"plan_name": "Basic", "billing_period": "term"}),
    )

    assert response.status_code == 200
    assert captured["metadata"]["student_count"] == 1


def test_shared_effective_plan_helper_handles_naive_trial_dates(client, test_school):
    from backend.subscription_state import get_effective_plan, is_trial_active

    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.utcnow() + timedelta(days=2)

    assert get_effective_plan(test_school) == "Premium"
    assert is_trial_active(test_school) is True


def test_usage_stats_handle_naive_trial_end_date(client, db, test_school, test_proprietor):
    from backend.email_service import get_school_usage_stats

    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.utcnow() + timedelta(days=2)
    test_school.is_trial_active = True
    db.session.commit()

    stats = get_school_usage_stats(test_school.id)

    assert stats is not None
    assert stats["trial_days_remaining"] >= 0
    assert stats["trial_expiring_soon"] in [True, False]


def test_term_proration_context_uses_published_national_calendar_when_school_term_missing(
    client, app, test_school, monkeypatch
):
    from backend.subscription_metering import get_current_term_reference, get_term_proration_context

    fake_now = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("backend.subscription_metering._now_utc", lambda: fake_now)

    with app.app_context():
        term_reference = get_current_term_reference(test_school.id)
        assert term_reference is not None
        assert term_reference["source"] == "national_basic_calendar"
        assert term_reference["start_date"].isoformat() == "2026-09-08"
        assert term_reference["end_date"].isoformat() == "2026-12-17"

        proration = get_term_proration_context(test_school.id, now=fake_now)
        assert proration["days_in_term"] == 101
        assert proration["days_remaining"] == 89
        assert proration["proration_ratio"] == pytest.approx(89 / 101, rel=0, abs=1e-6)


def test_import_published_national_calendar_terms(client, db, test_school, proprietor_headers):
    response = client.post(
        "/api/school/terms/import-national-calendar",
        headers=proprietor_headers,
        data=json.dumps({"academic_year": "2026/2027"}),
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["created_count"] == 3
    assert payload["skipped_count"] == 0

    terms_response = client.get("/api/school/terms", headers=proprietor_headers)
    assert terms_response.status_code == 200
    terms = terms_response.get_json()["terms"]
    assert [term["name"] for term in terms] == ["Term 1", "Term 2", "Term 3"]

    imported_term_1 = next(term for term in terms if term["name"] == "Term 1")
    imported_term_2 = next(term for term in terms if term["name"] == "Term 2")
    imported_term_3 = next(term for term in terms if term["name"] == "Term 3")

    assert imported_term_1["start_date"] == "2026-09-08"
    assert imported_term_1["end_date"] == "2026-12-17"
    assert imported_term_1["billing_due_date"] == "2027-01-05"
    assert imported_term_2["billing_due_date"] == "2027-04-20"
    assert imported_term_3["billing_due_date"] is None

    second_response = client.post(
        "/api/school/terms/import-national-calendar",
        headers=proprietor_headers,
        data=json.dumps({"academic_year": "2026/2027"}),
    )
    assert second_response.status_code == 200
    second_payload = second_response.get_json()
    assert second_payload["created_count"] == 0
    assert second_payload["skipped_count"] == 3


def test_import_published_national_calendar_terms_uses_recommended_year_when_omitted(
    client, app, db, test_school, proprietor_headers, monkeypatch
):
    monkeypatch.setattr(
        "backend.subscription_metering._now_utc",
        lambda: datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc),
    )

    response = client.post(
        "/api/school/terms/import-national-calendar",
        headers=proprietor_headers,
        data=json.dumps({}),
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["academic_year"] == "2026/2027"

    terms_response = client.get("/api/school/terms", headers=proprietor_headers)
    assert terms_response.status_code == 200
    terms_payload = terms_response.get_json()
    assert terms_payload["suggested_academic_year"] == "2026/2027"


def test_paystack_initialize_existing_term_cycle_uses_actual_term_days(
    client, app, db, test_school, proprietor_headers, monkeypatch
):
    from datetime import date

    from backend.api.models import AcademicTerm

    today = date.today()
    term = AcademicTerm(
        school_id=test_school.id,
        name="Term 3",
        academic_year="2025/2026",
        start_date=today - timedelta(days=44),
        end_date=today + timedelta(days=15),
        is_active=True,
        created_by="system",
    )
    db.session.add(term)

    test_school.subscription_plan = "Basic"
    test_school.subscription_status = "Active"
    test_school.next_billing_date = datetime.now(timezone.utc) + timedelta(days=15)
    db.session.commit()

    captured = {}

    def fake_initialize_payment(email, amount_cents, plan_name, school_id, metadata=None):
        captured["email"] = email
        captured["amount_cents"] = amount_cents
        captured["plan_name"] = plan_name
        captured["school_id"] = school_id
        captured["metadata"] = metadata or {}
        return {
            "status": "success",
            "authorization_url": "https://paystack.test/authorize",
            "access_code": "ACCESS-TERM-001",
            "reference": "PSK-TERM-001",
        }

    monkeypatch.setattr("backend.paystack_integration.initialize_payment", fake_initialize_payment)

    response = client.post(
        "/api/paystack/initialize",
        headers=proprietor_headers,
        data=json.dumps({"plan_name": "Premium", "billing_period": "term"}),
    )

    assert response.status_code == 200
    metadata = captured["metadata"]
    proration_data = metadata.get("proration_data") or {}
    assert proration_data.get("is_prorated") is True
    assert proration_data.get("calculation_source") == "existing_cycle"
    assert proration_data.get("days_remaining") == 16
    assert proration_data.get("days_in_period") == 60
    assert proration_data.get("term_name") == "Term 3"
    assert proration_data.get("reference_source") == "school_active_term"
    assert metadata.get("amount_cedis") == pytest.approx(proration_data.get("prorated_cost"), rel=0, abs=0.01)


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


def test_suspended_school_keeps_historical_term_access_only(client, db, test_school, proprietor_headers):
    from backend.api.models import AcademicTerm

    archived_term = AcademicTerm(
        school_id=test_school.id,
        name="Term 1",
        academic_year="2025/2026",
        start_date=datetime(2025, 9, 9, tzinfo=timezone.utc).date(),
        end_date=datetime(2025, 12, 18, tzinfo=timezone.utc).date(),
        is_active=False,
    )
    db.session.add(archived_term)

    test_school.subscription_plan = "Basic"
    test_school.next_billing_date = datetime.now(timezone.utc) - timedelta(days=20)
    test_school.subscription_status = "Active"
    db.session.commit()

    terms_response = client.get("/api/school/terms", headers=proprietor_headers)
    assert terms_response.status_code == 200
    payload = terms_response.get_json()
    assert payload["count"] == 1
    assert payload["terms"][0]["academic_year"] == "2025/2026"

    blocked = client.get("/api/school/fees", headers=proprietor_headers)
    assert blocked.status_code == 402
    blocked_payload = blocked.get_json()
    assert blocked_payload["error"] == "billing_restriction"
    assert blocked_payload["billing_status"]["status"] == "Suspended"


def test_suspended_school_keeps_archived_student_report_access(client, db, test_school, proprietor_headers):
    from backend.api.models import ReportCard, Student

    student = Student(
        school_id=test_school.id,
        first_name="Ama",
        surname="Mensah",
        name="Ama Mensah",
        student_code="RPT001",
        current_class="JHS 1",
    )
    db.session.add(student)
    db.session.flush()

    report = ReportCard(
        school_id=test_school.id,
        student_id=student.id,
        academic_term="Term 1",
        academic_year="2025/2026",
        class_name="JHS 1",
        subject_grades=[],
        term_average=78.5,
        status="Published",
    )
    db.session.add(report)

    test_school.subscription_plan = "Basic"
    test_school.next_billing_date = datetime.now(timezone.utc) - timedelta(days=20)
    test_school.subscription_status = "Active"
    db.session.commit()

    report_history = client.get(f"/api/students/{student.id}/reports", headers=proprietor_headers)
    assert report_history.status_code == 200
    payload = report_history.get_json()
    assert len(payload) == 1
    assert payload[0]["academic_term"] == "Term 1"
    assert payload[0]["academic_year"] == "2025/2026"


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


def test_bank_webhook_quarantines_payment_when_free_tier_school_is_over_capacity(client, db, test_school, monkeypatch):
    from backend.api.models import AMLTransactionFlag, Payment, Student

    secret = "test-bank-webhook-secret-0123456789"
    monkeypatch.setenv("BANK_WEBHOOK_SECRET", secret)

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

    student = Student(
        school_id=test_school.id,
        first_name="Esi",
        surname="Mensah",
        name="Esi Mensah",
        student_code="BANKCAP",
        current_class="JHS 2",
        total_tuition_owed=300.0,
    )
    db.session.add(student)
    db.session.commit()

    payload = {
        "status": "success",
        "reference": "BANKCAP-TUITION-T1",
        "amount": 120.0,
        "transaction_id": "BANK-WEBHOOK-BLOCK-001",
        "payer_name": "Parent Three",
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
    assert body["status"] == "blocked"
    assert body["payment_status"] == "Pending"

    payment = Payment.query.filter_by(reference_id="BANK-WEBHOOK-BLOCK-001").first()
    assert payment is not None
    assert payment.status == "Pending"

    db.session.refresh(student)
    assert student.total_tuition_owed == 300.0

    flag = AMLTransactionFlag.query.filter_by(
        payment_id=payment.id,
        rule_code="FREE_TIER_OVER_CAP_PAYMENT",
    ).first()
    assert flag is not None


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


def test_process_payment_confirmation_uses_prorated_term_end_anchor(client, app, db, test_school):
    from backend.api.models import LedgerEntry, School
    from backend.paystack_integration import process_payment_confirmation

    with app.app_context():
        override = datetime.now(timezone.utc) + timedelta(days=18)
        test_school.subscription_plan = "Free Tier"
        test_school.subscription_status = "Active"
        test_school.trial_plan = "Premium"
        test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
        test_school.is_trial_active = False
        db.session.commit()

        result = process_payment_confirmation(
            school_id=test_school.id,
            plan_name="Basic",
            amount_paid_cedis=180.0,
            reference="SUB-PRORATE-001",
            metadata={
                "billing_period": "term",
                "terms": 1,
                "student_count": 42,
                "proration_data": {
                    "is_prorated": True,
                    "days_remaining": 18,
                    "days_in_period": 120,
                    "proration_ratio": 0.15,
                    "next_billing_date_override": override.isoformat(),
                    "calculation_source": "current_term_remaining",
                },
            },
        )

        updated_school = School.query.get(test_school.id)
        assert result["status"] == "success"
        assert result["reference"] == "SUB-PRORATE-001"
        assert updated_school.subscription_plan == "Basic"
        assert updated_school.trial_plan is None
        assert updated_school.trial_end_date is None
        assert updated_school.is_trial_active is False
        assert updated_school.next_billing_date is not None
        normalized_next_billing = updated_school.next_billing_date
        if normalized_next_billing.tzinfo is None:
            normalized_next_billing = normalized_next_billing.replace(tzinfo=timezone.utc)
        assert normalized_next_billing.isoformat() == override.isoformat()

        entry = LedgerEntry.query.filter_by(tx_ref="SUB-PRORATE-001", tx_type="subscription").first()
        assert entry is not None
        meta = entry.meta or {}
        assert meta.get("billing_period") == "term"
        assert (meta.get("proration_data") or {}).get("next_billing_date_override") == override.isoformat()


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

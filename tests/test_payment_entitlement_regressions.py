import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import (
    AMLTransactionFlag,
    Inventory,
    LedgerEntry,
    Payment,
    PaymentCollectionIntent,
    SchoolSettings,
    Student,
    verify_ledger_chain,
)


@pytest.fixture()
def proprietor_headers(app, test_school, test_proprietor):
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    return {
        "Authorization": f"Bearer {token}",
        "X-School-ID": test_school.id,
        "Content-Type": "application/json",
    }


@pytest.mark.parametrize("payment_type", ["Tuition", "Feeding"])
def test_paid_pending_confirmation_seals_complete_metadata(
    client, db, test_school, test_proprietor, test_students,
    proprietor_headers, payment_type,
):
    student = test_students[0]
    student.total_tuition_owed = 200.0
    student.feeding_paid = False
    payment = Payment(
        school_id=test_school.id,
        student_id=student.id,
        created_by_user_id=test_proprietor.id,
        amount=25.0,
        payment_type=payment_type,
        method="Cash",
        status="Pending",
        reference_id=f"CONFIRM-{payment_type}",
        payment_category={"term": "Term 1", "frequency": "Daily"},
    )
    db.session.add(payment)
    db.session.commit()

    response = client.post(
        f"/api/finance/confirm-payment/{payment.id}",
        headers=proprietor_headers,
        json={},
    )

    assert response.status_code == 200, response.get_json()
    db.session.refresh(payment)
    db.session.refresh(student)
    assert payment.status == "Confirmed"
    assert payment.verified_by == test_proprietor.id
    entry = LedgerEntry.query.filter_by(
        school_id=test_school.id, student_id=student.id,
    ).one()
    assert entry.meta["confirmed_by"] == test_proprietor.username
    assert entry.amount == 25.0
    assert student.total_tuition_owed == (175.0 if payment_type == "Tuition" else 200.0)
    assert student.feeding_paid is (payment_type == "Feeding")
    valid, broken, checked = verify_ledger_chain(test_school.id)
    assert valid, broken
    assert checked == 1


def _set_plan(db, school, state):
    school.subscription_status = "Active"
    school.subscription_plan = "Free Tier" if state != "paid" else "Premium"
    school.trial_plan = "Premium" if state in {"expired", "trial"} else None
    school.trial_end_date = (
        datetime.now(timezone.utc) + timedelta(days=7 if state == "trial" else -1)
        if school.trial_plan else None
    )
    db.session.commit()


@pytest.mark.parametrize("payment_type", ["Inventory", "Uniform"])
def test_paid_receive_inventory_seals_enriched_metadata(
    client, db, test_school, test_students, proprietor_headers, payment_type,
):
    item = Inventory(
        school_id=test_school.id, item_name="School Shirt", item_type="Uniform",
        size="Large", sku="SHIRT-L", quantity=8, price=25.0,
    )
    db.session.add(item)
    db.session.commit()
    response = client.post(
        "/api/finance/receive-payment", headers=proprietor_headers,
        json={
            "student_id": test_students[0].id, "amount": 50.0,
            "type": payment_type, "method": "Cash",
            "reference_id": f"INVENTORY-{payment_type}",
            "payment_category": {"item_id": item.id, "quantity": 2},
        },
    )

    assert response.status_code == 200, response.get_json()
    payment = db.session.get(Payment, response.get_json()["payment_id"])
    assert payment.status == "Confirmed"
    db.session.refresh(item)
    assert item.quantity == 6
    enriched = {
        "item_name": "School Shirt", "item_type": "Uniform", "size": "Large",
        "sku": "SHIRT-L", "quantity": 2,
    }
    for field, value in enriched.items():
        assert payment.payment_category[field] == value
    entry = LedgerEntry.query.filter_by(tx_ref=payment.reference_id).one()
    assert entry.meta["payment_category"] == payment.payment_category
    valid, broken, checked = verify_ledger_chain(test_school.id)
    assert valid, broken
    assert checked == 1


@pytest.mark.parametrize("state", ["free", "expired"])
@pytest.mark.parametrize("provider", ["bank", "paystack"])
@pytest.mark.parametrize("payment_type", ["Tuition", "Feeding"])
def test_signed_callbacks_quarantine_unentitled_under_cap_payments(
    client, db, test_school, test_students, monkeypatch,
    state, provider, payment_type,
):
    _set_plan(db, test_school, state)
    student = test_students[0]
    student.total_tuition_owed = 300.0
    student.feeding_paid = False
    db.session.commit()
    assert Student.query.filter_by(school_id=test_school.id, status="Active").count() < 50
    reference = f"QUARANTINE-{provider}-{state}-{payment_type}"
    secret = "test-payment-entitlement-webhook-secret"
    if provider == "bank":
        monkeypatch.setenv("BANK_WEBHOOK_SECRET", secret)
        suffix = "TUITION-T1" if payment_type == "Tuition" else "FEED-MON"
        payload = {
            "status": "success", "reference": f"{student.student_code}-{suffix}",
            "amount": 25.0, "transaction_id": reference, "payer_name": "Parent",
        }
        signature_header = "X-Bank-Signature"
        digest = hashlib.sha256
    else:
        monkeypatch.setenv("PAYSTACK_SECRET_KEY", secret)
        payload = {
            "event": "charge.success",
            "data": {
                "id": 9001, "reference": reference, "status": "success",
                "amount": 2500, "channel": "mobile_money",
                "metadata": {
                    "school_id": test_school.id, "student_id": student.id,
                    "payment_type": payment_type,
                    "payment_category": {"frequency": "Monthly", "term": "Term 1"},
                },
                "authorization": {"reusable": False},
            },
        }
        signature_header = "X-Paystack-Signature"
        digest = hashlib.sha512
    raw = json.dumps(payload).encode("utf-8")
    path = f"/api/finance/webhook/{provider}"
    rejected = client.post(
        path, data=raw,
        headers={"Content-Type": "application/json", signature_header: "invalid"},
    )
    assert rejected.status_code == 401
    assert Payment.query.filter_by(reference_id=reference).count() == 0
    response = client.post(
        path, data=raw,
        headers={
            "Content-Type": "application/json",
            signature_header: hmac.new(secret.encode(), raw, digest).hexdigest(),
        },
    )

    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["status"] == "blocked"
    assert body["payment_status"] == "Pending"
    payment = Payment.query.filter_by(reference_id=reference).one()
    assert payment.status == "Pending"
    assert payment.amount == 25.0
    assert payment.student_id == student.id
    db.session.refresh(student)
    assert student.total_tuition_owed == 300.0
    assert student.feeding_paid is False
    assert LedgerEntry.query.filter_by(school_id=test_school.id).count() == 0
    flags = AMLTransactionFlag.query.filter_by(payment_id=payment.id).all()
    assert [flag.rule_code for flag in flags] == ["PAYMENT_FEATURE_UNAVAILABLE"]
    assert flags[0].details["collection_block"]["reason"] == "feature_unavailable"


@pytest.mark.parametrize("state", ["free", "expired"])
@pytest.mark.parametrize("operation", ["codes", "virtual_account", "receive", "initialize"])
def test_unentitled_payment_access_denied_before_provider_calls(
    client, db, test_school, test_students, proprietor_headers,
    monkeypatch, state, operation,
):
    _set_plan(db, test_school, state)
    student = test_students[0]
    provider = Mock(side_effect=AssertionError("Provider must not be called"))
    provisioning = Mock(side_effect=AssertionError("Provisioning must not be called"))
    monkeypatch.setattr("backend.routes._call_paystack_api", provider)
    monkeypatch.setattr("backend.routes._create_or_reuse_student_virtual_account_intent", provisioning)
    path = f"/api/students/{student.id}/payment-codes"
    if operation == "codes":
        response = client.get(path, headers=proprietor_headers)
    elif operation == "virtual_account":
        response = client.post(
            f"{path}/{student.student_code}-TUITION-T1/virtual-account",
            headers=proprietor_headers, json={},
        )
    else:
        path = (
            "/api/finance/receive-payment" if operation == "receive"
            else "/api/finance/paystack/initialize-payment"
        )
        response = client.post(
            path, headers=proprietor_headers,
            json={"student_id": student.id, "amount": 25.0, "type": "Tuition"},
        )

    assert response.status_code == 409, response.get_json()
    assert response.get_json()["error"] == "payment_collection_blocked"
    assert response.get_json()["reason"] == "feature_unavailable"
    provider.assert_not_called()
    provisioning.assert_not_called()
    assert Payment.query.filter_by(school_id=test_school.id).count() == 0
    assert PaymentCollectionIntent.query.filter_by(school_id=test_school.id).count() == 0
    assert LedgerEntry.query.filter_by(school_id=test_school.id).count() == 0


def test_active_premium_trial_payment_codes_get_does_not_provision(
    client, db, test_school, test_students, proprietor_headers, monkeypatch,
):
    _set_plan(db, test_school, "trial")
    test_students[0].total_tuition_owed = 100.0
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).one()
    settings.tuition_fee = 100.0
    db.session.commit()
    provider = Mock(side_effect=AssertionError("GET must not call provider"))
    provisioning = Mock(side_effect=AssertionError("GET must not provision"))
    monkeypatch.setattr("backend.routes._call_paystack_api", provider)
    monkeypatch.setattr("backend.routes._create_or_reuse_student_virtual_account_intent", provisioning)
    response = client.get(
        f"/api/students/{test_students[0].id}/payment-codes",
        headers=proprietor_headers,
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["payment_codes"]
    provider.assert_not_called()
    provisioning.assert_not_called()
    assert PaymentCollectionIntent.query.filter_by(school_id=test_school.id).count() == 0


@pytest.mark.parametrize("state", ["paid", "trial", "free", "expired"])
def test_staff_effective_plan_features_without_billing_data(
    client, db, test_school, auth_headers, state,
):
    _set_plan(db, test_school, state)
    settings = SchoolSettings.query.filter_by(school_id=test_school.id).one()
    settings.enabled_modules = {
        **(settings.enabled_modules or {}),
        "ai_pack_addon": True, "automation_pack_addon": True,
    }
    db.session.commit()
    response = client.get(
        "/api/school/subscription/effective-plan", headers=auth_headers,
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    entitled = state in {"paid", "trial"}
    assert payload["effective_plan"] == ("Premium" if entitled else "Free Tier")
    assert payload["features"]["payment_tracking"] is entitled
    assert set(payload) == {
        "plan", "plan_display_name", "base_plan", "base_plan_display_name",
        "effective_plan", "features", "report_templates", "active_addons", "trial",
    }
    assert payload["trial"]["active"] is (state == "trial")
    if not entitled:
        assert payload["active_addons"] == {"ai_pack": False, "automation_pack": False}
        for feature in (
            "ai_analysis", "ai_narratives", "student_rescue_agent",
            "exam_intelligence", "webhook_payment_automation",
        ):
            assert payload["features"][feature] is False
import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import (
    AMLTransactionFlag,
    LedgerEntry,
    Payment,
    PaymentCollectionIntent,
    SchoolVerification,
    verify_ledger_chain,
)


WEBHOOK_SECRET = "margin-webhook-test-secret"


@pytest.fixture()
def forbid_payment_effects(monkeypatch):
    def reject_effects(*args, **kwargs):
        pytest.fail("Held or unmapped payments must not apply balance effects")

    monkeypatch.setattr("backend.routes._apply_auto_payment_effects", reject_effects)
    monkeypatch.setattr("backend.routes._apply_confirmed_payment_effects", reject_effects)


@pytest.fixture()
def margin_route(client, db, test_school, test_students, monkeypatch):
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", WEBHOOK_SECRET)

    def reject_provider_call(*args, **kwargs):
        pytest.fail("Webhook integration tests must not call real providers")

    monkeypatch.setattr("backend.routes._call_paystack_api", reject_provider_call)
    monkeypatch.setattr("requests.sessions.Session.request", reject_provider_call)
    unique = uuid4().hex
    for student in test_students:
        student.total_tuition_owed = 75.0
    student = test_students[0]
    intent = PaymentCollectionIntent(
        school_id=test_school.id,
        student_id=student.id,
        provider="paystack",
        collection_channel="dedicated_virtual_account",
        intent_status="assigned",
        reference_code=f"{student.student_code}-TUIT-I1",
        payment_type="Tuition",
        payment_category={"fee_type": "Tuition", "installment_number": 1},
        base_amount=25.0,
        convenience_fee_amount=0.76,
        estimated_provider_fee_amount=0.50,
        platform_fee_amount=0.25,
        total_amount=25.76,
        provider_customer_code=f"CUS_MARGIN_{unique}",
        provider_dedicated_account_id=unique,
        provider_bank_name="Test Bank",
        provider_account_number=str(uuid4().int)[:10],
        provider_subaccount_code="ACCT_MARGIN_TEST",
        meta={
            "pricing": {
                "fee_model": "gross_up_margin_v1",
                "estimated_provider_fee_rate_pct": 1.95,
                "platform_margin_rate_pct": 1,
            },
            "split_config": {
                "split_code": f"SPL_MARGIN_{unique}",
                "settlement_mode": "paystack_flat_split",
                "fee_bearer": "account",
                "school_settlement_amount": 25.0,
                "school_settlement_amount_minor": 2500,
                "platform_settlement_amount": 0.76,
                "platform_settlement_amount_minor": 76,
            },
        },
    )
    db.session.add(intent)
    db.session.commit()
    return intent


def post_signed_webhook(client, intent, amount=2576, fees=50, account_number=None, path="/api/finance/webhook/paystack"):
    body = {
        "event": "charge.success",
        "data": {
            "reference": f"PS-MARGIN-{intent.provider_dedicated_account_id}",
            "status": "success",
            "amount": amount,
            "fees": fees,
            "authorization": {
                "channel": "dedicated_nuban",
                "receiver_account_number": account_number or intent.provider_account_number,
                "sender_name": "Test Parent",
                "sender_bank": "Test Bank",
            },
        },
    }
    raw = json.dumps(body).encode("utf-8")
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw, hashlib.sha512).hexdigest()
    return client.post(
        path,
        data=raw,
        headers={"Content-Type": "application/json", "X-Paystack-Signature": signature},
    )


def payment_for(intent):
    return Payment.query.filter_by(
        reference_id=f"PS-MARGIN-{intent.provider_dedicated_account_id}",
    ).one()


def record_counts(school_id):
    return tuple(
        model.query.filter_by(school_id=school_id).count()
        for model in (Payment, LedgerEntry, AMLTransactionFlag)
    )


def proprietor_headers(app, test_school, test_proprietor):
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    return {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}


@pytest.mark.parametrize("webhook_path", ["/api/finance/webhook/paystack", "/api/paystack/webhook"])
def test_exact_margin_webhook_credits_full_base_once_and_receipt_preserves_gross(
    client, app, db, test_school, test_proprietor, test_students, margin_route,
    webhook_path,
):
    response = post_signed_webhook(client, margin_route, path=webhook_path)
    assert response.status_code == 200
    assert response.get_json()["status"] == "recorded"
    assert response.get_json()["payment_status"] == "Confirmed"
    assert response.get_json()["applied_school_fee_amount"] == 25.0
    payment = payment_for(margin_route)
    assert payment.status == "Confirmed"
    assert payment.amount == 25.0
    category = payment.payment_category
    assert category["fee_model"] == "gross_up_margin_v1"
    assert category["gross_amount_paid"] == 25.76
    assert category["applied_school_fee_amount"] == 25.0
    assert category["actual_provider_fee_amount"] == 0.50
    assert category["actual_platform_net_amount"] == 0.26
    assert category["collected_convenience_fee_amount"] == 0.76
    db.session.refresh(test_students[0])
    db.session.refresh(margin_route)
    assert test_students[0].total_tuition_owed == 50.0
    assert all(student.total_tuition_owed == 75.0 for student in test_students[1:])
    assert margin_route.intent_status == "paid"
    assert margin_route.paid_at is not None
    assert margin_route.provider_reference == payment.reference_id
    ledger = LedgerEntry.query.filter_by(school_id=test_school.id).one()
    assert ledger.amount == 25.0
    assert verify_ledger_chain(test_school.id) == (True, [], 1)
    counts = record_counts(test_school.id)
    assert counts[:2] == (1, 1)
    paid_at = margin_route.paid_at

    receipts = client.get(
        "/api/finance/receipts",
        headers=proprietor_headers(app, test_school, test_proprietor),
    )
    assert receipts.status_code == 200
    receipt = receipts.get_json()["receipts"][0]
    assert receipt["id"] == payment.id
    assert receipt["status"] == "Confirmed"
    assert receipt["display_amount"] == 25.76
    assert receipt["applied_amount"] == 25.0
    assert receipt["provider_fee_amount"] == 0.50

    replay = post_signed_webhook(client, margin_route, path=webhook_path)
    assert replay.status_code == 200
    assert replay.get_json()["status"] == "duplicate"
    assert replay.get_json()["payment_status"] == "Confirmed"
    assert record_counts(test_school.id) == counts
    db.session.refresh(test_students[0])
    db.session.refresh(margin_route)
    assert test_students[0].total_tuition_owed == 50.0
    assert margin_route.intent_status == "paid"
    assert margin_route.paid_at == paid_at
    assert verify_ledger_chain(test_school.id) == (True, [], 1)


def assert_held_without_credit(db, school, students, intent):
    db.session.refresh(intent)
    for student in students:
        db.session.refresh(student)
        assert student.total_tuition_owed == 75.0
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None
    assert LedgerEntry.query.filter_by(school_id=school.id).count() == 0


@pytest.mark.parametrize("amount,fees,invalid_split,reason,rule_code", [
    (2575, 50, False, "payment_amount_mismatch", "PAYMENT_AMOUNT_MISMATCH"),
    (2577, 50, False, "payment_amount_mismatch", "PAYMENT_AMOUNT_MISMATCH"),
    (2100, 50, False, "payment_amount_mismatch", "PAYMENT_AMOUNT_MISMATCH"),
    (2576, 77, False, "processing_fee_exceeds_surcharge", "PAYMENT_SETTLEMENT_REVIEW"),
    (2576, 52, False, "processing_fee_exceeds_margin_allowance", "PAYMENT_SETTLEMENT_REVIEW"),
    (2576, 50, True, "invalid_settlement_split", "PAYMENT_SETTLEMENT_REVIEW"),
])
def test_review_webhook_preserves_gross_without_credit_and_replay_stays_pending(
    client, app, db, test_school, test_proprietor, test_students, margin_route,
    forbid_payment_effects, amount, fees, invalid_split, reason, rule_code,
):
    if invalid_split:
        margin_route.meta = {
            **margin_route.meta,
            "split_config": {**margin_route.meta["split_config"], "fee_bearer": "subaccount"},
        }
        db.session.commit()

    response = post_signed_webhook(client, margin_route, amount=amount, fees=fees)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "blocked"
    assert payload["reason"] == reason
    assert payload["payment_status"] == "Pending"
    assert payload["applied_school_fee_amount"] == 0
    payment = payment_for(margin_route)
    assert payment.status == "Pending"
    assert payment.amount == amount / 100
    assert payment.verified_at is None
    category = payment.payment_category
    assert category["gross_amount_paid"] == amount / 100
    assert category["applied_school_fee_amount"] == 0
    assert category["payment_collection_requires_review"] == reason
    flag = AMLTransactionFlag.query.filter_by(
        school_id=test_school.id, payment_id=payment.id, rule_code=rule_code,
    ).one()
    assert flag.status == "open"
    assert flag.student_id == test_students[0].id
    assert flag.details["reason"] == reason
    assert flag.details["gross_amount_paid"] == amount / 100
    assert_held_without_credit(db, test_school, test_students, margin_route)
    counts = record_counts(test_school.id)
    assert counts[:2] == (1, 0)

    headers = proprietor_headers(app, test_school, test_proprietor)
    receipts = client.get("/api/finance/receipts", headers=headers)
    assert receipts.status_code == 200
    receipt = receipts.get_json()["receipts"][0]
    assert receipt["id"] == payment.id
    assert receipt["status"] == "Pending"
    assert receipt["display_amount"] == amount / 100
    assert receipt["applied_amount"] == 0
    history = client.get(f"/api/students/{test_students[0].id}/payments", headers=headers)
    assert history.status_code == 200
    historical_payment = history.get_json()[0]
    assert historical_payment["id"] == payment.id
    assert historical_payment["status"] == "Pending"
    assert historical_payment["amount"] == historical_payment["applied_amount"] == 0
    assert historical_payment["display_amount"] == historical_payment["total_amount"] == amount / 100

    replay = post_signed_webhook(client, margin_route, amount=amount, fees=fees)
    assert replay.status_code == 200
    assert replay.get_json()["status"] == "duplicate"
    assert replay.get_json()["payment_status"] == "Pending"
    assert record_counts(test_school.id) == counts
    assert_held_without_credit(db, test_school, test_students, margin_route)
    db.session.refresh(payment)
    assert payment.amount == amount / 100
    assert payment.status == "Pending"
    assert payment.payment_category["gross_amount_paid"] == amount / 100


def test_unknown_account_without_metadata_hints_remains_unmapped(
    client, db, test_school, test_students, margin_route, forbid_payment_effects,
):
    counts = record_counts(test_school.id)
    account = margin_route.provider_account_number
    metadata = json.loads(json.dumps(margin_route.meta))
    response = post_signed_webhook(client, margin_route, account_number="0000000000")
    assert response.status_code == 200
    assert response.get_json()["status"] == "unmapped"
    assert record_counts(test_school.id) == counts
    assert_held_without_credit(db, test_school, test_students, margin_route)
    assert margin_route.provider_account_number == account
    assert margin_route.provider_reference is None
    assert margin_route.meta == metadata


@pytest.mark.parametrize("restriction,rule_code", [
    ("free", "PAYMENT_FEATURE_UNAVAILABLE"),
    ("unverified", "UNVERIFIED_SCHOOL_PAYMENT"),
])
def test_exact_margin_webhook_respects_collection_and_verification_blocks(
    client, db, test_school, test_students, margin_route, forbid_payment_effects,
    restriction, rule_code,
):
    if restriction == "free":
        test_school.subscription_plan = "Free Tier"
        test_school.trial_plan = None
        test_school.trial_end_date = None
    else:
        verification = SchoolVerification.query.filter_by(school_id=test_school.id).one()
        verification.status = "review_required"
    db.session.commit()

    response = post_signed_webhook(client, margin_route)
    assert response.status_code == 200
    assert response.get_json()["payment_status"] == "Pending"
    if restriction == "free":
        assert response.get_json()["status"] == "blocked"
    payment = payment_for(margin_route)
    assert payment.status == "Pending"
    assert payment.payment_category["gross_amount_paid"] == 25.76
    flag = AMLTransactionFlag.query.filter_by(
        school_id=test_school.id, payment_id=payment.id, rule_code=rule_code,
    ).one()
    assert flag.status == "open"
    assert_held_without_credit(db, test_school, test_students, margin_route)
    counts = record_counts(test_school.id)
    assert counts[:2] == (1, 0)

    replay = post_signed_webhook(client, margin_route)
    assert replay.status_code == 200
    assert replay.get_json()["status"] == "duplicate"
    assert replay.get_json()["payment_status"] == "Pending"
    assert record_counts(test_school.id) == counts
    assert_held_without_credit(db, test_school, test_students, margin_route)


def test_review_held_payment_cannot_be_approved_for_credit(
    client, app, db, test_school, test_proprietor, test_students, margin_route,
    forbid_payment_effects,
):
    response = post_signed_webhook(client, margin_route, amount=2575)
    assert response.status_code == 200
    assert response.get_json()["payment_status"] == "Pending"
    payment = payment_for(margin_route)
    counts = record_counts(test_school.id)

    approval = client.post(
        f"/api/finance/confirm-payment/{payment.id}",
        headers=proprietor_headers(app, test_school, test_proprietor),
        json={},
    )
    assert approval.status_code == 409
    db.session.refresh(payment)
    assert payment.status == "Pending"
    assert payment.amount == 25.75
    assert payment.verified_at is None
    assert record_counts(test_school.id) == counts
    assert_held_without_credit(db, test_school, test_students, margin_route)
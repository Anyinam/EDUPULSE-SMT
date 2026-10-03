from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.payment_collection_service import (
    create_or_reuse_student_virtual_account_intent,
    record_paystack_virtual_account_payment,
)
from backend.payment_workflow import calculate_payment_collection_breakdown


FEE_MODEL = "gross_up_margin_v1"


class IntentQuery:
    def __init__(self, intents):
        self.intents = intents

    def filter_by(self, **filters):
        return IntentQuery([
            intent for intent in self.intents
            if all(getattr(intent, key, None) == value for key, value in filters.items())
        ])

    def order_by(self, *args):
        return self

    def first(self):
        return next(iter(self.intents), None)

    def all(self):
        return self.intents


def make_intent(fee_model=FEE_MODEL):
    return SimpleNamespace(
        id=1, school_id="TEST", student_id=7, reference_code="TUITION-7",
        provider="paystack", collection_channel="dedicated_virtual_account",
        provider_account_number="1234567890", provider_dedicated_account_id="42",
        provider_customer_code="CUS_TEST", provider_bank_name="Test Bank",
        provider_reference=None, provider_last_event=None, intent_status="assigned",
        paid_at=None, payer_name=None, payer_bank_name=None, payment_type="Tuition",
        base_amount=25, total_amount=25.76, convenience_fee_amount=0.76,
        platform_fee_amount=0.25, estimated_provider_fee_amount=0.50,
        payment_category={"fee_type": "Tuition"}, expires_at=None,
        meta={
            "pricing": {"fee_model": fee_model},
            "split_config": {
                "settlement_mode": "paystack_flat_split", "fee_bearer": "account",
                "school_settlement_amount": 25, "school_settlement_amount_minor": 2500,
                "platform_settlement_amount": 0.76, "split_code": "SPL_TEST",
            },
        },
    )


def collect(intent, amount=2576, fees=50, status="recorded", status_code=200, payload_override=None, intents=None, payment_status="Confirmed"):
    model = SimpleNamespace(query=IntentQuery(intents or [intent]), id=SimpleNamespace(desc=lambda: None))
    payload = {"reference": "TX_TEST", "amount": amount, "fees": fees,
               "dedicated_account": {"account_number": "1234567890"}}
    payload.update(payload_override or {})
    body = {"status": status}
    if payment_status is not None:
        body["payment_status"] = payment_status
    recorder = Mock(return_value=(body, status_code))
    session = Mock()
    result = record_paystack_virtual_account_payment(
        payload, "charge.success", lambda value: str(value).strip() if value is not None else "",
        model, recorder, session,
    )
    return result, recorder, session


def test_approved_margin_pricing_and_full_base_settlement():
    pricing = calculate_payment_collection_breakdown(25, {"fee_model": FEE_MODEL})
    assert pricing["total_amount"] == 25.76
    assert pricing["estimated_provider_fee_amount"] == 0.50
    assert pricing["platform_fee_amount"] == 0.25
    assert pricing["rounding_surplus_amount"] == 0.01
    intent = make_intent()
    result, recorder, session = collect(intent)
    adjusted = recorder.call_args.args[0]
    category = adjusted["metadata"]["payment_category"]
    assert adjusted["amount"] == 2500
    assert category["applied_school_fee_amount"] == 25
    assert category["collected_convenience_fee_amount"] == 0.76
    assert category["actual_provider_fee_amount"] == 0.50
    assert category["actual_platform_net_amount"] == 0.26
    assert category["platform_fee_amount"] == 0.25
    assert category["fee_model"] == FEE_MODEL
    assert result[0]["applied_school_fee_amount"] == 25
    assert intent.intent_status == "paid"
    session.commit.assert_called_once()


@pytest.mark.parametrize("amount,fees,reason", [
    (2575, 50, "payment_amount_mismatch"),
    (2577, 50, "payment_amount_mismatch"),
    (2100, 50, "payment_amount_mismatch"),
    (2576, 77, "processing_fee_exceeds_surcharge"),
    (2576, 52, "processing_fee_exceeds_margin_allowance"),
])
def test_review_preserves_gross_but_never_credits_or_marks_paid(amount, fees, reason):
    intent = make_intent()
    result, recorder, _ = collect(intent, amount=amount, fees=fees, status="blocked")
    adjusted = recorder.call_args.args[0]
    assert adjusted["amount"] == 0
    assert adjusted["metadata"]["payment_collection_requires_review"] == reason
    assert adjusted["metadata"]["payment_category"]["gross_amount_paid"] == amount / 100
    assert result[0]["applied_school_fee_amount"] == 0
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None


@pytest.mark.parametrize("fee_model", [None, "legacy", "gross_up_margin_v2"])
def test_legacy_intent_accounting_is_unchanged(fee_model):
    intent = make_intent(fee_model)
    if fee_model is None:
        intent.meta.pop("pricing")
    result, recorder, _ = collect(intent)
    assert recorder.call_args.args[0]["amount"] == 2450
    assert result[0]["applied_school_fee_amount"] == 24.50
    assert "actual_platform_net_amount" not in recorder.call_args.args[0]["metadata"]["payment_category"]


@pytest.mark.parametrize("status", ["blocked", "pending", "quarantined", "unmapped"])
def test_new_intent_only_becomes_paid_after_recorded_or_duplicate(status):
    intent = make_intent()
    collect(intent, status=status)
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None


def test_failed_recorder_does_not_mutate_intent():
    intent = make_intent()
    before = deepcopy(vars(intent))
    _, _, session = collect(intent, status="error", status_code=400)
    assert vars(intent) == before
    session.commit.assert_not_called()


@pytest.mark.parametrize("status", ["recorded", "duplicate"])
def test_pending_recorder_record_never_marks_intent_paid(status):
    intent = make_intent()
    collect(intent, status=status, payment_status="Pending")
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None


@pytest.mark.parametrize("status", ["recorded", "duplicate"])
def test_unknown_recorder_payment_status_never_marks_new_intent_paid(status):
    intent = make_intent()
    collect(intent, status=status, payment_status=None)
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None


def test_recorded_then_duplicate_replays_do_not_bypass_recorder():
    intent = make_intent()
    collect(intent)
    original_paid_at = intent.paid_at
    result, recorder, _ = collect(intent, status="duplicate", payment_status="Confirmed")
    recorder.assert_called_once()
    assert result[0]["status"] == "duplicate"
    assert recorder.call_args.args[0]["amount"] == 2500
    assert intent.intent_status == "paid"
    assert intent.paid_at == original_paid_at


@pytest.mark.parametrize("status", ["recorded", "duplicate"])
def test_review_cannot_be_overridden_by_success_callback(status):
    intent = make_intent()
    collect(intent, amount=2577, status=status)
    assert intent.intent_status == "assigned"
    assert intent.paid_at is None


@pytest.mark.parametrize("fees,expected_net", [(0, 0.76), (60, 0.16), (76, 0)])
def test_known_provider_fees_preserve_margin_or_require_review(fees, expected_net):
    _, recorder, _ = collect(make_intent(), fees=fees)
    category = recorder.call_args.args[0]["metadata"]["payment_category"]
    assert recorder.call_args.args[0]["amount"] == (2500 if expected_net >= 0.25 else 0)
    assert category["payment_collection_requires_review"] == (None if expected_net >= 0.25 else "processing_fee_exceeds_margin_allowance")
    assert category["actual_platform_net_amount"] == expected_net
    assert category["provider_fee_is_estimated"] is False
    assert category["platform_margin_target_amount"] == 0.25


@pytest.mark.parametrize("fees", [None, "", "invalid", -1])
def test_missing_or_invalid_fee_is_not_disclosed_as_actual_zero(fees):
    _, recorder, _ = collect(make_intent(), fees=fees)
    category = recorder.call_args.args[0]["metadata"]["payment_category"]
    assert recorder.call_args.args[0]["amount"] == 2500
    assert category["actual_provider_fee_amount"] is None
    assert category["actual_platform_net_amount"] is None
    assert category["provider_fee_is_estimated"] is True
    assert category["estimated_platform_net_amount"] == 0.26


@pytest.mark.parametrize("field,value", [
    ("fee_bearer", "subaccount"), ("fee_bearer", None),
    ("settlement_mode", "percentage"), ("split_code", None),
    ("school_settlement_amount_minor", 2450),
])
def test_new_model_requires_explicit_account_bearer_full_base_flat_split(field, value):
    intent = make_intent()
    intent.meta["split_config"][field] = value
    _, recorder, _ = collect(intent, status="blocked")
    adjusted = recorder.call_args.args[0]
    assert adjusted["amount"] == 0
    assert adjusted["metadata"]["payment_collection_requires_review"] == "invalid_settlement_split"


def test_exact_amount_check_does_not_round_subcent_mismatch_away():
    _, recorder, _ = collect(make_intent(), amount=2576.1, status="blocked")
    assert recorder.call_args.args[0]["amount"] == 0
    assert recorder.call_args.args[0]["metadata"]["payment_collection_requires_review"] == "payment_amount_mismatch"


def test_fee_breakdown_is_used_when_top_level_fee_is_absent():
    _, recorder, _ = collect(make_intent(), fees=None, payload_override={"fees_breakdown": {"total": 50}})
    assert recorder.call_args.args[0]["metadata"]["payment_category"]["actual_provider_fee_amount"] == 0.50


def test_historical_paid_legacy_21_duplicate_is_not_rewritten():
    intent = make_intent(None)
    intent.intent_status = "paid"
    intent.provider_reference = "TX_TEST"
    intent.total_amount = 21
    before = deepcopy(vars(intent))
    result, recorder, session = collect(intent, amount=2100)
    assert result[0]["status"] == "duplicate"
    assert vars(intent) == before
    recorder.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize("override", [
    {"dedicated_account": {"account_number": "9999999999"}},
    {"metadata": {"student_id": "8"}},
    {"metadata": {"school_id": "OTHER"}},
])
def test_wrong_account_or_conflicting_hints_remain_unmapped(override):
    result, recorder, session = collect(make_intent(), payload_override=override)
    assert result is None
    recorder.assert_not_called()
    session.commit.assert_not_called()


def test_ambiguous_customer_match_remains_unmapped():
    intent = make_intent()
    other = make_intent()
    other.id = 2
    other.student_id = 8
    other.provider_account_number = "9999999999"
    result, recorder, _ = collect(intent, intents=[intent, other], payload_override={
        "dedicated_account": {}, "customer": {"customer_code": "CUS_TEST"},
    })
    assert result is None
    recorder.assert_not_called()


def provision(existing, pricing_override=None, calculate=calculate_payment_collection_breakdown):
    model = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    model.query = IntentQuery([existing])
    model.id = SimpleNamespace(desc=lambda: None)
    student = SimpleNamespace(id=7, school_id="TEST", parent_email="parent@example.com",
                              parent_name="Parent", guardian_name=None, name="Learner", parent_phone="123")
    school = SimpleNamespace(id="TEST", school_email="school@example.com", school_phone="456")
    settings = SimpleNamespace(country_code="GH", currency="GHS")
    split = Mock(return_value=(existing.meta["split_config"], None))
    customer = Mock(return_value=({"customer_code": "CUS_NEW", "first_name": "Parent", "last_name": "Test"}, None))
    account = Mock(return_value=({"id": 99, "account_number": "2222222222", "bank": {}}, None))
    session = Mock()
    payment_code = {"reference_code": "TUITION-7", "base_amount": 25, "fee_type": "Tuition"}
    if pricing_override is not None:
        payment_code["pricing_override"] = pricing_override
    result = create_or_reuse_student_virtual_account_intent(
        student, school, settings, payment_code, model, lambda value: str(value or ""),
        lambda: {"fee_model": FEE_MODEL}, calculate,
        lambda settings: {"paystack_subaccount_code": "ACCT_TEST"}, split,
        lambda country: ({"provider_slug": "test"}, None), lambda *args: "parent@example.com",
        customer, account, 30, session,
    )
    return result, split, customer, account, session


def test_assigned_route_reuses_only_when_amounts_and_fee_model_match():
    existing = make_intent()
    result, split, customer, account, session = provision(existing)
    assert result == (existing, None)
    split.assert_not_called()
    customer.assert_not_called()
    account.assert_not_called()
    session.add.assert_not_called()


def test_identical_amounts_with_legacy_version_create_new_assigned_route():
    existing = make_intent(None)
    result, split, customer, account, session = provision(existing)
    replacement, error = result
    assert error is None
    assert replacement is not existing
    assert existing.intent_status == "deactivated"
    assert replacement.meta["pricing"]["fee_model"] == FEE_MODEL
    split.assert_called_once()
    customer.assert_called_once()
    account.assert_called_once()
    session.add.assert_called_once_with(replacement)


def test_paid_legacy_route_is_returned_without_repricing_or_provisioning():
    existing = make_intent(None)
    existing.intent_status = "paid"
    existing.total_amount = 21
    before = deepcopy(vars(existing))
    calculate = Mock(side_effect=AssertionError("Paid routes must not be repriced"))
    result, split, customer, account, session = provision(existing, calculate=calculate)
    assert result == (existing, None)
    assert vars(existing) == before
    split.assert_not_called()
    customer.assert_not_called()
    account.assert_not_called()
    session.add.assert_not_called()
    calculate.assert_not_called()


def test_pricing_override_fee_model_is_saved_and_used_for_reuse():
    existing = make_intent()
    existing.total_amount = 25.49
    existing.convenience_fee_amount = 0.49
    result, _, _, _, _ = provision(existing, {"fee_model": "legacy", "estimated_provider_fee_rate_pct": 1.95})
    assert result[0].meta["pricing"]["fee_model"] == "legacy"
    assert result[0].total_amount == 25.49
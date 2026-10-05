from types import SimpleNamespace

import pytest

from backend.payment_workflow import (
    calculate_payment_collection_breakdown,
    get_tuition_collection_pricing,
)
from backend.school_configuration_service import (
    TuitionInstallmentPlanValidationError,
    get_school_fees_payload,
    update_school_fees,
)
from backend.payment_instruction_service import (
    attach_virtual_routes_to_payment_codes,
    build_payment_collection_intent_payload,
    build_student_payment_instruction_payload,
    TUITION_CONVENIENCE_FEE_KEY,
    TUITION_INSTALLMENT_PLAN_KEY,
)


class QueryStub:
    def __init__(self, result):
        self.result = result

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.result

    def get(self, identity):
        return self.result


@pytest.mark.parametrize("base,total,provider,margin,surplus", [
    (25, 25.76, 0.50, 0.25, 0.01),
    (75, 77.26, 1.51, 0.75, 0.0),
])
def test_shared_tuition_margin_breakdown(base, total, provider, margin, surplus):
    breakdown = calculate_payment_collection_breakdown(base, get_tuition_collection_pricing())
    assert breakdown["total_amount"] == total
    assert breakdown["estimated_provider_fee_amount"] == provider
    assert breakdown["platform_fee_amount"] == margin
    assert breakdown["rounding_surplus_amount"] == surplus
    assert breakdown["fee_model"] == "gross_up_margin_v1"


def test_school_fees_without_settings_exposes_shared_default_pricing():
    payload = get_school_fees_payload(
        "TEST", school_settings_model=SimpleNamespace(query=QueryStub(None)),
        get_feeding_plan_fees=lambda settings: {},
    )
    assert payload["tuition_transfer_pricing"] == get_tuition_collection_pricing()
    assert payload["tuition_platform_margin_rate_pct"] == 1
    assert payload["tuition_provider_fee_rate_pct"] == 1.95


def test_school_fees_accepts_platform_pricing():
    pricing = {"tuition_platform_margin_rate_pct": 2, "tuition_provider_fee_rate_pct": 3}
    payload = get_school_fees_payload(
        "TEST", school_settings_model=SimpleNamespace(query=QueryStub(None)),
        get_feeding_plan_fees=lambda settings: {}, payment_collection_pricing=pricing,
    )
    assert payload["tuition_transfer_pricing"] == get_tuition_collection_pricing(pricing)


def make_settings(legacy_percentage=1.95, installments=False):
    schedule = [
        {"installment_number": index, "amount": 25, "label": f"Installment {index}"}
        for index in range(1, 4)
    ]
    return SimpleNamespace(
        tuition_fee=75, feeding_fee=0, uniform_fee=0, transport_fee=0, terminal_report_fee=5,
        admission_fee_enabled=False, admission_fee_amount=0, country_code="GH",
        other_fees={
            "Library": 2,
            TUITION_CONVENIENCE_FEE_KEY: legacy_percentage,
            TUITION_INSTALLMENT_PLAN_KEY: {
                "enabled": installments, "installment_count": 3, "schedule": schedule,
            },
        },
    )


def feeding_fees(settings):
    return {"primary": 0, "daily": 0, "weekly": 0, "monthly": 0}


def make_instructions(settings, pricing=None):
    student = SimpleNamespace(
        id=1, school_id="TEST", student_code="ST01", name="Learner", current_class="Class 1",
        parent_name="Parent", parent_phone=None, parent_email=None,
        total_tuition_owed=75, is_on_scholarship=False, scholarship_covers_tuition=False,
    )
    return build_student_payment_instruction_payload(
        student=student, school_id="TEST",
        school_model=SimpleNamespace(query=QueryStub(None)),
        school_settings_model=SimpleNamespace(query=QueryStub(settings)), payment_model=None,
        generate_all_payment_codes=lambda student_code, fees: {"Tuition": "ST01-TUIT", "Library": "ST01-LIB"},
        get_school_admission_fee_config=lambda settings: {}, get_feeding_plan_fees=feeding_fees,
        attach_virtual_routes_to_payment_codes_fn=lambda student, codes: None,
        get_payment_provider_settings=lambda settings: {"paystack_subaccount_code": "ACCT_TEST"},
        paystack_dva_supported_countries={"GH"}, sanitize_string=lambda value: value.strip(),
        get_payment_collection_pricing=lambda: pricing or {},
    )


@pytest.mark.parametrize("legacy_percentage", [1.95, 0])
def test_three_installments_use_shared_margin_not_legacy_school_percentage(legacy_percentage):
    payload = make_instructions(make_settings(legacy_percentage, installments=True))
    full_code = next(code for code in payload["payment_codes"] if code["payment_category"].get("tuition_payment_option") == "full_remaining")
    assert full_code["reference_code"] == "ST01-TUIT-FULL"
    assert full_code["base_amount"] == 75
    assert full_code["total_amount"] == 77.26
    assert full_code["payment_category"]["payment_label"] == "Full Remaining Tuition"
    codes = [code for code in payload["payment_codes"] if code["payment_category"].get("installment_number")]
    assert len(codes) == 3
    for index, code in enumerate(codes, start=1):
        assert code["reference_code"] == f"ST01-TUIT-I{index}"
        assert code["base_amount"] == code["cash_amount"] == 25
        assert code["amount"] == code["total_amount"] == 25.76
        assert code["platform_fee_amount"] == 0.25
        assert code["estimated_provider_fee_amount"] == 0.50
        assert code["convenience_fee_amount"] == 0.76
        assert code["rounding_surplus_amount"] == 0.01
        assert code["fee_model"] == code["payment_category"]["fee_model"] == "gross_up_margin_v1"
        assert code["pricing_override"] == get_tuition_collection_pricing()
        assert "1.95% convenience fee" not in code["instructions"]
    assert payload["fees_configuration"]["tuition_transfer_pricing"] == get_tuition_collection_pricing()
    assert payload["fees_configuration"]["tuition_platform_margin_rate_pct"] == 1
    assert payload["school_payment_account"]["bank_account"] is None


@pytest.mark.parametrize("legacy_percentage", [1.95, 0])
def test_full_tuition_and_school_preview_share_pricing(legacy_percentage):
    settings = make_settings(legacy_percentage)
    school_payload = get_school_fees_payload(
        "TEST", school_settings_model=SimpleNamespace(query=QueryStub(settings)),
        get_feeding_plan_fees=feeding_fees,
    )
    preview = calculate_payment_collection_breakdown(
        school_payload["tuition_fee"], school_payload["tuition_transfer_pricing"],
    )
    payload = make_instructions(settings)
    code = payload["payment_codes"][0]
    for field in (
        "base_amount", "total_amount", "platform_fee_amount", "convenience_fee_amount",
        "estimated_provider_fee_amount", "rounding_surplus_amount", "fee_model",
    ):
        assert code[field] == preview[field]
    assert code["total_amount"] == 77.26
    assert code["platform_fee_amount"] == 0.75
    assert code["estimated_provider_fee_amount"] == 1.51
    assert school_payload["tuition_convenience_fee_percentage"] == legacy_percentage
    assert school_payload["other_fees"] == {"Library": 2.0}
    library_code = payload["payment_codes"][1]
    assert library_code["amount"] == 2
    assert library_code["platform_fee_amount"] == library_code["convenience_fee_amount"] == 0


def test_instruction_pricing_override_uses_platform_configuration():
    pricing = {"tuition_provider_fee_rate_pct": 2.5, "tuition_platform_margin_rate_pct": 1.5}
    code = make_instructions(make_settings(), pricing)["payment_codes"][0]
    expected_pricing = get_tuition_collection_pricing(pricing)
    assert code["pricing_override"] == expected_pricing
    assert code["total_amount"] == calculate_payment_collection_breakdown(75, expected_pricing)["total_amount"]


def make_intent(code, status="assigned", pricing=None, **overrides):
    values = {
        "id": 1, "provider": "paystack", "collection_channel": "dedicated_virtual_account",
        "intent_status": status, "reference_code": code["reference_code"], "payment_type": "Tuition",
        "currency": "GHS", "provider_bank_name": "Test Bank", "provider_bank_slug": "test-bank",
        "provider_account_name": "Test Learner", "provider_account_number": "1234567890",
        "provider_subaccount_code": "ACCT_TEST", "provider_customer_code": "CUS_TEST",
        "expires_at": None, "paid_at": None,
        "meta": {"pricing": pricing if pricing is not None else code["pricing_override"]},
    }
    for field in ("base_amount", "total_amount", "convenience_fee_amount", "estimated_provider_fee_amount", "platform_fee_amount"):
        values[field] = code[field]
    values.update(overrides)
    return SimpleNamespace(**values)


def attach_intent(code, intent):
    attach_virtual_routes_to_payment_codes(
        SimpleNamespace(id=1), [code],
        lambda student: {code["reference_code"]: intent},
        lambda intent: build_payment_collection_intent_payload(intent, lambda value: value.strip()),
    )


def test_matching_assigned_current_model_account_is_reused():
    code = next(code for code in make_instructions(make_settings(installments=True))["payment_codes"] if code["payment_category"].get("installment_number") == 1)
    intent = make_intent(code)
    attach_intent(code, intent)
    assert code["has_virtual_route"] is True
    assert code["needs_virtual_route_preparation"] is False
    assert code["preferred_payment_model"] == "virtual_account_ready"
    assert code["virtual_bank_account"] == "1234567890"
    assert code["virtual_route"]["fee_model"] == "gross_up_margin_v1"
    assert code["virtual_route"]["rounding_surplus_amount"] == 0.01


@pytest.mark.parametrize("overrides", [
    {"pricing": {}},
    {"total_amount": 76.46},
    {"base_amount": 74},
    {"convenience_fee_amount": 1.46},
    {"estimated_provider_fee_amount": 1.46},
    {"platform_fee_amount": 0},
])
def test_stale_assigned_account_hidden_and_requires_preparation(overrides):
    code = make_instructions(make_settings())["payment_codes"][0]
    intent = make_intent(code, **overrides)
    attach_intent(code, intent)
    assert code["has_virtual_route"] is False
    assert code["virtual_route"] is None
    assert code["virtual_bank_account"] is None
    assert code["virtual_bank_name"] is None
    assert code["subaccount_code"] is None
    assert code["needs_virtual_route_preparation"] is True
    assert intent.intent_status == "assigned"
    assert intent.provider_account_number == "1234567890"


def test_paid_legacy_account_remains_historical_not_new_payable_route():
    code = make_instructions(make_settings())["payment_codes"][0]
    intent = make_intent(code, status="paid", pricing={})
    attach_intent(code, intent)
    assert code["virtual_route"] is None
    assert code["virtual_bank_account"] is None
    assert code["has_virtual_route"] is False
    assert code["needs_virtual_route_preparation"] is False
    assert code["preferred_payment_model"] == "historical_paid"
    assert intent.intent_status == "paid"
    assert build_payment_collection_intent_payload(intent, lambda value: value)["rounding_surplus_amount"] == 0


def test_legacy_percentage_is_preserved_without_changing_new_pricing():
    settings = make_settings(legacy_percentage=0)
    commits = []
    update_school_fees(
        {"other_fees": {"Library": "3.5"}, "tuition_installment_plan": {"enabled": True, "installment_count": 3}},
        "TEST", 1, school_settings_model=SimpleNamespace(query=QueryStub(settings)),
        set_feeding_plan_fees=lambda *args: None, log_action=lambda *args: None,
        db_session=SimpleNamespace(commit=lambda: commits.append(True)),
    )
    assert commits == [True]
    assert settings.other_fees[TUITION_CONVENIENCE_FEE_KEY] == 0
    assert [item["amount"] for item in settings.other_fees[TUITION_INSTALLMENT_PLAN_KEY]["schedule"]] == [25, 25, 25]
    payload = get_school_fees_payload(
        "TEST", school_settings_model=SimpleNamespace(query=QueryStub(settings)),
        get_feeding_plan_fees=feeding_fees,
    )
    assert payload["other_fees"] == {"Library": 3.5}
    assert payload["tuition_transfer_pricing"] == get_tuition_collection_pricing()


def test_invalid_installment_sum_still_rejected():
    settings = make_settings()
    with pytest.raises(TuitionInstallmentPlanValidationError, match="add up exactly"):
        update_school_fees(
            {"tuition_installment_plan": {
                "enabled": True, "installment_count": 3,
                "schedule": [{"amount": 25}, {"amount": 25}, {"amount": 24}],
            }},
            "TEST", 1, school_settings_model=SimpleNamespace(query=QueryStub(settings)),
            set_feeding_plan_fees=lambda *args: None, log_action=lambda *args: None,
            db_session=SimpleNamespace(commit=lambda: pytest.fail("Invalid schedule must not commit")),
        )


class PaymentQueryStub:
    def __init__(self, payments):
        self.payments = payments

    def filter_by(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.payments


def make_paid_instructions(paid_amounts, owed=0):
    payments = [
        SimpleNamespace(amount=amount, status="Confirmed", payment_category={}, date_paid=None, id=index)
        for index, amount in enumerate(paid_amounts, start=1)
    ]
    payment_model = SimpleNamespace(
        query=PaymentQueryStub(payments), date_paid=SimpleNamespace(asc=lambda: None), id=SimpleNamespace(asc=lambda: None),
    )
    student = SimpleNamespace(
        id=1, school_id="TEST", student_code="ST01", name="Learner", current_class="Class 1",
        parent_name="Parent", parent_phone=None, parent_email=None,
        total_tuition_owed=owed, is_on_scholarship=False, scholarship_covers_tuition=False,
    )
    payload = build_student_payment_instruction_payload(
        student=student, school_id="TEST",
        school_model=SimpleNamespace(query=QueryStub(None)),
        school_settings_model=SimpleNamespace(query=QueryStub(make_settings())), payment_model=payment_model,
        generate_all_payment_codes=lambda student_code, fees: {"Tuition": "ST01-TUIT"},
        get_school_admission_fee_config=lambda settings: {}, get_feeding_plan_fees=feeding_fees,
        attach_virtual_routes_to_payment_codes_fn=lambda student, codes: attach_virtual_routes_to_payment_codes(
            student, codes, lambda student: {}, lambda intent: None,
        ),
        get_payment_provider_settings=lambda settings: {"paystack_subaccount_code": "ACCT_TEST"},
        paystack_dva_supported_countries={"GH"}, sanitize_string=lambda value: value.strip(),
        get_payment_collection_pricing=lambda: {},
    )
    return payload["payment_codes"][0]


def test_unbilled_balance_tuition_reference_subtracts_confirmed_payments():
    code = make_paid_instructions([30])
    assert code["base_amount"] == 45
    assert code["payment_category"]["tuition_status"] == "open"
    assert code["needs_virtual_route_preparation"] is True


def test_fully_paid_tuition_reference_needs_no_new_transfer_account():
    code = make_paid_instructions([50, 25])
    assert code["base_amount"] == 0
    assert code["total_amount"] == 0
    assert code["payment_category"]["tuition_status"] == "paid"
    assert code["needs_virtual_route_preparation"] is False
    assert "fully settled" in code["instructions"]


def test_explicit_outstanding_balance_still_wins():
    code = make_paid_instructions([30], owed=120)
    assert code["base_amount"] == 120
import math

import pytest

from backend.payment_workflow import calculate_payment_collection_breakdown


def test_tuition_gross_up_covers_school_provider_and_one_percent_margin():
    result = calculate_payment_collection_breakdown(25, {
        "fee_model": "gross_up_margin_v1",
        "estimated_provider_fee_rate_pct": 1.95,
        "platform_margin_rate_pct": 1,
    })
    assert result["total_amount"] == 25.76
    assert result["base_amount"] == 25
    assert result["platform_fee_amount"] == 0.25
    assert result["estimated_provider_fee_amount"] == 0.50
    assert result["convenience_fee_amount"] == 0.76
    assert result["rounding_surplus_amount"] == 0.01


@pytest.mark.parametrize("amount", [0, 0.01, 1, 25, 75, 100, 1000, 25000])
def test_cent_rounding_never_underfunds_the_school_or_margin(amount):
    result = calculate_payment_collection_breakdown(amount, {"fee_model": "gross_up_margin_v1"})
    assert round(result["total_amount"] - result["estimated_provider_fee_amount"] - result["base_amount"], 2) >= result["platform_fee_amount"]


@pytest.mark.parametrize("rate", [-1, 100, 101, math.inf, math.nan])
def test_invalid_provider_rates_are_rejected(rate):
    with pytest.raises(ValueError):
        calculate_payment_collection_breakdown(25, {"fee_model": "gross_up_margin_v1", "estimated_provider_fee_rate_pct": rate})


def test_legacy_payment_pricing_remains_unchanged():
    result = calculate_payment_collection_breakdown(25, {"estimated_provider_fee_rate_pct": 1.95})
    assert result["total_amount"] == 25.49
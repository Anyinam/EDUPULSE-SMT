from backend.payment_workflow import (
    build_intent_customer_email,
    first_valid_customer_email,
    normalize_paystack_customer_phone,
)


def _sanitize(value):
    return value


def test_phone_normalization_handles_local_and_formatted_numbers():
    assert normalize_paystack_customer_phone("024 412 3456") == "+233244123456"
    assert normalize_paystack_customer_phone("+233-24-412-3456") == "+233244123456"
    assert normalize_paystack_customer_phone("00233244123456") == "+233244123456"
    assert normalize_paystack_customer_phone("244123456") == "+233244123456"
    assert normalize_paystack_customer_phone("08031234567", country_code="NG") == "+2348031234567"


def test_phone_normalization_falls_back_to_next_valid_candidate():
    assert normalize_paystack_customer_phone("n/a", "", "0302123456") == "+233302123456"
    assert normalize_paystack_customer_phone("12", None) == ""


def test_customer_email_skips_malformed_parent_email():
    assert first_valid_customer_email(" ama@gmail ", "office@school.edu.gh") == "office@school.edu.gh"
    assert first_valid_customer_email(None, "bad") == ""


def test_customer_email_keeps_local_part_within_limit():
    email = build_intent_customer_email(
        "kwame.mensah.asante.family.account@gmail.com",
        "TESTSCHOOL12",
        "EDU-TESTSCHOOL12-000123-TUITION-2026-T1-INSTALLMENT-2",
        _sanitize,
    )
    local_part, domain = email.split("@")
    assert domain == "gmail.com"
    assert len(local_part) <= 64
    assert local_part.startswith("kwame.mensah")

    fallback = build_intent_customer_email("", "TESTSCHOOL12", "EDU-TESTSCHOOL12-000123-TUITION-2026-T1-INSTALLMENT-2", _sanitize)
    assert fallback.endswith("@parents.edupulse.invalid")
    assert len(fallback.split("@")[0]) <= 64


def test_customer_email_is_stable_per_reference():
    first = build_intent_customer_email("Parent@Example.com", "S1", "REF-1", _sanitize)
    assert first == build_intent_customer_email("Parent@Example.com", "S1", "REF-1", _sanitize)
    assert first == "Parent+edupulse-s1-ref-1@example.com"

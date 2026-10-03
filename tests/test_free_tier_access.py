from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def proprietor_headers(app, test_proprietor):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    return {"Authorization": f"Bearer {token}", "X-School-ID": test_proprietor.school_id}


@pytest.mark.parametrize("path", [
    "/api/finance/dashboard",
])
def test_expired_trial_blocks_payment_reads(client, db, test_school, proprietor_headers, path):
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()

    response = client.get(path, headers=proprietor_headers)

    assert response.status_code == 409
    assert response.get_json()["reason"] == "feature_unavailable"


def test_free_dashboard_redacts_payment_data(client, db, test_school, proprietor_headers):
    test_school.subscription_plan = "Free Tier"
    db.session.commit()

    response = client.get("/api/proprietor/live-feed", headers=proprietor_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["recent_payments"] == []
    assert payload["pending_payments"] == []
    assert payload["ledger_integrity"] is None
    assert payload["stats"]["today_revenue"] is None
    assert payload["stats"]["unpaid_tuition"] is None


@pytest.mark.parametrize("path", [
    "/api/finance/confirm-payment/1",
    "/api/finance/confirm-payments/bulk",
    "/api/finance/paystack/recover-reference",
])
def test_free_payment_actions_block_before_mutation(client, db, test_school, proprietor_headers, path):
    test_school.subscription_plan = "Free Tier"
    db.session.commit()

    response = client.post(path, headers=proprietor_headers, json={})

    assert response.status_code == 409
    assert response.get_json()["reason"] == "feature_unavailable"


def test_free_class_limit_and_usage(client, db, test_school, proprietor_headers):
    from backend.api.models import AcademicClass

    test_school.subscription_plan = "Free Tier"
    db.session.add(AcademicClass(school_id=test_school.id, name="JHS 1"))
    db.session.commit()

    response = client.post("/api/school/classes", headers=proprietor_headers, json={"name": "JHS 2"})

    assert response.status_code == 403
    assert response.get_json()["error"] == "class_limit_reached"
    assert AcademicClass.query.filter_by(school_id=test_school.id).count() == 1
    subscription = client.get("/api/school/subscription", headers=proprietor_headers).get_json()
    assert subscription["usage"]["classes"] == "1 / 1"


def test_free_staff_quota_excludes_proprietor(client, db, test_school, proprietor_headers):
    from backend.api.models import User

    test_school.subscription_plan = "Free Tier"
    for index in range(3):
        db.session.add(User(school_id=test_school.id, username=f"quota{index}", role="teacher", password_hash="test-only-hash"))
    db.session.commit()

    response = client.post("/api/staff/add", headers=proprietor_headers, json={
        "username": "fourth", "email": "fourth@example.com", "role": "teacher",
    })

    assert response.status_code == 403
    assert response.get_json()["error"] == "staff_limit_reached"
    assert response.get_json()["current_count"] == 3
    assert User.query.filter_by(school_id=test_school.id, username="fourth").first() is None


def test_free_insights_do_not_expose_financial_analysis(client, db, test_school, proprietor_headers):
    test_school.subscription_plan = "Free Tier"
    db.session.commit()

    response = client.get("/api/proprietor/ai-insights", headers=proprietor_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"]["total_debt"] is None
    assert payload["summary"]["revenue_this_week"] is None
    assert not any(item["title"] == "Outstanding Debts" for item in payload["insights"])
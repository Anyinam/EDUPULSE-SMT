from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import Payment
from backend.subscription_features import get_school_feature_level, school_has_addon


@pytest.mark.parametrize("active", [True, False])
def test_implicit_feature_checks_resolve_active_trial_and_expiry(active):
    school = SimpleNamespace(
        subscription_plan="Free Tier",
        trial_plan="Premium",
        trial_end_date=datetime.now(timezone.utc) + timedelta(days=1 if active else -1),
        settings=SimpleNamespace(enabled_modules={"ai_pack_addon": True, "automation_pack_addon": True}),
    )
    assert get_school_feature_level(school, "payment_tracking") is active
    assert get_school_feature_level(school, "advanced_analytics") is active
    assert get_school_feature_level(school, "student_rescue_agent") is active
    assert school_has_addon(school, "ai_pack") is active
    assert school_has_addon(school, "automation_pack") is active


def test_trial_live_feed_and_finance_totals_agree(client, app, db, test_school, test_proprietor, test_students):
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=5)
    db.session.add(Payment(school_id=test_school.id, student_id=test_students[0].id, amount=21, payment_type="Tuition", method="Cash", status="Confirmed", date_paid=datetime.now(timezone.utc)))
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    headers = {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}

    live = client.get("/api/proprietor/live-feed", headers=headers)
    finance = client.get("/api/finance/dashboard", headers=headers)

    assert live.status_code == finance.status_code == 200
    assert live.get_json()["stats"]["monthly_revenue"] == finance.get_json()["monthly_revenue"] == 21
    assert len(live.get_json()["recent_payments"]) == 1

    test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()
    assert client.get("/api/proprietor/live-feed", headers=headers).get_json()["stats"]["monthly_revenue"] is None
from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import Payment, School, SchoolVerification, Student


@pytest.mark.parametrize("restriction", ["free", "expired_trial", "over_cap", "unverified", "suspended"])
def test_receipts_remain_accessible_without_collection(client, app, db, test_school, test_proprietor, test_students, restriction):
    test_school.subscription_plan = "Free Tier"
    if restriction == "expired_trial":
        test_school.trial_plan = "Premium"
        test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    elif restriction == "over_cap":
        for index in range(51):
            db.session.add(Student(school_id=test_school.id, first_name="Student", surname=str(index), name=f"Student {index}", current_class="JHS 1", status="Active"))
    elif restriction == "unverified":
        SchoolVerification.query.filter_by(school_id=test_school.id).delete()
    elif restriction == "suspended":
        test_school.is_active = False
    payment = Payment(school_id=test_school.id, student_id=test_students[0].id, amount=20, payment_type="Tuition", method="Cash", status="Confirmed", payment_category={"provider_account_number": "private", "applied_school_fee_amount": 0})
    db.session.add(payment)
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    headers = {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}

    response = client.get("/api/finance/receipts", headers=headers)

    assert response.status_code == 200
    receipt = response.get_json()["receipts"][0]
    assert receipt["receipt_number"] == f"RCPT-{payment.id}"
    assert receipt["display_amount"] == 20
    assert receipt["applied_amount"] == 0
    assert "payment_category" not in receipt
    assert "provider_account_number" not in receipt
    assert client.get("/api/finance/dashboard", headers=headers).status_code in {402, 403, 409}


def test_receipt_archive_requires_authentication_and_tenant_binding(client, app, db, test_school, test_proprietor):
    assert client.get("/api/finance/receipts", headers={"X-School-ID": test_school.id}).status_code == 401
    db.session.add(School(id="OTHER", name="Other School"))
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    assert client.get("/api/finance/receipts", headers={"Authorization": f"Bearer {token}", "X-School-ID": "OTHER"}).status_code == 403
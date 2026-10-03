from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import Payment, SchoolVerification, Student


@pytest.mark.parametrize("restriction", ["expired_trial", "unverified", "over_cap", "suspended"])
def test_historical_records_survive_free_restrictions(client, app, db, test_school, test_proprietor, test_students, restriction):
    test_school.subscription_plan = "Free Tier"
    test_school.trial_plan = "Premium"
    test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    if restriction == "unverified":
        SchoolVerification.query.filter_by(school_id=test_school.id).delete()
    elif restriction == "over_cap":
        for index in range(51):
            db.session.add(Student(school_id=test_school.id, first_name="Archive", surname=str(index), name=f"Archive {index}", current_class="JHS 1", status="Active"))
    elif restriction == "suspended":
        test_school.is_active = False
    student = test_students[0]
    payment = Payment(school_id=test_school.id, student_id=student.id, amount=25, payment_type="Tuition", method="Cash", status="Confirmed")
    db.session.add(payment)
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    headers = {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}

    history = client.get(f"/api/students/{student.id}/payments", headers=headers)
    assert history.status_code == 200
    assert history.get_json()[0]["id"] == payment.id
    transactions = client.get("/api/finance/transactions", headers=headers)
    assert transactions.status_code == 200
    assert transactions.get_json()[0]["id"] == payment.id
    for path in ["/api/finance/audit/ledger", "/api/finance/audit/summary", "/api/finance/audit/events", "/api/finance/receipts"]:
        assert client.get(path, headers=headers).status_code == 200
    assert client.post("/api/finance/receive-payment", json={"student_id": student.id, "amount": 10, "type": "Tuition", "method": "Cash"}, headers=headers).status_code in {402, 403, 409}
    assert Payment.query.get(payment.id).status == "Confirmed"
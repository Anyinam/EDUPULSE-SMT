from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager, create_access_token

from backend import middleware


OPERATIONS = [
    ("POST", "/api/homeroom/attendance", "attendance"),
    ("POST", "/api/homeroom/attendance/batch", "attendance"),
    ("POST", "/api/homeroom/attendance/bulk", "attendance"),
    ("POST", "/api/admissions/students/bulk-update-status", "bulk_operations"),
    ("POST", "/api/staff/bulk-upload", "bulk_operations"),
    ("GET", "/api/inventory", "payment_tracking"),
    ("GET", "/api/inventory/export", "payment_tracking"),
    ("GET", "/api/inventory/transactions", "payment_tracking"),
    ("POST", "/api/inventory/item", "payment_tracking"),
    ("GET", "/api/staff/my-lesson-notes", "lesson_notes"),
    ("GET", "/api/headmaster/lesson-notes", "lesson_notes"),
    ("POST", "/api/staff/lesson-note", "lesson_notes"),
    ("POST", "/api/headmaster/lesson-note/1/review", "lesson_notes"),
    ("POST", "/api/headmaster/lesson-note/1/rescore", "lesson_notes"),
]


@pytest.fixture
def guarded_client(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="operational-test-secret-key-long-enough")
    JWTManager(app)
    school = SimpleNamespace(
        id="OPS-001", subscription_plan="Free Tier", trial_plan=None,
        trial_end_date=None, subscription_status="Active", is_active=True,
        next_billing_date=None,
        settings=SimpleNamespace(enabled_modules={}),
    )
    user = SimpleNamespace(id=1, school_id=school.id)
    monkeypatch.setattr(middleware, "School", SimpleNamespace(query=SimpleNamespace(get=lambda key: school)))
    monkeypatch.setattr(middleware, "User", SimpleNamespace(query=SimpleNamespace(get=lambda key: user)))

    @app.route("/api/<path:operation>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    @middleware.multi_tenant_guard
    def operation_handler(operation):
        return jsonify(reached_handler=True)

    with app.app_context():
        token = create_access_token(identity=str(user.id))
    headers = {"X-School-ID": school.id, "Authorization": f"Bearer {token}"}
    return app.test_client(), school, headers


@pytest.mark.parametrize("method,path,feature", OPERATIONS)
@pytest.mark.parametrize("state", ["free", "expired_trial", "Basic", "Premium", "School OS", "active_trial"])
def test_operational_entitlements(guarded_client, method, path, feature, state):
    client, school, headers = guarded_client
    if state in {"expired_trial", "active_trial"}:
        school.trial_plan = "Premium"
        offset = -1 if state == "expired_trial" else 1
        school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=offset)
        school.settings.enabled_modules = {"ai_pack_addon": True, "automation_pack_addon": True}
    elif state != "free":
        school.subscription_plan = state

    response = client.open(path, method=method, headers=headers, json={})
    if state in {"free", "expired_trial"}:
        assert response.status_code == 403
        payload = response.get_json()
        assert feature in payload["message"]
        assert not payload.get("reached_handler")
        if feature in {"attendance", "feeding"}:
            assert payload["required"] == "full_access"
            assert payload["current"] == "view_only"
        else:
            assert payload["current_plan"] == "Free Tier"
            assert payload["required_plan"] == "School OS"
    else:
        assert response.status_code == 200
        assert response.get_json()["reached_handler"] is True


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/homeroom/attendance"),
    ("GET", "/api/canteen/daily-count"),
    ("GET", "/api/kitchen/dashboard"),
    ("POST", "/api/admissions/admit"),
    ("POST", "/api/admissions/applications/1/review"),
    ("POST", "/api/homeroom/terminal-report"),
    ("POST", "/api/school/terms/import-national-calendar"),
    ("POST", "/api/finance/webhook/paystack"),
    ("POST", "/api/finance/receive-payment"),
    ("GET", "/api/inventory-other"),
])
def test_unrelated_routes_remain_accessible(guarded_client, method, path):
    client, school, headers = guarded_client
    response = client.open(path, method=method, headers=headers, json={})
    assert response.status_code == 200


def test_tenant_binding_precedes_entitlement_denial(guarded_client):
    client, school, headers = guarded_client
    school.id = "OTHER"
    headers["X-School-ID"] = "OTHER"
    response = client.get("/api/inventory", headers=headers)
    assert response.status_code == 403
    assert "does not belong" in response.get_json()["message"]


@pytest.mark.parametrize("field", ["feeding_fee", "feeding_daily_fee", "feeding_weekly_fee", "feeding_monthly_fee"])
@pytest.mark.parametrize("state", ["free", "expired_trial", "Basic", "active_trial"])
def test_feeding_edits_require_full_access(guarded_client, field, state):
    client, school, headers = guarded_client
    if state == "Basic":
        school.subscription_plan = "Basic"
    elif state in {"expired_trial", "active_trial"}:
        school.trial_plan = "Premium"
        offset = -1 if state == "expired_trial" else 1
        school.trial_end_date = datetime.now(timezone.utc) + timedelta(days=offset)
    response = client.post("/api/school/fees", headers=headers, json={field: 0, "tuition_fee": 100})
    if state in {"free", "expired_trial"}:
        assert response.status_code == 403
        assert response.get_json() == {
            "message": "Insufficient access level for 'feeding'",
            "required": "full_access", "current": "view_only",
        }
    else:
        assert response.status_code == 200


@pytest.mark.parametrize("method,payload", [("POST", {"tuition_fee": 100}), ("POST", {}), ("GET", None)])
def test_other_fee_workflows_remain_accessible(guarded_client, method, payload):
    client, school, headers = guarded_client
    response = client.open("/api/school/fees", method=method, headers=headers, json=payload)
    assert response.status_code == 200


@pytest.mark.parametrize("method,path,feature", OPERATIONS)
@pytest.mark.parametrize("expired_trial", [False, True])
def test_real_routes_deny_free_operations(client, test_proprietor, test_school, db, method, path, feature, expired_trial):
    test_school.subscription_plan = "Free Tier"
    if expired_trial:
        test_school.trial_plan = "Premium"
        test_school.trial_end_date = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()
    token = create_access_token(identity=str(test_proprietor.id))
    headers = {"X-School-ID": test_school.id, "Authorization": f"Bearer {token}"}
    response = client.open(path, method=method, headers=headers, json={})
    assert response.status_code == 403
    assert feature in response.get_json()["message"]


def test_paid_attendance_write_and_free_denial(client, test_proprietor, test_school, test_students, db):
    token = create_access_token(identity=str(test_proprietor.id))
    headers = {"X-School-ID": test_school.id, "Authorization": f"Bearer {token}"}
    student = test_students[0]
    test_school.subscription_plan = "Basic"
    student.is_present = False
    db.session.commit()
    response = client.post("/api/homeroom/attendance", headers=headers, json={"student_id": student.id, "status": True})
    assert response.status_code == 200
    db.session.refresh(student)
    assert student.is_present is True

    test_school.subscription_plan = "Free Tier"
    db.session.commit()
    response = client.post("/api/homeroom/attendance", headers=headers, json={"student_id": student.id, "status": False})
    assert response.status_code == 403
    db.session.refresh(student)
    assert student.is_present is True


@pytest.mark.parametrize("plan", ["Basic", "Premium"])
@pytest.mark.parametrize("path", [
    "/api/inventory", "/api/inventory/transactions", "/api/headmaster/lesson-notes",
])
def test_paid_real_read_routes(client, test_proprietor, test_school, db, plan, path):
    test_school.subscription_plan = plan
    db.session.commit()
    token = create_access_token(identity=str(test_proprietor.id))
    response = client.get(path, headers={
        "X-School-ID": test_school.id, "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.get_json() == []


def test_real_feeding_edit_and_free_read_only(client, test_proprietor, test_school, db):
    test_school.subscription_plan = "Basic"
    db.session.commit()
    token = create_access_token(identity=str(test_proprietor.id))
    headers = {"X-School-ID": test_school.id, "Authorization": f"Bearer {token}"}
    response = client.post("/api/school/fees", headers=headers, json={"feeding_fee": 25})
    assert response.status_code == 200
    db.session.refresh(test_school.settings)
    assert test_school.settings.feeding_fee == 25

    test_school.subscription_plan = "Free Tier"
    db.session.commit()
    response = client.post("/api/school/fees", headers=headers, json={"feeding_fee": 50})
    assert response.status_code == 403
    db.session.refresh(test_school.settings)
    assert test_school.settings.feeding_fee == 25
    assert client.get("/api/school/fees", headers=headers).status_code == 200
    response = client.post("/api/school/fees", headers=headers, json={"tuition_fee": 100})
    assert response.status_code == 200
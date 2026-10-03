from flask_jwt_extended import create_access_token

from backend.api.models import AcademicClass, Student, User


def test_active_report_classes_exclude_inactive_and_unused_classes(client, app, db, test_school, test_proprietor):
    db.session.add_all([
        AcademicClass(school_id=test_school.id, name="Nursery"),
        AcademicClass(school_id=test_school.id, name="JHS 3"),
        AcademicClass(school_id=test_school.id, name="Primary 2 Blue"),
        Student(school_id=test_school.id, first_name="Active", surname="Student", name="Active Student", current_class="Primary 2 Blue", status="Active"),
        Student(school_id=test_school.id, first_name="Former", surname="Student", name="Former Student", current_class="JHS 3", status="Graduated"),
    ])
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    headers = {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}

    response = client.get("/api/school/classes?active_only=true", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == [{"name": "Primary 2 Blue", "class_name": "Primary 2 Blue"}]
    assert len(client.get("/api/school/classes", headers=headers).get_json()) == 3
    roster = client.get("/api/students/by-class/Primary%202%20Blue", headers=headers)
    assert roster.status_code == 200
    assert roster.get_json()[0]["name"] == "Active Student"


def test_active_legacy_class_without_setup_record_is_usable(client, app, db, test_school, test_proprietor):
    db.session.add(Student(school_id=test_school.id, first_name="Legacy", surname="Student", name="Legacy Student", current_class="Primary 4 Red", status="active"))
    db.session.commit()
    with app.app_context():
        token = create_access_token(identity=str(test_proprietor.id))
    headers = {"Authorization": f"Bearer {token}", "X-School-ID": test_school.id}

    assert client.get("/api/school/classes?active_only=true", headers=headers).get_json() == [{"name": "Primary 4 Red", "class_name": "Primary 4 Red"}]
    response = client.get("/api/students/by-class/Primary%204%20Red", headers=headers)
    assert response.status_code == 200
    assert response.get_json()[0]["name"] == "Legacy Student"
    assert client.get("/api/students/by-class/Unknown%20Class", headers=headers).status_code == 400


def test_kitchen_staff_never_add_to_staff_meal_count(client, app, db, test_school, test_proprietor):
    from backend.routes import _get_daily_meal_breakdown

    for username, role, roles in [
        ("kitchen_primary", "kitchen", ["kitchen"]),
        ("kitchen_teacher", "teacher", ["teacher", "kitchen"]),
        ("kitchen_finance", "finance", ["finance", "kitchen"]),
        ("meal_teacher", "teacher", ["teacher"]),
    ]:
        db.session.add(User(school_id=test_school.id, username=username, role=role, roles=roles, password_hash="test-hash"))
    db.session.commit()

    breakdown = _get_daily_meal_breakdown(test_school.id)

    assert breakdown["total_staff_meals"] == 2
    assert breakdown["total_meals_needed"] == breakdown["covered_student_meals"] + 2
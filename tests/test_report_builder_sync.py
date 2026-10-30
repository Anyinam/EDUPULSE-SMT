from datetime import date, timedelta

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import AcademicTerm, ReportCard, School, Student, StudentGrade, User, db


def _headers(app, school_id, user_id):
    with app.app_context():
        token = create_access_token(identity=str(user_id))
    return {"Authorization": f"Bearer {token}", "X-School-ID": school_id}


@pytest.fixture
def classroom(test_school):
    subject_teacher = User(username="sync_subject", password_hash="hash", role="teacher", school_id=test_school.id)
    homeroom_teacher = User(
        username="sync_homeroom", password_hash="hash", role="teacher",
        school_id=test_school.id, assigned_class="JHS 1",
    )
    students = [
        Student(school_id=test_school.id, first_name="Ama", surname="Boateng", name="Ama Boateng", student_code="SYN001", current_class="JHS 1"),
        Student(school_id=test_school.id, first_name="Kofi", surname="Asare", name="Kofi Asare", student_code="SYN002", current_class="JHS 1"),
    ]
    today = date.today()
    term = AcademicTerm(
        school_id=test_school.id, name="Term 2", academic_year="2025/2026",
        start_date=today - timedelta(days=30), end_date=today + timedelta(days=30), is_active=True,
    )
    db.session.add_all([subject_teacher, homeroom_teacher, term, *students])
    db.session.commit()
    yield {"subject": subject_teacher, "homeroom": homeroom_teacher, "students": students, "term": term}

    ids = [s.id for s in students]
    ReportCard.query.filter(ReportCard.student_id.in_(ids)).delete(synchronize_session=False)
    StudentGrade.query.filter(StudentGrade.student_id.in_(ids)).delete(synchronize_session=False)
    for obj in [*students, subject_teacher, homeroom_teacher, term]:
        db.session.delete(obj)
    db.session.commit()


def _submit(client, app, school_id, teacher, subject, scores):
    return client.post(
        "/api/teacher/submit-grades-to-homeroom",
        headers=_headers(app, school_id, teacher.id),
        json={"class_name": "JHS 1", "subject": subject, "grade_data": scores},
    )


def test_submitted_grades_land_in_draft_report_for_active_term(client, app, test_school, classroom):
    ama, kofi = classroom["students"]

    response = _submit(client, app, test_school.id, classroom["subject"], "Mathematics", {
        str(ama.id): {"class_score": 25, "exam_score": 60},
        str(kofi.id): {"class_score": 20, "exam_score": 50},
    })
    assert response.status_code == 200
    sync = response.get_json()["report_builder"]
    assert sync["academic_term"] == "Term 2"
    assert sync["academic_year"] == "2025/2026"
    assert sync["reports_created"] == 2

    report = client.get(
        f"/api/homeroom/report-builder/report/{ama.id}?academic_term=Term 2&academic_year=2025/2026",
        headers=_headers(app, test_school.id, classroom["homeroom"].id),
    ).get_json()
    assert report["status"] == "Draft"
    assert [(g["subject"], g["total"]) for g in report["subject_grades"]] == [("Mathematics", 85.0)]
    assert report["overall_position"] == "1st"

    # A second subject is appended; resubmitting the first replaces it rather than duplicating.
    _submit(client, app, test_school.id, classroom["subject"], "English", {str(ama.id): {"class_score": 15, "exam_score": 40}})
    response = _submit(client, app, test_school.id, classroom["subject"], "Mathematics", {str(ama.id): {"class_score": 30, "exam_score": 70}})
    assert response.get_json()["report_builder"]["reports_updated"] == 1

    report = ReportCard.query.filter_by(student_id=ama.id, academic_term="Term 2", academic_year="2025/2026").one()
    totals = {g["subject"]: g["total"] for g in report.subject_grades}
    assert totals == {"Mathematics": 100.0, "English": 55.0}
    assert report.total_marks_obtained == 155.0


def test_submitted_reports_are_not_modified(client, app, test_school, classroom):
    ama = classroom["students"][0]
    db.session.add(ReportCard(
        school_id=test_school.id, student_id=ama.id, academic_term="Term 2", academic_year="2025/2026",
        class_name="JHS 1", status="Submitted",
        subject_grades=[{"subject": "Mathematics", "class_score": 10, "exam_score": 10, "total": 20}],
    ))
    db.session.commit()

    response = _submit(client, app, test_school.id, classroom["subject"], "Mathematics", {str(ama.id): {"class_score": 30, "exam_score": 70}})

    assert response.status_code == 200
    assert response.get_json()["report_builder"]["reports_skipped_locked"] == 1
    report = ReportCard.query.filter_by(student_id=ama.id, academic_term="Term 2").one()
    assert report.subject_grades[0]["total"] == 20


def test_rejects_students_from_another_school(client, app, test_school, classroom):
    other_school = School(id="OTHER-SYNC", name="Other School")
    db.session.add(other_school)
    db.session.flush()
    outsider = Student(school_id=other_school.id, first_name="Outside", surname="Learner", name="Outside Learner", student_code="OUT001", current_class="JHS 1")
    db.session.add(outsider)
    db.session.commit()
    try:
        response = _submit(client, app, test_school.id, classroom["subject"], "Mathematics", {
            str(outsider.id): {"class_score": 30, "exam_score": 70},
        })
        assert response.status_code == 400
        assert StudentGrade.query.filter_by(student_id=outsider.id).count() == 0
    finally:
        db.session.delete(outsider)
        db.session.delete(other_school)
        db.session.commit()


def test_free_tier_locks_report_builder_but_keeps_report_viewing(client, app, db, test_school, classroom):
    test_school.subscription_plan = "Free Tier"
    db.session.commit()
    ama = classroom["students"][0]
    headers = _headers(app, test_school.id, classroom["homeroom"].id)

    assert client.get("/api/homeroom/report-builder/students", headers=headers).status_code == 403
    assert client.get(f"/api/homeroom/report-builder/auto-fill/{ama.id}", headers=headers).status_code == 403
    assert client.post("/api/homeroom/report-builder/report", headers=headers, json={
        "student_id": ama.id, "academic_term": "Term 2", "academic_year": "2025/2026",
    }).status_code == 403
    assert client.post("/api/homeroom/report-builder/submit", headers=headers, json={"report_id": 1}).status_code == 403
    assert ReportCard.query.filter_by(student_id=ama.id).count() == 0

    # Approval and view screens still read saved reports.
    view = client.get(
        f"/api/homeroom/report-builder/report/{ama.id}?academic_term=Term 2&academic_year=2025/2026",
        headers=headers,
    )
    assert view.status_code == 404

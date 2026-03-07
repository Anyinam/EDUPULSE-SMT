"""
Pytest configuration and shared fixtures for EduPulse tests.
"""

import os
import sys
from datetime import datetime

import pytest

# Set test database URL BEFORE importing Flask app to prevent connection attempts
if "TEST_DATABASE_URL" not in os.environ:
    os.environ["TEST_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FLASK_ENV"] = "testing"
os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"
os.environ.setdefault(
    "DATA_ENCRYPTION_KEY", "Q7dG5vjXFn340xkmevogawqruIgndlsWdz4mg0PjkmI="
)


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    # Use pre-configured environment variables
    from backend.api.api import app as flask_app

    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )
    flask_app.config["JWT_SECRET_KEY"] = "test-secret-key-change-in-production"
    flask_app.config["ALLOW_ALL_DASHBOARDS"] = False

    return flask_app


@pytest.fixture(scope="session")
def db(app):
    """Create database for testing."""
    from backend.api.models import db

    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app, db):
    """Create test client with fresh database."""
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def test_school(db):
    """Create test school."""
    from backend.api.models import School, SchoolSettings

    school = School(
        id="TEST-001",
        name="Test School",
        primary_color="#1e3a8a",
        subscription_plan="Premium",
    )
    settings = SchoolSettings(school_id="TEST-001")

    db.session.add(school)
    db.session.add(settings)
    db.session.commit()

    yield school

    db.session.delete(school)
    db.session.delete(settings)
    db.session.commit()


@pytest.fixture()
def test_proprietor(db, test_school):
    """Create test proprietor user."""
    from backend.api.models import User

    user = User(
        username="proprietor1",
        school_id=test_school.id,
        role="proprietor",
        email="proprietor@test.edu",
    )
    user.set_password("PropPass123")

    db.session.add(user)
    db.session.commit()

    yield user

    db.session.delete(user)
    db.session.commit()


@pytest.fixture()
def test_teacher(db, test_school):
    """Create test teacher user."""
    from backend.api.models import User

    user = User(
        username="teacher1",
        school_id=test_school.id,
        role="teacher",
        email="teacher@test.edu",
        assigned_class="JHS 1",
    )
    user.set_password("TeacherPass123")

    db.session.add(user)
    db.session.commit()

    yield user

    db.session.delete(user)
    db.session.commit()


@pytest.fixture()
def test_headmaster(db, test_school):
    """Create test headmaster user."""
    from backend.api.models import User

    user = User(
        username="headmaster1",
        school_id=test_school.id,
        role="headmaster",
        email="headmaster@test.edu",
    )
    user.set_password("HeadmasterPass123")

    db.session.add(user)
    db.session.commit()

    yield user

    db.session.delete(user)
    db.session.commit()


@pytest.fixture()
def test_students(db, test_school):
    """Create multiple test students."""
    from backend.api.models import Student

    students = []
    for i in range(5):
        student = Student(
            school_id=test_school.id,
            first_name=f"Student{i+1}",
            surname="Test",
            name=f"Student {i+1}",
            student_code=f"S{i+1:03d}",
            current_class="JHS 1",
            total_tuition_owed=0.0,
            parent_email=f"parent{i+1}@test.edu",
            parent_phone=f"+233501234{i:03d}",
        )
        students.append(student)
        db.session.add(student)

    db.session.commit()

    yield students

    for student in students:
        db.session.delete(student)
    db.session.commit()


@pytest.fixture()
def test_auth_token(client, app, test_teacher):
    """Get JWT token for test user."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(test_teacher.id))
        return token


@pytest.fixture()
def auth_headers(test_auth_token, test_school):
    """Get authorization headers with token and school ID."""
    return {
        "Authorization": f"Bearer {test_auth_token}",
        "X-School-ID": test_school.id,
        "Content-Type": "application/json",
    }


@pytest.fixture()
def mock_email(mocker):
    """Mock email sending."""
    mock = mocker.patch("backend.routes.send_email_notification")
    return mock


@pytest.fixture()
def mock_payment_webhook(mocker):
    """Mock payment webhook processing."""
    mock = mocker.patch("backend.routes.process_payment_webhook")
    return mock


@pytest.fixture()
def mock_ai_analysis(mocker):
    """Mock AI narrative generation."""
    mock = mocker.patch("backend.utils.generate_descriptive_analysis")
    mock.return_value = "Student shows strong aptitude with consistent performance."
    return mock


# ============================================================================
# Hook: Automatically mark slow tests
# ============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# ============================================================================
# Hook: Log test execution times
# ============================================================================


def pytest_runtest_logreport(report):
    """Log test timing information."""
    if report.when == "teardown":
        if hasattr(report, "duration"):
            if report.duration > 1.0:
                print(f"\n⚠️  SLOW TEST: {report.nodeid} took {report.duration:.2f}s")


# ============================================================================
# Hook: Auto-use fixtures for security tests
# ============================================================================


@pytest.fixture(autouse=True)
def security_test_setup(monkeypatch):
    """Security setup for all tests."""
    # Ensure security headers are enabled
    monkeypatch.setenv("ALLOW_ALL_DASHBOARDS", "False")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "True")
    monkeypatch.setenv("FLASK_ENV", "testing")


# ============================================================================
# Custom Assertions
# ============================================================================


class CustomAssertions:
    """Custom assertion methods for EduPulse tests."""

    @staticmethod
    def assert_valid_terminal_report(report):
        """Assert terminal report has required fields."""
        assert "student_name" in report
        assert "student_code" in report
        assert "subjects" in report
        assert "narrative" in report
        assert isinstance(report["subjects"], list)

    @staticmethod
    def assert_valid_payment(payment):
        """Assert payment record is valid."""
        assert payment.amount > 0
        assert payment.amount <= 100000
        assert payment.status in ["Pending", "Confirmed", "Forwarded"]
        assert payment.payment_type in ["Tuition", "Feeding", "Uniform"]

    @staticmethod
    def assert_valid_grade(grade):
        """Assert grade record is valid."""
        assert 0 <= grade.total_score <= 100
        assert isinstance(grade.is_finalized, bool)


@pytest.fixture()
def assertions():
    """Provide custom assertions."""
    return CustomAssertions()

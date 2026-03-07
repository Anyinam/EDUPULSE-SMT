# EduPulse Test Suite

Comprehensive testing infrastructure for EduPulse application covering unit tests, integration tests, security tests, and performance benchmarks.

## Directory Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── test_validators.py       # Input validation schema tests (370+ lines)
├── test_api.py             # API endpoint integration tests (400+ lines)
├── test_security.py        # Security vulnerability tests (600+ lines)
├── test_integration.py     # End-to-end workflow tests (500+ lines)
└── README.md              # This file
```

## Test Categories

### 1. **test_validators.py** - Input Validation Tests
Tests for Marshmallow schema validation ensuring all inputs are sanitized and validated.

**Coverage:**
- LoginSchema validation (school_code, username, password)
- RegisterSchema validation (password strength requirements)
- StudentGradeSchema validation (class_score 0-30, exam_score 0-70)
- PaymentSchema validation (amounts 0.01-100,000, payment type enum)
- AttendanceSchema validation
- Email validation (format, domain)
- Phone validation (Ghana format: +233, 0xxx)
- Database constraint tests (payment amounts, score ranges)
- Security header verification

**Run:** `pytest tests/test_validators.py -v`

### 2. **test_api.py** - API Endpoint Tests  
Integration tests for all API endpoints with realistic workflows.

**Coverage:**
- Authentication (login, register, token validation)
- Student management (CRUD operations)
- Grade finalization (score validation, constraints)
- Payment recording (multiple payment types)
- Multi-tenant isolation (X-School-ID enforcement)
- Attendance tracking
- Authorization checks (role-based access)

**Run:** `pytest tests/test_api.py -v`

### 3. **test_security.py** - Security Vulnerability Tests
Comprehensive security tests for vulnerabilities and attack vectors.

**Coverage:**
- SQL injection prevention
- Brute force attack prevention (rate limiting)
- XSS and HTML injection prevention
- Email header injection prevention
- CSRF protection validation
- Authorization bypass attempts
- Authentication bypass tests
- Error handling (no information leakage)
- Security header verification
- Negative values and amount validation
- Duplicate payment detection
- Access control enforcement

**Run:** `pytest tests/test_security.py -v`

### 4. **test_integration.py** - Integration & Performance Tests
End-to-end workflow tests and performance benchmarks.

**Coverage:**
- Complete grade entry workflow
- Complete payment workflow
- Attendance tracking workflow
- Report generation
- Multi-student operations
- Concurrent operations
- Performance benchmarks (login < 500ms, queries < 1000ms)
- Data consistency checks
- Error recovery scenarios

**Run:** `pytest tests/test_integration.py -v`
**Run with performance tests:** `pytest tests/test_integration.py -v -m slow`

## conftest.py - Test Fixtures

Reusable fixtures for all tests:

```python
@pytest.fixture
def client:                 # Flask test client
def db:                     # Database session
def test_school:            # Pre-created test school
def test_proprietor:        # Proprietor user
def test_teacher:           # Teacher user with class assignment
def test_headmaster:        # Headmaster user
def test_students:          # 5 test students in JHS 1
def test_auth_token:        # JWT token for test user
def auth_headers:           # Headers with token + school ID
def mock_email:             # Mock email sending
def mock_payment_webhook:   # Mock webhook processing
def mock_ai_analysis:       # Mock AI narrative generation
def assertions:             # Custom assertion methods
```

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_validators.py -v
pytest tests/test_security.py -v
```

### Run Specific Test Class
```bash
pytest tests/test_api.py::TestAuthentication -v
pytest tests/test_security.py::TestMultiTenantIsolation -v
```

### Run Specific Test Method
```bash
pytest tests/test_api.py::TestAuthentication::test_valid_login -v
```

### Run with Coverage Report
```bash
pytest tests/ -v --cov=backend --cov-report=html --cov-report=term
```

### Run Only Security Tests
```bash
pytest tests/test_security.py -v -m security
```

### Run Performance Tests (marked as slow)
```bash
pytest tests/ -v -m slow
```

### Skip Performance Tests
```bash
pytest tests/ -v -m "not slow"
```

### Run Tests in Parallel
```bash
pytest tests/ -v -n auto  # Requires pytest-xdist
```

### Generate Test Report
```bash
pytest tests/ -v --html=report.html --self-contained-html
```

## Test Configuration (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    slow: Slow tests (deselect with '-m "not slow"')
    smoke: Smoke tests
```

## Coverage Goals

Target coverage for critical modules:

| Module | Target | Current |
|--------|--------|---------|
| backend/validators.py | 95% | - |
| backend/middleware.py | 90% | - |
| backend/api/api.py | 85% | - |
| backend/routes.py | 80% | - |
| backend/api/models.py | 75% | - |

**Overall Target:** 80% code coverage (excluding migrations, config)

## Test Data

### Test School
- ID: TEST-001
- Name: Test School
- Plan: Premium
- Primary Color: #1e3a8a

### Test Users
- **Proprietor:** username=proprietor1, password=PropPass123
- **Teacher:** username=teacher1, password=TeacherPass123, class=JHS 1
- **Headmaster:** username=headmaster1, password=HeadmasterPass123

### Test Students
5 students named "Student 1" - "Student 5" with:
- School: TEST-001
- Class: JHS 1
- Student Codes: S001 - S005

## Setting Up Test Environment

### 1. Install Test Dependencies
```bash
pip install -r requirements-dev.txt
```

### 2. Configure Test Database
```bash
# Uses in-memory SQLite by default
# To use PostgreSQL, set TEST_DATABASE_URL:
export TEST_DATABASE_URL=postgresql://user:password@localhost/edupulse_test
```

### 3. Run Tests
```bash
pytest tests/ -v
```

## Common Test Scenarios

### Test Grade Entry Workflow
```bash
pytest tests/test_integration.py::TestGradeEntryWorkflow -v
```

**Scenario:**
1. User authenticates (JWT token)
2. Fetches students by class
3. Enters class_score and exam_score
4. System validates and stores grades
5. Grade total calculated (class_score + exam_score)

### Test Payment Recording
```bash
pytest tests/test_integration.py::TestPaymentWorkflow -v
```

**Scenario:**
1. Selects student
2. Enters payment amount and type
3. System validates amount (0.01-100,000)
4. Records payment with reference ID
5. Updates student status (feeding_paid, tuition_owed)

### Test Security
```bash
pytest tests/test_security.py -v
```

**Scenario:**
1. Attempts SQL injection
2. Tests brute force protection
3. Validates multi-tenant isolation
4. Verifies JWT token expiry
5. Confirms security headers

### Test Concurrent Operations
```bash
pytest tests/test_integration.py::TestConcurrency -v
```

**Scenario:**
1. Multiple concurrent payments for same student
2. Concurrent grade entries
3. Simultaneous attendance records
4. System handles without conflicts

## Debugging Tests

### Run with Debug Output
```bash
pytest tests/ -v -s  # Show print statements
```

### Run with Detailed Tracebacks
```bash
pytest tests/ -v --tb=long
```

### Stop on First Failure
```bash
pytest tests/ -v -x
```

### Drop into Debugger on Failure
```bash
pytest tests/ -v --pdb
```

### Drop into Debugger on Error
```bash
pytest tests/ -v --pdb-trace
```

## Continuous Integration

GitHub Actions workflow (.github/workflows/security-tests-deploy.yml) runs:

1. **security-scan** - Bandit, Safety, Semgrep
2. **lint** - Black, isort, flake8, pylint
3. **test** - pytest with coverage (uploads to Codecov)
4. **build** - Docker build with Trivy scan
5. **dependency-check** - pip-licenses compliance
6. **deploy-production** - AWS ECS (main only)
7. **notify** - Slack + GitHub issues

Tests run on every push and pull request.

## Test Performance

| Test Suite | Duration | Count |
|------------|----------|-------|
| test_validators.py | ~2s | 30 tests |
| test_api.py | ~5s | 20 tests |
| test_security.py | ~8s | 25 tests |
| test_integration.py | ~10s | 15 tests |
| **Total** | **~25s** | **90 tests** |

## Troubleshooting

### Tests Fail with "No module named 'backend'"
```bash
# Ensure backend is in PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest tests/ -v
```

### Database Lock Errors
```bash
# Use fresh in-memory database
pytest tests/ -v --tb=short
```

### JWT Token Expired
```bash
# Tokens in tests have long expiry, check conftest.py
pytest tests/ -v -s  # Verbose output for debugging
```

### Performance Test Timeouts
```bash
# Increase timeout for slow systems
pytest tests/test_integration.py -v -m slow --timeout=300
```

## Adding New Tests

### 1. Create Test File
```python
# tests/test_feature.py
import pytest

class TestMyFeature:
    def test_something(self, client, auth_headers):
        response = client.get('/api/endpoint', headers=auth_headers)
        assert response.status_code == 200
```

### 2. Use Fixtures
```python
def test_with_students(self, test_students, auth_headers):
    for student in test_students:
        # Test with student data
        pass
```

### 3. Run New Tests
```bash
pytest tests/test_feature.py -v
```

## Best Practices

1. **Use fixtures** - Don't recreate test data in each test
2. **One assertion per test** - Makes failures clear
3. **Descriptive names** - Test names should describe what's tested
4. **No test dependencies** - Each test should work independently
5. **Mock external services** - Don't call real APIs in tests
6. **Use parametrize** - For multiple scenarios
7. **Test happy path AND sad path** - Include error cases
8. **Keep tests fast** - Mark slow tests with @pytest.mark.slow
9. **Clear error messages** - Add assertion messages: `assert x, "x should be positive"`

## Documentation

- [pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Flask Testing](https://flask.palletsprojects.com/testing/)
- [Marshmallow Documentation](https://marshmallow.readthedocs.io/)

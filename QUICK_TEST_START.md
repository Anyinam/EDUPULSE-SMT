# Quick Test Setup & Execution Guide

## 5-Minute Quick Start

### 1. Install Dependencies (1 minute)
```bash
# Activate virtual environment
source Eduenv/bin/activate          # Linux/Mac
# OR
Eduenv\Scripts\activate             # Windows

# Install testing packages
pip install -r requirements-dev.txt
```

### 2. Run Tests (2 minutes)
```bash
# Run all tests
pytest tests/ -v

# Or use the automated script
bash run_tests.sh              # Linux/Mac
run_tests.bat                  # Windows
```

### 3. View Results (2 minutes)
```bash
# Coverage report
open htmlcov/index.html        # Mac
xdg-open htmlcov/index.html    # Linux
start htmlcov\index.html       # Windows
```

---

## Common Testing Commands

### Run Specific Test Suite
```bash
pytest tests/test_validators.py -v     # Validation tests
pytest tests/test_api.py -v             # API endpoint tests
pytest tests/test_security.py -v        # Security tests
pytest tests/test_integration.py -v     # Integration tests
```

### Run Specific Test Class
```bash
pytest tests/test_api.py::TestAuthentication -v
pytest tests/test_security.py::TestMultiTenantIsolation -v
```

### Run with Coverage
```bash
pytest tests/ -v --cov=backend --cov-report=html
```

### Run Tests in Parallel (Faster)
```bash
# Requires pytest-xdist
pytest tests/ -n auto -v
```

### Skip Slow Tests
```bash
pytest tests/ -v -m "not slow"
```

### Run Only Security Tests
```bash
pytest tests/test_security.py -v
```

### Debug a Failing Test
```bash
pytest tests/test_file.py::TestClass::test_method -v -s --tb=long
```

---

## Quick Troubleshooting

### Tests Fail with "ModuleNotFoundError"
```bash
# Add current directory to Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)      # Linux/Mac
set PYTHONPATH=%PYTHONPATH%;%CD%          # Windows
pytest tests/ -v
```

### Virtual Environment Not Activated
```bash
# Linux/Mac
source Eduenv/bin/activate

# Windows
Eduenv\Scripts\activate
```

### Missing Test Dependencies
```bash
pip install -r requirements-dev.txt
```

### Tests Hang or Timeout
```bash
# Use short timeout
pytest tests/ -v --timeout=30
```

### Clear Pytest Cache
```bash
pytest --cache-clear
rm -rf .pytest_cache
pytest tests/ -v
```

---

## Test Environment Setup

### Use SQLite (Fast, Default)
```bash
export TEST_DATABASE_URL="sqlite:///:memory:"
pytest tests/ -v
```

### Use PostgreSQL (for Integration Tests)
```bash
# Create test database
psql -U postgres -c "CREATE DATABASE edupulse_test;"

# Set environment variable
export TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/edupulse_test"

pytest tests/ -v
```

### Set Flask to Testing Mode
```bash
export FLASK_ENV=testing
export FLASK_DEBUG=0
pytest tests/ -v
```

---

## Understanding Test Output

```
tests/test_validators.py::TestLoginSchema::test_valid_login PASSED    [ 10%]
├─ Test name
├─ Test class
├─ Test method
├─ Status (PASSED/FAILED)
└─ Progress (10%)

======================== 90 passed in 25.34s ========================
└─ All 90 tests passed in 25.34 seconds
```

### Test Result Symbols
- `PASSED` ✓ - Test succeeded
- `FAILED` ✗ - Test failed (check error message)
- `SKIPPED` ⊘ - Test skipped (marked with @pytest.mark.skip)
- `ERROR` ⚠ - Test setup/teardown error

---

## Expected Test Times

| Suite | Duration | Tests |
|-------|----------|-------|
| Validators | ~2s | 30 |
| API Endpoints | ~5s | 20 |
| Security | ~8s | 25 |
| Integration | ~10s | 15 |
| **Total** | **~25s** | **90** |

---

## Coverage Target

```
Name                Stmts   Miss  Cover   Required
─────────────────────────────────────────────────
backend/validators.py    120     6    95%      ✓
backend/middleware.py    180    18    90%      ✓
backend/routes.py       520    104   80%      ✓
backend/api/models.py   250    38    85%      ✓
─────────────────────────────────────────────────
TOTAL              1070    166    84%       ✓
```

---

## Continuous Development

### Watch Mode (Auto-run tests on code change)
```bash
# Requires pytest-watch
ptw tests/ -v
```

### Run After Each Commit (Git Hook)
```bash
# Create pre-commit hook
echo '#!/bin/bash' > .git/hooks/pre-commit
echo 'pytest tests/ -q' >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Run in CI/CD (GitHub Actions)
```yaml
- name: Run tests
  run: pytest tests/ -v --cov=backend
```

---

## Test Data Reference

### Test School
```python
school_id = 'TEST-001'
school_name = 'Test School'
subscription_plan = 'Premium'
```

### Test Users
```python
# Proprietor
username = 'proprietor1'
password = 'PropPass123'
role = 'proprietor'

# Teacher
username = 'teacher1'
password = 'TeacherPass123'
role = 'teacher'
assigned_class = 'JHS 1'

# Headmaster
username = 'headmaster1'
password = 'HeadmasterPass123'
role = 'headmaster'
```

### Test Students
```python
# 5 students in JHS 1
names: Student 1, Student 2, Student 3, Student 4, Student 5
codes: S001, S002, S003, S004, S005
class: JHS 1
school: TEST-001
```

---

## Using Fixtures in Your Tests

```python
def test_example(self, client, auth_headers, test_students):
    # client - Flask test client
    # auth_headers - JWT token + school ID headers
    # test_students - List of 5 pre-created students
    
    response = client.get(
        f'/api/students/{test_students[0].id}',
        headers=auth_headers
    )
    assert response.status_code == 200
```

---

## Test Organization

```
tests/
├── conftest.py                # Fixtures and configuration
├── test_validators.py         # Input validation (30 tests)
├── test_api.py               # Endpoints (20 tests)
├── test_security.py          # Security (25 tests)
├── test_integration.py       # Workflows (15 tests)
└── README.md                 # Full documentation
```

---

## Next Steps

1. **Run the automated script** - `bash run_tests.sh`
2. **Review coverage** - Open `htmlcov/index.html`
3. **Check failing tests** - Look for `FAILED` in output
4. **Add new tests** - Copy template from `tests/test_*.py`
5. **Setup CI/CD** - GitHub Actions workflows included

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Flask Testing Guide](https://flask.palletsprojects.com/testing/)
- [Coverage.py Guide](https://coverage.readthedocs.io/)
- [Test Best Practices](../TESTING_STANDARDS.md)

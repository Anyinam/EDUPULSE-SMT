@echo off
REM EduPulse Test Execution Script for Windows
REM Usage: run_tests.bat [options]

setlocal enabledelayedexpansion

REM Colors (using ANSI codes - requires Windows 10+)
set "RESET=[0m"
set "RED=[0;31m"
set "GREEN=[0;32m"
set "YELLOW=[1;33m"
set "BLUE=[0;34m"

REM Default values
set "TEST_ENV=test"
set "COVERAGE_THRESHOLD=80"
set "VERBOSE=false"
set "SKIP_SECURITY=false"

REM Parse arguments
:parse_args
if "%1"=="" goto end_parse
if "%1"=="--verbose" (
    set "VERBOSE=true"
    shift
    goto parse_args
)
if "%1"=="-v" (
    set "VERBOSE=true"
    shift
    goto parse_args
)
if "%1"=="--coverage" (
    set "COVERAGE_THRESHOLD=%2"
    shift
    shift
    goto parse_args
)
if "%1"=="--skip-security" (
    set "SKIP_SECURITY=true"
    shift
    goto parse_args
)
if "%1"=="--help" (
    echo Usage: run_tests.bat [options]
    echo.
    echo Options:
    echo   --verbose, -v       Enable verbose output
    echo   --coverage N        Set coverage threshold (default: 80)
    echo   --skip-security     Skip security tests
    echo   --help              Show this help message
    exit /b 0
)
shift
goto parse_args

:end_parse

echo [%BLUE%]========================================[%RESET%]
echo [%BLUE%]EduPulse Test Suite Execution[%RESET%]
echo [%BLUE%]========================================[%RESET%]
echo.

REM Check environment
echo [%YELLOW%][1/7] Checking environment...[%RESET%]

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [%RED%]✗ Python not found[%RESET%]
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set "PYTHON_VERSION=%%i"
echo [%GREEN%]✓ Python found: %PYTHON_VERSION%[%RESET%]

if not exist "backend\api\api.py" (
    echo [%RED%]✗ Flask app not found at backend\api\api.py[%RESET%]
    exit /b 1
)
echo [%GREEN%]✓ Flask app found[%RESET%]

if not exist "tests" (
    echo [%RED%]✗ Tests directory not found[%RESET%]
    exit /b 1
)
echo [%GREEN%]✓ Tests directory found[%RESET%]
echo.

REM Install dependencies
echo [%YELLOW%][2/7] Installing dependencies...[%RESET%]

if exist "Eduenv\Scripts\activate.bat" (
    call Eduenv\Scripts\activate.bat
    echo [%GREEN%]✓ Virtual environment activated[%RESET%]
) else (
    echo [%RED%]✗ Virtual environment not found at Eduenv\[%RESET%]
    exit /b 1
)

pip install -q -r requirements-dev.txt
if %ERRORLEVEL% EQU 0 (
    echo [%GREEN%]✓ Dependencies installed[%RESET%]
) else (
    echo [%YELLOW%]⚠ Some dependencies may not have installed[%RESET%]
)
echo [%YELLOW%]Ensuring correct database driver...[%RESET%]
python -m pip uninstall -y psycopg psycopg-binary >nul 2>nul
python -m pip install psycopg-binary --force-reinstall
python -m pip install "pytest-postgresql>=5.0.0" --no-deps
python -c "import psycopg" && echo [%GREEN%]✓ psycopg module verified[%RESET%] || echo [%RED%]✗ psycopg module missing[%RESET%]
echo.

REM Set up test environment
echo [%YELLOW%][3/7] Setting up test environment...[%RESET%]

set "FLASK_ENV=testing"
set "FLASK_DEBUG=0"
set "TEST_DATABASE_URL=sqlite:///:memory:"
set "ALLOW_ALL_DASHBOARDS=False"
set "RATE_LIMIT_ENABLED=True"

echo [%GREEN%]✓ Test environment configured[%RESET%]
echo   FLASK_ENV=testing
echo   TEST_DATABASE_URL=sqlite:///:memory:"
echo   ALLOW_ALL_DASHBOARDS=False
echo.

REM Run linting
echo [%YELLOW%][4/7] Running code quality checks...[%RESET%]

set "LINT_FAILED=0"

where black >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    black --check backend/ >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [%YELLOW%]⚠ Black formatting issues[%RESET%]
        set "LINT_FAILED=1"
    ) else (
        echo [%GREEN%]✓ Black passed[%RESET%]
    )
)

where isort >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    isort --check-only backend\ >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [%YELLOW%]⚠ isort import sorting issues[%RESET%]
        set "LINT_FAILED=1"
    ) else (
        echo [%GREEN%]✓ isort passed[%RESET%]
    )
)

where flake8 >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    flake8 backend\ --max-line-length=100 >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [%YELLOW%]⚠ flake8 style issues[%RESET%]
        set "LINT_FAILED=1"
    ) else (
        echo [%GREEN%]✓ flake8 passed[%RESET%]
    )
)

if %LINT_FAILED% EQU 1 (
    echo [%YELLOW%]Some linting issues found (continuing)[%RESET%]
)
echo.

REM Run tests
echo [%YELLOW%][5/7] Running test suite...[%RESET%]

set "PYTEST_ARGS=-v --tb=short"

if "%VERBOSE%"=="true" (
    set "PYTEST_ARGS=!PYTEST_ARGS! -s"
)

if "%SKIP_SECURITY%"=="false" (
    set "PYTEST_ARGS=!PYTEST_ARGS! tests\"
    echo [%BLUE%]Running all tests...[%RESET%]
) else (
    set "PYTEST_ARGS=!PYTEST_ARGS! tests\ --ignore=tests\test_security.py"
    echo [%YELLOW%]Skipping security tests[%RESET%]
)

pytest %PYTEST_ARGS%
if %ERRORLEVEL% EQU 0 (
    echo [%GREEN%]✓ All tests passed[%RESET%]
    set "TEST_PASSED=1"
) else (
    echo [%RED%]✗ Some tests failed[%RESET%]
    set "TEST_PASSED=0"
)
echo.

REM Generate coverage report
echo [%YELLOW%][6/7] Generating coverage report...[%RESET%]

pytest tests\ --cov=backend --cov-report=term --cov-report=html --cov-report=xml >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [%GREEN%]✓ Coverage report generated at htmlcov\index.html[%RESET%]
) else (
    echo [%YELLOW%]⚠ Coverage report generation failed[%RESET%]
)
echo.

REM Security scan
echo [%YELLOW%][7/7] Running security scans...[%RESET%]

if "%SKIP_SECURITY%"=="false" (
    where bandit >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        bandit -r backend\ -q >nul 2>nul
        if %ERRORLEVEL% EQU 0 (
            echo [%GREEN%]✓ Bandit security scan passed[%RESET%]
        ) else (
            echo [%RED%]✗ Bandit found security issues[%RESET%]
            set "TEST_PASSED=0"
        )
    )
) else (
    echo [%YELLOW%]Security scans skipped[%RESET%]
)
echo.

REM Final summary
echo [%BLUE%]========================================[%RESET%]
echo [%BLUE%]Test Execution Summary[%RESET%]
echo [%BLUE%]========================================[%RESET%]

if %TEST_PASSED% EQU 1 (
    echo [%GREEN%]✓ All tests passed successfully[%RESET%]
    set "FINAL_CODE=0"
) else (
    echo [%RED%]✗ Some tests failed[%RESET%]
    set "FINAL_CODE=1"
)

echo.
echo Generated Reports:
echo   - Coverage: htmlcov\index.html
echo.

exit /b %FINAL_CODE%

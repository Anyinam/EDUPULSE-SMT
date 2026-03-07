#!/bin/bash

# EduPulse Test Execution Script
# This script sets up the test environment and runs the comprehensive test suite
# Usage: bash run_tests.sh [options]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_ENV="test"
COVERAGE_THRESHOLD=80
VERBOSE=false
PARALLEL=false
SKIP_SECURITY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --coverage)
            COVERAGE_THRESHOLD="$2"
            shift 2
            ;;
        --skip-security)
            SKIP_SECURITY=true
            shift
            ;;
        --help|-h)
            echo "Usage: bash run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  --verbose, -v       Enable verbose output"
            echo "  --parallel          Run tests in parallel"
            echo "  --coverage N        Set coverage threshold (default: 80)"
            echo "  --skip-security     Skip security tests"
            echo "  --help, -h          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}EduPulse Test Suite Execution${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check environment
echo -e "${YELLOW}[1/7] Checking environment...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found: $(python3 --version)${NC}"

# Check if Flask app exists
if [ ! -f "backend/api/api.py" ]; then
    echo -e "${RED}✗ Flask app not found at backend/api/api.py${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Flask app found${NC}"

# Check if tests directory exists
if [ ! -d "tests" ]; then
    echo -e "${RED}✗ Tests directory not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Tests directory found${NC}"
echo ""

# Install dependencies
echo -e "${YELLOW}[2/7] Installing dependencies...${NC}"

# Check if venv is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Virtual environment not detected. Attempting to activate...${NC}"
    if [ -d "Eduenv" ]; then
        source Eduenv/bin/activate
        echo -e "${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}✗ Virtual environment not found at Eduenv/${NC}"
        exit 1
    fi
fi

# Install test dependencies
if pip install -q -r requirements-dev.txt 2>/dev/null; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ Some dependencies may not have installed${NC}"
fi

# Verify psycopg module (required by pytest-postgresql)
if python -c "import psycopg" 2>/dev/null; then
    echo -e "${GREEN}✓ Database driver verified (psycopg)${NC}"
else
    echo -e "${YELLOW}⚠ Installing psycopg...${NC}"
    python -m pip install -q "psycopg[binary]>=3.0.0" && echo -e "${GREEN}✓ psycopg installed${NC}"
fi
echo ""

# Set up test environment
echo -e "${YELLOW}[3/7] Setting up test environment...${NC}"

export FLASK_ENV=testing
export FLASK_DEBUG=0
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export TEST_DATABASE_URL="sqlite:///:memory:"
export ALLOW_ALL_DASHBOARDS="False"
export RATE_LIMIT_ENABLED="True"

echo -e "${GREEN}✓ Test environment configured${NC}"
echo "  FLASK_ENV=testing"
echo "  TEST_DATABASE_URL=sqlite:///:memory:"
echo "  ALLOW_ALL_DASHBOARDS=False"
echo ""

# Run linting
echo -e "${YELLOW}[4/7] Running code quality checks...${NC}"

LINT_FAILED=0

# Black
if command -v black &> /dev/null; then
    if black --check backend/ 2>&1 | grep -q "would reformat"; then
        echo -e "${YELLOW}⚠ Black formatting issues${NC}"
        LINT_FAILED=1
    else
        echo -e "${GREEN}✓ Black passed${NC}"
    fi
fi

# isort
if command -v isort &> /dev/null; then
    if isort --check-only backend/ 2>&1 | grep -q "ERROR"; then
        echo -e "${YELLOW}⚠ isort import sorting issues${NC}"
        LINT_FAILED=1
    else
        echo -e "${GREEN}✓ isort passed${NC}"
    fi
fi

# flake8
if command -v flake8 &> /dev/null; then
    if flake8 backend/ --max-line-length=100 2>&1 | grep -q "error"; then
        echo -e "${YELLOW}⚠ flake8 style issues${NC}"
        LINT_FAILED=1
    else
        echo -e "${GREEN}✓ flake8 passed${NC}"
    fi
fi

if [ $LINT_FAILED -eq 1 ]; then
    echo -e "${YELLOW}Some linting issues found (continuing)${NC}"
fi
echo ""

# Run tests
echo -e "${YELLOW}[5/7] Running test suite...${NC}"

PYTEST_ARGS="-v --tb=short"

if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -s"
fi

if [ "$PARALLEL" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -n auto"
    echo -e "${BLUE}Running tests in parallel...${NC}"
else
    echo -e "${BLUE}Running tests sequentially...${NC}"
fi

if [ "$SKIP_SECURITY" = false ]; then
    PYTEST_ARGS="$PYTEST_ARGS tests/"
else
    PYTEST_ARGS="$PYTEST_ARGS tests/ --ignore=tests/test_security.py"
    echo -e "${YELLOW}Skipping security tests${NC}"
fi

# Run pytest
if pytest $PYTEST_ARGS; then
    TEST_PASSED=true
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    TEST_PASSED=false
    echo -e "${RED}✗ Some tests failed${NC}"
fi
echo ""

# Generate coverage report
echo -e "${YELLOW}[6/7] Generating coverage report...${NC}"

COVERAGE_ARGS="--cov=backend --cov-report=term --cov-report=html --cov-report=xml"

if pytest tests/ $COVERAGE_ARGS 2>/dev/null | tee coverage_output.txt; then
    COVERAGE_PERCENT=$(grep -oP 'TOTAL\s+\K[0-9]+' coverage_output.txt | tail -1)
    
    if [ -n "$COVERAGE_PERCENT" ]; then
        if [ "$COVERAGE_PERCENT" -ge "$COVERAGE_THRESHOLD" ]; then
            echo -e "${GREEN}✓ Coverage ${COVERAGE_PERCENT}% (threshold: ${COVERAGE_THRESHOLD}%)${NC}"
        else
            echo -e "${RED}✗ Coverage ${COVERAGE_PERCENT}% below threshold ${COVERAGE_THRESHOLD}%${NC}"
            TEST_PASSED=false
        fi
    fi
    
    echo -e "${GREEN}✓ Coverage report generated at htmlcov/index.html${NC}"
else
    echo -e "${YELLOW}⚠ Coverage report generation failed${NC}"
fi
echo ""

# Security scan
echo -e "${YELLOW}[7/7] Running security scans...${NC}"

if [ "$SKIP_SECURITY" = false ]; then
    SECURITY_PASSED=true
    
    # Bandit
    if command -v bandit &> /dev/null; then
        if bandit -r backend/ -q 2>&1 | grep -q "ERROR"; then
            echo -e "${RED}✗ Bandit found security issues${NC}"
            SECURITY_PASSED=false
        else
            echo -e "${GREEN}✓ Bandit security scan passed${NC}"
        fi
    fi
    
    # Safety
    if command -v safety &> /dev/null; then
        if safety check --json 2>&1 | grep -q "vulnerability"; then
            echo -e "${YELLOW}⚠ Safety found dependency vulnerabilities${NC}"
        else
            echo -e "${GREEN}✓ Safety check passed${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Security scans skipped${NC}"
fi
echo ""

# Final summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Execution Summary${NC}"
echo -e "${BLUE}========================================${NC}"

if [ "$TEST_PASSED" = true ]; then
    echo -e "${GREEN}✓ All tests passed successfully${NC}"
    FINAL_CODE=0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    FINAL_CODE=1
fi

echo ""
echo "Generated Reports:"
echo "  - Coverage: htmlcov/index.html"
echo "  - Logs: tests.log (if created)"
echo ""

# Cleanup
rm -f coverage_output.txt

exit $FINAL_CODE

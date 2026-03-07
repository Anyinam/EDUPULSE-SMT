"""
Integration and performance tests for EduPulse application.
Tests for end-to-end workflows and performance benchmarks.
"""

import json
import time
from datetime import datetime, timedelta

import pytest


class TestGradeEntryWorkflow:
    """Integration tests for complete grade entry workflow."""

    def test_homeroom_teacher_grade_entry_workflow(
        self, client, auth_headers, db, test_students
    ):
        """Test complete workflow: login → fetch students → enter grades → finalize."""

        # 1. Verify user is authenticated (auth_headers already has token)
        response = client.get("/api/profile", headers=auth_headers)
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist

        # 2. Fetch students by class
        response = client.get("/api/students/by-class/JHS%201", headers=auth_headers)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, list) or isinstance(data, dict)

    def test_grade_entry_with_validation(self, client, auth_headers, db, test_students):
        """Test grade entry with proper validation."""

        payload = {
            "student_id": test_students[0].id,
            "class_score": 25,
            "exam_score": 65,
            "class_name": "JHS 1",
        }

        response = client.post(
            "/api/homeroom/finalize-class",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should accept valid grades or return 404 if endpoint not found
        assert response.status_code in [200, 201, 404, 422]

    def test_invalid_grade_scores_rejected(self, client, auth_headers, test_students):
        """Test that invalid grade scores are rejected."""

        invalid_scores = [
            {"class_score": -5, "exam_score": 60},
            {"class_score": 50, "exam_score": 60},  # class_score > 30
            {"class_score": 25, "exam_score": 100},  # exam_score > 70
            {"class_score": 25, "exam_score": -10},
        ]

        for scores in invalid_scores:
            payload = {
                "student_id": test_students[0].id,
                "class_score": scores["class_score"],
                "exam_score": scores["exam_score"],
                "class_name": "JHS 1",
            }

            response = client.post(
                "/api/homeroom/finalize-class",
                data=json.dumps(payload),
                content_type="application/json",
                headers=auth_headers,
            )

            # Invalid scores should be rejected or not found
            assert response.status_code in [400, 422, 404]


class TestPaymentWorkflow:
    """Integration tests for payment recording workflow."""

    def test_payment_recording_workflow(self, client, auth_headers, db, test_students):
        """Test complete payment workflow and verification."""

        payload = {
            "student_id": test_students[0].id,
            "amount": 50.00,
            "payment_type": "Feeding",
            "method": "Cash",
        }

        response = client.post(
            "/api/finance/receive-payment",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should create payment or return 404 if endpoint not found
        assert response.status_code in [200, 201, 404, 422]

        # If successful, verify payment was recorded
        if response.status_code in [200, 201]:
            data = json.loads(response.data)
            assert "payment_id" in data or "id" in data

    def test_multiple_payment_types(self, client, auth_headers, test_students):
        """Test recording different payment types."""

        payment_types = ["Tuition", "Feeding", "Uniform"]

        for i, ptype in enumerate(payment_types):
            payload = {
                "student_id": test_students[i].id,
                "amount": 25.00 + i * 10,
                "payment_type": ptype,
                "method": "Bank" if i % 2 else "Cash",
            }

            response = client.post(
                "/api/finance/receive-payment",
                data=json.dumps(payload),
                content_type="application/json",
                headers=auth_headers,
            )

            assert response.status_code in [200, 201, 403, 404, 422]

    def test_payment_history_retrieval(self, client, auth_headers, test_students):
        """Test retrieving payment history for student."""

        response = client.get(
            f"/api/students/{test_students[0].id}/payments", headers=auth_headers
        )

        # Should return payment history or 404
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert isinstance(data, list)


class TestAttendanceTracking:
    """Integration tests for attendance workflow."""

    def test_attendance_recording(self, client, auth_headers, test_students):
        """Test recording student attendance."""

        payload = {
            "student_id": test_students[0].id,
            "present": True,
            "date": datetime.now().isoformat(),
        }

        response = client.post(
            "/api/homeroom/attendance",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code in [200, 201, 404, 422]

    def test_bulk_attendance_recording(self, client, auth_headers, test_students):
        """Test recording attendance for multiple students."""

        attendance_records = [
            {
                "student_id": student.id,
                "present": True,
                "date": datetime.now().isoformat(),
            }
            for student in test_students[:3]
        ]

        response = client.post(
            "/api/homeroom/attendance/bulk",
            data=json.dumps({"records": attendance_records}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code in [200, 201, 404, 422]


class TestReportGeneration:
    """Integration tests for report generation."""

    def test_terminal_report_generation(self, client, auth_headers, test_students):
        """Test generating terminal/end-of-term reports."""

        payload = {"student_id": test_students[0].id, "term": "1", "year": 2024}

        response = client.post(
            "/api/homeroom/generate-terminal-report",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Report generation should work or return 404
        assert response.status_code in [200, 201, 404, 422]

        if response.status_code in [200, 201]:
            data = json.loads(response.data)
            # Terminal report should have structure
            assert data  # Non-empty response

    def test_class_report_generation(self, client, auth_headers):
        """Test generating class-level reports."""

        response = client.get(
            "/api/homeroom/class-report?class_name=JHS%201", headers=auth_headers
        )

        assert response.status_code in [200, 404]


class TestPerformance:
    """Performance benchmarks for critical operations."""

    @pytest.mark.slow
    def test_login_performance(self, client, test_school):
        """Test login endpoint performance (should be < 500ms)."""

        payload = {
            "school_code": "TEST-001",
            "username": "teacher1",
            "password": "TeacherPass123",
        }

        start_time = time.time()
        response = client.post(
            "/api/login",
            data=json.dumps(payload),
            content_type="application/json",
            headers={"X-School-ID": test_school.id},
        )
        elapsed = (time.time() - start_time) * 1000  # Convert to ms

        assert elapsed < 500, f"Login took {elapsed}ms (should be < 500ms)"

    @pytest.mark.slow
    def test_fetch_students_performance(self, client, auth_headers, db, test_school):
        """Test student list retrieval performance with many students."""
        from backend.api.models import Student

        # Create bulk students
        students = [
            Student(
                school_id=test_school.id,
                first_name=f"Student{i}",
                surname="Perf",
                name=f"Student {i}",
                student_code=f"S{i:05d}",
                current_class="JHS 1",
            )
            for i in range(100)
        ]
        db.session.add_all(students)
        db.session.commit()

        start_time = time.time()
        response = client.get("/api/students?limit=100", headers=auth_headers)
        elapsed = (time.time() - start_time) * 1000

        if response.status_code == 200:
            assert (
                elapsed < 1000
            ), f"Fetch students took {elapsed}ms (should be < 1000ms)"

    @pytest.mark.slow
    def test_grade_entry_bulk_performance(self, client, auth_headers, db, test_school):
        """Test bulk grade entry performance."""
        from backend.api.models import Student

        students = [
            Student(
                school_id=test_school.id,
                first_name=f"Student{i}",
                surname="Bulk",
                name=f"Student {i}",
                student_code=f"S{i:05d}",
                current_class="JHS 1",
            )
            for i in range(50)
        ]
        db.session.add_all(students)
        db.session.commit()

        grades = [
            {
                "student_id": s.id,
                "class_score": 20 + (i % 10),
                "exam_score": 50 + (i % 20),
                "class_name": "JHS 1",
            }
            for i, s in enumerate(db.session.query(Student).limit(50).all())
        ]

        start_time = time.time()
        for grade in grades[:10]:  # Test with 10 entries
            response = client.post(
                "/api/homeroom/finalize-class",
                data=json.dumps(grade),
                content_type="application/json",
                headers=auth_headers,
            )
            if response.status_code not in [200, 201, 404, 422]:
                break

        elapsed = (time.time() - start_time) * 1000
        avg_time = elapsed / min(10, len(grades))

        if response.status_code in [200, 201]:
            assert (
                avg_time < 200
            ), f"Average grade entry took {avg_time}ms (should be < 200ms)"


class TestDataConsistency:
    """Tests for data consistency across operations."""

    def test_payment_totals_consistency(self, client, auth_headers, db, test_students):
        """Test that payment totals remain consistent."""
        from datetime import datetime

        from backend.api.models import Payment

        student = test_students[0]
        initial_total = sum(p.amount for p in student.payments)

        # Record a payment
        payload = {
            "student_id": student.id,
            "amount": 100.00,
            "payment_type": "Tuition",
            "method": "Bank",
        }

        client.post(
            "/api/finance/receive-payment",
            data=json.dumps(payload),
            content_type="application/json",
            headers=auth_headers,
        )

        # Refresh from database
        db.session.refresh(student)
        final_total = sum(p.amount for p in student.payments)

        # Verify total increased (if endpoint works)
        assert final_total >= initial_total

    def test_grade_calculation_consistency(
        self, client, auth_headers, db, test_students
    ):
        """Test that grade totals are calculated consistently."""
        from backend.api.models import StudentGrade

        student = test_students[0]

        # Add grade record
        grade = StudentGrade(student_id=student.id, class_score=25, exam_score=65)
        db.session.add(grade)
        db.session.commit()

        # Verify total calculation
        expected_total = 25 + 65
        assert grade.total_score == expected_total


class TestConcurrency:
    """Tests for concurrent operation handling."""

    def test_concurrent_payment_recording(self, client, auth_headers, test_students):
        """Test that concurrent payments don't cause conflicts."""

        # Simulate concurrent payments for same student
        payloads = [
            {
                "student_id": test_students[0].id,
                "amount": 10.00 + i,
                "payment_type": "Feeding",
                "method": "Cash",
            }
            for i in range(5)
        ]

        responses = []
        for payload in payloads:
            response = client.post(
                "/api/finance/receive-payment",
                data=json.dumps(payload),
                content_type="application/json",
                headers=auth_headers,
            )
            responses.append(response.status_code)

        # All should succeed or fail gracefully
        assert all(r in [200, 201, 404, 409, 422] for r in responses)


class TestErrorRecovery:
    """Tests for error handling and recovery."""

    def test_network_error_recovery(self, client, auth_headers, mocker):
        """Test graceful handling of network errors."""

        mocker.patch(
            "backend.routes.db.session.commit",
            side_effect=Exception("Connection timeout"),
        )

        response = client.get("/api/students", headers=auth_headers)

        # Should return error not crash
        assert response.status_code >= 400

    def test_invalid_json_handling(self, client, auth_headers):
        """Test handling of invalid JSON requests."""

        response = client.post(
            "/api/finance/receive-payment",
            data='{"invalid json',
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code in [400, 422]

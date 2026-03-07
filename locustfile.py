"""
Locust load testing configuration for EduPulse API.
Tests authentication, student management, and core business workflows.

Usage:
    locust --host=http://localhost:5000
    
Then open http://localhost:8089 in your browser to configure and start the test.
"""

import random
import string
from locust import HttpUser, task, between, TaskSet


class EduPulseUser(HttpUser):
    """Simulates a typical EduPulse user workflow."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    host = "http://localhost:5000"
    
    def on_start(self):
        """Called when a simulated user starts - setup authentication."""
        # Generate unique school code for this user
        self.school_code = f"TEST-{random.randint(1000, 9999)}"
        self.username = f"user_{random.randint(1000, 9999)}"
        self.password = "Test@2026"
        
        # Register a test school
        self.register_school()
        
        # Login and get JWT token
        self.login()
    
    def register_school(self):
        """Register a new school tenant."""
        payload = {
            "schoolCode": self.school_code,
            "schoolName": f"Test School {self.school_code}",
            "username": self.username,
            "password": self.password,
            "termsAccepted": True,
            "termsVersion": "2026-02-22"
        }
        
        # Add CSRF protection headers
        csrf_headers = {
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/"
        }
        
        with self.client.post(
            "/api/register", 
            json=payload,
            headers=csrf_headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 400 and "already taken" in response.text:
                # School already exists, that's okay
                response.success()
            else:
                response.failure(f"Registration failed: {response.text}")
    
    def login(self):
        """Authenticate and store JWT token."""
        payload = {
            "schoolCode": self.school_code,
            "username": self.username,
            "password": self.password
        }
        
        # Add CSRF protection headers
        csrf_headers = {
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/"
        }
        
        with self.client.post(
            "/api/login",
            json=payload,
            headers=csrf_headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.headers = {
                    "Authorization": f"Bearer {self.token}",
                    "X-School-ID": self.school_code
                }
                response.success()
            else:
                response.failure(f"Login failed: {response.text}")
                self.token = None
                self.headers = {}
    
    @task(3)
    def get_students(self):
        """Fetch list of students."""
        if not hasattr(self, 'token') or not self.token:
            return
        
        self.client.get(
            "/api/students",
            headers=self.headers,
            name="/api/students [GET]"
        )
    
    @task(2)
    def create_student(self):
        """Admit a new student."""
        if not hasattr(self, 'token') or not self.token:
            return
        
        payload = {
            "first_name": f"Test{random.randint(100, 999)}",
            "surname": f"Student{random.randint(100, 999)}",
            "class_name": random.choice(["JHS 1", "JHS 2", "JHS 3"]),
            "gender": random.choice(["Male", "Female"]),
            "guardian_contact": f"0{random.randint(200000000, 599999999)}"
        }
        
        with self.client.post(
            "/api/students",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/students [POST]"
        ) as response:
            if response.status_code == 201:
                response.success()
                # Store student ID for later use
                if not hasattr(self, 'student_ids'):
                    self.student_ids = []
                data = response.json()
                if 'student' in data:
                    self.student_ids.append(data['student']['id'])
            else:
                response.failure(f"Failed to create student: {response.text}")
    
    @task(2)
    def get_finance_summary(self):
        """Check financial dashboard."""
        if not hasattr(self, 'token') or not self.token:
            return
        
        self.client.get(
            "/api/finance/summary",
            headers=self.headers,
            name="/api/finance/summary [GET]"
        )
    
    @task(1)
    def record_payment(self):
        """Record a student payment."""
        if not hasattr(self, 'token') or not self.token:
            return
        
        # Need a student ID - create one if we don't have any
        if not hasattr(self, 'student_ids') or not self.student_ids:
            self.create_student()
            if not hasattr(self, 'student_ids') or not self.student_ids:
                return
        
        student_id = random.choice(self.student_ids)
        amount = random.choice([50, 100, 150, 200, 250])
        
        payload = {
            "student_id": student_id,
            "amount": amount,
            "payment_type": random.choice(["Tuition", "Feeding", "Transport", "Books"]),
            "payment_method": random.choice(["Cash", "Mobile Money", "Bank Transfer"])
        }
        
        self.client.post(
            "/api/finance/payments",
            json=payload,
            headers=self.headers,
            name="/api/finance/payments [POST]"
        )
    
    @task(1)
    def get_dashboard_data(self):
        """Fetch dashboard statistics."""
        if not hasattr(self, 'token') or not self.token:
            return
        
        self.client.get(
            "/api/dashboard",
            headers=self.headers,
            name="/api/dashboard [GET]"
        )
    
    @task(1)
    def health_check(self):
        """Check API health."""
        self.client.get("/", name="/ [Health Check]")


class QuickTest(HttpUser):
    """Quick smoke test - just hits the health endpoint."""
    
    wait_time = between(0.5, 1.5)
    host = "http://localhost:5000"
    
    @task
    def health_check(self):
        self.client.get("/", name="/ [Quick Health]")


# Task sets for more complex scenarios
class TeacherWorkflow(TaskSet):
    """Simulates a teacher's typical workflow."""
    
    @task(3)
    def view_my_classes(self):
        self.client.get(
            "/api/homeroom/classes",
            headers=self.user.headers,
            name="[Teacher] View Classes"
        )
    
    @task(2)
    def record_attendance(self):
        # Simplified - would need actual class/student data
        pass
    
    @task(1)
    def enter_grades(self):
        # Simplified - would need actual student data
        pass


class ProprietorWorkflow(TaskSet):
    """Simulates proprietor oversight activities."""
    
    @task(5)
    def view_financial_reports(self):
        self.client.get(
            "/api/finance/summary",
            headers=self.user.headers,
            name="[Proprietor] Finance Summary"
        )
    
    @task(3)
    def view_all_students(self):
        self.client.get(
            "/api/students",
            headers=self.user.headers,
            name="[Proprietor] All Students"
        )
    
    @task(2)
    def view_staff(self):
        self.client.get(
            "/api/staff",
            headers=self.user.headers,
            name="[Proprietor] Staff List"
        )
    
    @task(1)
    def generate_report(self):
        self.client.get(
            "/api/reports/terminal",
            headers=self.user.headers,
            name="[Proprietor] Terminal Report"
        )

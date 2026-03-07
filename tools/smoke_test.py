import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.api.api import app


def pretty(resp):
    try:
        return json.dumps(resp.get_json(), indent=2)
    except Exception:
        return resp.data.decode("utf-8")


def run():
    client = app.test_client()

    headers = {"X-School-ID": "CCA-OFK"}

    print("\n1) Login as homeroom_teacher")
    r = client.post(
        "/api/login",
        json={
            "schoolCode": "CCA-OFK",
            "username": "homeroom_teacher",
            "password": "homeroom123",
        },
    )
    print("Status:", r.status_code)
    print(pretty(r))
    homeroom_token = r.get_json().get("token") if r.status_code == 200 else None

    print("\n2) Fetch students by class (homeroom)")
    if homeroom_token:
        h = {"X-School-ID": "CCA-OFK", "Authorization": f"Bearer {homeroom_token}"}
        r = client.get("/api/students/by-class/JHS%201", headers=h)
        print("Status:", r.status_code)
        print(pretty(r))
        students = r.get_json() if r.status_code == 200 else []
    else:
        students = []

    print(
        "\n3) Login as subject_teacher and attempt feeding payment for a student (should be denied)"
    )
    r = client.post(
        "/api/login",
        json={
            "schoolCode": "CCA-OFK",
            "username": "subject_teacher",
            "password": "subject123",
        },
    )
    subj_token = r.get_json().get("token") if r.status_code == 200 else None
    print("Login status:", r.status_code)

    if subj_token and students:
        student_id = students[0]["id"]
        h = {"X-School-ID": "CCA-OFK", "Authorization": f"Bearer {subj_token}"}
        payload = {
            "student_id": student_id,
            "amount": 2.0,
            "type": "Feeding",
            "method": "Cash",
        }
        r = client.post("/api/finance/receive-payment", headers=h, json=payload)
        print("Attempt feeding payment status:", r.status_code)
        print(pretty(r))
    else:
        print("Skipping feeding payment test (missing token or students)")

    print("\n4) Homeroom finalize class grades for JHS 1")
    if homeroom_token and students:
        student_id = students[0]["id"]
        h = {"X-School-ID": "CCA-OFK", "Authorization": f"Bearer {homeroom_token}"}
        grade_data = {str(student_id): 85}
        payload = {
            "class_name": "JHS 1",
            "subject": "Mathematics",
            "grade_data": grade_data,
        }
        r = client.post("/api/homeroom/finalize-class", headers=h, json=payload)
        print("Finalize status:", r.status_code)
        print(pretty(r))
    else:
        print("Skipping finalize (missing token or students)")


if __name__ == "__main__":
    run()

import base64
import io
import os

import pytest
from flask_jwt_extended import create_access_token

from backend.api.models import ParentAdmissionApplication, Student, db


PHOTO_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jP1sAAAAASUVORK5CYII="
)


@pytest.fixture
def admission_storage(app, tmp_path, monkeypatch, request):
    monkeypatch.setitem(app.config, "PARENT_ADMISSION_DOCUMENT_STORAGE_DIR", str(tmp_path / "admissions"))
    monkeypatch.setitem(app.config, "STUDENT_DOCUMENT_STORAGE_DIR", str(tmp_path / "students"))
    monkeypatch.setattr("backend.routes.send_email_notification", lambda *args, **kwargs: True)
    monkeypatch.delenv("DOCUMENT_STORAGE_S3_BUCKET", raising=False)
    objects = {}
    if request.param == "s3":
        class FakeS3Client:
            def put_object(self, **kwargs):
                assert kwargs["Bucket"] == "admission-photo-tests"
                assert kwargs["ServerSideEncryption"] == "AES256"
                objects[kwargs["Key"]] = kwargs["Body"]
                return {}

            def head_object(self, **kwargs):
                if kwargs["Key"] not in objects:
                    raise MissingObject()
                return {"ContentLength": len(objects[kwargs["Key"]])}

            def get_object(self, **kwargs):
                if kwargs["Key"] not in objects:
                    raise MissingObject()
                return {"Body": io.BytesIO(objects[kwargs["Key"]])}

        monkeypatch.setenv("DOCUMENT_STORAGE_S3_BUCKET", "admission-photo-tests")
        monkeypatch.setenv("DOCUMENT_STORAGE_S3_PREFIX", "test-documents")
        monkeypatch.setattr("backend.document_storage._get_s3_client", lambda: FakeS3Client())
    return objects


class MissingObject(Exception):
    response = {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}}


def _headers(user, school_id):
    return {
        "Authorization": f"Bearer {create_access_token(identity=str(user.id))}",
        "X-School-ID": school_id,
    }


def test_manual_admission_photo_is_saved_and_returned_in_student_roster(client, app, test_school, test_proprietor):
    photo = "data:image/png;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")
    headers = _headers(test_proprietor, test_school.id)
    response = client.post("/api/admissions/admit", headers=headers, json={
        "first_name": "Manual", "surname": "Learner", "class_assigned": "JHS 1",
        "student_code": "MANUALPHOTO", "profile_picture": photo,
    })
    assert response.status_code == 200, response.get_json()
    student = Student.query.filter_by(school_id=test_school.id, student_code="MANUALPHOTO").one()
    assert student.profile_picture == photo
    roster = client.get("/api/students", headers=headers)
    assert roster.status_code == 200
    assert next(item for item in roster.get_json() if item["id"] == student.id)["profile_picture"] == photo


def _submit(client, school_id, with_photo=True):
    payload = {
        "first_name": "Ama",
        "surname": "Boadu",
        "preferred_class": "JHS 1",
        "guardian_name": "Kojo Boadu",
        "parent_email": "guardian@example.com",
        "consent_confirmed": "true",
        "documents": [
            (io.BytesIO(b"birth certificate"), "birth-certificate.pdf"),
            (io.BytesIO(PHOTO_BYTES + b"guardian"), "guardian-passport.jpg", "image/jpeg"),
            (io.BytesIO(PHOTO_BYTES + b"guardian"), "guardian-headshot.jpg", "image/jpeg"),
        ],
    }
    if with_photo:
        payload["passport_photo"] = (io.BytesIO(PHOTO_BYTES), "learner.png", "image/png")
    response = client.post(
        f"/api/public/schools/{school_id}/admissions/apply",
        data=payload,
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return db.session.get(ParentAdmissionApplication, response.get_json()["application"]["id"])


def _approve(client, application, headers):
    response = client.post(
        f"/api/admissions/applications/{application.id}/review",
        headers=headers,
        data={"action": "approve", "class_assigned": "JHS 1"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_json()
    student = db.session.get(Student, response.get_json()["student_id"])
    assert application.admitted_student_id == student.id
    assert application.status == "Approved"
    return student


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_multipart_approval_sets_passport_photo(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id)
    photo = application.document_manifest[0]
    assert photo["category"] == "passport_photo"
    assert photo["is_primary_photo"] is True
    if admission_storage:
        assert photo["storage_backend"] == "s3"
        assert admission_storage[photo["storage_key"]] == PHOTO_BYTES
    student = _approve(client, application, _headers(test_proprietor, test_school.id))
    assert student.profile_picture == "data:image/png;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_approved_passport_is_in_students_response(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id)
    headers = _headers(test_proprietor, test_school.id)
    student = _approve(client, application, headers)
    response = client.get("/api/students", headers=headers)
    assert response.status_code == 200, response.get_json()
    listed = next(item for item in response.get_json() if item["id"] == student.id)
    assert listed.get("profile_picture") == "data:image/png;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_approved_document_vault_mirrors_manifest_and_downloads_with_auth(
    client, app, test_school, test_proprietor, admission_storage
):
    application = _submit(client, test_school.id)
    headers = _headers(test_proprietor, test_school.id)
    student = _approve(client, application, headers)
    response = client.get(f"/api/students/{student.id}/documents", headers=headers)
    assert response.status_code == 200, response.get_json()
    documents = response.get_json()["admission_documents"]
    assert {entry["document_id"] for entry in documents} == {
        entry["document_id"] for entry in application.document_manifest
    }
    assert all(entry["source"] == "parent_admission" for entry in documents)
    for document in documents:
        assert document["download_available"] is True
        original = next(entry for entry in application.document_manifest if entry["document_id"] == document["document_id"])
        if original.get("storage_key"):
            assert document["storage_key"] == original["storage_key"]
        assert client.get(document["download_path"], headers={"X-School-ID": test_school.id}).status_code in {401, 403}
        download = client.get(document["download_path"], headers=headers)
        assert download.status_code == 200
        expected = PHOTO_BYTES if document.get("is_primary_photo") else (
            b"birth certificate" if document["category"] == "birth_certificate" else PHOTO_BYTES + b"guardian"
        )
        assert download.data == expected
    photo_id = application.document_manifest[0]["document_id"]
    student_photo_path = f"/api/students/{student.id}/documents/{photo_id}/download"
    assert client.get(student_photo_path, headers={"X-School-ID": test_school.id}).status_code in {401, 403}
    photo_response = client.get(student_photo_path, headers=headers)
    assert photo_response.status_code == 200
    assert photo_response.data == PHOTO_BYTES


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_guardian_identity_image_never_becomes_student_photo(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id, with_photo=False)
    student = _approve(client, application, _headers(test_proprietor, test_school.id))
    assert not student.profile_picture


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_missing_passport_is_not_fabricated(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id)
    photo = application.document_manifest[0]
    if photo.get("storage_backend") == "s3":
        admission_storage.pop(photo["storage_key"])
    else:
        os.remove(os.path.join(app.config["PARENT_ADMISSION_DOCUMENT_STORAGE_DIR"], test_school.id, photo["stored_filename"]))
    headers = _headers(test_proprietor, test_school.id)
    student = _approve(client, application, headers)
    assert not student.profile_picture
    documents = client.get(f"/api/students/{student.id}/documents", headers=headers).get_json()["admission_documents"]
    missing_photo = next(entry for entry in documents if entry["document_id"] == photo["document_id"])
    assert missing_photo["download_available"] is False
    assert "download_path" not in missing_photo
    response = client.get(f"/api/students/{student.id}/documents/{photo['document_id']}/download", headers=headers)
    assert response.status_code == 404


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_latest_corrected_passport_becomes_profile_photo(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id)
    corrected_bytes = PHOTO_BYTES + b"corrected learner photo"
    response = client.post(
        f"/api/public/schools/{test_school.id}/admissions/status/{application.status_token}/resubmit",
        data={"passport_photo": (io.BytesIO(corrected_bytes), "corrected.png", "image/png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_json()
    corrected_entry = application.document_manifest[-1]
    assert corrected_entry["submitted_in_correction"] is True
    assert corrected_entry["is_primary_photo"] is True
    student = _approve(client, application, _headers(test_proprietor, test_school.id))
    assert student.profile_picture == "data:image/png;base64," + base64.b64encode(corrected_bytes).decode("ascii")


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_approved_photo_remains_persisted_after_source_loss(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id)
    student = _approve(client, application, _headers(test_proprietor, test_school.id))
    photo = application.document_manifest[0]
    if photo.get("storage_backend") == "s3":
        admission_storage.pop(photo["storage_key"])
    else:
        os.remove(os.path.join(app.config["PARENT_ADMISSION_DOCUMENT_STORAGE_DIR"], test_school.id, photo["stored_filename"]))
    db.session.expire(student)
    assert student.profile_picture == "data:image/png;base64," + base64.b64encode(PHOTO_BYTES).decode("ascii")


@pytest.mark.parametrize("admission_storage", ["local", "s3"], indirect=True)
def test_metadata_only_passport_is_not_fabricated(client, app, test_school, test_proprietor, admission_storage):
    application = _submit(client, test_school.id, with_photo=False)
    application.document_manifest = [
        *application.document_manifest,
        {"filename": "legacy.png", "content_type": "image/png", "category": "passport_photo", "is_primary_photo": True},
    ]
    db.session.commit()
    student = _approve(client, application, _headers(test_proprietor, test_school.id))
    assert not student.profile_picture
import os


class DocumentStorageError(RuntimeError):
    pass


def _get_s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise DocumentStorageError("boto3 is required when DOCUMENT_STORAGE_S3_BUCKET is configured") from exc
    return boto3.client("s3")


def _is_missing_object_error(exc: Exception) -> bool:
    response = getattr(exc, "response", {}) or {}
    status_code = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    error_code = str((response.get("Error") or {}).get("Code") or "")
    return status_code == 404 or error_code in {"404", "NoSuchKey", "NotFound"}


def get_document_bucket() -> str | None:
    return (os.getenv("DOCUMENT_STORAGE_S3_BUCKET") or "").strip() or None


def build_document_key(namespace: str, school_id: str, stored_filename: str) -> str:
    prefix = (os.getenv("DOCUMENT_STORAGE_S3_PREFIX") or "edupulse-documents").strip("/")
    return "/".join(
        part.strip("/")
        for part in (prefix, namespace, str(school_id), stored_filename)
        if part
    )


def store_document_bytes(object_key: str, file_bytes: bytes, content_type: str | None = None) -> bool:
    bucket = get_document_bucket()
    if not bucket:
        return False

    put_args = {
        "Bucket": bucket,
        "Key": object_key,
        "Body": file_bytes or b"",
        "ServerSideEncryption": "AES256",
    }
    if content_type:
        put_args["ContentType"] = content_type
    try:
        _get_s3_client().put_object(**put_args)
    except Exception as exc:
        raise DocumentStorageError("Unable to store document in durable storage") from exc
    return True


def document_exists(object_key: str | None) -> bool:
    bucket = get_document_bucket()
    if not bucket or not object_key:
        return False
    try:
        _get_s3_client().head_object(Bucket=bucket, Key=object_key)
        return True
    except Exception as exc:
        if _is_missing_object_error(exc):
            return False
        raise DocumentStorageError("Unable to check durable document storage") from exc


def read_document_bytes(object_key: str) -> bytes:
    bucket = get_document_bucket()
    if not bucket:
        raise FileNotFoundError("Durable document storage is not configured")
    try:
        response = _get_s3_client().get_object(Bucket=bucket, Key=object_key)
        return response["Body"].read()
    except Exception as exc:
        if _is_missing_object_error(exc):
            raise FileNotFoundError(object_key) from exc
        raise DocumentStorageError("Unable to read document from durable storage") from exc
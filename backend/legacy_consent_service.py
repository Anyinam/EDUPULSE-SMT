import json
import os
import secrets
from datetime import datetime, timezone


def get_legacy_consent_evidence_artifacts(
    school_settings,
    *,
    get_data_compliance_workflow_config,
    build_download_path,
):
    workflow_config = get_data_compliance_workflow_config(school_settings)
    artifacts = []
    for artifact in workflow_config.get("legacy_migration", {}).get("evidence_artifacts", []):
        item = dict(artifact)
        item["download_path"] = build_download_path(artifact["id"])
        artifacts.append(item)
    return {"artifacts": artifacts}


def upload_legacy_consent_evidence_artifact(
    uploaded_file,
    *,
    school_settings,
    actor_id,
    school_id,
    category,
    note,
    secure_filename,
    get_storage_root,
    get_data_compliance_workflow_config,
    set_data_compliance_workflow_config,
    build_download_path,
    log_action,
    logger,
    db_session,
):
    original_filename = secure_filename(uploaded_file.filename or "")
    if not original_filename:
        return None, {"message": "A valid filename is required."}, 400

    artifact_id = f"evidence_{secrets.token_hex(6)}"
    stored_filename = f"{artifact_id}_{original_filename}"
    target_path = os.path.join(get_storage_root(), stored_filename)
    uploaded_file.save(target_path)
    file_size = os.path.getsize(target_path)

    workflow_config = get_data_compliance_workflow_config(school_settings)
    artifacts = workflow_config["legacy_migration"].get("evidence_artifacts") or []
    new_artifact = {
        "id": artifact_id,
        "stored_filename": stored_filename,
        "original_filename": original_filename,
        "category": category,
        "note": note,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": actor_id,
        "size_bytes": file_size,
    }
    workflow_config["legacy_migration"]["evidence_artifacts"] = [new_artifact] + artifacts
    set_data_compliance_workflow_config(school_settings, workflow_config)
    db_session.commit()

    try:
        log_action(
            actor_id,
            school_id,
            "LEGACY_CONSENT_EVIDENCE_UPLOADED",
            json.dumps(
                {
                    "artifact_id": artifact_id,
                    "original_filename": original_filename,
                    "category": new_artifact["category"],
                }
            ),
        )
    except Exception as audit_error:
        logger.warning("Legacy consent evidence audit log failed for %s: %s", artifact_id, audit_error)

    response_artifact = dict(new_artifact)
    response_artifact["download_path"] = build_download_path(artifact_id)
    return {"message": "Consent evidence uploaded.", "artifact": response_artifact}, None, 201


def resolve_legacy_consent_evidence_download(
    artifact_id,
    school_settings,
    *,
    get_data_compliance_workflow_config,
    get_storage_root,
    resolve_existing_school_file,
):
    workflow_config = get_data_compliance_workflow_config(school_settings)
    matching_artifact = next(
        (
            item
            for item in workflow_config.get("legacy_migration", {}).get("evidence_artifacts", [])
            if item.get("id") == artifact_id
        ),
        None,
    )
    if not matching_artifact:
        return None, None, {"message": "Consent evidence artifact not found"}, 404

    resolved_path = resolve_existing_school_file(get_storage_root(), matching_artifact.get("stored_filename"))
    if not resolved_path:
        return None, None, {"message": "Consent evidence file is no longer available"}, 404

    return resolved_path, matching_artifact.get("original_filename") or "consent-evidence", None, 200
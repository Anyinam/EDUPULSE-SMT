import json
from datetime import date


def submit_parent_admission_application(
    school_id,
    payload,
    passport_photo,
    documents,
    school_model,
    school_settings_model,
    parent_admission_application_model,
    valid_grades,
    consent_version,
    sanitize_string,
    extract_parent_admission_document_details,
    store_parent_admission_document,
    build_ai_registrar_assessment,
    generate_parent_admission_code,
    secrets_module,
    build_parent_status_path,
    build_parent_public_url,
    send_parent_admission_update,
    get_public_school_profile_payload,
    build_parent_admission_payment_payload,
    build_parent_notification_sms,
    log_action,
    get_client_ip,
    logger,
    db_session,
):
    school = school_model.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return None, {"message": "School not found"}, 404
    settings = school_settings_model.query.filter_by(school_id=school_id).first()

    first_name = sanitize_string(payload.get("first_name") or "")
    surname = sanitize_string(payload.get("surname") or "")
    preferred_class = sanitize_string(payload.get("preferred_class") or payload.get("class_assigned") or "")
    guardian_name = sanitize_string(payload.get("guardian_name") or payload.get("parent_name") or "")
    parent_email = sanitize_string(payload.get("parent_email") or "")
    parent_phone = sanitize_string(payload.get("parent_phone") or "")
    consent_confirmed = str(payload.get("consent_confirmed") or payload.get("consentConfirmed") or "").strip().lower() in {"1", "true", "yes", "on"}
    resolved_consent_version = sanitize_string(payload.get("consent_version") or payload.get("consentVersion") or "") or consent_version

    if not first_name or not surname:
        return None, {"message": "first_name and surname are required"}, 400
    if preferred_class not in valid_grades:
        return None, {"message": f"preferred_class must be one of: {', '.join(valid_grades)}"}, 400
    if not guardian_name:
        return None, {"message": "guardian_name is required"}, 400
    if not parent_email and not parent_phone:
        return None, {"message": "Provide at least parent_email or parent_phone"}, 400
    if not consent_confirmed:
        return None, {"message": "Parent or guardian consent confirmation is required before submission."}, 400

    date_of_birth = None
    raw_dob = sanitize_string(payload.get("date_of_birth") or "")
    if raw_dob:
        try:
            date_of_birth = date.fromisoformat(raw_dob)
        except ValueError:
            return None, {"message": "Invalid date_of_birth format. Use YYYY-MM-DD."}, 400

    document_manifest = []
    if passport_photo and getattr(passport_photo, "filename", None):
        file_bytes = passport_photo.read()
        if file_bytes:
            entry = extract_parent_admission_document_details(
                passport_photo.filename,
                passport_photo.mimetype,
                file_bytes,
                category_override="passport_photo",
            )
            entry.update(store_parent_admission_document(school_id, passport_photo, file_bytes))
            entry["is_primary_photo"] = True
            document_manifest.append(entry)

    for uploaded in documents:
        if not uploaded or not getattr(uploaded, "filename", None):
            continue
        file_bytes = uploaded.read()
        entry = extract_parent_admission_document_details(
            uploaded.filename,
            uploaded.mimetype,
            file_bytes,
        )
        entry.update(store_parent_admission_document(school_id, uploaded, file_bytes))
        document_manifest.append(entry)

    assessment = build_ai_registrar_assessment(payload, document_manifest)
    application = parent_admission_application_model(
        school_id=school_id,
        application_code=generate_parent_admission_code(school_id),
        status_token=secrets_module.token_urlsafe(24),
        first_name=first_name,
        surname=surname,
        gender=sanitize_string(payload.get("gender") or "") or None,
        date_of_birth=date_of_birth,
        preferred_class=preferred_class,
        guardian_name=guardian_name,
        parent_email=parent_email or None,
        parent_phone=parent_phone or None,
        prior_school=sanitize_string(payload.get("prior_school") or "") or None,
        desired_test_mode=sanitize_string(payload.get("desired_test_mode") or "either") or "either",
        internet_quality=sanitize_string(payload.get("internet_quality") or "unknown") or "unknown",
        parent_notes=sanitize_string(payload.get("parent_notes") or "") or None,
        document_manifest=document_manifest,
        ai_summary=assessment["summary"],
        ai_recommendation=assessment["recommendation"],
        ai_readiness_score=assessment["readiness_score"],
        ai_flags=assessment["flags"],
        ai_missing_items=assessment["missing_items"],
        status=assessment["status"],
    )
    db_session.add(application)
    db_session.commit()

    try:
        log_action(
            None,
            school_id,
            "PARENT_ADMISSION_CONSENT_RECORDED",
            json.dumps(
                {
                    "application_id": application.id,
                    "application_code": application.application_code,
                    "status_token": application.status_token,
                    "consent_version": resolved_consent_version,
                    "accepted_ip": get_client_ip(),
                    "accepted_at": application.submitted_at.isoformat() if application.submitted_at else None,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as consent_log_error:
        logger.warning("Parent admission consent audit log failed for %s: %s", application.application_code, consent_log_error)

    status_path = build_parent_status_path(school_id, application.status_token)
    status_url = build_parent_public_url(status_path)
    email_sent = send_parent_admission_update(
        application,
        school,
        next_step="Keep this token safe and use the tracking link to monitor review updates from the school.",
    )

    return {
        "message": "Admission application submitted.",
        "application": application.to_public_dict(),
        "school": get_public_school_profile_payload(school, settings),
        "status_token": application.status_token,
        "status_path": status_path,
        "status_url": status_url,
        "payment_summary": build_parent_admission_payment_payload(application, school, settings),
        "consent_recorded": True,
        "notification": {
            "email_sent": email_sent,
            "sms_preview": build_parent_notification_sms(
                application.guardian_name,
                school.name,
                application.application_code,
                application.status_token,
                status_url,
            ) if application.parent_phone else None,
        },
    }, None, 201


def resubmit_parent_admission_application(
    school_id,
    status_token,
    payload,
    passport_photo,
    documents,
    school_model,
    parent_admission_application_model,
    valid_grades,
    sanitize_string,
    extract_parent_admission_document_details,
    store_parent_admission_document,
    build_ai_registrar_assessment,
    send_parent_admission_update,
    build_parent_status_path,
    db_session,
):
    school = school_model.query.filter_by(id=school_id, is_active=True).first()
    if not school:
        return None, {"message": "School not found"}, 404

    application = parent_admission_application_model.query.filter_by(
        school_id=school_id,
        status_token=status_token,
    ).first()
    if not application:
        return None, {"message": "Application not found"}, 404
    if application.status in {"Approved", "Rejected"}:
        return None, {"message": "This application can no longer be updated."}, 409

    merged_payload = {
        "guardian_name": sanitize_string(payload.get("guardian_name") or application.guardian_name or ""),
        "parent_email": sanitize_string(payload.get("parent_email") or application.parent_email or ""),
        "parent_phone": sanitize_string(payload.get("parent_phone") or application.parent_phone or ""),
        "preferred_class": sanitize_string(payload.get("preferred_class") or application.preferred_class or ""),
        "desired_test_mode": sanitize_string(payload.get("desired_test_mode") or application.desired_test_mode or "either"),
        "internet_quality": sanitize_string(payload.get("internet_quality") or application.internet_quality or "unknown"),
    }

    if not merged_payload["guardian_name"]:
        return None, {"message": "guardian_name is required"}, 400
    if not merged_payload["parent_email"] and not merged_payload["parent_phone"]:
        return None, {"message": "Provide at least parent_email or parent_phone"}, 400
    if merged_payload["preferred_class"] not in valid_grades:
        return None, {"message": f"preferred_class must be one of: {', '.join(valid_grades)}"}, 400

    application.guardian_name = merged_payload["guardian_name"]
    application.parent_email = merged_payload["parent_email"] or None
    application.parent_phone = merged_payload["parent_phone"] or None
    application.preferred_class = merged_payload["preferred_class"]
    application.desired_test_mode = merged_payload["desired_test_mode"] or "either"
    application.internet_quality = merged_payload["internet_quality"] or "unknown"
    application.prior_school = sanitize_string(payload.get("prior_school") or application.prior_school or "") or None

    new_notes = sanitize_string(payload.get("parent_notes") or "")
    if new_notes:
        existing_notes = (application.parent_notes or "").strip()
        application.parent_notes = f"{existing_notes}\n\nCorrection update: {new_notes}".strip()

    document_manifest = list(application.document_manifest or [])
    if passport_photo and getattr(passport_photo, "filename", None):
        file_bytes = passport_photo.read()
        if file_bytes:
            entry = extract_parent_admission_document_details(
                passport_photo.filename,
                passport_photo.mimetype,
                file_bytes,
                category_override="passport_photo",
            )
            entry.update(store_parent_admission_document(school_id, passport_photo, file_bytes))
            entry["submitted_in_correction"] = True
            entry["is_primary_photo"] = True
            document_manifest.append(entry)

    for uploaded in documents:
        if not uploaded or not getattr(uploaded, "filename", None):
            continue
        file_bytes = uploaded.read()
        entry = extract_parent_admission_document_details(uploaded.filename, uploaded.mimetype, file_bytes)
        entry.update(store_parent_admission_document(school_id, uploaded, file_bytes))
        entry["submitted_in_correction"] = True
        document_manifest.append(entry)

    application.document_manifest = document_manifest
    assessment = build_ai_registrar_assessment(
        {
            "guardian_name": application.guardian_name,
            "parent_email": application.parent_email,
            "parent_phone": application.parent_phone,
            "preferred_class": application.preferred_class,
            "desired_test_mode": application.desired_test_mode,
            "internet_quality": application.internet_quality,
        },
        document_manifest,
    )
    application.ai_summary = assessment["summary"]
    application.ai_recommendation = assessment["recommendation"]
    application.ai_readiness_score = assessment["readiness_score"]
    application.ai_flags = assessment["flags"]
    application.ai_missing_items = assessment["missing_items"]
    application.status = assessment["status"]
    db_session.commit()

    send_parent_admission_update(
        application,
        school,
        next_step="Your correction update has been received. Use the same tracking link to monitor the next school review decision.",
    )

    return {
        "message": "Application updated successfully.",
        "application": application.to_public_dict(),
        "status_path": build_parent_status_path(school_id, application.status_token),
    }, None, 200


def review_parent_admission_application(
    application_id,
    school_id,
    payload,
    reviewer_id,
    parent_admission_application_model,
    school_model,
    school_settings_model,
    sanitize_string,
    get_utc_now,
    get_parent_admission_workflow_config,
    build_parent_admission_follow_up_plan,
    parse_parent_admission_review_notes,
    build_parent_admission_response_message,
    serialize_parent_admission_review_notes,
    set_parent_admission_payment_summary,
    normalize_parent_admission_payment_summary,
    get_school_admission_fee_config,
    build_staff_parent_admission_payload,
    admit_student_from_payload,
    send_parent_admission_update,
    log_action,
    db_session,
):
    application = parent_admission_application_model.query.filter_by(
        id=application_id,
        school_id=school_id,
    ).first()
    if not application:
        return None, {"message": "Application not found"}, 404

    action = sanitize_string(payload.get("action") or "").lower()
    reviewer_notes = sanitize_string(payload.get("notes") or "")

    action_map = {
        "approve": "Approved",
        "reject": "Rejected",
        "request_correction": "NeedsCorrection",
        "invite_test": "TestReady",
        "schedule_visit": "VisitRequired",
    }
    if action not in action_map:
        return None, {"message": "Invalid review action"}, 400

    application.reviewed_by_user_id = reviewer_id
    application.reviewed_at = get_utc_now()
    application.status = action_map[action]

    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    workflow_config = get_parent_admission_workflow_config(settings)
    school = school_model.query.get(school_id)
    class_assigned = sanitize_string(payload.get("class_assigned") or application.preferred_class)
    try:
        follow_up_plan = build_parent_admission_follow_up_plan(action, payload, workflow_config)
    except ValueError as exc:
        return None, {"message": str(exc)}, 400

    if action == "schedule_visit" and not follow_up_plan and not reviewer_notes:
        return None, {"message": "Provide visit details or reviewer notes before marking the school visit as required."}, 400

    existing_payment_summary = parse_parent_admission_review_notes(application.reviewer_notes).get("payment_summary")

    parent_response_message = build_parent_admission_response_message(
        action,
        application,
        school,
        workflow_config,
        class_assigned=class_assigned,
        follow_up_plan=follow_up_plan,
    )
    application.reviewer_notes = serialize_parent_admission_review_notes(
        reviewer_notes,
        parent_response_message,
        follow_up_plan=follow_up_plan,
        class_assigned=class_assigned if action == "approve" else None,
    )
    if existing_payment_summary:
        set_parent_admission_payment_summary(
            application,
            normalize_parent_admission_payment_summary(
                existing_payment_summary,
                fee_config=get_school_admission_fee_config(settings),
            ),
        )

    response_payload = {
        "message": f"Application marked as {application.status}.",
        "application": build_staff_parent_admission_payload(application, settings, school_id),
    }

    if action == "approve":
        if application.admitted_student_id:
            return None, {"message": "Application has already been approved and converted to a student."}, 409
        admission_payload = {
            "first_name": application.first_name,
            "surname": application.surname,
            "gender": application.gender,
            "date_of_birth": application.date_of_birth.isoformat() if application.date_of_birth else None,
            "class_assigned": class_assigned,
            "guardian_name": application.guardian_name,
            "parent_name": application.guardian_name,
            "parent_email": application.parent_email,
            "parent_phone": application.parent_phone,
            "score": application.ai_readiness_score,
            "scholarship_type": "none",
        }
        try:
            student, _school, _scholarship_type, warning, proration_result = admit_student_from_payload(
                school_id,
                admission_payload,
                reviewer_id,
            )
        except ValueError as exc:
            db_session.rollback()
            status_code = 400 if "Invalid" in str(exc) or "Missing" in str(exc) else 403
            return None, {"message": str(exc)}, status_code

        application.admitted_student_id = student.id
        application.status = "Approved"
        db_session.commit()
        response_payload.update(
            {
                "message": f"Application approved and {student.name} admitted.",
                "student_id": student.id,
                "student_code": student.student_code,
                "warning": warning,
                "billing_notice": proration_result if proration_result.get("prorated_charge") else None,
                "application": build_staff_parent_admission_payload(application, settings, school_id),
            }
        )
        send_parent_admission_update(
            application,
            school,
            next_step=parent_response_message + " Contact the school directly for any approved charges, including admission fee if your school applies one.",
        )
    else:
        db_session.commit()
        next_step = parent_response_message
        if reviewer_notes:
            next_step = f"{next_step} School note: {reviewer_notes}"
        send_parent_admission_update(
            application,
            school,
            next_step=next_step,
        )

    log_action(
        reviewer_id,
        school_id,
        "PARENT_ADMISSION_REVIEWED",
        json.dumps(
            {
                "application_id": application.id,
                "application_code": application.application_code,
                "action": action,
                "status": application.status,
            }
        ),
    )

    return response_payload, None, 200
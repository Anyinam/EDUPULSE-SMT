import json
from datetime import datetime, timezone


def get_school_settings_payload(
    school_id,
    actor_id,
    remote_addr,
    school_model,
    school_settings_model,
    teacher_class_level_exam_summaries_key,
    get_enabled_modules,
    get_parent_admission_workflow_config,
    get_data_compliance_workflow_config,
    get_payment_provider_settings,
    masked_bank_fields_for_school,
    get_report_global_settings,
    has_ai_registrar_access,
    log_action,
):
    school = school_model.query.get(school_id)
    if not school:
        return None, {"message": "School not found"}, 404

    log_action(
        actor_id,
        school_id,
        "SETTINGS_VIEWED",
        json.dumps(
            {
                "module": "school_settings",
                "contains_bank_fields": True,
                "ip": remote_addr,
            }
        ),
    )

    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    enabled_modules = get_enabled_modules(settings)
    workflow_config = get_parent_admission_workflow_config(settings)
    compliance_workflow = get_data_compliance_workflow_config(settings)
    provider_settings = get_payment_provider_settings(settings)
    registration_ack = compliance_workflow.get("registration_acknowledgements") or {}
    legacy_migration = compliance_workflow.get("legacy_migration") or {}
    consent_plan_confirmed = bool(registration_ack.get("legacy_and_exam_consent_plan_confirmed"))
    bece_result_processing_enabled = bool(legacy_migration.get("bece_result_processing_enabled", False) or consent_plan_confirmed)
    bece_parent_notice_confirmed = bool(legacy_migration.get("bece_parent_notice_confirmed", False) or consent_plan_confirmed)
    masked_bank_fields = masked_bank_fields_for_school(school)

    return {
        "name": school.name,
        "motto": school.motto,
        "logo_url": school.logo_url,
        "primary_color": school.primary_color,
        "school_email": school.school_email,
        "school_phone": school.school_phone,
        "school_address": school.school_address,
        "school_website": school.school_website,
        "bank_name": masked_bank_fields["bank_name"],
        "bank_account": masked_bank_fields["bank_account"],
        "bank_account_name": masked_bank_fields["bank_account_name"],
        "bank_branch": masked_bank_fields["bank_branch"],
        "paystack_subaccount_code": provider_settings.get("paystack_subaccount_code", ""),
        "paystack_bank_code": provider_settings.get("paystack_bank_code", ""),
        "paystack_resolved_account_name": provider_settings.get("paystack_resolved_account_name", ""),
        "bank_details_masked": True,
        "country_code": settings.country_code if settings and settings.country_code else "GH",
        "anniversary_date": settings.anniversary_date.isoformat() if settings and settings.anniversary_date else None,
        "next_term_reopen_date": get_report_global_settings(settings).get("next_term_reopen_date") if settings else None,
        "ai_registrar_enabled": has_ai_registrar_access(school),
        "ai_registrar_addon_enabled": has_ai_registrar_access(school),
        "ai_bursar_addon_enabled": bool(enabled_modules.get("ai_bursar_addon", False)),
        "admissions_visit_location_default": workflow_config["visit_defaults"].get("location", ""),
        "admissions_visit_contact_person_default": workflow_config["visit_defaults"].get("contact_person", ""),
        "admissions_visit_contact_phone_default": workflow_config["visit_defaults"].get("contact_phone", ""),
        "admissions_approve_message_template": workflow_config["response_templates"].get("approve"),
        "admissions_reject_message_template": workflow_config["response_templates"].get("reject"),
        "admissions_correction_message_template": workflow_config["response_templates"].get("request_correction"),
        "admissions_online_test_message_template": workflow_config["response_templates"].get("invite_test"),
        "admissions_visit_message_template": workflow_config["response_templates"].get("schedule_visit"),
        "approval_pdf_enabled": bool(settings.approval_pdf_enabled) if settings else False,
        "approval_pdf_delivery_mode": settings.approval_pdf_delivery_mode if settings and settings.approval_pdf_delivery_mode else "email_link",
        "approval_pdf_include_payment_summary": bool(settings.approval_pdf_include_payment_summary) if settings else True,
        "approval_pdf_include_required_items": bool(settings.approval_pdf_include_required_items) if settings else True,
        "approval_pdf_required_items": settings.approval_pdf_required_items if settings and settings.approval_pdf_required_items else "",
        "data_compliance_school_authority_confirmed": bool(registration_ack.get("school_data_authority_confirmed", False)),
        "data_compliance_aggregated_analytics_accepted": bool(registration_ack.get("aggregated_analytics_accepted", False)),
        "data_compliance_registration_confirmed_at": registration_ack.get("accepted_at"),
        "data_compliance_registration_confirmed_ip": registration_ack.get("accepted_ip"),
        "legacy_parent_notice_dispatched": bool(legacy_migration.get("parent_notice_dispatched", False)),
        "legacy_consent_collection_completed": bool(legacy_migration.get("consent_collection_completed", False)),
        "legacy_consent_collection_date": legacy_migration.get("consent_collection_date") or "",
        "legacy_consent_evidence_notes": legacy_migration.get("evidence_notes") or "",
        "legacy_consent_evidence_artifact_count": len(legacy_migration.get("evidence_artifacts") or []),
        "bece_result_processing_enabled": bece_result_processing_enabled,
        "bece_parent_notice_confirmed": bece_parent_notice_confirmed,
        "teacher_class_level_exam_summaries_enabled": bool(get_report_global_settings(settings).get(teacher_class_level_exam_summaries_key, False)),
    }, None, 200


def update_school_settings(
    data,
    school_id,
    actor_id,
    remote_addr,
    school_model,
    school_settings_model,
    default_parent_admission_workflow,
    teacher_class_level_exam_summaries_key,
    sanitize_string,
    masked_bank_fields_for_school,
    get_payment_provider_settings,
    set_payment_provider_settings,
    set_report_global_setting,
    get_parent_admission_workflow_config,
    set_parent_admission_workflow_config,
    get_data_compliance_workflow_config,
    set_data_compliance_workflow_config,
    school_bank_details_ready_for_paystack,
    provision_school_paystack_subaccount,
    has_ai_registrar_access,
    log_action,
    logger,
    db_session,
):
    school = school_model.query.get(school_id)
    settings = school_settings_model.query.filter_by(school_id=school_id).first()
    if not settings:
        settings = school_settings_model(school_id=school_id)
        db_session.add(settings)

    changed_fields = []
    bank_fields_changed = []
    compliance_changed_fields = []
    workflow_changed = False
    provider_settings_changed = False
    paystack_subaccount_result = None

    if "name" in data:
        school.name = data["name"]
        changed_fields.append("name")
    if "logo_url" in data:
        school.logo_url = data["logo_url"]
        changed_fields.append("logo_url")
    if "primary_color" in data:
        school.primary_color = data["primary_color"]
        changed_fields.append("primary_color")
    if "motto" in data:
        school.motto = data["motto"]
        changed_fields.append("motto")
    if "school_email" in data:
        school.school_email = data["school_email"]
        changed_fields.append("school_email")
    if "school_phone" in data:
        school.school_phone = data["school_phone"]
        changed_fields.append("school_phone")
    if "school_address" in data:
        school.school_address = data["school_address"]
        changed_fields.append("school_address")
    if "school_website" in data:
        school.school_website = data["school_website"]
        changed_fields.append("school_website")

    masked_bank_fields = masked_bank_fields_for_school(school)

    if "bank_name" in data:
        incoming_bank_name = data["bank_name"]
        if incoming_bank_name != masked_bank_fields["bank_name"]:
            school.bank_name = incoming_bank_name
            changed_fields.append("bank_name")
            bank_fields_changed.append("bank_name")
    if "bank_account" in data:
        incoming_bank_account = data["bank_account"]
        if incoming_bank_account != masked_bank_fields["bank_account"]:
            school.bank_account = incoming_bank_account
            changed_fields.append("bank_account")
            bank_fields_changed.append("bank_account")
    if "bank_account_name" in data:
        incoming_account_name = data["bank_account_name"]
        if incoming_account_name != masked_bank_fields["bank_account_name"]:
            school.bank_account_name = incoming_account_name
            changed_fields.append("bank_account_name")
            bank_fields_changed.append("bank_account_name")
    if "bank_branch" in data:
        incoming_bank_branch = data["bank_branch"]
        if incoming_bank_branch != masked_bank_fields["bank_branch"]:
            school.bank_branch = incoming_bank_branch
            changed_fields.append("bank_branch")
            bank_fields_changed.append("bank_branch")

    provider_settings = get_payment_provider_settings(settings)
    if "country_code" in data:
        settings.country_code = (data["country_code"] or "GH").upper()
        changed_fields.append("country_code")
    if "anniversary_date" in data:
        from datetime import datetime as dt

        if data["anniversary_date"]:
            settings.anniversary_date = dt.strptime(data["anniversary_date"], "%Y-%m-%d").date()
        else:
            settings.anniversary_date = None
        changed_fields.append("anniversary_date")
    if "next_term_reopen_date" in data:
        next_term_reopen_date = (data.get("next_term_reopen_date") or "").strip()
        if next_term_reopen_date:
            from datetime import datetime as dt

            try:
                dt.strptime(next_term_reopen_date, "%Y-%m-%d").date()
            except ValueError:
                return None, {"message": "Invalid next_term_reopen_date format. Use YYYY-MM-DD."}, 400
        set_report_global_setting(settings, "next_term_reopen_date", next_term_reopen_date or None)
        changed_fields.append("next_term_reopen_date")

    workflow_config = get_parent_admission_workflow_config(settings)
    compliance_workflow = get_data_compliance_workflow_config(settings)

    if "admissions_visit_location_default" in data:
        workflow_config["visit_defaults"]["location"] = sanitize_string(data.get("admissions_visit_location_default") or "") or ""
        workflow_changed = True
        changed_fields.append("admissions_visit_location_default")
    if "admissions_visit_contact_person_default" in data:
        workflow_config["visit_defaults"]["contact_person"] = sanitize_string(data.get("admissions_visit_contact_person_default") or "") or ""
        workflow_changed = True
        changed_fields.append("admissions_visit_contact_person_default")
    if "admissions_visit_contact_phone_default" in data:
        workflow_config["visit_defaults"]["contact_phone"] = sanitize_string(data.get("admissions_visit_contact_phone_default") or "") or ""
        workflow_changed = True
        changed_fields.append("admissions_visit_contact_phone_default")
    if "admissions_approve_message_template" in data:
        workflow_config["response_templates"]["approve"] = sanitize_string(data.get("admissions_approve_message_template") or "") or default_parent_admission_workflow["response_templates"]["approve"]
        workflow_changed = True
        changed_fields.append("admissions_approve_message_template")
    if "admissions_reject_message_template" in data:
        workflow_config["response_templates"]["reject"] = sanitize_string(data.get("admissions_reject_message_template") or "") or default_parent_admission_workflow["response_templates"]["reject"]
        workflow_changed = True
        changed_fields.append("admissions_reject_message_template")
    if "admissions_correction_message_template" in data:
        workflow_config["response_templates"]["request_correction"] = sanitize_string(data.get("admissions_correction_message_template") or "") or default_parent_admission_workflow["response_templates"]["request_correction"]
        workflow_changed = True
        changed_fields.append("admissions_correction_message_template")
    if "admissions_online_test_message_template" in data:
        workflow_config["response_templates"]["invite_test"] = sanitize_string(data.get("admissions_online_test_message_template") or "") or default_parent_admission_workflow["response_templates"]["invite_test"]
        workflow_changed = True
        changed_fields.append("admissions_online_test_message_template")
    if "admissions_visit_message_template" in data:
        workflow_config["response_templates"]["schedule_visit"] = sanitize_string(data.get("admissions_visit_message_template") or "") or default_parent_admission_workflow["response_templates"]["schedule_visit"]
        workflow_changed = True
        changed_fields.append("admissions_visit_message_template")
    if workflow_changed:
        set_parent_admission_workflow_config(settings, workflow_config)

    if "paystack_subaccount_code" in data:
        provider_settings["paystack_subaccount_code"] = sanitize_string(data.get("paystack_subaccount_code") or "") or ""
        provider_settings_changed = True
        changed_fields.append("paystack_subaccount_code")
    if provider_settings_changed:
        set_payment_provider_settings(settings, provider_settings)

    if "data_compliance_school_authority_confirmed" in data:
        confirmed = bool(data.get("data_compliance_school_authority_confirmed"))
        compliance_workflow["registration_acknowledgements"]["school_data_authority_confirmed"] = confirmed
        if confirmed:
            if not compliance_workflow["registration_acknowledgements"].get("accepted_at"):
                compliance_workflow["registration_acknowledgements"]["accepted_at"] = datetime.now(timezone.utc).isoformat()
            if not compliance_workflow["registration_acknowledgements"].get("accepted_ip"):
                compliance_workflow["registration_acknowledgements"]["accepted_ip"] = remote_addr
            if actor_id is not None and not compliance_workflow["registration_acknowledgements"].get("proprietor_user_id"):
                compliance_workflow["registration_acknowledgements"]["proprietor_user_id"] = actor_id
        compliance_changed_fields.append("data_compliance_school_authority_confirmed")
    if "legacy_parent_notice_dispatched" in data:
        compliance_workflow["legacy_migration"]["parent_notice_dispatched"] = bool(data.get("legacy_parent_notice_dispatched"))
        compliance_changed_fields.append("legacy_parent_notice_dispatched")
    if "legacy_consent_collection_completed" in data:
        compliance_workflow["legacy_migration"]["consent_collection_completed"] = bool(data.get("legacy_consent_collection_completed"))
        compliance_changed_fields.append("legacy_consent_collection_completed")
    if "legacy_consent_collection_date" in data:
        consent_collection_date = sanitize_string(data.get("legacy_consent_collection_date") or "") or None
        if consent_collection_date:
            from datetime import datetime as dt

            try:
                dt.strptime(consent_collection_date, "%Y-%m-%d")
            except ValueError:
                return None, {"message": "Invalid legacy_consent_collection_date format. Use YYYY-MM-DD."}, 400
        compliance_workflow["legacy_migration"]["consent_collection_date"] = consent_collection_date
        compliance_changed_fields.append("legacy_consent_collection_date")
    if "legacy_consent_evidence_notes" in data:
        compliance_workflow["legacy_migration"]["evidence_notes"] = sanitize_string(data.get("legacy_consent_evidence_notes") or "") or ""
        compliance_changed_fields.append("legacy_consent_evidence_notes")
    if "bece_result_processing_enabled" in data:
        compliance_workflow["legacy_migration"]["bece_result_processing_enabled"] = bool(data.get("bece_result_processing_enabled"))
        compliance_changed_fields.append("bece_result_processing_enabled")
    if "bece_parent_notice_confirmed" in data:
        compliance_workflow["legacy_migration"]["bece_parent_notice_confirmed"] = bool(data.get("bece_parent_notice_confirmed"))
        compliance_changed_fields.append("bece_parent_notice_confirmed")
    if "teacher_class_level_exam_summaries_enabled" in data:
        set_report_global_setting(
            settings,
            teacher_class_level_exam_summaries_key,
            bool(data.get("teacher_class_level_exam_summaries_enabled")),
        )
        changed_fields.append("teacher_class_level_exam_summaries_enabled")
    if compliance_changed_fields:
        set_data_compliance_workflow_config(settings, compliance_workflow)
        changed_fields.extend(compliance_changed_fields)

    if "whatsapp_daily_limit" in data:
        settings.whatsapp_daily_limit = max(5, int(data.get("whatsapp_daily_limit") or 50))
        changed_fields.append("whatsapp_daily_limit")
    if "whatsapp_notifications_enabled" in data:
        settings.whatsapp_notifications_enabled = bool(data.get("whatsapp_notifications_enabled", True))
        changed_fields.append("whatsapp_notifications_enabled")
    if "approval_pdf_enabled" in data:
        if bool(data.get("approval_pdf_enabled")) and not has_ai_registrar_access(school):
            return None, {"message": "Approval PDFs require a paid subscription plan with AI Registrar included."}, 403
        settings.approval_pdf_enabled = bool(data.get("approval_pdf_enabled"))
        changed_fields.append("approval_pdf_enabled")
    if "approval_pdf_delivery_mode" in data:
        delivery_mode = (data.get("approval_pdf_delivery_mode") or "email_link").strip()
        if delivery_mode not in {"status_page_only", "email_link", "email_attachment"}:
            return None, {"message": "Invalid approval_pdf_delivery_mode."}, 400
        settings.approval_pdf_delivery_mode = delivery_mode
        changed_fields.append("approval_pdf_delivery_mode")
    if "approval_pdf_include_payment_summary" in data:
        settings.approval_pdf_include_payment_summary = bool(data.get("approval_pdf_include_payment_summary"))
        changed_fields.append("approval_pdf_include_payment_summary")
    if "approval_pdf_include_required_items" in data:
        settings.approval_pdf_include_required_items = bool(data.get("approval_pdf_include_required_items"))
        changed_fields.append("approval_pdf_include_required_items")
    if "approval_pdf_required_items" in data:
        settings.approval_pdf_required_items = sanitize_string(data.get("approval_pdf_required_items") or "") or None
        changed_fields.append("approval_pdf_required_items")

    manual_subaccount_override = bool(
        sanitize_string(data.get("paystack_subaccount_code") or "")
    ) if "paystack_subaccount_code" in data else False
    missing_subaccount_with_ready_bank_details = (
        not manual_subaccount_override
        and not sanitize_string(provider_settings.get("paystack_subaccount_code") or "")
        and school_bank_details_ready_for_paystack(school)
    )
    should_provision_subaccount = not manual_subaccount_override and (
        bool(bank_fields_changed) or missing_subaccount_with_ready_bank_details
    )
    if should_provision_subaccount:
        provider_settings = get_payment_provider_settings(settings)
        paystack_subaccount_result, provision_error = provision_school_paystack_subaccount(school, settings, provider_settings)
        if provision_error:
            logger.error(
                "Paystack subaccount provisioning failed for school %s: %s",
                school_id,
                provision_error,
            )
            db_session.rollback()
            return None, {
                "message": "EduPulse could not connect the school's Paystack settlement account right now. Confirm the bank details and try saving again.",
                "error": "payment_settlement_setup_unavailable",
                "provider_detail": provision_error,
            }, 502
        changed_fields.extend([
            "paystack_bank_code",
            "paystack_resolved_account_name",
            "paystack_subaccount_code",
        ])

    log_action(
        actor_id,
        school_id,
        "SETTINGS_UPDATE",
        json.dumps(
            {
                "updated_fields": changed_fields,
                "ip": remote_addr,
            }
        ),
    )

    if bank_fields_changed:
        log_action(
            actor_id,
            school_id,
            "BANK_DETAILS_UPDATED",
            json.dumps(
                {
                    "updated_fields": bank_fields_changed,
                    "contains_sensitive_data": True,
                    "ip": remote_addr,
                }
            ),
        )
    if compliance_changed_fields:
        log_action(
            actor_id,
            school_id,
            "DATA_COMPLIANCE_SETTINGS_UPDATED",
            json.dumps(
                {
                    "updated_fields": compliance_changed_fields,
                    "ip": remote_addr,
                }
            ),
        )
    db_session.commit()

    response_payload = {"message": "Settings updated."}
    if paystack_subaccount_result:
        response_payload.update(
            {
                "message": f"Settings updated. Paystack subaccount {paystack_subaccount_result['action']} automatically.",
                "paystack_subaccount_code": paystack_subaccount_result["subaccount_code"],
                "paystack_bank_code": paystack_subaccount_result["bank_code"],
                "paystack_resolved_account_name": paystack_subaccount_result["resolved_account_name"],
            }
        )
    return response_payload, None, 200
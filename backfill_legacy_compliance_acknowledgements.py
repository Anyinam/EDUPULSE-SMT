#!/usr/bin/env python3
"""Backfill legacy data-compliance registration acknowledgements for existing schools.

Why this exists:
- Older schools may predate registration acknowledgement fields now used by
  exam-intelligence readiness checks.
- This script performs a one-time backfill so legacy tenants are not blocked
  unexpectedly when importing WAEC/BECE result data.

Behavior:
- Reads each school's compliance workflow payload from SchoolSettings.
- If registration acknowledgement flags are missing/false, it backfills them
  using available audit evidence where possible.
- Applies an explicit legacy migration rule when evidence is absent.
- Writes a per-school audit log entry for traceability.

Usage:
- Dry run (default):
  python backfill_legacy_compliance_acknowledgements.py
- Apply changes:
  python backfill_legacy_compliance_acknowledgements.py --apply
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text

from backend.api.api import app
from backend.api.models import AuditLog, db
from backend.routes import _get_data_compliance_workflow_config, _set_data_compliance_workflow_config

BACKFILL_ACTION = "LEGACY_COMPLIANCE_BACKFILLED"
POLICY_ACCEPT_ACTION = "REGISTRATION_POLICY_ACCEPTED"
COMPLIANCE_ACCEPT_ACTION = "REGISTRATION_DATA_COMPLIANCE_ACKNOWLEDGED"


class _SettingsProxy:
    """Minimal settings-like object for reuse of workflow normalizers."""

    def __init__(self, school_id: str, report_template_config: Optional[Dict[str, Any]] = None):
        self.school_id = school_id
        self.report_template_config = report_template_config or {}


def _safe_json_loads(raw_value: Optional[str]) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_accepted_at(policy_log: Optional[AuditLog], compliance_log: Optional[AuditLog]) -> str:
    policy_details = _safe_json_loads(policy_log.details if policy_log else "")
    compliance_details = _safe_json_loads(compliance_log.details if compliance_log else "")

    for candidate in (
        policy_details.get("accepted_at"),
        compliance_details.get("accepted_at"),
        policy_log.timestamp.isoformat() if policy_log and policy_log.timestamp else None,
        compliance_log.timestamp.isoformat() if compliance_log and compliance_log.timestamp else None,
    ):
        if candidate:
            return str(candidate)

    return _iso_now()


def _pick_accepted_ip(policy_log: Optional[AuditLog], compliance_log: Optional[AuditLog]) -> Optional[str]:
    policy_details = _safe_json_loads(policy_log.details if policy_log else "")
    compliance_details = _safe_json_loads(compliance_log.details if compliance_log else "")

    for candidate in (
        policy_details.get("accepted_ip"),
        compliance_details.get("accepted_ip"),
    ):
        if candidate:
            return str(candidate)

    return None


def _pick_proprietor_actor_id(policy_log: Optional[AuditLog], compliance_log: Optional[AuditLog]) -> Optional[int]:
    for candidate in (
        policy_log.actor_id if policy_log else None,
        compliance_log.actor_id if compliance_log else None,
    ):
        if isinstance(candidate, int):
            return candidate
    return None


def _latest_log(school_id: str, action: str) -> Optional[AuditLog]:
    return (
        AuditLog.query.filter_by(school_id=school_id, action=action)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .first()
    )


def _upsert_school_settings_report_template_config(school_id: str, report_template_config: Dict[str, Any]) -> None:
    existing_row = db.session.execute(
        text("SELECT id FROM school_settings WHERE school_id = :school_id LIMIT 1"),
        {"school_id": school_id},
    ).first()

    payload = json.dumps(report_template_config, ensure_ascii=False)
    if existing_row:
        db.session.execute(
            text(
                """
                UPDATE school_settings
                SET report_template_config = :payload
                WHERE school_id = :school_id
                """
            ),
            {"payload": payload, "school_id": school_id},
        )
    else:
        db.session.execute(
            text(
                """
                INSERT INTO school_settings (school_id, report_template_config)
                VALUES (:school_id, :payload)
                """
            ),
            {"school_id": school_id, "payload": payload},
        )


def _backfill_school(
    school_id: str,
    settings_proxy: _SettingsProxy,
    apply_changes: bool,
    use_explicit_legacy_rule: bool,
) -> Dict[str, Any]:
    workflow = _get_data_compliance_workflow_config(settings_proxy)
    registration_ack = workflow.get("registration_acknowledgements") or {}

    had_school_authority = bool(registration_ack.get("school_data_authority_confirmed"))
    had_consent_plan = bool(registration_ack.get("legacy_and_exam_consent_plan_confirmed"))

    needs_backfill = not (had_school_authority and had_consent_plan)
    if not needs_backfill:
        return {
            "school_id": school_id,
            "changed": False,
            "reason": "already_complete",
        }

    policy_log = _latest_log(school_id, POLICY_ACCEPT_ACTION)
    compliance_log = _latest_log(school_id, COMPLIANCE_ACCEPT_ACTION)

    policy_details = _safe_json_loads(policy_log.details if policy_log else "")
    compliance_details = _safe_json_loads(compliance_log.details if compliance_log else "")

    school_authority_from_evidence = bool(
        compliance_details.get("school_data_authority_confirmed")
        or policy_log
        or compliance_log
    )
    consent_plan_from_evidence = bool(
        compliance_details.get("legacy_and_exam_consent_plan_confirmed")
    )

    # Explicit admin migration rule for legacy tenants:
    # If evidence for policy acceptance exists (or rule is enabled), ensure both
    # registration acknowledgement flags are marked true.
    should_apply_legacy_rule = bool(
        use_explicit_legacy_rule and (policy_log or compliance_log or not consent_plan_from_evidence)
    )

    updated_school_authority = had_school_authority or school_authority_from_evidence or should_apply_legacy_rule
    updated_consent_plan = had_consent_plan or consent_plan_from_evidence or should_apply_legacy_rule

    if not (updated_school_authority and updated_consent_plan):
        return {
            "school_id": school_id,
            "changed": False,
            "reason": "insufficient_evidence",
        }

    accepted_at = registration_ack.get("accepted_at") or _pick_accepted_at(policy_log, compliance_log)
    accepted_ip = registration_ack.get("accepted_ip") or _pick_accepted_ip(policy_log, compliance_log)
    proprietor_user_id = registration_ack.get("proprietor_user_id")
    if not isinstance(proprietor_user_id, int):
        proprietor_user_id = _pick_proprietor_actor_id(policy_log, compliance_log)

    updated_registration_ack = {
        **registration_ack,
        "school_data_authority_confirmed": True,
        "legacy_and_exam_consent_plan_confirmed": True,
        "accepted_at": accepted_at,
        "accepted_ip": accepted_ip,
        "terms_version": registration_ack.get("terms_version"),
        "policy_version": registration_ack.get("policy_version"),
        "proprietor_user_id": proprietor_user_id,
    }
    workflow["registration_acknowledgements"] = updated_registration_ack

    change_details = {
        "script": "backfill_legacy_compliance_acknowledgements.py",
        "school_id": school_id,
        "updated_fields": [
            "school_data_authority_confirmed",
            "legacy_and_exam_consent_plan_confirmed",
            "accepted_at",
            "accepted_ip",
        ],
        "source": {
            "policy_log_found": bool(policy_log),
            "compliance_log_found": bool(compliance_log),
            "used_explicit_legacy_rule": bool(should_apply_legacy_rule),
        },
    }

    if apply_changes:
        _set_data_compliance_workflow_config(settings_proxy, workflow)
        _upsert_school_settings_report_template_config(school_id, settings_proxy.report_template_config)
        db.session.add(
            AuditLog(
                school_id=school_id,
                actor_id=proprietor_user_id,
                action=BACKFILL_ACTION,
                details=json.dumps(change_details, ensure_ascii=False),
                timestamp=datetime.now(timezone.utc),
            )
        )

    return {
        "school_id": school_id,
        "changed": True,
        "reason": "backfilled",
        "details": change_details,
    }


def run_backfill(apply_changes: bool, use_explicit_legacy_rule: bool) -> int:
    school_ids = db.session.execute(text("SELECT id FROM schools ORDER BY id ASC")).scalars().all()

    processed = 0
    changed = 0
    skipped = 0

    for school_id in school_ids:
        processed += 1
        settings_row = db.session.execute(
            text(
                """
                SELECT report_template_config
                FROM school_settings
                WHERE school_id = :school_id
                LIMIT 1
                """
            ),
            {"school_id": school_id},
        ).first()

        config_payload = settings_row[0] if settings_row else None
        if isinstance(config_payload, str):
            try:
                config_payload = json.loads(config_payload)
            except Exception:
                config_payload = {}
        if not isinstance(config_payload, dict):
            config_payload = {}

        settings_proxy = _SettingsProxy(school_id=school_id, report_template_config=config_payload)

        result = _backfill_school(
            school_id=school_id,
            settings_proxy=settings_proxy,
            apply_changes=apply_changes,
            use_explicit_legacy_rule=use_explicit_legacy_rule,
        )
        if result.get("changed"):
            changed += 1
            print(f"[OK]   {school_id}: backfilled registration acknowledgements")
        else:
            skipped += 1
            print(f"[SKIP] {school_id}: {result.get('reason')}")

    if apply_changes:
        db.session.commit()
    else:
        db.session.rollback()

    print("\nSummary")
    print(f"- processed: {processed}")
    print(f"- changed:   {changed}")
    print(f"- skipped:   {skipped}")
    print(f"- mode:      {'apply' if apply_changes else 'dry-run'}")

    return changed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill legacy compliance registration acknowledgements")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag, the script runs as a dry run.",
    )
    parser.add_argument(
        "--no-explicit-legacy-rule",
        action="store_true",
        help="Disable the explicit legacy migration rule and use audit evidence only.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    use_explicit_legacy_rule = not args.no_explicit_legacy_rule

    print("Starting legacy compliance acknowledgement backfill...")
    print(f"- mode: {'apply' if args.apply else 'dry-run'}")
    print(f"- explicit legacy rule: {'enabled' if use_explicit_legacy_rule else 'disabled'}")

    with app.app_context():
        run_backfill(
            apply_changes=args.apply,
            use_explicit_legacy_rule=use_explicit_legacy_rule,
        )


if __name__ == "__main__":
    main()

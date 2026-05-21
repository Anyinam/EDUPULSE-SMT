"""External school KYB verification adapter.

Supports provider-agnostic automatic verification for services such as
Identitypass, Dojah, or Smile ID via environment-based configuration.

The adapter is intentionally conservative:
- It auto-approves only when the provider response is clearly clean.
- If the provider is unavailable or ambiguous, callers should fall back to
  local heuristics or route the school to manual review.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KYBProviderConfig:
    provider: str
    base_url: str
    verify_path: str
    api_key: str
    api_key_header: str
    timeout_seconds: int


def _first_nonempty(*values: Optional[str]) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def _provider_default_header(provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider == "smile_id":
        return "X-API-KEY"
    if provider == "dojah":
        return "Authorization"
    return "Authorization"


def _build_config() -> Optional[KYBProviderConfig]:
    provider = _first_nonempty(os.getenv("KYB_PROVIDER"), os.getenv("EDUPULSE_KYB_PROVIDER"), "identitypass").lower()

    base_url = _first_nonempty(
        os.getenv("KYB_BASE_URL"),
        os.getenv("EDUPULSE_KYB_BASE_URL"),
        os.getenv(f"{provider.upper()}_BASE_URL"),
    )
    verify_path = _first_nonempty(
        os.getenv("KYB_VERIFY_PATH"),
        os.getenv("EDUPULSE_KYB_VERIFY_PATH"),
        os.getenv(f"{provider.upper()}_VERIFY_PATH"),
        "/verify",
    )
    api_key = _first_nonempty(
        os.getenv("KYB_API_KEY"),
        os.getenv("EDUPULSE_KYB_API_KEY"),
        os.getenv(f"{provider.upper()}_API_KEY"),
    )
    api_key_header = _first_nonempty(
        os.getenv("KYB_API_KEY_HEADER"),
        os.getenv("EDUPULSE_KYB_API_KEY_HEADER"),
        os.getenv(f"{provider.upper()}_API_KEY_HEADER"),
        _provider_default_header(provider),
    )

    timeout_seconds_raw = _first_nonempty(
        os.getenv("KYB_TIMEOUT_SECONDS"),
        os.getenv("EDUPULSE_KYB_TIMEOUT_SECONDS"),
        "20",
    )
    try:
        timeout_seconds = max(3, int(timeout_seconds_raw))
    except Exception:
        timeout_seconds = 20

    if not base_url or not api_key:
        return None

    return KYBProviderConfig(
        provider=provider,
        base_url=base_url.rstrip("/"),
        verify_path=verify_path if verify_path.startswith("/") else f"/{verify_path}",
        api_key=api_key,
        api_key_header=api_key_header,
        timeout_seconds=timeout_seconds,
    )


def get_kyb_provider_status() -> Dict[str, Any]:
    config = _build_config()
    if not config:
        return {"configured": False, "provider": None}
    return {
        "configured": True,
        "provider": config.provider,
        "base_url": config.base_url,
        "verify_path": config.verify_path,
        "timeout_seconds": config.timeout_seconds,
    }


def _build_headers(config: KYBProviderConfig) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if (config.api_key_header or "").strip().lower() == "authorization":
        headers["Authorization"] = f"Bearer {config.api_key}"
    else:
        headers[config.api_key_header] = config.api_key
        headers.setdefault("Authorization", f"Bearer {config.api_key}")
    headers["X-EduPulse-KYB-Provider"] = config.provider
    return headers


def _normalize_risk_tier(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"low", "medium", "high", "critical"}:
        return text
    return "medium"


def _normalize_response(payload: Dict[str, Any], provider: str) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}

    raw_status = str(
        payload.get("verification_status")
        or payload.get("status")
        or payload.get("result")
        or payload.get("outcome")
        or ""
    ).strip().lower()
    risk_tier = _normalize_risk_tier(payload.get("risk_tier") or payload.get("risk") or payload.get("risk_level"))
    score = payload.get("score")

    clean_statuses = {"verified", "approved", "success", "passed", "clear", "ok", "valid"}
    review_statuses = {"review", "review_required", "manual_review", "pending_review"}
    reject_statuses = {"rejected", "failed", "denied", "blocked", "declined"}

    verified = False
    review_required = False
    if raw_status in clean_statuses:
        verified = True
    elif raw_status in review_statuses:
        review_required = True
    elif raw_status in reject_statuses:
        review_required = True

    if isinstance(score, (int, float)):
        if score >= 80 and raw_status not in reject_statuses:
            verified = True
        elif score < 60 and not verified:
            review_required = True

    for key in ("sanctions_hit", "pep_hit", "adverse_media_hit", "high_risk", "match_found", "bank_account_mismatch"):
        if bool(payload.get(key)):
            review_required = True
            verified = False

    reason = (
        payload.get("message")
        or payload.get("detail")
        or payload.get("reason")
        or raw_status
        or "provider_response_received"
    )

    if verified:
        outcome = "verified"
    elif review_required:
        outcome = "review_required"
    else:
        outcome = "unknown"

    return {
        "provider": provider,
        "outcome": outcome,
        "verified": verified,
        "risk_tier": risk_tier,
        "reason": str(reason),
        "raw": payload,
    }


def verify_school_profile(school, verification) -> Dict[str, Any]:
    """Run the configured provider against the school's KYB payload.

    Returns a conservative normalized response with keys:
    - outcome: verified | review_required | unknown | unavailable | error
    - verified: bool
    - risk_tier: low | medium | high | critical
    - reason: text
    - raw: provider payload (when available)
    """

    config = _build_config()
    if not config:
        return {
            "provider": None,
            "outcome": "unavailable",
            "verified": False,
            "risk_tier": "medium",
            "reason": "kyb_provider_not_configured",
            "raw": {},
        }

    payload = {
        "school_id": getattr(school, "id", None),
        "school_name": getattr(school, "name", None),
        "legal_name": getattr(verification, "legal_name", None),
        "organization_id": getattr(verification, "organization_id", None),
        "registration_number": getattr(verification, "registration_number", None),
        "tax_id": getattr(verification, "tax_id", None),
        "license_number": getattr(verification, "license_number", None),
        "bank_account_name": getattr(verification, "bank_account_name", None),
        "bank_name": getattr(verification, "bank_name", None),
        "owner_information": getattr(verification, "owner_information", {}) or {},
        "screening_results": getattr(verification, "screening_results", {}) or {},
        "documents": getattr(verification, "documents", []) or [],
    }

    url = f"{config.base_url}{config.verify_path}"
    headers = _build_headers(config)

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=config.timeout_seconds)
        if response.status_code >= 400:
            logger.warning("KYB provider %s returned HTTP %s", config.provider, response.status_code)
            return {
                "provider": config.provider,
                "outcome": "error",
                "verified": False,
                "risk_tier": "medium",
                "reason": f"provider_http_{response.status_code}",
                "raw": {},
            }

        body = response.json()
        if not isinstance(body, dict):
            body = {"result": body}
        normalized = _normalize_response(body, config.provider)
        normalized["raw"] = body
        return normalized
    except Exception as exc:
        logger.warning("KYB provider %s request failed: %s", config.provider, exc)
        return {
            "provider": config.provider,
            "outcome": "error",
            "verified": False,
            "risk_tier": "medium",
            "reason": "provider_request_failed",
            "raw": {},
        }

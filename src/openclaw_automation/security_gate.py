from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Mapping


def _env_truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_user_id(raw: str) -> str:
    value = (raw or "").strip().lower()
    if "@" in value:
        return value
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if value.startswith("+") and digits:
        return f"+{digits}"
    return value


def _normalize_binding(raw: str) -> str:
    return (raw or "").strip().lower()


def _normalize_base32_secret(secret: str) -> str:
    token = "".join(ch for ch in secret.strip().upper() if ch.isalnum())
    padding = "=" * ((8 - (len(token) % 8)) % 8)
    return token + padding


def generate_totp_code(secret: str, for_unix_ts: int, period_seconds: int = 30, digits: int = 6) -> str:
    counter = int(for_unix_ts // period_seconds)
    key = base64.b32decode(_normalize_base32_secret(secret), casefold=True)
    msg = counter.to_bytes(8, "big")
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = (
        ((digest[offset] & 0x7F) << 24)
        | ((digest[offset + 1] & 0xFF) << 16)
        | ((digest[offset + 2] & 0xFF) << 8)
        | (digest[offset + 3] & 0xFF)
    )
    code = code_int % (10**digits)
    return str(code).zfill(digits)


def verify_totp_code(
    *,
    secret: str,
    code: str,
    now_ts: int | None = None,
    period_seconds: int = 30,
    digits: int = 6,
    allowed_drift_steps: int = 1,
) -> bool:
    if not code or not secret:
        return False
    normalized = "".join(ch for ch in code if ch.isdigit())
    if len(normalized) != digits:
        return False
    now = int(now_ts if now_ts is not None else time.time())
    for drift in range(-allowed_drift_steps, allowed_drift_steps + 1):
        candidate = generate_totp_code(
            secret=secret,
            for_unix_ts=now + (drift * period_seconds),
            period_seconds=period_seconds,
            digits=digits,
        )
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sign_assertion_payload(payload: Mapping[str, Any], signing_key: str) -> str:
    body = _canonical_payload(payload).encode("utf-8")
    signature = hmac.new(signing_key.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return signature


def create_signed_assertion(
    *,
    user_id: str,
    signing_key: str,
    verified_at: int | None = None,
    expires_at: int | None = None,
    ttl_seconds: int = 7 * 24 * 60 * 60,
    verification_method: str = "totp",
    session_binding: str = "",
) -> Dict[str, Any]:
    now = int(time.time()) if verified_at is None else int(verified_at)
    expiry = int(expires_at) if expires_at is not None else int(now + ttl_seconds)
    payload: Dict[str, Any] = {
        "user_id": _normalize_user_id(user_id),
        "verified_at": now,
        "expires_at": expiry,
        "verification_method": verification_method,
        "nonce": secrets.token_hex(12),
    }
    if session_binding:
        payload["session_binding"] = _normalize_binding(session_binding)
    payload["signature"] = sign_assertion_payload(payload, signing_key)
    return payload


@dataclass
class SecurityGateDecision:
    enabled: bool
    risky: bool
    allowed: bool
    reason: str = ""
    required: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "risky": self.risky,
            "allowed": self.allowed,
            "required": self.required,
            "reason": self.reason,
        }


def _is_risky_run(manifest: Mapping[str, Any], inputs: Mapping[str, Any]) -> bool:
    if _env_truthy("OPENCLAW_SECURITY_REQUIRE_FOR_ALL_RUNS", default=False):
        return True
    if isinstance(inputs.get("credential_refs"), dict) and bool(inputs.get("credential_refs")):
        return True

    steps = manifest.get("requires_human_steps")
    if isinstance(steps, list):
        for step in steps:
            lowered = str(step).lower()
            if any(token in lowered for token in ("2fa", "mfa", "otp", "captcha", "login")):
                return True

    security_block = manifest.get("security")
    if isinstance(security_block, dict):
        if bool(security_block.get("requires_recent_verification")):
            return True
        if bool(security_block.get("state_changing")):
            return True
        if str(security_block.get("risk_level", "")).lower() in {"high", "critical"}:
            return True

    return False


def evaluate_security_gate(
    *,
    manifest: Mapping[str, Any],
    inputs: Mapping[str, Any],
    now_ts: int | None = None,
) -> SecurityGateDecision:
    enabled = _env_truthy("OPENCLAW_SECURITY_GATE_ENABLED", default=False)
    risky = _is_risky_run(manifest, inputs)
    if not enabled:
        return SecurityGateDecision(enabled=False, risky=risky, allowed=True, required=False)
    if not risky:
        return SecurityGateDecision(enabled=True, risky=False, allowed=True, required=False)

    assertion = inputs.get("security_assertion")
    if not isinstance(assertion, dict):
        contact = os.getenv("OPENCLAW_SECURITY_CONFIRM_IMESSAGE", "").strip()
        hint = " Provide a fresh verified security_assertion before running risky automations."
        if contact:
            hint += f" If in doubt, request confirmation via iMessage ({contact})."
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason="Security gate blocked run: missing security_assertion." + hint,
        )

    signing_key = os.getenv("OPENCLAW_SECURITY_SIGNING_KEY", "").strip()
    if not signing_key:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason=(
                "Security gate blocked run: OPENCLAW_SECURITY_SIGNING_KEY is not configured."
            ),
        )

    signed_payload = {k: v for k, v in assertion.items() if k != "signature"}
    expected_sig = sign_assertion_payload(signed_payload, signing_key)
    provided_sig = str(assertion.get("signature", ""))
    if not hmac.compare_digest(expected_sig, provided_sig):
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason="Security gate blocked run: invalid security_assertion signature.",
        )

    now = int(now_ts if now_ts is not None else time.time())
    verified_at = int(assertion.get("verified_at", 0))
    expires_at = int(assertion.get("expires_at", 0))
    if verified_at <= 0 or expires_at <= 0:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason="Security gate blocked run: malformed assertion timestamps.",
        )
    if now > expires_at:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason="Security gate blocked run: verification assertion expired.",
        )

    max_age = int(os.getenv("OPENCLAW_SECURITY_MAX_AGE_SECONDS", str(7 * 24 * 60 * 60)))
    if now - verified_at > max_age:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason=(
                "Security gate blocked run: verification is older than allowed window "
                f"({max_age}s)."
            ),
        )

    expected_user = _normalize_user_id(os.getenv("OPENCLAW_SECURITY_EXPECTED_USER_ID", ""))
    assertion_user = _normalize_user_id(str(assertion.get("user_id", "")))
    if expected_user and assertion_user != expected_user:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason=(
                "Security gate blocked run: assertion user does not match expected user "
                f"({expected_user})."
            ),
        )

    required_method = os.getenv("OPENCLAW_SECURITY_REQUIRED_METHOD", "totp").strip().lower()
    method = str(assertion.get("verification_method", "")).strip().lower()
    if required_method and method != required_method:
        return SecurityGateDecision(
            enabled=True,
            risky=True,
            allowed=False,
            required=True,
            reason=(
                "Security gate blocked run: verification method mismatch "
                f"(required={required_method}, got={method})."
            ),
        )

    expected_binding = _normalize_binding(os.getenv("OPENCLAW_SECURITY_EXPECTED_SESSION_BINDING", ""))
    if expected_binding:
        actual_binding = _normalize_binding(str(assertion.get("session_binding", "")))
        if actual_binding != expected_binding:
            return SecurityGateDecision(
                enabled=True,
                risky=True,
                allowed=False,
                required=True,
                reason=(
                    "Security gate blocked run: session binding mismatch "
                    f"(required={expected_binding}, got={actual_binding or 'missing'})."
                ),
            )

    return SecurityGateDecision(enabled=True, risky=True, allowed=True, required=True)

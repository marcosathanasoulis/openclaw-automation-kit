from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class CredentialResolution:
    resolved: Dict[str, str]
    unresolved: Dict[str, str]


def _env_name_from_ref(ref: str) -> str:
    sanitized = ref.upper().replace("/", "_").replace("-", "_").replace(".", "_")
    return f"OPENCLAW_SECRET_{sanitized}"


def _get_from_env(ref: str) -> str | None:
    return os.getenv(_env_name_from_ref(ref))


def _get_from_keychain(ref: str) -> str | None:
    if sys.platform != "darwin":
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.getenv("USER", ""), "-s", ref, "-w"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        return value or None
    except Exception:
        return None


def resolve_credential_refs(credential_refs: Dict[str, str]) -> CredentialResolution:
    resolved: Dict[str, str] = {}
    unresolved: Dict[str, str] = {}

    for logical_name, ref in credential_refs.items():
        value = _get_from_env(ref)
        if value is None:
            value = _get_from_keychain(ref)
        if value is None:
            unresolved[logical_name] = ref
            continue
        resolved[logical_name] = value

    return CredentialResolution(resolved=resolved, unresolved=unresolved)


def redacted_keys(credential_refs: Dict[str, str]) -> Dict[str, str]:
    # Keep refs visible but never reveal values in logs/responses.
    return {k: v for k, v in credential_refs.items()}

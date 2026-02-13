from __future__ import annotations

from typing import Any, Dict, List


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    errors: List[str] = []
    unresolved = context.get("unresolved_credential_refs", {})

    if unresolved:
        errors.append("Credential refs unresolved")

    # Demo event showing the exact handoff shape expected by messaging connectors.
    events.append(
        {
            "event": "SECOND_FACTOR_REQUIRED",
            "run_id": "demo-run-github",
            "step_id": "otp_1",
            "script_id": context["script_id"],
            "instructions": "Enter the 6-digit GitHub verification code",
            "resume_token": "demo-short-lived-token",
            "messaging_target": inputs.get("messaging_target", {}),
        }
    )

    return {
        "status": "needs_human_input",
        "summary": "GitHub login reached 2FA checkpoint. Send challenge via connector and resume run after user reply.",
        "events": events,
        "errors": errors,
    }


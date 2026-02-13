"""Skill-level runner: parses NL query and delegates to the appropriate airline runner."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Ensure the repo root is importable so engine + library runners resolve.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from openclaw_automation.engine import AutomationEngine
from openclaw_automation.nl import parse_query_to_run, resolve_script_dir


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    query = str(inputs.get("query", ""))
    if not query:
        return {"ok": False, "error": "missing 'query' in inputs"}

    parsed = parse_query_to_run(query)
    engine = AutomationEngine(_REPO_ROOT)
    script_dir = resolve_script_dir(_REPO_ROOT, parsed.script_dir)

    # Merge credential_refs from skill-level inputs into parsed inputs
    cred_refs = inputs.get("credential_refs")
    if isinstance(cred_refs, dict) and cred_refs:
        parsed.inputs["credential_refs"] = cred_refs

    result = engine.run(script_dir, parsed.inputs)
    result["parsed_notes"] = parsed.notes
    return result

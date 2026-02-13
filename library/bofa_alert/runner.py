from __future__ import annotations

import sys
from typing import Any, Dict


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    print(
        "WARNING: BrowserAgent not enabled. Results are placeholder data.",
        file=sys.stderr,
    )
    return {
        "mode": "placeholder",
        "real_data": False,
        "summary": f"PLACEHOLDER: Starter runner for {context['script_id']} received query: {inputs.get('query', '')}",
        "observations": ["Replace with OpenClaw automation flow"],
        "errors": [],
    }

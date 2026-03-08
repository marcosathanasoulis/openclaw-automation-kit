from __future__ import annotations

import importlib.util
import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any, Dict

from .contract import validate_inputs, validate_manifest, validate_output
from .credentials import redacted_keys, resolve_credential_refs

_BROWSER_AGENT_FAILURE_STATUSES = {"error", "stuck", "max_steps", "interrupted"}


def _browser_agent_failure_details(result: Dict[str, Any]) -> Dict[str, Any]:
    observations = result.get("raw_observations") or []
    status = ""
    detail = ""
    for item in observations:
        if not isinstance(item, str):
            continue
        lower = item.lower()
        if lower.startswith("browseragent status:"):
            status = item.split(":", 1)[1].strip().lower()
        if lower.startswith("browseragent adapter error:"):
            detail = item.split(":", 1)[1].strip()
            if not status and "browseragent status:" in lower:
                status = lower.split("browseragent status:", 1)[1].split(";", 1)[0].strip()
    if status in _BROWSER_AGENT_FAILURE_STATUSES:
        return {"status": status, "detail": detail}
    return {}


def _normalize_browser_agent_result(result: Dict[str, Any]) -> tuple[Dict[str, Any], list[str]]:
    details = _browser_agent_failure_details(result)
    if not details:
        return result, []

    normalized = dict(result)
    normalized["real_data"] = False
    normalized["matches"] = []
    summary = str(normalized.get("summary", "")).strip()
    prefix = "UNRELIABLE LIVE RUN"
    if summary:
        normalized["summary"] = summary if summary.startswith(prefix) else f"{prefix}: {summary}"
    else:
        normalized["summary"] = f"{prefix}: BrowserAgent ended with status {details['status']}."

    warnings = [f"BrowserAgent ended with status '{details['status']}'. Live availability was not confirmed."]
    if details["detail"]:
        warnings.append(details["detail"])
    return normalized, warnings


class AutomationEngine:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.manifest_schema = root_dir / "schemas" / "manifest.schema.json"

    def _load_runner_module(self, runner_path: Path):
        spec = importlib.util.spec_from_file_location("automation_runner", runner_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"failed loading runner: {runner_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def validate_script(self, script_dir: Path) -> Dict[str, Any]:
        manifest = validate_manifest(script_dir, self.manifest_schema)

        input_schema_path = script_dir / manifest["inputs_schema"]
        output_schema_path = script_dir / manifest["outputs_schema"]
        runner_path = script_dir / manifest["entrypoint"]

        for path in (input_schema_path, output_schema_path, runner_path):
            if not path.exists():
                raise FileNotFoundError(f"required file missing: {path}")

        return manifest

    def run(self, script_dir: Path, inputs: Dict[str, Any]) -> Dict[str, Any]:
        manifest = self.validate_script(script_dir)
        input_schema_path = script_dir / manifest["inputs_schema"]
        output_schema_path = script_dir / manifest["outputs_schema"]
        validate_inputs(inputs, input_schema_path)

        runner_path = script_dir / manifest["entrypoint"]
        module = self._load_runner_module(runner_path)
        if not hasattr(module, "run"):
            raise AttributeError(f"runner has no run(context, inputs): {runner_path}")

        credential_refs = inputs.get("credential_refs") if isinstance(inputs.get("credential_refs"), dict) else {}
        resolution = resolve_credential_refs(credential_refs)

        context = {
            "script_id": manifest["id"],
            "script_version": manifest["version"],
            "script_dir": str(script_dir),
            "credentials": resolution.resolved,
            "unresolved_credential_refs": resolution.unresolved,
        }

        timeout_seconds = int(os.getenv("OPENCLAW_RUNNER_TIMEOUT_SECONDS", "600"))
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(module.run, context, inputs)
                result = future.result(timeout=timeout_seconds)
        except FutureTimeoutError:
            return {
                "ok": False,
                "script_id": manifest["id"],
                "script_version": manifest["version"],
                "error": f"Runner exceeded timeout ({timeout_seconds}s)",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "script_id": manifest["id"],
                "script_version": manifest["version"],
                "error": str(exc),
            }

        if not isinstance(result, dict):
            return {
                "ok": False,
                "script_id": manifest["id"],
                "script_version": manifest["version"],
                "error": f"runner result must be a dict, got {type(result).__name__}",
            }

        try:
            validate_output(result, output_schema_path)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "script_id": manifest["id"],
                "script_version": manifest["version"],
                "error": f"output schema validation failed: {exc}",
            }

        normalized_result, normalization_warnings = _normalize_browser_agent_result(result)
        mode = str(normalized_result.get("mode", "live"))
        real_data = bool(normalized_result.get("real_data", mode != "placeholder"))

        envelope = {
            "ok": True,
            "script_id": manifest["id"],
            "script_version": manifest["version"],
            "mode": mode,
            "real_data": real_data,
            "placeholder": mode == "placeholder",
            "inputs": inputs,
            "credential_status": {
                "requested_refs": redacted_keys(credential_refs),
                "resolved_keys": sorted(resolution.resolved.keys()),
                "unresolved_refs": resolution.unresolved,
            },
            "warnings": (
                ["Runner returned placeholder data; BrowserAgent/live integration is not active."]
                if mode == "placeholder"
                else []
            ) + normalization_warnings,
            "result": normalized_result,
        }
        return envelope


def pretty_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)

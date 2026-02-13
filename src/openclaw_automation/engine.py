from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

from .contract import validate_inputs, validate_manifest


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
        validate_inputs(inputs, input_schema_path)

        runner_path = script_dir / manifest["entrypoint"]
        module = self._load_runner_module(runner_path)

        if not hasattr(module, "run"):
            raise AttributeError(f"runner has no run(context, inputs): {runner_path}")

        context = {
            "script_id": manifest["id"],
            "script_version": manifest["version"],
            "script_dir": str(script_dir),
        }

        result = module.run(context, inputs)
        if not isinstance(result, dict):
            raise TypeError("runner result must be a dict")

        return {
            "ok": True,
            "script_id": manifest["id"],
            "script_version": manifest["version"],
            "inputs": inputs,
            "result": result,
        }


def pretty_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)

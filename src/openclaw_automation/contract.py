from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import jsonschema


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_manifest(script_dir: Path, manifest_schema_path: Path) -> Dict[str, Any]:
    manifest_path = script_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    manifest = _load_json(manifest_path)
    schema = _load_json(manifest_schema_path)
    jsonschema.validate(manifest, schema)
    return manifest


def validate_inputs(inputs: Dict[str, Any], inputs_schema_path: Path) -> None:
    schema = _load_json(inputs_schema_path)
    jsonschema.validate(inputs, schema)


def validate_output(result: Dict[str, Any], output_schema_path: Path) -> None:
    schema = _load_json(output_schema_path)
    jsonschema.validate(result, schema)

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openclaw_automation.engine import AutomationEngine

README_STATUS_START = "<!-- AUTOMATION_STATUS:START -->"
README_STATUS_END = "<!-- AUTOMATION_STATUS:END -->"


@dataclass
class AutomationResult:
    script_id: str
    location: str
    validate_ok: bool
    smoke_ok: bool
    status: str
    notes: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect daily automation health status")
    parser.add_argument("--repo-root", default=".", help="Repo root path")
    parser.add_argument(
        "--smoke-inputs",
        default="status/smoke_inputs.json",
        help="JSON file mapping script_id -> input payload",
    )
    parser.add_argument(
        "--output",
        default="status/automation_status.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "--write-readme",
        action="store_true",
        help="Also update README status section",
    )
    return parser.parse_args()


def _discover_automation_dirs(root: Path) -> list[Path]:
    dirs: list[Path] = []
    for top in ["library", "examples"]:
        base = root / top
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "manifest.json").exists():
                dirs.append(child)
    return dirs


def _load_smoke_inputs(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            out[key] = value
    return out


def _status_emoji(status: str) -> str:
    if status == "PASS":
        return "✅"
    if status == "FAIL":
        return "❌"
    return "⚪"


def _build_markdown_table(results: list[AutomationResult], generated_at: str) -> str:
    lines = [
        README_STATUS_START,
        "## Daily Automation Health",
        "",
        f"_Last generated (UTC): {generated_at}_",
        "",
        "| Automation | Location | Validate | Smoke | Status | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| `{r.script_id}` | `{r.location}` | "
            f"{'pass' if r.validate_ok else 'fail'} | "
            f"{'pass' if r.smoke_ok else 'fail'} | "
            f"{_status_emoji(r.status)} {r.status.lower()} | {r.notes} |"
        )
    lines.extend(["", README_STATUS_END])
    return "\n".join(lines)


def _update_readme(root: Path, table: str) -> None:
    readme = root / "README.md"
    text = readme.read_text()
    if README_STATUS_START in text and README_STATUS_END in text:
        start_idx = text.index(README_STATUS_START)
        end_idx = text.index(README_STATUS_END) + len(README_STATUS_END)
        new_text = text[:start_idx] + table + text[end_idx:]
    else:
        new_text = text.rstrip() + "\n\n" + table + "\n"
    readme.write_text(new_text)


def main() -> int:
    args = _parse_args()
    root = Path(args.repo_root).resolve()
    engine = AutomationEngine(root)
    smoke_inputs = _load_smoke_inputs((root / args.smoke_inputs).resolve())
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    results: list[AutomationResult] = []
    for script_dir in _discover_automation_dirs(root):
        location = str(script_dir.relative_to(root))
        try:
            manifest = engine.validate_script(script_dir)
            script_id = str(manifest.get("id", location))
            validate_ok = True
        except Exception as exc:  # noqa: BLE001
            results.append(
                AutomationResult(
                    script_id=location,
                    location=location,
                    validate_ok=False,
                    smoke_ok=False,
                    status="FAIL",
                    notes=f"validate error: {type(exc).__name__}",
                )
            )
            continue

        smoke_payload = smoke_inputs.get(script_id)
        if smoke_payload is None:
            results.append(
                AutomationResult(
                    script_id=script_id,
                    location=location,
                    validate_ok=True,
                    smoke_ok=False,
                    status="SKIP",
                    notes="no smoke input configured",
                )
            )
            continue

        try:
            run_result = engine.run(script_dir, smoke_payload)
            smoke_ok = bool(run_result.get("ok"))
            errors = run_result.get("result", {}).get("errors", [])
            if smoke_ok and not errors:
                status = "PASS"
                notes = "ok"
            elif smoke_ok and errors:
                status = "FAIL"
                notes = f"errors: {len(errors)}"
            else:
                status = "FAIL"
                notes = "run failed"
            results.append(
                AutomationResult(
                    script_id=script_id,
                    location=location,
                    validate_ok=True,
                    smoke_ok=smoke_ok,
                    status=status,
                    notes=notes,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                AutomationResult(
                    script_id=script_id,
                    location=location,
                    validate_ok=True,
                    smoke_ok=False,
                    status="FAIL",
                    notes=f"smoke exception: {type(exc).__name__}",
                )
            )

    data = {
        "generated_at_utc": generated_at,
        "total": len(results),
        "pass": sum(1 for r in results if r.status == "PASS"),
        "fail": sum(1 for r in results if r.status == "FAIL"),
        "skip": sum(1 for r in results if r.status == "SKIP"),
        "results": [r.__dict__ for r in results],
    }

    output_path = (root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2) + "\n")

    if args.write_readme:
        table = _build_markdown_table(results, generated_at)
        _update_readme(root, table)

    print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

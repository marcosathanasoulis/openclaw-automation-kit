from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .engine import AutomationEngine, pretty_json
from .nl import parse_query_to_run, resolve_script_dir
from .security_gate import create_signed_assertion, verify_totp_code


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw automation toolkit CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a script automation spec")
    p_validate.add_argument("--script-dir", required=True)

    p_run = sub.add_parser("run", help="Validate and run a script")
    p_run.add_argument("--script-dir", required=True)
    p_run.add_argument("--input", required=True, help="JSON object string")

    p_query = sub.add_parser("run-query", help="Run from a plain-English query")
    p_query.add_argument("--query", required=True)
    cred_group = p_query.add_mutually_exclusive_group()
    cred_group.add_argument(
        "--credential-refs",
        default="{}",
        help="Optional JSON object of credential refs to merge into inputs",
    )
    cred_group.add_argument(
        "--credential-refs-file",
        help="Path to JSON file containing credential refs (safer than inline CLI JSON)",
    )
    cred_group.add_argument(
        "--credential-refs-env",
        help="Environment variable name holding JSON credential refs",
    )
    cred_group.add_argument(
        "--credential-refs-stdin",
        action="store_true",
        help="Read JSON credential refs from stdin",
    )
    sec_group = p_query.add_mutually_exclusive_group()
    sec_group.add_argument(
        "--security-assertion",
        default="{}",
        help="Optional JSON object proving recent verified user identity for risky runs",
    )
    sec_group.add_argument(
        "--security-assertion-file",
        help="Path to JSON security assertion (safer than inline JSON)",
    )
    sec_group.add_argument(
        "--security-assertion-env",
        help="Environment variable name holding JSON security assertion",
    )
    sec_group.add_argument(
        "--security-assertion-stdin",
        action="store_true",
        help="Read JSON security assertion from stdin",
    )

    p_doctor = sub.add_parser("doctor", help="Run local environment preflight checks")
    p_doctor.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output",
    )

    p_issue = sub.add_parser(
        "issue-security-assertion",
        help="Verify TOTP and issue a signed assertion for risky runs",
    )
    p_issue.add_argument("--user-id", required=True, help="Expected user identity (email or phone)")
    p_issue.add_argument("--totp-code", required=True, help="Current TOTP code")
    p_issue.add_argument(
        "--totp-secret-env",
        default="OPENCLAW_TOTP_SECRET",
        help="Environment variable holding the base32 TOTP secret",
    )
    p_issue.add_argument(
        "--signing-key-env",
        default="OPENCLAW_SECURITY_SIGNING_KEY",
        help="Environment variable holding assertion signing key",
    )
    p_issue.add_argument(
        "--ttl-seconds",
        type=int,
        default=7 * 24 * 60 * 60,
        help="Assertion validity window in seconds (default: 7 days)",
    )
    p_issue.add_argument(
        "--period-seconds",
        type=int,
        default=30,
        help="TOTP period in seconds",
    )
    p_issue.add_argument(
        "--drift-steps",
        type=int,
        default=1,
        help="Allowed TOTP time drift in step units",
    )
    p_issue.add_argument(
        "--digits",
        type=int,
        default=6,
        help="TOTP digits",
    )
    p_issue.add_argument(
        "--session-binding",
        default="",
        help="Optional session/device binding string to embed in assertion",
    )
    p_issue.add_argument(
        "--session-binding-env",
        default="",
        help="Environment variable name containing session binding string",
    )

    return parser.parse_args()


def _load_input(raw: str) -> Dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--input must be a JSON object")
    return data


def _load_credential_refs(args: argparse.Namespace) -> Dict[str, Any]:
    if getattr(args, "credential_refs_stdin", False):
        raw = sys.stdin.read().strip() or "{}"
        return _load_input(raw)
    if getattr(args, "credential_refs_file", None):
        raw = Path(args.credential_refs_file).read_text()
        return _load_input(raw)
    if getattr(args, "credential_refs_env", None):
        key = args.credential_refs_env
        raw = os.getenv(key, "{}")
        return _load_input(raw)
    return _load_input(getattr(args, "credential_refs", "{}"))


def _load_security_assertion(args: argparse.Namespace) -> Dict[str, Any]:
    if getattr(args, "security_assertion_stdin", False):
        raw = sys.stdin.read().strip() or "{}"
        return _load_input(raw)
    if getattr(args, "security_assertion_file", None):
        raw = Path(args.security_assertion_file).read_text()
        return _load_input(raw)
    if getattr(args, "security_assertion_env", None):
        key = args.security_assertion_env
        raw = os.getenv(key, "{}")
        return _load_input(raw)
    return _load_input(getattr(args, "security_assertion", "{}"))


def _doctor(root: Path) -> Dict[str, Any]:
    checks: Dict[str, Dict[str, Any]] = {}
    schema = root / "schemas" / "manifest.schema.json"
    checks["repo_schema"] = {
        "ok": schema.exists(),
        "details": str(schema),
    }
    checks["anthropic_api_key"] = {
        "ok": bool(os.getenv("ANTHROPIC_API_KEY")),
        "details": "Set for BrowserAgent/vision flows",
    }
    checks["bluebubbles_webhook"] = {
        "ok": bool(os.getenv("BLUEBUBBLES_WEBHOOK_URL")),
        "details": "Optional for iMessage notifications",
    }
    checks["openclaw_root_env"] = {
        "ok": bool(os.getenv("OPENCLAW_AUTOMATION_ROOT")),
        "details": os.getenv("OPENCLAW_AUTOMATION_ROOT", ""),
    }

    overall_ok = all(item["ok"] for key, item in checks.items() if key == "repo_schema")
    return {"ok": overall_ok, "root": str(root), "checks": checks}


def _detect_repo_root(script_dir: Path) -> Path:
    candidates = [Path.cwd(), script_dir.resolve(), *script_dir.resolve().parents]
    for candidate in candidates:
        schema = candidate / "schemas" / "manifest.schema.json"
        if schema.exists():
            return candidate
    raise FileNotFoundError("Could not locate repository root with schemas/manifest.schema.json")


def main() -> None:
    args = _parse_args()
    if args.command in {"validate", "run"}:
        script_dir = Path(args.script_dir).resolve()
        root = _detect_repo_root(script_dir)
    else:
        root = _detect_repo_root(Path.cwd())
    engine = AutomationEngine(root)

    if args.command == "validate":
        manifest = engine.validate_script(script_dir)
        print(pretty_json({"ok": True, "manifest": manifest}))
        return

    if args.command == "run":
        inputs = _load_input(args.input)
        result = engine.run(script_dir, inputs)
        if result.get("mode") == "placeholder":
            print(
                "WARNING: BrowserAgent not enabled. Results are placeholder data.",
                file=sys.stderr,
            )
        print(pretty_json(result))
        return

    if args.command == "run-query":
        parsed = parse_query_to_run(args.query)
        target_script_dir = resolve_script_dir(root, parsed.script_dir)
        credential_refs = _load_credential_refs(args)
        if credential_refs:
            parsed.inputs["credential_refs"] = credential_refs
        security_assertion = _load_security_assertion(args)
        if security_assertion:
            parsed.inputs["security_assertion"] = security_assertion
        result = engine.run(target_script_dir, parsed.inputs)
        if result.get("mode") == "placeholder":
            print(
                "WARNING: BrowserAgent not enabled. Results are placeholder data.",
                file=sys.stderr,
            )
        print(pretty_json({"parsed_notes": parsed.notes, **result}))
        return

    if args.command == "issue-security-assertion":
        secret = os.getenv(args.totp_secret_env, "").strip()
        if not secret:
            print(
                pretty_json(
                    {
                        "ok": False,
                        "error": f"Missing TOTP secret in env var: {args.totp_secret_env}",
                    }
                )
            )
            raise SystemExit(2)
        signing_key = os.getenv(args.signing_key_env, "").strip()
        if not signing_key:
            print(
                pretty_json(
                    {
                        "ok": False,
                        "error": f"Missing signing key in env var: {args.signing_key_env}",
                    }
                )
            )
            raise SystemExit(2)

        valid = verify_totp_code(
            secret=secret,
            code=args.totp_code,
            period_seconds=args.period_seconds,
            digits=args.digits,
            allowed_drift_steps=args.drift_steps,
        )
        if not valid:
            print(pretty_json({"ok": False, "error": "Invalid TOTP code"}))
            raise SystemExit(1)

        assertion = create_signed_assertion(
            user_id=args.user_id,
            signing_key=signing_key,
            ttl_seconds=args.ttl_seconds,
            verification_method="totp",
            session_binding=(
                os.getenv(args.session_binding_env, "").strip()
                if args.session_binding_env
                else args.session_binding
            ),
        )
        print(pretty_json({"ok": True, "security_assertion": assertion}))
        return

    if args.command == "doctor":
        result = _doctor(root)
        if args.json:
            print(pretty_json(result))
            return
        print(pretty_json(result))
        return


if __name__ == "__main__":
    main()

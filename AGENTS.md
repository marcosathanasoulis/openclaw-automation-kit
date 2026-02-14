# AGENTS.md

Operational rules for human + AI multi-agent collaboration in this repository.

## Branching (required)

- Never work directly on `main`.
- Every change must start from a new branch.
- Branch names:
  - `codex/<topic>` for Codex
  - `claude/<topic>` for Claude
  - `gemini/<topic>` for Gemini
  - human developers may use any clear prefix.

## Coordination files

- `INPROCESS.md`: short-lived operational status (locks, active runs, who is doing what now).
- `HANDOFF.md`: durable cross-agent context and decisions.

Before starting work:
1. `git checkout main && git pull --ff-only`
2. Create a new branch.
3. Read `INPROCESS.md` and `HANDOFF.md`.

During work:
- Update `INPROCESS.md` when taking/releasing shared resources.
- Add durable findings to `HANDOFF.md`.
- Commit and push frequently so other agents can pull.

## Shared resource locking

- Browser/CDP resources must not be used concurrently on the same endpoint.
- Respect `/tmp/browser_cdp.lock` and existing lock conventions.
- If lock is busy, work on non-lock tasks (tests/docs/parsers) until free.

## Code quality gates (before opening/updating PR)

Run locally:

```bash
ruff check .
pytest -q
./scripts/e2e_no_login_smoke.sh
```

## Security and data handling

- Never commit secrets, tokens, personal phone numbers, or real credentials.
- Use `credential_refs` only.
- Keep public demos sandboxed.
- No anti-bot bypass techniques.

## PR and merge flow

- Open PR from your branch to `main`.
- Resolve conflicts locally (do not overwrite other agents' work blindly).
- Merge only after required checks pass.

## Automation contribution policy

- New automations start in `examples/`.
- Promote to `library/` only after passing `docs/AUTOMATION_PROMOTION.md`.
- Include test evidence in PR.

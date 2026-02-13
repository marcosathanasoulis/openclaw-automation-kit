# GEMINI.md

Guidance for Gemini (or any additional agent) working in this repo.

## Coordination requirements
1. Read `INPROCESS.md` (if present) before changes.
2. Claim lock for shared resources before service/process restarts.
3. Do not modify secrets handling to store raw credentials in git or plaintext files.

## Safety boundaries
- No anti-bot bypass techniques.
- Keep MFA/human checkpoints intact.
- Prefer additive changes with tests.

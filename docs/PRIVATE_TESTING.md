# Private Testing With Real Accounts

Use a separate private repo/workspace for end-to-end tests that require your real:
- phone numbers
- account usernames/passwords
- 2FA channels
- personal destinations and travel windows

Do **not** put any of that data in this public repository.

## Recommended setup

1. Keep this public repo as framework + placeholders only.
2. Create a private companion repo for:
   - local `.env` files
   - private runner configs
   - personal smoke-test scripts
   - test fixtures containing your own account metadata
3. Store secrets in OS keychain or cloud secret manager and reference by logical key only.
4. Run integration tests from the private repo, importing this package.

## Public-safe placeholders

- Use `<your-phone-number>` in docs/examples.
- Use logical refs like `openclaw/united/password` instead of raw values.
- Keep sample webhook URLs and tokens synthetic.

## CI strategy

- Public CI: contract/schema/unit tests only (no live account access).
- Private CI (optional): credentialed smoke tests with strict secret controls.


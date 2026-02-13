# Developer Setup (Git + SSH)

Use this once on a new machine before contributing.

## 1. Create an SSH key (if you do not already have one)

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

## 2. Start ssh-agent and add your key

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

## 3. Add the public key to GitHub

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy output and add it in GitHub:
- Settings → SSH and GPG keys → New SSH key

## 4. Verify SSH access

```bash
ssh -T git@github.com
```

## 5. Clone with SSH

```bash
git clone git@github.com:marcosathanasoulis/openclaw-automation-kit.git
cd openclaw-automation-kit
```

## 6. Create local environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

## 7. Run baseline checks

```bash
ruff check .
pytest -q
```

## Notes
- If SSH is blocked in your environment, use HTTPS clone instead.
- Never commit `.env`, credentials, or tokens.

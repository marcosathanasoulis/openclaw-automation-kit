from __future__ import annotations

import base64
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import requests

TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GoogleAuthConfig:
    def __init__(self, account_email: str, token_file: Path, client_secret_file: Path) -> None:
        self.account_email = account_email
        self.token_file = token_file
        self.client_secret_file = client_secret_file


def _safe_account(account_email: str) -> str:
    return account_email.replace("@", "_at_").replace("+", "_plus_")


def _default_connector_root() -> Path:
    return Path(
        os.getenv(
            "OPENCLAW_GOOGLE_CONNECTOR_ROOT",
            "/Users/Marcos/code-projects/athanasoulis-ai-assistant",
        )
    ).expanduser()


def _resolve_auth_config(inputs: Dict[str, Any]) -> GoogleAuthConfig:
    account_email = str(
        inputs.get("account_email")
        or os.getenv("OPENCLAW_GOOGLE_ACCOUNT")
        or "marcos@athanasoulis.net"
    ).strip()

    root = _default_connector_root()
    token_dir = Path(
        os.getenv("OPENCLAW_GOOGLE_TOKEN_DIR", str(root / "credentials/google/tokens"))
    ).expanduser()
    client_secret_file = Path(
        os.getenv(
            "OPENCLAW_GOOGLE_CLIENT_SECRET_PATH",
            str(root / "credentials/google/client_secret.json"),
        )
    ).expanduser()

    token_file = Path(
        os.getenv(
            "OPENCLAW_GOOGLE_TOKEN_FILE",
            str(token_dir / f"token_{_safe_account(account_email)}.json"),
        )
    ).expanduser()

    if inputs.get("token_file"):
        token_file = Path(str(inputs["token_file"])).expanduser()
    if inputs.get("client_secret_file"):
        client_secret_file = Path(str(inputs["client_secret_file"])).expanduser()

    return GoogleAuthConfig(
        account_email=account_email,
        token_file=token_file,
        client_secret_file=client_secret_file,
    )


def _allowed_accounts() -> set[str]:
    raw = os.getenv("OPENCLAW_GOOGLE_ALLOWED_ACCOUNTS", "marcos@athanasoulis.net")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _enforce_account_allowlist(account_email: str) -> None:
    normalized = account_email.strip().lower()
    if normalized not in _allowed_accounts():
        raise PermissionError(
            "Blocked Google workspace access for non-allowlisted account: "
            f"{account_email!r}. Set OPENCLAW_GOOGLE_ALLOWED_ACCOUNTS to override."
        )


def _target_accounts(inputs: Dict[str, Any]) -> List[str]:
    explicit = str(inputs.get("account_email", "")).strip().lower()
    if explicit:
        _enforce_account_allowlist(explicit)
        return [explicit]
    allowed = sorted(_allowed_accounts())
    if not allowed:
        raise RuntimeError("OPENCLAW_GOOGLE_ALLOWED_ACCOUNTS is empty; set at least one account")
    return allowed


def _parse_rfc3339(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _refresh_access_token(token_data: Dict[str, Any], client_secret_data: Dict[str, Any]) -> Dict[str, Any]:
    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Google token file is missing refresh_token")

    client_id = token_data.get("client_id")
    client_secret = token_data.get("client_secret")

    if not client_id or not client_secret:
        client_section = client_secret_data.get("installed") or client_secret_data.get("web") or {}
        client_id = client_id or client_section.get("client_id")
        client_secret = client_secret or client_section.get("client_secret")

    if not client_id or not client_secret:
        raise RuntimeError("Google client credentials are missing (client_id/client_secret)")

    token_uri = token_data.get("token_uri") or client_secret_data.get("token_uri") or TOKEN_URI_DEFAULT
    resp = requests.post(
        token_uri,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Google token refresh failed: HTTP {resp.status_code}")

    refreshed = resp.json()
    access_token = refreshed.get("access_token")
    if not access_token:
        raise RuntimeError("Google token refresh response missing access_token")

    expires_in = int(refreshed.get("expires_in", 3600))
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 30))).isoformat()

    token_data["token"] = access_token
    token_data["expiry"] = expiry
    token_data["token_uri"] = token_uri
    token_data["client_id"] = client_id
    token_data["client_secret"] = client_secret
    return token_data


def _access_token(config: GoogleAuthConfig) -> str:
    if not config.token_file.exists():
        raise FileNotFoundError(
            f"Google token file not found: {config.token_file}. "
            "Set OPENCLAW_GOOGLE_TOKEN_FILE or OPENCLAW_GOOGLE_TOKEN_DIR."
        )

    token_data = _load_json(config.token_file)
    if not token_data.get("token"):
        raise RuntimeError("Google token file does not contain an access token")

    expiry_raw = str(token_data.get("expiry", "")).strip()
    is_expired = True
    if expiry_raw:
        try:
            expiry_dt = _parse_rfc3339(expiry_raw)
            is_expired = expiry_dt <= datetime.now(timezone.utc)
        except Exception:
            is_expired = True

    if not is_expired:
        return str(token_data["token"])

    if not config.client_secret_file.exists():
        raise FileNotFoundError(
            f"Google client secret file not found: {config.client_secret_file}. "
            "Set OPENCLAW_GOOGLE_CLIENT_SECRET_PATH or pass client_secret_file input."
        )

    secret_data = _load_json(config.client_secret_file)
    refreshed = _refresh_access_token(token_data, secret_data)
    config.token_file.write_text(json.dumps(refreshed, indent=2))
    return str(refreshed["token"])


def _bearer_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "OpenClawAutomationKit/0.1",
    }


def _list_meetings(access_token: str, target_date: date, max_results: int, calendar_id: str) -> List[Dict[str, str]]:
    time_min = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    time_max = datetime.combine(target_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

    cal_id = quote(calendar_id, safe="")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events"
    resp = requests.get(
        url,
        headers=_bearer_headers(access_token),
        params={
            "timeMin": time_min.isoformat().replace("+00:00", "Z"),
            "timeMax": time_max.isoformat().replace("+00:00", "Z"),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(max_results),
        },
        timeout=20,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Google Calendar API failed: HTTP {resp.status_code}")

    data = resp.json()
    out: List[Dict[str, str]] = []
    for item in data.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date") or ""
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date") or ""
        out.append(
            {
                "start": str(start),
                "end": str(end),
                "summary": str(item.get("summary") or "(No title)"),
                "location": str(item.get("location") or ""),
                "account_email": "",
            }
        )
    return out


def _decode_header_value(raw: str) -> str:
    # Gmail subjects can be MIME-encoded words.
    if "=?" not in raw:
        return raw
    try:
        parts: List[str] = []
        for chunk in raw.split("?="):
            if not chunk:
                continue
            segment = chunk if chunk.endswith("?=") else chunk + "?="
            if segment.startswith("=?") and "?B?" in segment.upper():
                data = segment.split("?", 4)[3]
                parts.append(base64.b64decode(data).decode("utf-8", errors="ignore"))
            else:
                parts.append(segment)
        return "".join(parts).strip()
    except Exception:
        return raw


def _list_emails(access_token: str, max_results: int, query: str) -> List[Dict[str, str]]:
    list_resp = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=_bearer_headers(access_token),
        params={"maxResults": str(max_results), "q": query},
        timeout=20,
    )
    if list_resp.status_code >= 400:
        raise RuntimeError(f"Gmail API list failed: HTTP {list_resp.status_code}")

    list_data = list_resp.json()
    out: List[Dict[str, str]] = []
    for item in list_data.get("messages", []):
        msg_id = str(item.get("id") or "")
        if not msg_id:
            continue
        msg_resp = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
            headers=_bearer_headers(access_token),
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            timeout=20,
        )
        if msg_resp.status_code >= 400:
            continue
        msg = msg_resp.json()
        headers = msg.get("payload", {}).get("headers", [])
        header_map = {str(h.get("name", "")).lower(): str(h.get("value", "")) for h in headers}
        out.append(
            {
                "id": msg_id,
                "from": header_map.get("from", ""),
                "subject": _decode_header_value(header_map.get("subject", "")),
                "date": header_map.get("date", ""),
                "snippet": str(msg.get("snippet") or ""),
                "account_email": "",
            }
        )
    return out


def _sort_meetings(meetings: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(meetings, key=lambda m: m.get("start", ""))


def _sort_emails(emails: List[Dict[str, str]]) -> List[Dict[str, str]]:
    def _key(row: Dict[str, str]) -> datetime:
        raw = row.get("date", "")
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)

    return sorted(emails, key=_key, reverse=True)


def _as_date(value: str | None) -> date:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return datetime.now().date()


def run(context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    del context
    task = str(inputs.get("task", "brief")).strip().lower()
    max_results = int(inputs.get("max_results", 10))
    calendar_id = str(inputs.get("calendar_id", os.getenv("OPENCLAW_GOOGLE_CALENDAR_ID", "primary"))).strip()
    gmail_query = str(inputs.get("gmail_query", "newer_than:7d"))
    target_date = _as_date(str(inputs.get("date", "") or ""))

    errors: List[str] = []
    meetings: List[Dict[str, str]] = []
    emails: List[Dict[str, str]] = []

    target_accounts = _target_accounts(inputs)
    account_errors: Dict[str, str] = {}

    try:
        for account_email in target_accounts:
            per_inputs = dict(inputs)
            per_inputs["account_email"] = account_email
            config = _resolve_auth_config(per_inputs)
            try:
                token = _access_token(config)
                if task in {"meetings", "brief"}:
                    per_meetings = _list_meetings(
                        token, target_date, max_results=max_results, calendar_id=calendar_id
                    )
                    for item in per_meetings:
                        item["account_email"] = account_email
                    meetings.extend(per_meetings)

                if task in {"emails", "brief"}:
                    per_emails = _list_emails(token, max_results=max_results, query=gmail_query)
                    for item in per_emails:
                        item["account_email"] = account_email
                    emails.extend(per_emails)
            except Exception as exc:  # noqa: BLE001
                account_errors[account_email] = str(exc)

    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    if account_errors:
        for account, message in account_errors.items():
            errors.append(f"{account}: {message}")

    meetings = _sort_meetings(meetings)
    emails = _sort_emails(emails)
    if task in {"emails", "brief"} and max_results > 0:
        emails = emails[:max_results]

    if errors:
        summary = "Google workspace fetch failed. See errors."
    elif task == "meetings":
        if meetings:
            summary = f"Found {len(meetings)} meeting(s) on {target_date.isoformat()} across {len(target_accounts)} account(s)."
        else:
            summary = f"No meetings found on {target_date.isoformat()} across {len(target_accounts)} account(s)."
    elif task == "emails":
        if emails and max_results == 1:
            top = emails[0]
            summary = (
                "Most recent matching email: "
                f"{top.get('date', '(unknown date)')} | "
                f"{top.get('from', '(unknown sender)')} | "
                f"{top.get('subject', '(no subject)')}"
            )
        else:
            summary = f"Found {len(emails)} recent email(s) across {len(target_accounts)} account(s)."
    else:
        summary = (
            f"Workspace brief for {target_date.isoformat()}: "
            f"{len(meetings)} meeting(s), {len(emails)} email(s) "
            f"across {len(target_accounts)} account(s)."
        )

    return {
        "task": task,
        "account_email": ",".join(target_accounts),
        "target_date": target_date.isoformat(),
        "calendar_id": calendar_id,
        "gmail_query": gmail_query,
        "meetings": meetings,
        "emails": emails,
        "summary": summary,
        "errors": errors,
    }

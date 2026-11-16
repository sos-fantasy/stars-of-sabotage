"""Pinterest posting through the Pinterest API v5.

Environment (GitHub Actions secrets and variables):
  PINTEREST_APP_ID         app ID from developers.pinterest.com > My apps
  PINTEREST_APP_SECRET     app secret (secret)
  PINTEREST_ACCESS_TOKEN   current access token (secret, rewritten on every refresh)
  PINTEREST_REFRESH_TOKEN  current refresh token (secret, rewritten on every refresh)
  SECRETS_PAT              fine-grained GitHub token, this repo only, "Secrets: read and write".
                           Needed because Pinterest replaces the refresh token on every refresh,
                           and the workflow's own GITHUB_TOKEN cannot write secrets.
  PINTEREST_BOARD_ID       board the cards go to (variable)
  PINTEREST_API            optional; defaults to https://api.pinterest.com/v5

Commands:
  auth-url             print the link the owner opens to approve the app
  connect CODE         trade the one-time code from pinterest-callback.html for tokens; saves them
  refresh              get a fresh token pair and save both (weekly, and before 30 days pass)
  check                confirm the token works; list boards with their IDs
  pin IMAGE_URL FILE   create one Pin; FILE is JSON {title, description, link, alt_text}

Token rules (Pinterest developer newsletter, Sept 2025; community reports, 2026): access tokens
last about 30 days, refresh tokens about 60, and each refresh returns a new refresh token while
the old one stops working. Losing the new one means the owner has to approve the app again.
Docs: https://developers.pinterest.com/docs/getting-started/scopes/
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("PINTEREST_API", "https://api.pinterest.com/v5").rstrip("/")
AUTH = "https://www.pinterest.com/oauth/"
REDIRECT = "https://starsofsabotage.com/pinterest-callback.html"
SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"
TITLE_MAX, DESC_MAX, ALT_MAX = 100, 500, 500


def _env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"{name} is not set. Add it under Settings > Secrets and variables > Actions.")
    return v


def _mask(value: str) -> None:
    """Hide a token in GitHub Actions logs before anything could print it."""
    if value and os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{value}")


def _request(method: str, path: str, *, token: str | None = None, form: dict | None = None,
             body: dict | None = None, basic: tuple[str, str] | None = None) -> dict:
    url = path if path.startswith("http") else f"{API}{path}"
    headers, data = {}, None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        raise SystemExit(f"Pinterest {method} {path}: HTTP {e.code} {detail}")


def _save_secret(name: str, value: str) -> None:
    env = dict(os.environ, GH_TOKEN=_env("SECRETS_PAT"))
    repo = os.environ.get("GITHUB_REPOSITORY", "sos-fantasy/stars-of-sabotage")
    r = subprocess.run(["gh", "secret", "set", name, "--repo", repo], input=value, text=True,
                       env=env, capture_output=True)
    if r.returncode:
        raise SystemExit(f"Could not save {name} to GitHub secrets: {r.stderr.strip()[:300]}")


def _store(tokens: dict) -> None:
    access, refresh = tokens.get("access_token", ""), tokens.get("refresh_token", "")
    _mask(access), _mask(refresh)
    if not access:
        raise SystemExit("Pinterest returned no access token.")
    # Save the refresh token first: it is the one that cannot be recovered.
    if refresh:
        _save_secret("PINTEREST_REFRESH_TOKEN", refresh)
    _save_secret("PINTEREST_ACCESS_TOKEN", access)
    days = lambda s: f"{int(s) / 86400:.0f} days" if s else "unknown"
    print(f"Saved. Access token good for {days(tokens.get('expires_in'))}; refresh token "
          f"{'replaced, good for ' + days(tokens.get('refresh_token_expires_in')) if refresh else 'unchanged'}. "
          f"Scopes: {tokens.get('scope', 'not listed')}.")


def auth_url() -> str:
    q = {"client_id": _env("PINTEREST_APP_ID"), "redirect_uri": REDIRECT, "response_type": "code",
         "scope": SCOPES, "state": secrets.token_urlsafe(12)}
    return AUTH + "?" + urllib.parse.urlencode(q)


def connect(code: str) -> None:
    t = _request("POST", "/oauth/token", basic=(_env("PINTEREST_APP_ID"), _env("PINTEREST_APP_SECRET")),
                 form={"grant_type": "authorization_code", "code": code.strip(), "redirect_uri": REDIRECT})
    _store(t)


def refresh() -> None:
    t = _request("POST", "/oauth/token", basic=(_env("PINTEREST_APP_ID"), _env("PINTEREST_APP_SECRET")),
                 form={"grant_type": "refresh_token", "refresh_token": _env("PINTEREST_REFRESH_TOKEN")})
    _store(t)


def check() -> None:
    tok = _env("PINTEREST_ACCESS_TOKEN")
    me = _request("GET", "/user_account", token=tok)
    print(f"OK: {me.get('username')} ({me.get('account_type')}) via {API}")
    boards = _request("GET", "/boards?page_size=50", token=tok).get("items", [])
    for b in boards:
        print(f"board {b['id']}  {b.get('privacy', '')}  {b.get('name')}")
    if not boards:
        print("No boards yet.")
    want = os.environ.get("PINTEREST_BOARD_ID", "")
    if want and want not in {b["id"] for b in boards}:
        raise SystemExit(f"PINTEREST_BOARD_ID {want} is not one of this account's boards.")


def pin_fields(meta: dict) -> dict:
    """Trim to Pinterest's limits and refuse empty fields, so a bad caption never posts."""
    out = {
        "title": meta["title"].strip()[:TITLE_MAX],
        "description": meta["description"].strip()[:DESC_MAX],
        "link": meta.get("link", "https://starsofsabotage.com/"),
        "alt_text": meta["alt_text"].strip()[:ALT_MAX],
    }
    for k, v in out.items():
        if not v:
            raise SystemExit(f"Pin {k} is empty.")
    return out


def publish_pinterest(image_url: str, meta: dict) -> dict:
    body = pin_fields(meta) | {"board_id": _env("PINTEREST_BOARD_ID"),
                               "media_source": {"source_type": "image_url", "url": image_url}}
    r = _request("POST", "/pins", token=_env("PINTEREST_ACCESS_TOKEN"), body=body)
    return {"id": r["id"], "url": f"https://www.pinterest.com/pin/{r['id']}/"}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "auth-url":
        print("Open this link while signed in to the Stars of Sabotage Pinterest account:\n" + auth_url())
    elif cmd == "connect":
        connect(args[0])
    elif cmd == "refresh":
        refresh()
    elif cmd == "check":
        check()
    elif cmd == "pin":
        meta = json.loads(open(args[1], encoding="utf-8").read())
        print(json.dumps(publish_pinterest(args[0], meta)))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

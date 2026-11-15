"""Instagram (and later Facebook Page) posting through Meta's Graph API.

Secrets come from the environment (GitHub Actions secrets and variables):
  IG_ACCESS_TOKEN  token from the app's Instagram API (Unified login) setup
  IG_USER_ID       Instagram account ID (17841480826292471 for @starsofsabotage)

Commands:
  python pipeline/social/meta.py check [IMAGE_URL]
      Confirms the token works, which Graph host accepts it, and (optionally)
      that IMAGE_URL is publicly reachable as a JPEG. Posts nothing.
  python pipeline/social/meta.py publish-instagram IMAGE_URL CAPTION_FILE
      Publishes one image post. Instagram fetches IMAGE_URL itself, so it must
      be a public JPEG (Meta content publishing docs).

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing/
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = "v24.0"
# Tokens starting "EAA" are Graph API tokens (graph.facebook.com); Instagram
# Login tokens use graph.instagram.com. `check` tries both and reports which works.
HOSTS = ["https://graph.facebook.com", "https://graph.instagram.com"]


def _call(method, url, params=None):
    data = None
    if params:
        enc = urllib.parse.urlencode(params)
        if method == "GET":
            url = f"{url}?{enc}"
        else:
            data = enc.encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"raw": body[:300].decode("utf-8", "replace")}


def _redact(obj, token):
    return json.loads(json.dumps(obj).replace(token, "[token]")) if token else obj


def _env():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    ig = os.environ.get("IG_USER_ID", "").strip()
    if not token or not ig:
        sys.exit("IG_ACCESS_TOKEN and IG_USER_ID must both be set.")
    return token, ig


def find_host(token, ig):
    for host in HOSTS:
        status, body = _call("GET", f"{host}/{GRAPH_VERSION}/{ig}",
                             {"fields": "id,username,media_count", "access_token": token})
        print(f"{host}: HTTP {status} {json.dumps(_redact(body, token))}")
        if status == 200 and body.get("id"):
            return host, body
    return None, None


def check(image_url=None):
    token, ig = _env()
    print(f"Token prefix: {token[:4]}..., length {len(token)}")
    host, account = find_host(token, ig)
    if not host:
        sys.exit("FAIL: no Graph host accepted this token for the Instagram account.")
    print(f"OK: @{account.get('username')} via {host}, {account.get('media_count')} posts so far.")

    # Expiry. debug_token accepts the token as its own access token for
    # user and system-user tokens; if Meta refuses, report and move on.
    status, body = _call("GET", f"https://graph.facebook.com/{GRAPH_VERSION}/debug_token",
                         {"input_token": token, "access_token": token})
    d = body.get("data", {}) if status == 200 else {}
    if d:
        exp = d.get("expires_at")
        print("Token type:", d.get("type"), "| valid:", d.get("is_valid"),
              "| expires:", "never" if exp in (0, None) else time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(exp)))
        print("Scopes:", ", ".join(d.get("scopes", [])))
    else:
        print(f"Could not read expiry (HTTP {status}): {json.dumps(_redact(body, token))}")

    status, body = _call("GET", f"{host}/{GRAPH_VERSION}/{ig}/content_publishing_limit",
                         {"fields": "quota_usage,config", "access_token": token})
    print(f"Publishing limit: HTTP {status} {json.dumps(_redact(body, token))}")

    if image_url:
        req = urllib.request.Request(image_url, method="HEAD")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get("Content-Type", "")
                print(f"Image: HTTP {r.status}, {ctype}")
                if "jpeg" not in ctype:
                    sys.exit("FAIL: Instagram only accepts JPEG.")
        except urllib.error.HTTPError as e:
            sys.exit(f"FAIL: image URL returned HTTP {e.code}. Is it deployed yet?")
    print("Check passed.")


def publish_instagram(image_url, caption):
    token, ig = _env()
    host, account = find_host(token, ig)
    if not host:
        sys.exit("FAIL: token not accepted; run `check` first.")
    base = f"{host}/{GRAPH_VERSION}/{ig}"
    status, body = _call("POST", f"{base}/media",
                         {"image_url": image_url, "caption": caption, "access_token": token})
    if status != 200 or "id" not in body:
        sys.exit(f"FAIL creating container: HTTP {status} {json.dumps(_redact(body, token))}")
    container = body["id"]
    print("Container:", container)

    for _ in range(20):  # Instagram fetches and processes the image first
        status, body = _call("GET", f"{host}/{GRAPH_VERSION}/{container}",
                             {"fields": "status_code,status", "access_token": token})
        code = body.get("status_code")
        print("Container status:", code)
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"FAIL: container {code}: {body.get('status')}")
        time.sleep(5)

    status, body = _call("POST", f"{base}/media_publish",
                         {"creation_id": container, "access_token": token})
    if status != 200 or "id" not in body:
        sys.exit(f"FAIL publishing: HTTP {status} {json.dumps(_redact(body, token))}")
    media = body["id"]
    status, body = _call("GET", f"{host}/{GRAPH_VERSION}/{media}",
                         {"fields": "permalink", "access_token": token})
    print("Published:", media, body.get("permalink", ""))


def check_facebook():
    """Can META_SYSTEM_TOKEN reach the Facebook Page? Posts nothing."""
    token = os.environ.get("META_SYSTEM_TOKEN", "").strip()
    page = os.environ.get("FB_PAGE_ID", "").strip()
    if not token or not page:
        sys.exit("META_SYSTEM_TOKEN and FB_PAGE_ID must both be set.")
    base = f"https://graph.facebook.com/{GRAPH_VERSION}"
    print(f"Token prefix: {token[:4]}..., length {len(token)}")
    status, body = _call("GET", f"{base}/me", {"fields": "id,name", "access_token": token})
    print(f"me: HTTP {status} {json.dumps(_redact(body, token))}")
    status, body = _call("GET", f"{base}/me/permissions", {"access_token": token})
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        print("Granted:", ", ".join(p["permission"] for p in body["data"] if p.get("status") == "granted"))
    else:
        print(f"permissions: HTTP {status} {json.dumps(_redact(body, token))}")
    status, body = _call("GET", f"{base}/{page}", {"fields": "id,name,access_token", "access_token": token})
    ok = status == 200 and bool(body.get("access_token"))
    shown = {k: v for k, v in body.items() if k != "access_token"} if isinstance(body, dict) else body
    print(f"page {page}: HTTP {status} {json.dumps(_redact(shown, token))} | page token available: {ok}")
    status, body = _call("GET", f"{base}/{page}", {"fields": "instagram_business_account{id,username}", "access_token": token})
    print(f"linked Instagram: HTTP {status} {json.dumps(_redact(body, token))}")
    if not ok:
        sys.exit("FAIL: cannot get a Page token.")
    print("Facebook check passed.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        check(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "check-facebook":
        check_facebook()
    elif cmd == "publish-instagram" and len(sys.argv) == 4:
        with open(sys.argv[3], encoding="utf-8") as f:
            publish_instagram(sys.argv[2], f.read().strip())
    else:
        sys.exit(__doc__)

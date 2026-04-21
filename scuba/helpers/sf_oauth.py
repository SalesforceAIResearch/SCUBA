"""
Salesforce OAuth Authorization Code helpers.

One-time interactive authorization saves a refresh token.
Subsequent calls use the refresh token to mint access tokens
and convert them to single-use frontdoor URLs via /services/oauth2/singleaccess.

Connected App requirements:
  - OAuth Scopes: "Full access (full)", "Perform requests at any time (refresh_token)"
  - Callback URL: http://localhost:9876/callback
  - Authorization Code flow enabled
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs

import requests

from scuba.helpers.utils import get_org_info

logger = logging.getLogger(__name__)

CALLBACK_PORT = 9876
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}/callback"
TOKEN_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "oauth_refresh_token.json")


def _generate_pkce():
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _save_refresh_token(org_alias: str, refresh_token: str, instance_url: str):
    token_store = {}
    if os.path.exists(TOKEN_STORE_PATH):
        with open(TOKEN_STORE_PATH) as f:
            token_store = json.load(f)
    token_store[org_alias] = {
        "refresh_token": refresh_token,
        "instance_url": instance_url,
    }
    os.makedirs(os.path.dirname(TOKEN_STORE_PATH), exist_ok=True)
    with open(TOKEN_STORE_PATH, "w") as f:
        json.dump(token_store, f, indent=2)


def _load_refresh_token(org_alias: str) -> dict | None:
    if not os.path.exists(TOKEN_STORE_PATH):
        return None
    with open(TOKEN_STORE_PATH) as f:
        store = json.load(f)
    return store.get(org_alias)


def authorize_interactive(org_alias: str) -> dict:
    """
    Run the Authorization Code + PKCE flow interactively.

    Opens a browser for the user to log in (MFA once is fine).
    Captures the callback, exchanges for tokens, saves the refresh_token.
    Returns the full token response dict.
    """
    org_info = get_org_info(org_alias)
    instance = org_info["instance"].rstrip("/")
    client_id = org_info["client_key"]
    client_secret = org_info["client_secret"]

    code_verifier, code_challenge = _generate_pkce()

    auth_params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{instance}/services/oauth2/authorize?{urlencode(auth_params)}"

    captured = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if "code" in query:
                captured["code"] = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h2>Authorization successful!</h2><p>You can close this tab.</p>")
            else:
                captured["error"] = query.get("error", ["unknown"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h2>Authorization failed: {captured.get('error')}</h2>".encode())

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("localhost", CALLBACK_PORT), _Handler)
    server_thread = threading.Thread(target=server.handle_request, daemon=True)
    server_thread.start()

    logger.info("Opening browser for Salesforce OAuth authorization (one-time)...")
    print(f"\n  Opening browser for Salesforce login...")
    print(f"  Log in and click Allow. This is a one-time step.\n")
    webbrowser.open(auth_url)

    server_thread.join(timeout=180)
    server.server_close()

    if "code" not in captured:
        raise RuntimeError(
            f"OAuth authorization failed: {captured.get('error', 'no callback received (timeout?)')}"
        )

    logger.info("Authorization code received, exchanging for tokens...")

    resp = requests.post(
        f"{instance}/services/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": captured["code"],
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    body = resp.json()
    if "access_token" not in body:
        raise RuntimeError(f"Token exchange failed: {body}")

    if "refresh_token" not in body:
        raise RuntimeError(
            "No refresh_token in response. "
            "Ensure the Connected App has 'Perform requests at any time (refresh_token, offline_access)' scope."
        )

    _save_refresh_token(org_alias, body["refresh_token"], body.get("instance_url", instance))
    logger.info(f"Refresh token saved for org '{org_alias}'. Scope: {body.get('scope')}")
    return body


def refresh_access_token(org_alias: str) -> dict:
    """
    Use a saved refresh_token to get a fresh access_token.
    If no refresh token is found, triggers interactive authorization automatically.
    Returns the token response dict (has access_token, instance_url, scope, etc.).
    """
    org_info = get_org_info(org_alias)
    saved = _load_refresh_token(org_alias)

    if saved is None:
        logger.info(f"No saved refresh token for '{org_alias}'. Starting interactive authorization...")
        body = authorize_interactive(org_alias)
        return body

    instance = org_info["instance"].rstrip("/")
    resp = requests.post(
        f"{instance}/services/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": saved["refresh_token"],
            "client_id": org_info["client_key"],
            "client_secret": org_info["client_secret"],
        },
    )
    body = resp.json()
    if "access_token" not in body:
        logger.warning(f"Refresh token expired/revoked for '{org_alias}'. Re-authorizing...")
        body = authorize_interactive(org_alias)
    return body


def get_frontdoor_url(access_token: str, instance_url: str) -> str:
    """
    Exchange an access_token for a single-use frontdoor URL
    via /services/oauth2/singleaccess.
    Each call returns a unique URL — call once per browser instance.
    """
    instance_url = instance_url.rstrip("/")
    resp = requests.post(
        f"{instance_url}/services/oauth2/singleaccess",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        data={},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"singleaccess failed (HTTP {resp.status_code}): {resp.text}")
    body = resp.json()
    if "frontdoor_uri" not in body:
        raise RuntimeError(f"singleaccess response missing frontdoor_uri: {body}")
    return body["frontdoor_uri"]


def get_frontdoor_url_for_org(org_alias: str) -> str:
    """
    All-in-one: refresh the access token (or authorize interactively
    if needed), then return a single-use frontdoor URL.
    """
    oauth = refresh_access_token(org_alias)
    return get_frontdoor_url(oauth["access_token"], oauth["instance_url"])

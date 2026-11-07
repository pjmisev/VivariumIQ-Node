"""HTTP authentication and JWT refresh helpers for the urcast node."""

from __future__ import annotations

import base64
import binascii
import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import config

PLACEHOLDER_TOKEN = "paste-your-jwt-token-here"
TOKEN_REFRESH_MARGIN = timedelta(hours=1)
REFRESH_RETRY_SECONDS = 60


class ApiError(RuntimeError):
    def __init__(self, message, *, status=None, detail=None):
        super().__init__(message)
        self.status = status
        self.detail = detail


class AuthError(RuntimeError):
    """Raised when a usable JWT cannot be obtained."""


def api_url():
    return config.get_str("URCAST_API_URL", config.DEFAULT_API_URL).rstrip("/")


def _error_detail(body):
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body

    detail = data.get("detail", data) if isinstance(data, dict) else data
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def _request_json(method, url, payload=None, token=None, timeout=10):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        detail = _error_detail(body)
        raise ApiError(
            f"HTTP {error.code}: {detail}",
            status=error.code,
            detail=detail,
        ) from None
    except urllib.error.URLError as error:
        raise ApiError(f"could not reach {url}: {error.reason}") from None

    if not body:
        return status, None

    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        raise ApiError(
            f"invalid JSON response from {url}: {body!r}",
            status=status,
        ) from None


def login(email, password):
    _, data = _request_json(
        "POST",
        f"{api_url()}/api/auth/login",
        {"email": email, "password": password},
    )
    token = (data or {}).get("access_token")
    if not token:
        raise ApiError("login response did not include access_token")
    return token


def register_user(username, email, password):
    _, data = _request_json(
        "POST",
        f"{api_url()}/api/user",
        {"username": username, "email": email, "password": password},
    )
    return data


def get_me(token):
    _, data = _request_json("GET", f"{api_url()}/api/auth/me", token=token)
    return data


def register_node(token, node_name, location_name=None, latitude=None, longitude=None):
    payload = {"node_name": node_name}
    if location_name is not None:
        payload["location_name"] = location_name
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude

    _, data = _request_json(
        "POST",
        f"{api_url()}/api/node",
        payload,
        token=token,
    )
    return data


def get_node(node_id):
    _, data = _request_json("GET", f"{api_url()}/api/node/{node_id}")
    return data


def check_authentication(token=None):
    token = token or config.get_str("URCAST_NODE_TOKEN")
    if not token or token == PLACEHOLDER_TOKEN:
        return None
    try:
        return get_me(token)
    except ApiError as error:
        if error.status == 401:
            return None
        raise


def token_expiry(token):
    if not token or token == PLACEHOLDER_TOKEN:
        return None

    try:
        payload_part = token.split(".")[1]
        padding = "=" * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part + padding))
    except (IndexError, ValueError, TypeError, binascii.Error):
        return None

    expires_at = payload.get("exp")
    if not isinstance(expires_at, (int, float)):
        return None
    return datetime.fromtimestamp(expires_at, tz=timezone.utc)


def _token_is_usable(token):
    expires_at = token_expiry(token)
    if expires_at is None:
        return False
    return expires_at > datetime.now(timezone.utc) + timedelta(seconds=30)


def _needs_refresh(token):
    expires_at = token_expiry(token)
    if expires_at is None:
        return True
    return expires_at - datetime.now(timezone.utc) <= TOKEN_REFRESH_MARGIN


class TokenManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._token = config.get_str("URCAST_NODE_TOKEN")
        self._email = config.get_str("URCAST_EMAIL")
        self._password = config.get_str("URCAST_PASSWORD")
        self._next_retry = 0.0

    def _credentials(self):
        if not self._email or not self._password:
            raise AuthError(
                "URCAST_EMAIL and URCAST_PASSWORD are missing from .env; "
                "run setup_node.py first"
            )
        return self._email, self._password

    def get_token(self, force_refresh=False):
        with self._lock:
            if not force_refresh and not _needs_refresh(self._token):
                return self._token

            email, password = self._credentials()
            now = time.monotonic()
            if (
                not force_refresh
                and now < self._next_retry
                and _token_is_usable(self._token)
            ):
                return self._token

            try:
                token = login(email, password)
            except ApiError as error:
                self._next_retry = now + REFRESH_RETRY_SECONDS
                if _token_is_usable(self._token):
                    return self._token
                raise AuthError(f"could not refresh JWT: {error}") from error

            self._token = token
            self._next_retry = 0.0
            config.save({"URCAST_NODE_TOKEN": token})
            return token


_manager = None


def get_token(force_refresh=False):
    global _manager
    if _manager is None:
        _manager = TokenManager()
    return _manager.get_token(force_refresh=force_refresh)

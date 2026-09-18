import base64
import hashlib
import hmac
import secrets
import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request, Response, WebSocket, status
from backend.config import get_settings

# Failed login attempts tracker: client_ip -> (attempts, lock_until_timestamp)
_failed_attempts: Dict[str, Tuple[int, float]] = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60.0
COOKIE_NAME = "resmon_session"


def check_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if IP is currently locked out."""
    now = time.time()
    if client_ip in _failed_attempts:
        attempts, lock_until = _failed_attempts[client_ip]
        if lock_until > now:
            return False
        if lock_until <= now and attempts >= MAX_FAILED_ATTEMPTS:
            # Lockout expired, reset
            _failed_attempts.pop(client_ip, None)
    return True


def record_failed_attempt(client_ip: str) -> None:
    now = time.time()
    attempts, _ = _failed_attempts.get(client_ip, (0, 0.0))
    attempts += 1
    lock_until = now + LOCKOUT_SECONDS if attempts >= MAX_FAILED_ATTEMPTS else 0.0
    _failed_attempts[client_ip] = (attempts, lock_until)


def reset_failed_attempts(client_ip: str) -> None:
    _failed_attempts.pop(client_ip, None)


def create_session_token(username: str, secret_key: str) -> str:
    """Create a tamper-proof HMAC signed session token with expiry timestamp (24 hours)."""
    expires_at = int(time.time()) + 86400
    payload = f"{username}:{expires_at}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("utf-8")


def verify_session_token(token: str, expected_username: str, secret_key: str) -> bool:
    """Verify validity, expiration, and HMAC signature of session token."""
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            return False
        user, expires_at_str, signature = parts
        if int(expires_at_str) < time.time():
            return False
        if not secrets.compare_digest(user, expected_username):
            return False
        payload = f"{user}:{expires_at_str}"
        expected_signature = hmac.new(
            secret_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return secrets.compare_digest(signature, expected_signature)
    except Exception:
        return False


def get_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def parse_basic_auth(auth_header: str) -> Tuple[str, str]:
    """Parse 'Basic <base64>' header into username and password."""
    if not auth_header or not auth_header.startswith("Basic "):
        return "", ""
    try:
        encoded = auth_header.split(" ", 1)[1].strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" in decoded:
            username, password = decoded.split(":", 1)
            return username, password
    except Exception:
        pass
    return "", ""


async def authenticate_http_request(request: Request, response: Response) -> bool:
    """
    Authenticate HTTP request via session cookie or HTTP Basic Auth.
    If unauthenticated, returns 401 with WWW-Authenticate header to trigger
    the native browser login dialog.
    """
    settings = get_settings()
    if not settings.AUTH_ENABLED:
        return True

    # 1. Check existing signed session cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token and verify_session_token(cookie_token, settings.AUTH_USERNAME, settings.SECRET_KEY):
        return True

    client_ip = get_client_ip(request)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. IP temporarily locked out for 60 seconds.",
        )

    # 2. Check HTTP Basic Auth header
    auth_header = request.headers.get("Authorization", "")
    username, password = parse_basic_auth(auth_header)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": 'Basic realm="ResMon"'},
        )

    user_match = secrets.compare_digest(username, settings.AUTH_USERNAME)
    pass_match = secrets.compare_digest(password, settings.AUTH_PASSWORD)

    if not (user_match and pass_match):
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="ResMon"'},
        )

    # Login successful: reset failed counter and set secure session cookie
    reset_failed_attempts(client_ip)
    session_token = create_session_token(settings.AUTH_USERNAME, settings.SECRET_KEY)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    return True


def authenticate_websocket(websocket: WebSocket) -> bool:
    """
    Authenticate WebSocket connection via cookie or Authorization header.
    """
    settings = get_settings()
    if not settings.AUTH_ENABLED:
        return True

    # 1. Check cookie
    cookie_token = websocket.cookies.get(COOKIE_NAME)
    if cookie_token and verify_session_token(cookie_token, settings.AUTH_USERNAME, settings.SECRET_KEY):
        return True

    # 2. Check Basic auth header (if client sends it)
    auth_header = websocket.headers.get("authorization", "")
    username, password = parse_basic_auth(auth_header)
    if username and password:
        user_match = secrets.compare_digest(username, settings.AUTH_USERNAME)
        pass_match = secrets.compare_digest(password, settings.AUTH_PASSWORD)
        if user_match and pass_match:
            return True

    return False

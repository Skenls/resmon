import base64
import hashlib
import hmac
import secrets
import time
from typing import Dict, List, Tuple
from fastapi import HTTPException, Request, Response, WebSocket, status
from backend.config import get_settings

# Failed login attempts tracker: client_ip -> list of failure timestamps
_failed_attempts: Dict[str, List[float]] = {}
MAX_FAILED_ATTEMPTS = 10
WINDOW_SECONDS = 60.0
COOKIE_NAME = "resmon_session"


def get_client_ip(request: Request) -> str:
    """Extract real client IP considering proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "unknown"


def is_rate_limited(client_ip: str) -> bool:
    """Return True if client_ip has exceeded MAX_FAILED_ATTEMPTS in the last WINDOW_SECONDS."""
    now = time.time()
    attempts = _failed_attempts.get(client_ip, [])
    # Keep only timestamps within the sliding window
    valid_attempts = [t for t in attempts if now - t < WINDOW_SECONDS]
    _failed_attempts[client_ip] = valid_attempts
    return len(valid_attempts) >= MAX_FAILED_ATTEMPTS


def record_failed_attempt(client_ip: str) -> None:
    now = time.time()
    attempts = _failed_attempts.get(client_ip, [])
    valid_attempts = [t for t in attempts if now - t < WINDOW_SECONDS]
    valid_attempts.append(now)
    _failed_attempts[client_ip] = valid_attempts


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
    If valid credentials are provided, always authenticates and resets failed attempts.
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

    # 2. Check HTTP Basic Auth header
    auth_header = request.headers.get("Authorization", "")
    username, password = parse_basic_auth(auth_header)

    # 3. If credentials were provided, verify them first
    if username:
        user_match = secrets.compare_digest(username, settings.AUTH_USERNAME)
        pass_match = secrets.compare_digest(password, settings.AUTH_PASSWORD)

        if user_match and pass_match:
            # Legitimate user: reset failed counter, issue session token, and allow immediately
            reset_failed_attempts(client_ip)
            session_token = create_session_token(settings.AUTH_USERNAME, settings.SECRET_KEY)
            request.state.session_token = session_token
            response.set_cookie(
                key=COOKIE_NAME,
                value=session_token,
                httponly=True,
                samesite="lax",
                max_age=86400,
            )
            return True

    # 4. Check if client IP is currently rate limited
    if is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. IP temporarily locked out for 60 seconds.",
        )

    # 5. Record the failed attempt if invalid credentials were provided
    if username:
        record_failed_attempt(client_ip)

    # 6. Challenge with 401 (browser popup)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": 'Basic realm="ResMon"'},
    )


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

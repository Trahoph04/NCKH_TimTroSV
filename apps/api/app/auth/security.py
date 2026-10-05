"""Password hashing (bcrypt) + JWT token encode/decode. Core security primitives."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _encode(sub: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def make_access_token(user_id: int, role: str) -> str:
    return _encode(
        str(user_id),
        "access",
        timedelta(minutes=settings.access_token_ttl_min),
        {"role": role},
    )


def make_refresh_token(user_id: int) -> str:
    return _encode(
        str(user_id),
        "refresh",
        timedelta(days=settings.refresh_token_ttl_days),
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Giải mã + verify. Raise jwt.InvalidTokenError nếu hỏng/hết hạn/sai type."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload


def make_ws_ticket(user_id: int, ttl_seconds: int = 60) -> str:
    """Vé ngắn hạn để mở WebSocket chat.

    Browser không gắn được header Authorization vào WebSocket, còn access token
    nằm trong httpOnly cookie phía Next (khác origin với API). Nên FE xin vé qua
    Route Handler (có cookie) rồi mở ws://API/chat/ws?ticket=... — vé chỉ sống
    60s và chỉ dùng được cho WS (type='ws'), lộ ra log URL cũng không thành
    access token.
    """
    return _encode(str(user_id), "ws", timedelta(seconds=ttl_seconds))

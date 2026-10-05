"""Auth providers — điểm mở rộng đa nguồn đăng nhập.

local  : email + password (bcrypt)
google : verify Google ID token
ctu    : MSSV + password (STUB — cắm sau, chỉ cần verify với hệ thống CTU)

Mỗi provider trả về VerifiedIdentity đã xác thực; router lo phần tạo/join user.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from ..config import settings
from .security import verify_password


@dataclass
class VerifiedIdentity:
    provider: str
    provider_user_id: str        # email(local) | google sub | mssv(ctu)
    email: str
    name: str | None = None
    avatar_url: str | None = None
    email_verified: bool = False


class AuthError(Exception):
    """Xác thực thất bại (sai mật khẩu, token hỏng...). Router map → 401."""


# ── local ────────────────────────────────────────────────────────────────
def verify_local(secret_hash: str | None, password: str) -> None:
    """Raise AuthError nếu sai. Không trả identity vì router đã có row từ repo."""
    if not verify_password(password, secret_hash or ""):
        raise AuthError("email hoặc mật khẩu sai")


# ── google ───────────────────────────────────────────────────────────────
GOOGLE_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google(id_token: str) -> VerifiedIdentity:
    """Verify Google ID token qua tokeninfo. Check aud == client_id."""
    if not settings.google_client_id:
        raise AuthError("Google login chưa cấu hình (thiếu GOOGLE_CLIENT_ID)")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GOOGLE_TOKENINFO, params={"id_token": id_token})
    if resp.status_code != 200:
        raise AuthError("Google token không hợp lệ")
    data = resp.json()
    if data.get("aud") != settings.google_client_id:
        raise AuthError("Google token sai audience")
    return VerifiedIdentity(
        provider="google",
        provider_user_id=data["sub"],
        email=data.get("email", ""),
        name=data.get("name"),
        avatar_url=data.get("picture"),
        email_verified=data.get("email_verified") in (True, "true"),
    )


# ── ctu ──────────────────────────────────────────────────────────────────
def verify_ctu(secret_hash: str | None, password: str) -> None:
    """Xác thực MSSV + mã dùng một lần của tài khoản ĐÃ CẤP TRƯỚC.

    KHÔNG phải SSO CTU thật — và nói rõ điều đó là có chủ đích. Tài khoản được
    `app.matching.import_survey` tạo sẵn từ phản hồi khảo sát, mật khẩu sinh
    ngẫu nhiên và in thành phiếu phát tại buổi thử nghiệm (không có SĐT nên
    không gửi OTP được, và dựng gửi email là ngoài phạm vi phiên này — xem
    Matching_Messaging_Design.md 1.4.3).

    Khi cắm SSO/LDAP CTU thật: bỏ `secret_hash`, gọi cổng CTU ở đây và giữ
    nguyên chữ ký phía router. `user_identities.secret_hash` tách khỏi
    `users.password_hash` chính là để lúc đó không phải đụng bảng users.
    """
    if not secret_hash:
        raise AuthError("Tài khoản này chưa đặt mã đăng nhập")
    if not verify_password(password, secret_hash):
        raise AuthError("MSSV hoặc mã đăng nhập sai")

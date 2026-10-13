"""FastAPI dependencies: rút current user từ Bearer access token."""
from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .schemas import UserOut
from .security import decode_token

_bearer = HTTPBearer(auto_error=True)

LOCKED_DETAIL = "Tài khoản đã bị khoá. Liên hệ quản trị viên nếu cần mở lại."

# engine set bởi main.py qua init_auth()
_repo = None


def init_auth_deps(repo) -> None:
    global _repo
    _repo = repo


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
) -> UserOut:
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token không hợp lệ")

    user = _repo.get_user(int(payload["sub"]))
    if user is None:
        raise HTTPException(401, "User không tồn tại")
    # đọc DB mỗi request ⇒ admin khoá là có hiệu lực ngay, không chờ access token hết hạn (mig 101)
    if user.get("locked_at") is not None:
        raise HTTPException(403, LOCKED_DETAIL)
    return UserOut(**user)


def require_admin(user: UserOut = Depends(get_current_user)) -> UserOut:
    if user.role != "admin":
        raise HTTPException(403, "Yêu cầu quyền admin")
    return user

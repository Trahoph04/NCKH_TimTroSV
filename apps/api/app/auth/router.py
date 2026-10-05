"""Auth endpoints: register, login (local), login/google, refresh, me."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from .deps import get_current_user
from .providers import AuthError, verify_ctu, verify_google, verify_local
from .repo import AuthRepo
from .schemas import (
    CtuLoginIn,
    GoogleLoginIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
)
from .security import decode_token, hash_password, make_access_token, make_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])

_engine: Engine | None = None


def init_auth(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_repo() -> AuthRepo:
    if _engine is None:
        raise HTTPException(503, "Auth repo chưa khởi tạo")
    return AuthRepo(_engine)


def _tokens(user_id: int, role: str) -> TokenPair:
    return TokenPair(
        access_token=make_access_token(user_id, role),
        refresh_token=make_refresh_token(user_id),
    )


@router.post("/register", response_model=TokenPair, status_code=201)
def register(body: RegisterIn, repo: AuthRepo = Depends(get_repo)):
    if repo.email_exists(body.email):
        raise HTTPException(409, "Email đã đăng ký")
    try:
        created = repo.create_user_with_identity(
            email=body.email,
            name=body.name,
            provider="local",
            provider_user_id=body.email,
            secret_hash=hash_password(body.password),
        )
    except IntegrityError:
        raise HTTPException(409, "Email đã đăng ký")
    return _tokens(created["user_id"], created["role"])


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, repo: AuthRepo = Depends(get_repo)):
    identity = repo.find_identity("local", body.email)
    if identity is None:
        raise HTTPException(401, "Email hoặc mật khẩu sai")
    try:
        verify_local(identity["secret_hash"], body.password)
    except AuthError as e:
        raise HTTPException(401, str(e))
    return _tokens(identity["user_id"], identity["role"])


@router.post("/login/google", response_model=TokenPair)
async def login_google(body: GoogleLoginIn, repo: AuthRepo = Depends(get_repo)):
    try:
        vi = await verify_google(body.id_token)
    except AuthError as e:
        raise HTTPException(401, str(e))

    identity = repo.find_identity("google", vi.provider_user_id)
    if identity is not None:
        return _tokens(identity["user_id"], identity["role"])

    # lần đầu: tạo user + google identity (secret_hash NULL)
    try:
        created = repo.create_user_with_identity(
            email=vi.email,
            name=vi.name,
            provider="google",
            provider_user_id=vi.provider_user_id,
            secret_hash=None,
            avatar_url=vi.avatar_url,
            email_verified=vi.email_verified,
        )
    except IntegrityError:
        # email đã tồn tại (đăng ký local trước) — chặn để tránh chiếm tài khoản
        raise HTTPException(409, "Email đã dùng cho phương thức đăng nhập khác")
    return _tokens(created["user_id"], created["role"])


@router.post("/login/ctu", response_model=TokenPair)
def login_ctu(body: CtuLoginIn, repo: AuthRepo = Depends(get_repo)):
    """Đăng nhập bằng MSSV — tài khoản cấp trước cho buổi thử nghiệm.

    KHÔNG tự tạo tài khoản khi không tìm thấy MSSV (khác /login/google): pool
    ghép chỉ gồm người đã đồng ý dùng thử trong khảo sát, nên tạo tài khoản
    bằng một MSSV lạ sẽ mở pool cho người chưa đồng ý.

    Thông điệp lỗi giống nhau cho "không có MSSV" và "sai mã" — không để kẻ gọi
    API dò xem MSSV nào có trong hệ thống.
    """
    identity = repo.find_identity("ctu", body.mssv.strip().upper())
    if identity is None:
        raise HTTPException(401, "MSSV hoặc mã đăng nhập sai")
    try:
        verify_ctu(identity["secret_hash"], body.password)
    except AuthError:
        raise HTTPException(401, "MSSV hoặc mã đăng nhập sai")
    return _tokens(identity["user_id"], identity["role"])


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, repo: AuthRepo = Depends(get_repo)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Refresh token hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Refresh token không hợp lệ")

    user = repo.get_user(int(payload["sub"]))
    if user is None:
        raise HTTPException(401, "User không tồn tại")
    return _tokens(user["id"], user["role"])


@router.get("/me", response_model=UserOut)
def me(user: UserOut = Depends(get_current_user)):
    return user

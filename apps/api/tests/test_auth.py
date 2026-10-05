import asyncio
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth import providers, security
from app.auth.providers import AuthError, verify_ctu, verify_google, verify_local
from app.auth.security import (
    decode_token,
    hash_password,
    make_access_token,
    make_refresh_token,
    verify_password,
)
from app.config import settings


# ── hash_password / verify_password ──
def test_hash_verify_roundtrip():
    hashed = hash_password("s3cret123")
    assert verify_password("s3cret123", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("s3cret123")
    assert verify_password("wrong-pass", hashed) is False


def test_verify_password_empty_hash():
    assert verify_password("anything", "") is False


def test_verify_password_none_hash():
    assert verify_password("anything", None) is False


# ── access / refresh tokens ──
def test_access_token_roundtrip():
    token = make_access_token(42, "user")
    payload = decode_token(token, "access")
    assert payload["sub"] == "42"
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    token = make_refresh_token(42)
    payload = decode_token(token, "refresh")
    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"


def test_decode_wrong_type_access_as_refresh():
    token = make_access_token(1, "user")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, "refresh")


def test_decode_wrong_type_refresh_as_access():
    token = make_refresh_token(1)
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, "access")


def test_expired_access_token(monkeypatch):
    monkeypatch.setattr(settings, "access_token_ttl_min", -1)
    token = make_access_token(1, "user")
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, "access")


def test_expired_refresh_token(monkeypatch):
    monkeypatch.setattr(settings, "refresh_token_ttl_days", -1)
    token = make_refresh_token(1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, "refresh")


def test_expired_token_manual_craft():
    # craft trực tiếp bằng jwt.encode, không đi qua make_access_token
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "type": "access",
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token, "access")


# ── providers.verify_local ──
def test_verify_local_correct_password():
    hashed = hash_password("correct-pw")
    verify_local(hashed, "correct-pw")  # không raise


def test_verify_local_wrong_password():
    hashed = hash_password("correct-pw")
    with pytest.raises(AuthError):
        verify_local(hashed, "wrong-pw")


def test_verify_local_none_hash():
    with pytest.raises(AuthError):
        verify_local(None, "any-pw")


# ── providers.verify_ctu ──
# Không còn là stub: tài khoản MSSV được app.matching.import_survey cấp trước từ
# phản hồi khảo sát, xác thực cục bộ bằng user_identities.secret_hash (chưa phải
# SSO CTU thật — xem docstring verify_ctu).
def test_verify_ctu_dung_mat_khau_thi_khong_raise():
    h = hash_password("ma-dung-nhat-1-lan")
    verify_ctu(h, "ma-dung-nhat-1-lan")          # không raise = đạt


def test_verify_ctu_sai_mat_khau():
    h = hash_password("ma-dung")
    with pytest.raises(AuthError):
        verify_ctu(h, "ma-sai")


def test_verify_ctu_chua_dat_ma_dang_nhap():
    """secret_hash NULL (vd identity google) không được đi qua đường MSSV."""
    with pytest.raises(AuthError):
        verify_ctu(None, "bat-ky")


# ── providers.verify_google ──
def test_verify_google_no_client_id(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    with pytest.raises(AuthError):
        asyncio.run(verify_google("some-id-token"))


class _FakeResp:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeAsyncClient:
    """Fake httpx.AsyncClient — trả FakeResp cố định, không đi network."""

    def __init__(self, response: _FakeResp):
        self._response = response

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, *args, **kwargs):
        return self._response


def test_verify_google_bad_status(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-abc")
    fake = _FakeAsyncClient(_FakeResp(400, {}))
    monkeypatch.setattr(providers.httpx, "AsyncClient", fake)
    with pytest.raises(AuthError):
        asyncio.run(verify_google("bad-token"))


def test_verify_google_aud_mismatch(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-abc")
    fake = _FakeAsyncClient(_FakeResp(200, {"aud": "other-client", "sub": "123"}))
    monkeypatch.setattr(providers.httpx, "AsyncClient", fake)
    with pytest.raises(AuthError):
        asyncio.run(verify_google("mismatched-token"))


def test_verify_google_success(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-abc")
    fake = _FakeAsyncClient(
        _FakeResp(
            200,
            {
                "aud": "client-abc",
                "sub": "goog-sub-1",
                "email": "user@example.com",
                "name": "Test User",
                "picture": "http://example.com/avatar.png",
                "email_verified": "true",
            },
        )
    )
    monkeypatch.setattr(providers.httpx, "AsyncClient", fake)
    identity = asyncio.run(verify_google("good-token"))
    assert identity.provider == "google"
    assert identity.provider_user_id == "goog-sub-1"
    assert identity.email == "user@example.com"
    assert identity.email_verified is True

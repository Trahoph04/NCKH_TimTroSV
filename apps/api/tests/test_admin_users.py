"""Quản lý người dùng cho admin (mig 101, thuyết minh dòng 4): chỉ admin; khoá có hiệu lực ngay với token đang có, chặn
đăng nhập/refresh; không tự khoá/tự hạ quyền. Chạy trên nckh_test."""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app, engine

client = TestClient(app)
PASSWORD = "testpass123"


def _register(admin: bool = False) -> dict:
    email = f"adminusers_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": PASSWORD, "name": "SV thử quản lý"})
    assert r.status_code == 201, r.text
    tokens = r.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    if admin:
        with engine.begin() as conn:
            conn.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user_id})
    return {"email": email, "headers": headers, "id": user_id, "refresh": tokens["refresh_token"]}


def test_admin_users_requires_admin():
    assert client.get("/admin/users").status_code == 403
    student = _register()
    assert client.get("/admin/users", headers=student["headers"]).status_code == 403
    assert client.patch(f"/admin/users/{student['id']}", json={"role": "admin"},
                        headers=student["headers"]).status_code == 403


def test_admin_searches_users_by_email():
    admin, student = _register(admin=True), _register()
    r = client.get("/admin/users", params={"q": student["email"]}, headers=admin["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == student["id"] and item["role"] == "user" and item["locked"] is False
    assert item["providers"] == ["local"]


def test_lock_blocks_existing_token_login_and_refresh_then_unlock_restores():
    admin, student = _register(admin=True), _register()
    r = client.patch(f"/admin/users/{student['id']}", json={"locked": True}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["locked"] is True

    assert client.get("/auth/me", headers=student["headers"]).status_code == 403  # token cũ mất hiệu lực ngay
    assert client.post("/auth/login", json={"email": student["email"], "password": PASSWORD}).status_code == 403
    assert client.post("/auth/refresh", json={"refresh_token": student["refresh"]}).status_code == 403
    # sai mật khẩu vẫn là 401 như mọi tài khoản — không lộ tài khoản nào đang bị khoá
    assert client.post("/auth/login", json={"email": student["email"], "password": "wrong-pass"}).status_code == 401

    r = client.patch(f"/admin/users/{student['id']}", json={"locked": False}, headers=admin["headers"])
    assert r.json()["locked"] is False
    assert client.get("/auth/me", headers=student["headers"]).status_code == 200


def test_promote_and_demote_user():
    admin, student = _register(admin=True), _register()
    r = client.patch(f"/admin/users/{student['id']}", json={"role": "admin"}, headers=admin["headers"])
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert client.get("/admin/users", headers=student["headers"]).status_code == 200  # quyền mới có hiệu lực ngay
    r = client.patch(f"/admin/users/{student['id']}", json={"role": "user"}, headers=admin["headers"])
    assert r.json()["role"] == "user"


def test_admin_cannot_lock_or_demote_self():
    admin = _register(admin=True)
    assert client.patch(f"/admin/users/{admin['id']}", json={"locked": True}, headers=admin["headers"]).status_code == 400
    assert client.patch(f"/admin/users/{admin['id']}", json={"role": "user"}, headers=admin["headers"]).status_code == 400


def test_update_validates_input():
    admin = _register(admin=True)
    assert client.patch("/admin/users/999999999", json={"locked": True}, headers=admin["headers"]).status_code == 404
    assert client.patch(f"/admin/users/{admin['id']}", json={"role": "superuser"},
                        headers=admin["headers"]).status_code == 422


def test_locked_user_websocket_is_refused():
    import pytest
    from starlette.websockets import WebSocketDisconnect

    from app.auth.security import make_ws_ticket

    admin, student = _register(admin=True), _register()
    ticket = make_ws_ticket(student["id"])  # vé cấp TRƯỚC khi bị khoá
    client.patch(f"/admin/users/{student['id']}", json={"locked": True}, headers=admin["headers"])
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/chat/ws?ticket={ticket}") as ws:
            ws.receive_text()
    assert exc.value.code == 4403

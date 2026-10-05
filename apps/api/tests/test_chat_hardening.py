"""Các lỗi chat từ rà soát 04/10: TOCTOU huỷ ghép, đối phương xoá tài khoản,
phân trang hội thoại, giới hạn socket, envelope Redis hỏng, upload quá lớn.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import ratelimit
from app.chat.body_limit import max_upload_bytes
from app.chat.hub import MAX_SOCKETS_PER_USER, ChatHub
from app.chat.repo import ChatRepo, ConversationGone
from app.main import app, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


def _user(name: str = "SV") -> dict:
    email = f"chat_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123", "name": name})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = client.get("/auth/me", headers=h).json()["id"]
    assert client.post("/matching/profile", headers=h, json={
        "gender": "nu", "sleep_time": 1, "cleanliness": 4, "noise_tolerance": 3,
        "budget_band": 1, "scenario": 2}).status_code == 200
    return {"id": uid, "h": h}


def _pair() -> tuple[dict, dict, int]:
    a, b = _user("An"), _user("Bình")
    client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"}, headers=a["h"])
    res = client.post("/matching/swipe", json={"target_id": a["id"], "decision": "like"},
                      headers=b["h"]).json()
    assert res["matched"] is True
    return a, b, res["conversation_id"]


def test_ghi_tin_sau_khi_hoi_thoai_bi_xoa_nem_ConversationGone_khong_500():
    """Mô phỏng khe TOCTOU: router đã kiểm quyền xong, đối phương huỷ ghép, rồi mới ghi."""
    a, _, conv = _pair()
    repo = ChatRepo(engine)
    assert repo.is_member(conv, a["id"])
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM conversations WHERE id = :c"), {"c": conv})
    with pytest.raises(ConversationGone):
        repo.create_message(conv, a["id"], "text", "xin chào")
    with pytest.raises(ConversationGone):
        repo.mark_read(conv, a["id"], 1)


def test_doi_phuong_xoa_tai_khoan_thi_moi_endpoint_deu_404():
    a, b, conv = _pair()
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": b["id"]})
    assert client.get(f"/chat/conversations/{conv}", headers=a["h"]).status_code == 404
    assert client.get(f"/chat/conversations/{conv}/messages", headers=a["h"]).status_code == 404
    assert client.post(f"/chat/conversations/{conv}/messages", json={"body": "hi"},
                       headers=a["h"]).status_code == 404


def test_danh_sach_hoi_thoai_phan_trang_keyset():
    me = _user("Tôi")
    convs = []
    for i in range(3):
        o = _user(f"B{i}")
        client.post("/matching/swipe", json={"target_id": o["id"], "decision": "like"}, headers=me["h"])
        convs.append(client.post("/matching/swipe", json={"target_id": me["id"], "decision": "like"},
                                 headers=o["h"]).json()["conversation_id"])
    p1 = client.get("/chat/conversations?limit=2", headers=me["h"]).json()
    assert len(p1["items"]) == 2 and p1["has_more"] is True and p1["next"]
    p2 = client.get("/chat/conversations", headers=me["h"],
                    params={"limit": 2, **p1["next"]}).json()
    assert p2["has_more"] is False
    ids = [c["id"] for c in p1["items"] + p2["items"]]
    assert sorted(ids) == sorted(convs) and len(set(ids)) == 3
    # thiếu một nửa con trỏ ⇒ 422
    assert client.get("/chat/conversations?before_id=1", headers=me["h"]).status_code == 422


def test_websocket_qua_so_socket_moi_user_bi_dong_4429():
    from starlette.websockets import WebSocketDisconnect

    u = _user()
    socks = []
    try:
        for _ in range(MAX_SOCKETS_PER_USER):
            t = client.post("/chat/ws-ticket", headers=u["h"]).json()["ticket"]
            ws = client.websocket_connect(f"/chat/ws?ticket={t}").__enter__()
            assert ws.receive_json()["type"] == "hello"
            socks.append(ws)
        t = client.post("/chat/ws-ticket", headers=u["h"]).json()["ticket"]
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect(f"/chat/ws?ticket={t}") as ws:
                ws.receive_json()
        assert e.value.code == 4429
    finally:
        for ws in socks:
            ws.__exit__(None, None, None)


@pytest.mark.parametrize("data", [
    "không phải json",
    json.dumps({"origin": "khac"}),             # thiếu text
    json.dumps({"origin": "khac", "text": 42}),  # text sai kiểu
    json.dumps(["mảng"]),
])
def test_envelope_redis_hong_khong_nem_loi(data):
    hub = ChatHub(None)
    hub._on_redis_message({"channel": "chat:u:1", "data": data})
    hub._on_redis_message({"channel": "chat:u:khong-phai-so",
                           "data": json.dumps({"origin": "khac", "text": "{}"})})


def test_upload_anh_qua_lon_bi_chan_413_truoc_khi_doc_body():
    a, _, conv = _pair()
    big = b"x" * (max_upload_bytes() + 1)
    r = client.post(f"/chat/conversations/{conv}/images", headers=a["h"],
                    files=[("files", ("a.png", big, "image/png"))])
    assert r.status_code == 413

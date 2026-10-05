"""E2E chat realtime + nền match (DB thật, Redis thật nếu có — không mock).

Chạy: DATABASE_URL=... REDIS_URL=... pytest tests/test_chat.py
Mỗi test tự đăng ký user mới (email random) nên chạy lặp được.
"""
import io
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from app.config import settings
from app.main import app, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def _media_tmp(tmp_path):
    old = settings.media_dir
    settings.media_dir = str(tmp_path)
    yield
    settings.media_dir = old


def _user(name: str = "SV", gender: str = "nu") -> dict:
    """Đăng ký + TẠO HỒ SƠ Ở GHÉP.

    Hồ sơ là bắt buộc để swipe được: POST /matching/swipe kiểm lọc cứng (chỉ ghép
    cùng giới), nên user không có hồ sơ thì không có giới tính để kiểm ⇒ 409.
    Trước đây swipe chỉ kiểm "user tồn tại" nên test không cần hồ sơ — đó chính
    là lỗ hổng cho phép ghép khác giới bằng cách POST thẳng target_id.
    """
    email = f"chat_{uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "testpass123", "name": name})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/auth/me", headers=h).json()
    # Hồ sơ tối thiểu để qua `in_pool`: giới tính + ít nhất một chiều lối sống.
    # Không khai deal_breakers/hanh_vi ⇒ không cặp nào bị lọc cứng loại oan.
    pr = client.post(
        "/matching/profile",
        json={"gender": gender, "sleep_time": 1, "cleanliness": 4,
              "noise_tolerance": 3, "budget_band": 1, "scenario": 2},
        headers=h,
    )
    assert pr.status_code == 200, pr.text
    return {"id": me["id"], "h": h, "name": name}


def _like(a: dict, b: dict) -> dict:
    r = client.post("/matching/swipe", json={"target_id": b["id"], "decision": "like"}, headers=a["h"])
    assert r.status_code == 200, r.text
    return r.json()


def _pair() -> tuple[dict, dict, int]:
    a, b = _user("An"), _user("Bình")
    assert _like(a, b)["matched"] is False
    res = _like(b, a)
    assert res["matched"] is True
    return a, b, res["conversation_id"]


def _send(u: dict, conv: int, body: str, **extra) -> dict:
    r = client.post(f"/chat/conversations/{conv}/messages", json={"body": body, **extra}, headers=u["h"])
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ match
def test_one_way_like_shows_in_likes_then_like_back_matches():
    a, b = _user("An"), _user("Bình")
    assert _like(a, b) == {"matched": False, "conversation_id": None}

    likes = client.get("/matching/likes", headers=b["h"]).json()["items"]
    assert [x["user_id"] for x in likes] == [a["id"]]
    assert "email" not in likes[0]  # T1: không lộ liên hệ
    assert client.get("/chat/unread", headers=b["h"]).json()["likes"] == 1

    res = _like(b, a)
    assert res["matched"] is True and res["conversation_id"]
    assert client.get("/matching/likes", headers=b["h"]).json()["items"] == []

    # hội thoại xuất hiện ở cả hai bên, có tin hệ thống, chưa tính là chưa đọc
    for u, other in ((a, b), (b, a)):
        items = client.get("/chat/conversations", headers=u["h"]).json()["items"]
        assert len(items) == 1
        c = items[0]
        assert c["id"] == res["conversation_id"]
        assert c["partner"]["id"] == other["id"]
        assert c["last_message"]["kind"] == "system"
        assert c["unread"] == 0 and c["user_message_count"] == 0

    # thích lại lần nữa: không tạo hội thoại thứ hai
    assert _like(a, b)["conversation_id"] == res["conversation_id"]


def test_pass_does_not_match_and_self_swipe_rejected():
    a, b = _user(), _user()
    client.post("/matching/swipe", json={"target_id": a["id"], "decision": "pass"}, headers=b["h"])
    assert _like(a, b)["matched"] is False
    r = client.post("/matching/swipe", json={"target_id": a["id"], "decision": "like"}, headers=a["h"])
    assert r.status_code == 400


def test_concurrent_mutual_likes_create_exactly_one_conversation():
    a, b = _user(), _user()
    results = []

    def go(x, y):
        results.append(_like(x, y))

    ts = [threading.Thread(target=go, args=(a, b)), threading.Thread(target=go, args=(b, a))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert any(r["matched"] for r in results)
    with engine.connect() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) FROM conversation_members m1 JOIN conversation_members m2 "
                "ON m1.conversation_id = m2.conversation_id WHERE m1.user_id = :a AND m2.user_id = :b"
            ),
            {"a": a["id"], "b": b["id"]},
        ).scalar_one()
    assert n == 1


# ----------------------------------------------------------------- tin nhắn
def test_send_list_poll_and_idempotent_client_id():
    a, b, conv = _pair()
    m1 = _send(a, conv, "  Chào bạn nha!  ", client_id="c-1")
    assert m1["body"] == "Chào bạn nha!" and m1["sender_id"] == a["id"] and m1["kind"] == "text"
    again = _send(a, conv, "Chào bạn nha!", client_id="c-1")  # mạng chập chờn, gửi lại
    assert again["id"] == m1["id"]
    m2 = _send(b, conv, "Chào An")

    page = client.get(f"/chat/conversations/{conv}/messages", headers=a["h"]).json()
    bodies = [m["body"] for m in page["items"] if m["kind"] == "text"]
    assert bodies == ["Chào bạn nha!", "Chào An"]

    polled = client.get(f"/chat/conversations/{conv}/messages?after_id={m1['id']}", headers=a["h"]).json()
    assert [m["id"] for m in polled["items"]] == [m2["id"]]

    older = client.get(f"/chat/conversations/{conv}/messages?before_id={m2['id']}&limit=1", headers=a["h"]).json()
    assert [m["id"] for m in older["items"]] == [m1["id"]] and older["has_more"] is True

    r = client.post(f"/chat/conversations/{conv}/messages", json={"body": "   "}, headers=a["h"])
    assert r.status_code == 422


def test_concurrent_same_client_id_khong_tao_tin_trung_va_khong_500():
    """Idempotency client_id phải chịu được 2 request SONG SONG.

    Bản trước là check-then-insert: cả hai request đều SELECT thấy "chưa có" rồi
    cùng INSERT ⇒ UNIQUE uq_messages_client nổ IntegrityError ⇒ 500, đúng lúc FE
    retry hoặc người dùng double-tap. Không có test nào phủ nên lỗi này ship xanh.
    """
    a, b, conv = _pair()
    results: list[int] = []
    errors: list[str] = []

    def send():
        try:
            r = client.post(
                f"/chat/conversations/{conv}/messages",
                json={"body": "gui song song", "client_id": "dup-race-1"},
                headers=a["h"],
            )
            results.append(r.status_code)
            if r.status_code >= 400:
                errors.append(r.text)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], errors
    assert results == [201, 201], results
    # ĐÚNG MỘT tin được lưu
    with engine.connect() as conn:
        n = conn.execute(
            text("SELECT count(*) FROM messages WHERE conversation_id = :c AND client_id = 'dup-race-1'"),
            {"c": conv},
        ).scalar_one()
    assert n == 1


def test_non_member_cannot_read_or_send():
    a, b, conv = _pair()
    stranger = _user()
    assert client.get(f"/chat/conversations/{conv}/messages", headers=stranger["h"]).status_code == 404
    assert client.get(f"/chat/conversations/{conv}", headers=stranger["h"]).status_code == 404
    r = client.post(f"/chat/conversations/{conv}/messages", json={"body": "hi"}, headers=stranger["h"])
    assert r.status_code == 404
    assert client.get("/chat/conversations").status_code == 403  # thiếu token


def test_unread_and_read_receipts():
    a, b, conv = _pair()
    _send(a, conv, "1")
    _send(a, conv, "2")
    last = _send(a, conv, "3")
    assert client.get("/chat/unread", headers=b["h"]).json()["messages"] == 3
    assert client.get("/chat/unread", headers=a["h"]).json()["messages"] == 0

    r = client.post(f"/chat/conversations/{conv}/read", json={"message_id": last["id"]}, headers=b["h"])
    assert r.json()["last_read_message_id"] == last["id"]
    assert client.get("/chat/unread", headers=b["h"]).json()["messages"] == 0

    # không lùi, không vượt tin cuối
    r = client.post(f"/chat/conversations/{conv}/read", json={"message_id": 1}, headers=b["h"])
    assert r.json()["last_read_message_id"] == last["id"]
    r = client.post(f"/chat/conversations/{conv}/read", json={"message_id": 10**9}, headers=b["h"])
    assert r.json()["last_read_message_id"] == last["id"]

    conv_a = client.get(f"/chat/conversations/{conv}", headers=a["h"]).json()
    assert conv_a["partner_last_read"] == last["id"]  # A thấy "Đã xem"


def test_share_listing_snapshot_server_side():
    a, b, conv = _pair()
    with engine.connect() as conn:
        lid = conn.execute(
            text("SELECT id FROM aggregated_listings WHERE status IS DISTINCT FROM 'hidden' LIMIT 1")
        ).scalar()
    if lid is None:
        pytest.skip("DB chưa có tin trọ")
    r = client.post(
        f"/chat/conversations/{conv}/messages",
        json={"kind": "listing", "listing_id": lid, "body": "Phòng này sao?"},
        headers=a["h"],
    )
    assert r.status_code == 201, r.text
    p = r.json()["payload"]
    assert p["listing_id"] == lid and p["title"]
    detail = client.get(f"/chat/conversations/{conv}", headers=b["h"]).json()
    assert detail["shared_listings"][0]["payload"]["listing_id"] == lid
    r = client.post(
        f"/chat/conversations/{conv}/messages", json={"kind": "listing", "listing_id": 10**8}, headers=a["h"]
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------- ảnh
def _png_with_gps() -> bytes:
    img = Image.new("RGB", (2400, 1200), (200, 120, 40))
    exif = Image.Exif()
    exif[0x8825] = {2: (10.0, 1.0, 30.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_image_upload_strips_exif_resizes_and_is_private():
    a, b, conv = _pair()
    raw = _png_with_gps()
    assert Image.open(io.BytesIO(raw)).getexif().get(0x8825) is not None
    r = client.post(
        f"/chat/conversations/{conv}/images",
        files=[("files", ("phong.jpg", raw, "image/jpeg"))],
        data={"body": "ảnh phòng", "client_id": "img-1"},
        headers=a["h"],
    )
    assert r.status_code == 201, r.text
    msg = r.json()
    assert msg["kind"] == "image" and msg["body"] == "ảnh phòng"
    img = msg["payload"]["images"][0]
    assert max(img["w"], img["h"]) == 1600

    got = client.get(f"/chat/media/{img['id']}", headers=b["h"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/jpeg"
    out = Image.open(io.BytesIO(got.content))
    assert len(out.getexif()) == 0  # GPS/EXIF đã bị xoá

    stranger = _user()
    assert client.get(f"/chat/media/{img['id']}", headers=stranger["h"]).status_code == 404
    assert client.get("/chat/media/../../etc/passwd", headers=a["h"]).status_code == 404


def test_image_upload_rejects_non_image_and_too_many():
    a, b, conv = _pair()
    r = client.post(
        f"/chat/conversations/{conv}/images",
        files=[("files", ("x.jpg", b"not an image", "image/jpeg"))],
        headers=a["h"],
    )
    assert r.status_code == 422
    small = io.BytesIO()
    Image.new("RGB", (10, 10)).save(small, "PNG")
    files = [("files", (f"{i}.png", small.getvalue(), "image/png")) for i in range(5)]
    r = client.post(f"/chat/conversations/{conv}/images", files=files, headers=a["h"])
    assert r.status_code == 422


# ------------------------------------------------------------------ huỷ ghép
def test_unmatch_deletes_everything_and_does_not_auto_rematch(tmp_path):
    a, b, conv = _pair()
    _send(a, conv, "hello")
    small = io.BytesIO()
    Image.new("RGB", (10, 10)).save(small, "PNG")
    msg = client.post(
        f"/chat/conversations/{conv}/images",
        files=[("files", ("a.png", small.getvalue(), "image/png"))],
        headers=a["h"],
    ).json()
    media_id = msg["payload"]["images"][0]["id"]
    assert (tmp_path / "chat" / f"{media_id}.jpg").exists()

    assert client.delete(f"/chat/conversations/{conv}", headers=b["h"]).status_code == 204
    assert client.get("/chat/conversations", headers=a["h"]).json()["items"] == []
    assert not (tmp_path / "chat" / f"{media_id}.jpg").exists()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM messages WHERE conversation_id = :c"), {"c": conv}).scalar() == 0

    # lượt thích cũ không tự ghép lại
    assert _like(a, b)["matched"] is False


def test_report_partner():
    a, b, conv = _pair()
    r = client.post(f"/chat/conversations/{conv}/report", json={"reason": "spam", "note": "x"}, headers=a["h"])
    assert r.status_code == 201
    with engine.connect() as conn:
        row = conn.execute(text("SELECT target_id, reason FROM user_reports WHERE id = :i"), {"i": r.json()["id"]}).one()
    assert row.target_id == b["id"] and row.reason == "spam"


# ----------------------------------------------------------------- WebSocket
def _ticket(u: dict) -> str:
    r = client.post("/chat/ws-ticket", headers=u["h"])
    assert r.status_code == 200, r.text
    return r.json()["ticket"]


def _recv_until(ws, typ: str, limit: int = 10) -> dict:
    for _ in range(limit):
        ev = ws.receive_json()
        if ev.get("type") == typ:
            return ev
    raise AssertionError(f"không nhận được {typ}")


def test_websocket_bad_ticket_closed_4401():
    from starlette.websockets import WebSocketDisconnect

    # Vé sai bị từ chối NGAY ở bước bắt tay (chưa accept) — không cấp socket
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/chat/ws?ticket=bogus") as ws:
            ws.receive_json()
    assert e.value.code == 4401

    # access token không dùng thay vé được (sai type)
    a = _user()
    token = a["h"]["Authorization"].split()[1]
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(f"/chat/ws?ticket={token}") as ws:
            ws.receive_json()
    assert e.value.code == 4401


def test_websocket_realtime_message_typing_read_presence():
    a, b, conv = _pair()
    with client.websocket_connect(f"/chat/ws?ticket={_ticket(b)}") as wb:
        hello = wb.receive_json()
        assert hello["type"] == "hello" and hello["user_id"] == b["id"] and hello["online"] == []

        with client.websocket_connect(f"/chat/ws?ticket={_ticket(a)}") as wa:
            hello_a = wa.receive_json()
            assert hello_a["online"] == [b["id"]]
            pres = _recv_until(wb, "presence")
            assert pres == {"type": "presence", "user_id": a["id"], "online": True}

            # A đang nhập → B thấy
            wa.send_json({"type": "typing", "conversation_id": conv, "is_typing": True})
            ev = _recv_until(wb, "typing")
            assert ev["user_id"] == a["id"] and ev["is_typing"] is True

            # A gửi qua REST → B nhận tức thì qua socket; A cũng nhận (đồng bộ tab khác)
            sent = _send(a, conv, "Realtime nè", client_id="rt-1")
            ev = _recv_until(wb, "message.new")
            assert ev["conversation_id"] == conv and ev["message"]["id"] == sent["id"]
            assert ev["message"]["body"] == "Realtime nè"
            assert _recv_until(wa, "message.new")["message"]["client_id"] == "rt-1"

            # B đọc → A nhận "đã xem"
            client.post(f"/chat/conversations/{conv}/read", json={"message_id": sent["id"]}, headers=b["h"])
            ev = _recv_until(wa, "read")
            assert ev["user_id"] == b["id"] and ev["message_id"] == sent["id"]

            # ping/pong giữ presence
            wa.send_json({"type": "ping"})
            assert _recv_until(wa, "pong")["type"] == "pong"

            # typing vào hội thoại không phải của mình: bị bỏ qua (không lỗi, không lọt)
            wa.send_json({"type": "typing", "conversation_id": 10**8})

        # A ngắt kết nối → B thấy offline + last_seen
        pres = _recv_until(wb, "presence")
        assert pres["user_id"] == a["id"] and pres["online"] is False and pres["last_seen_at"]

    convs = client.get("/chat/conversations", headers=b["h"]).json()["items"]
    assert convs[0]["partner"]["online"] is False and convs[0]["partner"]["last_seen_at"]


def test_websocket_receives_new_match_and_unmatch():
    a, b = _user(), _user()
    with client.websocket_connect(f"/chat/ws?ticket={_ticket(a)}") as wa:
        wa.receive_json()  # hello
        _like(b, a)
        assert _recv_until(wa, "like.new")["type"] == "like.new"
        res = _like(a, b)
        ev = _recv_until(wa, "match.new")
        assert ev["conversation_id"] == res["conversation_id"]
        client.delete(f"/chat/conversations/{res['conversation_id']}", headers=b["h"])
        ev = _recv_until(wa, "conversation.removed")
        assert ev["conversation_id"] == res["conversation_id"] and ev["by_user_id"] == b["id"]

"""Hai khẳng định trong docs/tech_specs/Chat_Realtime.md mà trước đây CHƯA test:

1. Fan-out nhiều worker: sự kiện publish ở process A tới được socket nằm ở
   process B qua Redis pub/sub — và không bị giao trùng ở A.
2. Redis chết ⇒ hub chạy local-only: publish không ném lỗi, socket cùng process
   vẫn nhận, và hub tự thử nối lại sau khoảng chờ.

Hai "process" ở đây là hai ChatHub độc lập (origin khác nhau) trong cùng một
pytest — đúng thứ phân biệt hai worker uvicorn: mỗi worker có một ChatHub riêng
và chỉ nói chuyện với nhau qua Redis.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest
import redis

from app.chat.hub import ChatHub, Connection
from app.config import settings


class FakeWS:
    def __init__(self):
        self.got: list[dict] = []
        self.event = threading.Event()

    async def send_text(self, text: str) -> None:
        self.got.append(json.loads(text))
        self.event.set()


def _loop_thread():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    return loop, t


def _redis_up() -> bool:
    try:
        redis.from_url(settings.redis_url, socket_connect_timeout=1).ping()
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.fixture
def loop():
    lp, t = _loop_thread()
    yield lp
    lp.call_soon_threadsafe(lp.stop)
    t.join(timeout=2)


def _wait(cond, timeout=3.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.mark.skipif(not _redis_up(), reason="cần Redis thật (docker compose)")
def test_fanout_qua_redis_giua_hai_worker_va_khong_giao_trung(loop):
    a, b = ChatHub(settings.redis_url), ChatHub(settings.redis_url)
    assert a.origin != b.origin
    uid = 900_000_000 + int(time.time()) % 1_000_000   # tránh đụng user thật đang mở socket
    ws_b, ws_a = FakeWS(), FakeWS()
    b.register(Connection(user_id=uid, websocket=ws_b, loop=loop))
    a.register(Connection(user_id=uid, websocket=ws_a, loop=loop))
    # listener pubsub của cả hai đã psubscribe (register → _get_redis → _start_listener)
    time.sleep(0.3)

    a.publish([uid], {"type": "ping-test", "n": 1})
    assert _wait(lambda: len(ws_b.got) == 1), "socket ở worker B không nhận được qua Redis"
    assert ws_b.got[0] == {"type": "ping-test", "n": 1}
    time.sleep(0.3)
    # worker A giao tại chỗ đúng MỘT lần; envelope quay về từ Redis bị bỏ nhờ `origin`
    assert len(ws_a.got) == 1 and len(ws_b.got) == 1


def test_redis_chet_thi_chay_local_only_khong_nem_loi(loop):
    hub = ChatHub("redis://127.0.0.1:1/0")      # cổng 1: chắc chắn không có Redis
    ws = FakeWS()
    conn = Connection(user_id=42, websocket=ws, loop=loop)
    assert hub.register(conn) is True           # online theo đếm cục bộ
    hub.publish([42], {"type": "message.new", "x": 1})
    assert _wait(lambda: ws.got == [{"type": "message.new", "x": 1}])
    assert hub.is_online(42) is True
    hub.heartbeat(42)                            # không ném
    # đang trong khoảng chờ 30s ⇒ không thử nối lại mỗi lần gọi (không chặn request)
    t0 = time.monotonic()
    for _ in range(20):
        hub.publish([42], {"type": "noop"})
    assert time.monotonic() - t0 < 1.0
    assert hub.unregister(conn) is True


def test_redis_song_lai_sau_khoang_cho_thi_noi_lai(loop):
    if not _redis_up():
        pytest.skip("cần Redis thật")
    hub = ChatHub(settings.redis_url)
    hub._redis_retry_at = time.monotonic() + 3600   # giả lập: vừa mất Redis
    assert hub._get_redis() is None
    hub._redis_retry_at = 0.0                        # hết khoảng chờ
    assert hub._get_redis() is not None

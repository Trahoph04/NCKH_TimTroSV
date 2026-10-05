"""Realtime hub cho chat: quản lý WebSocket + fan-out sự kiện qua Redis pub/sub.

Mô hình (docs/tech_specs/Chat_Realtime.md):

- Mỗi user có 1 kênh logic `chat:u:<user_id>`. Mọi sự kiện (tin mới, đã xem,
  đang nhập, online/offline, ghép mới…) được "publish tới danh sách user_id".
- Giao tại chỗ: nếu user đang có WebSocket ở CHÍNH process này → gửi thẳng.
- Giao chéo process: đồng thời PUBLISH lên Redis; mỗi process có 1 thread
  psubscribe `chat:u:*`, nhận envelope của process KHÁC rồi giao cho các socket
  tại chỗ. Envelope có `origin` để không giao trùng.
- Redis chết ⇒ vẫn chạy được ở chế độ 1 process (chỉ giao tại chỗ). FE còn có
  fallback polling REST, nên không có đường nào làm mất tin: tin luôn nằm ở DB
  trước khi được publish.

Hub thread-safe: REST endpoint (def thường) chạy trong threadpool, gọi
`publish()` từ thread khác — việc gửi xuống socket luôn được đẩy về đúng event
loop của socket đó bằng `run_coroutine_threadsafe`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

import redis

log = logging.getLogger("chat.hub")

CHANNEL_PREFIX = "chat:u:"
PRESENCE_TTL_S = 90  # client ping 25s/lần; mất 3 nhịp liên tiếp mới coi là offline
# Một người thật mở vài tab/thiết bị; hàng chục socket của một user là script
# hoặc vòng reconnect lỗi — chặn để một client hỏng không giữ hết file descriptor.
MAX_SOCKETS_PER_USER = 5


def _json_default(o: Any):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    raise TypeError(f"not serializable: {type(o)}")


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


@dataclass(eq=False)
class Connection:
    user_id: int
    websocket: Any                     # starlette WebSocket
    loop: asyncio.AbstractEventLoop
    conv_ids: set[int] = field(default_factory=set)  # cache quyền thành viên (typing)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    async def send_text(self, text: str) -> None:
        try:
            await self.websocket.send_text(text)
        except Exception:  # noqa: BLE001 — socket đóng giữa chừng: bỏ qua, disconnect sẽ dọn
            pass


class ChatHub:
    def __init__(self, redis_url: str | None):
        self.origin = uuid.uuid4().hex[:12]
        self._redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._pubsub_thread = None
        self._redis_retry_at = 0.0
        self._lock = threading.RLock()
        # Lock RIÊNG cho kết nối Redis: ping/psubscribe có thể mất tới vài giây
        # khi Redis chậm, giữ self._lock lúc đó là chặn mọi publish/register.
        self._redis_lock = threading.Lock()
        self._conns: dict[int, set[Connection]] = {}
        self._last_seen_local: dict[int, float] = {}

    # ------------------------------------------------------------------ redis
    def _get_redis(self) -> redis.Redis | None:
        """Kết nối Redis lười + tự thử lại sau 30s nếu đang chết.

        Check-then-act phải nằm TRONG lock: bản trước kiểm `self._redis is None`
        ngoài lock ⇒ hai thread (threadpool REST + event loop WS) cùng thấy None,
        cùng kết nối và cùng psubscribe ⇒ mỗi envelope chéo process bị giao HAI
        lần (tin nhắn hiện đôi bên người nhận).
        """
        if not self._redis_url:
            return None
        r = self._redis
        if r is not None:
            return r
        if time.monotonic() < self._redis_retry_at:
            return None
        with self._redis_lock:
            if self._redis is not None:          # thread khác vừa kết nối xong
                return self._redis
            now = time.monotonic()
            if now < self._redis_retry_at:
                return None
            try:
                r = redis.from_url(self._redis_url, decode_responses=True,
                                   socket_connect_timeout=1, socket_timeout=2)
                r.ping()
                self._start_listener(r)
                self._redis = r
                log.info("chat hub: redis ok (origin=%s)", self.origin)
                return r
            except Exception as exc:  # noqa: BLE001
                self._redis_retry_at = now + 30
                log.warning("chat hub: redis unavailable, local-only mode: %s", exc)
                return None

    def _drop_redis(self, exc: Exception) -> None:
        log.warning("chat hub: redis error, fallback local-only: %s", exc)
        self._redis = None
        self._redis_retry_at = time.monotonic() + 30
        t, self._pubsub_thread = self._pubsub_thread, None
        if t is not None:
            try:
                t.stop()
            except Exception:  # noqa: BLE001
                pass

    def _start_listener(self, r: redis.Redis) -> None:
        if self._pubsub_thread is not None:
            return
        # pubsub cần socket không timeout (chờ tin lâu); client riêng
        sub = redis.from_url(self._redis_url, decode_responses=True).pubsub(
            ignore_subscribe_messages=True
        )
        sub.psubscribe(**{f"{CHANNEL_PREFIX}*": self._on_redis_message})

        def _on_error(exc, pubsub, thread):  # noqa: ANN001
            log.warning("chat hub: pubsub thread died: %s", exc)
            self._drop_redis(exc)

        self._pubsub_thread = sub.run_in_thread(
            sleep_time=0.05, daemon=True, exception_handler=_on_error
        )

    def _on_redis_message(self, msg: dict) -> None:
        try:
            env = json.loads(msg["data"])
        except (ValueError, KeyError, TypeError):
            return
        if not isinstance(env, dict):
            return
        if env.get("origin") == self.origin:
            return  # đã giao tại chỗ lúc publish
        # Envelope do process khác (hoặc ai đó PUBLISH tay vào Redis) gửi tới —
        # không được tin cấu trúc. Ném lỗi ở callback này là giết thread pubsub
        # ⇒ _drop_redis ⇒ cả hub rơi về local-only vì MỘT tin hỏng.
        text_ = env.get("text")
        if not isinstance(text_, str):
            return
        try:
            uid = int(str(msg.get("channel", ""))[len(CHANNEL_PREFIX):])
        except ValueError:
            return
        try:
            self._deliver_local([uid], text_)
        except Exception:  # noqa: BLE001
            log.exception("chat hub: deliver từ redis lỗi, bỏ qua envelope")

    # ------------------------------------------------------------ connections
    def register(self, conn: Connection) -> bool:
        """Thêm socket. Trả True nếu user vừa chuyển offline → online."""
        with self._lock:
            conns = self._conns.setdefault(conn.user_id, set())
            first_local = not conns
            conns.add(conn)
        r = self._get_redis()
        if r is not None:
            try:
                key = f"presence:{conn.user_id}"
                n = r.incr(key)
                r.expire(key, PRESENCE_TTL_S)
                return n == 1
            except Exception as exc:  # noqa: BLE001
                self._drop_redis(exc)
        return first_local

    def unregister(self, conn: Connection) -> bool:
        """Bỏ socket. Trả True nếu user vừa chuyển online → offline."""
        with self._lock:
            conns = self._conns.get(conn.user_id, set())
            conns.discard(conn)
            last_local = not conns
            if last_local:
                self._conns.pop(conn.user_id, None)
                self._last_seen_local[conn.user_id] = time.time()
        # _get_redis() chứ không phải self._redis: nếu lúc register Redis đang
        # chết rồi sống lại, đọc thẳng self._redis sẽ bỏ qua lần decr này và bộ
        # đếm presence lệch vĩnh viễn (user offline vẫn báo online).
        r = self._get_redis()
        if r is not None:
            try:
                key = f"presence:{conn.user_id}"
                n = r.decr(key)
                if n <= 0:
                    r.delete(key)
                    return True
                return False
            except Exception as exc:  # noqa: BLE001
                self._drop_redis(exc)
        return last_local

    def heartbeat(self, user_id: int) -> None:
        """Gia hạn presence. PHẢI dựng lại key nếu nó đã biến mất.

        EXPIRE trên key không tồn tại là NO-OP: nếu ping cách nhau > PRESENCE_TTL_S
        (tab ngủ, mạng chớp, Redis evict) thì key hết hạn và từ đó mọi heartbeat
        đều vô nghĩa ⇒ user đang online bị báo offline VĨNH VIỄN cho tới khi
        reconnect. Dựng lại theo số socket cục bộ đang thực sự mở.
        """
        r = self._get_redis()
        if r is None:
            return
        try:
            key = f"presence:{user_id}"
            if r.expire(key, PRESENCE_TTL_S):
                return
            with self._lock:
                live = len(self._conns.get(user_id, ()))
            if live:
                # SET rồi hết hạn (không INCR): key đã mất nên bộ đếm cũ vô nghĩa,
                # đặt lại bằng số socket thật của process này.
                r.set(key, live, ex=PRESENCE_TTL_S)
        except Exception as exc:  # noqa: BLE001
            self._drop_redis(exc)

    def is_online(self, user_id: int) -> bool:
        with self._lock:
            if self._conns.get(user_id):
                return True
        r = self._get_redis()
        if r is not None:
            try:
                v = r.get(f"presence:{user_id}")
                return bool(v) and int(v) > 0
            except Exception as exc:  # noqa: BLE001
                self._drop_redis(exc)
        return False

    def online_map(self, user_ids: Iterable[int]) -> dict[int, bool]:
        ids = list(dict.fromkeys(user_ids))
        if not ids:
            return {}
        with self._lock:
            out = {u: bool(self._conns.get(u)) for u in ids}
        r = self._get_redis()
        if r is not None:
            try:
                vals = r.mget([f"presence:{u}" for u in ids])
                for u, v in zip(ids, vals):
                    out[u] = out[u] or (bool(v) and int(v) > 0)
            except Exception as exc:  # noqa: BLE001
                self._drop_redis(exc)
        return out

    def socket_count(self, user_id: int) -> int:
        with self._lock:
            return len(self._conns.get(user_id, ()))

    def local_connection_count(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._conns.values())

    # --------------------------------------------------------------- publish
    def publish(self, user_ids: Iterable[int], event: dict) -> None:
        """Gửi `event` tới mọi socket của các user. Gọi được từ bất kỳ thread nào."""
        ids = list(dict.fromkeys(int(u) for u in user_ids))
        if not ids:
            return
        text = dumps(event)
        # Tin đã COMMIT vào DB trước khi publish, nên lỗi ở tầng giao realtime
        # KHÔNG được biến request thành 500: người gửi sẽ thấy "gửi thất bại" rồi
        # gửi lại một tin đã nằm trong DB. Realtime là best-effort — mất một nhịp
        # đẩy thì FE còn polling bù (xem useChatSocket fallback).
        try:
            self._deliver_local(ids, text)
        except Exception:  # noqa: BLE001
            log.exception("deliver_local failed (tin đã lưu DB, bỏ qua nhịp đẩy)")
        r = self._get_redis()
        if r is None:
            return
        env = dumps({"origin": self.origin, "text": text})
        try:
            pipe = r.pipeline(transaction=False)
            for uid in ids:
                pipe.publish(f"{CHANNEL_PREFIX}{uid}", env)
            pipe.execute()
        except Exception as exc:  # noqa: BLE001
            self._drop_redis(exc)

    def _deliver_local(self, user_ids: list[int], text: str) -> None:
        with self._lock:
            targets = [c for uid in user_ids for c in self._conns.get(uid, ())]
        for conn in targets:
            if conn.loop.is_closed():
                continue
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is conn.loop:
                running.create_task(conn.send_text(text))
            else:
                asyncio.run_coroutine_threadsafe(conn.send_text(text), conn.loop)

"""Giới hạn tần suất theo user cho các hành động ghi (swipe, lời mời, tin nhắn, báo cáo).

Cửa sổ trượt trong bộ nhớ tiến trình — đủ cho cấu hình hiện tại (uvicorn 1
worker, xem apps/api/Dockerfile). Chạy nhiều worker thì mỗi worker đếm riêng ⇒
giới hạn thực tế nhân lên theo số worker; khi đó chuyển sang Redis (INCR+EXPIRE).
Không dùng Redis ngay vì Redis là phụ trợ: Redis chết thì chat phải còn chạy
(CLAUDE.md), và một bộ giới hạn phụ thuộc Redis sẽ hoặc chặn hết hoặc mở hết.

Mục đích là chặn script/bấm giữ phím làm bẩn số liệu nghiên cứu và spam người
khác, không phải chống DoS — ngưỡng đặt rộng hơn nhiều so với người dùng thật.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

# (số lần, cửa sổ giây)
LIMITS: dict[str, tuple[int, float]] = {
    "swipe": (60, 60.0),       # deck tối đa 30 thẻ; 1 thẻ/giây đã là quẹt không đọc
    "invite": (10, 60.0),
    "message": (30, 60.0),
    "upload": (10, 60.0),
    "report": (5, 600.0),
    "rate": (30, 60.0),
    "rec_session": (10, 600.0),  # mỗi lượt đánh giá gợi ý tốn 3 lần xếp hạng toàn danh mục
    "rec_judge": (90, 60.0),     # ~25 thẻ/lượt, bấm nhanh
    "chatbot": (12, 60.0),       # mỗi câu hỏi gọi LLM + truy xuất vector — ngưỡng giữ nguyên của branch PHUC
    "chatbot_feedback": (30, 60.0),
}

_lock = threading.Lock()
_hits: dict[tuple[str, int], deque[float]] = defaultdict(deque)


def check_rate(action: str, user_id: int) -> None:
    """Ném 429 khi `user_id` vượt giới hạn của `action`. Gọi ĐẦU endpoint, trước khi ghi DB."""
    limit, window = LIMITS[action]
    now = time.monotonic()
    key = (action, user_id)
    with _lock:
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            retry = max(1, int(window - (now - q[0])) + 1)
            raise HTTPException(
                429,
                "Bạn thao tác quá nhanh, thử lại sau ít phút",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)


def reset() -> None:
    """Cho test: xoá bộ đếm giữa các ca kiểm thử."""
    with _lock:
        _hits.clear()

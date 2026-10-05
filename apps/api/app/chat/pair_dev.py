"""Ghép thẳng 2 tài khoản để test chat (khi màn "Ghép bạn ở" chưa có).

Đi qua ĐÚNG đường thật: hai bên cùng 'like' ⇒ match_requests accepted + hội thoại.

    docker compose exec api python -m app.chat.pair_dev --list
    docker compose exec api python -m app.chat.pair_dev a@gmail.com han.demo@example.com
    docker compose exec api python -m app.chat.pair_dev a@gmail.com b@x.com --hello   # kèm 1 tin chào từ B

Chỉ dùng cho dev/demo — không mở thành API.
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from ..config import settings
from ..matching.repo import MatchError, MatchRepo
from .repo import ChatRepo


def _find(conn, email: str):
    return conn.execute(
        text("SELECT id, email, COALESCE(name, '') AS name FROM users WHERE lower(email) = lower(:e)"),
        {"e": email.strip()},
    ).mappings().first()


def _list(conn) -> None:
    rows = conn.execute(
        text("SELECT id, email, COALESCE(name, '') AS name FROM users ORDER BY id LIMIT 50")
    ).mappings().all()
    print("Tài khoản trong CSDL:")
    for r in rows:
        print(f"  #{r['id']:<4} {r['email']:<40} {r['name']}")


def main(argv: list[str]) -> int:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    args = [a for a in argv if not a.startswith("--")]
    with engine.connect() as conn:
        if "--list" in argv or len(args) != 2:
            if len(args) != 2 and "--list" not in argv:
                print(__doc__)
            _list(conn)
            return 0 if "--list" in argv else 1
        has_tables = conn.execute(text("SELECT to_regclass('public.conversations') IS NOT NULL")).scalar()
        if not has_tables:
            print("CSDL chưa có bảng chat — chạy migration trước:\n"
                  "  docker compose exec -T db psql -U nckh -d nckh < infra/db/migrations/92_matching_chat.sql")
            return 1
        a, b = _find(conn, args[0]), _find(conn, args[1])
        missing = [e for e, u in ((args[0], a), (args[1], b)) if u is None]
        if missing:
            print("Không tìm thấy:", ", ".join(missing))
            _list(conn)
            return 1

    repo = MatchRepo(engine)
    try:
        repo.swipe(b["id"], a["id"], "like")
        res = repo.swipe(a["id"], b["id"], "like")
    except MatchError as e:
        print("Lỗi:", e.detail)
        return 1

    conv = res["conversation_id"]
    if "--hello" in argv and res["created"]:
        ChatRepo(engine).create_message(conv, b["id"], "text", f"Chào {a['name'] or 'bạn'}! Mình test chat nhé 👋")
    state = "đã tạo hội thoại mới" if res["created"] else "hai bạn đã ghép từ trước"
    print(f"OK — {a['email']} ↔ {b['email']}: {state} (conversation #{conv}).")
    print(f"Mở: http://<máy>:3000/chat?c={conv}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

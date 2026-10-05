"""Dọn ảnh chat mồ côi.

    docker compose exec -T api python -m app.chat.media_gc [--dry-run] [--min-age-min 60]

Ảnh mồ côi sinh ra từ ba đường, không đường nào tự dọn được:
  1. process_image() ghi file TRƯỚC khi transaction lưu tin commit — tiến trình
     chết giữa chừng ⇒ file có trên đĩa, không có dòng chat_media.
  2. Xoá tài khoản: conversation_members CASCADE nhưng hội thoại còn lại với một
     người ⇒ ảnh trong đó không ai xem được nữa (is_member đòi ≥ 2 người).
  3. unmatch() xoá file SAU commit — lỗi đĩa lúc đó để lại file không có dòng.
Bước 2 xoá luôn hội thoại "một người" (tin + dòng chat_media cascade) — đúng cam
kết rút dữ liệu khi một bên rời đi.

--min-age-min: chỉ xoá file cũ hơn N phút, để không xoá ảnh của request đang
upload dở (file đã ghi, transaction chưa commit).
"""
from __future__ import annotations

import argparse
import time
import uuid

from sqlalchemy import create_engine, text

from ..config import settings
from .media import delete_files, media_root


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-age-min", type=int, default=60)
    args = ap.parse_args()

    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        lonely = list(conn.execute(text(
            "SELECT c.id FROM conversations c "
            "WHERE (SELECT count(*) FROM conversation_members m WHERE m.conversation_id = c.id) < 2"
        )).scalars())
        lonely_media = [str(x) for x in conn.execute(text(
            "SELECT id FROM chat_media WHERE conversation_id = ANY(:ids)"), {"ids": lonely}).scalars()]
        if lonely and not args.dry_run:
            conn.execute(text("DELETE FROM conversations WHERE id = ANY(:ids)"), {"ids": lonely})
        known = {str(x) for x in conn.execute(text("SELECT id FROM chat_media")).scalars()}

    cutoff = time.time() - args.min_age_min * 60
    stray: list[str] = []
    for f in media_root().glob("*.jpg"):
        try:
            mid = str(uuid.UUID(f.stem))
        except ValueError:
            continue
        if mid not in known and f.stat().st_mtime < cutoff:
            stray.append(mid)

    if not args.dry_run:
        delete_files(lonely_media)
        delete_files(stray)
        # dòng chat_media của hội thoại "một người" đã cascade ⇒ file của nó giờ cũng không có dòng
    print(f"{'[dry-run] ' if args.dry_run else ''}hội thoại một người: {len(lonely)} "
          f"(ảnh {len(lonely_media)}) · file không có dòng chat_media: {len(stray)}")


if __name__ == "__main__":
    main()

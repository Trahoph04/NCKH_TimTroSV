"""Dữ liệu demo cho chat: vài SV mô phỏng đã ghép + 1 lượt thích đang chờ.

Chạy (stack docker đang lên):
    docker compose exec api python -m app.chat.seed_demo           # tạo nếu chưa có
    docker compose exec api python -m app.chat.seed_demo --reset   # xoá demo cũ rồi tạo lại

Tất cả hồ sơ đều `is_simulated = TRUE` (UI gắn nhãn "Hồ sơ mô phỏng", loại khỏi
mọi số liệu eval — Matching_Messaging_Design.md mục 2.8). Mật khẩu chung: demo1234
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from ..auth.repo import AuthRepo
from ..auth.security import hash_password
from ..config import settings
from ..matching.repo import MatchRepo
from .repo import ChatRepo

PASSWORD = "demo1234"

# key, email, tên, giới, đơn vị, bio, sleep, clean, smoke, noise, budget
PEOPLE = [
    ("thu", "thu.demo@example.com", "Minh Thư", "nu", "Trường CNTT&TT",
     "Cần chỗ yên tĩnh để học bài, hay nấu ăn cuối tuần.", 2, 4, False, 2, 1),
    ("han", "han.demo@example.com", "Ngọc Hân", "nu", "Trường Kinh tế",
     "Đi làm thêm buổi tối, về trễ nhưng rất nhẹ nhàng.", 2, 5, False, 3, 1),
    ("tran", "tran.demo@example.com", "Bảo Trân", "nu", "Trường Nông nghiệp",
     "Dậy sớm chạy bộ, thích phòng sạch sẽ thoáng mát.", 0, 5, False, 2, 2),
    ("linh", "linh.demo@example.com", "Khánh Linh", "nu", "Trường Sư phạm",
     "Ít nói, thích nuôi cây trong phòng.", 1, 4, False, 2, 1),
    ("huy", "huy.demo@example.com", "Gia Huy", "nam", "Trường Bách khoa",
     "Hay chơi game tới khuya nhưng đeo tai nghe.", 2, 3, False, 4, 1),
    ("duc", "duc.demo@example.com", "Đức Anh", "nam", "Trường CNTT&TT",
     "Thích đá banh chiều, ngủ trước 0h.", 1, 4, False, 3, 1),
]

CONVERSATIONS = {
    ("thu", "han"): [
        ("han", "Chào Thư nha! Mình thấy hồ sơ bạn cũng học gần khu II, ngân sách gần giống mình."),
        ("thu", "Ừ đúng rồi! Mình đang để ý phòng khoảng 25 m² gần đường 3/2, chia đôi tầm 900k/người."),
        ("thu", "@listing"),
        ("han", "Nhìn ổn đó. Chiều thứ 7 đi coi phòng chung không?"),
    ],
    ("huy", "duc"): [
        ("duc", "Chào Huy, bạn tìm phòng khu nào vậy?"),
    ],
}
MATCH_ONLY = [("thu", "linh")]          # mới ghép, chưa nhắn → dải "Mới ghép"
PENDING_LIKES = [("tran", "thu")]       # Trân đã thích Thư → tab "Lời mời" của Thư
SCORES = {("thu", "han"): 0.92, ("huy", "duc"): 0.81, ("thu", "linh"): 0.77}


def main(reset: bool = False) -> None:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    auth, match, chat = AuthRepo(engine), MatchRepo(engine), ChatRepo(engine)

    if reset:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE email = ANY(:emails)"),
                {"emails": [p[1] for p in PEOPLE]},
            )
            # hội thoại mồ côi (thành viên đã bị xoá theo user) — xoá luôn tin còn lại
            conn.execute(
                text(
                    "DELETE FROM conversations c WHERE (SELECT count(*) FROM conversation_members m "
                    "WHERE m.conversation_id = c.id) < 2"
                )
            )
        print("đã xoá tài khoản demo cũ")

    ids: dict[str, int] = {}
    for key, email, name, gender, don_vi, bio, sleep, clean, smoke, noise, budget in PEOPLE:
        ident = auth.find_identity("local", email)
        if ident is None:
            uid = auth.create_user_with_identity(
                email=email, name=name, provider="local", provider_user_id=email,
                secret_hash=hash_password(PASSWORD), email_verified=True,
            )["user_id"]
        else:
            uid = ident["user_id"]
        ids[key] = uid
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO roommate_profiles (user_id, sleep_time, cleanliness, smoke, "
                    "noise_tolerance, bio, gender, don_vi, budget_band, is_simulated, src) "
                    "VALUES (:u, :sl, :cl, :sm, :no, :bio, :g, :dv, :bb, TRUE, 'seed') "
                    "ON CONFLICT (user_id) DO UPDATE SET sleep_time = EXCLUDED.sleep_time, "
                    "cleanliness = EXCLUDED.cleanliness, smoke = EXCLUDED.smoke, "
                    "noise_tolerance = EXCLUDED.noise_tolerance, bio = EXCLUDED.bio, "
                    "gender = EXCLUDED.gender, don_vi = EXCLUDED.don_vi, "
                    "budget_band = EXCLUDED.budget_band, is_simulated = TRUE, src = 'seed'"
                ),
                {"u": uid, "sl": sleep, "cl": clean, "sm": smoke, "no": noise, "bio": bio,
                 "g": gender, "dv": don_vi, "bb": budget},
            )

    with engine.connect() as conn:
        listing_id = conn.execute(
            text(
                "SELECT id FROM aggregated_listings WHERE status IS DISTINCT FROM 'hidden' "
                "ORDER BY quality_score DESC NULLS LAST, id LIMIT 1"
            )
        ).scalar()

    for (a, b), script in CONVERSATIONS.items():
        match.swipe(ids[b], ids[a], "like", score=SCORES.get((a, b)))
        res = match.swipe(ids[a], ids[b], "like", score=SCORES.get((a, b)))
        conv = res["conversation_id"]
        if not res["created"]:
            continue  # đã seed trước đó
        for who, body in script:
            if body == "@listing":
                snap = chat.listing_snapshot(listing_id) if listing_id else None
                if snap:
                    chat.create_message(conv, ids[who], "listing", None, snap)
                continue
            chat.create_message(conv, ids[who], "text", body)

    for a, b in MATCH_ONLY:
        match.swipe(ids[b], ids[a], "like", score=SCORES.get((a, b)))
        match.swipe(ids[a], ids[b], "like", score=SCORES.get((a, b)))
    for liker, target in PENDING_LIKES:
        match.swipe(ids[liker], ids[target], "like")

    print("Tài khoản demo (mật khẩu: %s):" % PASSWORD)
    for key, email, name, *_ in PEOPLE:
        print(f"  {name:<12} {email}")
    print("Gợi ý demo: đăng nhập thu.demo@example.com và han.demo@example.com ở 2 trình duyệt → /chat")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)

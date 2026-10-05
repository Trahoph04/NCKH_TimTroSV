"""Tầng DB của ghép bạn ở: hồ sơ · deck xếp hạng · swipe → match + hội thoại.

Thuật toán nằm ở các module THUẦN (không chạm DB): filters.py (lọc cứng 2 tầng),
score.py (Gower + harmonic), weights.py, stable.py. Repo chỉ nạp hồ sơ, gọi
chúng, rồi ghi kết quả. Nhờ vậy notebook eval gọi đúng hàm mà API đang dùng.

Hai bất biến của file này:
  · Mọi đường sinh match (swipe 2 chiều, lời mời được chấp nhận) đều đi qua
    `create_match()` để hội thoại luôn được tạo trong CÙNG transaction.
  · Telemetry deck (position/score/features) ĐỌC TỪ deck_log do server ghi,
    KHÔNG nhận từ body của client — xem 93_matching_deck.sql phần 1.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .filters import hard_filter_reason, passes_hard_filters
from .profile import Profile
from .score import pair_score
from .weights import DEFAULT as DEFAULT_WEIGHTS
from .weights import UNIFORM as UNIFORM_WEIGHTS

MATCH_SYSTEM_TEXT = "Hai bạn đã ghép đôi! Chào nhau một câu để bắt đầu nhé 👋"

# Thông tin T1 (ẩn danh) — KHÔNG có email/SĐT/MSSV. Dùng chung cho Lời mời + cột hồ sơ chat.
PROFILE_COLS = (
    "u.id AS user_id, COALESCE(NULLIF(u.name, ''), 'Sinh viên CTU') AS name, u.avatar_url, "
    "u.email_verified, rp.gender, rp.don_vi, rp.bio, rp.sleep_time, rp.wake_time, "
    "rp.cleanliness, rp.smoke, rp.smoke_in_room, rp.noise_tolerance, rp.budget_band, "
    "COALESCE(rp.is_simulated, FALSE) AS is_simulated"
)


# Toàn bộ cột thuật toán cần. KHÁC `PROFILE_COLS` ở trên: cái đó là T1 (ẩn danh)
# cho chat, cái này cho tính điểm — không bao giờ trả thẳng ra API.
_ALGO_COLS = (
    "rp.user_id, rp.gender, rp.don_vi, rp.budget_band, rp.scenario, rp.sleep_time, "
    "rp.wake_time, rp.cleanliness, rp.noise_tolerance, rp.ac_usage, rp.money_style, "
    "rp.share_stuff, rp.smoke, rp.smoke_in_room, rp.hanh_vi, rp.deal_breakers, "
    "rp.persona, rp.bio, COALESCE(rp.is_simulated, FALSE) AS is_simulated"
)

# Cột người dùng tự khai được qua POST /matching/profile. `is_simulated` và `src`
# KHÔNG nằm đây: client không được tự nhận mình là hồ sơ mô phỏng.
PROFILE_WRITABLE = (
    "gender", "don_vi", "budget_band", "scenario", "sleep_time", "wake_time",
    "cleanliness", "noise_tolerance", "ac_usage", "money_style", "share_stuff",
    "smoke", "smoke_in_room", "hanh_vi", "deal_breakers", "persona", "bio",
    "need_from", "roommate_status",
)

WEIGHT_SETS = {"survey": DEFAULT_WEIGHTS, "uniform": UNIFORM_WEIGHTS}

# 'pass' không vĩnh viễn: ở pool nhỏ xoá vĩnh viễn là đốt pool (doc 3.5 mục 2).
PASS_COOLDOWN_DAYS = 7


class MatchError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def create_match(
    conn: Connection,
    a: int,
    b: int,
    *,
    score: float | None = None,
) -> tuple[int, int, bool]:
    """Ghi nhận a–b đã ghép. Trả (match_id, conversation_id, created_new).

    Idempotent: gọi lại khi đã có hội thoại thì trả hội thoại cũ. Phải chạy trong
    transaction của caller (đã giữ advisory lock của cặp).
    """
    mr = conn.execute(
        text(
            "SELECT id FROM match_requests "
            "WHERE (from_user = :a AND to_user = :b) OR (from_user = :b AND to_user = :a) "
            "ORDER BY id LIMIT 1 FOR UPDATE"
        ),
        {"a": a, "b": b},
    ).scalar()
    if mr is None:
        # b thích trước → from_user=b (người khởi xướng), to_user=a (người đáp lại)
        mr = conn.execute(
            text(
                "INSERT INTO match_requests (from_user, to_user, score, status, responded_at) "
                "VALUES (:b, :a, :score, 'accepted', now()) RETURNING id"
            ),
            {"a": a, "b": b, "score": score},
        ).scalar_one()
    else:
        conn.execute(
            text(
                "UPDATE match_requests SET status = 'accepted', responded_at = now(), "
                "score = COALESCE(:score, score) WHERE id = :id"
            ),
            {"id": mr, "score": score},
        )

    conv = conn.execute(
        text("SELECT id FROM conversations WHERE match_id = :m"), {"m": mr}
    ).scalar()
    if conv is not None:
        return mr, conv, False

    conv = conn.execute(
        text("INSERT INTO conversations (kind, match_id) VALUES ('pair', :m) RETURNING id"),
        {"m": mr},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO conversation_members (conversation_id, user_id) "
            "VALUES (:c, :a), (:c, :b)"
        ),
        {"c": conv, "a": a, "b": b},
    )
    conn.execute(
        text(
            "INSERT INTO messages (conversation_id, sender_id, kind, body) "
            "VALUES (:c, NULL, 'system', :body)"
        ),
        {"c": conv, "body": MATCH_SYSTEM_TEXT},
    )
    return mr, conv, True


def lock_pair(conn: Connection, a: int, b: int) -> None:
    """Khoá theo cặp (không phụ thuộc thứ tự) — 2 người bấm thích cùng lúc vẫn ra đúng 1 match."""
    lo, hi = sorted((a, b))
    conn.execute(text("SELECT pg_advisory_xact_lock(CAST(:lo AS INTEGER), CAST(:hi AS INTEGER))"), {"lo": lo, "hi": hi})


class MatchRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    def swipe(
        self,
        user_id: int,
        target_id: int,
        decision: str,
    ) -> dict:
        """Thích / bỏ qua. Hai 'like' đối nhau ⇒ match + hội thoại cùng transaction.

        KHÔNG nhận deck_position/deck_mode/score từ caller nữa. Bản trước lấy
        chúng từ body do FE gửi — chính dữ liệu dùng để chứng minh đã khử thiên
        lệch vị trí (doc 3.6), nên để client tự khai thì bằng chứng vô giá trị.
        Giờ đọc từ `deck_log` do GET /matching/deck ghi.

        Lọc cứng được kiểm LẠI ở đây, không chỉ ở deck: deck là gợi ý, swipe là
        hành động ghi. Bản trước chỉ kiểm "user tồn tại" ⇒ bất kỳ client đã đăng
        nhập nào cũng ghép được KHÁC GIỚI bằng cách POST thẳng target_id — phá
        đúng cam kết "chỉ ghép cùng giới" đã hứa trong form khảo sát.
        """
        if user_id == target_id:
            raise MatchError(400, "Không thể tự ghép với chính mình")

        with self.engine.begin() as conn:
            # Tách "user không tồn tại" (404) khỏi "user chưa có hồ sơ ghép" (409):
            # gộp hai cái thành 404 vừa sai nghĩa vừa khiến FE không biết nên hiện
            # "không tìm thấy" hay "mời bạn ấy điền hồ sơ".
            if conn.execute(
                text("SELECT 1 FROM users WHERE id = :id"), {"id": target_id}
            ).first() is None:
                raise MatchError(404, "Không tìm thấy người dùng")

            me = self._load_profile(conn, user_id)
            if me is None:
                raise MatchError(409, "Bạn chưa có hồ sơ ở ghép — hãy điền hồ sơ trước")
            other = self._load_profile(conn, target_id)
            if other is None:
                raise MatchError(409, "Bạn ấy chưa có hồ sơ ở ghép")

            why = hard_filter_reason(me, other)
            if why is not None:
                raise MatchError(409, _reject_message(why))

            # Telemetry do SERVER ghi lúc phục vụ deck; không có thì để NULL
            # (swipe từ tab "Lời mời" không đi qua deck — đó là trường hợp hợp lệ).
            tel = conn.execute(
                text(
                    "SELECT position, score, features, deck_mode FROM deck_log "
                    "WHERE user_id = :u AND target_id = :t "
                    "ORDER BY served_at DESC LIMIT 1"
                ),
                {"u": user_id, "t": target_id},
            ).mappings().first()

            lock_pair(conn, user_id, target_id)
            conn.execute(
                text(
                    "INSERT INTO swipes (user_id, target_id, decision, score_at_swipe, "
                    "features, deck_position, deck_mode) "
                    "VALUES (:u, :t, :d, :score, CAST(:features AS JSONB), :pos, :mode) "
                    "ON CONFLICT (user_id, target_id) DO UPDATE SET "
                    "decision = EXCLUDED.decision, updated_at = now(), "
                    "score_at_swipe = COALESCE(EXCLUDED.score_at_swipe, swipes.score_at_swipe), "
                    "features = COALESCE(EXCLUDED.features, swipes.features), "
                    # Đổi ý phải cập nhật CẢ telemetry: bản trước giữ nguyên
                    # position/mode của lần swipe đầu ⇒ dữ liệu khử thiên lệch
                    # vị trí lệch âm thầm.
                    "deck_position = COALESCE(EXCLUDED.deck_position, swipes.deck_position), "
                    "deck_mode = COALESCE(EXCLUDED.deck_mode, swipes.deck_mode)"
                ),
                {
                    "u": user_id, "t": target_id, "d": decision,
                    "score": tel["score"] if tel else None,
                    "features": _json(tel["features"]) if tel and tel["features"] else None,
                    "pos": tel["position"] if tel else None,
                    "mode": tel["deck_mode"] if tel else None,
                },
            )
            if decision != "like":
                return {"matched": False, "conversation_id": None, "created": False}

            liked_back = conn.execute(
                text(
                    "SELECT 1 FROM swipes WHERE user_id = :t AND target_id = :u "
                    "AND decision = 'like'"
                ),
                {"u": user_id, "t": target_id},
            ).first()
            if not liked_back:
                return {"matched": False, "conversation_id": None, "created": False}

            score = tel["score"] if tel else pair_score(me, other, DEFAULT_WEIGHTS).score
            _, conv_id, created = create_match(conn, user_id, target_id, score=score)
        return {"matched": True, "conversation_id": conv_id, "created": created}

    # ── Hồ sơ ─────────────────────────────────────────────────────────────────

    def _load_profile(self, conn: Connection, user_id: int) -> Profile | None:
        row = conn.execute(
            text(f"SELECT {_ALGO_COLS} FROM roommate_profiles rp WHERE rp.user_id = :u"),
            {"u": user_id},
        ).mappings().first()
        return None if row is None else Profile.from_row(row)

    def get_profile(self, user_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT user_id, gender, don_vi, budget_band, scenario, sleep_time, "
                    "wake_time, cleanliness, noise_tolerance, ac_usage, money_style, "
                    "share_stuff, smoke, smoke_in_room, hanh_vi, deal_breakers, persona, "
                    "bio, need_from, roommate_status, "
                    "COALESCE(is_simulated, FALSE) AS is_simulated, src, updated_at "
                    "FROM roommate_profiles WHERE user_id = :u"
                ),
                {"u": user_id},
            ).mappings().first()
        return dict(row) if row else None

    def upsert_profile(self, user_id: int, fields: dict) -> dict:
        """Ghi hồ sơ 12 câu. Chỉ nhận cột trong PROFILE_WRITABLE.

        src='app' để phân biệt với 'form' (nhập từ khảo sát) và 'seed' — notebook
        eval cần lọc theo nguồn, và `is_simulated` phải do server quyết.
        """
        data = {k: v for k, v in fields.items() if k in PROFILE_WRITABLE}
        if not data:
            raise MatchError(400, "Không có trường hợp lệ nào để lưu")

        cols = sorted(data)
        insert_cols = ", ".join(["user_id", *cols, "src", "updated_at"])
        insert_vals = ", ".join([":user_id", *(f":{c}" for c in cols), "'app'", "now()"])
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"INSERT INTO roommate_profiles ({insert_cols}) VALUES ({insert_vals}) "
                    f"ON CONFLICT (user_id) DO UPDATE SET {updates}, src = 'app', updated_at = now()"
                ),
                {"user_id": user_id, **data},
            )
        return self.get_profile(user_id) or {}

    # ── Deck ──────────────────────────────────────────────────────────────────

    def _pool(self, conn: Connection, me: Profile) -> list[Profile]:
        """Hồ sơ cùng giới, có tài khoản thật, chưa bị mình quyết định gần đây.

        'pass' chỉ bị loại trong PASS_COOLDOWN_DAYS ngày; 'like' thì loại hẳn
        (đã quyết rồi, không hỏi lại). Người đã match cũng loại.
        """
        rows = conn.execute(
            text(
                f"SELECT {_ALGO_COLS} FROM roommate_profiles rp "
                "JOIN users u ON u.id = rp.user_id "
                "WHERE rp.user_id <> :me AND rp.gender = :g "
                "  AND NOT EXISTS (SELECT 1 FROM swipes s WHERE s.user_id = :me "
                "                  AND s.target_id = rp.user_id "
                "                  AND (s.decision = 'like' "
                f"                       OR s.updated_at > now() - INTERVAL '{PASS_COOLDOWN_DAYS} days')) "
                "  AND NOT EXISTS (SELECT 1 FROM match_requests mr "
                "                  WHERE mr.status = 'accepted' "
                "                    AND ((mr.from_user = :me AND mr.to_user = rp.user_id) "
                "                      OR (mr.to_user = :me AND mr.from_user = rp.user_id)))"
            ),
            {"me": me.user_id, "g": me.gender},
        ).mappings().all()
        return [Profile.from_row(r) for r in rows]

    def _exposure(self, conn: Connection, ids: list[int]) -> dict[int, int]:
        """Số lần mỗi hồ sơ đã được đưa vào deck của người khác (đo congestion).

        Dùng để HẠ ƯU TIÊN hồ sơ đã bị hiển thị quá nhiều. Ở pool nhỏ, vài hồ sơ
        "trung tính mọi chiều" xuất hiện trong deck của tất cả mọi người và hứng
        hết lời mời, số còn lại không nhận được gì — đúng hiện tượng congestion
        trong Fair Reciprocal Recommendation (RecSys 2024).
        """
        if not ids:
            return {}
        rows = conn.execute(
            text(
                "SELECT target_id, count(DISTINCT user_id) AS n FROM deck_log "
                "WHERE target_id = ANY(:ids) GROUP BY target_id"
            ),
            {"ids": ids},
        ).mappings().all()
        return {r["target_id"]: int(r["n"]) for r in rows}

    def deck(
        self,
        user_id: int,
        *,
        limit: int = 10,
        mode: str = "ranked",
        weights_ver: str = "survey",
        exposure_penalty: float = 0.02,
    ) -> dict:
        """Bộ thẻ hôm nay: lọc cứng → điểm hai chiều → xếp hạng → GHI deck_log.

        mode='random' dùng cho buổi thử nghiệm: xáo thứ tự tất định (theo
        user_id, KHÔNG dùng random thật để chạy lại ra đúng thứ tự cũ), và FE
        phải ẩn %/lý do. Nếu deck xếp theo điểm thì thẻ đầu được like nhiều hơn
        VÌ NÓ Ở ĐẦU ⇒ mô hình học chính thiên lệch vị trí đó (doc 3.6).
        """
        weights = WEIGHT_SETS.get(weights_ver, DEFAULT_WEIGHTS)
        with self.engine.begin() as conn:
            me = self._load_profile(conn, user_id)
            if me is None:
                return {"items": [], "reason": "no_profile", "pool_total": 0}
            if not me.in_pool:
                return {"items": [], "reason": "profile_incomplete", "pool_total": 0}

            pool = self._pool(conn, me)
            # Lọc reciprocal: không đưa thẻ của B cho A nếu B sẽ loại cứng A.
            # Ở pool ~5 thẻ, tiết kiệm swipe vô ích là sống còn (doc 3.5 mục 4).
            eligible = [p for p in pool if passes_hard_filters(me, p)]

            scored = []
            for p in eligible:
                ps = pair_score(me, p, weights)
                scored.append((ps, p))

            if mode == "random":
                scored.sort(key=lambda t: (t[1].user_id * 2654435761) % 1000003)
            else:
                expo = self._exposure(conn, [p.user_id for _, p in scored])
                scored.sort(
                    key=lambda t: (
                        -(t[0].score - exposure_penalty * expo.get(t[1].user_id, 0)),
                        t[1].user_id,
                    )
                )

            picked = scored[:limit]
            items = []
            for pos, (ps, p) in enumerate(picked):
                conn.execute(
                    text(
                        "INSERT INTO deck_log (user_id, target_id, position, score, s_ab, "
                        "s_ba, features, deck_mode, weights_ver) VALUES "
                        "(:u, :t, :pos, :sc, :sab, :sba, CAST(:f AS JSONB), :mode, :wv)"
                    ),
                    {
                        "u": user_id, "t": p.user_id, "pos": pos, "sc": ps.score,
                        "sab": ps.s_ab, "sba": ps.s_ba, "f": _json(ps.breakdown),
                        "mode": mode, "wv": weights_ver,
                    },
                )
                items.append({
                    "user_id": p.user_id,
                    "position": pos,
                    # mode='random': ẩn mọi tín hiệu của thuật toán để không dẫn dắt
                    # người chấm trong buổi thử nghiệm.
                    "score": None if mode == "random" else ps.score,
                    "reasons": [] if mode == "random" else ps.reasons,
                    "caveat": None if mode == "random" else ps.caveat,
                    "soft_flags": [] if mode == "random" else ps.soft_flags,
                    "is_simulated": p.is_simulated,
                })

            profiles = self._deck_profiles(conn, [i["user_id"] for i in items])

        for it in items:
            it["profile"] = profiles.get(it["user_id"])
        return {
            "items": items,
            "reason": None if items else ("pool_empty" if not eligible else "deck_done"),
            "pool_total": len(eligible),
            "deck_mode": mode,
            "weights_ver": weights_ver,
        }

    def _deck_profiles(self, conn: Connection, ids: list[int]) -> dict[int, dict]:
        """Thông tin T1 (ẩn danh) để render thẻ — KHÔNG email/SĐT/MSSV."""
        if not ids:
            return {}
        rows = conn.execute(
            text(
                f"SELECT {PROFILE_COLS}, rp.scenario, rp.ac_usage, rp.money_style, "
                "rp.hanh_vi, rp.persona "
                "FROM users u LEFT JOIN roommate_profiles rp ON rp.user_id = u.id "
                "WHERE u.id = ANY(:ids)"
            ),
            {"ids": ids},
        ).mappings().all()
        return {r["user_id"]: dict(r) for r in rows}

    def likes_received(self, user_id: int, *, limit: int = 50) -> list[dict]:
        """Tab "Lời mời": những người đã thích mình mà mình CHƯA quyết định.

        Có LIMIT: bản trước không giới hạn, pool lớn dần là trả cả bảng về FE.
        """
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {PROFILE_COLS}, s.created_at AS liked_at "
                    "FROM swipes s JOIN users u ON u.id = s.user_id "
                    "LEFT JOIN roommate_profiles rp ON rp.user_id = s.user_id "
                    "WHERE s.target_id = :u AND s.decision = 'like' "
                    "AND NOT EXISTS (SELECT 1 FROM swipes s2 "
                    "                WHERE s2.user_id = :u AND s2.target_id = s.user_id) "
                    "ORDER BY s.created_at DESC LIMIT :lim"
                ),
                {"u": user_id, "lim": limit},
            ).mappings().all()
        return [dict(r) for r in rows]

    def passed(self, user_id: int, *, limit: int = 50) -> list[dict]:
        """Thẻ mình đã bỏ qua — để có nút "Xem lại thẻ đã bỏ qua"."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT {PROFILE_COLS}, s.updated_at AS passed_at "
                    "FROM swipes s JOIN users u ON u.id = s.target_id "
                    "LEFT JOIN roommate_profiles rp ON rp.user_id = s.target_id "
                    "WHERE s.user_id = :u AND s.decision = 'pass' "
                    "ORDER BY s.updated_at DESC LIMIT :lim"
                ),
                {"u": user_id, "lim": limit},
            ).mappings().all()
        return [dict(r) for r in rows]

    def count_likes_received(self, user_id: int) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT count(*) FROM swipes s WHERE s.target_id = :u AND s.decision = 'like' "
                    "AND NOT EXISTS (SELECT 1 FROM swipes s2 "
                    "                WHERE s2.user_id = :u AND s2.target_id = s.user_id)"
                ),
                {"u": user_id},
            ).scalar_one()


_REJECT_MESSAGES = {
    "gender_mismatch": "Hệ thống chỉ ghép bạn ở cùng giới tính",
    "a_not_in_pool": "Hồ sơ của bạn chưa đủ để ghép — hãy khai giới tính và phần lối sống",
    "b_not_in_pool": "Hồ sơ của bạn ấy chưa đủ để ghép",
    "budget_gap": "Ngân sách hai bạn lệch quá xa",
    "scenario_alone": "Một trong hai bạn đã khai muốn ở một mình",
    "self": "Không thể tự ghép với chính mình",
}


def _reject_message(why: str) -> str:
    """Thông điệp cho người dùng, KHÔNG tiết lộ deal-breaker cụ thể của người kia.

    Nói "bạn ấy hút thuốc trong phòng" là lộ hồ sơ của người thứ ba cho người
    không được xem — vi phạm tầng T1 (chỉ tên + tóm tắt lối sống).
    """
    if why.startswith("hard_db_a:"):
        return "Bạn ấy có điều bạn đã khai là không chấp nhận được"
    if why.startswith("hard_db_b:"):
        return "Hồ sơ của bạn có điều bạn ấy đã khai là không chấp nhận được"
    return _REJECT_MESSAGES.get(why, "Cặp này không đi qua được bộ lọc an toàn")


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)

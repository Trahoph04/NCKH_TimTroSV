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

import random
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .filters import hard_filter_reason, only_feasibility_gap, passes_hard_filters
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
    "rp.persona, rp.bio, rp.need_from, COALESCE(rp.is_simulated, FALSE) AS is_simulated"
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

# ε-greedy (doc 3.4 [R3]): 20% số thẻ của deck 'ranked' lấy NGOÀI top theo điểm.
# Luôn xếp theo điểm thì mô hình chỉ thấy phản hồi trên vùng nó đã tin ⇒ không
# bao giờ biết mình sai (vòng phản hồi).
EPSILON = 0.2

# Thẻ mô phỏng không bao giờ quẹt lại ⇒ deck toàn thẻ mô phỏng thì buổi thử
# nghiệm không sinh nổi một match thật. Hồ sơ thật được chọn TRƯỚC, thẻ mô phỏng
# chỉ lấp phần còn trống và không quá số thẻ thật (≤ 50% deck). Sàn MIN_SIM_SLOTS
# để người có rất ít/không có hồ sơ thật cùng giới vẫn thấy deck thay vì màn trống.
MIN_SIM_SLOTS = 2

# Deck buổi thử nghiệm (mode='random'): ~20% thẻ là ứng viên chỉ lệch tiêu chí
# KHẢ THI (ngân sách, thời điểm) để mô hình có mẫu d_k lớn (doc 3.6). Không bao
# giờ nới lọc an toàn (giới tính, deal-breaker cứng).
SPREAD_SHARE = 0.2

# decided_ms lớn hơn mức này coi như người dùng bỏ đi rồi quay lại — không phải
# "thời gian cân nhắc", ghi NULL thay vì làm lệch phân phối.
DECIDED_MS_MAX = 10 * 60 * 1000


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

    Chỉ dùng lại dòng ĐANG HIỆU LỰC (pending = lời mời chờ, accepted = đang
    ghép). Dòng 'unmatched'/'rejected' của lần trước giữ nguyên làm vết thống kê;
    ghép lại thì sinh dòng mới (94_matching_eval.sql bỏ UNIQUE cũ để cho phép).
    """
    mr = conn.execute(
        text(
            "SELECT id FROM match_requests "
            "WHERE ((from_user = :a AND to_user = :b) OR (from_user = :b AND to_user = :a)) "
            "  AND status IN ('pending', 'accepted') "
            "ORDER BY id DESC LIMIT 1 FOR UPDATE"
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
                "UPDATE match_requests SET status = 'accepted', "
                "responded_at = COALESCE(responded_at, now()), "
                "score = COALESCE(:score, score) WHERE id = :id AND status = 'pending'"
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


def active_conversation(conn: Connection, a: int, b: int) -> int | None:
    """Hội thoại của cặp đang ghép (accepted), nếu có."""
    return conn.execute(
        text(
            "SELECT c.id FROM match_requests mr JOIN conversations c ON c.match_id = mr.id "
            "WHERE mr.status = 'accepted' "
            "  AND ((mr.from_user = :a AND mr.to_user = :b) OR (mr.from_user = :b AND mr.to_user = :a)) "
            "ORDER BY mr.id DESC LIMIT 1"
        ),
        {"a": a, "b": b},
    ).scalar()


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

        Trả thêm `unmatch_conversation_id` khi 'pass' một người ĐANG ghép: router
        gọi ChatRepo.unmatch() để xoá hội thoại. Bản trước đổi swipe thành pass
        nhưng để hội thoại nằm lại ⇒ "đã bỏ qua" mà vẫn nhắn tin được với nhau.
        """
        with self.engine.begin() as conn:
            res = self._swipe_tx(conn, user_id, target_id, decision)
        return res

    def _swipe_tx(self, conn: Connection, user_id: int, target_id: int, decision: str) -> dict:
        """Thân của swipe, chạy trong transaction của caller (invite dùng lại).

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

        # Telemetry do SERVER ghi lúc phục vụ deck; không có thì để NULL
        # (swipe từ tab "Lời mời" không đi qua deck — đó là trường hợp hợp lệ).
        # decided_ms tính ở đây (thời điểm swipe − lúc thẻ được phục vụ), không
        # nhận từ client vì client sửa được.
        tel = conn.execute(
            text(
                "SELECT position, score, features, deck_mode, explore, "
                "CAST(EXTRACT(EPOCH FROM (now() - served_at)) * 1000 AS BIGINT) AS elapsed_ms "
                "FROM deck_log WHERE user_id = :u AND target_id = :t "
                "ORDER BY served_at DESC LIMIT 1"
            ),
            {"u": user_id, "t": target_id},
        ).mappings().first()

        liked_me = conn.execute(
            text(
                "SELECT 1 FROM swipes WHERE user_id = :t AND target_id = :u "
                "AND decision = 'like'"
            ),
            {"u": user_id, "t": target_id},
        ).first() is not None

        why = hard_filter_reason(me, other)
        if why is not None and decision == "like":
            # Lệch KHẢ THI (ngân sách/thời điểm) được nới khi thẻ đến từ deck độ
            # tản của buổi thử nghiệm, hoặc khi người kia đã thích mình trước
            # (họ đã tự chấp nhận độ lệch — không cho đáp lại thì "Lời mời" thành
            # lời mời không bấm nhận được). Lý do AN TOÀN thì không bao giờ nới.
            relaxed = only_feasibility_gap(me, other) and (
                (tel is not None and tel["explore"] == "spread") or liked_me
            )
            if not relaxed:
                raise MatchError(409, _reject_message(why))

        decided_ms = None
        if tel is not None and tel["elapsed_ms"] is not None and 0 <= tel["elapsed_ms"] <= DECIDED_MS_MAX:
            decided_ms = int(tel["elapsed_ms"])

        lock_pair(conn, user_id, target_id)
        conn.execute(
            text(
                "INSERT INTO swipes (user_id, target_id, decision, score_at_swipe, "
                "features, deck_position, deck_mode, decided_ms) "
                "VALUES (:u, :t, :d, :score, CAST(:features AS JSONB), :pos, :mode, :ms) "
                "ON CONFLICT (user_id, target_id) DO UPDATE SET "
                "decision = EXCLUDED.decision, updated_at = now(), "
                "score_at_swipe = COALESCE(EXCLUDED.score_at_swipe, swipes.score_at_swipe), "
                "features = COALESCE(EXCLUDED.features, swipes.features), "
                # Đổi ý phải cập nhật CẢ telemetry: bản trước giữ nguyên
                # position/mode của lần swipe đầu ⇒ dữ liệu khử thiên lệch
                # vị trí lệch âm thầm.
                "deck_position = COALESCE(EXCLUDED.deck_position, swipes.deck_position), "
                "deck_mode = COALESCE(EXCLUDED.deck_mode, swipes.deck_mode), "
                "decided_ms = COALESCE(EXCLUDED.decided_ms, swipes.decided_ms)"
            ),
            {
                "u": user_id, "t": target_id, "d": decision,
                "score": tel["score"] if tel else None,
                "features": _json(tel["features"]) if tel and tel["features"] else None,
                "pos": tel["position"] if tel else None,
                "mode": tel["deck_mode"] if tel else None,
                "ms": decided_ms,
            },
        )
        if decision != "like":
            # Lời mời đang chờ giữa hai người không được treo lại: bỏ qua người
            # đã mời mình = từ chối; bỏ qua người mình đã mời = rút lời mời.
            conn.execute(
                text(
                    "UPDATE match_requests SET responded_at = now(), "
                    "status = CASE WHEN from_user = :t THEN 'rejected' ELSE 'withdrawn' END "
                    "WHERE ((from_user = :t AND to_user = :u) OR (from_user = :u AND to_user = :t)) "
                    "  AND status = 'pending'"
                ),
                {"u": user_id, "t": target_id},
            )
            return {
                "matched": False, "conversation_id": None, "created": False,
                "unmatch_conversation_id": active_conversation(conn, user_id, target_id),
            }

        if not liked_me:
            return {"matched": False, "conversation_id": None, "created": False,
                    "unmatch_conversation_id": None}

        score = tel["score"] if tel else pair_score(me, other, DEFAULT_WEIGHTS).score
        _, conv_id, created = create_match(conn, user_id, target_id, score=score)
        return {"matched": True, "conversation_id": conv_id, "created": created,
                "unmatch_conversation_id": None}

    # ── Lời mời kèm lời nhắn (doc 2.10, 3.5 ý 3) ─────────────────────────────

    def invite(self, user_id: int, target_id: int, note: str | None) -> dict:
        """Gửi lời mời = 'like' + một match_requests 'pending' mang lời nhắn.

        Đi song song với swipe chứ không thay: match 2 chiều nhân đôi tỉ lệ rụng,
        lời mời cho người kia một lý do cụ thể để đáp lại. Vì lời mời CŨNG là một
        'like', người kia quẹt thích trong deck vẫn ra match như thường.
        """
        note = (note or "").strip() or None
        with self.engine.begin() as conn:
            res = self._swipe_tx(conn, user_id, target_id, "like")
            if res["matched"]:
                if note:
                    conn.execute(
                        text(
                            "UPDATE match_requests SET note = COALESCE(note, :n) "
                            "WHERE id = (SELECT match_id FROM conversations WHERE id = :c)"
                        ),
                        {"n": note, "c": res["conversation_id"]},
                    )
                return {**res, "invite_id": None}

            score = conn.execute(
                text("SELECT score_at_swipe FROM swipes WHERE user_id = :u AND target_id = :t"),
                {"u": user_id, "t": target_id},
            ).scalar()
            inv = conn.execute(
                text(
                    "UPDATE match_requests SET note = :n, created_at = now() "
                    "WHERE from_user = :u AND to_user = :t AND status = 'pending' RETURNING id"
                ),
                {"u": user_id, "t": target_id, "n": note},
            ).scalar()
            if inv is None:
                inv = conn.execute(
                    text(
                        "INSERT INTO match_requests (from_user, to_user, score, status, note) "
                        "VALUES (:u, :t, :s, 'pending', :n) RETURNING id"
                    ),
                    {"u": user_id, "t": target_id, "s": score, "n": note},
                ).scalar_one()
        return {**res, "invite_id": inv}

    def respond_invite(self, user_id: int, invite_id: int, accept: bool) -> dict:
        """Nhận / từ chối lời mời. Đi qua _swipe_tx để mọi kiểm lọc cứng + telemetry
        giống hệt swipe — nhận lời mời KHÔNG phải cửa sau vượt lọc an toàn."""
        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT from_user, to_user, status FROM match_requests "
                    "WHERE id = :id FOR UPDATE"
                ),
                {"id": invite_id},
            ).mappings().first()
            # 404 cả khi lời mời là của người khác: không lộ id nào tồn tại
            if row is None or row["to_user"] != user_id:
                raise MatchError(404, "Không tìm thấy lời mời")
            if row["status"] != "pending":
                raise MatchError(409, "Lời mời này đã được xử lý")
            res = self._swipe_tx(conn, user_id, row["from_user"], "like" if accept else "pass")
        return {**res, "from_user": row["from_user"]}

    def invites(self, user_id: int, *, limit: int = 50) -> dict:
        """Lời mời đang chờ: nhận được + đã gửi."""
        q = (
            f"SELECT mr.id AS invite_id, mr.note, mr.created_at AS invited_at, {PROFILE_COLS} "
            "FROM match_requests mr JOIN users u ON u.id = mr.{other} "
            "LEFT JOIN roommate_profiles rp ON rp.user_id = u.id "
            "WHERE mr.{me} = :u AND mr.status = 'pending' "
            "ORDER BY mr.created_at DESC LIMIT :lim"
        )
        with self.engine.connect() as conn:
            received = conn.execute(
                text(q.format(other="from_user", me="to_user")), {"u": user_id, "lim": limit}
            ).mappings().all()
            sent = conn.execute(
                text(q.format(other="to_user", me="from_user")), {"u": user_id, "lim": limit}
            ).mappings().all()
        return {"received": [dict(r) for r in received], "sent": [dict(r) for r in sent]}

    # ── Chấm điểm làm mù 1–5 (doc 2.7) ───────────────────────────────────────

    def rating_cards(self, user_id: int, *, round_no: int = 1) -> dict:
        """5 thẻ chấm điểm: top-3 của thuật toán + 2 ngẫu nhiên trong pool, xáo trộn.

        Sinh MỘT LẦN mỗi (người, vòng) rồi đọc lại — F5 không được đổi bộ thẻ,
        nếu không người chấm thấy thẻ mới và nhóm 'random' không còn ngẫu nhiên
        theo thiết kế. Không trả arm/score ra ngoài: người chấm biết thẻ nào của
        thuật toán thì phép so Wilcoxon vô nghĩa.

        Pool chấm điểm KHÔNG trừ người đã quẹt (khác deck): đây là phép đo độc
        lập, không phải gợi ý. Top-3 dùng điểm thuần (không trừ exposure, không
        ε) — đúng thứ thuật toán tin là tốt nhất.
        """
        with self.engine.begin() as conn:
            rows = self._rating_rows(conn, user_id, round_no)
            if not rows:
                me = self._load_profile(conn, user_id)
                if me is None:
                    return {"items": [], "reason": "no_profile", "round": round_no}
                if not me.in_pool:
                    return {"items": [], "reason": "profile_incomplete", "round": round_no}
                others = conn.execute(
                    text(
                        f"SELECT {_ALGO_COLS} FROM roommate_profiles rp "
                        "JOIN users u ON u.id = rp.user_id "
                        "WHERE rp.user_id <> :me AND rp.gender = :g"
                    ),
                    {"me": user_id, "g": me.gender},
                ).mappings().all()
                eligible = [p for p in (Profile.from_row(r) for r in others)
                            if passes_hard_filters(me, p)]
                if not eligible:
                    return {"items": [], "reason": "pool_empty", "round": round_no}

                scored = sorted(((pair_score(me, p, DEFAULT_WEIGHTS), p) for p in eligible),
                                key=lambda t: (-t[0].score, t[1].user_id))
                rng = random.Random(f"rate:{user_id}:{round_no}")
                algo = scored[:RATING_ALGO_K]
                rest = scored[RATING_ALGO_K:]
                rand = rng.sample(rest, min(RATING_RANDOM_K, len(rest)))
                cards = [("algo", i + 1, t) for i, t in enumerate(algo)] + \
                        [("random", None, t) for t in rand]
                rng.shuffle(cards)
                codes = _card_codes(rng, len(cards))
                for pos, ((arm, rank, (ps, p)), code) in enumerate(zip(cards, codes)):
                    conn.execute(
                        text(
                            "INSERT INTO roommate_ratings (rater_id, target_id, round, card_code, "
                            "arm, algo_rank, display_pos, score, s_ab, s_ba, weights_ver, "
                            "target_is_simulated) VALUES (:r, :t, :rd, :code, :arm, :rank, :pos, "
                            ":sc, :sab, :sba, 'survey', :sim) "
                            "ON CONFLICT DO NOTHING"
                        ),
                        {"r": user_id, "t": p.user_id, "rd": round_no, "code": code,
                         "arm": arm, "rank": rank, "pos": pos, "sc": ps.score,
                         "sab": ps.s_ab, "sba": ps.s_ba, "sim": p.is_simulated},
                    )
                rows = self._rating_rows(conn, user_id, round_no)
            profiles = self._deck_profiles(conn, [r["target_id"] for r in rows])
        items = [{
            "card_code": r["card_code"],
            "position": r["display_pos"],
            "rating": r["rating"],
            "is_simulated": r["target_is_simulated"],
            "profile": profiles.get(r["target_id"]),
        } for r in rows]
        return {"items": items, "reason": None, "round": round_no,
                "done": all(i["rating"] is not None for i in items)}

    def _rating_rows(self, conn: Connection, user_id: int, round_no: int) -> list:
        return conn.execute(
            text(
                "SELECT target_id, card_code, display_pos, rating, target_is_simulated "
                "FROM roommate_ratings WHERE rater_id = :u AND round = :rd ORDER BY display_pos"
            ),
            {"u": user_id, "rd": round_no},
        ).mappings().all()

    def rate(self, user_id: int, card_code: str, rating: int, *, round_no: int = 1) -> None:
        with self.engine.begin() as conn:
            n = conn.execute(
                text(
                    "UPDATE roommate_ratings SET rating = :v, rated_at = now() "
                    "WHERE rater_id = :u AND round = :rd AND card_code = :c"
                ),
                {"u": user_id, "rd": round_no, "c": card_code.upper(), "v": rating},
            ).rowcount
        if n == 0:
            raise MatchError(404, "Không tìm thấy thẻ chấm điểm")

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
        """Bộ thẻ hôm nay: lọc cứng → điểm hai chiều → chọn thẻ → xếp → GHI deck_log.

        Chọn thẻ (cả hai mode): hồ sơ thật trước, thẻ mô phỏng ≤ số thẻ thật
        (xem MIN_SIM_SLOTS). 'ranked' thêm ε-greedy; 'random' thêm thẻ độ tản.

        mode='random' dùng cho buổi thử nghiệm: xáo thứ tự tất định theo người
        xem (chạy lại ra đúng thứ tự cũ), và FE phải ẩn %/lý do. Nếu deck xếp
        theo điểm thì thẻ đầu được like nhiều hơn VÌ NÓ Ở ĐẦU ⇒ mô hình học
        chính thiên lệch vị trí đó (doc 3.6).
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

            expo = self._exposure(conn, [p.user_id for p in eligible])
            scored = [(pair_score(me, p, weights), p) for p in eligible]
            # Thứ hạng theo điểm (trừ exposure) dùng cho CẢ HAI mode khi CHỌN thẻ;
            # mode chỉ khác nhau ở thứ tự HIỂN THỊ.
            scored.sort(
                key=lambda t: (
                    -(t[0].score - exposure_penalty * expo.get(t[1].user_id, 0)),
                    t[1].user_id,
                )
            )

            n_spread = 0
            spread: list = []
            if mode == "random":
                spread_pool = [p for p in pool if not passes_hard_filters(me, p)
                               and only_feasibility_gap(me, p)]
                n_spread = min(len(spread_pool), round(SPREAD_SHARE * limit))
                if n_spread:
                    sp = sorted(((pair_score(me, p, weights), p) for p in spread_pool),
                                key=lambda t: (t[1].is_simulated, -t[0].score, t[1].user_id))
                    spread = [(ps, p, "spread") for ps, p in sp[:n_spread]]

            rng = random.Random(f"deck:{user_id}:{date.today().isoformat()}")
            chosen = _choose(scored, limit - len(spread),
                             epsilon=EPSILON if mode == "ranked" else 0.0, rng=rng)

            if mode == "random":
                picked = chosen + spread
                random.Random(f"order:{user_id}").shuffle(picked)
            else:
                picked = chosen

            items = []
            for pos, (ps, p, explore) in enumerate(picked):
                conn.execute(
                    text(
                        "INSERT INTO deck_log (user_id, target_id, position, score, s_ab, "
                        "s_ba, features, deck_mode, weights_ver, explore) VALUES "
                        "(:u, :t, :pos, :sc, :sab, :sba, CAST(:f AS JSONB), :mode, :wv, :ex)"
                    ),
                    {
                        "u": user_id, "t": p.user_id, "pos": pos, "sc": ps.score,
                        "sab": ps.s_ab, "sba": ps.s_ba, "f": _json(ps.breakdown),
                        "mode": mode, "wv": weights_ver, "ex": explore,
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
                    f"SELECT {PROFILE_COLS}, s.created_at AS liked_at, "
                    # lời nhắn kèm theo nếu "thích" này đến từ POST /matching/invite
                    "mr.id AS invite_id, mr.note "
                    "FROM swipes s JOIN users u ON u.id = s.user_id "
                    "LEFT JOIN roommate_profiles rp ON rp.user_id = s.user_id "
                    "LEFT JOIN match_requests mr ON mr.from_user = s.user_id "
                    "     AND mr.to_user = :u AND mr.status = 'pending' "
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


RATING_ALGO_K = 3
RATING_RANDOM_K = 2
# Bỏ các ký tự dễ đọc nhầm khi chép tay từ phiếu (0/O, 1/I/L)
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _card_codes(rng: random.Random, n: int) -> list[str]:
    codes: set[str] = set()
    while len(codes) < n:
        codes.add("".join(rng.choice(_CODE_ALPHABET) for _ in range(4)))
    return sorted(codes, key=lambda _: rng.random())


def _choose(scored: list, k: int, *, epsilon: float, rng: random.Random) -> list:
    """Chọn ≤ k thẻ từ danh sách đã xếp theo điểm. Trả [(PairScore, Profile, explore)].

    1. Hồ sơ thật trước; thẻ mô phỏng ≤ max(số thẻ thật, MIN_SIM_SLOTS).
    2. ε-greedy trên nhóm thật: round(ε·k) chỗ lấy NGẪU NHIÊN từ phần đuôi (ngoài
       top), chèn vào vị trí ngẫu nhiên — đặt cuối deck thì người dùng hiếm khi
       quẹt tới, tín hiệu khám phá mất. Số chỗ cố định (không tung đồng xu từng
       thẻ) để tỉ lệ 80/20 đúng ở mọi deck, kể cả deck 5 thẻ.
    """
    if k <= 0:
        return []
    real = [t for t in scored if not t[1].is_simulated]
    sims = [t for t in scored if t[1].is_simulated]

    n_real = min(len(real), k)
    n_explore = round(epsilon * n_real) if len(real) > n_real else 0
    n_explore = min(n_explore, len(real) - n_real)
    top = [(ps, p, None) for ps, p in real[: n_real - n_explore]]
    explore = [(ps, p, "epsilon") for ps, p in rng.sample(real[n_real - n_explore:], n_explore)]

    n_sim = min(k - n_real, max(n_real, MIN_SIM_SLOTS), len(sims))
    # Thẻ mô phỏng xếp xen theo điểm với thẻ thật (không dồn xuống cuối): vị trí
    # chỉ là chuyện hiển thị, phần "ưu tiên thật" đã nằm ở bước CHỌN.
    rank = {p.user_id: i for i, (_, p) in enumerate(scored)}  # giữ thứ hạng đã trừ exposure
    picked = sorted(top + [(ps, p, None) for ps, p in sims[:n_sim]],
                    key=lambda t: rank[t[1].user_id])
    for item in explore:
        picked.insert(rng.randrange(len(picked) + 1), item)
    return picked


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)

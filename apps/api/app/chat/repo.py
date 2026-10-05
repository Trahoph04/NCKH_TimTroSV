"""Truy vấn chat: hội thoại, tin nhắn, đã xem, ảnh, báo cáo, huỷ ghép, lộ liên hệ.

Quy tắc an toàn đặt ở tầng này (không phụ thuộc FE ẩn nút):
- mọi thao tác trên hội thoại đều kiểm tra `is_member` trước;
- hội thoại chỉ sinh từ match (matching/repo.create_match) — không có hàm tạo tay;
- ảnh chỉ tải được bởi thành viên hội thoại chứa ảnh đó;
- liên hệ (T3) chỉ ra khi MỌI thành viên đã đồng ý, và điều kiện đó nằm trong
  WHERE của câu SQL lấy liên hệ — gọi thẳng API vẫn không lấy được.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..matching.repo import PROFILE_COLS

MSG_COLS = "id, conversation_id, sender_id, kind, body, payload, client_id, created_at"


class ConversationGone(Exception):
    """Hội thoại bị xoá (huỷ ghép) giữa lúc kiểm quyền và lúc ghi — router trả 404."""


def _msg(row) -> dict:
    d = dict(row)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    return d


class ChatRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    # ---------------------------------------------------------------- quyền
    # "Thành viên" = mình có trong hội thoại VÀ còn ít nhất một người khác. Đối
    # phương xoá tài khoản ⇒ dòng member của họ bị CASCADE, hội thoại còn mỗi
    # mình: get_conversation (JOIN đối phương) đã trả 404 nhưng các endpoint chỉ
    # kiểm is_member thì vẫn đọc/ghi tin được — hai câu trả lời trái nhau.
    _MEMBER_SQL = (
        "SELECT 1 FROM conversation_members me "
        "WHERE me.conversation_id = :c AND me.user_id = :u "
        "  AND EXISTS (SELECT 1 FROM conversation_members p "
        "              WHERE p.conversation_id = :c AND p.user_id <> :u)"
    )

    def is_member(self, conv_id: int, user_id: int) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text(self._MEMBER_SQL), {"c": conv_id, "u": user_id}).first() is not None

    def member_ids(self, conv_id: int) -> list[int]:
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text("SELECT user_id FROM conversation_members WHERE conversation_id = :c"),
                    {"c": conv_id},
                ).scalars()
            )

    def conversation_ids(self, user_id: int) -> set[int]:
        with self.engine.connect() as conn:
            return set(
                conn.execute(
                    text("SELECT conversation_id FROM conversation_members WHERE user_id = :u"),
                    {"u": user_id},
                ).scalars()
            )

    def partner_ids(self, user_id: int) -> list[int]:
        """Những người đã ghép với user (để báo online/offline)."""
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    text(
                        "SELECT DISTINCT p.user_id FROM conversation_members me "
                        "JOIN conversation_members p ON p.conversation_id = me.conversation_id "
                        "AND p.user_id <> me.user_id WHERE me.user_id = :u"
                    ),
                    {"u": user_id},
                ).scalars()
            )

    # ------------------------------------------------------------ hội thoại
    _CONV_SQL = (
        "SELECT c.id, c.created_at, c.last_message_at, "
        "me.last_read_message_id AS my_last_read, "
        "p.user_id AS partner_id, p.last_read_message_id AS partner_last_read, "
        "COALESCE(NULLIF(u.name, ''), 'Sinh viên CTU') AS partner_name, "
        "u.avatar_url AS partner_avatar, u.last_seen_at AS partner_last_seen, "
        "rp.don_vi AS partner_don_vi, COALESCE(rp.is_simulated, FALSE) AS partner_simulated, "
        "mr.score, "
        "lm.id AS lm_id, lm.sender_id AS lm_sender, lm.kind AS lm_kind, lm.body AS lm_body, "
        "lm.payload AS lm_payload, lm.created_at AS lm_created_at, "
        "(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id "
        "   AND m.id > me.last_read_message_id AND m.sender_id IS NOT NULL "
        "   AND m.sender_id <> me.user_id) AS unread, "
        "(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id "
        "   AND m.sender_id IS NOT NULL) AS user_message_count "
        "FROM conversation_members me "
        "JOIN conversations c ON c.id = me.conversation_id "
        "JOIN conversation_members p ON p.conversation_id = c.id AND p.user_id <> me.user_id "
        "JOIN users u ON u.id = p.user_id "
        "LEFT JOIN roommate_profiles rp ON rp.user_id = p.user_id "
        "LEFT JOIN match_requests mr ON mr.id = c.match_id "
        "LEFT JOIN LATERAL (SELECT * FROM messages m WHERE m.conversation_id = c.id "
        "                   ORDER BY m.id DESC LIMIT 1) lm ON TRUE "
        "WHERE me.user_id = :u AND c.kind = 'pair' "
    )

    @staticmethod
    def _conv(row) -> dict:
        r = dict(row)
        last = None
        if r.get("lm_id") is not None:
            payload = r["lm_payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            last = {
                "id": r["lm_id"], "sender_id": r["lm_sender"], "kind": r["lm_kind"],
                "body": r["lm_body"], "payload": payload, "created_at": r["lm_created_at"],
            }
        return {
            "id": r["id"],
            "created_at": r["created_at"],
            "last_message_at": r["last_message_at"],
            "score": r["score"],
            "unread": r["unread"],
            "user_message_count": r["user_message_count"],
            "my_last_read": r["my_last_read"],
            "partner_last_read": r["partner_last_read"],
            "partner": {
                "id": r["partner_id"],
                "name": r["partner_name"],
                "avatar_url": r["partner_avatar"],
                "don_vi": r["partner_don_vi"],
                "is_simulated": r["partner_simulated"],
                "last_seen_at": r["partner_last_seen"],
            },
            "last_message": last,
        }

    def list_conversations(
        self,
        user_id: int,
        *,
        limit: int = 50,
        before: tuple[Any, int] | None = None,
    ) -> tuple[list[dict], bool]:
        """Trang hội thoại mới nhất. Phân trang keyset theo (last_message_at, id).

        Bản trước không LIMIT: mỗi dòng kéo 2 subquery đếm + 1 LATERAL, nên chi
        phí tăng tuyến tính theo số hội thoại MỖI LẦN mở trang chat. Keyset chứ
        không OFFSET: hội thoại có tin mới nhảy lên đầu giữa hai trang thì OFFSET
        sẽ lặp/bỏ sót dòng.
        """
        params: dict[str, Any] = {"u": user_id, "l": max(1, min(limit, 200)) + 1}
        cond = ""
        if before is not None:
            cond = "AND (c.last_message_at, c.id) < (:bt, :bi) "
            params["bt"], params["bi"] = before
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(self._CONV_SQL + cond + "ORDER BY c.last_message_at DESC, c.id DESC LIMIT :l"),
                params,
            ).mappings().all()
        has_more = len(rows) > params["l"] - 1
        return [self._conv(r) for r in rows[: params["l"] - 1]], has_more

    def get_conversation(self, conv_id: int, user_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(self._CONV_SQL + "AND c.id = :c"), {"u": user_id, "c": conv_id}
            ).mappings().first()
            if row is None:
                return None
            conv = self._conv(row)
            prof = conn.execute(
                text(
                    f"SELECT {PROFILE_COLS} FROM users u "
                    "LEFT JOIN roommate_profiles rp ON rp.user_id = u.id WHERE u.id = :p"
                ),
                {"p": conv["partner"]["id"]},
            ).mappings().first()
            shared = conn.execute(
                text(
                    "SELECT id, sender_id, payload, created_at FROM messages "
                    "WHERE conversation_id = :c AND kind = 'listing' ORDER BY id DESC LIMIT 6"
                ),
                {"c": conv_id},
            ).mappings().all()
            # Trạng thái T3 đi kèm luôn: FE cần biết "mình đã đồng ý chưa / họ đã
            # đồng ý chưa" ngay lần mở hồ sơ, nếu tách request riêng thì panel
            # phải đoán và nháy một nhịp sai trạng thái.
            contact = self._contact_state(conn, conv_id, user_id)
        conv["partner_profile"] = dict(prof) if prof else None
        conv["shared_listings"] = [_msg(s) for s in shared]
        conv["contact"] = contact
        return conv

    # ------------------------------------------------------------- tin nhắn
    def list_messages(
        self,
        conv_id: int,
        *,
        after_id: int | None = None,
        before_id: int | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """after_id: tin MỚI hơn (polling/đồng bộ lại). Ngược lại: trang mới nhất / cũ hơn before_id."""
        limit = max(1, min(limit, 200))
        with self.engine.connect() as conn:
            if after_id is not None:
                rows = conn.execute(
                    text(
                        f"SELECT {MSG_COLS} FROM messages WHERE conversation_id = :c "
                        "AND id > :a ORDER BY id ASC LIMIT :l"
                    ),
                    {"c": conv_id, "a": after_id, "l": limit + 1},
                ).mappings().all()
                has_more = len(rows) > limit
                return [_msg(r) for r in rows[:limit]], has_more
            params: dict[str, Any] = {"c": conv_id, "l": limit + 1}
            cond = ""
            if before_id is not None:
                cond = "AND id < :b "
                params["b"] = before_id
            rows = conn.execute(
                text(
                    f"SELECT {MSG_COLS} FROM messages WHERE conversation_id = :c {cond}"
                    "ORDER BY id DESC LIMIT :l"
                ),
                params,
            ).mappings().all()
        has_more = len(rows) > limit
        return [_msg(r) for r in reversed(rows[:limit])], has_more

    def create_message(
        self,
        conv_id: int,
        sender_id: int,
        kind: str,
        body: str | None,
        payload: dict | None = None,
        client_id: str | None = None,
        media: list[dict] | None = None,
    ) -> tuple[dict, bool]:
        """Lưu tin. Trả (message, is_new). Trùng client_id ⇒ trả tin cũ (gửi lại an toàn).

        Ném ConversationGone khi hội thoại biến mất giữa lúc router kiểm quyền và
        lúc ghi (đối phương bấm huỷ ghép đúng lúc đó). Bản trước rơi vào lỗi FK /
        `.one()` ⇒ 500; giờ khoá dòng member ngay đầu transaction — DELETE
        conversations (cascade xoá member) phải chờ transaction này xong, nên
        giữa kiểm và ghi không còn khe hở. NO KEY UPDATE chứ không FOR SHARE:
        cuối hàm UPDATE chính dòng này (con trỏ đã đọc), hai lần gửi song song
        cùng giữ SHARE rồi cùng xin nâng khoá ⇒ deadlock.
        """
        with self.engine.begin() as conn:
            if conn.execute(
                text(self._MEMBER_SQL + " FOR NO KEY UPDATE OF me"), {"c": conv_id, "u": sender_id}
            ).first() is None:
                raise ConversationGone()
            if client_id:
                old = conn.execute(
                    text(
                        f"SELECT {MSG_COLS} FROM messages WHERE conversation_id = :c "
                        "AND sender_id = :s AND client_id = :cid"
                    ),
                    {"c": conv_id, "s": sender_id, "cid": client_id},
                ).mappings().first()
                if old is not None:
                    return _msg(old), False
            for m in media or []:
                conn.execute(
                    text(
                        "INSERT INTO chat_media (id, conversation_id, uploader_id, width, height, bytes) "
                        "VALUES (:id, :c, :u, :w, :h, :b)"
                    ),
                    {"id": m["id"], "c": conv_id, "u": sender_id, "w": m["w"], "h": m["h"], "b": m["bytes"]},
                )
            # ON CONFLICT DO NOTHING thay vì tin vào lần SELECT ở trên: lần kiểm
            # đó là check-then-insert, hai request cùng client_id gửi SONG SONG
            # (double-tap, retry của FE) đều thấy "chưa có" rồi cùng INSERT ⇒
            # UNIQUE uq_messages_client nổ IntegrityError ⇒ 500, trong khi đúng
            # nghĩa idempotency là trả lại tin đã có.
            inserted = conn.execute(
                text(
                    "INSERT INTO messages (conversation_id, sender_id, kind, body, payload, client_id) "
                    "VALUES (:c, :s, :k, :body, CAST(:payload AS JSONB), :cid) "
                    "ON CONFLICT (conversation_id, sender_id, client_id) "
                    "  WHERE client_id IS NOT NULL DO NOTHING "
                    f"RETURNING {MSG_COLS}"
                ),
                {
                    "c": conv_id, "s": sender_id, "k": kind, "body": body,
                    "payload": None if payload is None else json.dumps(payload, ensure_ascii=False),
                    "cid": client_id,
                },
            ).mappings().first()
            if inserted is None:
                # Request song song đã thắng — trả đúng tin của nó, is_new=False
                # để router KHÔNG publish message.new lần hai (tránh tin trùng
                # trên màn hình người nhận).
                existing = conn.execute(
                    text(
                        f"SELECT {MSG_COLS} FROM messages WHERE conversation_id = :c "
                        "AND sender_id = :s AND client_id = :cid"
                    ),
                    {"c": conv_id, "s": sender_id, "cid": client_id},
                ).mappings().one()
                return _msg(existing), False
            row = inserted
            conn.execute(
                text("UPDATE conversations SET last_message_at = :t WHERE id = :c"),
                {"c": conv_id, "t": row["created_at"]},
            )
            # gửi tin ⇒ coi như đã đọc hết tới tin của chính mình
            conn.execute(
                text(
                    "UPDATE conversation_members SET last_read_message_id = :m, last_read_at = now() "
                    "WHERE conversation_id = :c AND user_id = :s AND last_read_message_id < :m"
                ),
                {"c": conv_id, "s": sender_id, "m": row["id"]},
            )
        return _msg(row), True

    def mark_read(self, conv_id: int, user_id: int, message_id: int) -> tuple[int, bool]:
        """Đẩy con trỏ đã đọc lên (không bao giờ lùi, không vượt tin cuối). Trả (con trỏ, có đổi)."""
        with self.engine.begin() as conn:
            before = conn.execute(
                text(
                    "SELECT last_read_message_id FROM conversation_members "
                    "WHERE conversation_id = :c AND user_id = :u FOR UPDATE"
                ),
                {"c": conv_id, "u": user_id},
            ).scalar()
            if before is None:  # huỷ ghép sau lúc router kiểm quyền (TOCTOU) ⇒ 404, không 500
                raise ConversationGone()
            max_id = conn.execute(
                text("SELECT COALESCE(max(id), 0) FROM messages WHERE conversation_id = :c"),
                {"c": conv_id},
            ).scalar_one()
            target = min(message_id, max_id)
            if target <= before:
                return before, False
            conn.execute(
                text(
                    "UPDATE conversation_members SET last_read_message_id = :m, last_read_at = now() "
                    "WHERE conversation_id = :c AND user_id = :u"
                ),
                {"c": conv_id, "u": user_id, "m": target},
            )
        return target, True

    def total_unread(self, user_id: int) -> int:
        with self.engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT count(*) FROM conversation_members me "
                    "JOIN messages m ON m.conversation_id = me.conversation_id "
                    "WHERE me.user_id = :u AND m.id > me.last_read_message_id "
                    "AND m.sender_id IS NOT NULL AND m.sender_id <> :u"
                ),
                {"u": user_id},
            ).scalar_one()

    # ------------------------------------------------------------- tin trọ
    def listing_snapshot(self, listing_id: int) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT id, title, price, area, district, address, images, route_time_campus "
                    "FROM aggregated_listings WHERE id = :id "
                    "AND status IS DISTINCT FROM 'hidden'"
                ),
                {"id": listing_id},
            ).mappings().first()
        if row is None:
            return None
        images = row["images"] or []
        route = row["route_time_campus"]
        return {
            "listing_id": row["id"],
            "title": row["title"],
            "price": row["price"],
            "area": float(row["area"]) if row["area"] is not None else None,
            "district": row["district"],
            "address": row["address"],
            "image": images[0] if images else None,
            "minutes_khu2": round(route[1]) if route and len(route) > 1 and route[1] is not None else None,
        }

    # ------------------------------------------------------------------ ảnh
    def media_conversation(self, media_id: str, user_id: int) -> int | None:
        """conversation_id nếu user là thành viên hội thoại chứa ảnh, ngược lại None."""
        with self.engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT cm.conversation_id FROM chat_media cm "
                    "JOIN conversation_members m ON m.conversation_id = cm.conversation_id "
                    "AND m.user_id = :u WHERE cm.id = CAST(:id AS UUID)"
                ),
                {"id": media_id, "u": user_id},
            ).scalar()

    # ------------------------------------------- T3: lộ liên hệ hai chiều
    # Lời hứa đã in trong phiếu khảo sát (≈30 SV đã đọc): "Người được ghép chỉ
    # nhìn thấy TÊN và TÓM TẮT THÓI QUEN SINH HOẠT của bạn. MSSV và thông tin
    # liên hệ của bạn CHỈ hiện ra sau khi CẢ HAI BÊN cùng bấm đồng ý kết nối."
    #
    # Vì sao T3 là lần đồng ý THỨ HAI, tách khỏi match: với UX vuốt thì một match
    # rất rẻ (năm cái vuốt trong ba mươi giây). Gắn việc lộ số vào chính cái match
    # nghĩa là một buổi vuốt vui tay = phát số điện thoại cho năm người lạ.
    #
    # MSSV KHÔNG bao giờ nằm trong danh sách lộ: nó ở user_identities(provider='ctu'),
    # chỉ dùng để xác thực nội bộ CTU. Vì vậy câu SQL dưới đây CỐ Ý không JOIN
    # user_identities — không select cột thì không có đường lỡ trả ra.
    _CONTACT_SQL = (
        "SELECT u.id AS user_id, COALESCE(NULLIF(u.name, ''), 'Sinh viên CTU') AS name, "
        "u.email, u.phone "
        "FROM conversation_members other "
        "JOIN users u ON u.id = other.user_id "
        "WHERE other.conversation_id = :c AND other.user_id <> :u "
        # Cổng khoá nằm NGAY trong WHERE chứ không ở Python: còn một người chưa
        # đồng ý ⇒ không dòng nào thoả ⇒ không có gì để lộ, kể cả khi ai đó gọi
        # thẳng endpoint thay vì bấm nút trên FE.
        "AND NOT EXISTS (SELECT 1 FROM conversation_members x "
        "                WHERE x.conversation_id = :c "
        "                  AND NOT COALESCE(x.contact_consent, FALSE)) "
        # Thêm điều kiện ":u là thành viên": NOT EXISTS ở trên đúng cả khi người
        # gọi đứng ngoài hội thoại (mọi thành viên khác đã đồng ý), nên nếu thiếu
        # dòng này thì người lạ xem được liên hệ của một cặp đã mở T3.
        "AND EXISTS (SELECT 1 FROM conversation_members me "
        "            WHERE me.conversation_id = :c AND me.user_id = :u)"
    )

    _CONSENT_STATE_SQL = (
        "SELECT COALESCE(me.contact_consent, FALSE) AS mine, "
        # Đếm thay vì bool_and: schema conversation_members mở cho N người
        # (kind='group', chưa có UI), nên "họ" phải hiểu là TẤT CẢ người còn lại.
        "(SELECT count(*) FROM conversation_members o "
        "   WHERE o.conversation_id = :c AND o.user_id <> :u) AS others, "
        "(SELECT count(*) FROM conversation_members o "
        "   WHERE o.conversation_id = :c AND o.user_id <> :u "
        "     AND COALESCE(o.contact_consent, FALSE)) AS others_ok "
        "FROM conversation_members me "
        "WHERE me.conversation_id = :c AND me.user_id = :u"
    )

    @staticmethod
    def _contact(row) -> dict:
        # phone rỗng ("" do người dùng xoá ô rồi lưu) phải quy về None, nếu không
        # zalo_url thành "https://zalo.me/" — một cái nút chết.
        phone = (row["phone"] or "").strip() or None
        return {
            "user_id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "phone": phone,
            # Zalo chỉ là deep link theo số máy, KHÔNG gọi API Zalo nào. Khảo sát
            # không thu số điện thoại ⇒ hôm nay phone NULL với mọi hồ sơ thật, chỉ
            # có nếu người dùng tự nhập trong app. Trả None để FE khỏi vẽ nút chết.
            "zalo_url": f"https://zalo.me/{phone}" if phone else None,
        }

    def _contact_state(self, conn, conv_id: int, user_id: int) -> dict | None:
        """None = không phải thành viên (router đổi thành 404, không phải 403)."""
        row = conn.execute(
            text(self._CONSENT_STATE_SQL), {"c": conv_id, "u": user_id}
        ).mappings().first()
        if row is None:
            return None
        mine = bool(row["mine"])
        # others == 0: hội thoại còn trơ một người (user kia bị xoá, ON DELETE
        # CASCADE dọn dòng member). Không có ai để lộ cho nhau ⇒ không bao giờ coi
        # là "họ đã đồng ý", nếu không NOT EXISTS ở _CONTACT_SQL sẽ đúng một cách
        # vô nghĩa và state báo đã mở trong khi không có liên hệ nào.
        theirs = row["others"] > 0 and row["others_ok"] == row["others"]
        partner = None
        if mine and theirs:
            p = conn.execute(
                text(self._CONTACT_SQL), {"c": conv_id, "u": user_id}
            ).mappings().first()
            if p is not None:
                partner = self._contact(p)
        return {
            "mine": mine,
            "theirs": theirs,
            # `unlocked` lấy theo KẾT QUẢ câu SQL có cổng khoá, không lấy theo
            # `mine and theirs` tính ở Python: hai nguồn sự thật mà lệch nhau thì
            # FE sẽ hiện "đã mở" kèm liên hệ rỗng.
            "unlocked": partner is not None,
            "waiting_for_other": mine and not theirs,
            "partner": partner,
        }

    def contact_state(self, conv_id: int, user_id: int) -> dict | None:
        with self.engine.connect() as conn:
            return self._contact_state(conn, conv_id, user_id)

    def grant_contact_consent(self, conv_id: int, user_id: int) -> tuple[dict, bool] | None:
        """Bật contact_consent cho CHÍNH người gọi. Trả (state, vừa mới bật).

        Idempotent: bấm lần hai không phải lỗi, chỉ là `vừa mới bật = False` để
        router khỏi phát lại sự kiện realtime.
        """
        with self.engine.begin() as conn:
            # FOR UPDATE trên ĐÚNG dòng của mình: hai người bấm cùng lúc khoá hai
            # dòng khác nhau nên không deadlock, mà vẫn không có hai request của
            # cùng một người cùng đọc "chưa bật" rồi cùng báo "vừa mới bật".
            row = conn.execute(
                text(
                    "SELECT COALESCE(contact_consent, FALSE) FROM conversation_members "
                    "WHERE conversation_id = :c AND user_id = :u FOR UPDATE"
                ),
                {"c": conv_id, "u": user_id},
            ).first()
            if row is None:
                return None
            newly = not row[0]
            if newly:
                # user_id = :u là cả quyền và phạm vi: không có đường nào trong
                # endpoint này bật đồng ý THAY cho người khác.
                conn.execute(
                    text(
                        "UPDATE conversation_members SET contact_consent = TRUE "
                        "WHERE conversation_id = :c AND user_id = :u"
                    ),
                    {"c": conv_id, "u": user_id},
                )
        # Đọc state SAU khi commit (connection mới), không đọc trong transaction
        # ghi: hai người bấm đồng ý gần như cùng lúc thì mỗi transaction chỉ thấy
        # snapshot trước commit của người kia ⇒ cả hai nhận "đang chờ" dù đã đủ
        # hai chữ ký, phải F5 mới thấy mở.
        state = self.contact_state(conv_id, user_id)
        return None if state is None else (state, newly)

    # ------------------------------------------------- huỷ ghép / báo cáo
    def unmatch(self, conv_id: int, user_id: int) -> tuple[list[int], list[str]]:
        """Huỷ ghép: xoá CỨNG hội thoại (tin + ảnh) — tôn trọng quyền rút dữ liệu.

        Đặt cả hai swipe về 'pass' để lượt thích cũ không tự ghép lại; đánh dấu
        match_requests = 'unmatched' (giữ vết cho thống kê, không giữ nội dung).
        Trả (member_ids, media_ids) để router báo realtime + xoá file.
        """
        with self.engine.begin() as conn:
            members = list(
                conn.execute(
                    text("SELECT user_id FROM conversation_members WHERE conversation_id = :c"),
                    {"c": conv_id},
                ).scalars()
            )
            media = [
                str(x)
                for x in conn.execute(
                    text("SELECT id FROM chat_media WHERE conversation_id = :c"), {"c": conv_id}
                ).scalars()
            ]
            match_id = conn.execute(
                text("SELECT match_id FROM conversations WHERE id = :c"), {"c": conv_id}
            ).scalar()
            if match_id is not None:
                conn.execute(
                    text(
                        "UPDATE match_requests SET status = 'unmatched', responded_at = now() "
                        "WHERE id = :m"
                    ),
                    {"m": match_id},
                )
            if len(members) == 2:
                a, b = members
                conn.execute(
                    text(
                        "UPDATE swipes SET decision = 'pass', updated_at = now() "
                        "WHERE (user_id = :a AND target_id = :b) OR (user_id = :b AND target_id = :a)"
                    ),
                    {"a": a, "b": b},
                )
            conn.execute(text("DELETE FROM conversations WHERE id = :c"), {"c": conv_id})
        return members, media

    def report(self, conv_id: int, reporter_id: int, target_id: int, reason: str, note: str | None) -> int:
        with self.engine.begin() as conn:
            return conn.execute(
                text(
                    "INSERT INTO user_reports (reporter_id, target_id, conversation_id, reason, note) "
                    "VALUES (:r, :t, :c, :reason, :note) RETURNING id"
                ),
                {"r": reporter_id, "t": target_id, "c": conv_id, "reason": reason, "note": note},
            ).scalar_one()

    def touch_last_seen(self, user_id: int) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE users SET last_seen_at = now() WHERE id = :u"), {"u": user_id})

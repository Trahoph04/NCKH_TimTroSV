import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..listings.repo import visible_clause
from .schemas import AdminReviewOut, ReviewIn, ReviewOut, ReviewSummary

_REVIEW_COLS = ("r.id, r.listing_id, r.rating, r.tags, r.content, r.stay_period AS relation, r.status, "
                "r.created_at, r.updated_at, u.name AS author_name")


def short_name(name: str | None) -> str:
    """'Trần Hoàng Phú' → 'Phú T.H.' — tên gọi (chữ cuối) + chữ cái đầu họ/đệm; không lộ họ tên đầy đủ trên trang công khai."""
    # bỏ phần trong ngoặc ("Nguyễn Văn A (CNTT)") và mẩu không có chữ cái — nếu không ra "CNTT) N.V.A.(."
    cleaned = re.sub(r"\([^)]*\)", " ", name or "")
    parts = [p for p in re.split(r"[\s,;/]+", cleaned) if any(ch.isalpha() for ch in p)]
    if not parts:
        return "Sinh viên"
    initials = ".".join(p[0].upper() for p in parts[:-1])
    return f"{parts[-1]} {initials}." if initials else parts[-1]


def _out(row) -> ReviewOut:
    d = dict(row)
    d["tags"] = d.get("tags") or []
    d["author"] = short_name(d.pop("author_name", None))
    return ReviewOut(**d)


class ReviewRepo:
    """Đánh giá nhà trọ của SV (bảng reviews mig 90 + 102). Chỉ status 'visible' tính vào điểm và hiện công khai."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def listing_reviewable(self, listing_id: int) -> bool:
        return self.listing_owner(listing_id) is not False

    def listing_owner(self, listing_id: int) -> int | None | bool:
        """posted_by của tin đang hiện (None = tin crawl/khảo sát); False = tin không tồn tại/đang ẩn/hết hạn."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT posted_by FROM aggregated_listings WHERE id = :id AND status NOT IN ('expired', 'hidden') "
                     f"AND {visible_clause(None)}"),
                {"id": listing_id},
            ).first()
        return False if row is None else row.posted_by

    def summary(self, listing_id: int) -> ReviewSummary:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT rating, count(*) AS n FROM reviews WHERE listing_id = :id AND status = 'visible' "
                     "GROUP BY rating"),
                {"id": listing_id},
            ).mappings().all()
            tags = conn.execute(
                text("SELECT t AS tag, count(*) AS n FROM reviews, unnest(tags) AS t "
                     "WHERE listing_id = :id AND status = 'visible' GROUP BY t"),
                {"id": listing_id},
            ).mappings().all()
        counts = {r["rating"]: r["n"] for r in rows}
        total = sum(counts.values())
        average = round(sum(k * v for k, v in counts.items()) / total, 1) if total else None
        return ReviewSummary(average=average, total=total, rating_counts=counts,
                             tag_counts={t["tag"]: t["n"] for t in tags})

    def visible(self, listing_id: int, page: int, size: int) -> list[ReviewOut]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {_REVIEW_COLS} FROM reviews r LEFT JOIN users u ON u.id = r.user_id "
                     "WHERE r.listing_id = :id AND r.status = 'visible' "
                     "ORDER BY COALESCE(r.updated_at, r.created_at) DESC, r.id DESC LIMIT :limit OFFSET :offset"),
                {"id": listing_id, "limit": size, "offset": (page - 1) * size},
            ).mappings().all()
        return [_out(r) for r in rows]

    def mine(self, listing_id: int, user_id: int) -> ReviewOut | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT {_REVIEW_COLS} FROM reviews r LEFT JOIN users u ON u.id = r.user_id "
                     "WHERE r.listing_id = :id AND r.user_id = :u"),
                {"id": listing_id, "u": user_id},
            ).mappings().first()
        return _out(row) if row else None

    def upsert(self, listing_id: int, user_id: int, body: ReviewIn) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO reviews (listing_id, user_id, rating, tags, content, stay_period) "
                    "VALUES (:id, :u, :rating, :tags, :content, :relation) "
                    "ON CONFLICT (listing_id, user_id) WHERE listing_id IS NOT NULL AND user_id IS NOT NULL "
                    "DO UPDATE SET rating = EXCLUDED.rating, tags = EXCLUDED.tags, content = EXCLUDED.content, "
                    # admin đã ẩn thì sửa lại vẫn ẩn — không tự thoát kiểm duyệt bằng cách bấm Lưu
                    "stay_period = EXCLUDED.stay_period, updated_at = now()"
                ),
                {"id": listing_id, "u": user_id, "rating": body.rating, "tags": body.tags,
                 "content": body.content, "relation": body.relation},
            )

    def delete_mine(self, listing_id: int, user_id: int) -> bool:
        # đánh giá admin đã ẩn không xoá được: xoá rồi gửi lại sẽ thành hàng mới 'visible' = thoát kiểm duyệt
        with self.engine.begin() as conn:
            return conn.execute(
                text("DELETE FROM reviews WHERE listing_id = :id AND user_id = :u AND status <> 'hidden'"),
                {"id": listing_id, "u": user_id},
            ).rowcount > 0

    def admin_search(self, status: str | None, page: int, size: int) -> tuple[int, list[AdminReviewOut]]:
        where, params = "r.listing_id IS NOT NULL", {}
        if status:
            where += " AND r.status = :status"
            params["status"] = status
        with self.engine.connect() as conn:
            total = conn.execute(text(f"SELECT count(*) FROM reviews r WHERE {where}"), params).scalar_one()
            rows = conn.execute(
                text(f"SELECT {_REVIEW_COLS}, a.title AS listing_title, u.email AS author_email FROM reviews r "
                     "LEFT JOIN users u ON u.id = r.user_id LEFT JOIN aggregated_listings a ON a.id = r.listing_id "
                     f"WHERE {where} ORDER BY COALESCE(r.updated_at, r.created_at) DESC, r.id DESC "
                     "LIMIT :limit OFFSET :offset"),
                {**params, "limit": size, "offset": (page - 1) * size},
            ).mappings().all()
        items = []
        for r in rows:
            d = dict(r)
            d["tags"] = d.get("tags") or []
            d["author"] = short_name(d.pop("author_name", None))
            items.append(AdminReviewOut(**d))
        return total, items

    def set_status(self, review_id: int, status: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(
                text("UPDATE reviews SET status = :s WHERE id = :id AND listing_id IS NOT NULL"),
                {"s": status, "id": review_id},
            ).rowcount > 0

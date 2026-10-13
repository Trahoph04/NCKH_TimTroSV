import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Tag chuẩn hoá — key khớp apps/web/src/lib/reviews.ts (đổi thì đổi cả hai). Tag tiêu cực là tín hiệu rủi ro do người đã
# ở/đi xem báo lại (thuyết minh 14.2 "cảnh báo thông tin rủi ro") — không có mô hình AI chấm (ADR-024).
POSITIVE_TAGS = ("dung_mo_ta", "chu_tot", "sach_se", "yen_tinh", "an_ninh_tot")
NEGATIVE_TAGS = ("coc_khong_tra", "gia_khong_dung", "dien_nuoc_cao", "an_ninh_kem", "on_ao", "ngap_nuoc",
                 "chu_kho_chiu")
ALL_TAGS = POSITIVE_TAGS + NEGATIVE_TAGS

Relation = Literal["dang_o", "da_o", "da_xem"]  # đang ở | đã từng ở | đã đi xem phòng (lưu ở cột stay_period)

# SĐT / link trong nhận xét: thành kênh quảng cáo, lộ số người khác (NĐ 13/2023) — từ chối thay vì tự che
_PHONE = re.compile(r"(?<![\d.,])(?:\+84|0)(?:[\s.\-]?\d){8,10}(?!\d)")
_LINK = re.compile(r"(https?://|www\.|zalo\.me|facebook\.com|fb\.com|\.com\b|\.vn\b)", re.IGNORECASE)


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    tags: list[str] = Field(default_factory=list, max_length=6)
    content: str | None = Field(default=None, max_length=1000)
    relation: Relation

    @field_validator("tags")
    @classmethod
    def _known_tags(cls, tags: list[str]) -> list[str]:
        unknown = [t for t in tags if t not in ALL_TAGS]
        if unknown:
            raise ValueError(f"tag không hợp lệ: {unknown}")
        return list(dict.fromkeys(tags))  # bỏ trùng, giữ thứ tự

    @field_validator("content")
    @classmethod
    def _clean_content(cls, content: str | None) -> str | None:
        if content is None:
            return None
        content = content.strip()
        if not content:
            return None
        if _PHONE.search(content) or _LINK.search(content):
            raise ValueError("Không ghi số điện thoại hay đường link trong đánh giá")
        return content


class ReviewOut(BaseModel):
    id: int
    listing_id: int
    rating: int
    tags: list[str]
    content: str | None = None
    relation: str | None = None
    author: str                      # tên rút gọn ("Phú T.H.") — không lộ họ tên đầy đủ/email
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class ReviewSummary(BaseModel):
    average: float | None = None
    total: int = 0
    rating_counts: dict[int, int] = Field(default_factory=dict)
    tag_counts: dict[str, int] = Field(default_factory=dict)


class ReviewList(BaseModel):
    summary: ReviewSummary
    items: list[ReviewOut]
    page: int
    size: int


class AdminReviewOut(ReviewOut):
    listing_title: str | None = None
    author_email: str | None = None


class AdminReviewPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[AdminReviewOut]


class ReviewModerationIn(BaseModel):
    status: Literal["visible", "hidden"]

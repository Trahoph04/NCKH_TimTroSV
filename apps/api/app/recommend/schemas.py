from pydantic import BaseModel, Field, field_validator

from ..listings.schemas import HousingType, ListingOut
from .core import AMENITY_LABELS, SURVEY_TOP3


class RecommendIn(BaseModel):
    """Tiêu chí gợi ý — khớp câu C1/C4/C5/top-3 của khảo sát."""

    budget: int = Field(ge=500_000, le=20_000_000)          # VND/tháng
    campus: int = Field(default=1, ge=0, le=2)
    max_minutes: float = Field(default=10, ge=3, le=60)
    housing: HousingType | None = None
    required: list[str] = Field(default_factory=list, max_length=8)
    top_factors: list[str] = Field(default_factory=list, max_length=3)
    gender: str | None = None

    @field_validator("required")
    @classmethod
    def _amenities(cls, v: list[str]) -> list[str]:
        bad = [a for a in v if a not in AMENITY_LABELS]
        if bad:
            raise ValueError(f"tiện ích không hợp lệ: {bad}")
        return list(dict.fromkeys(v))

    @field_validator("top_factors")
    @classmethod
    def _factors(cls, v: list[str]) -> list[str]:
        bad = [f for f in v if f not in SURVEY_TOP3]
        if bad:
            raise ValueError(f"yếu tố không hợp lệ: {bad}")
        return list(dict.fromkeys(v))

    @field_validator("gender")
    @classmethod
    def _gender(cls, v: str | None) -> str | None:
        if v not in (None, "nam", "nu"):
            raise ValueError("gender phải là 'nam' | 'nu'")
        return v


class RecommendItem(BaseModel):
    listing: ListingOut
    match: int                 # 0..100 = U × 100
    reasons: list[str]
    ask: list[str]             # tiện ích người dùng cần mà tin không nhắc → nên hỏi chủ trọ


class RecommendOut(BaseModel):
    items: list[RecommendItem]
    relaxed: list[str]         # ràng buộc đã nới khi quá ít tin thoả
    candidates: int            # số tin qua lọc cứng (sau khi nới, nếu có)
    weights: dict[str, float]
    algo_ver: str


class Prefill(BaseModel):
    budget: int | None = None
    gender: str | None = None


class EvalCard(BaseModel):
    """Thẻ đánh giá mù — CỐ Ý không có điểm, lý do hay hệ nào xếp hạng."""

    card_code: str
    listing: ListingOut
    minutes: float | None
    relevance: int | None = None


class EvalSession(BaseModel):
    session_id: int
    campus: int
    cards: list[EvalCard]
    judged: int
    completed: bool


class JudgeIn(BaseModel):
    card_code: str = Field(min_length=4, max_length=8)
    relevance: int = Field(ge=0, le=2)

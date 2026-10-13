from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class HousingType(str, Enum):
    """Loại chỗ ở SV thuê được — khớp cleaner.pipeline.HOUSING_TYPES."""

    phong_tro = "phong_tro"
    nha_mini = "nha_mini"


class SortBy(str, Enum):
    price_asc = "price_asc"
    price_desc = "price_desc"
    newest = "newest"
    nearest = "nearest"
    freshness = "freshness"
    quality = "quality"


def risk_level(score: float | None) -> str:
    """risk_score → nhãn badge (FR-7.2). ✅ safe / ⚠️ caution / 🔴 suspicious."""
    # ponytail: risk engine chưa build (team làm sau) → score=0 mặc định = CHƯA đánh giá,
    # không phải "an toàn". Bỏ guard này khi risk detection ghi score thật.
    if not score:
        return "unknown"
    if score < 0.3:
        return "safe"
    if score < 0.6:
        return "caution"
    return "suspicious"


def freshness_label(last_seen: datetime | None, now: datetime | None = None) -> str:
    """last_seen → 'cập nhật X giờ/ngày trước' (FR-2.8)."""
    if last_seen is None:
        return "không rõ"
    from datetime import timezone

    now = now or datetime.now(timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    secs = max(0, (now - last_seen).total_seconds())
    if secs < 3600:
        return f"cập nhật {int(secs // 60)} phút trước"
    if secs < 86400:
        return f"cập nhật {int(secs // 3600)} giờ trước"
    return f"cập nhật {int(secs // 86400)} ngày trước"


class SearchParams(BaseModel):
    q: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_area: float | None = None
    district: str | None = None
    amenities: list[str] = Field(default_factory=list)
    max_distance_ctu: float | None = None        # mét
    housing: HousingType | None = None            # None = phòng trọ + nhà mini
    sort: SortBy = SortBy.newest
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


class ListingOut(BaseModel):
    id: int
    title: str
    price: int | None = None
    area: float | None = None
    address: str | None = None
    district: str | None = None
    lat: float | None = None
    lng: float | None = None
    distance_to_ctu: float | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    source: str
    source_url: str | None = None
    risk_score: float | None = None
    risk_level: str = "unknown"
    geocode_confidence: str | None = None
    freshness_score: float | None = None
    freshness_label: str = ""
    quality_score: float | None = None
    last_seen: datetime | None = None
    # [khuI, khuII, khuIII] phút, None = chưa route. Từng phần tử cũng có thể None: ORS Matrix không tìm được đường tới
    # riêng một khu ⇒ auto_route ghi [4.0, None, 3.2]; khai list[float] thì mọi trang có tin đó lỗi 500 (bắt từ nhánh
    # open-mobility của Huy, 13/10)
    route_time_campus: list[float | None] | None = None
    listing_type: str | None = None  # phong_tro | nha_mini | ... (tin user tự đăng có thể chưa phân loại)
    offer_kind: str | None = None    # 'lease_transfer' = pass phòng/sang nhượng → FE hiện nhãn riêng
    location_precise: bool | None = None  # app.cleaner.audit: False = toạ độ cấp phường (bản đồ ẩn mặc định)
    rating_avg: float | None = None       # điểm TB đánh giá SV đang hiện (app/reviews); None = chưa có
    rating_count: int = 0


class ContactOut(BaseModel):
    """Liên hệ của 1 tin — endpoint riêng, KHÔNG nằm trong ListingOut: số chỉ trả khi người dùng mở đúng 1 tin,
    không lấy hàng loạt được qua /listings hay /nearby. Không có số ⇒ FE đưa người dùng sang trang nguồn."""

    phone: str | None = None
    zalo: str | None = None
    facebook: str | None = None
    source: str
    source_url: str | None = None


class SearchResult(BaseModel):
    total: int
    page: int
    size: int
    items: list[ListingOut]


class ListingCreate(BaseModel):
    """Payload đăng tin UGC (FR-3.1)."""

    title: str = Field(min_length=1)
    price: int | None = None
    area: float | None = None
    address: str | None = None
    district: str | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)


class ListingUpdate(BaseModel):
    """Payload sửa tin UGC — mọi field optional (partial update)."""

    title: str | None = None
    price: int | None = None
    area: float | None = None
    address: str | None = None
    district: str | None = None
    description: str | None = None
    images: list[str] | None = None

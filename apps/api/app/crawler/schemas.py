from datetime import datetime

from pydantic import BaseModel, Field


class RawListing(BaseModel):
    """Field thô trích từ HTML, chưa chuẩn hóa."""

    source: str
    source_id: str | None = None
    source_url: str | None = None
    title: str = ""
    price_text: str | None = None
    area_text: str | None = None
    address: str | None = None
    district: str | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    amenities_text: str | None = None


class NormalizedListing(BaseModel):
    """Listing đã chuẩn hóa, sẵn sàng upsert vào DB."""

    source: str
    source_id: str | None = None
    source_url: str | None = None
    title: str
    price: int | None = None          # VND
    area: float | None = None         # m2
    address: str | None = None
    district: str | None = None
    description: str | None = None
    images: list[str] = Field(default_factory=list)
    amenities: dict[str, bool] = Field(default_factory=dict)
    content_hash: str = ""
    seen_at: datetime | None = None
    # geocode (T2)
    lat: float | None = None
    lng: float | None = None
    geocode_confidence: str = "failed"
    distance_to_ctu: float | None = None
    # thuộc tính mềm trích từ mô tả (crawler/extras.py) — None = nguồn chưa trích
    extras: dict | None = None
    # text chứa liên hệ lấy từ trang chi tiết (crawler/contact.py). None = nguồn không có
    contact_text: str | None = None
    # liên hệ + địa chỉ chuẩn hoá do nguồn tự cung cấp (nhatot) — migration 91
    contact: dict | None = None
    address_norm: dict | None = None

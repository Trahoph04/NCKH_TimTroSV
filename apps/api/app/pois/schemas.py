from pydantic import BaseModel


class PoiOut(BaseModel):
    id: int
    category: str
    name: str | None = None
    lat: float
    lng: float
    distance_m: float  # đường chim bay từ điểm truy vấn


class CategorySummary(BaseModel):
    category: str
    label: str
    count: int                      # số tiện ích trong bán kính
    nearest: PoiOut | None = None   # gần nhất trong bán kính


class PoiSummary(BaseModel):
    radius: int
    categories: list[CategorySummary]

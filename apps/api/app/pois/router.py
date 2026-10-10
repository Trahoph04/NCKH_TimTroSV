from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from .categories import CATEGORIES
from .repo import PoiRepo
from .schemas import PoiOut, PoiSummary

router = APIRouter(prefix="/pois", tags=["pois"])

# engine được set bởi main.py qua init_pois(engine)
_engine: Engine | None = None


def init_pois(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_repo() -> PoiRepo:
    if _engine is None:
        raise HTTPException(503, "POI repo chưa khởi tạo")
    return PoiRepo(_engine)


@router.get("/summary", response_model=PoiSummary)
def poi_summary(
    lat: float,
    lng: float,
    radius: int = Query(1000, gt=0, le=3000),
    repo: PoiRepo = Depends(get_repo),
):
    """Tiện ích quanh 1 điểm: đếm theo nhóm + cái gần nhất (đường chim bay). Khai TRƯỚC route động."""
    return repo.summary(lat, lng, radius)


@router.get("", response_model=list[PoiOut])
def pois_near(
    lat: float,
    lng: float,
    radius: int = Query(1000, gt=0, le=5000),
    category: str | None = None,
    repo: PoiRepo = Depends(get_repo),
):
    """Tiện ích trong bán kính, gần trước. category: cho|sieu_thi|atm|nha_thuoc|y_te|xe_buyt."""
    if category is not None and category not in CATEGORIES:
        raise HTTPException(422, f"category phải là một trong {list(CATEGORIES)}")
    return repo.near(lat, lng, radius, category)

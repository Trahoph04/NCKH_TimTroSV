import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Engine

from ..auth import require_admin
from ..auth.schemas import UserOut
from ..config import settings
from ..crawler.geocode import Geocoder, haversine_m, CTU_LAT, CTU_LNG
from .repo import ListingQueryRepo, ListingWriteRepo, RouteCacheRepo
from .routing import CAMPUSES, OSRM_PROFILE, PROFILE, matrix_minutes, route_geometry, route_geometry_osrm
from .schemas import (
    ContactOut, HousingType, ListingCreate, ListingOut, ListingUpdate, SearchParams, SearchResult, SortBy,
)

log = logging.getLogger("listings.router")

router = APIRouter(prefix="/listings", tags=["listings"])

# engine được set bởi main.py qua init_listings(engine)
_engine: Engine | None = None


def init_listings(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_repo() -> ListingQueryRepo:
    if _engine is None:
        raise HTTPException(503, "Listings repo chưa khởi tạo")
    return ListingQueryRepo(_engine)


def get_write_repo() -> ListingWriteRepo:
    if _engine is None:
        raise HTTPException(503, "Listings repo chưa khởi tạo")
    return ListingWriteRepo(_engine)


async def _geocode_address(address: str | None):
    """Geocode address → (lat, lng, conf, distance_to_ctu). None nếu không có address."""
    if not address:
        return None, None, None, None
    async with Geocoder() as g:
        lat, lng, conf = await g.geocode(address)
    dist = haversine_m(lat, lng, CTU_LAT, CTU_LNG) if lat is not None and lng is not None else None
    return lat, lng, conf, dist


async def _route_one(lat: float | None, lng: float | None) -> list[float] | None:
    """Route 1 điểm tới 3 campus (VIỆC 4 — re-route khi user sửa address).

    ors_api_key rỗng hoặc lỗi mạng → None, skip êm (không chặn create/update tin).
    """
    if lat is None or lng is None or not settings.ors_api_key:
        return None
    try:
        times = await matrix_minutes([(lat, lng)])
        return times[0] if times else None
    except Exception as exc:  # noqa: BLE001 — routing lỗi không chặn CRUD tin
        log.warning("route on address change fail: %s", exc)
        return None


@router.get("", response_model=SearchResult)
def search_listings(
    q: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_area: float | None = None,
    district: str | None = None,
    amenities: list[str] = Query(default_factory=list),
    max_distance_ctu: float | None = None,
    housing: HousingType | None = None,
    sort: SortBy = SortBy.newest,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    repo: ListingQueryRepo = Depends(get_repo),
):
    """Tìm kiếm + lọc + sắp xếp + phân trang (FR-2.1/2.2/2.3). Ẩn tin expired.

    housing: phong_tro | nha_mini; bỏ trống = cả hai.
    """
    params = SearchParams(
        q=q, min_price=min_price, max_price=max_price, min_area=min_area,
        district=district, amenities=amenities, max_distance_ctu=max_distance_ctu,
        housing=housing, sort=sort, page=page, size=size,
    )
    total, items = repo.search(params)
    return SearchResult(total=total, page=page, size=size, items=items)


@router.get("/nearby", response_model=list[ListingOut])
def nearby_listings(
    lat: float,
    lng: float,
    radius: float = Query(2000, gt=0, le=20000),
    housing: HousingType | None = None,
    repo: ListingQueryRepo = Depends(get_repo),
):
    """Tìm theo bán kính trên bản đồ (FR-2.5). radius: mét. housing như GET /listings."""
    return repo.nearby(lat, lng, radius, housing=housing)


@router.get("/managed", response_model=list[ListingOut])
def managed_listings(
    _admin: UserOut = Depends(require_admin),
    repo: ListingQueryRepo = Depends(get_repo),
):
    """Tin nhập tay qua trang quản lý (source='user', của mọi admin). Phải khai báo TRƯỚC /{listing_id}."""
    return repo.managed()


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, repo: ListingQueryRepo = Depends(get_repo)):
    """Chi tiết 1 tin (FR-2.6). Ẩn tin expired/hidden."""
    item = repo.get_visible(listing_id)
    if item is None:
        raise HTTPException(404, "Không tìm thấy tin")
    return item


@router.get("/{listing_id}/contact", response_model=ContactOut)
def get_contact(listing_id: int, repo: ListingQueryRepo = Depends(get_repo)):
    """Liên hệ của 1 tin: số điện thoại nếu tin có, không thì link trang nguồn (FE hiện "Xem tin gốc")."""
    c = repo.contact(listing_id)
    if c is None:
        raise HTTPException(404, "Không tìm thấy tin")
    return c


@router.get("/{listing_id}/route", response_model=list[list[float]])
async def get_route_geometry(
    listing_id: int,
    campus: int = Query(1, ge=0, le=2),
    repo: ListingQueryRepo = Depends(get_repo),
):
    """Polyline route thật campus→tin (FR-M.8), fetch on-demand khi user click 1 tin.

    campus: 0=khu I, 1=khu II (mặc định), 2=khu III.
    """
    item = repo.get_visible(listing_id)
    if item is None or item.lat is None or item.lng is None:
        raise HTTPException(404, "Không tìm thấy tin hoặc tin chưa có toạ độ")
    # Thứ tự: cache (ORS rồi OSRM) → ORS → OSRM. Nhiều tin chung 1 toạ độ cấp phường + demo không được phụ thuộc
    # quota/mạng; ORS Directions từng hết quota cả ngày (403) làm bản đồ mất đường đi ở mọi tin chưa có trong cache.
    cache = RouteCacheRepo(_engine)
    for profile in (PROFILE, OSRM_PROFILE):
        cached = cache.get(item.lat, item.lng, campus, profile)
        if cached is not None:
            return cached
    errors = []
    engines = ([(PROFILE, route_geometry)] if settings.ors_api_key else []) + [(OSRM_PROFILE, route_geometry_osrm)]
    for profile, fetch in engines:
        try:
            path = await fetch(CAMPUSES[campus], (item.lat, item.lng))
        except Exception as exc:  # noqa: BLE001 — engine này lỗi thì thử engine sau
            errors.append(f"{profile}: {exc}")
            log.warning("route %s fail #%s: %s", profile, listing_id, exc)
            continue
        try:
            cache.put(item.lat, item.lng, campus, profile, path)
        except Exception as exc:  # noqa: BLE001 — ghi cache hỏng không chặn trả đường đi
            log.warning("route cache put fail: %s", exc)
        return path
    raise HTTPException(502, "Không lấy được route: " + " | ".join(errors)[:300])


# Sinh viên KHÔNG đăng tin (ADR-024): dữ liệu chỉ từ crawl (có link gốc), khảo sát thực địa và admin nhập tay.
# Tin do người lạ tự đăng là chỗ dễ lừa đảo nhất mà hệ thống không có kiểm duyệt/chấm rủi ro cho nó.


@router.post("", response_model=ListingOut, status_code=201)
async def create_listing(
    body: ListingCreate,
    user: UserOut = Depends(require_admin),
    repo: ListingQueryRepo = Depends(get_repo),
    write: ListingWriteRepo = Depends(get_write_repo),
):
    """Admin nhập tin tay (source='user', posted_by = admin)."""
    lat, lng, conf, dist = await _geocode_address(body.address)
    new_id = write.create(body.model_dump(), user.id, lat, lng, conf, dist)
    times = await _route_one(lat, lng)
    if times is not None:
        write.set_route_time(new_id, times)
    return repo.get(new_id)


@router.put("/{listing_id}", response_model=ListingOut)
async def update_listing(
    listing_id: int,
    body: ListingUpdate,
    _admin: UserOut = Depends(require_admin),
    repo: ListingQueryRepo = Depends(get_repo),
    write: ListingWriteRepo = Depends(get_write_repo),
):
    """Admin sửa tin nhập tay. Tin crawl/khảo sát không sửa tay được: lần crawl/import sau sẽ ghi đè."""
    owner_row = write.get_owner(listing_id)
    if owner_row is None:
        raise HTTPException(404, "Không tìm thấy tin")
    if owner_row["source"] != "user":
        raise HTTPException(409, "Tin crawl/khảo sát được cập nhật bởi pipeline — sửa ở nguồn rồi nạp lại")

    fields = body.model_dump(exclude_unset=True)
    lat, lng, conf, dist = None, None, None, None
    if "address" in fields:
        lat, lng, conf, dist = await _geocode_address(fields["address"])

    write.update(listing_id, fields, lat, lng, conf, dist)
    if "address" in fields:
        times = await _route_one(lat, lng)
        if times is not None:
            write.set_route_time(listing_id, times)
    return repo.get(listing_id)


@router.delete("/{listing_id}", status_code=204)
def delete_listing(
    listing_id: int,
    _admin: UserOut = Depends(require_admin),
    write: ListingWriteRepo = Depends(get_write_repo),
):
    """Admin ẩn tin bất kỳ (status='hidden', không xoá). Crawler upsert không bật lại tin 'hidden' (ADR-022)."""
    if write.get_owner(listing_id) is None:
        raise HTTPException(404, "Không tìm thấy tin")
    write.soft_delete(listing_id)

"""Bản đồ v2 (docs/specs/Map_MapLibre_POI.md): classifier nhà mini, nạp gói Chợ Tốt, nhãn toạ độ
dùng chung, lọc loại chỗ ở, tiện ích OSM, cache đường đi. Phần DB chạy trên nckh_test (conftest)."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.cleaner.pipeline import classify, detect_offer_kind, reclassify, score, validate
from app.config import settings
from app.crawler import import_catalog
from app.crawler.repo import ListingRepo
from app.listings.repo import RouteCacheRepo, build_filters
from app.listings.routing import PROFILE
from app.listings.schemas import HousingType, SearchParams
from app.main import app, engine
from app.pois.categories import category_of, overpass_query
from app.pois.fetch_overpass import to_items, to_sql

client = TestClient(app)


# ── Classifier ──
@pytest.mark.parametrize(
    ("title", "price", "area", "expected"),
    [
        ("Cho thuê Minihouse KDC 91B, 25m2, full nội thất, 4 triệu", 4_000_000, 25, "nha_mini"),
        ("Mini House Mặt Tiền Bờ Kè Cái Sơn - 3.3 Triệu", 3_300_000, None, "nha_mini"),
        ("Cho thuê căn hộ mini gần ĐHCT", 3_500_000, None, "nha_mini"),
        # "phòng ngủ" mô tả căn, không phải cho thuê phòng
        ("Minihouse 4,4 triệu 2 phòng ngủ Hồ Bún Xáng", 4_400_000, 40, "nha_mini"),
        ("Cho thuê phòng trọ có phòng tắm riêng", 2_000_000, 20, "phong_tro"),
        # "phòng minihouse" là 1 phòng — gói 789 gắn room
        ("Cho thuê phòng Minihouse hẻm 30/4, Cần Thơ", 2_300_000, None, "phong_tro"),
        # tiêu đề Chợ Tốt không có chữ "phòng"
        ("Trọ gần ĐHCT, CĐ NGHỀ", 3_000_000, None, "phong_tro"),
        ("Cho thuê trọ mới xây KDC Thạnh Mỹ - Cái Răng", 2_000_000, None, "phong_tro"),
        # "kho" từng khớp chuỗi con của "không"/"Khoa" → phòng trọ thành mặt bằng
        ("Cho thuê trọ không gác, 1tr1, Trương Vĩnh Nguyên", 1_100_000, None, "phong_tro"),
        ("Nhà trọ sinh viên Toàn Khoa, Cần Thơ, giá 2tr", 2_000_000, None, "phong_tro"),
        ("Cho thuê kho chứa hàng 100m2", 9_000_000, 100, "mat_bang"),
    ],
)
def test_classify_map_v2(title, price, area, expected):
    assert classify(title, price, area) == expected


def test_validate_and_score_nha_mini():
    assert validate("nha_mini", 3_500_000) == (True, None)
    assert validate("nha_mini", 500_000)[0] is False
    # nhà mini được cộng điểm "đúng loại chỗ ở" như phòng trọ — không tụt hạng sau khi phân loại lại
    args = (False, "medium", ["x"], "m" * 60, "Ninh Kiều")
    assert score("nha_mini", *args) == score("phong_tro", *args)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Pass trọ full nội thất đường Nguyễn Văn Cừ", "lease_transfer"),
        ("Mình cần pass phòng giá 2tr2", "lease_transfer"),
        ("Sang nhượng phòng trọ gần ĐHCT", "lease_transfer"),
        ("Cho thuê phòng trọ giá rẻ gần CTU", None),
    ],
)
def test_detect_offer_kind(title, expected):
    assert detect_offer_kind(title) == expected


# ── Lọc loại chỗ ở ──
def test_build_filters_housing():
    where_all, _ = build_filters(SearchParams())
    assert "listing_type IN ('phong_tro', 'nha_mini')" in where_all
    where_mini, _ = build_filters(SearchParams(housing=HousingType.nha_mini))
    assert "listing_type = 'nha_mini'" in where_mini and "source <> 'user'" in where_mini
    where_room, _ = build_filters(SearchParams(housing=HousingType.phong_tro))
    assert "listing_type = 'phong_tro'" in where_room


def test_housing_param_rejects_unknown_type():
    assert client.get("/listings", params={"housing": "khac"}).status_code == 422


# ── DB helpers ──
def _insert_listing(source: str, lat: float, lng: float, **cols) -> int:
    values = {
        "title": "Phòng trọ test map v2", "price": 2_000_000, "area": 20.0, "source": source,
        "source_id": uuid4().hex[:12], "cleaning_status": "cleaned", "listing_type": "phong_tro",
        "geocode_confidence": "high", "is_imputed_area": False, "quality_score": 0.5,
    }
    values.update(cols)
    names = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    with engine.begin() as conn:
        return conn.execute(
            text(
                f"INSERT INTO aggregated_listings ({names}, geom) VALUES ({params}, "
                "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)) RETURNING id"
            ),
            {**values, "lat": lat, "lng": lng},
        ).scalar_one()


def _cleanup(source: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM aggregated_listings WHERE source = :s"), {"s": source})


def _row(listing_id: int) -> dict:
    with engine.connect() as conn:
        return dict(conn.execute(
            text("SELECT * FROM aggregated_listings WHERE id = :id"), {"id": listing_id}
        ).mappings().one())


# ── Nhãn toạ độ dùng chung (điểm mặc định của phường) ──
def test_mark_shared_coords_downgrades_only_shared_points():
    src = f"t_{uuid4().hex[:8]}"
    try:
        a = _insert_listing(src, 10.014643, 105.76153)
        b = _insert_listing(src, 10.014643, 105.76153)
        pinned = _insert_listing(src, 10.0412, 105.7801)
        assert ListingRepo(engine).mark_shared_coords(src) == 2
        assert _row(a)["geocode_confidence"] == "medium"
        assert _row(b)["geocode_confidence"] == "medium"
        assert _row(pinned)["geocode_confidence"] == "high"
    finally:
        _cleanup(src)


# ── Phân loại lại tin đã làm sạch ──
def test_reclassify_keeps_imputed_area_flag():
    src = f"t_{uuid4().hex[:8]}"
    try:
        mini = _insert_listing(src, 10.03, 105.77, title="Cho thuê Minihouse KDC 91B full nội thất",
                               price=3_800_000, area=30.0, listing_type="khac", quality_score=0.4)
        # area 30 là số IMPUTE — luật dự phòng giá/diện tích không được dùng nó
        imputed = _insert_listing(src, 10.03, 105.77, title="Cho thuê chỗ ở thoáng mát",
                                  price=2_000_000, area=30.0, listing_type="khac",
                                  is_imputed_area=True, quality_score=0.4)
        reclassify(engine, apply=True)
        m = _row(mini)
        assert m["listing_type"] == "nha_mini"
        # 0,30 đúng loại chỗ ở + 0,20 diện tích thật + 0,20 toạ độ high (không ảnh/mô tả/quận)
        assert m["quality_score"] == pytest.approx(0.7)
        i = _row(imputed)
        assert i["listing_type"] == "khac"
        assert i["is_imputed_area"] is True
    finally:
        _cleanup(src)


# ── Nạp gói Chợ Tốt ──
def _catalog_row(**overrides) -> dict:
    row = {
        "source_id": f"9{uuid4().int % 10**8:08d}", "source": "chotot",
        "source_url": "https://www.chotot.com/134979386.htm",
        "title": "Phòng trọ 1.8tr/tháng, gác rộng, giờ tự do",
        "description": "Phòng có gác, điện 4k, nước 100k/người.\n[Liên hệ qua nguồn]",
        "price": 1_800_000, "area": None, "address": "Đường 3/2, Phường Hưng Lợi, Quận Ninh Kiều, Cần Thơ",
        "district": "Quận Ninh Kiều", "images": ["https://cdn.chotot.com/a.jpg"],
        "latitude": 10.014643, "longitude": 105.76153, "offer_kind": "rental",
        "first_seen": None, "last_seen": None, "seller_metadata_status": "OBSERVED",
        "seller_metadata": {"observed_at": "2026-10-01T13:23:42.395905+00:00"},
    }
    row.update(overrides)
    return row


def test_catalog_row_mapping():
    n = import_catalog.row_to_listing(_catalog_row())
    assert n.source == "nhatot" and n.district == "Ninh Kiều"
    assert n.area is None  # gói để NULL khi không có số đo — không tự điền
    assert n.lat == pytest.approx(10.014643) and n.geocode_confidence == "high"
    first, last = import_catalog.observed_at(_catalog_row())
    assert last is not None and last.isoformat().startswith("2026-10-01")
    assert import_catalog.observed_at(
        _catalog_row(seller_metadata_status="NOT_FOUND", seller_metadata=None)
    ) == (None, None)


def test_import_rows_inserts_new_only_and_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "ors_api_key", "")  # không gọi ORS thật trong test
    new = _catalog_row(title="Pass trọ full nội thất đường Nguyễn Văn Cừ", offer_kind="lease_transfer")
    gone = _catalog_row(seller_metadata_status="NOT_FOUND", seller_metadata=None)
    sid_existing = f"8{uuid4().int % 10**8:08d}"
    existing_id = _insert_listing("nhatot", 10.02, 105.77, source_id=sid_existing,
                                  description="mô tả cũ đã trích extras")
    try:
        stats = import_catalog.import_rows(
            engine, [new, gone, _catalog_row(source_id=sid_existing)], apply=True
        )
        assert stats["inserted"] == 1 and stats["existing"] == 1 and stats["no_evidence"] == 1
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT * FROM aggregated_listings WHERE source = 'nhatot' AND source_id = :s"
            ), {"s": new["source_id"]}).mappings().one()
        assert row["offer_kind"] == "lease_transfer"
        assert row["cleaning_status"] == "cleaned" and row["listing_type"] == "phong_tro"
        assert row["last_seen"].isoformat().startswith("2026-10-01")  # không phải now()
        assert _row(existing_id)["description"] == "mô tả cũ đã trích extras"  # không ghi đè

        again = import_catalog.import_rows(engine, [new], apply=True)
        assert again["inserted"] == 0 and again["existing"] == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM aggregated_listings WHERE source = 'nhatot' AND source_id = ANY(:ids)"
            ), {"ids": [new["source_id"], gone["source_id"], sid_existing]})


# ── Tiện ích OSM ──
def test_category_of_and_query():
    assert category_of({"amenity": "marketplace"}) == "cho"
    assert category_of({"shop": "convenience"}) == "sieu_thi"
    assert category_of({"highway": "bus_stop"}) == "xe_buyt"
    assert category_of({"amenity": "cafe"}) is None
    q = overpass_query((9.96, 105.68, 10.10, 105.84))
    assert '["amenity"~"^(marketplace)$"](9.96,105.68,10.1,105.84)' in q
    assert q.strip().endswith("out center tags;")


def test_to_items_and_sql():
    data = {"elements": [
        {"type": "node", "id": 1, "lat": 10.03, "lon": 105.77,
         "tags": {"amenity": "pharmacy", "name": "Nhà thuốc Long Châu", "phone": "0900"}},
        {"type": "way", "id": 2, "center": {"lat": 10.04, "lon": 105.78},
         "tags": {"amenity": "marketplace", "name": "Chợ Xuân Khánh"}},
        {"type": "node", "id": 3, "lat": 10.0, "lon": 105.7, "tags": {"amenity": "cafe"}},
    ]}
    items = to_items(data)
    assert [(i["osm_type"], i["category"]) for i in items] == [("node", "nha_thuoc"), ("way", "cho")]
    assert "phone" not in items[0]["tags"]  # chỉ giữ tag cần hiển thị
    sql = to_sql(items)
    assert sql.count("ST_MakePoint") == 2 and "ON CONFLICT (osm_type, osm_id) DO NOTHING" in sql


def test_poi_endpoints():
    osm_id = uuid4().int % 10**12
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO pois (osm_type, osm_id, category, name, geom) VALUES "
            "('node', :a, 'cho', 'Chợ test', ST_SetSRID(ST_MakePoint(105.7700, 10.0330), 4326)), "
            "('node', :b, 'cho', 'Chợ xa', ST_SetSRID(ST_MakePoint(105.7900, 10.0500), 4326))"
        ), {"a": osm_id, "b": osm_id + 1})
    try:
        r = client.get("/pois/summary", params={"lat": 10.0322, "lng": 105.7683, "radius": 500})
        assert r.status_code == 200, r.text
        cho = next(c for c in r.json()["categories"] if c["category"] == "cho")
        assert cho["count"] >= 1 and cho["nearest"]["distance_m"] < 500
        assert len(r.json()["categories"]) == 6  # nhóm 0 cái vẫn trả về

        near = client.get("/pois", params={"lat": 10.0322, "lng": 105.7683, "radius": 500,
                                           "category": "cho"}).json()
        names = [p["name"] for p in near]
        assert "Chợ test" in names and "Chợ xa" not in names
        assert client.get("/pois", params={"lat": 10, "lng": 105, "category": "x"}).status_code == 422
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM pois WHERE osm_id IN (:a, :b)"), {"a": osm_id, "b": osm_id + 1})


# ── Cache đường đi ──
def test_route_endpoint_serves_cache_without_ors(monkeypatch):
    monkeypatch.setattr(settings, "ors_api_key", "")
    src = f"t_{uuid4().hex[:8]}"
    lat, lng = 10.012345, 105.712345
    listing_id = _insert_listing(src, lat, lng)
    path = [[10.0322, 105.7683], [lat, lng]]
    try:
        RouteCacheRepo(engine).put(lat, lng, 1, PROFILE, path)
        r = client.get(f"/listings/{listing_id}/route", params={"campus": 1})
        assert r.status_code == 200, r.text
        assert r.json() == path
        # khu chưa có trong cache + không có key ORS → dự phòng OSRM (giả lập, không gọi mạng trong test)
        from app.listings import router as lr

        async def fake_osrm(origin, dest):
            return [[origin[0], origin[1]], [dest[0], dest[1]]]

        monkeypatch.setattr(lr, "route_geometry_osrm", fake_osrm)
        r2 = client.get(f"/listings/{listing_id}/route", params={"campus": 2})
        assert r2.status_code == 200 and r2.json()[-1] == [lat, lng]
        assert RouteCacheRepo(engine).get(lat, lng, 2, "osrm-driving") is not None  # đã lưu cache riêng

        async def broken(origin, dest):
            raise RuntimeError("down")

        monkeypatch.setattr(lr, "route_geometry_osrm", broken)
        assert client.get(f"/listings/{listing_id}/route", params={"campus": 0}).status_code == 502
    finally:
        _cleanup(src)
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM route_cache WHERE origin_lat = round(CAST(:lat AS NUMERIC), 5) "
                "AND origin_lng = round(CAST(:lng AS NUMERIC), 5)"
            ), {"lat": lat, "lng": lng})


def test_contact_endpoint_phone_or_source_and_not_in_bulk_listing():
    src = f"t_{uuid4().hex[:8]}"
    with_phone = _insert_listing(src, 10.05, 105.77, contact_phone="0900000001", source_url="https://x.vn/1")
    no_phone = _insert_listing(src, 10.051, 105.771, source_url="https://www.nhatot.com/123.htm")
    try:
        a = client.get(f"/listings/{with_phone}/contact").json()
        assert a["phone"] == "0900000001" and a["source_url"] == "https://x.vn/1"
        b = client.get(f"/listings/{no_phone}/contact").json()
        assert b["phone"] is None and b["source_url"].startswith("https://www.nhatot.com")
        # số không lộ qua API chi tiết / danh sách
        assert "contact_phone" not in client.get(f"/listings/{with_phone}").json()
        with engine.begin() as conn:
            conn.execute(text("UPDATE aggregated_listings SET status='hidden' WHERE id=:i"), {"i": with_phone})
        assert client.get(f"/listings/{with_phone}/contact").status_code == 404
    finally:
        _cleanup(src)

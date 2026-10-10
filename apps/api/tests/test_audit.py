"""Rà soát chất lượng (app.cleaner.audit): luật offline giữ tin sạch, loại tin vị trí cấp phường/tin mẫu/ngoài phạm vi."""
from datetime import datetime, timezone

from app.cleaner.audit import offline_reasons, street_matches


def row(i, **kw):
    base = dict(id=i, source="nhatot", source_id=str(i), source_url="", title=f"Phòng {i}", price=2_000_000,
                listing_type="phong_tro", images=["a", "b", "c"], description="x" * 120, street=f"{i} Đường Mậu Thân",
                address="Ninh Kiều", address_confidence="street", geocode_confidence="high",
                last_seen=datetime(2026, 9, 30, tzinfo=timezone.utc), offer_kind=None,
                lat=10.040 + i * 0.001, lng=105.775)
    base.update(kw)
    return base


def test_clean_pinned_listing_is_kept():
    assert offline_reasons([row(1)]) == {}


def test_each_dirty_rule():
    rows = [
        row(1, images=["https://images.unsplash.com/x.jpg"] * 3),
        row(2, lat=None, lng=None),
        row(3, lat=10.0109, lng=105.6706),                       # Phong Điền, ~10 km
        row(4, geocode_confidence="medium"),
        row(5, lat=10.0159, lng=105.7656),                       # trùng tâm khu I
        row(6, source="phongtro123", address_confidence="street"),  # nguồn HTML không có số nhà
        row(7, price=500_000),
        row(8, images=["a"]),
        row(9, offer_kind="lease_transfer"),
    ]
    assert offline_reasons(rows) == {
        1: "tin_mau", 2: "khong_toa_do", 3: "ngoai_pham_vi", 4: "vi_tri_cap_phuong", 5: "vi_tri_cap_phuong",
        6: "vi_tri_cap_phuong", 7: "gia_bat_thuong", 8: "thieu_thong_tin", 9: "sang_nhuong",
    }


def test_shared_point_with_different_addresses_is_ward_level_but_same_address_is_ok():
    pt = dict(lat=10.0146, lng=105.7615)
    shared = [row(1, street="117 Đường 3/2", **pt), row(2, street="Hẻm 51 Đường 3/2", **pt)]
    assert set(offline_reasons(shared).values()) == {"vi_tri_cap_phuong"}
    same_house = [row(1, street="117 Đường 3/2", **pt), row(2, title="Phòng 2 cùng nhà", street="117 Đường 3/2", **pt)]
    assert offline_reasons(same_house) == {}


def test_duplicate_keeps_listing_with_more_images():
    a = row(1, title="Phòng đẹp gần CTU", images=["a", "b", "c"])
    b = row(2, title="Phòng  đẹp gần ctu", images=["a", "b", "c", "d"])
    assert offline_reasons([a, b]) == {1: "trung_lap"}


def test_street_matching():
    assert street_matches("108/31 Đường Cách Mạng Tháng 8", "Cách Mạng Tháng 8")
    assert street_matches("Hẻm 309, Đường Hoàng Quốc Việt", "Hoàng Quốc Việt")
    assert not street_matches("Đường Vườn Mận", "Tạ Thị Phi")
    assert not street_matches("Đường Nguyễn Trãi", None)


def test_system_policy_keeps_imprecise_but_still_drops_dirty():
    from app.cleaner.audit import imprecise_ids

    rows = [
        row(1, geocode_confidence="medium"),                     # tin thật, toạ độ cấp phường → GIỮ, đánh dấu
        row(2, geocode_confidence="medium", images=["a"]),       # cấp phường + thiếu ảnh → vẫn LOẠI vì thiếu ảnh
        row(3),                                                  # chính xác
    ]
    assert offline_reasons(rows, keep_imprecise=True) == {2: "thieu_thong_tin"}
    assert imprecise_ids(rows) == {1, 2}
    assert offline_reasons(rows) == {1: "vi_tri_cap_phuong", 2: "thieu_thong_tin"}  # strict


def test_survey_source_is_precise_and_exempt_from_photo_rule():
    from app.cleaner.audit import imprecise_ids

    survey = row(1, source="survey", images=[], description="Giờ giấc tự do, điện 4k, nước 15k",
                 address_confidence="street")
    scraped = row(2, source="phongtro123", images=[], description="x" * 120, address_confidence="exact")
    assert offline_reasons([survey, scraped]) == {2: "thieu_thong_tin"}
    assert imprecise_ids([survey]) == set()

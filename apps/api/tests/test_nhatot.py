import json
from pathlib import Path

from app.crawler.nhatot import ad_to_listing, _address

FIX = Path(__file__).parent / "fixtures" / "nhatot_ad.json"


def _ad():
    return json.loads(FIX.read_text(encoding="utf-8"))["ads"][0]


def test_map_core_fields():
    n = ad_to_listing(_ad())
    assert n.source == "nhatot" and n.source_id == "133867371"
    assert n.source_url == "https://www.nhatot.com/133867371.htm"
    assert n.price == 2_000_000 and n.area == 12.0
    assert n.district == "Ninh Kiều"
    assert n.address == "85/26 Đường Phạm Ngũ Lão, Phường Thới Bình, Quận Ninh Kiều, Cần Thơ"
    assert len(n.images) == 2
    assert n.content_hash


def test_map_real_coordinates_high_confidence():
    n = ad_to_listing(_ad())
    assert n.geocode_confidence == "high"
    assert abs(n.lat - 10.045173) < 1e-6 and abs(n.lng - 105.77522) < 1e-6
    assert 1000 < n.distance_to_ctu < 3000  # ~1.8 km tới khu II


def test_map_extras_and_deposit_field_priority():
    n = ad_to_listing(_ad())
    ex = n.extras
    assert ex["deposit_amount"] == 2_000_000       # field `deposit` thắng regex
    assert ex["electricity_price"] == 3500
    assert ex["water_price"] == 20_000 and ex["water_unit"] == "person"
    assert ex["gender_only"] == "nu"
    assert ex["free_hours"] is True


def test_bad_coordinates_fall_back_to_geocode():
    ad = _ad()
    ad["latitude"], ad["longitude"] = 21.0, 105.8   # Hà Nội — ngoài bbox Cần Thơ
    n = ad_to_listing(ad)
    assert n.geocode_confidence == "failed" and n.lat is None


def test_address_without_street_number():
    ad = _ad()
    ad["street_number"] = ""
    assert _address(ad) == "Đường Phạm Ngũ Lão, Phường Thới Bình, Quận Ninh Kiều, Cần Thơ"

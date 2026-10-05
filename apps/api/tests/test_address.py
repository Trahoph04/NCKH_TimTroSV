from app.crawler.address import (
    canon_district,
    canon_ward,
    compose,
    extract_street,
    normalize_address,
)


def test_district_variants_collapse_to_one():
    for raw in ["Ninh Kiều", "Quận Ninh Kiều, Cần Thơ", "Ninh Kieu",
                "Quận Ninh Kiều , Thành phố Cần Thơ", "q ninh kieu"]:
        assert canon_district(raw) == "Ninh Kiều", raw
    # 'Bình Thuỷ' và 'Bình Thủy' là một
    assert canon_district("Quận Bình Thuỷ, Cần Thơ") == "Bình Thủy"
    assert canon_district("Quận Bình Thủy") == "Bình Thủy"
    assert canon_district("Quận 1, TP HCM") is None


def test_ward():
    assert canon_ward("Phường Xuân Khánh, Ninh Kiều") == "Xuân Khánh"
    assert canon_ward("P. An Hòa") == "An Hòa"
    assert canon_ward("gần hồ Bún Xáng, hưng lợi") == "Hưng Lợi"
    assert canon_ward("Phòng trọ đẹp") is None


def test_street_with_keyword():
    assert extract_street("85/26 Đường Phạm Ngũ Lão") == "85/26 Đường Phạm Ngũ Lão"
    assert extract_street("phòng trọ hẻm 51 đường 3/2") == "Hẻm 51 Đường 3/2"


def test_street_without_keyword():
    assert extract_street("Hẻm 22 Nguyễn Văn Cừ nối dài, An Bình") == "Hẻm 22 Nguyễn Văn Cừ nối dài"
    assert extract_street("Địa chỉ: 12 Trần Việt Châu") == "12 Trần Việt Châu"
    assert extract_street("Phòng 20m2 giá rẻ gần trường") is None


def test_compose_full():
    assert compose("85/26 Đường Phạm Ngũ Lão", "Thới Bình", "Ninh Kiều") == (
        "85/26 Đường Phạm Ngũ Lão, P. Thới Bình, Q. Ninh Kiều, Cần Thơ"
    )
    assert compose(None, None, None) is None


def test_confidence_ladder():
    assert normalize_address("85/26 Đường Phạm Ngũ Lão, Phường Thới Bình, Quận Ninh Kiều, Cần Thơ")[
        "address_confidence"] == "exact"
    assert normalize_address(None, "Ninh Kiều", None, "Trọ gần bến xe")[
        "address_confidence"] == "district"
    assert normalize_address(None, None, "Cho thuê phòng", "Giá rẻ, thoáng mát")[
        "address_confidence"] == "none"


def test_full_pipeline_fields():
    a = normalize_address("85/26 Đường Phạm Ngũ Lão, Phường Thới Bình, Quận Ninh Kiều, Cần Thơ")
    assert a["street"] == "85/26 Đường Phạm Ngũ Lão"
    assert a["ward"] == "Thới Bình"
    assert a["district_norm"] == "Ninh Kiều"
    assert a["address_source"] == "source"

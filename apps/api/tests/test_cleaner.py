from app.cleaner.pipeline import classify, normalize_title, resolve_area, score, validate


# ── T1: classify ──
def test_classify_phong_tro_explicit():
    assert classify("Cho thuê phòng trọ giá rẻ gần CTU", 2_000_000, 20) == "phong_tro"


def test_classify_nha_tro_edge_case():
    # "nhà trọ" phải rơi vào phong_tro, KHÔNG phải nha_nguyen_can
    assert classify("Nhà trọ gần CTU giá rẻ", 2_000_000, 20) == "phong_tro"


def test_classify_mat_bang():
    assert classify("Cho thuê mặt bằng kinh doanh mặt tiền", 15_000_000, 80) == "mat_bang"


def test_classify_nha_nguyen_can_keyword():
    assert classify("Nhà nguyên căn mặt tiền đường lớn", 8_000_000, 70) == "nha_nguyen_can"


def test_classify_nha_nguyen_can_by_price_area():
    assert classify("Cho thuê chỗ ở đẹp thoáng mát", 8_000_000, 80) == "nha_nguyen_can"


def test_classify_phong_tro_by_price_area():
    assert classify("Cho thuê chỗ ở đẹp thoáng mát", 2_000_000, 20) == "phong_tro"


def test_classify_khac_default():
    assert classify("Sang nhượng gấp giá tốt", 5_000_000, 45) == "khac"


def test_classify_survey_name_only_title_is_phong_tro():
    # tin khảo sát chỉ có tên trọ, không đo diện tích — nguồn khác vẫn 'khac'
    assert classify("TT HOME – 3/2 ĐOẠN GẦN CẦU ĐẦU SẤU", 2_400_000, None, "survey") == "phong_tro"
    assert classify("TT HOME – 3/2 ĐOẠN GẦN CẦU ĐẦU SẤU", 2_400_000, None, "nhatot") == "khac"
    # luật theo tiêu đề vẫn thắng
    assert classify("MINIHOUSE KDC 91B", 2_500_000, None, "survey") == "nha_mini"


# ── T2: validate ──
def test_validate_phong_tro_valid():
    assert validate("phong_tro", 5_000_000) == (True, None)


def test_validate_phong_tro_invalid_too_high():
    is_valid, reason = validate("phong_tro", 12_000_000)
    assert is_valid is False
    assert reason == "Giá ngoài khoảng phòng trọ"


def test_validate_nha_nguyen_can_valid():
    assert validate("nha_nguyen_can", 12_000_000) == (True, None)


def test_validate_none_price():
    is_valid, reason = validate("phong_tro", None)
    assert is_valid is False
    assert reason == "Thiếu giá"


def test_validate_mat_bang_out_of_range():
    is_valid, reason = validate("mat_bang", 500_000)
    assert is_valid is False
    assert reason == "Giá ngoài khoảng nhà/mặt bằng"


def test_validate_khac_valid():
    assert validate("khac", 1_000_000) == (True, None)


def test_validate_khac_invalid():
    is_valid, reason = validate("khac", 25_000_000)
    assert is_valid is False
    assert reason == "Giá bất thường"


# ── T3: resolve_area ──
def test_resolve_area_given():
    assert resolve_area(25, 2_000_000, None) == (25, False)


def test_resolve_area_from_description():
    area, is_imputed = resolve_area(None, 2_000_000, "Phòng đẹp, diện tích 18m2, có gác")
    assert area == 18
    assert is_imputed is False


def test_resolve_area_imputed_from_price():
    area, is_imputed = resolve_area(None, 1_200_000, "Không có mô tả diện tích")
    assert area == 20
    assert is_imputed is True


def test_resolve_area_zero_area_falls_through():
    # area=0 coi như thiếu, phải rơi qua nhánh regex/impute
    area, is_imputed = resolve_area(0, None, None)
    assert area == 0.0
    assert is_imputed is True


# ── T4: normalize_title ──
def test_normalize_title_kept_when_long_enough():
    title = "Cho thuê phòng trọ giá rẻ gần CTU"
    assert normalize_title(title, "phong_tro", 20, "Ninh Kiều") == title


def test_normalize_title_generated_when_short():
    result = normalize_title("Rẻ", "phong_tro", 20, "Ninh Kiều")
    assert result == "Phòng trọ 20m² tại Ninh Kiều"


def test_normalize_title_generated_when_empty():
    result = normalize_title("", "nha_nguyen_can", 70, None)
    assert result == "Nhà nguyên căn 70m² tại Cần Thơ"


def test_normalize_title_mat_bang_label():
    result = normalize_title(None, "mat_bang", 80, "Cái Răng")
    assert result == "Mặt bằng 80m² tại Cái Răng"


def test_normalize_title_khac_label():
    result = normalize_title("  ", "khac", 40, None)
    assert result == "Chỗ ở 40m² tại Cần Thơ"


# ── T5: score ──
def test_score_perfect_phong_tro():
    q = score(
        listing_type="phong_tro",
        is_imputed_area=False,
        geocode_confidence="high",
        images=["a.jpg"],
        description="Phòng trọ rộng rãi, đầy đủ nội thất, gần trường đại học Cần Thơ, an ninh tốt.",
        district="Ninh Kiều",
    )
    assert q == 1.0


def test_score_low_mat_bang():
    q = score(
        listing_type="mat_bang",
        is_imputed_area=True,
        geocode_confidence="low",
        images=[],
        description="",
        district=None,
    )
    assert q == 0.0


def test_score_clamped_to_one():
    q = score(
        listing_type="phong_tro",
        is_imputed_area=False,
        geocode_confidence="high",
        images=["a.jpg", "b.jpg"],
        description="A" * 100,
        district="Bình Thủy",
    )
    assert q <= 1.0


def test_score_district_khong_ro_no_bonus():
    q = score(
        listing_type="khac",
        is_imputed_area=True,
        geocode_confidence=None,
        images=None,
        description=None,
        district="Không rõ",
    )
    assert q == 0.0

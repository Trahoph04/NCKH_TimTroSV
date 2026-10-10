from app.crawler.extras import extract_extras


def test_dien_nuoc_k_style():
    e = extract_extras("Phòng 20m2, điện 3k5/kw, nước 20k/người, cọc 1 tháng")
    assert e.electricity_price == 3500
    assert e.water_price == 20_000 and e.water_unit == "person"
    assert e.deposit_months == 1.0 and e.deposit_amount is None


def test_dien_nuoc_dot_style():
    e = extract_extras("Giá điện 3.500đ/kWh, nước 15.000đ/khối. Đặt cọc 1.500.000")
    assert e.electricity_price == 3500
    assert e.water_price == 15_000 and e.water_unit == "m3"
    assert e.deposit_amount == 1_500_000


def test_dien_nuoc_range_and_month():
    e = extract_extras("Điện 4.000/số - nước 100k/tháng. Cọc 2 triệu")
    assert e.electricity_price == 4000
    assert e.water_price == 100_000 and e.water_unit == "month"
    assert e.deposit_amount == 2_000_000


def test_gia_nha_nuoc():
    e = extract_extras("Điện nước giá nhà nước, giờ giấc tự do")
    assert e.utility_state_price is True
    assert e.electricity_price is None
    assert e.free_hours is True


def test_khong_coc():
    e = extract_extras("Vào ở ngay, không cọc, không giới nghiêm")
    assert e.deposit_months == 0.0
    assert e.free_hours is True


def test_nu_only():
    for txt in [
        "Phòng trọ chỉ cho nữ thuê, gần CTU",
        "Cho thuê phòng dành cho sinh viên nữ",
        "Nhà trọ nữ, an ninh, khoá cổng 23h",
        "Ưu tiên nữ, không hút thuốc",
        "KTX nữ gần khu 2",
    ]:
        assert extract_extras(txt).gender_only == "nu", txt


def test_nam_only():
    assert extract_extras("Phòng chỉ nhận nam, ở ghép").gender_only == "nam"


def test_nam_nu_both_is_none():
    assert extract_extras("Cho thuê phòng nam nữ đều được").gender_only is None
    assert extract_extras("Nhận nam/nữ, sinh viên, người đi làm").gender_only is None


def test_gender_not_in_generic_text():
    # "Nam Kỳ Khởi Nghĩa" / tên người không được bắt nhầm
    assert extract_extras("Phòng đường Nam Kỳ Khởi Nghĩa, LH chị Nữ").gender_only is None


def test_curfew_hour():
    e = extract_extras("Khu trọ an ninh, khóa cổng lúc 23h, có camera")
    assert e.curfew_hour == 23 and e.free_hours is False


def test_curfew_midnight():
    e = extract_extras("Giới nghiêm 12h đêm")
    assert e.curfew_hour == 12 or e.curfew_hour is None  # 12h đêm mơ hồ → chấp nhận None
    assert e.free_hours is False


def test_empty():
    e = extract_extras(None, "")
    assert e.as_dict() == {k: None for k in e.as_dict()}


def test_nhatot_real_body():
    body = (
        "CHO THUÊ PHÒNG TRỌ MỚI XÂY HẺM 51 ĐƯỜNG 3/2\n"
        "- Diện tích 20m2, gác lửng, WC riêng\n"
        "- Giá 1tr8/tháng, điện 3.500/kwh, nước 60k/người/tháng\n"
        "- Cọc 1 tháng, giờ giấc tự do, chỉ nhận nữ sinh viên"
    )
    e = extract_extras(body)
    assert e.electricity_price == 3500
    assert e.water_price == 60_000 and e.water_unit == "person"
    assert e.deposit_months == 1.0
    assert e.free_hours is True
    assert e.gender_only == "nu"


def test_price_not_confused_with_electricity():
    # "điện" trong "điện thoại" + giá 1.8 triệu không được thành electricity_price
    e = extract_extras("Liên hệ điện thoại 0909xxx, giá 1.800.000/tháng")
    assert e.electricity_price is None


def test_deposit_comma_separators_does_not_crash():
    # "cọc 1,500,000" từng làm ValueError → chết cả backfill_extras
    e = extract_extras("Phòng đẹp, đặt cọc 1,500,000 khi nhận phòng")
    assert e.deposit_amount == 1_500_000


def test_deposit_malformed_number_is_skipped():
    e = extract_extras("Cọc 1.500.00 (ghi sai), phòng 20m2")
    assert e.deposit_amount is None and e.deposit_months is None


def test_unit_letter_not_glued_to_next_word():
    # "k" của "khi"/"kwh" từng bị nuốt làm đơn vị tiền → sai giá trị hoặc mất giá trị
    assert extract_extras("Đặt cọc 1,500,000 khi nhận phòng").deposit_amount == 1_500_000
    assert extract_extras("Điện 3.500 kwh, nước 15.000 khối").electricity_price == 3500
    assert extract_extras("Cọc 2 triệu khi ký hợp đồng").deposit_amount == 2_000_000


def test_free_hours_negated_management_and_own_gate_key():
    from app.crawler.extras import extract_extras

    t = "Mỗi phòng có chìa khóa cổng rào riêng. Không quản lý giờ giấc; Wf tốc độ cao"
    assert extract_extras(t).free_hours is True
    assert extract_extras("Có chìa khoá cổng riêng cho từng phòng").free_hours is None
    assert extract_extras("Khoá cổng lúc 23h").free_hours is False


def test_electricity_not_confused_with_area_or_phone():
    from app.crawler.extras import extract_extras

    t = "Diện tích: 5x5m có gác\nđiện 3.500đ/kw\nnước 10.000đ/m3"
    assert extract_extras(t).electricity_price == 3500
    assert extract_extras("Diện tích 5m x 5m, điện thoại 0909 123 456").electricity_price is None

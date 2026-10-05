from app.crawler.contact import Contact, extract_contact, find_phones, normalize_phone


def test_normalize_mobile_formats():
    for raw in ["0909123456", "0909.123.456", "0909 123 456", "+84 909 123 456",
                "84909123456", "(0909) 123-456"]:
        assert normalize_phone(raw) == "0909123456", raw


def test_normalize_landline_cantho():
    assert normalize_phone("0292 3831 530") == "02923831530"


def test_reject_invalid():
    assert normalize_phone("012345") is None          # quá ngắn
    assert normalize_phone("0123456789") is None      # đầu số không tồn tại
    assert normalize_phone("1800545450") is None      # không bắt đầu bằng 0
    assert normalize_phone("20000000") is None        # giá tiền, không phải SĐT


def test_masked_phone_is_skipped():
    # Chợ Tốt che số → KHÔNG được đoán, không được lấy
    assert find_phones("Liên hệ: ***") == []
    assert extract_contact("Phòng trọ", "LH: 0909 *** ***").contact_phone is None


def test_price_is_not_phone():
    c = extract_contact("Cho thuê phòng", "Giá 1.800.000/tháng, cọc 2.000.000, điện 3.500đ")
    assert c.contact_phone is None


def test_phone_zalo_facebook_name():
    c = extract_contact(
        "Phòng trọ gần CTU",
        "LH: Chị Hạnh 0909.123.456 (Zalo 0987654321). Fb: facebook.com/trosv.cantho",
        source="description",
    )
    assert c.contact_phone == "0909123456"
    assert c.contact_zalo == "0987654321"
    assert c.contact_name == "Chị Hạnh"
    assert "facebook.com/trosv.cantho" in c.contact_facebook
    assert c.contact_source == "description"


def test_two_numbers_main_and_alt():
    c = extract_contact("LH 0909123456 hoặc 0912345678")
    assert c.contact_phone == "0909123456"
    assert c.contact_phone_alt == "0912345678"


def test_ignore_site_hotline():
    # 1900... không hợp lệ sẵn; test hotline di động của trang rao vặt
    c = extract_contact("Hỗ trợ 0938888888 - phòng trọ của anh Tuấn 0912345678",
                        ignore=["0938888888"])
    assert c.contact_phone == "0912345678"


def test_name_not_from_common_words():
    assert extract_contact("Chi phí điện nước rẻ, view đẹp").contact_name is None
    assert extract_contact("Phòng có ánh sáng tự nhiên").contact_name is None


def test_empty():
    assert extract_contact(None, "").as_dict() == Contact().as_dict()

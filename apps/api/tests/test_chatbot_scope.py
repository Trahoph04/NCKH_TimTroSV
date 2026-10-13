"""Quy tắc khẩn cấp / ngoài khu vực / so sánh với kết quả trước / mức phạt / biểu giá điện (scope.py + legal_retrieval, 08/10/2026)."""
import pytest

from app.room_service.chatbot.legal_retrieval import fine_question, tariff_question, rental_electricity_question
from app.room_service.chatbot.parser import parse_query
from app.room_service.chatbot.providers import normalize_text
from app.room_service.chatbot.scope import (EMERGENCY_ANSWERS, comparative_updates, emergency_kind, out_of_area_answer,
                                            out_of_area_place)


@pytest.mark.parametrize("message,kind", [
    ("Tôi bị chủ trọ đe doạ đánh, tôi phải làm gì ngay bây giờ?", "violence"),
    ("Chủ trọ hành hung em tối qua", "violence"),
    ("Phòng trọ đang cháy, em phải làm sao?", "fire"),
    ("Nhà trọ vừa cháy lớn", "fire"),
    ("Bạn em bị điện giật ở phòng", "medical"),
    ("Em muốn chết quá", "self_harm"),
])
def test_emergency_detected(message, kind):
    assert emergency_kind(normalize_text(message)) == kind
    parsed = parse_query(message)
    assert parsed.intent == "emergency"
    assert EMERGENCY_ANSWERS[kind]


@pytest.mark.parametrize("message", [
    "Nhà trọ cần đáp ứng yêu cầu phòng cháy chữa cháy nào?",       # câu hỏi pháp lý, không phải đang có cháy
    "Điều kiện phòng cháy phòng trọ khi xem phòng là gì?",
    "Trách nhiệm của chủ trọ khi xảy ra hỏa hoạn là gì?",
    "Tìm phòng trọ dưới 2 triệu gần Đại học Cần Thơ",
    "Xe em đang chạy ổn, nhưng phòng trọ ở đâu rẻ?",
    "Bạo lực gia đình bị xử phạt thế nào?",
])
def test_emergency_not_triggered_by_legal_or_normal_questions(message):
    assert emergency_kind(normalize_text(message)) is None
    assert parse_query(message).intent != "emergency"


def test_emergency_answers_name_the_right_numbers():
    assert "113" in EMERGENCY_ANSWERS["violence"] and "115" in EMERGENCY_ANSWERS["violence"]
    assert "114" in EMERGENCY_ANSWERS["fire"] and "nhảy" in EMERGENCY_ANSWERS["fire"]
    assert "115" in EMERGENCY_ANSWERS["medical"]
    assert "115" in EMERGENCY_ANSWERS["self_harm"]


@pytest.mark.parametrize("message,place", [
    ("Tìm phòng trọ ở Hà Nội", "Hà Nội"),
    ("phòng trọ gần ĐH Bách khoa Hà Nội giá rẻ", "Hà Nội"),
    ("Tìm phòng ở TP.HCM dưới 3 triệu", "TP. Hồ Chí Minh"),
    ("có phòng nào ở Đà Nẵng không", "Đà Nẵng"),
])
def test_out_of_area_detected(message, place):
    assert out_of_area_place(normalize_text(message)) == place
    assert parse_query(message).intent == "out_of_area"
    assert place in out_of_area_answer(place)


@pytest.mark.parametrize("message", [
    "Em ở Hà Nội xuống Cần Thơ học, tìm phòng ở Ninh Kiều",     # có nhắc Cần Thơ ⇒ tìm bình thường
    "Nhà trọ Hà Ngọc giá bao nhiêu",                           # "Hà Ngọc" không phải "Hà Nội"
    "Phòng trọ ở Sóc Trăng gần cơ sở Đại học Cần Thơ",         # Sóc Trăng/Hậu Giang nay thuộc TP. Cần Thơ
    "Tìm phòng trọ ở Hậu Giang",
    "Tìm phòng trọ dưới 2 triệu",
])
def test_out_of_area_not_triggered(message):
    assert out_of_area_place(normalize_text(message)) is None
    assert parse_query(message).intent != "out_of_area"


def test_comparative_updates_use_only_shown_numbers():
    shown = {"min_price": 1_000_000, "min_distance": 800.0, "max_area": 20.0}
    cheaper = comparative_updates("Còn phòng nào rẻ hơn không?", shown)
    assert cheaper == {"max_price": 1_000_000, "max_price_exclusive": True, "min_price": None}
    assert comparative_updates("phòng nào gần hơn", shown) == {"max_distance_ctu": 799.0}
    assert comparative_updates("có phòng rộng hơn không", shown) == {"min_area": 20.1}
    assert comparative_updates("Còn phòng nào rẻ hơn không?", {}) == {}          # lượt đầu, chưa có gì để so
    assert comparative_updates("Tìm phòng có máy lạnh", shown) == {}              # không phải câu so sánh


def test_fine_question_is_narrow():
    assert fine_question("Mức phạt khi chủ trọ không đăng ký tạm trú là bao nhiêu?")
    assert fine_question("Nếu tôi không đăng ký tạm trú thì bị phạt bao nhiêu?")
    assert not fine_question("Hoàn trả tiền cọc khi trả phòng như thế nào?")       # có "hoàn trả" nhưng không hỏi mức phạt
    assert not fine_question("Giá điện sinh hoạt bậc 1 là bao nhiêu?")


def test_tariff_vs_rental_electricity():
    assert tariff_question("Giá điện sinh hoạt bậc 1 hiện nay là bao nhiêu đồng một kWh?")
    assert not rental_electricity_question("Giá điện sinh hoạt bậc 1 hiện nay là bao nhiêu đồng một kWh?")
    # câu hỏi về cách chủ trọ thu tiền điện vẫn là nhánh người thuê nhà
    for q in ("Chủ trọ được thu tiền điện của người thuê như thế nào theo quy định?",
              "Chủ trọ thu điện 4.000 đồng/kWh có đúng không?"):
        assert rental_electricity_question(q) and not tariff_question(q)



def test_deposit_disputes_are_legal_questions_not_listing_search():
    from app.room_service.chatbot.parser import parse_query
    for q in ("Chủ trọ giữ cọc không trả thì sao?", "Chủ trọ không trả lại tiền cọc phải làm sao?",
              "Trả phòng sớm có được hoàn cọc không?", "Bị mất cọc khi chuyển đi trước hạn"):
        assert parse_query(q).intent == "legal_question", q
    # tìm phòng có nhắc mức cọc vẫn là tìm phòng
    assert parse_query("Phòng dưới 2 triệu cọc 1 tháng gần CTU").intent == "find_listing"



def test_deposit_question_expands_to_civil_code_terms():
    from app.room_service.chatbot.legal_retrieval import expand_legal_query
    expanded = expand_legal_query("Chủ trọ giữ cọc không trả thì sao?")
    assert "tài sản đặt cọc" in expanded and "bên nhận đặt cọc" in expanded

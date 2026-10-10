from __future__ import annotations

import re
from dataclasses import dataclass

from .providers import normalize_text
from .schemas import ChatFilters
from .scope import emergency_kind, out_of_area_place
from .topics import has_phrase, question_categories


DISTRICTS = {
    "ninh kieu": "Ninh Kiều",
    "cai rang": "Cái Răng",
    "binh thuy": "Bình Thủy",
    "o mon": "Ô Môn",
    "thot not": "Thốt Nốt",
    "phong dien": "Phong Điền",
    "co do": "Cờ Đỏ",
    "thoi lai": "Thới Lai",
    "vinh thanh": "Vĩnh Thạnh",
}

# Key = parsed_amenities của crawler repo này (crawler/normalize.parse_amenities), KHÁC catalog branch PHUC
# (private_bathroom/refrigerator/flexible_hours). "gác", "nuôi thú cưng" không có cột ⇒ không lọc cứng
# (lọc theo key không tồn tại = 0 kết quả); BM25 trên mô tả vẫn bắt được 2 từ này.
AMENITIES = {
    "may lanh": "air_conditioner",
    "dieu hoa": "air_conditioner",
    "wifi": "wifi",
    "wi fi": "wifi",
    "internet": "wifi",
    "cho de xe": "parking",
    "giu xe": "parking",
    "wc rieng": "private_wc",
    "ve sinh rieng": "private_wc",
    "toilet rieng": "private_wc",
    "tu lanh": "fridge",
    "may giat": "washing_machine",
    "bep": "kitchen",
    "gio giac tu do": "free_hours",
    "gio tu do": "free_hours",
    "ban cong": "balcony",
}


@dataclass(frozen=True)
class ParsedQuery:
    intent: str
    filters: ChatFilters
    confidence: float


def _money(value: str, unit: str | None) -> int:
    number = float(value.replace(",", "."))
    if unit in {"tr", "trieu"}:
        return int(number * 1_000_000)
    if unit in {"k", "nghin", "ngan"}:
        return int(number * 1_000)
    return int(number)


def _prices(text: str) -> tuple[int | None, int | None]:
    # Remove measurements before parsing budgets. Without this guard, the `k`
    # in `2 km` can be misread as two thousand đồng.
    text = re.sub(
        r"\d+(?:[\.,]\d+)?\s*(?:km|m2|m vuong|m|phut)\b",
        " ",
        text,
    )
    pattern = r"(\d+(?:[\.,]\d+)?)\s*(trieu|tr|k|nghin|ngan|dong)?"
    between = re.search(rf"(?:tu|khoang)\s+{pattern}\s+(?:den|toi|-)\s+{pattern}", text)
    if between:
        left_unit = between.group(2) or between.group(4)
        right_unit = between.group(4) or between.group(2)
        return _money(between.group(1), left_unit), _money(between.group(3), right_unit)
    max_match = re.search(rf"(?:duoi|khong qua|toi da|tam|<=)\s*{pattern}", text)
    min_match = re.search(rf"(?:tren|toi thieu|it nhat|>=)\s*{pattern}", text)
    min_price = _money(min_match.group(1), min_match.group(2)) if min_match else None
    max_price = _money(max_match.group(1), max_match.group(2)) if max_match else None
    if min_price is None and max_price is None:
        budget = re.search(r"(\d+(?:[\.,]\d+)?)\s*(trieu|tr|k|nghin|ngan)\b", text)
        if budget:
            max_price = _money(budget.group(1), budget.group(2))
    return min_price, max_price


def parse_query(message: str) -> ParsedQuery:
    text = normalize_text(message)
    # Khẩn cấp ưu tiên TUYỆT ĐỐI, trước cả nhận diện "tìm phòng"/"pháp lý" (xem scope.py)
    if emergency_kind(text):
        return ParsedQuery("emergency", ChatFilters(), 0.99)
    # Basic tenant support does not compose documents or perform legal filing.
    drafting = any(has_phrase(text,t) for t in ('soan','soan thao','viet giup','viet cho','tao mau','dien ho','dien giup','lam giup'))
    documents = any(has_phrase(text,t) for t in ('hop dong','to khai','don khoi kien','don to cao','don to giac','ho so'))
    if (drafting and documents) or any(has_phrase(text,t) for t in ('mau to khai','mau hop dong','huong dan dien to khai','dien mau ct01')):
        return ParsedQuery('out_of_scope', ChatFilters(), 0.98)
    housing_terms = ("phong", "tro", "nha", "thue", "cho o", "can ho", "mat bang", "ctu", "truong")
    legal_terms = (
        "luat", "nghi dinh", "thong tu", "quyet dinh",
        "hop dong", "dat coc", "tam tru", "cu tru", "tranh chap", "khieu nai",
        "phong chay", "pccc", "gia dien", "tien dien", "thu dien", "kwh", "dinh muc dien", "gia nuoc", "tien nuoc",
        "quyen cua nguoi thue", "nghia vu", "xu phat", "boi thuong", "don phuong cham dut",
    )
    out_terms = ("thoi tiet", "bong da", "lap trinh", "chung khoan", "nau an", "tin tuc")
    detail_followup = any(has_phrase(text, term) for term in ("phong do", "tin vua", "phong vua", "cac tin vua"))
    if (question_categories(message) or any(has_phrase(text, term) for term in legal_terms)
            or re.search(r"\b(?:dieu|khoan)\s+\d+\b", text)) and not detail_followup:
        return ParsedQuery("legal_question", ChatFilters(listing_type=None), 0.92)
    if any(has_phrase(text, term) for term in out_terms) and not any(has_phrase(text, term) for term in housing_terms):
        return ParsedQuery("out_of_scope", ChatFilters(), 0.98)

    if out_of_area_place(text):
        return ParsedQuery("out_of_area", ChatFilters(), 0.98)

    min_price, max_price = _prices(text)
    district = next((label for key, label in DISTRICTS.items() if key in text), None)
    amenities = sorted({value for key, value in AMENITIES.items() if key in text})

    min_area = None
    area_match = re.search(r"(?:tren|toi thieu|it nhat|tu)\s*(\d+(?:[\.,]\d+)?)\s*m(?:2| vuong)\b", text)
    if area_match:
        min_area = float(area_match.group(1).replace(",", "."))

    max_distance = None
    distance_match = re.search(r"(?:cach(?: truong| ctu)?|trong vong|duoi|khong qua)\s*(\d+(?:[\.,]\d+)?)\s*(km|m)\b", text)
    if distance_match:
        max_distance = float(distance_match.group(1).replace(",", "."))
        if distance_match.group(2) == "km":
            max_distance *= 1000

    max_minutes = None
    minute_match = re.search(r"(?:duoi|khong qua|trong vong)\s*(\d+)\s*phut", text)
    if minute_match:
        max_minutes = float(minute_match.group(1))

    gender = None
    if "chi nu" in text or "nu thue" in text or "phong nu" in text or "cho nu" in text:
        gender = "female"
    elif "chi nam" in text or "nam thue" in text or "phong nam" in text or "cho nam" in text:
        gender = "male"

    # None = mọi loại UI đang hiện (phòng trọ + nhà mini, visible_clause). Branch PHUC mặc định phong_tro
    # vì catalog của nó không có nhà mini — giữ thế thì chatbot không bao giờ gợi ý minihouse.
    listing_type = None
    if "nha nguyen can" in text:
        listing_type = "nha_nguyen_can"
    elif "mat bang" in text:
        listing_type = "mat_bang"
    elif re.search(r"nha mini|mini ?house|can ho mini|chung cu mini|studio", text):
        listing_type = "nha_mini"

    filters = ChatFilters(
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        district=district,
        amenities=amenities,
        gender=gender,
        max_distance_ctu=max_distance,
        max_route_minutes=max_minutes,
        listing_type=listing_type,
        max_price_exclusive=bool(re.search(r"\bduoi\s*\d+(?:[.,]\d+)?\s*(?:trieu|tr|k|nghin|ngan)\b", text)),
        sort_by="price_asc" if any(has_phrase(text, term) for term in ("re nhat", "gia thue thap nhat", "gia thap nhat")) else None,
    )
    evidence = sum(
        value not in (None, False, [], "phong_tro")
        for value in filters.model_dump().values()
    )
    intent = "find_listing" if any(has_phrase(text, term) for term in housing_terms) or evidence else "clarify"
    return ParsedQuery(intent, filters, min(0.98, 0.72 + evidence * 0.04))


def merge_filters(parsed: ChatFilters, explicit: ChatFilters | None) -> ChatFilters:
    if explicit is None:
        return parsed
    data = parsed.model_dump()
    for key, value in explicit.model_dump(exclude_none=True, exclude_unset=True).items():
        if key == "amenities":
            data[key] = sorted(set(data.get(key, [])) | set(value))
        else:
            data[key] = value
    return ChatFilters(**data)

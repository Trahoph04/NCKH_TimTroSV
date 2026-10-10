"""Quy tắc đứng TRƯỚC truy xuất và LLM — khẩn cấp, ngoài khu vực, câu hỏi so sánh với kết quả trước (08/10/2026).

Vì sao có file này (đo trên 17 ca kiểm tra thêm ngoài bộ 36 câu của Phúc):
- "Tôi bị chủ trọ đe doạ đánh, phải làm gì?" bị coi là tìm phòng (có chữ "chủ trọ") và trả "chưa tìm thấy tin trọ phù hợp" —
  người đang gặp nguy hiểm nhận câu trả lời vô nghĩa, không có số 113.
- "Tìm phòng trọ ở Hà Nội" trả 5 tin Cần Thơ không báo gì (khớp chữ "Hà" của "Hà Ngọc").
- "Còn phòng nào rẻ hơn không?" trả giá không hề rẻ hơn lượt trước.
Tất cả là quy tắc xác định (không dùng mô hình): nhanh, kiểm thử được, không bịa. Mỗi quy tắc ưu tiên KHÔNG nhận nhầm — câu hỏi pháp lý
về PCCC hay bạo lực gia đình vẫn đi đường pháp lý; chỉ tình huống ĐANG xảy ra (ngôi thứ nhất/thì hiện tại) mới vào đường khẩn cấp.
"""
from __future__ import annotations

import re

from .providers import normalize_text
from .topics import has_phrase

# ── khẩn cấp ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Số điện thoại khẩn cấp quốc gia: 113 Công an, 114 Cảnh sát PCCC & CNCH, 115 Cấp cứu.
_VIOLENCE = (
    "de doa", "doa danh", "doa giet", "bi danh", "danh toi", "hanh hung", "bi hiep", "bi xam hai", "bi cuop",
    "bi quay roi tinh duc", "bi sam so", "bi dua dao", "cam dao", "bi nhot", "bi giam giu",
)
# "đang/bị/vừa cháy …" — KHÔNG khớp "phòng cháy chữa cháy" (câu hỏi pháp lý) hay "đang chạy xe"
_FIRE = (
    re.compile(r"\b(?:dang|bi|vua)\s+chay\s+(?:nha|tro|phong|day|dien|lon|to)\b"),
    re.compile(r"\b(?:nha|phong|tro|day dien|ca day)\s+(?:dang|bi|vua)\s+chay\b"),
    re.compile(r"\bdang\s+hoa hoan\b"),
)
_MEDICAL = re.compile(r"\b(?:cap cuu|ngo doc|bi dien giat|bat tinh|ngung tho|ngat xiu)\b")
_SELF_HARM = ("tu tu", "tu sat", "muon chet", "khong muon song", "ket thuc cuoc song", "lam hai ban than")

EMERGENCY_ANSWERS = {
    "violence": (
        "Nếu bạn đang gặp nguy hiểm trực tiếp, hãy ưu tiên an toàn của mình trước:\n"
        "- Rời khỏi nơi đó hoặc đến chỗ đông người, an toàn (nhà bạn bè, cửa hàng, trụ sở công an).\n"
        "- Gọi **113** (Công an) hoặc báo công an phường/xã nơi bạn ở. Nếu bị thương, gọi **115** (cấp cứu).\n"
        "- Giữ lại bằng chứng: tin nhắn, ghi âm/ghi hình, ảnh vết thương, tên người chứng kiến. Không tự đối đầu.\n"
        "- Báo người thân hoặc bạn bè tin cậy và phòng công tác sinh viên của trường để được hỗ trợ.\n\n"
        "Khi bạn đã an toàn, mình có thể giải thích quyền của người thuê hoặc cách tố cáo. "
        "Đây là hướng dẫn chung, không thay thế sự hỗ trợ của cơ quan chức năng."
    ),
    "fire": (
        "Nếu đang có cháy: thoát ra ngoài ngay theo lối thoát nạn, không dùng thang máy, không quay lại lấy đồ. "
        "Gọi **114** (Cảnh sát PCCC và cứu nạn, cứu hộ) và báo cho mọi người xung quanh.\n"
        "- Nếu bị kẹt trong phòng: đóng kín cửa, dùng khăn hoặc chăn ướt bịt kín khe cửa, ra ban công hoặc cửa sổ "
        "để ra tín hiệu cầu cứu và chờ lực lượng chức năng. Tuyệt đối không nhảy từ trên cao xuống.\n"
        "- Có người bị thương hoặc ngạt khói: gọi **115** (cấp cứu)."
    ),
    "medical": (
        "Nếu có người nguy kịch, gọi **115** (cấp cứu) ngay và nói rõ địa chỉ, tình trạng người bệnh.\n"
        "- Trường hợp điện giật: ngắt nguồn điện (cầu dao/phích cắm) trước khi chạm vào người bị nạn; không dùng tay trần kéo họ ra.\n"
        "- Ở lại cùng người bệnh cho tới khi nhân viên y tế đến."
    ),
    "self_harm": (
        "Mình rất tiếc bạn đang cảm thấy như vậy. Bạn không phải một mình, và bạn xứng đáng được giúp đỡ ngay bây giờ.\n"
        "- Nếu bạn đang có nguy cơ làm hại bản thân hoặc ai đó đang gặp nguy hiểm: gọi **115** (cấp cứu) hoặc **113** (công an) ngay.\n"
        "- Nhờ một người thân, bạn bè hoặc người ở gần bạn ở bên cạnh lúc này.\n"
        "- Liên hệ phòng công tác sinh viên hoặc bộ phận tư vấn tâm lý của trường để được hỗ trợ.\n\n"
        "Mình là trợ lý tìm trọ nên không thể thay thế chuyên gia, nhưng việc nói ra với một người tin cậy là bước rất quan trọng."
    ),
}


def emergency_kind(text: str) -> str | None:
    """Loại khẩn cấp ("violence"|"fire"|"medical"|"self_harm") hoặc None. `text` đã normalize_text."""
    if any(has_phrase(text, term) for term in _SELF_HARM):
        return "self_harm"
    if any(pattern.search(text) for pattern in _FIRE):
        return "fire"
    if any(has_phrase(text, term) for term in _VIOLENCE):
        return "violence"
    if _MEDICAL.search(text):
        return "medical"
    return None


# ── ngoài khu vực ────────────────────────────────────────────────────────────────────────────────────────────────────
# Dữ liệu chỉ quanh ĐH Cần Thơ. Sóc Trăng và Hậu Giang KHÔNG nằm ở đây: từ 07/2025 hai tỉnh sáp nhập vào TP. Cần Thơ
# (và CTU có cơ sở ở đó) nên coi là cùng khu vực. Dùng cụm từ nguyên vẹn (has_phrase) — "Hà Ngọc" không khớp "Hà Nội".
_OTHER_PLACES = {
    "ha noi": "Hà Nội", "ho chi minh": "TP. Hồ Chí Minh", "sai gon": "TP. Hồ Chí Minh", "tphcm": "TP. Hồ Chí Minh",
    "tp hcm": "TP. Hồ Chí Minh", "hcm": "TP. Hồ Chí Minh", "thu duc": "TP. Hồ Chí Minh", "da nang": "Đà Nẵng",
    "hai phong": "Hải Phòng", "da lat": "Đà Lạt", "nha trang": "Nha Trang", "vung tau": "Vũng Tàu", "bien hoa": "Biên Hòa",
    "binh duong": "Bình Dương", "long an": "Long An", "tien giang": "Tiền Giang", "my tho": "Mỹ Tho", "ben tre": "Bến Tre",
    "vinh long": "Vĩnh Long", "dong thap": "Đồng Tháp", "cao lanh": "Cao Lãnh", "an giang": "An Giang",
    "long xuyen": "Long Xuyên", "kien giang": "Kiên Giang", "rach gia": "Rạch Giá", "phu quoc": "Phú Quốc",
    "ca mau": "Cà Mau", "bac lieu": "Bạc Liêu", "tra vinh": "Trà Vinh", "quang ninh": "Quảng Ninh", "thua thien hue": "Huế",
    "tp hue": "Huế",
}
_LOCAL = (
    "can tho", "ninh kieu", "cai rang", "binh thuy", "o mon", "thot not", "phong dien", "co do", "thoi lai", "vinh thanh",
    "ctu", "dhct", "dai hoc can tho", "hau giang", "soc trang", "vi thanh", "nga bay", "long my", "khu 1", "khu 2", "khu 3",
    "khu i", "khu ii", "khu iii",
)


def out_of_area_place(text: str) -> str | None:
    """Tên nơi ngoài Cần Thơ nếu người dùng muốn tìm phòng ở đó và KHÔNG nhắc khu vực địa phương; ngược lại None.

    "Từ Hà Nội xuống Cần Thơ học, tìm phòng ở Ninh Kiều" có nhắc Cần Thơ ⇒ vẫn tìm bình thường.
    """
    if any(has_phrase(text, local) for local in _LOCAL):
        return None
    for phrase, label in _OTHER_PLACES.items():
        if has_phrase(text, phrase):
            return label
    return None


def out_of_area_answer(place: str) -> str:
    return (f"Hiện Trọ CTU chỉ có tin nhà trọ quanh Đại học Cần Thơ (Ninh Kiều, Cái Răng, Bình Thủy, Ô Môn, Phong Điền, "
            f"Thốt Nốt…), chưa có dữ liệu ở {place}. Bạn muốn mình tìm phòng ở khu vực nào của Cần Thơ, với ngân sách bao nhiêu?")


# ── câu hỏi so sánh với kết quả lượt trước ──────────────────────────────────────────────────────────────────────────
def comparative_updates(message: str, shown: dict) -> dict:
    """Biến "rẻ hơn / gần hơn / rộng hơn" thành bộ lọc so với CÁC TIN ĐÃ HIỆN lượt trước.

    `shown`: {"min_price", "min_distance", "max_area"} của các tin lượt trước (None nếu không có). Trả dict cập nhật cho ChatFilters;
    rỗng nếu câu không so sánh hoặc thiếu số liệu. "Rẻ hơn" = rẻ hơn TẤT CẢ tin đã hiện (nghiêm ngặt): người dùng hỏi vì
    chưa ưng giá những tin đang thấy.
    """
    text = normalize_text(message)
    updates: dict = {}
    if re.search(r"\b(?:re hon|gia thap hon|thap hon|it tien hon|tiet kiem hon)\b", text) and shown.get("min_price"):
        updates.update(max_price=int(shown["min_price"]), max_price_exclusive=True, min_price=None)
    if re.search(r"\b(?:gan hon|gan truong hon|gan ctu hon)\b", text) and shown.get("min_distance"):
        updates["max_distance_ctu"] = max(0.0, float(shown["min_distance"]) - 1.0)
    if re.search(r"\b(?:rong hon|lon hon|dien tich lon hon)\b", text) and shown.get("max_area"):
        updates["min_area"] = float(shown["max_area"]) + 0.1
    return updates

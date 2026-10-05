"""Quy đổi "lựa chọn trong form v2" → "giá trị cột roommate_profiles".

Tách khỏi import_survey.py để test được bằng pytest mà không cần DB, và để chỗ
duy nhất định nghĩa cực tính nằm cạnh profile.py (cùng một nguồn sự thật).

KHỚP BẰNG CHUỖI CON, KHÔNG BẰNG ==: Google Form trả về gạch ngang dài (en-dash
'–') ở '1,5 – 2 triệu', '22h – 24h', 'Để 1–2 ngày', và lần export khác có thể
trả gạch thường. So khớp tuyệt đối sẽ im lặng ra None cho cả cột. Mỗi mục dưới
đây chọn một chuỗi con ĐỦ ĐẶC TRƯNG để không trùng lựa chọn khác.
"""
from __future__ import annotations

from .profile import DB_SMOKE_IN_ROOM

# (chuỗi con đặc trưng, giá trị) — xét theo thứ tự, khớp đầu tiên thắng.
# Ngân sách khớp bằng TIỀN TỐ, không phải chuỗi con: '2 – 2,5 triệu' chứa chuỗi
# con '2,5' nên khớp-chuỗi-con sẽ trả band 3 thay vì 2 (lệch 1 bậc = lọc cứng
# ngân sách loại oan/bỏ sót cặp). Thứ tự dài-trước để '2,5' không bị '2' ăn mất.
_BUDGET_PREFIX = [("Dưới 1,5", 0), ("Trên 3,5", 4), ("2,5", 3), ("1,5", 1), ("2", 2)]
_SCENARIO = [("một mình", 1), ("ghép 2", 2), ("ghép 3", 3)]
_SLEEP = [("Trước 22h", 0), ("22h", 1), ("Sau 0h", 2)]
_NOISE = [("Rất khó chịu", 1), ("Hơi khó chịu", 2), ("Nhắc nhẹ", 3), ("Không sao cả", 5)]
_DISHES = [("ngay lập tức", 5), ("trong ngày", 4), ("ngày rồi rửa", 2), ("hết chén sạch", 1)]
_AC = [("Ít khi bật", 0), ("Bật lúc nóng", 1), ("gần như cả đêm", 2)]
_MONEY = [("sòng phẳng", 1), ("Chia đều", 2)]
_PERSONA = [("Huy", "A"), ("Phúc", "B")]


def _pick(text: str | None, table):
    if not text:
        return None
    for needle, value in table:
        if needle in text:
            return value
    return None


def gender(text: str | None) -> str | None:
    """Chỉ 'nam'|'nu'. Mọi giá trị khác (kể cả 'Không muốn nêu') → None = ngoài pool ghép."""
    if not text:
        return None
    t = text.strip().lower()
    if t.startswith("nam"):
        return "nam"
    if t.startswith("nữ") or t.startswith("nu"):
        return "nu"
    return None


def budget_band(text: str | None) -> int | None:
    if not text:
        return None
    t = text.strip()
    for prefix, value in _BUDGET_PREFIX:
        if t.startswith(prefix):
            return value
    return None



def scenario(text): return _pick(text, _SCENARIO)
def sleep_time(text): return _pick(text, _SLEEP)
def noise_tolerance(text): return _pick(text, _NOISE)
def cleanliness(text): return _pick(text, _DISHES)
def ac_usage(text): return _pick(text, _AC)
def money_style(text): return _pick(text, _MONEY)
def persona(text): return _pick(text, _PERSONA)


def smoking(text: str | None) -> tuple[bool | None, bool | None, bool]:
    """→ (smoke, smoke_in_room, tự_suy_ra_deal_breaker_hút_thuốc).

    Vì sao tách smoke khỏi smoke_in_room: form có 4 mức, chỉ mức "hút VÀ cần hút
    TRONG PHÒNG" mới đụng deal-breaker. Gộp thành một cờ nhị phân là loại oan
    người hút thuốc ra ngoài hút.

    Cờ thứ ba: lựa chọn "mình không hút, và KHÔNG chịu được người ở chung hút" là
    một deal-breaker được khai NGẦM — form không bắt chọn lại ở câu deal-breaker.
    Không suy ra thì người đó mất lớp bảo vệ mình vừa yêu cầu.
    """
    if not text:
        return None, None, False
    if "KHÔNG chịu được" in text:
        return False, False, True
    if "cũng được" in text:
        return False, False, False
    if "ra ngoài hút" in text:
        return True, False, False
    if "trong phòng" in text:
        return True, True, False
    return None, None, False


def split_multi(raw: str | None, options: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Tách câu nhiều lựa chọn → (các option khớp, token lạ còn lại).

    KHÔNG dùng raw.split(','): nhiều option TỰ CHỨA dấu phẩy ('Ở bẩn, không dọn
    dẹp', 'Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)').
    split(',') sẽ băm chúng thành các mảnh không khớp option nào ⇒ mất sạch
    deal-breaker, lọc cứng thành vô hiệu mà không báo lỗi.

    Khớp option DÀI trước: 'Nấu ăn trong phòng' là chuỗi con của... không có, nhưng
    'Đi chơi về khuya' nằm trong 'Mình hay đi chơi về khuya' ⇒ thứ tự dài-trước
    tránh ăn mất option dài.

    Token lạ được trả về chứ không bỏ im: nó là tín hiệu form đã đổi lựa chọn.
    """
    if not raw:
        return [], []
    found: list[str] = []
    rest = raw
    for opt in sorted(options, key=len, reverse=True):
        if opt in rest:
            found.append(opt)
            rest = rest.replace(opt, "", 1)
    leftover = [t for t in (x.strip(" ,") for x in rest.split(",")) if t]
    return found, leftover


def deal_breakers_with_smoking(found: list[str], infer_smoke: bool) -> list[str]:
    if infer_smoke and DB_SMOKE_IN_ROOM not in found:
        return [*found, DB_SMOKE_IN_ROOM]
    return found

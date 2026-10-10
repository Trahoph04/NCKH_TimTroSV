"""Trích thuộc tính "mềm" từ mô tả tin: tiền điện/nước, cọc, giới tính, giờ giấc.

Các nguồn (nhatot, phongtro123, mogi...) KHÔNG có field riêng cho mấy thứ này —
chủ trọ viết tự do trong body: "điện 3k5/kw, nước 20k/người, cọc 1 tháng, chỉ nữ".
Module này là regex thuần (không I/O) để test được và chạy backfill trên data cũ.

Quy ước output (khớp migration 90_extras_reviews.sql):
  electricity_price  int  VND/kWh        (1.500–6.000 hợp lệ)
  water_price        int  VND            (đi kèm water_unit)
  water_unit         str  'm3' | 'person' | 'month'
  utility_state_price bool  "điện nước giá nhà nước / giá dân / theo điện lực"
  deposit_amount     int  VND
  deposit_months     float  số tháng cọc (0 = không cọc)
  gender_only        str  'nu' | 'nam' | None (None = không ràng buộc / không rõ)
  curfew_hour        int  giờ khoá cổng (23 = 23h); None = không thấy
  free_hours         bool | None  True "giờ giấc tự do", False "có giới nghiêm"
Không tìm thấy → None (KHÔNG đoán mặc định) — chatbot/UI phải hiện "chưa rõ".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass


@dataclass
class Extras:
    electricity_price: int | None = None
    water_price: int | None = None
    water_unit: str | None = None
    utility_state_price: bool | None = None
    deposit_amount: int | None = None
    deposit_months: float | None = None
    gender_only: str | None = None
    curfew_hour: int | None = None
    free_hours: bool | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# ── chuẩn hoá text ────────────────────────────────────────────────────────────
def _fold(text: str | None) -> str:
    """bỏ dấu + lowercase + gộp khoảng trắng; giữ số, '/', '.', ','."""
    if not text:
        return ""
    t = unicodedata.normalize("NFD", text)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.replace("đ", "d").replace("Đ", "D").lower()
    # "3k5" → "3.5k"  (cách viết phổ biến: 3k5 = 3.500)
    t = re.sub(r"(\d)k(\d)\b", r"\1.\2k", t)
    t = re.sub(r"[–—]", "-", t)  # en/em dash → '-'
    return re.sub(r"\s+", " ", t)


# số kiểu VN: "3.500", "3,5", "20.000", "3.5", "20"
_NUM = r"(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)"
# \b bắt buộc: không có, "k" khớp luôn chữ cái đầu của "khi"/"kwh" → đơn vị sai
_UNIT_MONEY = r"(k\b|nghin\b|ngan\b|ng\b|d\b|vnd\b|dong\b)?"


def _to_vnd(num: str, unit: str | None) -> int | None:
    """'3.500'→3500; '3,5'+'k'→3500; '20'+'k'→20000; '3.5' (không unit) → 3500 (tự hiểu là nghìn)."""
    s = num
    # 3.500 / 20.000 kiểu VN (nhóm 3 số) → bỏ dấu
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        v = float(s.replace(".", "").replace(",", ""))
    else:
        v = float(s.replace(",", "."))
    if unit in ("k", "nghin", "ngan", "ng"):
        v *= 1000
    elif unit is None and v < 100:
        v *= 1000  # "điện 3.5" / "nước 20" → nghìn đồng
    return int(round(v))


# ── điện ──────────────────────────────────────────────────────────────────────
# Bỏ dấu làm "diện tích" / "điện thoại" / "điện máy" trùng mặt chữ "dien" ⇒ "Diện tích: 5x5m" từng bị đọc thành
# tiền điện 5.000đ (tin 1598, 07/10). Loại các cụm đó bằng lookahead.
_ELEC = re.compile(
    r"dien(?! ?(?:tich|thoai|may))[^\d\n]{0,25}?" + _NUM + r"\s*" + _UNIT_MONEY + r"\s*(?:/|\s|1)?\s*(kwh|kw|so|ki|ky|chu|dien)?",
)
_ELEC_STATE = re.compile(r"(dien|nuoc|dien nuoc)[^.\n]{0,20}(gia nha nuoc|gia dan|theo gia dien luc|gia dien luc|gia sinh hoat|theo dong ho)")


def extract_electricity(t: str) -> int | None:
    for m in _ELEC.finditer(t):
        v = _to_vnd(m.group(1), m.group(2))
        if 1500 <= v <= 6000:
            return v
    return None


# ── nước ──────────────────────────────────────────────────────────────────────
_WATER = re.compile(
    r"nuoc[^\d\n]{0,25}?" + _NUM + r"\s*" + _UNIT_MONEY
    + r"\s*(?:/|\s|1)?\s*(khoi|m3|m³|m 3|nguoi|ng\b|thang|phong)?",
)
_WATER_UNIT = {"khoi": "m3", "m3": "m3", "m³": "m3", "m 3": "m3",
               "nguoi": "person", "ng": "person", "thang": "month", "phong": "month"}


def extract_water(t: str) -> tuple[int | None, str | None]:
    for m in _WATER.finditer(t):
        v = _to_vnd(m.group(1), m.group(2))
        unit_raw = (m.group(3) or "").strip()
        unit = _WATER_UNIT.get(unit_raw)
        if unit is None:
            # không ghi đơn vị: ≤30k gần như chắc là /khối, 30k–200k là /người hoặc /tháng
            unit = "m3" if v <= 30_000 else "person"
        if 3_000 <= v <= 200_000:
            return v, unit
    return None, None


# ── cọc ───────────────────────────────────────────────────────────────────────
# \b bắt buộc: không có nó, "nuoc 20k coc 1 thang" khớp nhánh "k...coc" → sai thành "không cọc"
_NO_DEPOSIT = re.compile(r"(?<![\w.,])(khong|mien|ko|k)\s*(can\s*)?(dat\s*)?coc")
_DEPOSIT = re.compile(
    r"coc[^\d\n]{0,20}?" + _NUM + r"\s*(trieu\b|tr\b|thang\b|th\b|k\b|nghin\b|ngan\b|d\b|vnd\b)?",
)


def _num_to_float(num: str) -> float | None:
    """'1.500.000' / '1,500,000' → 1500000.0 ; '2,5' → 2.5 ; số dị dạng → None (bỏ qua).

    Dạng nhóm nghìn phải bỏ CẢ '.' lẫn ',' — trước đây đổi ',' thành '.' nên
    "cọc 1,500,000" thành "1.500.000" và float() ném ValueError, làm chết cả backfill.
    """
    s = num.strip()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s):
        return float(re.sub(r"[.,]", "", s))
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def extract_deposit(t: str) -> tuple[int | None, float | None]:
    if _NO_DEPOSIT.search(t):
        return None, 0.0
    for m in _DEPOSIT.finditer(t):
        num, unit = m.group(1), (m.group(2) or "")
        raw = _num_to_float(num)
        if raw is None:
            continue
        if unit in ("thang", "th"):
            if 0 < raw <= 3:
                return None, raw
        elif unit in ("trieu", "tr"):
            if 0 < raw <= 10:
                return int(raw * 1_000_000), None
        elif unit in ("k", "nghin", "ngan"):
            if 100 <= raw <= 10_000:
                return int(raw * 1000), None
        else:
            # "cọc 1" → tháng; "cọc 1.500.000" → VND
            if raw <= 3:
                return None, raw
            if 100_000 <= raw <= 10_000_000:
                return int(raw), None
    return None, None


# ── giới tính ─────────────────────────────────────────────────────────────────
_BOTH = re.compile(r"\bnam\s*(/|,|-|hoac|hay|va|&|\s)\s*nu\b|\bnu\s*(/|,|-|hoac|hay|va|&|\s)\s*nam\b|ca nam (lan|va) nu")
_FEMALE = re.compile(
    r"(chi|danh|uu tien|chi nhan|nhan|cho|phu hop)\s*(cho\s*)?(thue\s*)?(sinh vien|sv|ban|nguoi|nu sinh|hoc sinh)?\s*nu\b"
    r"|\b(phong|tro|nha tro|khu tro|day tro)\s+(danh cho\s+|cho\s+)?nu\b"
    r"|\bnu\s+(thue|o ghep|o\b)"
    r"|\b(ktx|ky tuc xa)\s+nu\b"
    r"|\bnu sinh\b"
)
_MALE = re.compile(
    r"(chi|danh|uu tien|chi nhan|nhan|cho|phu hop)\s*(cho\s*)?(thue\s*)?(sinh vien|sv|ban|nguoi)?\s*nam\b"
    r"|\b(phong|tro|nha tro|khu tro|day tro)\s+(danh cho\s+|cho\s+)?nam\b"
    r"|\bnam\s+(thue|o ghep)\b"
    r"|\b(ktx|ky tuc xa)\s+nam\b"
)


def extract_gender(t: str) -> str | None:
    """t = text đã fold NHƯNG đại từ 'chị' đã được thay bằng 'ms' (xem extract_extras) —
    sau khi bỏ dấu 'chị Nữ' (tên người) và 'chỉ nữ' (ràng buộc) trùng nhau."""
    if _BOTH.search(t):
        return None
    f, m = bool(_FEMALE.search(t)), bool(_MALE.search(t))
    if f and not m:
        return "nu"
    if m and not f:
        return "nam"
    return None


# ── giờ giấc ──────────────────────────────────────────────────────────────────
_FREE = re.compile(
    r"gio giac tu do|tu do gio giac|khong gioi nghiem|ko gioi nghiem|khong khoa cong|24/24|24h"
    r"|khong quan ly gio( giac)?|khong gioi han gio( giac)?"
)
_CURFEW = re.compile(r"(khoa|dong|gioi nghiem|dong cua)\s*(cong|cua)?[^\d\n]{0,12}?(\d{1,2})\s*(h|g|gio)\b")


def extract_hours(t: str) -> tuple[int | None, bool | None]:
    m = _CURFEW.search(t)
    if m:
        h = int(m.group(3))
        if 20 <= h <= 24 or 0 <= h <= 2:
            return h % 24, False
    if _FREE.search(t):
        return None, True
    # "chìa khoá cổng riêng" (mỗi phòng tự mở cổng) KHÔNG phải giới nghiêm — từng gắn nhầm free_hours=False
    if re.search(r"gioi nghiem|(?<!chia )khoa cong", t):
        return None, False
    return None, None


# ── entry point ───────────────────────────────────────────────────────────────
def extract_extras(*texts: str | None) -> Extras:
    raw = " . ".join(x for x in texts if x)
    t = _fold(raw)
    if not t:
        return Extras()
    # đại từ xưng hô "chị/Chị" (LH chị Nữ, chị Nam) → 'ms' TRƯỚC khi bỏ dấu, tránh nhầm với "chỉ nữ"
    t_gender = _fold(re.sub(r"\b[Cc][Hh][Ịị]\b", "ms", raw))
    water_price, water_unit = extract_water(t)
    deposit_amount, deposit_months = extract_deposit(t)
    curfew, free = extract_hours(t)
    return Extras(
        electricity_price=extract_electricity(t),
        water_price=water_price,
        water_unit=water_unit,
        utility_state_price=True if _ELEC_STATE.search(t) else None,
        deposit_amount=deposit_amount,
        deposit_months=deposit_months,
        gender_only=extract_gender(t_gender),
        curfew_hour=curfew,
        free_hours=free,
    )

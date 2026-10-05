"""Trích thông tin liên hệ công khai từ tin đăng: SĐT, Zalo, Facebook, tên người đăng.

PHẠM VI (quan trọng cho phần "đạo đức nghiên cứu" của báo cáo):
  - CHỈ đọc thông tin mà người đăng TỰ GHI trong tiêu đề/mô tả/trang chi tiết đã tải về.
  - Nguồn nào che số (Chợ Tốt/nhatot hiện ***) thì bỏ qua — module này KHÔNG tìm cách
    gọi API ẩn hay bỏ qua cơ chế che số.
  - SĐT là dữ liệu cá nhân (NĐ 13/2023): lưu để liên hệ/khử trùng tin, KHÔNG hiển thị
    công khai cho khách vãng lai; UI nên hiện nút "xem tin gốc".

Chuẩn hoá: mọi số về dạng 0xxxxxxxxx (bỏ +84/84, bỏ . - () khoảng trắng).
Không chắc → None, không đoán.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

# Đầu số di động VN hợp lệ sau chuyển đổi 11→10 số (2018).
MOBILE_PREFIXES = (
    "032", "033", "034", "035", "036", "037", "038", "039",          # Viettel
    "070", "076", "077", "078", "079",                               # Mobifone
    "081", "082", "083", "084", "085", "088",                        # Vinaphone
    "056", "058",                                                    # Vietnamobile
    "059",                                                           # Gmobile
    "086", "096", "097", "098",                                      # Viettel
    "089", "090", "093",                                             # Mobifone
    "091", "094",                                                    # Vinaphone
    "092",                                                           # Vietnamobile
    "099",                                                           # Gmobile
    "087",                                                           # Itelecom
)
LANDLINE_PREFIXES = ("0292",)  # cố định Cần Thơ


@dataclass
class Contact:
    contact_phone: str | None = None
    contact_phone_alt: str | None = None
    contact_zalo: str | None = None
    contact_name: str | None = None
    contact_facebook: str | None = None
    contact_source: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.replace("đ", "d").replace("Đ", "D").lower()


# Chuỗi ứng viên: bắt đầu bằng +84/84/0, theo sau là số + dấu phân tách phổ biến.
_CAND = re.compile(r"(?<![\d*])(?:\+?84|0)[\s.\-()]?\d[\d\s.\-()]{7,14}(?![\d*])")
# Ký tự che số của các trang rao vặt
_MASK = re.compile(r"[*x]{2,}|\bxxx\b|\bấn\b|\bbấm\b", re.IGNORECASE)


def normalize_phone(raw: str) -> str | None:
    """'+84 909.123.456' / '0909 123 456' → '0909123456'. Không hợp lệ → None."""
    d = re.sub(r"\D", "", raw)
    if d.startswith("84") and not d.startswith("840"):
        d = "0" + d[2:]
    elif d.startswith("840"):
        d = d[2:]
    if not d.startswith("0"):
        return None
    if len(d) == 10 and d[:3] in MOBILE_PREFIXES:
        return d
    if len(d) in (10, 11) and d[:4] in LANDLINE_PREFIXES:
        return d
    return None


def find_phones(text: str) -> list[str]:
    """Mọi SĐT hợp lệ, giữ thứ tự xuất hiện, không trùng."""
    out: list[str] = []
    for m in _CAND.finditer(text):
        around = text[max(0, m.start() - 12): m.end() + 12]
        if _MASK.search(around):
            continue  # số bị nguồn che (vd Chợ Tốt "***") → bỏ
        p = normalize_phone(m.group(0))
        if p and p not in out:
            out.append(p)
    return out


_ZALO_NEAR = re.compile(r"zalo[^0-9+]{0,15}((?:\+?84|0)[\d\s.\-()]{8,14})", re.IGNORECASE)
_FB = re.compile(r"(?:https?://)?(?:www\.|m\.)?(?:facebook\.com|fb\.com|fb\.me)/[A-Za-z0-9_.\-/?=]+")
# "LH: Chị Hạnh", "Liên hệ anh Tuấn", "gặp cô Ba", "A. Minh", "Ms Lan"
_NAME = re.compile(
    r"(?:lien he|lh|gap|chu nha|chinh chu|mr|ms|mrs)?[\s:.\-]*"
    r"(?<![\wà-ỹÀ-Ỹ])(a|anh|c|chi|chị|co|cô|chu|chú|ong|ông|ba|bà|bac|bác|em|ms|mr)(?![\wà-ỹÀ-Ỹ])[\s.:]*"
    r"([a-zà-ỹA-ZÀ-Ỹ][\wà-ỹÀ-Ỹ]{1,14})",
    re.IGNORECASE,
)
_NAME_STOP = {
    "toi", "ban", "minh", "em", "nha", "tro", "phong", "can", "tho", "co", "khong",
    "chi", "anh", "gap", "lien", "he", "zalo", "sdt", "duong", "hem", "moi", "ngay",
    "nay", "gia", "dien", "nuoc", "thue", "xem", "vao", "o", "san", "sang",
}


def extract_name(raw_text: str) -> str | None:
    """Tên/xưng hô người đăng, giữ nguyên dấu: 'Chị Hạnh', 'Anh Tuấn'."""
    for m in _NAME.finditer(raw_text):
        title, name = m.group(1), m.group(2)
        if _fold(name) in _NAME_STOP or len(name) < 2:
            continue
        if not name[0].isupper():          # tên riêng phải viết hoa → tránh "chi phi", "anh sang"
            continue
        title_disp = {"a": "Anh", "anh": "Anh", "c": "Chị", "chi": "Chị", "co": "Cô",
                      "chu": "Chú", "ong": "Ông", "ba": "Bà", "bac": "Bác", "em": "Em",
                      "ms": "Ms", "mr": "Mr"}.get(_fold(title), title.capitalize())
        return f"{title_disp} {name}"[:80]
    return None


def extract_contact(*texts: str | None, source: str | None = None,
                    ignore: "list[str] | set[str] | None" = None) -> Contact:
    """Trích liên hệ từ (title, description, contact_text...).

    source: nhãn ghi vào cột contact_source.
    ignore: hotline của chính trang rao vặt (cấu hình `ignore_phones` trong sources/*.json)
            — số tổng đài lặp lại ở MỌI tin, phải loại nếu không sẽ thành "chủ trọ".
    """
    raw = "\n".join(t for t in texts if t)
    if not raw.strip():
        return Contact()
    folded = _fold(raw)

    zalo = None
    mz = _ZALO_NEAR.search(raw)
    if mz:
        zalo = normalize_phone(mz.group(1))

    skip = {normalize_phone(x) or re.sub(r"\D", "", x) for x in (ignore or [])}
    phones = [p for p in find_phones(raw) if p not in skip]
    if zalo in skip:
        zalo = None
    # số Zalo cũng là SĐT → không tính trùng vào phone chính
    main = next((p for p in phones if p != zalo), None)
    alt = next((p for p in phones if p not in (main, zalo)), None)
    if zalo is None and main and "zalo" in folded:
        zalo = main  # "Zalo/ĐT 0909..." — cùng số

    fb = _FB.search(raw)
    c = Contact(
        contact_phone=main,
        contact_phone_alt=alt,
        contact_zalo=zalo,
        contact_name=extract_name(raw),
        contact_facebook=fb.group(0)[:300] if fb else None,
    )
    if any([c.contact_phone, c.contact_zalo, c.contact_facebook, c.contact_name]):
        c.contact_source = source
    return c

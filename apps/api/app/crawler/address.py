"""Địa chỉ rõ ràng: chuẩn hoá quận/phường/đường + reverse geocode khi tin thiếu địa chỉ.

Vấn đề đang có trong DB: cột `district` là text tự do của từng nguồn — 14 biến thể cho
3 quận ("Ninh Kiều" / "Quận Ninh Kiều, Cần Thơ" / "Ninh Kieu" / "Quận Ninh Kiều , Thành
phố Cần Thơ"...), 39% tin không có `address`. Mọi thống kê group-by đều sai.

Module này sinh ra:
  address_full       "85/26 Phạm Ngũ Lão, P. Thới Bình, Q. Ninh Kiều, Cần Thơ"
  street             "85/26 Phạm Ngũ Lão"   (kèm số nhà/hẻm nếu có)
  ward               "Thới Bình"
  district_norm      "Ninh Kiều"            ← 1 dạng duy nhất, dùng cho filter/thống kê
  address_confidence exact | street | ward | district | none
  address_source     source | detail_page | description | reverse_geocode

Thứ tự lấy dữ liệu: địa chỉ của nguồn → trích từ mô tả → reverse geocode toạ độ
(chỉ tin có toạ độ thật, vd nhatot). Không suy diễn quá mức: không có → NULL.
"""
from __future__ import annotations

import asyncio
import re
import unicodedata

import httpx

NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "TroCTU-NCKH/1.0 (contact: phub2303891@student.ctu.edu.vn)"
RATE_LIMIT = 1.0  # giây/req theo usage policy Nominatim

CITY = "Cần Thơ"

# quận/huyện Cần Thơ — key bỏ dấu, value dạng hiển thị chuẩn DUY NHẤT
DISTRICTS: dict[str, str] = {
    "ninh kieu": "Ninh Kiều",
    "binh thuy": "Bình Thủy",
    "cai rang": "Cái Răng",
    "o mon": "Ô Môn",
    "thot not": "Thốt Nốt",
    "phong dien": "Phong Điền",
    "co do": "Cờ Đỏ",
    "thoi lai": "Thới Lai",
    "vinh thanh": "Vĩnh Thạnh",
}

# phường quanh 3 khu CTU — dùng để nhận ra phường viết thiếu chữ "Phường"
WARDS: dict[str, str] = {
    "xuan khanh": "Xuân Khánh", "an khanh": "An Khánh", "an hoa": "An Hòa",
    "an cu": "An Cư", "an nghiep": "An Nghiệp", "an phu": "An Phú",
    "an binh": "An Bình", "hung loi": "Hưng Lợi", "tan an": "Tân An",
    "thoi binh": "Thới Bình", "cai khe": "Cái Khế", "an lac": "An Lạc",
    "le binh": "Lê Bình", "hung phu": "Hưng Phú", "hung thanh": "Hưng Thạnh",
    "ba lang": "Ba Láng", "thuong thanh": "Thường Thạnh", "phu thu": "Phú Thứ",
    "tan phu": "Tân Phú", "an thoi": "An Thới", "bui huu nghia": "Bùi Hữu Nghĩa",
    "tra noc": "Trà Nóc", "tra an": "Trà An", "long hoa": "Long Hòa",
    "long tuyen": "Long Tuyền", "thoi an dong": "Thới An Đông",
}

_CITY_WORDS = ("can tho", "tp can tho", "thanh pho can tho", "tpct")


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFD", t or "")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.replace("đ", "d").replace("Đ", "D").lower()).strip()


def canon_district(*texts: str | None) -> str | None:
    """Mọi biến thể → 1 tên quận chuẩn. 'Quận Ninh Kiều , Thành phố Cần Thơ' → 'Ninh Kiều'."""
    for txt in texts:
        f = _fold(txt)
        if not f:
            continue
        for key, name in DISTRICTS.items():
            if key in f:
                return name
    return None


def canon_ward(*texts: str | None) -> str | None:
    """Tên phường chuẩn, ưu tiên phần có chữ 'Phường/P.' rồi mới dò bảng WARDS."""
    for txt in texts:
        if not txt:
            continue
        m = re.search(r"(?:phường|phuong|p\.)\s*([0-9]{1,2}|[A-ZÀ-Ỹ][\wà-ỹ]*(?:\s+[A-ZÀ-Ỹ][\wà-ỹ]*){0,2})",
                      txt, re.IGNORECASE)
        if m:
            cand = m.group(1).strip(" ,.")
            f = _fold(cand)
            if f in WARDS:
                return WARDS[f]
            if cand.isdigit() or len(cand) > 1:
                return cand.title() if not cand.isdigit() else cand
    for txt in texts:
        f = _fold(txt)
        for key, name in WARDS.items():
            if re.search(rf"\b{re.escape(key)}\b", f):
                return name
    return None


# "85/26 Phạm Ngũ Lão", "hẻm 51 đường 3/2", "số 12 Nguyễn Văn Cừ nối dài"
_NAME_PART = r"[A-ZÀ-Ỹ0-9][\wÀ-ỹà-ỹ/]*"
_SUFFIX = r"(?:\s+(?:nối\s*dài|noi\s*dai))?"

# A. có chữ "đường": [số nhà] [hẻm N] đường Tên
_STREET = re.compile(
    r"((?:số\s*)?\d+[\w/]*\s*)?"
    r"(?:(hẻm|hem|ngõ|ngo|kiệt|kiet)\s*([\w/]+)\s*,?\s*)?"
    r"(?:đường|duong|đ\.)\s+(" + _NAME_PART + r"(?:\s+" + _NAME_PART + r"){0,4})" + _SUFFIX,
    re.IGNORECASE,
)
# B. hẻm/ngõ + số + tên đường (không có chữ "đường"): "Hẻm 22 Nguyễn Văn Cừ nối dài"
_STREET_HEM = re.compile(
    r"(hẻm|hem|ngõ|ngo|kiệt|kiet)\s*([\w/]+)[\s,]+"
    r"(" + _NAME_PART + r"(?:\s+" + _NAME_PART + r"){1,4})" + _SUFFIX,
    re.IGNORECASE,
)
# C. số nhà + tên đường viết hoa, không có từ khoá nào
_STREET_BARE = re.compile(
    r"(?:^|[,\n]|\b[ỞởOo]\s|\b[Tt]ại\s|[Đđ]ịa\s*chỉ\s*:?\s*|[Ss]ố\s+)\s*((?:[Ss]ố\s*)?\d+[\w/]*)\s+"
    r"(" + _NAME_PART + r"(?:\s+" + _NAME_PART + r"){1,4})" + _SUFFIX,
)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ,.")[:200]


def extract_street(*texts: str | None) -> str | None:
    """Số nhà + tên đường từ địa chỉ/mô tả tự do. Không thấy → None."""
    for txt in texts:
        if not txt:
            continue
        m = _STREET.search(txt)
        if m:
            num, hem_kw, hem_no, name = m.group(1), m.group(2), m.group(3), m.group(4)
            parts = []
            if num:
                parts.append(num.strip())
            if hem_kw and hem_no:
                parts.append(f"Hẻm {hem_no}")
            parts.append(f"Đường {name.strip()}")
            return _clean(m.group(0) if False else " ".join(parts))
        m = _STREET_HEM.search(txt)
        if m and _fold(m.group(3)) not in _CITY_WORDS:
            return _clean(f"Hẻm {m.group(2)} {m.group(3)}")
        m = _STREET_BARE.search(txt)
        if m and _fold(m.group(2)) not in _CITY_WORDS:
            return _clean(f"{m.group(1)} {m.group(2)}")
    return None


def compose(street: str | None, ward: str | None, district: str | None) -> str | None:
    parts = []
    if street:
        parts.append(street)
    if ward:
        parts.append(ward if re.match(r"^(P\.|Phường)", ward) else f"P. {ward}")
    if district:
        parts.append(f"Q. {district}" if district in ("Ninh Kiều", "Bình Thủy", "Cái Răng", "Ô Môn", "Thốt Nốt")
                     else f"H. {district}")
    if not parts:
        return None
    parts.append(CITY)
    return ", ".join(parts)


class NormalizedAddress(dict):
    """dict khớp tên cột migration 91 (address_full, street, ward, district_norm, ...)."""


def normalize_address(
    address: str | None = None,
    district: str | None = None,
    title: str | None = None,
    description: str | None = None,
    source_label: str | None = None,
) -> NormalizedAddress:
    """Ghép mọi mẩu text có sẵn → địa chỉ chuẩn + độ tin cậy."""
    street = extract_street(address, description, title)
    ward = canon_ward(address, description, title)
    dist = canon_district(address, district, title, description)

    if street and re.match(r"^(số\s*)?\d", street, re.IGNORECASE):
        conf = "exact"
    elif street:
        conf = "street"
    elif ward:
        conf = "ward"
    elif dist:
        conf = "district"
    else:
        conf = "none"

    src = source_label
    if src is None:
        src = "source" if address else ("description" if (street or ward) else None)

    return NormalizedAddress(
        address_full=compose(street, ward, dist),
        street=street,
        ward=ward,
        district_norm=dist,
        address_confidence=conf,
        address_source=src,
    )


class ReverseGeocoder:
    """Nominatim /reverse cho tin CÓ toạ độ nhưng THIẾU địa chỉ (vd nhatot ghim bản đồ)."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(timeout=15.0)
        self._own = client is None
        self._lock = asyncio.Lock()
        self._cache: dict[tuple[float, float], dict | None] = {}

    async def __aenter__(self) -> "ReverseGeocoder":
        return self

    async def __aexit__(self, *exc) -> None:
        if self._own:
            await self._client.aclose()

    async def lookup(self, lat: float, lng: float) -> dict | None:
        key = (round(lat, 5), round(lng, 5))
        if key in self._cache:
            return self._cache[key]
        try:
            async with self._lock:
                await asyncio.sleep(RATE_LIMIT)
                r = await self._client.get(
                    NOMINATIM_REVERSE,
                    params={"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 18,
                            "addressdetails": 1, "accept-language": "vi"},
                    headers={"User-Agent": USER_AGENT},
                )
            r.raise_for_status()
            data = r.json().get("address") or {}
        except (httpx.HTTPError, ValueError, KeyError):
            data = {}
        self._cache[key] = data or None
        return data or None

    async def normalize(self, lat: float, lng: float) -> NormalizedAddress:
        a = await self.lookup(lat, lng) or {}
        num = a.get("house_number")
        road = a.get("road")
        street = " ".join(p for p in [num, road] if p) or None
        ward = canon_ward(a.get("suburb"), a.get("quarter"), a.get("village"), a.get("city_district"))
        dist = canon_district(a.get("city_district"), a.get("county"), a.get("suburb"), a.get("state"))
        conf = "exact" if num and road else "street" if road else "ward" if ward else "district" if dist else "none"
        return NormalizedAddress(
            address_full=compose(street, ward, dist),
            street=street, ward=ward, district_norm=dist,
            address_confidence=conf, address_source="reverse_geocode",
        )

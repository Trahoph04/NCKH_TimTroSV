"""Nạp bộ dữ liệu nhà trọ do nhóm KHẢO SÁT THỰC ĐỊA (Excel) vào `aggregated_listings`, source = 'survey'.

Khác dữ liệu crawl: toạ độ do nhóm lấy tại chỗ ⇒ geocode 'high' + location_precise TRUE (bản đồ cắm ghim). Chạy lại
được khi file được bổ sung: khoá (source='survey', source_id='KS-<STT>') — tin đã có thì cập nhật.

Cột bắt buộc (dòng tiêu đề, không phân biệt hoa thường): STT · Tên · tọa độ ("lat, lng") · Địa chỉ · Giá ·
Thông tin thêm · Thông tin liên hệ. Ảnh: chạy trước `eval/tools/prepare_survey_images.py` (bỏ EXIF, ra
apps/web/public/khao-sat/) để có manifest {STT: [url…]}.

    docker cp /tmp/survey_images.json "$(docker compose ps -q api)":/tmp/survey_images.json
    docker compose exec -T api python -m app.crawler.import_survey --images /tmp/survey_images.json < data.xlsx
    ... --apply   để ghi DB

Liên hệ (SĐT/Facebook chủ trọ) chỉ lưu vào cột contact_* — giao diện hiện KHÔNG hiển thị; muốn công khai phải có sự
đồng ý của chủ trọ (NĐ 13/2023). File Excel gốc chứa liên hệ nên KHÔNG commit vào repo.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

from sqlalchemy import create_engine, text

from ..cleaner.pipeline import run_cleaner
from ..config import settings
from .address import normalize_address
from .contact import normalize_phone
from .extras import extract_extras
from .geocode import CTU_LAT, CTU_LNG, haversine_m
from .normalize import compute_content_hash, extract_area_from_text, infer_district, parse_amenities
from .pipeline import auto_route
from .repo import ListingRepo
from .schemas import NormalizedListing

log = logging.getLogger("crawler.import_survey")

SOURCE = "survey"
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COLUMNS = {"stt": "stt", "ten": "name", "toa do": "coords", "dia chi": "address", "gia": "price",
           "thong tin them": "info", "thong tin lien he": "contact"}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").strip()


def read_xlsx(data: bytes) -> list[dict]:
    """Sheet đầu tiên → list dict theo dòng tiêu đề. Đọc bằng zip + XML (container api không có openpyxl)."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{_NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{_NS}t")))
    sheet = sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))[0]
    rows = []
    for r in ET.fromstring(z.read(sheet)).iter(f"{_NS}row"):
        vals: dict[int, str] = {}
        for c in r.iter(f"{_NS}c"):
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group():
                col = col * 26 + ord(ch) - 64
            v = c.find(f"{_NS}v")
            if c.get("t") == "inlineStr":
                vals[col - 1] = "".join(t.text or "" for t in c.iter(f"{_NS}t"))
            elif v is not None:
                vals[col - 1] = shared[int(v.text)] if c.get("t") == "s" else v.text
        if vals:
            rows.append([vals.get(i) for i in range(max(vals) + 1)])
    header = [COLUMNS.get(_fold(h or "")) for h in rows[0]]
    missing = set(COLUMNS.values()) - set(header)
    if missing:
        raise SystemExit(f"thiếu cột: {sorted(missing)} (có: {rows[0]})")
    return [{k: (row[i].strip() if i < len(row) and row[i] else None) for i, k in enumerate(header) if k}
            for row in rows[1:] if any(row)]


def parse_price(raw: str | None) -> int | None:
    """'1tr7' → 1.700.000 · '3,6tr -4 tr' → 3.600.000 (cận dưới) · '950k' → 950.000 · '2,8tr' → 2.800.000."""
    s = _fold(raw or "").replace(" ", "")
    m = re.match(r"(\d+)tr(\d+)", s)
    if m:
        return int(m.group(1)) * 1_000_000 + int(m.group(2).ljust(3, "0")[:3]) * 1_000
    m = re.match(r"(\d+(?:[.,]\d+)?)(tr|trieu)", s)
    if m:
        return round(float(m.group(1).replace(",", ".")) * 1_000_000)
    m = re.match(r"(\d+)k", s)
    if m:
        return int(m.group(1)) * 1_000
    return None


def parse_coords(raw: str | None) -> tuple[float, float] | None:
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)", raw or "")
    if not m:
        return None
    lat, lng = float(m.group(1)), float(m.group(2))
    return (lat, lng) if 9.5 < lat < 10.6 and 105.2 < lng < 106.2 else None  # chặn đảo thứ tự / gõ sai


def row_to_listing(r: dict, images: list[str]) -> tuple[NormalizedListing, dict]:
    stt = int(float(r["stt"]))
    name = re.sub(r"\s+", " ", r["name"] or "").strip()
    address = r["address"]
    # tên ngắn ("Trọ Ngân", "M20B") bị normalize_title thay bằng tiêu đề chung ⇒ ghép địa chỉ cho đủ nghĩa
    title = name if len(name) >= 15 else f"{name} – {address}" if address else name
    desc = (r["info"] or "").strip()
    price = parse_price(r["price"])
    if r["price"] and price and not re.fullmatch(r"\s*[\d.,]+\s*(tr|k|triệu)?\s*\d*\s*", r["price"], re.I):
        desc += f"\nGiá theo khảo sát: {r['price'].strip()}"  # khoảng giá "3,6tr - 4tr" — lưu cận dưới, ghi nguyên văn
    n = NormalizedListing(
        source=SOURCE, source_id=f"KS-{stt:03d}", source_url=None, title=title, price=price,
        area=extract_area_from_text(title, desc), address=address,
        district=infer_district(address, title, desc), description=desc or None, images=images,
        amenities=parse_amenities(desc, title),
    )
    coords = parse_coords(r["coords"])
    if coords:
        n.lat, n.lng, n.geocode_confidence = coords[0], coords[1], "high"
        n.distance_to_ctu = haversine_m(n.lat, n.lng, CTU_LAT, CTU_LNG)
    n.content_hash = compute_content_hash(n)
    contact = (r["contact"] or "").strip()
    phone = normalize_phone(contact) if contact and not contact.startswith("http") else None
    ct = {"contact_phone": phone, "contact_phone_alt": None, "contact_zalo": None, "contact_name": None,
          "contact_facebook": contact if contact.startswith("http") else None,
          "contact_source": SOURCE if contact else None}
    return n, ct


def _nearest_district(conn, lat: float, lng: float) -> str | None:
    """Quận của tin gần nhất có quận (≤ 1,5 km) — tin khảo sát hay chỉ ghi hẻm/đường, không ghi quận.

    Lấy `district_norm`, không lấy `district`: cột thô của tin crawl lẫn "Ninh Kiều, Cần Thơ", "Quận Ninh Kiều…"."""
    return conn.execute(text(
        "SELECT district_norm FROM aggregated_listings WHERE district_norm IS NOT NULL AND geom IS NOT NULL "
        "AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, 1500) "
        "ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lng, :lat), 4326) LIMIT 1"
    ), {"lat": lat, "lng": lng}).scalar()


def import_rows(engine, rows: list[dict], images: dict[int, list[str]], apply: bool) -> list[dict]:
    repo = ListingRepo(engine)
    report = []
    for r in rows:
        n, ct = row_to_listing(r, images.get(int(float(r["stt"])), []))
        if n.district is None and n.lat is not None:
            with engine.connect() as conn:
                n.district = _nearest_district(conn, n.lat, n.lng)
        issues = [k for k, bad in (("thiếu giá", n.price is None), ("thiếu/sai toạ độ", n.lat is None),
                                   ("không có ảnh", not n.images)) if bad]
        report.append({"source_id": n.source_id, "title": n.title, "price": n.price, "area": n.area,
                       "district": n.district, "images": len(n.images), "issues": issues})
        if not apply:
            continue
        repo.upsert(n)
        repo.set_extras(SOURCE, n.source_id, extract_extras(n.title, n.description).as_dict())
        repo.set_address(SOURCE, n.source_id, normalize_address(n.address, n.district, n.title, n.description))
        repo.set_contact(SOURCE, n.source_id, ct)
    if apply:
        run_cleaner(engine)
        with engine.begin() as conn:
            # toạ độ đo tại chỗ: đúng nghĩa "vị trí chính xác" của bản đồ (ADR-022)
            conn.execute(text("UPDATE aggregated_listings SET location_precise = (geom IS NOT NULL) "
                              "WHERE source = :s"), {"s": SOURCE})
            # nhóm không đo diện tích thì để trống — cleaner tự điền theo giá (is_imputed_area) là số đoán, không
            # được hiện ra như số khảo sát
            conn.execute(text("UPDATE aggregated_listings SET area = NULL WHERE source = :s AND is_imputed_area"),
                         {"s": SOURCE})
        repo.refresh_scores()
        asyncio.run(auto_route(repo, SOURCE))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", help="manifest JSON từ eval/tools/prepare_survey_images.py")
    ap.add_argument("--apply", action="store_true", help="ghi DB (mặc định chỉ kiểm tra)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    images = {}
    if args.images:
        with open(args.images, encoding="utf-8") as f:
            images = {int(k): v for k, v in json.load(f).items()}
    rows = read_xlsx(sys.stdin.buffer.read())
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    for item in import_rows(engine, rows, images, args.apply):
        print(json.dumps(item, ensure_ascii=False))
    if not args.apply:
        print("(chỉ kiểm tra — thêm --apply để ghi DB)")


if __name__ == "__main__":
    main()

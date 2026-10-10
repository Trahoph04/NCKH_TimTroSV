"""Cầu nối notebook 01 ↔ hệ gợi ý THẬT trong apps/api/app/recommend/core.py (thuần, không DB).

Như roommate_lib: đăng ký package rỗng `app` / `app.recommend` để import core.py mà KHÔNG chạy __init__.py
(kéo FastAPI). Số trong báo cáo phải là số của sản phẩm.

Không in email/họ tên/MSSV: chỉ đọc 4 cột tiêu chí của khảo sát.
"""
from __future__ import annotations

import csv
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
DATA = ROOT / "eval" / "data"
SURVEY_CSV = DATA / "survey_v2.csv"
CANDIDATES_CSV = DATA / "rec_candidates.csv"
JUDGMENTS_CSV = DATA / "rec_judgments.csv"


def _bootstrap() -> None:
    if "app.recommend.core" in sys.modules:
        return
    sys.path.insert(0, str(API))
    for name, path in (("app", API / "app"), ("app.recommend", API / "app" / "recommend")):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(path)]
            sys.modules[name] = mod


_bootstrap()
from app.recommend import core  # noqa: E402

# Nhãn câu trả lời khảo sát → tham số. Lựa chọn nhiều chứa dấu phẩy ("Tiện nghi (máy lạnh, wifi…)") nên
# so khớp theo nhãn đầy đủ, KHÔNG tách theo dấu phẩy.
BUDGET = {"Dưới 1,5 triệu": 1_500_000, "1,5 – 2 triệu": 2_000_000, "2 – 2,5 triệu": 2_500_000,
          "2,5 – 3,5 triệu": 3_500_000, "Trên 3,5 triệu": 4_500_000}
COMMUTE = {"Dưới 5 phút": 5, "5–10 phút": 10, "10–15 phút": 15, "15–20 phút": 20,
           "Trên 20 phút cũng được nếu rẻ": 30}
AMENITY = {"Wifi / internet": "wifi", "Máy lạnh": "air_conditioner", "WC riêng trong phòng": "private_wc",
           "Chỗ để xe": "parking", "Được nấu ăn / có bếp": "kitchen", "Tủ lạnh": "fridge",
           "Máy giặt": "washing_machine", "Giờ giấc tự do": "free_hours"}  # "Gác lửng" chưa có trong crawler
FACTOR = {"Giá thuê rẻ": "gia", "Gần trường / đi lại nhanh": "gan_truong", "An ninh khu vực": None,
          "Giờ giấc tự do, chủ không ở chung": "gio_tu_do", "Tiện nghi (máy lạnh, wifi, WC riêng…)": "tien_nghi",
          "Có chỗ để xe": "cho_de_xe", "Gần chợ / quán ăn": "gan_cho"}


def _labels(cell: str, mapping: dict) -> list[str]:
    return [label for label in mapping if label in (cell or "")]


def survey_rows() -> list[dict]:
    with open(SURVEY_CSV, encoding="utf-8") as f:
        return [{k: r[k] for k in ("budget", "max_commute", "required_amenities", "top3_factors")}
                for r in csv.DictReader(f)]


def survey_top3_counts() -> dict[str, int]:
    """Tính lại SURVEY_TOP3 từ CSV — notebook assert khớp hằng số trong core.py."""
    counts: dict[str, int] = {}
    for r in survey_rows():
        for label in _labels(r["top3_factors"], FACTOR):
            if FACTOR[label]:
                counts[FACTOR[label]] = counts.get(FACTOR[label], 0) + 1
    return counts


def survey_queries(campus: int = 1) -> list[core.Query]:
    """31 bộ tiêu chí thật. Khảo sát không lưu câu khu học ⇒ mặc định khu II (giả định ghi trong báo cáo)."""
    out = []
    for r in survey_rows():
        if r["budget"] not in BUDGET or r["max_commute"] not in COMMUTE:
            continue
        out.append(core.Query(
            budget=BUDGET[r["budget"]], campus=campus, max_minutes=COMMUTE[r["max_commute"]],
            required=tuple(AMENITY[a] for a in _labels(r["required_amenities"], AMENITY)),
            top_factors=tuple(FACTOR[f] for f in _labels(r["top3_factors"], FACTOR) if FACTOR[f]),
        ))
    return out


def load_candidates(path: Path = CANDIDATES_CSV) -> list[core.Candidate]:
    def num(v: str) -> float | None:
        return float(v) if v != "" else None
    with open(path, encoding="utf-8") as f:
        return [core.Candidate(
            id=int(r["id"]), price=int(r["price"]), minutes=(num(r["m0"]), num(r["m1"]), num(r["m2"])),
            amenities=frozenset(a for a in r["amenities"].split("|") if a),
            free_hours=None if r["free_hours"] == "" else bool(int(r["free_hours"])),
            listing_type=r["listing_type"] or None, gender_only=r["gender_only"] or None,
            lat=float(r["lat"]), lng=float(r["lng"]), market_pois=int(r["market_pois"]),
            quality=float(r["quality"] or 0),
        ) for r in csv.DictReader(f)]


def run_systems(cands: list[core.Candidate], q: core.Query, k: int = 10) -> dict[str, list[core.Candidate]]:
    top, _, _ = core.recommend(cands, q, k)
    return {"de_xuat": [s.c for s in top], "b_gia": core.baseline_price(cands, q, k),
            "b_cosine": core.baseline_cosine(cands, q, k)}


def satisfies(c: core.Candidate, q: core.Query) -> bool:
    """Ràng buộc GỐC người dùng khai (không nới): giá ≤ ngân sách, phút ≤ T, đúng loại."""
    m = c.minutes[q.campus]
    return (m is not None and m <= q.max_minutes and c.price <= q.budget
            and (not q.housing or c.listing_type == q.housing))

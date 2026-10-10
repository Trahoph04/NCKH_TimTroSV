"""Rà soát chất lượng tin đang hiển thị — chỉ giữ tin SẠCH (quyết định 07/10/2026: nhóm sẽ thay bằng bộ dữ liệu
khảo sát riêng, nên tin chưa sạch loại hẳn khỏi hệ thống).

Sạch = vị trí chính xác + còn trên nguồn + đủ thông tin + trong phạm vi. Hai tầng:
  1. luật offline (không gọi mạng) — tin mẫu, ngoài phạm vi, vị trí cấp phường, giá bất thường, thiếu thông tin, trùng
  2. kiểm qua mạng, chỉ cho tin qua tầng 1 — tin còn trên nguồn (Chợ Tốt: gateway JSON; nguồn khác: HTTP), toạ độ nằm
     đúng con đường ghi trong địa chỉ (Nominatim reverse, 1 request/giây đúng chính sách OSM)

Loại = KHÔNG xoá: tin đã gỡ khỏi nguồn → status 'expired'; còn lại → 'hidden'; lý do ghi `audit_reason` (mig 98).
Khôi phục: UPDATE aggregated_listings SET status='active', audit_reason=NULL WHERE audit_reason IS NOT NULL.

Hai chế độ (ADR-022 sửa đổi 07/10):
  --policy system (mặc định) — loại tin BẨN, GIỮ tin thật chỉ có toạ độ cấp phường với location_precise = FALSE
                               (bản đồ mặc định không cắm ghim chúng, danh sách/gợi ý vẫn dùng)
  --policy strict            — loại luôn tin vị trí không chính xác (bộ dữ liệu demo tối giản)
Tin Chợ Tốt đã gỡ: `--nhatot-seen-since <ISO>` = mọi tin nhatot không được crawl full thấy kể từ mốc đó (đã kiểm mẫu
07/10: 29/30 tin không thấy trả 404). Không có cờ này thì hỏi gateway từng tin (chậm).

  docker compose exec api python -m app.cleaner.audit                         # chỉ đếm (không gọi mạng)
  docker compose exec api python -m app.cleaner.audit --network --apply \
      --nhatot-seen-since 2026-10-07T13:00+07:00                               # sau 1 lượt crawl nhatot full
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime

import httpx
from sqlalchemy import create_engine, text

from app.config import settings
from app.listings.repo import visible_clause

log = logging.getLogger("cleaner.audit")

KHU_II = (10.0322, 105.7683)
# tâm 3 khu CTU + hằng CTU_LAT/LNG của geocode.py: toạ độ trùng các điểm này là tâm hành chính/landmark,
# không phải nhà trọ (tâm phường Hưng Lợi rơi ngay cổng khu I → tin hiện "1 phút tới khu I")
CAMPUS_POINTS = ((10.0159, 105.7656), (10.0322, 105.7683), (10.0340, 105.7798), (10.0301, 105.7681))
MAX_KM_FROM_KHU_II = 8.0     # phạm vi thuyết minh: Ninh Kiều và lân cận
CAMPUS_PIN_M = 150
# Nguồn có toạ độ do NGƯỜI biết chỗ đặt: người đăng tự ghim (Chợ Tốt) hoặc nhóm đo tại chỗ (khảo sát thực địa).
PINNED_SOURCES = ("nhatot", "survey")
# Nhóm tự xác minh tại chỗ ⇒ không áp luật "≥ 3 ảnh" (luật đó đo độ tin cậy của tin crawl), không có link nguồn để kiểm.
FIELD_SOURCES = ("survey",)
USER_AGENT = "TroCTU-NCKH/1.0 (contact: phub2303891@student.ctu.edu.vn)"

REASONS = {
    "tin_mau": "tin mẫu (seed) — URL giả, ảnh kho",
    "khong_toa_do": "không có toạ độ",
    "ngoai_pham_vi": f"cách khu II > {MAX_KM_FROM_KHU_II:g} km",
    "vi_tri_cap_phuong": "toạ độ chỉ tới cấp phường/đường (điểm mặc định, dùng chung, trùng tâm trường, thiếu số nhà)",
    "gia_bat_thuong": "giá thiếu hoặc ngoài khoảng 0,7–8 tr (nhà mini 10 tr)",
    "thieu_thong_tin": "dưới 3 ảnh hoặc mô tả < 50 ký tự (tin khảo sát: chỉ cần mô tả ≥ 20 ký tự)",
    "sang_nhuong": "tin pass phòng/sang nhượng — điều khoản cọc, hợp đồng do người thuê cũ nói, chưa kiểm được",
    "trung_lap": "trùng tiêu đề + giá với tin khác (giữ bản nhiều ảnh nhất)",
    "da_go_khoi_nguon": "tin đã bị gỡ khỏi trang nguồn",
    "sai_duong": "toạ độ không nằm trên con đường ghi trong địa chỉ",
}


def _norm(s: str | None) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip()


def _dist_m(lat1, lng1, lat2, lng2) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def _points(rows: list[dict]) -> dict[tuple, set]:
    # điểm dùng chung bởi ≥ 2 địa chỉ KHÁC NHAU = điểm mặc định/tâm đường (cùng địa chỉ nhiều phòng thì vẫn hợp lệ)
    by_point: dict[tuple, set] = defaultdict(set)
    for r in rows:
        if r["lat"] is not None:
            by_point[(round(r["lat"], 6), round(r["lng"], 6))].add(_norm(r["street"] or r["address"]))
    return by_point


def is_imprecise(r: dict, by_point: dict[tuple, set]) -> bool:
    """Toạ độ chỉ tới cấp phường/đường (tin có thể vẫn thật)."""
    return (r["geocode_confidence"] != "high"
            or len(by_point[(round(r["lat"], 6), round(r["lng"], 6))]) >= 2
            or any(_dist_m(r["lat"], r["lng"], la, ln) <= CAMPUS_PIN_M for la, ln in CAMPUS_POINTS)
            # nguồn HTML không có ghim của người đăng: chỉ tin địa chỉ có số nhà mới có thể chính xác
            or (r["source"] not in PINNED_SOURCES and r["address_confidence"] != "exact"))


def imprecise_ids(rows: list[dict]) -> set[int]:
    by_point = _points(rows)
    return {r["id"] for r in rows if r["lat"] is not None and is_imprecise(r, by_point)}


def offline_reasons(rows: list[dict], keep_imprecise: bool = False) -> dict[int, str]:
    """Tầng 1 — luật không cần mạng. rows: tin đang hiển thị (dict có các cột của load()). Trả {id: lý do}.

    Luật "bẩn" xét TRƯỚC luật vị trí: tin vừa cấp phường vừa thiếu ảnh phải bị loại vì thiếu ảnh — nếu chỉ ghi
    "vị trí" thì chế độ system (giữ tin cấp phường) sẽ giữ nhầm nó. keep_imprecise=True: không loại vì vị trí.
    """
    out: dict[int, str] = {}
    by_point = _points(rows)
    for r in rows:
        imgs = r["images"] or []
        if r["source"] == "ugc" or any("unsplash.com" in (u or "") for u in imgs):
            out[r["id"]] = "tin_mau"
        elif r["lat"] is None:
            out[r["id"]] = "khong_toa_do"
        elif _dist_m(r["lat"], r["lng"], *KHU_II) > MAX_KM_FROM_KHU_II * 1000:
            out[r["id"]] = "ngoai_pham_vi"
        elif (r["price"] is None or r["price"] < 700_000
              or r["price"] > (10_000_000 if r["listing_type"] == "nha_mini" else 8_000_000)):
            out[r["id"]] = "gia_bat_thuong"
        elif (r["source"] not in FIELD_SOURCES and (len(imgs) < 3 or len(r["description"] or "") < 50)) \
                or (r["source"] in FIELD_SOURCES and len(r["description"] or "") < 20):
            out[r["id"]] = "thieu_thong_tin"
        elif r.get("offer_kind") == "lease_transfer":
            out[r["id"]] = "sang_nhuong"
        elif not keep_imprecise and is_imprecise(r, by_point):
            out[r["id"]] = "vi_tri_cap_phuong"

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["id"] not in out:
            groups[(_norm(r["title"]), r["price"])].append(r)
    for g in groups.values():
        if len(g) > 1:
            g.sort(key=lambda r: (-len(r["images"] or []), -(r["last_seen"].timestamp() if r["last_seen"] else 0), r["id"]))
            for r in g[1:]:
                out[r["id"]] = "trung_lap"
    return out


def street_matches(street: str | None, osm_road: str | None) -> bool:
    """Tên đường trong địa chỉ tin ↔ tên đường OSM tại toạ độ (bỏ số nhà, 'hẻm N', 'đường')."""
    kw = re.sub(r"^(\d+[\w/]*\s*,?\s+)?(hem \d+[\w/]*\s*,?\s+)?(duong\s+)?", "", _norm(street))
    road = re.sub(r"^duong\s+", "", _norm(osm_road))
    if not kw or not road:
        return False
    return kw[:8] in road or road[:8] in kw


def network_checks(rows: list[dict], alive_ids: set[int] | None = None,
                   street_ids: set[int] | None = None) -> dict[int, str]:
    """Tầng 2 — chỉ gọi cho tin đã qua tầng 1. Trả {id: 'da_go_khoi_nguon' | 'sai_duong'}.

    alive_ids / street_ids: chỉ kiểm tin còn sống / khớp đường cho các id này (None = mọi tin) — khớp đường chỉ có
    nghĩa với tin đang được coi là vị trí chính xác.
    """
    out: dict[int, str] = {}
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as cli:
        for i, r in enumerate(rows, 1):
            if alive_ids is not None and r["id"] not in alive_ids:
                alive = True
            else:
                alive = _alive(cli, r)
            if not alive:
                out[r["id"]] = "da_go_khoi_nguon"
                continue
            if street_ids is not None and r["id"] not in street_ids:
                continue
            try:
                rev = cli.get("https://nominatim.openstreetmap.org/reverse",
                              params={"lat": r["lat"], "lon": r["lng"], "format": "jsonv2", "zoom": 17}).json()
                road = (rev.get("address") or {}).get("road")
                if not street_matches(r["street"], road):
                    out[r["id"]] = "sai_duong"
            except Exception as exc:  # noqa: BLE001
                log.warning("reverse #%s lỗi: %s", r["id"], exc)
            time.sleep(1.1)
            if i % 25 == 0:
                log.info("đã kiểm %d/%d", i, len(rows))
    return out


def _alive(cli: httpx.Client, r: dict) -> bool:
    try:
        if r["source"] == "nhatot":
            # trang nhatot.com chặn bot (403); gateway JSON công khai mà crawler dùng trả 404 khi tin bị gỡ
            ok = cli.get(f"https://gateway.chotot.com/v1/public/ad-listing/{r['source_id']}").status_code == 200
            time.sleep(1.5)
        else:
            ok = cli.get(r["source_url"]).status_code not in (404, 410)
            time.sleep(1.0)
        return ok
    except Exception as exc:  # noqa: BLE001 — mạng lỗi: KHÔNG kết luận tin đã gỡ
        log.warning("liveness #%s lỗi mạng: %s", r["id"], exc)
        return True


def load(engine) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            f"""
            SELECT id, source, source_id, source_url, title, price, listing_type::text AS listing_type, images,
                   description, street, address, address_confidence, geocode_confidence, last_seen, offer_kind,
                   ST_Y(geom) AS lat, ST_X(geom) AS lng
            FROM aggregated_listings
            WHERE status NOT IN ('expired', 'hidden') AND {visible_clause(None)} AND source <> 'user'
            """
        )).mappings()]


def apply(engine, reasons: dict[int, str], precise: dict[int, bool]) -> None:
    with engine.begin() as conn:
        for lid, reason in reasons.items():
            conn.execute(text(
                "UPDATE aggregated_listings SET status = CAST(:st AS listing_status), audit_reason = :r, "
                "audit_at = now() WHERE id = :id"
            ), {"st": "expired" if reason == "da_go_khoi_nguon" else "hidden", "r": reason, "id": lid})
        for lid, ok in precise.items():
            conn.execute(text("UPDATE aggregated_listings SET location_precise = :p WHERE id = :id"),
                         {"p": ok, "id": lid})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=("system", "strict"), default="system")
    ap.add_argument("--network", action="store_true", help="kiểm tin còn trên nguồn + toạ độ đúng đường (chậm)")
    ap.add_argument("--nhatot-seen-since", help="ISO time của lượt crawl nhatot full: tin không thấy từ mốc này = đã gỡ")
    ap.add_argument("--apply", action="store_true", help="ghi DB (mặc định chỉ đếm)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine = create_engine(settings.database_url)
    rows = load(engine)
    strict = args.policy == "strict"
    reasons = offline_reasons(rows, keep_imprecise=not strict)
    imprecise = imprecise_ids(rows)

    if args.nhatot_seen_since:
        since = datetime.fromisoformat(args.nhatot_seen_since)
        for r in rows:
            if r["id"] not in reasons and r["source"] == "nhatot" and (r["last_seen"] is None or r["last_seen"] < since):
                reasons[r["id"]] = "da_go_khoi_nguon"
    if args.network:
        rest = [r for r in rows if r["id"] not in reasons]
        alive_ids = {r["id"] for r in rest if r["source"] not in FIELD_SOURCES
                     and not (args.nhatot_seen_since and r["source"] == "nhatot")}
        street_ids = {r["id"] for r in rest if r["id"] not in imprecise and r["source"] not in FIELD_SOURCES}
        log.info("tầng 2: kiểm sống %d tin, khớp đường %d tin", len(alive_ids), len(street_ids))
        for lid, why in network_checks(rest, alive_ids, street_ids).items():
            if why == "sai_duong" and not strict:
                imprecise.add(lid)  # toạ độ lệch đường: vẫn là tin thật, chỉ không chính xác
            else:
                reasons[lid] = why

    kept = [r for r in rows if r["id"] not in reasons]
    precise = {r["id"]: r["id"] not in imprecise for r in kept}
    counts = Counter(reasons.values())
    report = {"policy": args.policy, "visible_before": len(rows), "kept": len(kept),
              "kept_precise": sum(precise.values()), "kept_approximate": len(kept) - sum(precise.values()),
              "removed": {k: counts.get(k, 0) for k in REASONS if counts.get(k)}, "network": args.network}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    if args.apply:
        apply(engine, reasons, precise)
        print("ĐÃ GHI — loại", len(reasons), "tin; gắn location_precise cho", len(precise), "tin")
    else:
        print("(chỉ đếm — thêm --apply để ghi)")


if __name__ == "__main__":
    main()

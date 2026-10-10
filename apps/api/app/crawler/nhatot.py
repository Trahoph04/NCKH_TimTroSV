"""Nguồn nhatot.com (Chợ Tốt) qua JSON gateway công khai — KHÔNG parse HTML.

Vì sao nguồn này đáng giá nhất:
  - có `latitude/longitude` cho mọi tin → geocode_confidence='high', NHƯNG tin không được người
    đăng ghim nhận điểm mặc định của phường → repo.mark_shared_coords hạ về 'medium' sau mỗi run
    (đo 07/10: 610 tin / 61 điểm). Các nguồn HTML khác chỉ ra được cấp phường, xem ADR-011.
  - có `deposit` (tiền cọc) là field riêng
  - `body` dài, chủ trọ hay ghi điện/nước/giới tính → extras.py trích được
  - 1 request = 50 tin, không cần fetch detail từng tin (≈14 request cho cả Cần Thơ)

Endpoint (verified 13/09/2026):
  GET https://gateway.chotot.com/v1/public/ad-listing?region_v2=5027&cg=1050&limit=50&o=<offset>
  region_v2=5027 = Cần Thơ, area_v2=502701 = Ninh Kiều, cg=1050 = "Phòng trọ".
  Response: {"total": N, "ads": [...]}. SĐT bị che (***) — không lấy, không cần.
  URL công khai của tin: https://www.nhatot.com/<list_id>.htm (redirect sang slug đầy đủ).

Lịch sự: 2 s/request, UA định danh, dừng khi ads rỗng. Không đăng nhập, không bypass gì.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .address import canon_district, canon_ward, compose
from .contact import extract_contact
from .extras import extract_extras
from .geocode import CTU_LAT, CTU_LNG, haversine_m
from .normalize import compute_content_hash, infer_district, parse_amenities
from .schemas import NormalizedListing

log = logging.getLogger("crawler.nhatot")

GATEWAY = "https://gateway.chotot.com/v1/public/ad-listing"
REGION_CAN_THO = 5027
AREA_NINH_KIEU = 502701
CATEGORY_PHONG_TRO = 1050
PAGE_SIZE = 50
DELAY_S = 2.0
USER_AGENT = "TroCTU-NCKH/1.0 (contact: phub2303891@student.ctu.edu.vn)"

# Ninh Kiều bao trọn 3 khu CTU; các quận khác (Cái Răng, Bình Thuỷ) cách >3 km,
# vẫn lấy để thống kê nhưng incremental chỉ quét Ninh Kiều cho nhẹ.
AREAS_FULL = [502701, 502703, 502704]  # Ninh Kiều, Bình Thuỷ, Cái Răng
AREAS_INCREMENTAL = [502701]


def _address(ad: dict) -> str | None:
    parts = [
        (ad.get("street_number") or "").strip(),
        (ad.get("street_name") or "").strip(),
        (ad.get("ward_name") or "").strip(),
        (ad.get("area_name") or "").strip(),
        "Cần Thơ",
    ]
    s = ", ".join(p for p in parts if p)
    # "85/26 , Đường Phạm Ngũ Lão" → "85/26 Đường Phạm Ngũ Lão"
    if parts[0] and parts[1]:
        s = s.replace(f"{parts[0]}, {parts[1]}", f"{parts[0]} {parts[1]}", 1)
    return s or None


def ad_to_address(ad: dict) -> dict:
    """Địa chỉ chuẩn hoá từ field riêng của Chợ Tốt — chính xác hơn mọi nguồn HTML."""
    num = (ad.get("street_number") or "").strip()
    road = (ad.get("street_name") or "").strip()
    street = " ".join(p for p in (num, road) if p) or None
    ward = canon_ward(ad.get("ward_name")) or (ad.get("ward_name") or "").replace("Phường ", "").strip() or None
    dist = canon_district(ad.get("area_name"))
    conf = "exact" if (num and road) else "street" if road else "ward" if ward else "district" if dist else "none"
    return {
        "address_full": compose(street, ward, dist),
        "street": street, "ward": ward, "district_norm": dist,
        "address_confidence": conf, "address_source": "source",
    }


def ad_to_listing(ad: dict) -> NormalizedListing:
    """Map 1 ad JSON → NormalizedListing (+ extras đính ở attr `extras`)."""
    title = (ad.get("subject") or "").strip()
    body = ad.get("body") or ""
    lat, lng = ad.get("latitude"), ad.get("longitude")
    n = NormalizedListing(
        source="nhatot",
        source_id=str(ad["list_id"]),
        source_url=f"https://www.nhatot.com/{ad['list_id']}.htm",
        title=title,
        price=int(ad["price"]) if ad.get("price") else None,
        area=float(ad["size"]) if ad.get("size") else None,
        address=_address(ad),
        district=(ad.get("area_name") or "").replace("Quận ", "").replace("Huyện ", "").strip()
        or infer_district(ad.get("area_name"), title),
        description=body.strip() or None,
        images=list(ad.get("images") or []),
        amenities=parse_amenities(body, title),
        seen_at=datetime.fromtimestamp((ad.get("list_time") or 0) / 1000, tz=timezone.utc)
        if ad.get("list_time") else None,
    )
    if lat and lng and 9.5 < float(lat) < 10.6 and 105.2 < float(lng) < 106.2:
        n.lat, n.lng, n.geocode_confidence = float(lat), float(lng), "high"
        n.distance_to_ctu = haversine_m(n.lat, n.lng, CTU_LAT, CTU_LNG)
    else:
        n.geocode_confidence = "failed"  # pipeline sẽ geocode theo address như nguồn khác
    n.content_hash = compute_content_hash(n)

    n.address_norm = ad_to_address(ad)
    # SĐT trên Chợ Tốt bị che (***) → thường rỗng; chỉ lấy nếu người đăng tự ghi trong body.
    # account_name là tên người đăng do chính họ đặt → dùng làm contact_name khi body không có.
    ct = extract_contact(title, body, source="listing_field")
    if not ct.contact_name and ad.get("account_name"):
        ct.contact_name = str(ad["account_name"])[:80]
        ct.contact_source = ct.contact_source or "listing_field"
    n.contact = ct.as_dict()

    ex = extract_extras(title, body)
    # nhatot có field cọc riêng → ưu tiên hơn regex
    if ad.get("deposit"):
        ex.deposit_amount = int(ad["deposit"])
    n.extras = ex.as_dict()
    return n


async def fetch_ads(
    client: httpx.AsyncClient,
    area_v2: int | None = None,
    max_pages: int | None = None,
) -> list[dict]:
    ads: list[dict] = []
    offset, page = 0, 0
    while True:
        params = {"region_v2": REGION_CAN_THO, "cg": CATEGORY_PHONG_TRO,
                  "limit": PAGE_SIZE, "o": offset}
        if area_v2:
            params["area_v2"] = area_v2
        r = await client.get(GATEWAY, params=params, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        data = r.json()
        batch = data.get("ads") or []
        if page == 0:
            log.info("nhatot area=%s total=%s", area_v2, data.get("total"))
        ads.extend(batch)
        page += 1
        if len(batch) < PAGE_SIZE or (max_pages and page >= max_pages):
            break
        offset += PAGE_SIZE
        await asyncio.sleep(DELAY_S)
    return ads


async def run_nhatot(repo, mode: str = "incremental") -> dict:
    """Crawl nhatot → upsert + extras. Cùng hợp đồng trả về như run_source()."""
    run_id = repo.start_run("nhatot", mode)
    counts = {"fetched": 0, "new_count": 0, "updated_count": 0, "expired_count": 0, "error": None}
    areas = AREAS_INCREMENTAL if mode == "incremental" else AREAS_FULL
    max_pages = 2 if mode == "incremental" else None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            all_ads: list[dict] = []
            for area in areas:
                all_ads.extend(await fetch_ads(client, area_v2=area, max_pages=max_pages))
                await asyncio.sleep(DELAY_S)
        counts["fetched"] = len(all_ads)

        seen_ids: list[str] = []
        for ad in all_ads:
            if not ad.get("list_id") or ad.get("category") not in (None, CATEGORY_PHONG_TRO):
                continue
            n = ad_to_listing(ad)
            result = repo.upsert(n)
            repo.set_extras("nhatot", n.source_id, n.extras)
            repo.set_contact("nhatot", n.source_id, n.contact)
            repo.set_address("nhatot", n.source_id, n.address_norm)
            seen_ids.append(n.source_id)
            if result == "new":
                counts["new_count"] += 1
            elif result == "updated":
                counts["updated_count"] += 1

        if mode == "full":
            counts["expired_count"] = repo.mark_misses("nhatot", seen_ids)
        # upsert vừa ghi lại 'high' cho mọi tin → hạ lại các điểm mặc định của phường
        repo.mark_shared_coords("nhatot")
        repo.refresh_scores()
        from .pipeline import auto_route  # import trong hàm: pipeline import nhatot gián tiếp qua __init__
        await auto_route(repo, "nhatot")
    except Exception as exc:  # noqa: BLE001
        counts["error"] = str(exc)
        repo.finish_run(run_id, **counts)
        raise
    repo.finish_run(run_id, **counts)
    log.info("nhatot done mode=%s %s", mode, counts)
    return counts

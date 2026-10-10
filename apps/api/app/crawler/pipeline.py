import logging

import httpx

from .dedup import find_duplicates
from .fetcher import BlockedError, Fetcher
from .address import normalize_address
from .contact import extract_contact
from .extras import extract_extras
from .geocode import CTU_LAT, CTU_LNG, Geocoder, haversine_m
from .normalize import normalize
from .parser import (
    list_page_urls,
    load_source_config,
    parse_detail_page,
    parse_list_page,
)
from .repo import ListingRepo
from .schemas import NormalizedListing

log = logging.getLogger("crawler.pipeline")


def process_html_pages(source: str, pages_html: list[str]) -> list[NormalizedListing]:
    """Pure: HTML → parse → normalize → dedup. Test được không cần mạng/DB."""
    config = load_source_config(source)
    raws = []
    for html in pages_html:
        raws.extend(parse_list_page(html, config))

    normalized = [normalize(r) for r in raws]

    # cross-source dedup: bỏ bản trùng, gộp source_url giữ bản đại diện
    dup_map = find_duplicates(normalized)
    deduped = [n for i, n in enumerate(normalized) if i not in dup_map]
    log.info("source=%s parsed=%d deduped=%d", source, len(normalized), len(deduped))
    return deduped


def merge_detail(n: NormalizedListing, detail: dict, base_url: str = "") -> NormalizedListing:
    """Gộp field từ detail page vào listing đã normalize (address/images/price ưu tiên detail)."""
    from urllib.parse import urljoin

    from .normalize import compute_content_hash, extract_area_from_text, parse_price

    if detail.get("address"):
        n.address = detail["address"]
    if detail.get("description"):
        n.description = detail["description"]
    if detail.get("contact_text"):
        n.contact_text = detail["contact_text"]
    if detail.get("images"):
        # ảnh detail có thể là relative path (vd tromoi /storage/...) → urljoin base
        n.images = [urljoin(base_url, u) if base_url else u for u in detail["images"]]
    if detail.get("price_text"):
        p = parse_price(detail["price_text"])
        if p:
            n.price = p
    # diện tích: trích đa biến thể từ description/title (label, kích thước, m vuông)
    if n.area is None:
        n.area = extract_area_from_text(n.description, n.title)
    n.content_hash = compute_content_hash(n)
    return n


async def auto_route(repo: ListingRepo, source: str) -> int:
    """Phút tới 3 khu cho tin có geom nhưng chưa route_time_campus (tin mới, hoặc tin cũ lỡ sót), 1 call ORS
    Matrix. KHÔNG route lại toàn bộ. Thiếu key/lỗi mạng → skip êm, không làm hỏng cả crawl job. Dùng chung cho
    crawler HTML và nhatot (trước 07/10 nhatot không gọi ⇒ 126 tin Chợ Tốt mới không có "X phút tới trường")."""
    from ..config import settings as _settings
    if not _settings.ors_api_key:
        log.info("ORS_API_KEY rỗng — skip auto-route source=%s", source)
        return 0
    pending = repo.pending_route()
    if not pending:
        return 0
    try:
        from ..listings.routing import matrix_minutes
        times = await matrix_minutes([(r["lat"], r["lng"]) for r in pending])
    except Exception as exc:  # noqa: BLE001 — routing lỗi không crash crawl job
        log.warning("auto-route fail source=%s: %s", source, exc)
        return 0
    updates = [(r["id"], t) for r, t in zip(pending, times) if t is not None]
    repo.set_route_times(updates)
    log.info("auto-route source=%s routed=%d/%d", source, len(updates), len(pending))
    return len(updates)


async def run_source(
    source: str,
    mode: str,
    repo: ListingRepo,
    fetcher: Fetcher | None = None,
    geocoder: "Geocoder | None" = None,
) -> dict:
    """Crawl một nguồn theo mode. Ghi crawl_runs, upsert listings, geocode, freshness."""
    config = load_source_config(source)
    run_id = repo.start_run(source, mode)
    counts = {"fetched": 0, "new_count": 0, "updated_count": 0,
              "expired_count": 0, "error": None}

    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    own_geocoder = geocoder is None
    geocoder = geocoder or Geocoder()
    try:
        pages_html: list[str] = []
        for url in list_page_urls(config, mode):
            try:
                pages_html.append(await fetcher.get(url))
                counts["fetched"] += 1
            except BlockedError as exc:
                # T1: bị chặn → log + alert + bỏ nguồn (không làm hỏng cả pipeline)
                counts["error"] = str(exc)
                log.warning("BLOCKED source=%s: %s", source, exc)
                break
            except httpx.HTTPStatusError as exc:
                # URL list sai/hết trang (404/410/5xx) → dừng nguồn này, không crash job
                counts["error"] = str(exc)
                log.warning("HTTP %s source=%s url=%s", exc.response.status_code, source, url)
                break

        listings = process_html_pages(source, pages_html)

        # tầng 2: fetch detail page lấy đủ field (giới hạn cho incremental)
        max_detail = config.get("max_detail_incremental", 20) if mode == "incremental" else len(listings)
        for n in listings[:max_detail]:
            if not n.source_url:
                continue
            try:
                detail_html = await fetcher.get(n.source_url)
                merge_detail(n, parse_detail_page(detail_html, config), config.get("base_url", ""))
            except BlockedError as exc:
                counts["error"] = str(exc)
                log.warning("BLOCKED detail source=%s: %s", source, exc)
                break
            except Exception as exc:  # noqa: BLE001 — 1 detail lỗi không làm hỏng cả run
                log.warning("detail fetch fail %s: %s", n.source_url, exc)

        # geocode (T2): address → lat/lng/confidence + distance_to_ctu.
        # Address rỗng/rác (vd bds123 "Xin chào Khách", mogi trống) → fallback district
        # để vẫn có toạ độ cấp quận (lên được bản đồ/nearby thay vì mất hẳn).
        for n in listings:
            lat, lng, conf = await geocoder.geocode(n.address)
            if lat is None and n.district:
                lat, lng, conf = await geocoder.geocode(f"{n.district}, Cần Thơ")
            n.lat, n.lng, n.geocode_confidence = lat, lng, conf
            if lat is not None and lng is not None:
                n.distance_to_ctu = haversine_m(lat, lng, CTU_LAT, CTU_LNG)

        for n in listings:
            result = repo.upsert(n)
            if result == "new":
                counts["new_count"] += 1
            elif result == "updated":
                counts["updated_count"] += 1
            if n.source_id and (result != "seen"):
                # thuộc tính mềm (điện/nước/cọc/giới tính) từ mô tả — migration 90
                repo.set_extras(n.source, n.source_id, extract_extras(n.title, n.description).as_dict())
                # liên hệ công khai + địa chỉ chuẩn hoá — migration 91
                repo.set_contact(n.source, n.source_id, extract_contact(
                    n.title, n.description, n.contact_text,
                    source="detail_page" if n.contact_text else "description",
                    ignore=config.get("ignore_phones"),
                ).as_dict())
                repo.set_address(n.source, n.source_id, normalize_address(
                    n.address, n.district, n.title, n.description,
                ))

        # full sweep: tin không thấy → miss_count++/expired
        if mode == "full":
            seen_ids = [n.source_id for n in listings if n.source_id]
            counts["expired_count"] = repo.mark_misses(source, seen_ids)

        repo.refresh_scores()

        await auto_route(repo, source)
    except Exception as exc:  # noqa: BLE001 — ghi lỗi vào run rồi re-raise cho scheduler log
        counts["error"] = str(exc)
        repo.finish_run(run_id, **counts)
        raise
    finally:
        if own_fetcher:
            await fetcher.__aexit__(None, None, None)
        if own_geocoder:
            await geocoder.__aexit__(None, None, None)

    repo.finish_run(run_id, **counts)
    log.info("run done source=%s mode=%s %s", source, mode, counts)
    return counts

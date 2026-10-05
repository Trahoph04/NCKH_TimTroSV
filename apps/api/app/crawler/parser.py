import json
import re
from pathlib import Path
from urllib.parse import urljoin
import hashlib

from selectolax.parser import HTMLParser, Node

from .schemas import RawListing

SOURCES_DIR = Path(__file__).parent / "sources"

_ATTR_RE = re.compile(r"^(.*?)::attr\((.+)\)$")


def load_source_config(source: str) -> dict:
    path = SOURCES_DIR / f"{source}.json"
    if not path.exists():
        raise FileNotFoundError(f"Không có selector config cho nguồn '{source}': {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _split_attr(selector: str) -> tuple[str, str | None]:
    """'a.x::attr(href)' -> ('a.x', 'href'); 'span.p' -> ('span.p', None)."""
    m = _ATTR_RE.match(selector)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return selector.strip(), None


def _extract(node: Node, selector: str | None) -> str | None:
    """Lấy text hoặc attr từ node con đầu tiên khớp 1 trong các selector (phân tách bằng ',')."""
    if not selector:
        return None
    for raw in selector.split(","):
        css, attr = _split_attr(raw)
        found = node.css_first(css)
        if found is None:
            continue
        if attr:
            val = found.attributes.get(attr)
        else:
            val = found.text(strip=True)
        if val:
            return val
    return None


def _extract_all(node: Node, selector: str | None) -> list[str]:
    out: list[str] = []
    if not selector:
        return out
    for raw in selector.split(","):
        css, attr = _split_attr(raw)
        for found in node.css(css):
            val = found.attributes.get(attr) if attr else found.text(strip=True)
            if val:
                out.append(val)
    return out


def parse_list_page(html: str, config: dict) -> list[RawListing]:
    """Trích danh sách RawListing từ HTML 1 trang list.

    item_mode:
      - "thumb_parent" (mặc định): item selector trỏ thumb, card = thumb.parent (phongtro123)
      - "self": item selector chính là card chứa đủ field (tromoi.com)
    """
    sel = config["selectors"]
    base = config.get("base_url", "")
    source = config["source"]
    item_mode = config.get("item_mode", "thumb_parent")
    tree = HTMLParser(html)

    cards: list[Node] = []
    for node in tree.css(sel["item"]):
        card = node.parent if item_mode == "thumb_parent" else node
        if card is not None:
            cards.append(card)

    listings: list[RawListing] = []
    for item in cards:
        anchor = item.css_first(sel.get("item_anchor", "a"))
        url = anchor.attributes.get(sel.get("item_url_attr", "href")) if anchor else None
        if url and base:
            url = urljoin(base, url)

        source_id = None
        if url:
            pat = sel.get("source_id_pattern")
            m = re.search(pat, url) if pat else (re.search(r"pr(\d+)\.html", url) or re.search(r"(\d{5,})", url))
            if m:
                source_id = m.group(1)
            else:
                # slug cuối path làm id ổn định (nguồn không có ID số, vd tromoi)
                slug = url.rstrip("/").split("/")[-1].split(".")[0]
                source_id = slug or hashlib.md5(url.encode("utf-8")).hexdigest()
            # source_id cột VARCHAR(100): slug dài → hash md5 (32 ký tự) để không tràn
            if source_id and len(source_id) > 100:
                source_id = hashlib.md5(source_id.encode("utf-8")).hexdigest()

        thumb_img = item.css_first(sel.get("thumb", "img"))
        images = []
        if thumb_img:
            src = thumb_img.attributes.get("src") or thumb_img.attributes.get("data-src")
            if src:
                images.append(src)

        listings.append(
            RawListing(
                source=source,
                source_id=source_id,
                source_url=url,
                title=_extract(item, sel.get("title")) or "",
                price_text=_extract(item, sel.get("price")),
                area_text=_extract(item, sel.get("area")),
                address=_extract(item, sel.get("address")),
                district=_extract(item, sel.get("district")),
                description=_extract(item, sel.get("description")),
                images=images,
                amenities_text=_extract(item, sel.get("amenities")),
            )
        )
    return listings


def parse_jsonld(html: str) -> dict | None:
    """Đọc JSON-LD schema.org (Hostel/Product/Place) — nguồn ổn định hơn CSS.

    Trả {name, description, address} nếu có, None nếu không.
    """
    tree = HTMLParser(html)
    for script in tree.css('script[type="application/ld+json"]'):
        raw = script.text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for d in candidates:
            if not isinstance(d, dict):
                continue
            if d.get("@type") in ("Hostel", "Product", "Place", "Apartment", "Accommodation", "Offer"):
                addr = d.get("address")
                street = addr.get("streetAddress") if isinstance(addr, dict) else None
                return {
                    "name": d.get("name"),
                    "description": d.get("description"),
                    "address": street,
                }
    return None


def parse_detail_page(html: str, config: dict) -> dict:
    """Trích field bổ sung từ detail page: address đầy đủ (JSON-LD), price/area, images."""
    det = config.get("detail", {})
    tree = HTMLParser(html)
    result: dict = {}

    ld = parse_jsonld(html)
    if ld:
        result["address"] = ld.get("address")
        result["description"] = ld.get("description")
        if ld.get("name"):
            result["title"] = ld["name"]

    # address từ CSS (nguồn không có JSON-LD, vd tromoi dùng .box-address)
    if not result.get("address"):
        addr = _extract(tree.root, det.get("address"))
        if addr:
            result["address"] = addr

    # title từ CSS h1 nếu JSON-LD không cho
    if not result.get("title"):
        title = _extract(tree.root, det.get("title"))
        if title:
            result["title"] = title

    # description body đầy đủ (JSON-LD desc thường bị cắt, thiếu "Diện tích: X m²")
    body = _extract(tree.root, det.get("description_body"))
    if body and len(body) > len(result.get("description") or ""):
        result["description"] = body

    # price chính trên detail (selector riêng, fs-5 lớn)
    price = _extract(tree.root, det.get("price"))
    if price:
        result["price_text"] = price

    # khối liên hệ (selector riêng mỗi nguồn, vd ".box-contact"). KHÔNG quét cả trang —
    # quét cả trang sẽ dính hotline/tổng đài của chính website thành "SĐT chủ trọ".
    contact = _extract(tree.root, det.get("contact"))
    if contact:
        result["contact_text"] = contact[:2000]

    # images: gallery, ưu tiên data-src (lazy-load)
    img_attr = det.get("images_attr", "src")
    img_filter = det.get("images_filter", "static123")  # substring CDN để lọc icon/logo
    imgs: list[str] = []
    for img in tree.css(det.get("images", "img")):
        src = img.attributes.get(img_attr) or img.attributes.get("src")
        if src and img_filter in src and src not in imgs:
            imgs.append(src)
    if imgs:
        result["images"] = imgs

    return result


def list_page_urls(config: dict, mode: str) -> list[str]:
    """Sinh URL các trang list theo mode (incremental ít trang, full nhiều trang)."""
    n = config["incremental_pages"] if mode == "incremental" else config["full_pages"]
    tmpl = config["list_url"] + config.get("list_page_param", "")
    return [tmpl.format(page=p) for p in range(1, n + 1)]

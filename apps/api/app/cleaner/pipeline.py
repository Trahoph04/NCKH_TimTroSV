import logging
import re

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.crawler.normalize import extract_area_from_text, _strip_accents

log = logging.getLogger("cleaner.pipeline")

# ── Labels dùng khi generate title placeholder ──
_TYPE_LABELS = {
    "phong_tro": "Phòng trọ",
    "nha_mini": "Nhà mini",
    "nha_nguyen_can": "Nhà nguyên căn",
    "mat_bang": "Mặt bằng",
    "khac": "Chỗ ở",
}

# Loại chỗ ở SV thuê được — search/map chỉ trả các loại này (listings/repo.py).
HOUSING_TYPES = ("phong_tro", "nha_mini")

# Khớp theo TỪ: bản cũ so chuỗi con nên "kho" bắt cả "không ngập", "Toàn Khoa" → 14 phòng trọ
# thật bị xếp mặt bằng (đo 07/10 trên DB).
_MAT_BANG = re.compile(r"\b(mat bang|kho|xuong|van phong|kinh doanh)\b")
# Tiêu đề Chợ Tốt hay viết "Trọ gần ĐHCT…", không có chữ "phòng".
_TRO = re.compile(r"\btro\b")
_ROOM_PARTS = re.compile(r"\bphong (ngu|khach|tam|bep|wc|ve sinh)\b")
# Đối chiếu nhãn rà soát văn bản của gói Chợ Tốt 789: bắt 165/168 tin mini_house, nhầm 1/614 phòng.
_NHA_MINI = re.compile(
    r"mini\s*-?\s*house|minh\s*house|can ho mini|chung cu mini|nha mini|can ho dich vu|studio|duplex"
)
# Chỉ xét TIÊU ĐỀ: mô tả hay có câu "không cho sang nhượng hợp đồng" → dương tính giả.
_LEASE_TRANSFER = re.compile(
    r"\bpass (lai )?(phong|tro|hop dong)\b|\bcan pass\b|\bsang nhuong\b|\bnhuong lai\b"
)


def _impute_area_from_price(price: int | None) -> float:
    """Heuristic đoán diện tích theo mức giá khi không có area/regex."""
    if not price or price <= 0:
        return 0.0
    if price < 1_000_000:
        return 15.0
    elif price < 1_500_000:
        return 20.0
    elif price < 2_500_000:
        return 25.0
    elif price < 4_000_000:
        return 30.0
    return 40.0


# ── T1: Phân loại ──
def classify(title: str | None, price: int | None, area: float | None, source: str | None = None) -> str:
    """Phân loại listing_type từ title (bỏ dấu, lowercase) + giá/diện tích fallback."""
    blob = _strip_accents((title or "").lower())

    if _MAT_BANG.search(blob):
        return "mat_bang"

    # "Minihouse 2 phòng ngủ" — phòng ngủ/khách/tắm/bếp là mô tả căn, không phải "cho thuê phòng"
    room_blob = _ROOM_PARTS.sub(" ", blob)
    if any(
        kw in room_blob
        for kw in ("phong tro", "nha tro", "phong cho thue", "ky tuc", "o ghep", "phong ")
    ) or _TRO.search(room_blob):
        return "phong_tro"

    # Sau phong_tro: "Cho thuê phòng minihouse" là 1 phòng (gói 789 gắn room), còn tiêu đề
    # chỉ có "Minihouse…" trước đây lọt phong_tro nhờ luật giá/diện tích bên dưới.
    if _NHA_MINI.search(blob):
        return "nha_mini"

    if any(kw in blob for kw in ("nha nguyen can", "nha mat tien", "nguyen can", "biet thu")):
        return "nha_nguyen_can"
    if price is not None and price > 6_000_000 and area is not None and area > 60:
        return "nha_nguyen_can"

    if price is not None and price <= 4_000_000 and area is not None and area <= 40:
        return "phong_tro"

    # Tin khảo sát thực địa đều là nhà trọ nhóm đã tới tận nơi, nhưng tiêu đề là tên trọ ("TT HOME",
    # "2T House") và thường không đo diện tích ⇒ không luật nào bắt, rơi 'khac' và biến khỏi UI.
    # Chỉ áp ở cuối: tiêu đề có dấu hiệu mặt bằng/nhà mini/nguyên căn vẫn theo luật ở trên.
    if source == "survey":
        return "phong_tro"

    return "khac"


# ── T2: Validate giá theo loại ──
def validate(listing_type: str, price: int | None) -> tuple[bool, str | None]:
    """Kiểm tra giá hợp lý theo listing_type. Trả (is_valid, reject_reason)."""
    if price is None:
        return False, "Thiếu giá"

    if listing_type == "phong_tro":
        if 300_000 <= price <= 8_000_000:
            return True, None
        return False, "Giá ngoài khoảng phòng trọ"

    if listing_type == "nha_mini":
        # gói Chợ Tốt 789: nhà mini 2,6–6,2 tr; nới trần cho căn 2 phòng ngủ
        if 1_000_000 <= price <= 10_000_000:
            return True, None
        return False, "Giá ngoài khoảng nhà mini"

    if listing_type in ("nha_nguyen_can", "mat_bang"):
        if 1_000_000 <= price <= 50_000_000:
            return True, None
        return False, "Giá ngoài khoảng nhà/mặt bằng"

    # khac
    if 300_000 <= price <= 20_000_000:
        return True, None
    return False, "Giá bất thường"


# ── T3: Resolve diện tích ──
def resolve_area(
    area: float | None, price: int | None, description: str | None
) -> tuple[float, bool]:
    """Trả (area, is_imputed). Ưu tiên area có sẵn > regex mô tả > heuristic theo giá."""
    if area is not None and area > 0:
        return area, False

    extracted = extract_area_from_text(description)
    if extracted is not None:
        return extracted, False

    return _impute_area_from_price(price), True


# ── T4: Normalize title ──
def normalize_title(
    title: str | None, listing_type: str, area: float, district: str | None
) -> str:
    """Giữ title gốc nếu đủ dài (>=15 ký tự); ngược lại generate placeholder."""
    if title and len(title.strip()) >= 15:
        return title

    label = _TYPE_LABELS.get(listing_type, "Chỗ ở")
    return f"{label} {area}m² tại {district or 'Cần Thơ'}"


# ── T5: Quality score ──
def score(
    listing_type: str,
    is_imputed_area: bool,
    geocode_confidence: str | None,
    images,
    description: str | None,
    district: str | None,
) -> float:
    """Tổng điểm chất lượng, clamp [0,1], round 2 chữ số."""
    total = 0.0
    if listing_type in HOUSING_TYPES:
        total += 0.30
    if not is_imputed_area:
        total += 0.20
    if geocode_confidence in ("high", "medium"):
        total += 0.20
    if images:
        total += 0.15
    if description and len(description) >= 50:
        total += 0.10
    if district and district != "Không rõ":
        total += 0.05

    return round(max(0.0, min(1.0, total)), 2)


def detect_offer_kind(title: str | None) -> str | None:
    """'lease_transfer' khi tiêu đề là pass phòng/sang nhượng; None = không thấy dấu hiệu."""
    blob = _strip_accents((title or "").lower())
    return "lease_transfer" if _LEASE_TRANSFER.search(blob) else None


def run_cleaner(engine: Engine) -> None:
    """ETL pipeline 5 tầng: classify -> validate -> resolve_area -> normalize_title -> score."""
    log.info("Starting Data Cleaning Pipeline...")

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, title, price, area, description, district,
                       source, source_url, images, geocode_confidence
                FROM aggregated_listings
                WHERE cleaning_status = 'raw'
                """
            )
        ).mappings().all()

        if not rows:
            log.info("No raw rows to clean.")
            return

        cleaned_count = 0
        rejected_count = 0
        imputed_count = 0
        type_counts: dict[str, int] = {}

        for r in rows:
            l_id = r["id"]
            title = r["title"] or ""
            price = r["price"]
            area = r["area"]
            desc = r["description"]
            district = r["district"]
            images = r["images"]
            geocode_confidence = r["geocode_confidence"]

            logs: list[str] = []

            # 1. Classify
            lt = classify(title, price, area, r["source"])

            # 2. Validate
            is_valid, reason = validate(lt, price)
            if not is_valid:
                conn.execute(
                    text(
                        """
                        UPDATE aggregated_listings
                        SET listing_type = :listing_type,
                            cleaning_status = 'rejected',
                            quality_score = 0,
                            cleaning_logs = :logs,
                            updated_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"listing_type": lt, "logs": reason, "id": l_id},
                )
                rejected_count += 1
                type_counts[lt] = type_counts.get(lt, 0) + 1
                continue

            # 3. Resolve area
            resolved_area, is_imputed = resolve_area(area, price, desc)
            if is_imputed:
                logs.append(f"Area imputed: {resolved_area}")
            elif area is None or area <= 0:
                logs.append(f"Area extracted from description: {resolved_area}")

            # 4. Normalize title
            new_title = normalize_title(title, lt, resolved_area, district)
            if new_title != title:
                logs.append("Title normalized")

            # 5. Score
            q = score(lt, is_imputed, geocode_confidence, images, desc, district)

            conn.execute(
                text(
                    """
                    UPDATE aggregated_listings
                    SET title = :title,
                        area = :area,
                        listing_type = :listing_type,
                        cleaning_status = 'cleaned',
                        quality_score = :quality_score,
                        is_imputed_area = :is_imputed,
                        offer_kind = COALESCE(:offer_kind, offer_kind),
                        cleaning_logs = :logs,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "title": new_title,
                    "area": resolved_area,
                    "listing_type": lt,
                    "quality_score": q,
                    "is_imputed": is_imputed,
                    # COALESCE: nhãn do nguồn cấp (gói Chợ Tốt) không bị luật tiêu đề xoá
                    "offer_kind": detect_offer_kind(title),
                    "logs": " | ".join(logs) if logs else None,
                    "id": l_id,
                },
            )

            cleaned_count += 1
            type_counts[lt] = type_counts.get(lt, 0) + 1
            if is_imputed:
                imputed_count += 1

        type_summary = ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items()))
        log.info(
            f"Cleaner finished: Processed {len(rows)}, Cleaned {cleaned_count}, "
            f"Rejected {rejected_count}, Imputed Area {imputed_count}, Types: {type_summary}"
        )


def reclassify(engine: Engine, apply: bool = False) -> dict[tuple[str, str], int]:
    """Áp classifier mới lên tin ĐÃ xử lý, không chạy lại toàn pipeline. Trả {(cũ, mới): số tin}.

    Vì sao không set 'raw' cho tin 'cleaned' rồi run_cleaner: tầng resolve_area đã GHI ĐÈ `area` bằng
    số impute, chạy lại sẽ coi số đó là diện tích thật (is_imputed_area thành False). Nên ở đây chỉ
    tính lại listing_type / validate / quality_score từ cột đã lưu. Tin 'rejected' thì khác: nhánh
    reject không đụng area/title → đưa về 'raw' an toàn, run_cleaner làm nốt.
    """
    changes: dict[tuple[str, str], int] = {}
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, title, price, area, description, district, images, source,
                       geocode_confidence, is_imputed_area, listing_type, offer_kind,
                       cleaning_status, quality_score
                FROM aggregated_listings
                WHERE cleaning_status IN ('cleaned', 'rejected')
                """
            )
        ).mappings().all()

        for r in rows:
            # area đã impute không phải số đo → không cho luật dự phòng giá/diện tích dùng nó,
            # đúng như lúc run_cleaner phân loại lần đầu (area gốc khi đó là NULL).
            area = None if r["is_imputed_area"] else r["area"]
            lt = classify(r["title"], r["price"], area, r["source"])
            offer = detect_offer_kind(r["title"]) or r["offer_kind"]
            ok, reason = validate(lt, r["price"])

            if r["cleaning_status"] == "rejected":
                if ok:
                    key = (f"rejected:{r['listing_type']}", lt)
                    changes[key] = changes.get(key, 0) + 1
                    if apply:
                        conn.execute(
                            text("UPDATE aggregated_listings SET cleaning_status = 'raw' WHERE id = :id"),
                            {"id": r["id"]},
                        )
                continue

            q = score(lt, r["is_imputed_area"], r["geocode_confidence"], r["images"],
                      r["description"], r["district"])
            if lt == r["listing_type"] and q == r["quality_score"] and offer == r["offer_kind"] and ok:
                continue
            key = (r["listing_type"], lt if ok else f"{lt}:rejected")
            changes[key] = changes.get(key, 0) + 1
            if not apply:
                continue
            if ok:
                conn.execute(
                    text(
                        "UPDATE aggregated_listings SET listing_type = :lt, quality_score = :q, "
                        "offer_kind = :offer, updated_at = now() WHERE id = :id"
                    ),
                    {"lt": lt, "q": q, "offer": offer, "id": r["id"]},
                )
            else:
                conn.execute(
                    text(
                        "UPDATE aggregated_listings SET listing_type = :lt, cleaning_status = 'rejected', "
                        "quality_score = 0, cleaning_logs = :reason, updated_at = now() WHERE id = :id"
                    ),
                    {"lt": lt, "reason": reason, "id": r["id"]},
                )

    if apply:
        run_cleaner(engine)  # làm nốt các tin rejected vừa đưa về 'raw'
    return changes

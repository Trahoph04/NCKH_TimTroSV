"""Vector E5 (384 chiều) cho tin trọ để chatbot truy xuất ngữ nghĩa — chạy sau mỗi lần crawl/import.

    docker compose exec api python -m app.room_service.chatbot.index_listings          # chỉ tin mới/đổi nội dung
    docker compose exec api python -m app.room_service.chatbot.index_listings --all    # nhúng lại toàn bộ

Chỉ nhúng tin UI đang hiện (visible_clause) — tin ẩn chatbot cũng không trả. Tin chưa có vector vẫn được
chatbot tìm qua BM25 + bộ lọc (vector_score = 0), nên bỏ qua bước này chỉ làm giảm chất lượng, không hỏng.
Văn bản nhúng giữ đúng scripts/index_listing_embeddings.py của branch PHUC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging

from sqlalchemy import create_engine, text

from ...config import settings
from ...listings.repo import visible_clause
from .providers import E5EmbeddingProvider

log = logging.getLogger("chatbot.index_listings")
BATCH = 32


def canonical_text(row: dict) -> str:
    amenities = row.get("parsed_amenities") or {}
    return " | ".join(str(value or "") for value in (
        row.get("title"), row.get("description"), row.get("address"), row.get("district"),
        row.get("price"), row.get("area"), json.dumps(amenities, sort_keys=True, ensure_ascii=False),
    ))


def index_listings(engine, embedder, model_name: str, reembed_all: bool = False) -> dict:
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(
            "SELECT id, title, description, address, district, price, area, parsed_amenities, "
            "embedded_content_hash, embedding_model FROM aggregated_listings "
            f"WHERE status = 'active' AND {visible_clause(None)} ORDER BY id")).mappings()]
    pending = []
    for row in rows:
        content = canonical_text(row)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if reembed_all or row["embedded_content_hash"] != digest or row["embedding_model"] != model_name:
            pending.append((row["id"], content, digest))
    for start in range(0, len(pending), BATCH):
        batch = pending[start:start + BATCH]
        vectors = embedder.embed_passages([content for _, content, _ in batch])
        with engine.begin() as conn:
            for (listing_id, _, digest), vector in zip(batch, vectors):
                conn.execute(text(
                    "UPDATE aggregated_listings SET embedding_vector = CAST(:v AS vector), embedding_model = :m, "
                    "embedded_content_hash = :h, embedded_at = now() WHERE id = :id"),
                    {"v": "[" + ",".join(f"{x:.9g}" for x in vector) + "]", "m": model_name,
                     "h": digest, "id": listing_id})
        log.info("đã nhúng %d/%d", min(start + BATCH, len(pending)), len(pending))
    return {"visible": len(rows), "embedded": len(pending), "unchanged": len(rows) - len(pending)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="nhúng lại cả tin không đổi nội dung")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    model = settings.chatbot_embedding_model
    embedder = E5EmbeddingProvider(model, allow_download=True)
    try:
        embedder.embed_passages(["kiểm tra model"])
    except RuntimeError as exc:
        raise SystemExit(f"{exc} — build api với INSTALL_ML=true rồi chạy lại") from exc
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        print(json.dumps(index_listings(engine, embedder, model, args.all), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

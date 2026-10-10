"""Nạp corpus pháp lý + KTX của chatbot (apps/api/chatbot_corpus) vào schema riêng, vector E5 thật.

    docker compose exec api python -m app.room_service.legal_knowledge.index_corpus            # nạp/cập nhật
    docker compose exec api python -m app.room_service.legal_knowledge.index_corpus --prune    # + tắt nguồn đã rời manifest

Chạy lại an toàn: tài liệu cùng sha256 + cùng EXTRACTION_VERSION thì bỏ qua. Logic chia đoạn/nhúng giữ đúng
scripts/index_legal_agent_corpus.py + index_ctu_ktx.py của branch PHUC (đoạn ≤ 1.200 ký tự, nhúng
"tiêu đề\\nđiều khoản\\nnội dung", giữ nguyên văn điều khoản làm parent_content để trích dẫn đủ ngoại lệ),
gộp thành 1 bước vì repo này không có chuỗi schema v7→v16→KTX của branch đó (ADR-023).

Cần image build với INSTALL_ML=true (sentence-transformers). Lần đầu tải model ~470 MB vào volume /models.
Không bao giờ ghi vector giả: thiếu model ⇒ dừng, corpus giữ nguyên.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path

from sqlalchemy import create_engine, text

from ...config import settings
from ..chatbot.providers import E5EmbeddingProvider
from .chunker import LegalChunk
from .extractor import ExtractedDocument, ExtractedPage
from .repo import LegalKnowledgeRepository
from .storage import legal_schema

log = logging.getLogger("legal_knowledge.index_corpus")

# apps/api/chatbot_corpus — trong image là /app/chatbot_corpus (Dockerfile COPY)
DEFAULT_CORPUS = Path(__file__).resolve().parents[3] / "chatbot_corpus"
BATCH = 24


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_ddl(schema: str) -> str:
    """Bảng corpus riêng: cùng cột public.legal_* (mig 100) + cột điều khoản mà repo đọc khi schema != public.

    Sequence riêng để id không đụng corpus khác (giống migration 101 của branch PHUC).
    """
    return f"""
    CREATE SCHEMA IF NOT EXISTS {schema};
    CREATE SEQUENCE IF NOT EXISTS {schema}.document_id;
    CREATE SEQUENCE IF NOT EXISTS {schema}.chunk_id;
    CREATE TABLE IF NOT EXISTS {schema}.legal_documents (LIKE public.legal_documents INCLUDING ALL);
    ALTER TABLE {schema}.legal_documents ALTER COLUMN id SET DEFAULT nextval('{schema}.document_id');
    ALTER TABLE {schema}.legal_documents ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{{}}';
    CREATE TABLE IF NOT EXISTS {schema}.legal_chunks (LIKE public.legal_chunks INCLUDING ALL);
    ALTER TABLE {schema}.legal_chunks ALTER COLUMN id SET DEFAULT nextval('{schema}.chunk_id');
    ALTER TABLE {schema}.legal_chunks ADD COLUMN IF NOT EXISTS provision_id TEXT;
    ALTER TABLE {schema}.legal_chunks ADD COLUMN IF NOT EXISTS parent_content TEXT;
    ALTER TABLE {schema}.legal_chunks ADD COLUMN IF NOT EXISTS source_metadata JSONB NOT NULL DEFAULT '{{}}';
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{schema}_document_fk') THEN
            ALTER TABLE {schema}.legal_chunks ADD CONSTRAINT {schema}_document_fk
            FOREIGN KEY (document_id) REFERENCES {schema}.legal_documents(id) ON DELETE CASCADE;
        END IF;
    END $$;
    INSERT INTO public.legal_corpus_releases (schema_name, status) VALUES ('{schema}', 'staging')
    ON CONFLICT (schema_name) DO NOTHING;
    """


def pieces(provision: dict, maximum: int = 1200) -> list[str]:
    """Giới hạn đầu vào E5 (512 token); điều khoản trọn vẹn vẫn giữ ở parent_content."""
    content = provision["content"]
    if len(content) <= maximum:
        return [content]
    result, current = [], ""
    for line in content.splitlines(keepends=True):
        if len(current) + len(line) > maximum and current:
            result.append(current.strip())
            current = ""
        if len(line) > maximum:
            # đoạn DOCX không xuống dòng có thể dài hơn cả ngưỡng
            for offset in range(0, len(line), maximum):
                if current:
                    result.append(current.strip())
                    current = ""
                result.append(line[offset:offset + maximum].strip())
        else:
            current += line
    if current.strip():
        result.append(current.strip())
    return [piece for piece in result if piece]


def index_corpus(engine, corpus: Path, schema: str, embedder, prune: bool = False) -> dict:
    schema = legal_schema(schema)
    if schema == "public":
        raise SystemExit("Corpus phục vụ phải ở schema legal_* riêng — public chỉ là khung")
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with engine.begin() as conn:
        conn.exec_driver_sql(_schema_ddl(schema))
    repo = LegalKnowledgeRepository(engine, schema)

    indexed, skipped = [], []
    for entry in manifest["documents"]:
        path = corpus / entry["file"]
        if _sha(path) != entry["sha256"]:
            raise SystemExit(f"sai checksum: {entry['file']} — file corpus bị sửa tay?")
        source_path = f"chatbot_corpus/{entry['file']}"
        if repo.current_hash(source_path) == entry["sha256"]:
            skipped.append(entry["id"])
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        source = data["source"]
        chunks, parents = [], []
        for provision in data["provisions"]:
            for content in pieces(provision):
                chunks.append(LegalChunk(len(chunks), provision["page_from"], provision["page_to"],
                                         provision["heading"], content,
                                         hashlib.sha256(content.encode()).hexdigest()))
                parents.append(provision)
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), BATCH):
            # tiêu đề văn bản + nhãn điều khoản quyết định truy xuất theo số điều; thân giữ nguyên văn
            vectors.extend(embedder.embed_passages(
                [f"{source['title']}\n{c.heading or ''}\n{c.content}" for c in chunks[start:start + BATCH]]))
        if len(vectors) != len(chunks) or any(len(v) != 384 for v in vectors):
            raise SystemExit(f"thiếu vector E5 cho {entry['id']}")
        pages = tuple(ExtractedPage(n, "", source.get("page_kind") == "physical_pdf")
                      for n in range(1, int(source.get("pages") or 1) + 1))
        ocr = "tesseract" if source.get("ocr_used", "OCR" in str(source.get("extraction", ""))) else None
        doc = ExtractedDocument(path, source_path, source["title"], entry["category"], "structured_json",
                                "application/json", entry["sha256"], pages, ocr)
        doc_id = repo.replace_document(doc, chunks, vectors, settings.chatbot_embedding_model)
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE {schema}.legal_documents SET source_metadata = CAST(:m AS jsonb) WHERE id = :id"),
                         {"id": doc_id, "m": json.dumps(source, ensure_ascii=False)})
            for index, parent in enumerate(parents):
                meta = {k: v for k, v in parent.items() if k != "content"}
                meta["selected_points_only"] = bool(source.get("contains_selected_points"))
                context = parent.get("article_context")
                conn.execute(text(
                    f"UPDATE {schema}.legal_chunks SET provision_id = :pid, parent_content = :parent, "
                    "source_metadata = CAST(:m AS jsonb) WHERE document_id = :id AND chunk_index = :i"),
                    {"id": doc_id, "i": index, "pid": parent["provision_id"],
                     "parent": (context + "\n\n" if context else "") + parent["content"],
                     "m": json.dumps(meta, ensure_ascii=False)})
        indexed.append({"id": entry["id"], "chunks": len(chunks)})
        log.info("indexed %s (%d đoạn)", entry["id"], len(chunks))

    active = [f"chatbot_corpus/{e['file']}" for e in manifest["documents"]]
    with engine.begin() as conn:
        stale = conn.execute(text(
            f"SELECT source_path FROM {schema}.legal_documents WHERE status = 'ready' AND NOT (source_path = ANY(:p))"),
            {"p": active}).scalars().all()
        if prune and stale:
            # giữ đoạn + vector để khôi phục được; chỉ rút khỏi truy xuất
            conn.execute(text(
                f"UPDATE {schema}.legal_documents SET status = 'failed', updated_at = now(), "
                "error_message = 'inactive: không còn trong chatbot_corpus/manifest.json' "
                "WHERE status = 'ready' AND NOT (source_path = ANY(:p))"), {"p": active})
        counts = dict(conn.execute(text(
            f"SELECT count(DISTINCT d.id) AS documents, count(c.id) AS chunks, count(c.embedding_vector) AS vectors "
            f"FROM {schema}.legal_documents d JOIN {schema}.legal_chunks c ON c.document_id = d.id "
            "WHERE d.status = 'ready'")).mappings().one())
        if counts["chunks"] != counts["vectors"]:
            raise SystemExit("có đoạn đang phục vụ mà chưa có vector — kiểm tra lại model E5")
        categories = {r["category"]: r["n"] for r in conn.execute(text(
            f"SELECT category, count(*) AS n FROM {schema}.legal_documents WHERE status = 'ready' "
            "GROUP BY category ORDER BY category")).mappings()}
        conn.execute(text(
            "UPDATE public.legal_corpus_releases SET status = 'active', manifest_sha256 = :h, "
            "activated_at = COALESCE(activated_at, now()), validation = CAST(:v AS jsonb) WHERE schema_name = :s"),
            {"s": schema, "h": _sha(manifest_path), "v": json.dumps({**counts, "categories": categories})})
    return {"schema": schema, "indexed": indexed, "skipped": len(skipped), **counts, "categories": categories,
            "stale_sources": list(stale), "pruned": bool(prune and stale)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--schema", default=settings.chatbot_legal_schema)
    ap.add_argument("--prune", action="store_true", help="tắt (không xoá) tài liệu không còn trong manifest")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # allow_download: lần đầu tải model vào HF_HOME (/models); API lúc chạy chỉ đọc cache local
    embedder = E5EmbeddingProvider(settings.chatbot_embedding_model, allow_download=True)
    try:
        embedder.embed_passages(["kiểm tra model"])
    except RuntimeError as exc:
        raise SystemExit(f"{exc} — build api với INSTALL_ML=true rồi chạy lại") from exc
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        print(json.dumps(index_corpus(engine, args.corpus, args.schema, embedder, args.prune), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

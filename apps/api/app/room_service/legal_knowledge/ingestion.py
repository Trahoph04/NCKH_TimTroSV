from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import logging

from ..chatbot.providers import EmbeddingProvider
from .chunker import chunk_pages
from .extractor import extract_document, file_sha256, scan_documents
from .repo import LegalKnowledgeRepository


@dataclass
class IndexingReport:
    discovered: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    chunks: int = 0
    ocr_pages: int = 0
    errors: list[str] = field(default_factory=list)


class LegalDocumentIndexer:
    def __init__(
        self,
        repository: LegalKnowledgeRepository,
        embedder: EmbeddingProvider | None,
        *,
        batch_size: int = 24,
        ocr_language: str = "vie+eng",
        force_ocr: bool = False,
    ):
        self.repository = repository
        self.embedder = embedder
        self.batch_size = max(1, batch_size)
        self.ocr_language = ocr_language
        self.force_ocr = force_ocr

    def index_folder(self, root: Path, *, force: bool = False, category: str | None = None,
                     sources: list[str] | None = None) -> IndexingReport:
        root = root.resolve()
        paths = scan_documents(root)
        if category:
            paths = [path for path in paths if path.relative_to(root).parts[0] == category]
        if sources:
            paths = [path for path in paths if path.relative_to(root).as_posix() in sources]
            if len(paths) != len(set(sources)):
                raise ValueError("Không tìm thấy đầy đủ đường dẫn --source trong thư mục dữ liệu/nhóm đã chọn")
        report = IndexingReport(discovered=len(paths))
        for path in paths:
            relative = path.relative_to(root).as_posix()
            digest = file_sha256(path)
            if not (force or self.force_ocr) and self.repository.current_hash(relative) == digest:
                report.skipped += 1
                continue
            try:
                document = extract_document(
                    path,
                    root,
                    ocr_language=self.ocr_language,
                    force_ocr=self.force_ocr,
                )
                chunks = chunk_pages(document.pages)
                if not chunks:
                    raise RuntimeError("Không tạo được chunk nội dung")
                vectors: list[list[float] | None] = []
                if self.embedder is None:
                    vectors = [None] * len(chunks)
                    model_name = None
                else:
                    for start in range(0, len(chunks), self.batch_size):
                        batch = chunks[start : start + self.batch_size]
                        vectors.extend(self.embedder.embed_passages([chunk.content for chunk in batch]))
                    model_name = getattr(self.embedder, "model_name", None)
                self.repository.replace_document(document, chunks, vectors, model_name)
                report.indexed += 1
                report.chunks += len(chunks)
                report.ocr_pages += document.ocr_page_count
                logging.getLogger(__name__).info("Indexed %s: %s chunks, %s OCR pages", relative, len(chunks), document.ocr_page_count)
            except Exception as exc:
                report.failed += 1
                message = f"{relative}: {type(exc).__name__}: {exc}"
                report.errors.append(message)
                category = path.relative_to(root).parts[0] if len(path.relative_to(root).parts) > 1 else "uncategorized"
                try:
                    self.repository.mark_failed(relative, path.stem, category, digest, message)
                except Exception:
                    pass
        return report

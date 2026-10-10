import zipfile
from pathlib import Path

import pytest

from app.room_service.chatbot.parser import parse_query
from app.room_service.chatbot.providers import DeterministicFakeEmbedder, GroundedTemplateGenerator
from app.room_service.chatbot.schemas import ChatAskRequest
from app.room_service.chatbot.service import ChatService
from app.room_service.legal_knowledge.chunker import chunk_pages
from app.room_service.legal_knowledge.extractor import ExtractedPage, extract_document, scan_documents
from app.room_service.legal_knowledge.ingestion import LegalDocumentIndexer


def test_legal_intent_is_detected_before_housing_search():
    parsed = parse_query("Theo luật thì hợp đồng thuê trọ có cần đặt cọc không?")
    assert parsed.intent == "legal_question"
    assert parsed.filters.listing_type is None


def test_scan_extract_text_and_law_aware_chunking(tmp_path: Path):
    category = tmp_path / "electricity"
    category.mkdir()
    source = category / "thong-tu.txt"
    source.write_text(
        "CHƯƠNG I QUY ĐỊNH CHUNG\n\nĐiều 1. Phạm vi điều chỉnh\n\n"
        + "Quy định về giá điện cho người thuê nhà. " * 80,
        encoding="utf-8",
    )
    assert scan_documents(tmp_path) == [source]
    document = extract_document(source, tmp_path)
    chunks = chunk_pages(document.pages, target_chars=600, overlap_chars=80)
    assert document.category == "electricity"
    assert chunks
    assert chunks[0].page_from == 1
    assert any(chunk.heading and "Điều 1" in chunk.heading for chunk in chunks)
    assert all(chunk.content_sha256 for chunk in chunks)


@pytest.mark.parametrize("part_name", ["word/document.xml", "word\\document.xml"])
def test_docx_extraction_uses_paragraph_boundaries_without_extra_dependency(tmp_path: Path, part_name: str):
    path = tmp_path / "law.docx"
    xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Điều 1. Hợp đồng thuê nhà</w:t></w:r></w:p>
      <w:p><w:r><w:t>Người thuê có quyền theo thỏa thuận.</w:t></w:r></w:p></w:body>
    </w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(part_name, xml)
    original_bytes = path.read_bytes()
    document = extract_document(path, tmp_path)
    assert "Điều 1" in document.pages[0].text
    assert "Người thuê" in document.pages[0].text
    assert path.read_bytes() == original_bytes


@pytest.mark.parametrize("part_names", [
    ["word/document.xml", "word\\document.xml"],
    ["word/document.xml", "word/document.xml"],
    ["../word/document.xml"],
    ["other.xml"],
])
def test_docx_rejects_missing_or_ambiguous_document_parts(tmp_path: Path, part_names: list[str]):
    path = tmp_path / "invalid.docx"
    with zipfile.ZipFile(path, "w") as archive:
        for part_name in part_names:
            # Deliberate duplicate member tests a malformed archive.
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive.writestr(part_name, "<document/>")
    with pytest.raises(RuntimeError, match="DOCX không hợp lệ"):
        extract_document(path, tmp_path)


@pytest.mark.parametrize("content", [b"not a zip", b"<broken XML"])
def test_docx_rejects_corrupt_archive_or_xml(tmp_path: Path, content: bytes):
    path = tmp_path / "corrupt.docx"
    if content == b"not a zip":
        path.write_bytes(content)
    else:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("word/document.xml", content)
    with pytest.raises(RuntimeError, match="DOCX không hợp lệ"):
        extract_document(path, tmp_path)


class _LegalRepo:
    def retrieve_legal(self, query, vector, limit=5):
        return [
            {
                "chunk_id": 10,
                "document_id": 3,
                "title": "Thông tư giá điện",
                "category": "electricity",
                "source_path": "electricity/thong-tu.pdf",
                "page_from": 4,
                "page_to": 4,
                "heading": "Điều 3. Giá bán điện",
                "content": "Bên cho thuê thu tiền điện theo giá và định mức được quy định.",
                "similarity_score": 0.9,
                "rank": 1,
            }
        ][:limit]


def test_legal_chat_returns_page_level_source_without_listing():
    service = ChatService(
        _LegalRepo(), DeterministicFakeEmbedder(), GroundedTemplateGenerator()
    )
    result = service.ask(ChatAskRequest(message="Thông tư quy định giá điện phòng trọ thế nào?"))
    assert result.intent == "legal_question"
    assert result.listings == []
    assert result.sources[0].kind == "legal_document"
    assert result.sources[0].page_from == 4
    assert result.sources[0].excerpt == "Bên cho thuê thu tiền điện theo giá và định mức được quy định."
    assert result.evaluation_contexts == []
    assert "[1]" in result.answer


def test_legal_source_excerpt_is_bounded():
    class LongRepo(_LegalRepo):
        def retrieve_legal(self, query, vector, limit=5):
            rows = super().retrieve_legal(query, vector, limit)
            rows[0]["content"] = "Luật. " * 1000
            return rows
    result = ChatService(LongRepo(), DeterministicFakeEmbedder(), GroundedTemplateGenerator()).ask(
        ChatAskRequest(message="Thông tư quy định giá điện phòng trọ thế nào?"))
    assert len(result.sources[0].excerpt) == 1801
    assert result.sources[0].excerpt.endswith("…")


class _MemoryRepo:
    def __init__(self):
        self.hashes = {}
        self.saved = []

    def current_hash(self, source_path):
        return self.hashes.get(source_path)

    def replace_document(self, document, chunks, vectors, model):
        self.hashes[document.source_path] = document.content_sha256
        self.saved.append((document, chunks, vectors, model))
        return len(self.saved)

    def mark_failed(self, *args):
        raise AssertionError("indexing should not fail")


def test_indexer_is_idempotent_and_embeds_passages(tmp_path: Path):
    source = tmp_path / "residence" / "law.txt"
    source.parent.mkdir()
    source.write_text("Điều 1. Đăng ký tạm trú. " * 30, encoding="utf-8")
    repo = _MemoryRepo()
    indexer = LegalDocumentIndexer(repo, DeterministicFakeEmbedder())
    first = indexer.index_folder(tmp_path)
    second = indexer.index_folder(tmp_path)
    assert first.indexed == 1 and first.chunks >= 1
    assert second.skipped == 1 and second.indexed == 0
    assert len(repo.saved[0][2][0]) == 384

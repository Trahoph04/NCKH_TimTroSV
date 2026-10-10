"""Real PostgreSQL retrieval checks; isolated test database only."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="Requires isolated test database")


def test_old_electricity_clause_survives_large_newer_unrelated_corpus():
    from app.config import settings
    from app.room_service.chatbot.repo import ChatRepository
    engine = create_engine(settings.database_url)
    doc_ids = []
    try:
        with engine.begin() as conn:
            for category in ("electricity", "housing_contract"):
                doc_ids.append(conn.execute(text(
                    "INSERT INTO legal_documents(source_path,title,category,document_type,content_sha256,status) "
                    "VALUES(:path,:title,:category,'txt',:sha,'ready') RETURNING id"
                ), dict(path=f"test/{uuid4()}", title="Văn bản thử nghiệm", category=category, sha="a" * 64)).scalar_one())
            for idx, heading, content in (
                (0, "Điều 12. Giá điện | Khoản 5", "Chủ nhà cho thuê thu tiền điện của người thuê nhà không vượt quá hóa đơn tiền điện."),
                (1, "Điều 12. Giá điện | Khoản 5", "Bốn người sử dụng điện được tính một định mức; ba người bằng 3/4 định mức."),
                (2, "Điều 21. Hiệu lực | Khoản 1", "Quy định này có hiệu lực từ ngày điều chỉnh giá bán lẻ điện bình quân theo điều kiện chuyển tiếp nêu tại văn bản."),
            ):
                conn.execute(text("INSERT INTO legal_chunks(document_id,chunk_index,heading,content,content_sha256) "
                                  "VALUES(:doc,:idx,:heading,:content,:sha)"),
                             dict(doc=doc_ids[0], idx=idx, heading=heading, content=content, sha="b" * 64))
            conn.execute(text("INSERT INTO legal_chunks(document_id,chunk_index,heading,content,content_sha256) "
                              "SELECT :doc,n,'Giá thuê nhà','Giá thuê nhà của người thuê nhà theo diện tích sàn.',:sha "
                              "FROM generate_series(0,650) n"), dict(doc=doc_ids[1], sha="c" * 64))
        rows = ChatRepository(engine).retrieve_legal("Chủ trọ được thu tiền điện như thế nào?", None)
        assert rows and rows[0]["document_id"] == doc_ids[0]
        assert "hóa đơn" in rows[0]["content"] and "3/4" in rows[0]["content"]
        assert any("điều kiện chuyển tiếp" in row["content"] for row in rows)
        assert all(row["document_id"] == doc_ids[0] for row in rows)
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM legal_documents WHERE id=ANY(:ids)"), {"ids": doc_ids})
        engine.dispose()

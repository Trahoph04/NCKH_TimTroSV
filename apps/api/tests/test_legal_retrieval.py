"""Regression cases from the observed electricity answer; distractors are intentional."""
import pytest

from app.room_service.legal_knowledge.quality import text_quality, usable_legal_text
from app.room_service.legal_knowledge.chunker import chunk_pages
from app.room_service.legal_knowledge.extractor import ExtractedPage
from app.room_service.chatbot.legal_retrieval import (
    legal_tokens, expand_legal_query, rerank_legal, evidence_issues,
)
from app.room_service.chatbot.repo import bm25_scores
from app.room_service.chatbot.parser import parse_query
from app.room_service.chatbot.providers import GenerationResult, DeterministicFakeEmbedder
from app.room_service.chatbot.service import ChatService
from app.room_service.chatbot.schemas import ChatAskRequest


def test_ordinary_room_residence_does_not_use_collective_dormitory_rule():
    rows=[dict(chunk_id=1,category='residence',heading='Điều 12. Đăng ký tạm trú | Khoản 2',similarity_score=.95,
        content='Sinh viên ở ký túc xá được đơn vị quản lý lập danh sách đăng ký tạm trú.'),
        dict(chunk_id=2,category='residence',heading='Điều 27. Điều kiện đăng ký tạm trú | Khoản 1',similarity_score=.5,
        content='Công dân đến sinh sống tại chỗ ở hợp pháp ngoài nơi thường trú để học tập thì phải đăng ký tạm trú.')]
    result=rerank_legal('Sinh viên thuê trọ cần làm thủ tục cư trú nào?',[dict(r) for r in rows])
    assert [row['chunk_id'] for row in result]==[2]
    assert any(r['chunk_id']==1 for r in rerank_legal('Sinh viên ở ký túc xá đăng ký tạm trú thế nào?',[dict(r) for r in rows]))


def test_rental_electricity_excludes_dormitory_tariff_scope():
    rows=[dict(chunk_id=1,category='electricity',heading='Giá điện ký túc xá',similarity_score=.95,
        content='Ký túc xá sinh viên áp dụng giá bán lẻ điện sinh hoạt theo số người.'),
        dict(chunk_id=2,category='electricity',heading='Giá điện người thuê nhà',similarity_score=.5,
        content='Chủ nhà cho thuê thu tiền điện của người thuê nhà không vượt quá hóa đơn tiền điện.')]
    assert [r['chunk_id'] for r in rerank_legal('Chủ trọ thu tiền điện thế nào?',rows)]==[2]


def test_multiline_quoted_evidence_remains_a_partial_answer():
    from app.room_service.chatbot.legal_retrieval import legal_completion_status
    answer='Nguồn: “Điều kiện đầu tiên có nhiều thông tin hỗ trợ cho một phần yêu cầu.\n\nDòng cuối.” [1].\n\nChưa đủ căn cứ để kết luận toàn bộ yêu cầu.'
    assert legal_completion_status(answer)=='partial'


def test_damaged_font_and_reversed_fine_are_not_safe_evidence():
    damaged = "B6n mua diQn thuC nhd chri nhd gi6 b6n tliQn " * 20
    clean = "Bên mua điện sử dụng vào mục đích sinh hoạt của người thuê nhà. " * 10
    assert len(damaged) > 80
    assert text_quality(damaged) < 0.6
    assert text_quality(clean) > 0.9
    assert not usable_legal_text("Phạt tiền từ 40.000.000 đồng đến 20.000.000 đồng.")
    assert usable_legal_text("Phạt tiền từ 20.000.000 đồng đến 30.000.000 đồng.")


def test_article_and_short_final_clause_are_preserved_without_cross_article_overlap():
    pages = [ExtractedPage(10, "Điều 12. Giá bán lẻ điện sinh hoạt\n5. Người thuê nhà được cấp định mức.\n"
                          "c) Ba người được tính 3/4 định mức.\nĐiều 13. Quy định khác\n1. Quy định cuối."),
             ExtractedPage(11, "2. Điều kiện bổ sung.")]
    chunks = chunk_pages(pages)
    assert any("Khoản 5" in (chunk.heading or "") and "3/4" in chunk.content for chunk in chunks)
    assert any("Điều kiện bổ sung" in chunk.content for chunk in chunks)
    assert not any("Điều 13" in (chunk.heading or "") and "3/4" in chunk.content for chunk in chunks)


def test_points_inherit_fine_preamble_without_borrowing_other_remedies():
    chunks = chunk_pages([ExtractedPage(16, "Điều 13. Sử dụng điện\n11. Biện pháp khắc phục hậu quả:\n"
                                       "c) Người cho thuê nhà hoàn trả tiền thu thừa.\n"
                                       "d) Buộc dùng thiết bị đo đếm đúng quy chuẩn.")])
    refund = next(chunk for chunk in chunks if "Điểm c" in (chunk.heading or ""))
    assert "Biện pháp khắc phục" in refund.content
    assert "thiết bị" not in refund.content


def test_generation_guard_preserves_invoice_ceiling_and_delayed_commencement():
    chunks = [dict(rank=1, content="Tổng tiền điện chủ nhà thu của người thuê nhà không được vượt quá hóa đơn. "
                   "Ba người được tính 3/4 định mức. Quy định có hiệu lực kể từ ngày thực hiện điều chỉnh giá điện.")]
    question = "Chủ trọ được thu tiền điện như thế nào?"
    assert evidence_issues("Chủ trọ phải bằng số tiền hóa đơn [1].", chunks, question)
    assert evidence_issues("Ba người được tính 3/4 định mức [1].", chunks, question)
    assert not evidence_issues("Ba người được tính 3/4 định mức theo điều kiện hiệu lực gắn với điều chỉnh giá điện [1].", chunks, question)
    from app.room_service.chatbot.legal_retrieval import append_commencement_evidence
    supplemented = append_commencement_evidence("Ba người được tính 3/4 định mức [1].", chunks, question)
    assert "có hiệu lực kể từ ngày thực hiện điều chỉnh giá điện" in supplemented
    assert not evidence_issues(supplemented, chunks, question)


@pytest.mark.parametrize("question", [
    "Chủ trọ được thu tiền điện như thế nào theo quy định?",
    "Chủ trọ thu điện 4.000 đồng/kWh có đúng không?",
    "Ba sinh viên ở chung được tính định mức điện thế nào?",
])
def test_rental_electricity_beats_grid_and_theft_distractors(question):
    texts = [
        "Chủ sở hữu có trách nhiệm bảo vệ hành lang an toàn điện. Quy định về công trình điện.",
        "Số tiền trộm cắp điện được tính theo sản lượng điện và giá điện.",
        "Chủ nhà cho thuê thu tiền điện của người thuê nhà không vượt quá hóa đơn tiền điện hằng tháng. "
        "Sinh viên được cấp định mức theo số người sử dụng điện.",
    ]
    scores = bm25_scores(expand_legal_query(question), texts, tokenizer=legal_tokens)
    rows = [dict(chunk_id=i, content=content, similarity_score=score) for i, (content, score)
            in enumerate(zip(texts, scores))]
    ranked = rerank_legal(question, rows)
    assert ranked[0]["chunk_id"] == 2
    assert len(ranked) == 1
    assert parse_query(question).intent == "legal_question"


def test_legal_tokenizer_retains_rental_relationships():
    assert {"chu", "tro", "cho", "thue", "nha"} <= set(legal_tokens("chủ trọ cho thuê nhà"))


def test_floor_area_is_not_electricity_evidence():
    rows = [dict(chunk_id=1, similarity_score=1.0,
                 content="Giá thuê nhà tính theo diện tích sàn cho người thuê nhà.")]
    assert rerank_legal("Chủ trọ thu tiền điện thế nào?", rows) == []


def test_appendix_does_not_inherit_effectiveness_heading():
    chunks = chunk_pages([ExtractedPage(20, "Điều 21. Hiệu lực thi hành\n1. Có hiệu lực theo thời điểm quy định.\n\n"
                                       "Nơi nhận: Văn phòng Chính phủ\n\n22 Phụ lục\nBiểu mẫu giá bán điện.")])
    assert any(chunk.heading == "Phụ lục" for chunk in chunks)
    assert not any("Biểu mẫu" in chunk.content and "Điều 21" in (chunk.heading or "") for chunk in chunks)


@pytest.mark.parametrize("native", [
    "B6n mua diQn thuC nhd chri nhd gi6 b6n tliQn " * 50,
    "Người ký: CỔNG THÔNG TIN ĐIỆN TỬ CHÍNH PHỦ. Email: vanban@example.gov.vn. Thời gian ký 08/04/2026.",
])
def test_pdf_ocr_recovers_corrupt_font_and_signature_only_page(monkeypatch, tmp_path, native):
    import sys
    from types import SimpleNamespace
    from app.room_service.legal_knowledge import extractor
    clean = "Người cho thuê nhà thu tiền điện theo giá bán lẻ điện sinh hoạt. " * 12
    class Rect:
        def __init__(self, *args): pass
        def get_area(self): return 10000
    page = SimpleNamespace(get_text=lambda _: native, rect=Rect(),
                           get_image_info=lambda: [{"bbox": (0, 0, 100, 100)}],
                           get_pixmap=lambda **kwargs: SimpleNamespace(width=1, height=1, samples=b"rgb"))
    class Document:
        def __enter__(self): return [page]
        def __exit__(self, *args): pass
    monkeypatch.setitem(sys.modules, "fitz", SimpleNamespace(open=lambda _: Document(), Rect=Rect, Matrix=lambda *args: None))
    monkeypatch.setitem(sys.modules, "PIL", SimpleNamespace(Image=SimpleNamespace(frombytes=lambda *args: object())))
    monkeypatch.setattr(extractor, "_ocr_image", lambda *args: clean)
    pages, engine = extractor._extract_pdf(tmp_path / "test.pdf", language="vie+eng", force_ocr=False, min_text_chars=80)
    assert pages[0].text == clean and pages[0].ocr_used and engine == "tesseract"


def test_guards_reject_false_absence_and_unsupported_amount():
    chunks = [dict(rank=1, content="Người cho thuê nhà thu tiền điện cao hơn quy định bị phạt "
                   "từ 20.000.000 đồng đến 30.000.000 đồng.")]
    question = "Chủ trọ thu tiền điện cao hơn quy định bị phạt thế nào?"
    assert evidence_issues("Không có quy định cụ thể về cách thu tiền điện [1].", chunks, question)
    assert evidence_issues("Chủ nhà bị phạt 90.000.000 đồng [1].", chunks, question)
    assert evidence_issues("Chủ nhà bị phạt 80–90 triệu đồng [1].", chunks, question)
    assert not evidence_issues("Người cho thuê nhà thu tiền điện cao hơn quy định bị phạt 20–30 triệu đồng [1].", chunks, question)
    assert not evidence_issues("Người cho thuê nhà thu tiền điện cao hơn quy định bị phạt "
                               "từ 20.000.000 đồng đến 30.000.000 đồng [1].", chunks, question)


def test_service_rejects_valid_citation_number_with_invalid_conclusion():
    class Repo:
        def retrieve_legal(self, query, vector, limit=5):
            return [dict(rank=1, chunk_id=1, document_id=1, title="Thông tư giá điện", category="electricity",
                         content="Chủ nhà thu tiền điện của người thuê nhà theo hóa đơn và định mức.",
                         similarity_score=0.95)]

    class BadGenerator:
        calls = 0
        def generate(self, *args, **kwargs):
            self.calls += 1
            return GenerationResult("Không có quy định cụ thể về thu tiền điện [1].", "test")

    generator = BadGenerator()
    result = ChatService(Repo(), DeterministicFakeEmbedder(), generator).ask(
        ChatAskRequest(message="Chủ trọ thu tiền điện thế nào?"))
    assert generator.calls == 2
    assert result.no_answer and result.degraded
    assert "Không có quy định cụ thể" not in result.answer


def test_empty_semantic_retrieval_retries_lexical_search():
    class Repo:
        calls = []
        def retrieve_legal(self, query, vector, limit=5):
            self.calls.append((query, vector))
            return []

    from app.room_service.chatbot.providers import GroundedTemplateGenerator
    repo = Repo()
    result = ChatService(repo, DeterministicFakeEmbedder(), GroundedTemplateGenerator()).ask(
        ChatAskRequest(message="Chủ trọ thu tiền điện thế nào?"))
    assert len(repo.calls) == 2 and repo.calls[1][1] is None
    assert result.no_answer


def test_legal_effectiveness_followup_retains_previous_question():
    from app.room_service.chatbot.service import rewrite_query
    rewritten = rewrite_query("Quy định này áp dụng từ khi nào?", [
        {"role": "user", "content": "Chủ trọ thu tiền điện thế nào?"},
        {"role": "assistant", "content": "Theo Thông tư giá điện..."},
    ])
    assert "Chủ trọ thu tiền điện" in rewritten
    assert parse_query(rewritten).intent == "legal_question"


def test_cross_article_reference_is_not_a_new_heading():
    chunks = chunk_pages([ExtractedPage(4, "Điều 4. Mức phạt tiền\n1. Áp dụng đối với cá nhân, trừ các hành vi tại\n\n"
                                       "Điều 14 đến Điều 16 của Nghị định này áp dụng đối với tổ chức.")])
    assert all("Điều 4." in (chunk.heading or "") for chunk in chunks)
    assert any("Điều 14 đến Điều 16" in chunk.content for chunk in chunks)


def test_extractive_answer_copies_financial_terms_from_source():
    from app.room_service.chatbot.legal_answer import extract_legal_answer
    # Deliberately synthetic amounts: the implementation must copy, never supply a stored fine.
    clause = "Phạt tiền từ 11.000.000 đồng đến 17.000.000 đồng đối với người cho thuê nhà thu tiền điện vượt quy định."
    result = extract_legal_answer("Chủ trọ thu tiền điện cao bị phạt thế nào?", [
        dict(rank=2, title="Văn bản thử nghiệm", content=clause)])
    assert result.provider == "legal-extractive"
    assert clause in result.text and "[2]" in result.text
    assert "20.000.000" not in result.text


def test_extractive_short_lease_keeps_meter_continuation():
    from app.room_service.chatbot.legal_answer import extract_legal_answer
    result = extract_legal_answer("Thuê nhà dưới 12 tháng không kê khai số người thì tính điện thế nào?", [
        dict(rank=1, title="Văn bản thử nghiệm", content="Trường hợp thuê dưới 12 tháng và không kê khai đầy đủ số người "
             "thì áp dụng giá bán điện cho toàn bộ sản lượng tại\n\n: công tơ điện của bên mua điện.")])
    assert result is not None
    assert "tại công tơ điện của bên mua điện." in result.text


def test_missing_bank_evidence_is_explicit_abstention():
    from app.room_service.chatbot.legal_answer import extract_legal_answer
    result = extract_legal_answer("Chủ trọ thu tiền điện qua ngân hàng nào?", [
        dict(rank=1, title="Văn bản thử nghiệm", content="Chủ nhà thu tiền điện của người thuê nhà theo hóa đơn và định mức tại khoản 5.")])
    assert result.provider == "legal-insufficient"
    assert "Chưa tìm thấy căn cứ" in result.text
    assert "không đủ để kết luận" in result.text


def test_general_contract_price_clause_is_not_excluded_by_a_sales_subcondition():
    from app.room_service.chatbot.legal_retrieval import rerank_legal
    row=dict(document_id=1,chunk_id=1,category='housing_contract',title='Văn bản thử',
        heading='Điều 163. Hợp đồng về nhà ở | Khoản 3',similarity_score=.8,
        content='3. Giá trị góp vốn, giá giao dịch về nhà ở nếu hợp đồng có thỏa thuận về giá; '
                'trường hợp mua bán, cho thuê mua nhà ở do Nhà nước quy định về giá thì thực hiện theo quy định đó.')
    assert rerank_legal('Hợp đồng thuê phòng có cần ghi rõ tiền thuê không?',[row])


def test_cannot_turn_one_permitted_case_into_the_only_legal_basis():
    from app.room_service.chatbot.legal_retrieval import evidence_issues
    rows=[dict(rank=1,heading='Điều 170. Giá thuê',content='Bên cho thuê có quyền điều chỉnh giá thuê nhà sau khi thực hiện cải tạo nhà ở và được bên thuê đồng ý.')]
    issues=evidence_issues('Bên cho thuê chỉ có quyền điều chỉnh giá khi cải tạo nhà và được bên thuê đồng ý [1].',rows,'Chủ trọ tăng giá thế nào?')
    assert any('chưa loại trừ các căn cứ khác' in i for i in issues)

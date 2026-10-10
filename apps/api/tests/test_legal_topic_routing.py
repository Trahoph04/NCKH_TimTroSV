import pytest

from app.room_service.chatbot.parser import parse_query
from app.room_service.chatbot.topics import question_categories
from app.room_service.chatbot.legal_retrieval import rerank_legal, evidence_issues
from app.room_service.legal_knowledge.chunker import chunk_pages
from app.room_service.legal_knowledge.extractor import ExtractedPage


@pytest.mark.parametrize("question, category", [
    ("Dữ liệu cá nhân bị chia sẻ trái phép thì giải quyết thế nào?", "privacy_data"),
    ("Ảnh căn cước của tôi được lưu thế nào?", "privacy_data"),
    ("Lối thoát nạn nhà trọ bị chặn, tôi phải làm gì?", "fire_safety"),
    ("Tôi đã chuyển cọc, bên nhận cắt liên lạc, trình báo ở đâu?", "criminal_law"),
    ("Tiền nước dùng chung đồng hồ nên thỏa thuận thế nào?", "water_cantho"),
    ("Nền tảng trực tuyến xử lý người đăng tin giả thế nào?", "ecommerce_platform"),
    ("Người môi giới giấu thông tin phòng thì sao?", "real_estate_brokerage"),
    ("Đăng ký cư trú cần giấy tờ gì?", "residence"),
])
def test_route_knowledge_to_source_corpus(question, category):
    assert parse_query(question).intent == "legal_question"
    assert category in question_categories(question)


def test_word_boundaries_avoid_substring_and_condition_confusion():
    assert parse_query("Nếu không có phòng đúng tất cả điều kiện, cần nới gì?").intent == "find_listing"
    assert parse_query("Điều 27 Luật Cư trú quy định gì?").intent == "legal_question"


def test_category_gate_rejects_semantic_neighbour_not_answering_topic():
    rows = [dict(chunk_id=1, category="electricity", similarity_score=.95,
                 content="Người thuê nhà trả tiền điện theo hóa đơn."),
            dict(chunk_id=2, category="residence", similarity_score=.7,
                 heading="Điều 27. Đăng ký tạm trú", content="Sinh viên thuê nhà đăng ký tạm trú tại nơi cư trú theo quy định.")]
    assert [row["chunk_id"] for row in rerank_legal("Sinh viên thuê trọ cần thủ tục cư trú nào?", rows)] == [2]


def test_multi_topic_retains_direct_supporting_law():
    assert {"criminal_law", "housing_contract"} <= set(question_categories("Tranh chấp hợp đồng đặt cọc khi nào là lừa đảo?"))
    assert {"residence", "privacy_data"} <= set(question_categories("Thông tin cá nhân cho đăng ký cư trú?"))


def test_source_headings_preserve_short_extracts_and_markdown():
    chunks = chunk_pages([ExtractedPage(1, "Điều 27 — đăng ký tạm trú\nNgười đến cư trú cần đăng ký tạm trú.\n\nĐiều 30 — thông báo lưu trú\nNội dung thông báo lưu trú riêng.\n\n## Hồ sơ\nThông tin hồ sơ.")])
    assert len(chunks) == 3
    assert "Điều 27" in chunks[0].heading and "Điều 30" in chunks[1].heading
    assert chunks[2].heading == "## Hồ sơ"


def test_uncited_legal_obligation_is_not_accepted():
    assert evidence_issues("Người thuê phải trả thêm phí.", [dict(rank=1, content="Hợp đồng thuê nhà ghi thỏa thuận các bên.")], "Hợp đồng thuê nhà cần gì?")


def test_appendix_reference_does_not_erase_delayed_commencement_clause():
    text = "Điều 21. Hiệu lực thi hành\n\n1. Thông tư có hiệu lực từ ngày ký, trừ điểm c khoản 5 Điều 12 và Phụ lục có hiệu lực kể từ ngày thực hiện điều chỉnh giá."
    chunks = chunk_pages([ExtractedPage(1, text)])
    assert all("Điều 21" in (chunk.heading or "") for chunk in chunks)
    assert any("kể từ ngày thực hiện" in chunk.content for chunk in chunks)


def test_model_evidence_checker_rejects_cross_source_claim():
    import httpx
    from app.room_service.chatbot.providers import OllamaQwenGenerator
    def handler(request):
        import json
        payload = json.loads(request.content)
        assert payload["format"]["required"] == ["supported", "issues"]
        return httpx.Response(200, json={"message": {"content": '{"supported":false,"issues":["Nguồn [1] không nêu hoàn trả bằng hiện vật."]}'}})
    generator = OllamaQwenGenerator("http://example.test", "test", transport=httpx.MockTransport(handler))
    issues = generator.check_legal_evidence("Hoàn cọc thế nào?", "Trả bằng hiện vật [1].", [dict(rank=1, content="Tài sản đặt cọc được trả lại hoặc trừ nghĩa vụ trả tiền.")])
    assert issues and "hiện vật" in issues[0]
    generator.close()


def test_rejects_generalized_legal_absence_from_partial_water_source():
    assert evidence_issues("Văn bản pháp luật hiện hành không quy định công thức chia chi phí nước [1].", [dict(rank=1, content="Quyết định này không nêu cách chia chi phí nước.")], "Dùng chung đồng hồ nước?")


def test_partial_extraction_preserves_complete_condition_and_exception():
    from app.room_service.chatbot.legal_answer import extract_partial_provisions
    paragraph = "Khi hợp đồng được thực hiện, tài sản đặt cọc được trả lại hoặc trừ nghĩa vụ trả tiền; nếu bên đặt cọc từ chối giao kết thì tài sản thuộc bên nhận, trừ trường hợp có thỏa thuận khác."
    result = extract_partial_provisions("Hoàn tiền cọc theo hợp đồng được xác định thế nào?", [dict(rank=2, title="Văn bản thử", heading="Điều 328. Đặt cọc", content=paragraph)])
    assert paragraph in result.text and "[2]" in result.text
    assert "câu trả lời một phần" in result.text
    assert result.provider == "legal-partial-extractive"


def test_private_lease_does_not_cite_purchase_only_condominium_clause():
    rows = [dict(chunk_id=1, category="housing_contract", similarity_score=.99,
                 heading="Điều 163. Hợp đồng về nhà ở | Khoản 2",
                 content="Đối với hợp đồng mua bán, hợp đồng thuê mua căn hộ chung cư thì các bên ghi diện tích sở hữu chung."),
            dict(chunk_id=2, category="housing_contract", similarity_score=.7,
                 heading="Điều 163. Hợp đồng về nhà ở | Khoản 4",
                 content="Thời hạn và phương thức thanh toán tiền nếu là mua bán, cho thuê mua, cho thuê nhà ở.")]
    result = rerank_legal("Hợp đồng thuê trọ cần ghi rõ điều khoản gì?", rows)
    assert [row["chunk_id"] for row in result] == [2]


def test_copied_document_footnote_is_not_a_retrieval_source_number():
    from app.room_service.chatbot.service import _citation_accuracy
    assert _citation_accuracy('Trích: “Điều khoản trong nguồn[98].” [1].', [dict(rank=1)]) == 1
    assert _citation_accuracy('Kết luận bên ngoài trích đoạn [98].', [dict(rank=1)]) == 0

import json

import httpx
import pytest

from app.room_service.chatbot.parser import merge_filters, parse_query
from app.room_service.chatbot.providers import (
    DeterministicFakeEmbedder,
    FallbackResponseGenerator,
    GeminiGenerator,
    GroundedTemplateGenerator,
    OllamaQwenGenerator,
    content_hash,
)
from app.room_service.chatbot.repo import bm25_scores
from app.room_service.chatbot.schemas import ChatAskRequest, ChatFilters
from app.room_service.chatbot.service import ChatService, rewrite_query


def test_parse_price_district_and_amenities():
    parsed = parse_query(
        "Tìm phòng trọ từ 1,5 triệu đến 2 triệu ở Ninh Kiều, có máy lạnh và gác"
    )
    assert parsed.intent == "find_listing"
    assert parsed.filters.min_price == 1_500_000
    assert parsed.filters.max_price == 2_000_000
    assert parsed.filters.district == "Ninh Kiều"
    # "gác" không còn là bộ lọc cứng: crawler repo này không có key mezzanine (BM25 vẫn bắt chữ "gác")
    assert set(parsed.filters.amenities) == {"air_conditioner"}


def test_parse_distance_area_gender_and_type():
    parsed = parse_query(
        "Nhà nguyên căn chỉ nữ, ít nhất 30m2, cách trường không quá 2km"
    )
    assert parsed.filters.listing_type == "nha_nguyen_can"
    assert parsed.filters.gender == "female"
    assert parsed.filters.min_area == 30
    assert parsed.filters.max_distance_ctu == 2000
    assert parsed.filters.max_price is None


def test_distance_unit_is_never_parsed_as_thousand_dong():
    parsed = parse_query("Phòng có gác cách trường dưới 2 km")
    assert parsed.filters.max_distance_ctu == 2000
    assert parsed.filters.max_price is None


def test_out_of_scope_detection():
    parsed = parse_query("Cho mình dự báo thời tiết ngày mai")
    assert parsed.intent == "out_of_scope"


def test_explicit_filters_override_parser_and_union_amenities():
    parsed = parse_query("Phòng trọ dưới 2 triệu có wifi").filters
    merged = merge_filters(
        parsed,
        ChatFilters(max_price=1_800_000, amenities=["air_conditioner"]),
    )
    assert merged.max_price == 1_800_000
    assert set(merged.amenities) == {"wifi", "air_conditioner"}


def test_bm25_ranks_keyword_listing_first():
    scores = bm25_scores(
        "wifi máy lạnh Ninh Kiều",
        [
            "Phòng Ninh Kiều có wifi máy lạnh gần trường",
            "Nhà nguyên căn Cái Răng rộng rãi",
        ],
    )
    assert scores[0] == 1.0
    assert scores[0] > scores[1]


def test_content_hash_normalizes_accents_and_spacing():
    assert content_hash(" Phòng   trọ ") == content_hash("phong tro")
    assert content_hash("phòng mới") != content_hash("phòng cũ")


def test_fake_embedding_is_deterministic_384_dimensions():
    embedder = DeterministicFakeEmbedder()
    first = embedder.embed_query("phòng trọ gần CTU").vector
    second = embedder.embed_query("phòng trọ gần CTU").vector
    assert first == second
    assert first is not None and len(first) == 384


class FakeRepo:
    def __init__(self, listings):
        self.listings = listings
        self.retrieve_calls = 0

    def retrieve(self, query, filters, vector, limit=5):
        self.retrieve_calls += 1
        return self.listings[:limit]


def _listing():
    return {
        "id": 1,
        "title": "Phòng trọ gần CTU",
        "price": 1_800_000,
        "area": 20.0,
        "address": "Xuân Khánh, Ninh Kiều",
        "district": "Ninh Kiều",
        "description": "Có máy lạnh",
        "parsed_amenities": {"air_conditioner": True},
        "distance_to_ctu": 500.0,
        "route_time_campus": [8.0, 4.0, 12.0],
        "source": "dev_seed",
        "source_url": "https://example.test/1",
        "similarity_score": 0.88,
        "vector_score": 0.8,
        "bm25_score": 0.9,
        "match_reasons": ["Khớp từ khóa", "Gần CTU"],
        "rank": 1,
    }


def test_service_is_stateless_caps_sources_and_returns_grounded_answer():
    repo = FakeRepo([dict(_listing(), id=i, rank=i) for i in range(1, 8)])
    service = ChatService(
        repo, DeterministicFakeEmbedder(), GroundedTemplateGenerator(), max_results=5
    )
    result = service.ask(ChatAskRequest(message="Tìm phòng trọ gần CTU"))
    assert len(result.listings) == 5
    assert len(result.sources) == 5
    assert "[1]" in result.answer
    assert result.no_answer is False
    assert result.retrieval_mode == "hybrid"
    assert result.generation_provider == "template"
    assert repo.retrieve_calls == 1
    assert "session_id" not in result.model_dump()
    assert "message_id" not in result.model_dump()


def test_short_follow_up_uses_only_latest_client_side_user_context():
    rewritten = rewrite_query(
        "Còn phòng nào rẻ hơn?",
        [
            {"role": "user", "content": "Tìm phòng ở Ninh Kiều"},
            {"role": "assistant", "content": "Có ba phòng."},
        ],
    )
    assert rewritten == "Tìm phòng ở Ninh Kiều. Yêu cầu tiếp theo: Còn phòng nào rẻ hơn?"


def test_evaluation_context_is_opt_in_and_unevaluated_risk_is_unknown():
    service = ChatService(
        FakeRepo([_listing()]), DeterministicFakeEmbedder(), GroundedTemplateGenerator()
    )
    result = service.ask(
        ChatAskRequest(message="Tìm phòng trọ gần CTU", include_evaluation_contexts=True)
    )
    assert result.listings[0].risk_level == "unknown"
    assert result.listings[0].risk_score is None
    assert result.citation_accuracy == 1.0
    assert result.evaluation_contexts[0].listing_id == 1


def test_service_never_invents_result_when_retrieval_empty():
    repo = FakeRepo([])
    service = ChatService(repo, DeterministicFakeEmbedder(), GroundedTemplateGenerator())
    result = service.ask(ChatAskRequest(message="Tìm phòng trọ trên sao Hỏa"))
    assert result.no_answer is True
    assert result.listings == []


def test_template_generator_uses_only_listing_values():
    answer = GroundedTemplateGenerator().generate("x", [_listing()]).text
    assert "Phòng trọ gần CTU" in answer
    assert "1.8 triệu" in answer


def test_ollama_qwen_generator_uses_local_chat_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen2.5:7b"
        assert payload["think"] is False
        assert payload["options"]["num_ctx"] == 8192
        assert "CONTEXT LISTING" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Chọn phòng [1]."}},
        )

    generator = OllamaQwenGenerator(
        "http://ollama.test",
        "qwen2.5:7b",
        transport=httpx.MockTransport(handler),
    )
    result = generator.generate("Phòng nào phù hợp?", [_listing()])
    assert result.text == "Chọn phòng [1]."
    assert result.provider == "qwen-local"
    assert result.model == "qwen2.5:7b"


def test_gemini_generator_sends_key_in_header_not_url():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "secret-test-key"
        assert "secret-test-key" not in str(request.url)
        assert request.url.path.endswith("/models/gemini-test:generateContent")
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Gemini đề xuất phòng [1]."}]}}
                ]
            },
        )

    generator = GeminiGenerator(
        "secret-test-key",
        "gemini-test",
        base_url="https://gemini.test/v1beta",
        transport=httpx.MockTransport(handler),
    )
    result = generator.generate("Phòng nào phù hợp?", [_listing()])
    assert result.text == "Gemini đề xuất phòng [1]."
    assert result.provider == "gemini"


def test_provider_chain_falls_back_to_grounded_template():
    def unavailable(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "offline"})

    generator = FallbackResponseGenerator(
        [
            OllamaQwenGenerator(
                "http://ollama.test",
                "qwen2.5:7b",
                transport=httpx.MockTransport(unavailable),
            )
        ]
    )
    result = generator.generate("Phòng nào phù hợp?", [_listing()])
    assert result.provider == "template"
    assert "Phòng trọ gần CTU" in result.text
    assert result.degraded_reasons


def test_legal_fallback_is_short_and_does_not_dump_or_interpret_law():
    contexts = [dict(rank=i, title="Văn bản", content="Nội dung luật dài. " * 500) for i in range(1, 6)]
    result = GroundedTemplateGenerator().generate("Tiền điện?", contexts, context_kind="legal")
    assert len(result.text) < 500
    assert "chưa tổng hợp được kết luận" in result.text
    assert "Nội dung luật dài" not in result.text
    assert all(f"[{i}]" in result.text for i in range(1, 6))


@pytest.mark.parametrize("message,reason", [({"content": "Kết luận bị cắt [1]"}, "length"), ({"thinking": "private reasoning", "content": ""}, "stop")])
def test_local_incomplete_or_thinking_only_output_uses_safe_fallback(message, reason):
    generator = FallbackResponseGenerator([OllamaQwenGenerator(
        "http://ollama.test", "qwen3.5:4b",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"message": message, "done_reason": reason})),
    )])
    result = generator.generate("Tìm trọ", [_listing()])
    assert result.provider == "template"
    assert result.degraded_reasons
    assert "private reasoning" not in result.text
    assert "Kết luận bị cắt" not in result.text


def test_qwen35_configurable_context_and_final_answer_only():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3.5:4b"
        assert payload["think"] is False
        assert payload["options"]["num_ctx"] == 4096
        assert payload["stream"] is False
        return httpx.Response(200, json={"done_reason": "stop", "message": {"thinking": "private reasoning", "content": "Phòng phù hợp [1]."}})
    result = OllamaQwenGenerator("http://ollama.test", "qwen3.5:4b", context_length=4096,
        transport=httpx.MockTransport(handler)).generate("Tìm trọ", [_listing()])
    assert result.text == "Phòng phù hợp [1]."
    assert result.model == "qwen3.5:4b"

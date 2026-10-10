import json

import httpx
import pytest

from app.config import Settings
from app.room_service.chatbot.providers import GeminiGenerator, FallbackResponseGenerator, GenerationResult, OllamaQwenGenerator
from app.room_service.chatbot.legal_retrieval import rerank_legal, evidence_issues


def test_numbered_credentials_are_read_without_exposing_secret_repr():
    # gemini_api_key="" cô lập khỏi khoá THẬT trong biến môi trường của container (08/10: có khoá nhóm ⇒ test này từng hỏng)
    settings = Settings(_env_file=None, gemini_api_key="", gemini_api_key_1="first", gemini_api_key_2="second", gemini_api_key_3="third")
    assert settings.configured_gemini_keys == ["third", "second", "first"]
    assert settings.gemini_api_key_3.__repr__() == "SecretStr('**********')"


def test_denied_key_is_cooled_down_and_successful_key_is_reused():
    calls = []
    def handler(request):
        key = request.headers["x-goog-api-key"]
        calls.append(key)
        assert key not in str(request.url)
        if key == "denied":
            return httpx.Response(403, json={"error": {"message": "denied"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Đối chiếu nguồn [1]."}]}, "finishReason": "STOP"}]})
    generator = GeminiGenerator("denied", "gemini-test", api_keys=["denied", "working"], transport=httpx.MockTransport(handler))
    for _ in range(2):
        assert generator.generate("Pháp lý?", [{"rank": 1, "title": "Luật", "content": "Nguồn luật"}], context_kind="legal").provider == "gemini"
    assert calls == ["denied", "working", "working"]


def test_quota_is_not_bypassed_by_rotating_keys():
    calls = []
    def handler(request):
        calls.append(request.headers["x-goog-api-key"])
        return httpx.Response(429, json={"error": {"message": "quota"}})
    generator = GeminiGenerator("first", "gemini-test", api_keys=["first", "second"], transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="429"):
        generator.request_json("prompt", {"type": "object"})
    assert calls == ["first"]


def test_model_overload_cools_down_all_credentials():
    calls = []
    def handler(request):
        calls.append(request.headers["x-goog-api-key"])
        return httpx.Response(503, json={"error": {"message": "overloaded"}})
    generator = GeminiGenerator("first", "gemini-test", api_keys=["first", "second"], transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="503"):
        generator.request_json("prompt", {"type": "object"})
    with pytest.raises(RuntimeError, match="tạm ngừng"):
        generator.request_json("prompt", {"type": "object"})
    assert calls == ["first"]


def test_daily_quota_uses_server_retry_delay_instead_of_retrying_every_minute():
    import time
    def handler(request):
        return httpx.Response(429, json={"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3600s"}]}})
    generator = GeminiGenerator("working", "gemini-test", transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="429"):
        generator.request_json("prompt", {"type": "object"})
    assert generator._model_blocked_until - time.monotonic() > 3500


def test_structured_response_excludes_thinking_and_rejects_token_truncation():
    truncated = False
    def handler(request):
        return httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS" if truncated else "STOP",
            "content": {"parts": [{"thought": True, "text": "hidden reasoning"}, {"text": '{"supported":true,"issues":[]}'}]}}]})
    generator = GeminiGenerator("working", "gemini-test", transport=httpx.MockTransport(handler))
    assert generator.request_json("prompt", {"type": "object"})[0] == '{"supported":true,"issues":[]}'
    truncated = True
    with pytest.raises(RuntimeError, match="giới hạn token"):
        generator.request_json("prompt", {"type": "object"})


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "```\n{}\n```"])
def test_proxy_structured_response_can_be_read_by_evidence_checker(wrapper):
    output = wrapper.format('{"supported":true,"issues":[]}')
    def handler(request):
        assert request.url.host == "proxy.local"
        prompt = json.loads(request.content)['contents'][0]['parts'][0]['text']
        assert 'OUTPUT_SCHEMA:' in prompt
        assert '"supported": boolean, "issues": [string]' in prompt
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": output}]}}]})
    generator = GeminiGenerator("working", "gemini-test", base_url="http://proxy.local/v1beta",
                                transport=httpx.MockTransport(handler))
    try:
        assert generator.check_legal_evidence("Question?", "Source statement [1].",
                                             [{"rank": 1, "content": "Source statement."}]) == []
    finally:
        generator.close()


@pytest.mark.parametrize('result', [
    {'supported': 'true', 'issues': []},
    {'supported': True, 'issues': None},
    {'supported': True, 'issues': [{'reason': 'unknown shape'}]},
    [],
])
def test_evidence_checker_cannot_accept_invalid_proxy_verdict(result):
    def handler(request):
        return httpx.Response(200, json={'candidates': [{'content': {'parts': [{'text': json.dumps(result)}]}}]})
    generator = GeminiGenerator('working', 'gemini-test', transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ValueError, match='Invalid source verification JSON shape'):
            generator.check_legal_evidence('Question?', 'Source statement [1].',
                                          [{'rank': 1, 'content': 'Source statement.'}])
    finally:
        generator.close()


def test_proxy_structured_response_does_not_hide_prose_outside_json_block():
    output = 'Result:\n```json\n{"supported":true,"issues":[]}\n```'
    def handler(request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": output}]}}]})
    generator = GeminiGenerator("working", "gemini-test", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(json.JSONDecodeError):
            generator.check_legal_evidence("Question?", "Source statement [1].",
                                          [{"rank": 1, "content": "Source statement."}])
    finally:
        generator.close()


def test_evidence_checker_preserves_semantic_rejection_and_falls_back_only_on_unavailability():
    class Checker:
        def __init__(self, unavailable=False, issues=()):
            self.unavailable, self.issues, self.calls = unavailable, list(issues), 0
        def check_legal_evidence(self, *args):
            self.calls += 1
            if self.unavailable:
                raise RuntimeError("offline")
            return self.issues
    primary, backup = Checker(issues=["Sai điều kiện"]), Checker()
    assert FallbackResponseGenerator([primary, backup]).check_legal_evidence("q", "a", []) == ["Sai điều kiện"]
    assert backup.calls == 0
    primary.unavailable = True
    assert FallbackResponseGenerator([primary, backup]).check_legal_evidence("q", "a", []) == []
    assert backup.calls == 1


def test_privacy_question_prioritizes_consent_over_identity_travel_and_breach_notice():
    rows = [dict(chunk_id=1, category="privacy_data", similarity_score=.9, heading="Thông báo vi phạm", content="Thông báo công khai vi phạm dữ liệu cá nhân."),
            dict(chunk_id=2, category="privacy_data", similarity_score=.7, heading="Sự đồng ý của chủ thể dữ liệu", content="Xử lý, cung cấp dữ liệu cá nhân cần sự đồng ý của chủ thể."),
            dict(chunk_id=3, category="privacy_data", similarity_score=.95, heading="Giá trị sử dụng thẻ căn cước", content="Thẻ căn cước thay giấy tờ xuất nhập cảnh.")]
    assert rerank_legal("Chủ trọ có được công khai ảnh giấy tờ và số điện thoại của tôi không?", rows)[0]["chunk_id"] == 2


def test_preventive_risk_prioritizes_fraud_over_prosecution_jurisdiction():
    rows = [dict(chunk_id=1, category="criminal_law", similarity_score=.95, heading="Thẩm quyền giải quyết", content="Tiếp nhận kiến nghị khởi tố của người nhận cọc."),
            dict(chunk_id=2, category="criminal_law", similarity_score=.7, heading="Tội lừa đảo chiếm đoạt tài sản", content="Dùng thủ đoạn gian dối chiếm đoạt tài sản.")]
    assert rerank_legal("Người nhận cọc không cho xem phòng, cần kiểm tra dấu hiệu rủi ro nào?", rows)[0]["chunk_id"] == 2


def test_specific_source_limitation_is_not_a_claim_that_all_law_has_no_rule():
    chunk = dict(rank=1, content="Văn bản này không nêu công thức chia chi phí nước.")
    assert not evidence_issues("Văn bản này không nêu công thức chia chi phí nước [1].", [chunk], "Tiền nước?")
    assert evidence_issues("Pháp luật không quy định công thức chia chi phí nước [1].", [chunk], "Tiền nước?")


def test_verification_sources_are_not_duplicated_for_repeated_citations():
    evidence = "Điều khoản đầy đủ gồm điều kiện và ngoại lệ. " * 100
    def handler(request):
        body = json.loads(request.content)
        data = json.loads(body["messages"][1]["content"])
        assert len(data["claims"]) == 2
        assert len(data["SOURCES"]) == 1
        assert data["SOURCES"][0]["text"] == evidence
        assert all(c["cited_ranks"] == [1] for c in data["claims"])
        return httpx.Response(200, json={"message": {"content": '{"supported":true,"issues":[]}'}})
    generator = OllamaQwenGenerator("http://test", "qwen-test", transport=httpx.MockTransport(handler))
    assert not generator.check_legal_evidence("q", "Kết luận A [1].\nKết luận B [1].", [{"rank": 1, "content": evidence}])
    generator.close()


def test_verifier_outage_does_not_regenerate_the_same_answer():
    from app.room_service.chatbot.service import ChatService
    from app.room_service.chatbot.schemas import ChatAskRequest
    from app.room_service.chatbot.providers import DeterministicFakeEmbedder
    class Repo:
        def retrieve_legal(self, *args, **kwargs):
            return [dict(document_id=1, chunk_id=1, rank=1, similarity_score=1, title="Luật thử", category="privacy_data",
                         content="Dữ liệu cá nhân được xử lý theo mục đích đã xác định.")]
    class Provider:
        calls = 0
        def generate(self, *args, **kwargs):
            self.calls += 1
            return GenerationResult("Dữ liệu cá nhân được xử lý theo mục đích đã xác định [1].", "test")
        def check_legal_evidence(self, *args):
            raise RuntimeError("offline")
    provider = Provider()
    service = ChatService(Repo(), DeterministicFakeEmbedder(), FallbackResponseGenerator([provider]))
    result = service.ask(ChatAskRequest(message="Dữ liệu cá nhân được xử lý thế nào?"))
    assert provider.calls == 1
    assert result.no_answer


@pytest.mark.parametrize("claim", [
    "Nếu thông tin sai lệch, người môi giới vi phạm nghĩa vụ và có thể bị xử lý hành chính hoặc dân sự.",
    "Người thuê nên kiểm tra hợp đồng và yêu cầu bồi thường nếu có thỏa thuận phạt.",
    "Người môi giới có nghĩa vụ hoàn trả phí.",
])
def test_uncited_legal_consequences_cannot_hide_behind_advice(claim):
    assert evidence_issues(claim, [dict(rank=1,content="Cung cấp đầy đủ, trung thực hồ sơ, thông tin bất động sản.")], "Môi giới cung cấp sai thông tin?")


def test_adding_a_citation_does_not_invent_a_remedy_absent_from_that_source():
    source = dict(rank=1,content="Cung cấp đầy đủ, trung thực hồ sơ, thông tin về bất động sản và chịu trách nhiệm về thông tin cung cấp.")
    assert evidence_issues("Người môi giới phải bồi thường do cung cấp sai thông tin [1].", [source], "Môi giới?")
    source["content"] += " Bên vi phạm phải bồi thường thiệt hại."
    assert not evidence_issues("Người môi giới phải bồi thường do cung cấp sai thông tin [1].", [source], "Môi giới?")


def test_general_checking_advice_does_not_require_a_legal_obligation_citation():
    assert not evidence_issues("Bạn nên kiểm tra thời hạn hợp đồng và đối chiếu thông tin phòng.", [dict(rank=1,content="Hồ sơ bất động sản.")], "Môi giới?")

import pytest
from app.room_service.chatbot.legal_retrieval import (
    evidence_issues, legal_completion_status, diversified_legal_rows, expand_legal_query, rerank_legal,
)
from app.room_service.chatbot.topics import question_categories, required_evidence_categories
from app.room_service.chatbot.providers import DeterministicFakeEmbedder, GenerationResult
from app.room_service.chatbot.schemas import ChatAskRequest
from app.room_service.chatbot.service import ChatService

def source(content, heading='Điều 62. Nội dung môi giới bất động sản | Khoản 3'):
    return dict(rank=1, content=content, heading=heading)

def test_work_description_does_not_create_a_legal_obligation():
    row = source('Thực hiện các công việc theo ủy quyền để hoàn thành giao dịch bất động sản.')
    assert evidence_issues('Nghĩa vụ của người môi giới là thực hiện công việc được quy định tại Điều 62, Khoản 3 [1].', [row], 'Môi giới?')
    assert not evidence_issues('Nội dung công việc môi giới bao gồm thực hiện công việc theo ủy quyền tại Điều 62, Khoản 3 [1].', [row], 'Môi giới?')

@pytest.mark.parametrize('answer', [
    'Người môi giới có nghĩa vụ cung cấp thông tin tại Điều 65 [1].',
    'Nội dung môi giới tại Điều 62, Khoản 2 là công việc theo ủy quyền [1].',
])
def test_article_and_clause_must_match_own_citation(answer):
    assert evidence_issues(answer, [source('Thực hiện công việc theo ủy quyền.')], 'Môi giới?')

def test_authority_inspection_is_not_a_tenant_obligation():
    row = source('Ủy ban nhân dân cấp xã có trách nhiệm tổ chức kiểm tra đột xuất đối với nhà ở.', 'Điều 13. Kiểm tra')
    assert evidence_issues('Người thuê phải tổ chức kiểm tra đột xuất đối với nhà ở theo Điều 13 [1].', [row], 'PCCC?')
    assert not evidence_issues('Ủy ban nhân dân cấp xã có trách nhiệm tổ chức kiểm tra đột xuất đối với nhà ở theo Điều 13 [1].', [row], 'PCCC?')

@pytest.mark.xfail(strict=True, reason='fail sẵn trên branch PHUC @445f89d (code chưa sửa) — chờ phía chatbot sửa evidence_issues')
def test_incomplete_exception_is_not_safe_evidence():
    row = source('Nếu bên nhận đặt cọc từ chối thực hiện hợp đồng thì phải trả lại tài sản đặt cọc, trừ trườ', 'Điều 328. Đặt cọc')
    assert evidence_issues('Bên nhận đặt cọc phải trả lại tài sản đặt cọc theo Điều 328 [1].', [row], 'Hoàn cọc?')

def test_missing_evidence_statement_cannot_hide_an_unsupported_duty():
    row = source('Thực hiện công việc theo ủy quyền.', 'Điều 62. Nội dung môi giới')
    assert evidence_issues('Chưa tìm thấy căn cứ, nhưng người môi giới phải hoàn trả tiền theo Điều 62 [1].', [row], 'Môi giới?')

def test_section_label_is_not_an_uncited_numeric_claim():
    row = source('Thời hạn và phương thức thanh toán do các bên thỏa thuận.', 'Điều 163. Hợp đồng về nhà ở | Khoản 4')
    assert not evidence_issues('**Thời hạn và phương thức thanh toán**\nKhuyến nghị: nên đối chiếu thời hạn và phương thức thanh toán trong hợp đồng [1].', [row], 'Hợp đồng?')
    assert evidence_issues('Thời hạn là 03 ngày.\nKhuyến nghị: đối chiếu nguồn [1].', [row], 'Hợp đồng?')

def test_cloud_pacing_is_shared_across_clients(monkeypatch):
    import time, threading
    from concurrent.futures import ThreadPoolExecutor
    import httpx
    from app.room_service.chatbot.providers import GeminiGenerator
    calls, lock = [], threading.Lock()
    def handler(request):
        with lock: calls.append(time.monotonic())
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{}'}]},'finishReason':'STOP'}]})
    clients = [GeminiGenerator('test','test-paced-model',transport=httpx.MockTransport(handler),min_request_interval_seconds=.04) for _ in range(3)]
    GeminiGenerator._next_request_at.pop('test-paced-model',None)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda c: c.request_json('test',{'type':'object'}),clients))
    assert len(calls)==3 and min(b-a for a,b in zip(sorted(calls),sorted(calls)[1:])) >= .025
    for client in clients: client.close()

def test_prepared_sources_retain_exception_and_current_residence_clauses():
    from pathlib import Path
    data = Path('/data')
    if not data.exists():
        pytest.skip('Requires the indexed corpus mount')
    civil = (data/'housing_contract/Bo-luat-91-2015-QH13-doi-chieu-20261003.md').read_text(encoding='utf-8')
    residence = (data/'residence/Luat-68-2020-QH14-doi-chieu-20261003.md').read_text(encoding='utf-8')
    fire = (data/'fire_safety/Luat-55-2024-QH15-dieu-8-20-21-23-24.md').read_text(encoding='utf-8')
    assert 'trừ trường hợp có thoả thuận khác.' in civil
    assert 'Cung cấp đầy đủ, chính xác, kịp thời thông tin, giấy tờ, tài liệu' in residence
    assert 'cấp phiếu tiếp nhận hồ sơ' in residence and '15 ngày trước ngày kết thúc' in residence
    assert 'Khi có người lưu trú qua đêm' in residence and 'ngày, tháng, năm sinh' in residence
    assert 'Người thuê, mượn, ở nhờ nhà ở có trách nhiệm' in fire
    assert 'trừ trường hợp có thỏa thuận khác với người cho thuê' in fire

@pytest.mark.parametrize('answer,expected', [
    ('Chưa tìm thấy căn cứ về danh mục thông tin cần cung cấp [1].', 'insufficient'),
    ('Chưa tìm thấy căn cứ cho danh mục bắt buộc [1].\nHợp đồng về nhà ở gồm họ và tên, địa chỉ của các bên [2].', 'partial'),
    ('Tài sản đặt cọc được trả lại hoặc trừ vào nghĩa vụ trả tiền, trừ trường hợp có thỏa thuận khác [1].', 'complete'),
    ('Nguồn nêu: “Nếu chưa đủ căn cứ thì không thể kết luận.” [1].', 'complete'),
])
def test_completion_follows_content_not_provider(answer, expected):
    assert legal_completion_status(answer) == expected

def test_mixed_identity_request_reserves_all_three_facets():
    query = 'Chủ trọ có thể yêu cầu thông tin cá nhân nào để làm hợp đồng và đăng ký cư trú?'
    assert set(required_evidence_categories(query)) == {'residence', 'housing_contract', 'privacy_data'}
    rows = [dict(chunk_id=i, document_id=i, category=cat, heading=f'Điều {i}') for i,cat in enumerate(
        ['privacy_data','privacy_data','privacy_data','residence','housing_contract'], 1)]
    selected = diversified_legal_rows(query, rows, 3)
    assert {row['category'] for row in selected} == {'residence','housing_contract','privacy_data'}
    assert 'họ tên' in expand_legal_query(query)

def test_generic_registration_papers_do_not_route_to_privacy():
    assert question_categories('Đăng ký tạm trú cần giấy tờ gì?') == ('residence',)

def test_cloud_fallback_precedes_local_without_duplicating_primary(monkeypatch):
    from app.config import Settings
    from app.room_service.chatbot import router
    settings = Settings(_env_file=None,chatbot_llm_provider='auto',gemini_api_key_3='test-only')
    monkeypatch.setattr(router,'settings',settings)
    monkeypatch.setattr(router,'_service',None)
    monkeypatch.setattr(router,'E5EmbeddingProvider',lambda *a: DeterministicFakeEmbedder())
    router.init_chatbot(object())
    assert [p.model for p in router.get_service().generator.providers] == [
        'gemini-3.5-flash-lite','gemini-3.1-flash-lite',settings.ollama_model]
    router.close_chatbot()
    settings.gemini_fallback_model = settings.gemini_model
    router.init_chatbot(object())
    assert len(router.get_service().generator.providers) == 2
    router.close_chatbot()

def test_general_housing_contract_identity_clause_survives_rental_scope_filter():
    row = dict(chunk_id=1,document_id=1,category='housing_contract',similarity_score=.7,
        heading='Điều 163. Hợp đồng về nhà ở | Khoản 1',
        content='Hợp đồng về nhà ở do các bên thỏa thuận và phải được lập thành văn bản, bao gồm hợp đồng mua bán, cho thuê và các nội dung: họ và tên cá nhân, địa chỉ của các bên.')
    assert rerank_legal('Chủ trọ có thể yêu cầu thông tin cá nhân nào để làm hợp đồng và đăng ký cư trú?', [row])

@pytest.mark.parametrize('answer,partial', [
    ('Chưa tìm thấy căn cứ xác định danh mục thông tin bắt buộc [1].', False),
    ('Chưa tìm thấy căn cứ xác định danh mục bắt buộc [1].\nHợp đồng về nhà ở gồm họ tên và địa chỉ các bên [1].', True),
])
def test_service_flags_incomplete_cloud_answer(answer, partial):
    class Repo:
        def retrieve_legal(self, *args, **kwargs):
            return [dict(rank=1, chunk_id=1, document_id=1, similarity_score=.95,
                title='Nguồn thử', category='housing_contract', source_path='test.md',
                heading='Điều 163. Hợp đồng về nhà ở', content='Hợp đồng về nhà ở gồm họ tên và địa chỉ các bên.')]
    class Generator:
        def generate(self, *args, **kwargs): return GenerationResult(answer, 'gemini', 'test-model')
    result = ChatService(Repo(), DeterministicFakeEmbedder(), Generator()).ask(
        ChatAskRequest(message='Hợp đồng cần thông tin cá nhân nào?'))
    assert result.no_answer is True
    assert result.partial_answer is partial


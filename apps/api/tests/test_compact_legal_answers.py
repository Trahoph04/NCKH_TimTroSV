"""Regression checks for long source fallbacks and source-notice false positives."""
import json
from dataclasses import replace

from app.room_service.chatbot.agent_workflow import GeminiAnswerSynthesisAgent, LegalAgentWorkflow
from app.room_service.chatbot.legal_retrieval import evidence_issues, rerank_legal
from app.room_service.chatbot.providers import DeterministicFakeEmbedder, GenerationResult
from app.room_service.chatbot.schemas import ChatAskRequest
from app.room_service.chatbot.service import ChatService
from app.room_service.chatbot.source_selection import render_selection, selection_candidates, render_source_fallback
from app.room_service.chatbot.topics import question_categories
from app.room_service.chatbot.agents import QuestionAnalysisAgent, QuestionPlan


QUESTION = 'Hợp đồng thuê trọ có cần ghi giá thuê và thời hạn thanh toán không?'
NOTICE = 'Hướng dẫn kiểm tra thuê phòng của đơn vị xuất bản; không phải điều luật.'


def row(content=None):
    return dict(rank=1, document_id=1, chunk_id=1, title='Nguồn kiểm tra',
                heading='Giá thuê và thanh toán', category='housing_contract',
                similarity_score=.95, source_scope_warning=NOTICE,
                content=content or 'Các bên thỏa thuận giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ.')


class Selector:
    providers = []

    def generate(self, question, contexts, **kwargs):
        return render_selection(question, contexts, selection_candidates(contexts),
                                '{"selected_ids":[1],"insufficient":false}', 'qwen-local', 'test')


class Client:
    model = 'test'

    def __init__(self, fail=False):
        self.fail = fail
        self.checked = []

    def request_json(self, prompt, schema, **kwargs):
        assert NOTICE in prompt  # Writer still receives applicability notices.
        if self.fail:
            raise RuntimeError('writer unavailable')
        return json.dumps(dict(summary=dict(
            text='Các bên thỏa thuận giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ',
            source_ranks=[1]), steps=[], limitations=[], follow_up_questions=[], coverage='complete')), {}

    def check_legal_evidence(self, question, answer, contexts):
        self.checked.append(answer)
        assert NOTICE not in answer
        return []


def ask(context, client):
    class Repo:
        def retrieve_legal(self, *args, **kwargs):
            return [context]
    agent = LegalAgentWorkflow(Selector(), GeminiAnswerSynthesisAgent(client), client)
    return ChatService(Repo(), DeterministicFakeEmbedder(), agent).ask(
        ChatAskRequest(message=QUESTION, include_evaluation_contexts=True))


def test_publisher_notice_does_not_force_good_synthesis_back_to_quotes():
    client = Client()
    result = ask(row(), client)
    assert result.generation_provider == 'gemini-agent'
    assert NOTICE in result.answer
    assert len(client.checked) == 1
    assert result.citation_accuracy == 1


def test_only_exact_application_notice_is_exempt_and_unsupported_claim_still_fails():
    source = row()
    draft = Selector().generate(QUESTION, [source])
    generated = GenerationResult('Các bên thỏa thuận giá thuê [1].\n' + NOTICE +
                                 '\nChủ trọ phải hoàn trả 99 triệu đồng.',
                                 'gemini-agent', source_fallback=draft)
    assert NOTICE not in generated.text_for_verification
    assert evidence_issues(generated.text_for_verification, [source], QUESTION)
    altered = replace(generated, text=NOTICE + ' Chủ trọ phải hoàn trả 99 triệu đồng.')
    assert altered.text_for_verification == altered.text
    assert evidence_issues(altered.text_for_verification, [source], QUESTION)
    untrusted = replace(generated, source_fallback=None, evidence_limitations=(NOTICE,))
    assert untrusted.text_for_verification == untrusted.text


def test_large_clause_is_not_cut_to_hide_its_exception_and_remains_in_context():
    full = ('Các bên thỏa thuận giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ. ' * 55
            + 'Trừ trường hợp có thỏa thuận khác về điều kiện thanh toán.')
    result = ask(row(full), Client(fail=True))
    assert len(result.answer) <= 3500
    assert full not in result.answer
    assert 'xem nội dung nguồn' in result.answer
    assert NOTICE in result.answer
    assert result.no_answer  # Navigation is not a complete answer.
    assert result.evaluation_contexts[0].content == full
    assert result.citation_accuracy == 1


def test_compact_fallback_keeps_whole_short_unit_and_commencement_notice():
    unit = 'Quy định áp dụng khi đáp ứng điều kiện nêu trong nguồn, trừ trường hợp được miễn.'
    notice = 'Hiệu lực của quy định xác thực: áp dụng từ ngày 01/01/2027.'
    parts = [dict(rank=1, document='Nguồn', heading='Điều kiện', text=unit),
             dict(rank=2, document='Nguồn dài', heading='Điều 17', text=unit * 80)]
    answer = render_source_fallback(parts, [notice])
    assert f'“{unit}” [1]' in answer
    assert unit * 80 not in answer and '[2]' in answer
    assert notice in answer and 'Chưa đủ căn cứ' in answer
    assert len(answer) <= 3500


def test_renter_checking_posts_includes_practical_advice_without_rerouting_operator_duties():
    query = 'Khi tìm phòng qua một nền tảng trực tuyến, tôi nên kiểm tra người đăng và nguồn tin như thế nào?'
    categories = question_categories(query)
    assert categories[0] == 'criminal_law' and 'housing_contract' in categories
    duties = 'Nền tảng đăng tin có trách nhiệm gì đối với thông tin người bán hoặc người cho thuê?'
    assert question_categories(duties) == ('ecommerce_platform',)
    contexts = [dict(chunk_id=1, category='ecommerce_platform', similarity_score=.9,
                     heading='Điều 17. Trách nhiệm của chủ quản nền tảng',
                     content='Chủ quản nền tảng phải kiểm tra người bán và gỡ bỏ thông tin vi phạm.'),
                dict(chunk_id=2, category='criminal_law', similarity_score=.5,
                     heading='Khuyến cáo người thuê kiểm tra tin đăng',
                     content='Khi tìm phòng trực tuyến, người thuê cần kiểm tra người đăng và xác minh nguồn tin để cảnh giác lừa đảo.')]
    assert rerank_legal(query, contexts, 5)[0]['chunk_id'] == 2


def test_analysis_accepts_a_single_missing_fact_without_losing_gemini_plan():
    class AnalysisClient:
        model = 'test'
        def request_json(self, prompt, schema, **kwargs):
            assert 'OUTPUT_SCHEMA:' in prompt
            return json.dumps(dict(search_queries=['Cách kiểm tra tin đăng trực tuyến'],
                                   categories=['ecommerce_platform'],
                                   missing_information='Chưa biết tên nền tảng.', as_of_date=None)), {}
    result = QuestionAnalysisAgent(AnalysisClient()).analyze('Tôi kiểm tra người đăng trên nền tảng trực tuyến thế nào?')
    assert result.step['provider'] == 'gemini'
    assert result.plan.missing_information == ['Chưa biết tên nền tảng.']
    assert 'criminal_law' in result.plan.categories
    assert QuestionPlan(missing_information=None).missing_information == []


def test_invalid_analysis_retains_field_diagnostics_and_detected_topics():
    class AnalysisClient:
        model = 'test'
        def request_json(self, *args, **kwargs):
            return '{"missing_information":{"invented":"object"}}', {}
    result = QuestionAnalysisAgent(AnalysisClient()).analyze('Tôi báo cáo tin đăng sai trên nền tảng trực tuyến thế nào?')
    assert result.step['provider'] == 'rules'
    assert result.step['validation_errors'] == [{'field': 'missing_information', 'type': 'list_type'}]
    assert 'ecommerce_platform' in result.plan.categories


def test_practical_checklist_reserves_image_source_despite_different_source_vocabulary():
    from app.room_service.chatbot.legal_retrieval import diversified_legal_rows, expand_legal_query
    from app.room_service.chatbot.topics import required_evidence_categories
    query = 'Khi tìm phòng qua một nền tảng trực tuyến, tôi nên kiểm tra người đăng và nguồn tin như thế nào?'
    rows = [dict(chunk_id=1, document_id=1, category='ecommerce_platform', similarity_score=.7,
                 heading='Google Lens', content='Trang web có hình ảnh đó hoặc có hình ảnh tương tự; nhấp vào Tìm bằng Google Ống kính.'),
            dict(chunk_id=2, document_id=2, category='ecommerce_platform', similarity_score=.8,
                 heading='Bảo vệ người dùng', content='Xác thực số điện thoại cho mỗi tài khoản người đăng; loại bỏ tin có giá thấp đáng ngờ.'),
            dict(chunk_id=3, document_id=3, category='housing_contract', similarity_score=.7,
                 heading='Kiểm tra phòng', content='Kiểm tra địa chỉ phòng và số điện thoại người cho thuê.')]
    ranked = rerank_legal(query, rows, 5)
    assert {r['chunk_id'] for r in diversified_legal_rows(query, ranked, 4)} == {1, 2, 3}
    assert 'Google Ống kính' in expand_legal_query(query)
    assert 'ecommerce_platform' not in required_evidence_categories(query)


def test_operator_general_duties_outrank_ordering_only_special_case():
    query = 'Nền tảng đăng tin có trách nhiệm gì đối với thông tin người cho thuê?'
    rows = [dict(chunk_id=1, category='ecommerce_platform', similarity_score=.9,
                 heading='Điều 17. Trách nhiệm của chủ quản nền tảng | Khoản 2',
                 content='Nền tảng có chức năng đặt hàng trực tuyến phải cung cấp công cụ tải dữ liệu hợp đồng.'),
            dict(chunk_id=2, category='ecommerce_platform', similarity_score=.5,
                 heading='Điều 17. Trách nhiệm của chủ quản nền tảng | Khoản 1',
                 content='Nền tảng thực hiện xác thực danh tính và kiểm duyệt nội dung thông tin do người bán cung cấp.')]
    assert rerank_legal(query, rows, 5)[0]['chunk_id'] == 2


def test_agency_deadline_cannot_be_generalized_to_every_user_report():
    rows = [dict(rank=1, heading='Nguồn điều kiện',
                 content='Tạm ngừng tài khoản trong thời hạn 24 giờ kể từ khi nhận yêu cầu của cơ quan nhà nước có thẩm quyền.')]
    assert any('24 giờ' in issue for issue in evidence_issues(
        'Nền tảng phải tạm ngừng tài khoản trong thời hạn 24 giờ khi người dùng báo cáo [1].', rows, 'Báo cáo tin đăng?'))
    assert not evidence_issues('Nền tảng tạm ngừng tài khoản trong thời hạn 24 giờ kể từ yêu cầu của cơ quan nhà nước có thẩm quyền [1].', rows, 'Trách nhiệm nền tảng?')


def test_operator_selection_keeps_distinct_duties_from_complete_parent_units():
    from app.room_service.chatbot.legal_retrieval import diversified_legal_rows
    from app.room_service.chatbot.source_selection import missing_selection_facets
    query = 'Nền tảng đăng tin có trách nhiệm gì đối với thông tin người bán?'
    rows = [dict(rank=1, document_id=1, chunk_id=1, heading='Định danh', category='ecommerce_platform',
                 content='Nền tảng xác thực danh tính và kiểm duyệt thông tin người bán.'),
            dict(rank=2, document_id=1, chunk_id=2, heading='Định danh chi tiết', category='ecommerce_platform',
                 content='Xác thực danh tính bằng số định danh cá nhân.'),
            dict(rank=3, document_id=2, chunk_id=3, heading='Kiểm duyệt', category='ecommerce_platform',
                 content='Lọc từ khóa và gỡ bỏ nội dung sai, tiếp nhận phản ánh theo quy trình công khai.'),
            dict(rank=4, document_id=2, chunk_id=4, heading='Nền tảng có chức năng đặt hàng', category='ecommerce_platform',
                 content='Một đoạn ngắn chưa chứa phần cung cấp dữ liệu.',
                 parent_content='Nền tảng có chức năng đặt hàng cung cấp dữ liệu trong 24 giờ từ yêu cầu của cơ quan nhà nước có thẩm quyền.')]
    selected = diversified_legal_rows(query, rows, 3)
    assert {r['chunk_id'] for r in selected} == {1, 3, 4}
    # Selection sees the complete clause, including the authority condition.
    rows[-1]['content'] = rows[-1]['parent_content']
    missing = missing_selection_facets(query, selection_candidates(rows), '{"selected_ids":[1],"insufficient":false}')
    assert any('từ khóa' in m for m in missing) and any('cơ quan' in m for m in missing)


def test_reporting_selection_does_not_omit_available_picture_evidence():
    from app.room_service.chatbot.source_selection import missing_selection_facets
    rows = [dict(rank=1, title='Báo cáo', heading='Thao tác', category='ecommerce_platform',
                 content='Chọn Báo cáo tin đăng, chọn lý do và gửi đường link cho bộ phận hỗ trợ.'),
            dict(rank=2, title='Bằng chứng', heading='Hình ảnh', category='ecommerce_platform',
                 content='Thông tin (hình ảnh) trao đổi mua bán của bạn với người bán thể hiện hành vi vi phạm (nếu có).')]
    assert any('hình ảnh' in m for m in missing_selection_facets(
        'Báo cáo tin đăng sai thế nào?', selection_candidates(rows), '{"selected_ids":[1],"insufficient":false}'))
    from app.room_service.chatbot.evidence_units import platform_reporting_question
    from app.room_service.chatbot.legal_retrieval import expand_legal_query
    paraphrase = 'Nếu một tin đăng nhà trọ có thông tin sai, tôi có thể báo cáo cho nền tảng bằng cách nào?'
    assert platform_reporting_question(paraphrase)
    assert 'hình ảnh trao đổi' in expand_legal_query(paraphrase)


def test_writer_must_not_guess_a_redacted_support_email():
    rows = [dict(rank=1, heading='Liên hệ', content='Gửi đường link và lý do qua email [email protected] để báo cáo tin.')]
    assert any('email' in issue for issue in evidence_issues(
        'Gửi đường link và lý do qua email trogiup@chotot.vn để báo cáo tin [1].', rows, 'Báo cáo tin?'))
    rows[0]['content'] = 'Gửi đường link và lý do qua email support@example.com để báo cáo tin.'
    assert not evidence_issues('Gửi đường link và lý do qua email support@example.com để báo cáo tin [1].', rows, 'Báo cáo tin?')


def test_report_selection_keeps_available_handling_rule_with_its_agency_condition():
    from app.room_service.chatbot.source_selection import missing_selection_facets
    rows = [dict(rank=1, title='Báo tin', heading='Thao tác', category='ecommerce_platform',
                 content='Chọn Báo cáo tin đăng và gửi đường link, lý do cho bộ phận hỗ trợ.'),
            dict(rank=2, title='Nguồn xử lý', heading='Xử lý vi phạm', category='ecommerce_platform',
                 content='Gỡ bỏ tin vi phạm trong 24 giờ kể từ yêu cầu của cơ quan nhà nước có thẩm quyền.')]
    missing = missing_selection_facets('Tôi báo cáo tin đăng sai cho nền tảng thế nào?',
                                      selection_candidates(rows), '{"selected_ids":[1],"insufficient":false}')
    assert any('đúng điều kiện' in point for point in missing)


def test_operator_writer_cannot_silently_drop_supported_complaint_channel():
    query = 'Nền tảng có trách nhiệm gì đối với thông tin người bán?'
    rows = [dict(rank=1, category='ecommerce_platform', heading='Tiếp nhận phản ánh',
                 content='Nền tảng duy trì kênh công khai để tiếp nhận phản ánh và giải quyết khiếu nại.')]
    assert any('tiếp nhận phản ánh' in issue for issue in evidence_issues(
        'Nền tảng có các trách nhiệm đối với người bán [1].', rows, query))
    assert not evidence_issues('Nền tảng duy trì kênh công khai tiếp nhận phản ánh và giải quyết khiếu nại [1].', rows, query)


def test_delayed_identity_requirement_is_not_hidden_only_in_a_footer():
    from datetime import datetime
    future_year = datetime.now().year + 1
    rows = [dict(rank=1, heading='Định danh', content='Thực hiện xác thực điện tử danh tính người bán.',
                 source_scope_warning=f'Điều hiệu lực: quy định xác thực điện tử áp dụng từ 01/01/{future_year}.')]
    assert any('áp dụng muộn' in issue for issue in evidence_issues(
        'Nền tảng phải thực hiện xác thực điện tử danh tính người bán [1].', rows, 'Trách nhiệm nền tảng?'))
    assert not evidence_issues(f'Nền tảng thực hiện xác thực điện tử danh tính người bán từ ngày 01/01/{future_year} [1].', rows, 'Trách nhiệm nền tảng?')

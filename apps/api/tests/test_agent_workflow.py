import json

import pytest

from app.room_service.chatbot.agent_workflow import GeminiAnswerSynthesisAgent, LegalAgentWorkflow
from app.room_service.chatbot.agents import QuestionAnalysisAgent, QuestionPlan
from app.room_service.chatbot.providers import DeterministicFakeEmbedder, GroundedTemplateGenerator
from app.room_service.chatbot.schemas import ChatAskRequest
from app.room_service.chatbot.service import ChatService
from app.room_service.chatbot.source_selection import render_selection, selection_candidates


QUESTION = 'Hợp đồng thuê trọ có cần ghi giá thuê và thời hạn thanh toán không?'


def prompt_data(prompt):
    return json.JSONDecoder().raw_decode(prompt[prompt.index('{"QUESTION"'):])[0]


def rows():
    return [dict(rank=1, document_id=1, chunk_id=11, title='Nguồn thử', category='housing_contract',
                 heading='Thanh toán', similarity_score=0.95, source_path='one',
                 content='Các bên thỏa thuận giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ.'),
            dict(rank=2, document_id=2, chunk_id=22, title='Nguồn không được chọn', category='housing_contract',
                 heading='Bồi thường', similarity_score=0.8, source_path='two',
                 content='Thông tin bồi thường khác, không được sử dụng khi Qwen không chọn nguồn này.')]


def draft(*, insufficient=False):
    context = rows()
    return render_selection(QUESTION, context, selection_candidates(context),
        json.dumps({'selected_ids': [1], 'insufficient': insufficient}), 'qwen-local', 'qwen-test')


def answer(*, ranks=None, coverage='complete'):
    return {'summary': {'text': 'Các bên thỏa thuận giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ',
                        'source_ranks': ranks or [1]},
            'steps': [{'text': 'Khuyến nghị: nên đối chiếu giá thuê và thời hạn thanh toán trong hợp đồng thuê trọ',
                       'source_ranks': [1]}],
            'limitations': [], 'follow_up_questions': [], 'coverage': coverage}


class Selector:
    providers = []
    def __init__(self, insufficient=False):
        self.calls = 0
        self.insufficient = insufficient

    def generate(self, question, contexts, **kwargs):
        self.calls += 1
        return draft(insufficient=self.insufficient) if contexts else GroundedTemplateGenerator().generate(question, [], context_kind='legal')

    def check_legal_evidence(self, *args):
        raise RuntimeError('Local verifier unavailable')


class Client:
    model = 'gemini-test'
    def __init__(self, result=None, error=None, rejection=None):
        self.result = result or answer()
        self.error = error
        self.rejection = rejection or []
        self.writes = 0
        self.checks = 0

    def request_json(self, prompt, schema, **kwargs):
        self.writes += 1
        payload = prompt_data(prompt)
        assert [r['rank'] for r in payload['EVIDENCE']] == [1]
        assert 'Nguồn không được chọn' not in prompt
        assert 'OUTPUT_SCHEMA:' in prompt
        if self.error:
            raise self.error
        return json.dumps(self.result, ensure_ascii=False), {}

    def check_legal_evidence(self, question, text, contexts):
        self.checks += 1
        assert [r['rank'] for r in contexts] == [1]
        return self.rejection


def workflow(client=None, selector=None):
    client = client or Client()
    selector = selector or Selector()
    return LegalAgentWorkflow(selector, GeminiAnswerSynthesisAgent(client), client), selector, client


class Repo:
    legal_schema = 'public'
    def retrieve_legal(self, *args, **kwargs):
        return rows()


def service(agent, repo=None):
    return ChatService(repo or Repo(), DeterministicFakeEmbedder(), agent,
                       question_analyzer=QuestionAnalysisAgent())


def test_workflow_keeps_selected_source_scope_and_records_roles():
    agent, selector, client = workflow()
    result = service(agent).ask(ChatAskRequest(message=QUESTION, include_evaluation_contexts=True))
    assert result.generation_provider == 'gemini-agent'
    assert '[1]' in result.answer and '[2]' not in result.answer
    assert 'Các đoạn trả lời trực tiếp' not in result.answer
    assert selector.calls == client.writes == client.checks == 1
    roles = [step['agent'] for step in result.agent_trace]
    assert roles[:4] == ['question_analysis', 'legal_retrieval', 'evidence_selection', 'answer_synthesis']
    assert any(s['agent'] == 'source_verification' and s['provider'] == 'gemini' and s['status'] == 'accepted' for s in result.agent_trace)


@pytest.mark.parametrize('bad_result,error', [
    (answer(ranks=[2]), None),
    ({'summary': 'malformed'}, None),
    (None, RuntimeError('HTTP 429')),
])
def test_writer_failure_uses_verbatim_draft_without_unverified_claims(bad_result, error):
    agent, _, client = workflow(Client(result=bad_result, error=error))
    result = service(agent).ask(ChatAskRequest(message=QUESTION))
    assert result.generation_provider == 'qwen-local'
    assert rows()[0]['content'] in result.answer and rows()[1]['content'] not in result.answer
    assert client.checks == 0
    assert result.degraded and any(s.get('status') == 'fallback' for s in result.agent_trace)
    assert any(s.get('provider') == 'exact_source_match' for s in result.agent_trace)


def test_writer_cannot_erase_partial_selection_or_missing_evidence():
    agent, _, _ = workflow(selector=Selector(insufficient=True))
    result = service(agent).ask(ChatAskRequest(message=QUESTION))
    assert result.partial_answer and result.no_answer
    assert 'Chưa đủ căn cứ' in result.answer
    assert any(s['agent'] == 'answer_synthesis' and s['status'] == 'partial' for s in result.agent_trace)


def test_schema_retry_keeps_evidence_and_validates_repaired_claims():
    class RepairClient(Client):
        def request_json(self, prompt, schema, **kwargs):
            self.result = answer()
            if self.writes == 0:
                self.result['summary']['title'] = 'Unwanted title'
            else:
                assert 'extra_forbidden' in prompt_data(prompt)['ISSUES'][-1]
            return super().request_json(prompt, schema, **kwargs)
    agent, selector, client = workflow(RepairClient())
    result = service(agent).ask(ChatAskRequest(message=QUESTION))
    assert client.writes == 2 and client.checks == selector.calls == 1
    assert result.generation_provider == 'gemini-agent'
    assert any(s.get('status') == 'schema_retry' for s in result.agent_trace)


def test_invalid_schema_retry_stops_after_two_attempts():
    agent, selector, client = workflow(Client(result={'summary':'malformed'}))
    result = service(agent).ask(ChatAskRequest(message=QUESTION))
    assert client.writes == 2 and selector.calls == 1 and client.checks == 0
    assert result.generation_provider == 'qwen-local'


def test_semantic_rejection_repairs_once_reuses_selection_then_falls_back():
    agent, selector, client = workflow(Client(rejection=['Kết luận chưa được nguồn xác nhận.']))
    result = service(agent).ask(ChatAskRequest(message=QUESTION))
    assert selector.calls == 1 and client.writes == client.checks == 2
    assert result.generation_provider == 'qwen-local'
    assert rows()[0]['content'] in result.answer
    assert result.degraded
    assert len([s for s in result.agent_trace if s['agent'] == 'source_verification' and s['status'] == 'rejected']) == 2
    assert any(s.get('repair') is True for s in result.agent_trace)


def test_empty_retrieval_never_calls_writer_or_verifier():
    class EmptyRepo(Repo):
        def retrieve_legal(self, *args, **kwargs):
            return []
    agent, _, client = workflow()
    result = service(agent, EmptyRepo()).ask(ChatAskRequest(message=QUESTION))
    assert client.writes == client.checks == 0
    assert result.no_answer and not result.sources
    assert any(s.get('reason') == 'no_selected_evidence' for s in result.agent_trace)


def test_plan_is_passed_as_data_and_traces_do_not_accumulate_between_requests():
    agent, _, client = workflow()
    captured = []
    original = client.request_json
    def request(prompt, schema, **kwargs):
        captured.append(prompt_data(prompt))
        return original(prompt, schema, **kwargs)
    client.request_json = request
    plan = QuestionPlan(missing_information=['Các bên đã thỏa thuận ngày thanh toán chưa?'])
    first = agent.generate_legal(QUESTION, rows(), question_plan=plan)
    second = agent.generate_legal(QUESTION, rows(), question_plan=plan)
    assert len(first.agent_trace) == len(second.agent_trace) == 2
    assert captured[0]['PLAN']['missing_information'] == plan.missing_information
    assert first.source_fallback.literal_source_answer and not first.literal_source_answer


def test_fallback_provider_chain_preserves_selection_metadata():
    from app.room_service.chatbot.providers import FallbackResponseGenerator
    chained = FallbackResponseGenerator([Selector(insufficient=True)])
    result = chained.generate(QUESTION, rows(), context_kind='legal')
    assert result.literal_source_answer and len(result.selected_evidence) == 1
    assert result.evidence_limitations


def test_router_builds_enabled_workflow_and_closes_each_client_once(monkeypatch):
    from app.config import Settings
    from app.room_service.chatbot import router
    settings = Settings(_env_file=None, chatbot_agents_enabled=True,
        chatbot_answer_synthesis_enabled=True, chatbot_answer_synthesis_model='gemini-writer-test',
        chatbot_question_analysis_model='gemini-analysis-test', gemini_api_key='test-only')
    monkeypatch.setattr(router, 'settings', settings)
    monkeypatch.setattr(router, '_service', None)
    monkeypatch.setattr(router, 'E5EmbeddingProvider', lambda *args: DeterministicFakeEmbedder())
    router.init_chatbot(object())
    current = router.get_service()
    assert isinstance(current.generator, LegalAgentWorkflow)
    assert current.generator.writer.client.model == 'gemini-writer-test'
    assert current.generator.verifier is current.generator.writer.client
    assert current.question_analyzer.client.model == 'gemini-analysis-test'
    clients = [*current.generator.providers, current.question_analyzer.client, current.generator.verifier]
    calls = []
    for client in clients:
        close = client.close
        def tracked(_client=client, _close=close):
            calls.append(id(_client))
            _close()
        monkeypatch.setattr(client, 'close', tracked)
    router.close_chatbot()
    assert len(calls) == len(set(calls)) == len(clients)

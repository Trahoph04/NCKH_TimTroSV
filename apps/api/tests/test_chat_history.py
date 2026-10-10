"""Cache semantics plus PostgreSQL HTTP tests in an isolated temporary schema."""
import os
from pathlib import Path
import re
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import settings
from app.room_service.chatbot.history import answer_key, normalized_question, reusable, shared_answer_key, public_answer
from app.room_service.chatbot.schemas import ChatAskRequest, ChatAskResponse, ChatHistoryMessage


QUESTION = 'Phí ở KTX CTU bao nhiêu một tháng?'


def response(**updates):
    data = dict(answer='Phí KTX theo khung công bố của CTU [1].', intent='legal_question', confidence=.9,
                generation_provider='gemini-agent', latency_ms=1200,
                agent_trace=[dict(agent='source_verification', provider='gemini', status='accepted')],
                sources=[dict(kind='legal_document', rank=1, similarity_score=.9, title='Thông tin KTX',
                              source='CTU', category='student_housing')])
    data.update(updates)
    return ChatAskResponse(**data)


def test_exact_question_normalization_keeps_accents_numbers_and_punctuation():
    assert normalized_question('  PHÍ  KTX\nCTU? ') == normalized_question('phí ktx ctu?')
    assert normalized_question('phi ktx') != normalized_question('phí ktx')
    assert normalized_question('phí 220000') != normalized_question('phí 475000')


def test_standalone_legal_repeat_can_reuse_despite_prior_turns():
    first = ChatAskRequest(message=QUESTION)
    repeated = ChatAskRequest(message=QUESTION.upper(), conversation_history=[
        dict(role='user', content=QUESTION), dict(role='assistant', content='Thông tin theo nguồn CTU.')])
    assert answer_key(first) == answer_key(repeated)


def test_followup_and_listing_filters_are_part_of_cache_identity():
    first = ChatAskRequest(message='Quy định này áp dụng từ khi nào?', conversation_history=[dict(role='user', content=QUESTION)])
    other = first.model_copy(update={'conversation_history': [ChatHistoryMessage(role='user', content='Hợp đồng thuê trọ cần ghi gì?')]})
    assert answer_key(first) != answer_key(other)
    assert answer_key(ChatAskRequest(message='Tìm phòng có wifi', filters={'max_price': 2000000})) != answer_key(
        ChatAskRequest(message='Tìm phòng có wifi', filters={'max_price': 3000000}))


def test_only_supported_answers_are_reusable_including_sourced_partial():
    assert reusable(response())
    assert reusable(response(no_answer=True, partial_answer=True))
    assert not reusable(response(generation_provider='template'))
    assert not reusable(response(agent_trace=[], degraded=True))


def test_verified_retained_subset_is_reusable_after_rejected_drafts():
    trace = [dict(agent='source_verification', status='rejected'),
             dict(agent='source_verification', status='partial_retained',
                  retained_claim_ids=['summary', 'steps:0'], rejected_claim_ids=['steps:1']),
             dict(agent='citation_and_rule_checks', status='accepted')]
    assert reusable(response(no_answer=True, partial_answer=True, degraded=True, agent_trace=trace))
    assert not reusable(response(no_answer=True, partial_answer=True, agent_trace=trace[:-1]))
    assert not reusable(response(no_answer=True, partial_answer=True,
        agent_trace=[*trace[:-1], dict(agent='citation_and_rule_checks', status='rejected')]))
    assert not reusable(response(no_answer=True, partial_answer=True,
        agent_trace=[trace[0], dict(agent='source_verification', status='partial_retained', retained_claim_ids=[]), trace[-1]]))


def test_earlier_acceptance_does_not_cache_a_final_rejected_answer():
    assert not reusable(response(agent_trace=[dict(agent='source_verification', status='accepted'),
                                              dict(agent='source_verification', status='rejected')]))
    assert not reusable(response(no_answer=True, partial_answer=False))


@pytest.mark.parametrize('message', ['Tôi cần đăng ký tạm trú', 'Phí KTX cho MSSV 12345678?',
    'Phí KTX cho a@example.com?', 'Quy định này áp dụng từ khi nào?', 'Phòng đó còn không?'])
def test_personal_or_ambiguous_questions_do_not_enter_shared_cache(message):
    assert shared_answer_key(ChatAskRequest(message=message)) is None


def test_shared_key_includes_filters_and_excludes_context():
    assert shared_answer_key(ChatAskRequest(message=QUESTION)) == shared_answer_key(ChatAskRequest(message=QUESTION.upper()))
    assert shared_answer_key(ChatAskRequest(message=QUESTION, conversation_history=[dict(role='user', content=QUESTION)])) is None
    assert shared_answer_key(ChatAskRequest(message=QUESTION, conversation_state={})) is None
    assert shared_answer_key(ChatAskRequest(message=QUESTION, include_evaluation_contexts=True)) is None
    assert shared_answer_key(ChatAskRequest(message='Tìm phòng có wifi', filters={'max_price': 2000000})) != shared_answer_key(
        ChatAskRequest(message='Tìm phòng có wifi', filters={'max_price': 3000000}))


def test_public_answer_does_not_copy_private_identifiers_or_agent_trace():
    payload = public_answer(response(conversation_id=uuid4(), turn_id=8, event_id=99,
        agent_trace=[{'question': 'private'}], evaluation_contexts=[dict(kind='legal_document', rank=1, content='private')]))
    assert not {'conversation_id', 'turn_id', 'event_id', 'agent_trace', 'evaluation_contexts', 'conversation_state'} & payload.keys()


@pytest.fixture
def history_api(monkeypatch):
    if os.environ.get('RUN_CHAT_HISTORY_DB_TESTS') != '1':
        pytest.skip('Requires PostgreSQL; each test creates and removes its own isolated schema')
    from app.auth import deps
    from app.auth.security import make_access_token
    from app.room_service.chatbot import router as routes
    from app.room_service.chatbot.repo import ChatRepository

    namespace = 'legal_history_test_' + uuid4().hex[:12]
    assert re.fullmatch(r'legal_history_test_[a-f0-9]{12}', namespace)
    admin = create_engine(settings.database_url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {namespace}'))
    engine = create_engine(settings.database_url, connect_args={'options': f'-csearch_path={namespace},public'})
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE users (id integer PRIMARY KEY)'))
            conn.execute(text('INSERT INTO users VALUES (1),(2)'))
            # bảng aggregated_listings giả tạo TRƯỚC migration để ALTER của mig 100 rơi vào schema tạm, không đụng public
            conn.execute(text('CREATE TABLE aggregated_listings (id integer, updated_at timestamptz DEFAULT now(), last_seen timestamptz DEFAULT now(), '
                              'listing_type text, quality_score real, freshness_score real, status text, cleaning_status text)'))
            # repo này gộp phần chatbot của mig 94/98/99/100 (branch PHUC) vào 100_chatbot.sql — cần thư mục infra/
            # trong container: docker cp infra/db/migrations/. <api>:/app/infra/db/migrations/
            migration = next((parent / 'infra/db/migrations/100_chatbot.sql' for parent in Path(__file__).resolve().parents
                              if (parent / 'infra/db/migrations/100_chatbot.sql').is_file()), None)
            if migration is None:
                pytest.skip('Thiếu infra/db/migrations/100_chatbot.sql cạnh tests')
            conn.connection.driver_connection.execute(migration.read_text(encoding='utf-8'))
            conn.execute(text("INSERT INTO legal_documents (id,source_path,title,category,document_type,content_sha256,status) "
                              "VALUES (1,'test.txt','Thông tin KTX','student_housing','txt','first','ready')"))
            conn.execute(text("INSERT INTO legal_chunks (document_id,chunk_index,content,content_sha256) VALUES (1,0,'Phí KTX CTU','first')"))
            conn.execute(text("ALTER TABLE legal_documents ADD COLUMN source_metadata jsonb DEFAULT '{}'"))
            conn.execute(text("ALTER TABLE legal_chunks ADD COLUMN source_metadata jsonb DEFAULT '{}', ADD COLUMN parent_content text, ADD COLUMN provision_id text"))
        class Auth:
            def get_user(self, uid):
                return dict(id=uid, email=f'user{uid}@example.com', name='Test', role='admin' if uid == 2 else 'user', auth_version=0) if uid in (1, 2) else None
        monkeypatch.setattr(deps, '_repo', Auth())
        monkeypatch.setattr(routes, 'check_rate', lambda *args: None)
        class Service:
            def __init__(self):
                self.repo = ChatRepository(engine, namespace)
                self.calls = []
            def ask(self, body):
                self.calls.append(body)
                return response(evaluation_contexts=[dict(kind='legal_document', rank=1, content='admin-only source text')]
                                if body.include_evaluation_contexts else [])
        service = Service()
        app = FastAPI()
        app.include_router(routes.router)
        from app.room_service.legal_knowledge.admin import router as documents_router
        app.include_router(documents_router)
        app.dependency_overrides[routes.get_service] = lambda: service
        client = TestClient(app)
        headers = lambda uid: {'Authorization': f'Bearer {make_access_token(uid, "user")}' }
        yield client, service, engine, headers
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {namespace} CASCADE'))
        admin.dispose()


def test_saved_conversation_reload_repeat_and_owner_isolation(history_api):
    client, service, engine, headers = history_api
    first = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION})
    assert first.status_code == 200, first.text
    first = first.json()
    cid = first['conversation_id']
    assert first['turn_id'] and not first['reused_answer']
    repeated = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION.upper(), 'conversation_id': cid})
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()['reused_answer'] and len(service.calls) == 1
    assert repeated.json()['turn_id'] != first['turn_id']
    detail = client.get(f'/chatbot/conversations/{cid}', headers=headers(1)).json()
    assert [t['question'] for t in detail['turns']] == [QUESTION, QUESTION.upper()]
    assert detail['turns'][0]['response']['sources'][0]['category'] == 'student_housing'
    assert client.get('/chatbot/conversations', headers=headers(1)).json()['items'][0]['turn_count'] == 2
    assert client.get('/chatbot/conversations', headers=headers(2)).json()['items'] == []
    for method, payload in [('get', None), ('delete', None)]:
        assert getattr(client, method)(f'/chatbot/conversations/{cid}', headers=headers(2)).status_code == 404
    assert client.post('/chatbot/ask', headers=headers(2), json={'message': QUESTION, 'conversation_id': cid}).status_code == 404
    assert len(service.calls) == 1
    other = client.post('/chatbot/ask', headers=headers(2), json={'message': QUESTION})
    assert other.json()['reused_answer'] and len(service.calls) == 1
    assert other.json()['conversation_id'] != cid
    assert other.json()['event_id'] != first['event_id']
    assert other.json()['agent_trace'] == [dict(agent='saved_answer', provider='shared_cache', status='reused')]
    assert client.get('/chatbot/conversations').status_code in (401, 403)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM chatbot_turns')).scalar_one() == 3


def test_expiry_source_change_and_delete_invalidate_reuse(history_api):
    client, service, engine, headers = history_api
    cid = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()['conversation_id']
    with engine.begin() as conn:
        conn.execute(text("UPDATE chatbot_turns SET cache_expires_at=now()-interval '1 second'"))
        conn.execute(text("UPDATE chatbot_shared_answers SET expires_at=now()-interval '1 second'"))
    assert not client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()['reused_answer']
    with engine.begin() as conn:
        conn.execute(text("UPDATE legal_documents SET content_sha256='changed', updated_at=now()"))
    assert not client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()['reused_answer']
    assert len(service.calls) == 3
    assert client.delete(f'/chatbot/conversations/{cid}', headers=headers(1)).status_code == 204
    assert client.get(f'/chatbot/conversations/{cid}', headers=headers(1)).status_code == 404
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM chatbot_turns WHERE conversation_id=:id'), {'id': cid}).scalar_one() == 0


def test_server_context_pagination_and_bad_ids(history_api):
    client, service, _, headers = history_api
    cid = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()['conversation_id']
    follow = client.post('/chatbot/ask', headers=headers(1), json={'message': 'Quy định này áp dụng từ khi nào?',
        'conversation_id': cid, 'conversation_history': [{'role': 'user', 'content': 'Đây là ngữ cảnh giả'}]})
    assert follow.status_code == 200, follow.text
    assert service.calls[-1].conversation_history[0].content == QUESTION
    newest = client.get(f'/chatbot/conversations/{cid}?limit=1', headers=headers(1)).json()
    assert newest['has_more'] and len(newest['turns']) == 1
    older = client.get(f'/chatbot/conversations/{cid}?limit=1&before_id={newest["turns"][0]["id"]}', headers=headers(1)).json()
    assert not older['has_more'] and older['turns'][0]['question'] == QUESTION
    assert client.get('/chatbot/conversations/not-a-uuid', headers=headers(1)).status_code == 422


def test_delete_conversation_preserves_public_cache_but_removes_private_turns(history_api):
    client, service, _, headers = history_api
    first = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()
    assert client.delete(f'/chatbot/conversations/{first["conversation_id"]}', headers=headers(1)).status_code == 204
    repeat = client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION})
    assert repeat.status_code == 200, repeat.text
    assert repeat.json()['reused_answer'] and len(service.calls) == 1
    assert repeat.json()['conversation_id'] != first['conversation_id']


def test_context_and_personal_answers_are_not_shared(history_api):
    client, service, _, headers = history_api
    personal = 'Tôi hỏi phí ở KTX CTU bao nhiêu một tháng?'
    client.post('/chatbot/ask', headers=headers(1), json={'message': personal})
    assert not client.post('/chatbot/ask', headers=headers(2), json={'message': personal}).json()['reused_answer']
    assert len(service.calls) == 2


def test_shared_listing_restores_followup_state_and_filters(history_api):
    client, service, _, headers = history_api
    def ask(body):
        service.calls.append(body)
        return response(intent='listing_search', generation_provider='qwen', sources=[],
                        applied_filters={'max_price': 2000000},
                        conversation_state={'filters': {'max_price': 2000000}, 'listing_ids': [123], 'selected_listing_id': 123},
                        listings=[dict(id=123, title='Phòng công khai', source='Datahouse', price=1800000)])
    service.ask = ask
    body = {'message': 'Tìm phòng trọ dưới 2 triệu có wifi'}
    client.post('/chatbot/ask', headers=headers(1), json=body)
    shared = client.post('/chatbot/ask', headers=headers(2), json=body).json()
    assert shared['reused_answer'] and len(service.calls) == 1
    assert shared['conversation_state']['listing_ids'] == [123]
    assert shared['conversation_state']['filters']['max_price'] == 2000000
    followup = client.post('/chatbot/ask', headers=headers(2), json={
        'message': 'Phòng đó còn không?', 'conversation_id': shared['conversation_id']})
    assert followup.status_code == 200, followup.text
    assert not followup.json()['reused_answer'] and len(service.calls) == 2
    assert service.calls[-1].conversation_state.selected_listing_id == 123


def test_admin_document_controls_permissions_audit_and_cache_invalidation(history_api):
    client, service, engine, headers = history_api
    client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION})
    assert client.get('/admin/documents', headers=headers(1)).status_code == 403
    assert client.patch('/admin/documents/1', headers=headers(1), json={'admin_enabled': False}).status_code == 403
    assert client.get('/admin/documents').status_code in (401, 403)
    listing = client.get('/admin/documents?q=KTX', headers=headers(2)).json()
    assert listing['total'] == 1 and listing['corpus_schema'] == service.repo.legal_schema
    assert client.get('/admin/documents?q=%25', headers=headers(2)).json()['total'] == 0
    detail = client.get('/admin/documents/1', headers=headers(2)).json()
    assert detail['chunks'][0]['content'] == 'Phí KTX CTU'
    scope_before = __import__('app.room_service.chatbot.history', fromlist=['ChatHistoryStore']).ChatHistoryStore(engine).scope(service.repo, legal=True)
    changed = client.patch('/admin/documents/1', headers=headers(2), json={'admin_enabled': False, 'title': 'Tên mới'})
    assert changed.status_code == 200, changed.text
    assert not changed.json()['document']['admin_enabled']
    assert not client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION}).json()['reused_answer']
    assert len(service.calls) == 2
    with engine.connect() as conn:
        audit = conn.execute(text('SELECT * FROM legal_document_admin_audit')).mappings().one()
        assert audit['actor_id'] == 2 and audit['before_data']['admin_enabled'] and not audit['after_data']['admin_enabled']
    from app.room_service.chatbot.history import ChatHistoryStore
    assert ChatHistoryStore(engine).scope(service.repo, legal=True) != scope_before
    assert client.patch('/admin/documents/1', headers=headers(2), json={'admin_enabled': True}).status_code == 200
    assert client.patch('/admin/documents/1', headers=headers(2), json={'status': 'ready'}).status_code == 422
    assert client.patch('/admin/documents/1', headers=headers(2), json={'title': ' '}).status_code == 422
    assert client.patch('/admin/documents/999', headers=headers(2), json={'admin_enabled': False}).status_code == 404
    with engine.begin() as conn:
        conn.execute(text("UPDATE legal_documents SET status='failed',admin_enabled=false WHERE id=1"))
    assert client.patch('/admin/documents/1', headers=headers(2), json={'admin_enabled': True}).status_code == 409


def test_disabled_document_is_excluded_from_actual_retrieval(history_api):
    client, service, engine, headers = history_api
    with engine.begin() as conn:
        conn.execute(text("UPDATE legal_chunks SET content=:content,parent_content=:content,heading='Phí ký túc xá CTU' WHERE document_id=1"),
            {'content': 'Phí ở ký túc xá CTU được công bố theo loại phòng và cơ sở. Sinh viên đăng ký ở ký túc xá theo hướng dẫn của trường và đóng phí ở hàng tháng theo thông báo.'})
    assert service.repo.retrieve_legal(QUESTION, None)
    assert client.patch('/admin/documents/1', headers=headers(2), json={'admin_enabled': False}).status_code == 200
    assert service.repo.retrieve_legal(QUESTION, None) == []
    assert client.patch('/admin/documents/1', headers=headers(2), json={'admin_enabled': True}).status_code == 200
    assert service.repo.retrieve_legal(QUESTION, None)


def test_evaluation_context_is_not_persisted_or_reused(history_api):
    client, service, _, headers = history_api
    # Regular accounts cannot request source payloads intended for evaluations.
    assert client.post('/chatbot/ask', headers=headers(1), json={'message': QUESTION, 'include_evaluation_contexts': True}).status_code == 403
    from app.room_service.chatbot.history import ask_with_history, ChatHistoryStore
    result = ask_with_history(service, 1, ChatAskRequest(message=QUESTION, include_evaluation_contexts=True))
    assert result.evaluation_contexts
    stored = ChatHistoryStore(service.repo.engine).conversation(1, result.conversation_id, 50, None)
    assert not stored['turns'][0]['response'].get('evaluation_contexts')
    assert not ask_with_history(service, 1, ChatAskRequest(message=QUESTION)).reused_answer

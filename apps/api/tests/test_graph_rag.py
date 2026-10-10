import os
import pytest
from sqlalchemy import create_engine, text
from app.room_service.chatbot.graph_retrieval import GraphChatRepository, graph_schema, location_entities
from app.room_service.chatbot.repo import ChatRepository
from app.room_service.chatbot.schemas import ChatFilters
from app.room_service.chatbot.providers import _grounded_prompt


def test_graph_location_is_one_constraint_and_source_namespace_survives_response():
    from app.room_service.chatbot.providers import DeterministicFakeEmbedder, GroundedTemplateGenerator
    from app.room_service.chatbot.service import ChatService
    from app.room_service.chatbot.schemas import ChatAskRequest
    class Repo:
        graph_enabled = True
        listing_schema = 'housing_graph_v1'
        def retrieve(self, *args, **kwargs):
            return [dict(id=i, rank=i, title='Phòng Xuân Khánh', source='chotot', similarity_score=.79,
                _graph_trace={'stage': 'graph_retrieval', 'seed_entities': ['location:xuan_khanh', 'location:street_3_2']})
                for i in (1, 2)]
    result = ChatService(Repo(), DeterministicFakeEmbedder(), GroundedTemplateGenerator()).ask(
        ChatAskRequest(message='Có phòng nào gần đường 3/2 hoặc khu Xuân Khánh không?'))
    assert not result.no_answer
    assert result.confidence == .6762
    assert result.listings[0].corpus_schema == 'housing_graph_v1'
    assert result.retrieval_mode == 'graph_hybrid'
    assert result.agent_trace[0]['stage'] == 'graph_retrieval'


@pytest.mark.parametrize('value', ['public', 'graph_v1;DROP TABLE users', 'graph_../housing', 'Graph_v1'])
def test_graph_identifiers_reject_sql_injection(value):
    with pytest.raises(ValueError):
        graph_schema(value)


def test_explicit_location_entities_have_no_district_guess():
    assert location_entities('Quận Ninh Kiều') == []
    assert location_entities('Đường 3/20') == []
    assert location_entities('Gần đường 3/2 hoặc Xuân Khánh') == ['location:xuan_khanh', 'location:street_3_2']


def test_listing_schema_rejects_unsafe_identifier():
    with pytest.raises(ValueError):
        ChatRepository(None, listing_schema='housing_v2;DROP SCHEMA public')


def test_graph_context_retains_approximate_distance_method():
    prompt = _grounded_prompt('gần trường', [{'id': 123, 'rank': 1, 'graph_facts': [
        {'relation': 'distance_to', 'target': 'campus:ctu_khu_ii',
         'evidence': {'field': 'distance_to_ctu', 'method': 'approximate_haversine'}}]}])
    assert 'approximate_haversine' in prompt
    assert 'route_time_campus_minutes":null' in prompt


@pytest.fixture
def graph_repo():
    if os.getenv('RUN_GRAPH_DB_TESTS') != '1':
        pytest.skip('Explicit opt-in to read-only graph release integration checks')
    from app.config import settings
    engine = create_engine(settings.database_url)
    yield GraphChatRepository(engine, settings.chatbot_legal_schema, settings.chatbot_listing_schema, settings.chatbot_graph_schema)
    engine.dispose()


def test_location_walk_cannot_return_wrong_neighborhood_or_over_budget(graph_repo):
    rows = graph_repo.retrieve('Tìm phòng ở Xuân Khánh dưới 2 triệu',
                               ChatFilters(listing_type='phong_tro', max_price=2_000_000), None)
    assert rows
    for row in rows:
        assert row['price'] <= 2_000_000
        assert any(fact['target'] == 'location:xuan_khanh' for fact in row['graph_facts'])
        assert row['_graph_trace']['traversed_edges'] > 0


def test_graph_amenity_evidence_is_grounded_and_missing_capacity_stays_unknown(graph_repo):
    rows = graph_repo.retrieve('phòng có nhà vệ sinh riêng và giờ giấc tự do',
        ChatFilters(listing_type='phong_tro', amenities=['private_bathroom', 'flexible_hours']), None)
    assert rows
    for row in rows:
        for key in ['private_bathroom', 'flexible_hours']:
            assert row['parsed_amenities'][key] is True
            assert any(fact['target'] == 'amenity:' + key and fact['evidence']['value'] is True for fact in row['graph_facts'])
        assert all(fact['relation'] != 'capacity' for fact in row['graph_facts'])


def test_legal_walk_is_bounded_and_never_attaches_another_law_as_same_source(graph_repo):
    with graph_repo.engine.connect() as conn:
        seed = conn.execute(text(f"SELECT n.document_id,n.provision_id,n.label FROM {graph_repo.graph_schema}.edges e "
            f"JOIN {graph_repo.graph_schema}.nodes n ON n.id=e.source WHERE e.relation='cites' LIMIT 1")).mappings().one()
    rows = graph_repo.retrieve_legal(seed['label'], None)
    assert rows
    assert all(row['_graph_trace']['max_hops'] == 2 for row in rows if row.get('_graph_trace'))
    with graph_repo.engine.connect() as conn:
        for row in rows:
            for provision in row.get('graph_provision_ids', []):
                assert conn.execute(text(f'SELECT count(*) FROM {graph_repo.legal_schema}.legal_chunks WHERE document_id=:doc AND provision_id=:pid'),
                    {'doc': row['document_id'], 'pid': provision}).scalar_one() > 0


def test_graph_release_refuses_mismatched_source_schema(graph_repo):
    with pytest.raises(ValueError, match='does not match'):
        GraphChatRepository(graph_repo.engine, graph_repo.legal_schema, 'housing_fresh_v4', graph_repo.graph_schema)

def test_rental_payment_question_retains_price_and_deadline_from_same_article(graph_repo):
    rows=graph_repo.retrieve_legal('Hợp đồng thuê phòng có cần ghi rõ tiền thuê, tiền cọc và ngày thanh toán không?',None)
    contract=[row for row in rows if 'Hợp đồng về nhà ở' in (row.get('heading') or '')]
    assert contract
    # Native Word must retain both price and payment conditions.
    assert any('Giá trị góp vốn' in row['content'] and 'phương thức thanh toán' in row['content'] for row in contract)
    assert all(len(row['content'])<=5500 for row in contract)

def test_deposit_question_retains_return_and_forfeiture_conditions(graph_repo):
    rows=graph_repo.retrieve_legal('Tiền cọc trong hợp đồng thuê được trả lại hay mất trong trường hợp nào?',None)
    deposit=[row for row in rows if 'Đặt cọc' in (row.get('heading') or '')]
    assert deposit
    from app.room_service.chatbot.legal_retrieval import normalize_text
    assert any(all(term in normalize_text(row['content']) for term in
        ('tra lai', 'thuoc ve', 'thoa thuan khac')) for row in deposit)
    assert all(row['source_id']=='civil91-word' and row['page_kind']=='logical_document'
        and row['page_from']==row['page_to']==1 for row in deposit)

def test_invoice_check_retrieves_word_rental_billing_rule_and_commencement(graph_repo):
    rows=graph_repo.retrieve_legal('Nếu tôi nghi tiền điện bị thu cao hơn quy định, nên kiểm tra hóa đơn và căn cứ nào?',None)
    guidance=[row for row in rows if row.get('source_id')=='electricity60-word']
    assert any('không được vượt quá' in row['content'] and 'hoá đơn tiền điện' in row['content'] for row in guidance)
    assert any('ngày thực hiện điều chỉnh' in row['content'] for row in guidance)
    assert all(row['page_kind']=='logical_document' for row in guidance)

import json
import pytest
from app.room_service.chatbot.agents import QuestionAnalysisAgent, QuestionPlan
from app.room_service.legal_knowledge.provisions import structure_provisions
from app.room_service.legal_knowledge.storage import legal_sql


def test_analysis_preserves_mixed_subjects_and_rejects_invented_articles():
    class Client:
        model = 'gemini-test'
        def request_json(self, *args, **kwargs):
            return json.dumps({'search_queries':['Điều 999 hoàn cọc'], 'categories':['housing_contract']}), {}
    result = QuestionAnalysisAgent(Client()).analyze('Hợp đồng và hồ sơ tạm trú cần thông tin cá nhân gì?')
    assert result.step['status'] == 'fallback'
    assert {'housing_contract','residence','privacy_data'} <= set(result.plan.categories)
    assert not result.plan.search_queries


def test_analysis_never_supplies_an_answer_and_keeps_original_topics():
    class Client:
        model = 'gemini-test'
        def request_json(self, *args, **kwargs):
            assert 'Không trả lời pháp lý' in args[0]
            return json.dumps({'search_queries':['Hồ sơ đăng ký tạm trú'], 'categories':['residence']}), {}
    result = QuestionAnalysisAgent(Client()).analyze('Hợp đồng thuê trọ và tạm trú')
    assert result.step['provider'] == 'gemini'
    assert result.plan.categories == ['residence','housing_contract']
    with pytest.raises(ValueError):
        QuestionPlan.model_validate({'answer':'invented conclusion'})


def test_provisions_keep_complete_clauses_and_exception_without_editorial_tail():
    text = ('GHI CHÚ NGỮ CẢNH\nKhông dùng phần này.\n\nĐiều 328. Đặt cọc\n'
            '1. Nội dung định nghĩa.\n2. Hoàn trả nếu hợp đồng được giao kết, thực hiện; trừ trường hợp có thoả thuận khác.\n'
            '\nGhi chú: Đây là bản rút gọn.\nKhông phải điều luật.')
    provisions = structure_provisions(text,'a'*64)
    assert len(provisions) == 2
    assert provisions[1].clause == '2'
    assert 'trừ trường hợp có thoả thuận khác.' in provisions[1].content
    assert 'Ghi chú' not in provisions[1].content
    assert provisions[1].content == text[provisions[1].source_start:provisions[1].source_end].strip()


def test_provisions_keep_checklist_points_and_do_not_invent_articles():
    text = 'Điều 28. Hồ sơ\n1. Hồ sơ bao gồm:\na) Tờ khai;\nb) Chứng minh chỗ ở.\n2. Thủ tục nộp hồ sơ.'
    items = structure_provisions(text,'b'*64)
    assert items[0].points == ['a','b']
    assert 'a) Tờ khai' in items[0].content and 'b) Chứng minh' in items[0].content
    assert structure_provisions('Bản diễn giải không có điều luật.','c'*64) == []


def test_legal_namespace_cannot_inject_sql_or_touch_listings():
    with pytest.raises(ValueError): legal_sql('SELECT * FROM legal_chunks','public; DROP TABLE aggregated_listings')
    sql = str(legal_sql('SELECT * FROM legal_chunks JOIN legal_documents ON true','legal_v2'))
    assert 'legal_v2.legal_chunks' in sql and 'legal_v2.legal_documents' in sql
    assert str(legal_sql('SELECT * FROM aggregated_listings','legal_v2')) == 'SELECT * FROM aggregated_listings'


def test_operative_article_line_is_not_discarded():
    text='Điều 3. Thời gian áp dụng: từ ngày 10 tháng 5 năm 2025.'
    result=structure_provisions(text,'d'*64)
    assert len(result)==1 and result[0].content==text


def test_amended_clause_numbers_remain_inside_the_parent_amendment():
    text=('“Stray stamp quote\nĐiều 4. Sửa đổi\n'
          '1. Sửa Điều 30 như sau:\n“Điều 30. Thông báo\n1. Nội dung thứ nhất.\n2. Nội dung thứ hai.”.\n'
          '2. Bãi bỏ một quy định.\nĐiều 6. Hiệu lực\n1. Ngày áp dụng.')
    result=structure_provisions(text,'e'*64)
    assert [(p.article,p.clause) for p in result]==[('4','1'),('4','2'),('6','1')]
    assert '2. Nội dung thứ hai.' in result[0].content


def test_clause_preserves_statutory_introduction_separately():
    text='Điều 163. Hợp đồng về nhà ở\nHợp đồng phải lập thành văn bản bao gồm:\n1. Tên các bên;\n2. Thời hạn.'
    result=structure_provisions(text,'f'*64)
    assert result[1].clause=='1'
    assert result[1].article_context=='Hợp đồng phải lập thành văn bản bao gồm:'
    assert result[1].content=='1. Tên các bên;'


def test_separate_verifier_never_generates_the_answer_and_records_fallback():
    from app.room_service.chatbot.agents import QwenAnswerAgent
    from app.room_service.chatbot.providers import EvidenceIssues
    class Local:
        providers=[]
        def generate(self,*args,**kwargs): return 'local answer'
        def check_legal_evidence(self,*args,**kwargs): return EvidenceIssues(['local issue'])
    class Verifier:
        model='gemini-test'
        def check_legal_evidence(self,*args,**kwargs): return []
    agent=QwenAnswerAgent(Local(),Verifier())
    assert agent.generate('question',[])=='local answer'
    result=agent.check_legal_evidence('question','answer',[])
    assert not result and result.trace['provider']=='gemini'
    class Unavailable:
        model='gemini-test'
        def check_legal_evidence(self,*args,**kwargs): raise RuntimeError('HTTP 429')
    fallback=QwenAnswerAgent(Local(),Unavailable()).check_legal_evidence('question','answer',[])
    assert fallback==['local issue']
    assert fallback.trace['provider']=='qwen_and_rules' and fallback.trace['http_status']==429
    assert fallback.degraded_reasons


def test_gemini_verification_scopes_each_claim_to_its_own_citations(monkeypatch):
    from app.room_service.chatbot.providers import GeminiGenerator
    client=GeminiGenerator('test','gemini-test')
    def request(prompt,schema):
        payload=json.JSONDecoder().raw_decode(prompt[prompt.index('{"QUESTION"'):])[0]
        assert [s['rank'] for s in payload['CLAIMS'][0]['cited_sources']]==[1]
        assert [s['rank'] for s in payload['CLAIMS'][1]['cited_sources']]==[2]
        assert 'unused evidence' not in prompt
        return json.dumps({'supported':True,'issues':[]}),{}
    monkeypatch.setattr(client,'request_json',request)
    try:
        assert client.check_legal_evidence('question','Claim one [1]. Claim two [2].',[
            {'rank':1,'content':'evidence one'},{'rank':2,'content':'evidence two'},
            {'rank':3,'content':'unused evidence'}])==[]
    finally:client.close()


def test_local_selection_copies_source_numbers_and_exceptions_without_paraphrase():
    from app.room_service.chatbot.source_selection import selection_candidates,render_selection
    rows=[{'rank':1,'title':'Nguồn thử','category':'housing_contract','heading':'Điều 1. Điều kiện | Khoản 2',
        'content':'2. Trả lại 17 đơn vị khi đã thực hiện hợp đồng, trừ trường hợp có thỏa thuận khác.','context_complete':True}]
    candidates=selection_candidates(rows)
    result=render_selection('Hoàn cọc theo hợp đồng thế nào?',rows,candidates,
        json.dumps({'selected_ids':[1],'insufficient':False}),'qwen-local','qwen-test')
    assert result.literal_source_answer and rows[0]['content'] in result.text
    assert '17 đơn vị' in result.text and '[1]' in result.text
    with pytest.raises(ValueError):render_selection('question',rows,candidates,
        json.dumps({'selected_ids':[999],'insufficient':False}),'qwen-local','qwen-test')
    with pytest.raises(ValueError):render_selection('question',rows,[dict(candidates[0],text='fabricated legal text')],
        json.dumps({'selected_ids':[1],'insufficient':False}),'qwen-local','qwen-test')


def test_source_selection_keeps_article_checklist_and_marks_fragments_incomplete():
    from app.room_service.chatbot.source_selection import selection_candidates,render_selection
    rows=[{'rank':1,'title':'Nguồn thử','category':'housing_contract','heading':'Điều 163. Hợp đồng về nhà ở',
        'content':'Hợp đồng phải lập thành văn bản.\n\n1. Tên các bên.\n\n2. Thời hạn và giá.','context_complete':False}]
    candidates=selection_candidates(rows)
    assert len(candidates)==1 and candidates[0]['text']==rows[0]['content']
    result=render_selection('Nội dung hợp đồng thuê trọ?',rows,candidates,
        json.dumps({'selected_ids':[1],'insufficient':False}),'qwen-local','qwen-test')
    assert 'Chưa đủ căn cứ' in result.text


def test_clause_checklist_keeps_every_point_with_its_introduction():
    from app.room_service.chatbot.source_selection import selection_candidates
    content='1. Phải bảo đảm các điều kiện:\n\na) Điều kiện về điện.\n\nb) Điều kiện về bếp.\n\nc) Lối thoát nạn.'
    rows=[{'rank':1,'title':'Nguồn thử','category':'fire_safety','heading':'Điều 1 | Khoản 1','content':content}]
    candidates=selection_candidates(rows)
    assert len(candidates)==1 and candidates[0]['text']==content


def test_missing_deposit_facet_is_not_marked_complete():
    from app.room_service.chatbot.source_selection import selection_candidates,render_selection
    rows=[{'rank':1,'title':'Nguồn thử','category':'housing_contract','heading':'Điều kiện hợp đồng',
           'content':'Các bên thỏa thuận giá thuê, thời hạn và phương thức thanh toán.'}]
    result=render_selection('Hợp đồng có cần ghi rõ tiền cọc, tiền thuê và ngày thanh toán?',rows,selection_candidates(rows),
        json.dumps({'selected_ids':[1],'insufficient':False}),'qwen-local','qwen-test')
    assert 'Chưa đủ căn cứ' in result.text


def test_selected_source_keeps_its_commencement_conditions():
    from app.room_service.chatbot.source_selection import selection_candidates,render_selection
    rows=[{'rank':1,'title':'Nguồn thử','source_path':'same','category':'electricity','heading':'Điều kiện thuê nhà',
           'content':'Người thuê nhà được tính định mức theo các điều kiện trong nguồn.'},
          {'rank':2,'title':'Nguồn thử','source_path':'same','category':'electricity','heading':'Hiệu lực, phạm vi mức phạt và điều khoản chuyển tiếp',
           'content':'Quy định này có hiệu lực khi điều kiện chuyển tiếp trong nguồn được đáp ứng.'}]
    result=render_selection('Người thuê được tính tiền điện thế nào?',rows,selection_candidates(rows),
        json.dumps({'selected_ids':[1],'insufficient':False}),'qwen-local','qwen-test')
    assert rows[1]['content'] in result.text and '[2]' in result.text


def test_local_selector_retries_an_omitted_deposit_once_then_copies_sources():
    import httpx
    from app.room_service.chatbot.providers import OllamaQwenGenerator
    calls=[]
    def handler(request):
        payload=json.loads(request.content);calls.append(payload)
        ids=[2] if len(calls)==1 else [1,2]
        return httpx.Response(200,json={'message':{'content':json.dumps({'selected_ids':ids,'insufficient':False})}})
    rows=[{'rank':1,'title':'Nguồn thử','category':'housing_contract','heading':'Đặt cọc','content':'Các bên thỏa thuận việc đặt cọc bảo đảm hợp đồng.'},
          {'rank':2,'title':'Nguồn thử','category':'housing_contract','heading':'Thanh toán','content':'Các bên thỏa thuận giá thuê và thời hạn thanh toán.'}]
    generator=OllamaQwenGenerator('http://ollama.test','qwen-test',legal_answer_mode='source_select',transport=httpx.MockTransport(handler))
    try:
        result=generator.generate('Hợp đồng cần ghi rõ tiền cọc và thanh toán không?',rows,context_kind='legal')
        assert len(calls)==2 and 'tiền cọc' in calls[1]['messages'][1]['content']
        assert all(row['content'] in result.text for row in rows)
        assert result.literal_source_answer
    finally:generator.close()


def test_gemini_verification_scopes_each_claim_to_its_own_citations(monkeypatch):
    from app.room_service.chatbot.providers import GeminiGenerator
    client=GeminiGenerator('test','gemini-test')
    def request(prompt,schema):
        payload=json.JSONDecoder().raw_decode(prompt[prompt.index('{"QUESTION"'):])[0]
        assert [s['rank'] for s in payload['CLAIMS'][0]['cited_sources']]==[1]
        assert [s['rank'] for s in payload['CLAIMS'][1]['cited_sources']]==[2]
        assert 'unused evidence' not in prompt
        return json.dumps({'supported':True,'issues':[]}),{}
    monkeypatch.setattr(client,'request_json',request)
    try:
        assert client.check_legal_evidence('question','Claim one [1]. Claim two [2].',[
            {'rank':1,'content':'evidence one'},{'rank':2,'content':'evidence two'},
            {'rank':3,'content':'unused evidence'}])==[]
    finally:client.close()

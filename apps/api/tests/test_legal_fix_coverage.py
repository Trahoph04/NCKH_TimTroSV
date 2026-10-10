import json
from app.room_service.chatbot.evidence_units import requested_contract_facets,whole_supplementary_units,scope_issues
from app.room_service.chatbot.legal_retrieval import diversified_legal_rows
from app.room_service.legal_knowledge.provisions import structure_provisions


def test_original_question_reserves_all_contract_facets_after_reranking():
    question='Hợp đồng có cần ghi rõ tiền cọc, tiền thuê và ngày thanh toán không?'
    rows=[{'document_id':1,'chunk_id':i,'heading':h,'content':b,'category':'housing_contract'} for i,h,b in [
        (1,'Nội dung hợp đồng','Phương thức thanh toán.'),(2,'Giá thuê','Giá thuê do thỏa thuận.'),
        (3,'Điều 328. Đặt cọc','Đặt cọc bảo đảm giao kết hợp đồng.')]]
    assert requested_contract_facets(question)=={'deposit','rent','payment'}
    assert {r['chunk_id'] for r in diversified_legal_rows(question,rows,3)}=={1,2,3}


def test_numbered_footnote_does_not_merge_clause_three_into_two():
    source='Điều 146. Tiếp nhận\n2. Nội dung khoản hai.\n3.[74] Nội dung khoản ba.\n4. Khoản bốn.'
    units=structure_provisions(source,'a'*64)
    assert [p.clause for p in units]==['2','3','4']
    assert units[1].content=='3.[74] Nội dung khoản ba.'
    assert all(p.content==source[p.source_start:p.source_end].strip() for p in units)


def test_repeal_inventory_middle_fragment_never_becomes_commencement():
    parent='2. Bãi bỏ các thông tư sau đây:\na) Văn bản một;\nb) Văn bản hai.'
    rows=[{'document_id':1,'chunk_index':i,'heading':'Hiệu lực | Khoản 2','provision_id':'same',
        'content':text,'parent_content':parent} for i,text in enumerate(parent.splitlines())]
    rows.append({'document_id':1,'chunk_index':4,'heading':'Hiệu lực | Khoản 1','provision_id':'first',
        'content':'1. Áp dụng khi có sự kiện.','parent_content':'1. Áp dụng khi có sự kiện.'})
    chosen=whole_supplementary_units(rows)
    assert len(chosen)==1 and chosen[0]['content']=='1. Áp dụng khi có sự kiện.'


def test_tenant_broker_fee_does_not_use_employee_compensation():
    parts=[{'category':'real_estate_brokerage','text':'Cá nhân được hưởng thù lao từ doanh nghiệp kinh doanh dịch vụ môi giới.'}]
    assert scope_issues('Khoản phí môi giới người thuê trả nên được ghi ra sao?',parts)


def test_notice_to_electricity_seller_is_not_notice_to_tenant():
    parts=[{'category':'electricity','text':'Khi số người thuê thay đổi, chủ nhà thông báo cho bên bán điện để điều chỉnh định mức. Sản lượng điện được đo tại công tơ.'}]
    assert scope_issues('Chủ trọ có phải thông báo cách tính tiền điện và số điện đã sử dụng không?',parts)


def test_public_guidance_is_not_presented_as_a_statutory_obligation():
    from app.room_service.chatbot.source_selection import selection_candidates,render_selection
    contexts=[{'rank':1,'title':'Hướng dẫn Cần Thơ','heading':'Hướng dẫn công khai',
        'category':'electricity','source_id':'electricity-cantho-guidance',
        'content':'Đoàn kiểm tra lưu ý công khai cách tính cho người thuê và ghi chỉ số công tơ.'}]
    result=render_selection('Chủ trọ có phải thông báo cách tính tiền điện không?',contexts,
        selection_candidates(contexts),' {"selected_ids":[1],"insufficient":false}', 'qwen-local','model')
    assert any('Chưa đủ căn cứ để kết luận nghĩa vụ thông báo bắt buộc' in notice
               for notice in result.evidence_limitations)
    assert 'Chưa đủ căn cứ' in result.text


def test_web_provenance_is_accepted_by_public_response_schema():
    from app.room_service.chatbot.schemas import ChatSource
    source=ChatSource(kind='legal_document',rank=1,similarity_score=.9,title='Hướng dẫn',
        source='Trang thông tin Cần Thơ',page_kind='web_excerpt',source_url='https://btgdv.cantho.gov.vn/')
    assert source.model_dump(mode='json')['page_kind']=='web_excerpt'


def test_reporting_evidence_is_reserved_over_internal_authority_notice():
    from app.room_service.chatbot.legal_retrieval import rerank_legal
    question='Nếu nhiều sinh viên bị nhận cọc rồi cắt liên lạc, chúng tôi nên cung cấp thông tin gì cho cơ quan có thẩm quyền?'
    rows=[{'document_id':1,'chunk_id':1,'category':'criminal_law','heading':'Điều 146. Thủ tục tiếp nhận | Khoản 5',
        'content':'Cơ quan điều tra thông báo bằng văn bản cho Viện kiểm sát trong thời hạn tiếp nhận.', 'similarity_score':.9},
        {'document_id':2,'chunk_id':2,'category':'criminal_law','heading':'Khuyến cáo cơ quan Công an',
        'content':'Nạn nhân cần lưu giữ tài liệu, tin nhắn, chứng từ chuyển tiền và trình báo Công an.', 'similarity_score':.2}]
    assert diversified_legal_rows(question,rerank_legal(question,rows),1)[0]['chunk_id']==2


def test_qwen_retry_requires_evidence_for_person_reporting():
    from app.room_service.chatbot.source_selection import missing_selection_facets
    question='Tôi đã chuyển cọc cho tin giả mạo, nên lưu lại bằng chứng gì và trình báo ở đâu?'
    candidates=[{'id':1,'category':'criminal_law','text':'Cơ quan điều tra thông báo Viện kiểm sát.'},
        {'id':2,'category':'criminal_law','text':'Lưu giữ tin nhắn và chứng từ chuyển tiền, trình báo Công an.'}]
    assert 'bằng chứng người trình báo cần lưu/cung cấp' in missing_selection_facets(question,candidates,
        '{"selected_ids":[1],"insufficient":false}')

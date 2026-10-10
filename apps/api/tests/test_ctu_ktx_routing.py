import pytest

from app.room_service.chatbot.parser import parse_query
from app.room_service.chatbot.topics import question_categories
from app.room_service.chatbot.legal_retrieval import rental_electricity_question, rerank_legal


@pytest.mark.parametrize('question', [
    'KTX CTU thu tiền điện nước như thế nào?',
    'Kí túc xá có được nấu ăn không?',
    'Ký túc xá có wifi và chỗ gửi xe không?',
    'Tân sinh viên đăng ký KTX CTU như thế nào?',
])
def test_dormitory_operational_questions_use_ctu_sources_first(question):
    assert question_categories(question)[0] == 'student_housing'
    assert parse_query(question).intent == 'legal_question'


def test_private_rental_question_does_not_use_ctu_dormitory_sources():
    categories = question_categories('Chủ trọ thu tiền điện nước như thế nào?')
    assert 'student_housing' not in categories
    assert categories[0] == 'electricity'


@pytest.mark.parametrize('name', ['KTX', 'ký túc xá', 'kí túc xá'])
def test_dormitory_aliases_keep_electricity_and_collective_residence_evidence(name):
    query = f'{name} CTU thu tiền điện nước như thế nào?'
    assert not rental_electricity_question(query)
    row = dict(chunk_id=1, document_id=1, category='student_housing', heading='Thông tin KTX',
               similarity_score=.9, content='Ký túc xá: điện nước phòng nộp hàng tháng theo thực tế sử dụng.')
    assert rerank_legal(query, [dict(row)])
    residence = dict(row, category='residence', content='Sinh viên ở ký túc xá được đơn vị quản lý lập danh sách đăng ký tạm trú.')
    assert rerank_legal(f'{name} đăng ký tạm trú thế nào?', [residence])

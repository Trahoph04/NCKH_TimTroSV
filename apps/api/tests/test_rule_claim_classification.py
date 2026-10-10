from app.room_service.chatbot.legal_retrieval import evidence_issues,_clipped_condition


def checked(text,kind,content):
    row=dict(rank=1,heading='Hướng dẫn',content=content)
    claim=dict(claim_id='summary',kind=kind,rendered=text)
    return evidence_issues(text,[row],'',claim_records=(claim,))


def test_residence_or_storage_is_not_an_unfinished_exception():
    assert not _clipped_condition('Từ 30 ngày trở lên thì phải thực hiện đăng ký tạm trú.')
    assert not _clipped_condition('Dữ liệu được lưu trữ.')
    assert not _clipped_condition('Phai dang ky tam tru.')
    assert _clipped_condition('Phải thực hiện, trừ...')
    assert _clipped_condition('Phải thực hiện, trừ trường hợp...')
    assert _clipped_condition('Phải thực hiện theo quy...')


def test_source_guided_data_entry_requirement_is_not_a_legal_obligation():
    content='Hướng dẫn tra cứu hóa đơn. Bước 1: Truy cập website. Bước 2: Nhập IDKH và Mã xác nhận trên biên nhận thanh toán.'
    answer='Quy trình tra cứu yêu cầu phải có sẵn thông tin IDKH và Mã xác nhận trên biên nhận thanh toán [1].'
    assert not checked(answer,'source_limit',content)
    assert checked('Theo pháp luật, chủ trọ bắt buộc phải cung cấp IDKH để tra cứu hóa đơn [1].','procedure',content)
    assert checked('Để tra cứu phải nhập IDKH và mật khẩu ngân hàng [1].','procedure',content)


def test_negated_channel_classification_is_not_the_word_must():
    content='Gọi 114 để báo cháy và cứu nạn trong tình huống khẩn cấp.'
    answer='114 là số khẩn cấp báo cháy, không phải đường dây xử lý tranh chấp thuê trọ [1].'
    assert not checked(answer,'source_limit',content)
    assert checked(answer[:-4]+', nhưng chủ trọ phải hoàn trả toàn bộ tiền cọc [1].','source_limit',content)

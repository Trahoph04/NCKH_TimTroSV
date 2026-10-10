"""Legal vocabulary, transparent reranking and conservative evidence checks.

These rules improve recall; they never supply a legal answer or a tariff.
"""
from __future__ import annotations

import re
import unicodedata

from .providers import normalize_text
from ..legal_knowledge.quality import usable_legal_text
from .topics import question_categories, required_evidence_categories, TOPICS, has_phrase, user_listing_check_question

LEGAL_STOP_WORDS = {"toi", "minh", "giup", "xin", "hoi", "the", "nao", "sao", "la",
                    "va", "cua", "theo", "quy", "dinh", "duoc", "co", "khong", "ve"}


def legal_tokens(value: str) -> list[str]:
    return [word for word in re.findall(r"[a-z0-9]+", normalize_text(value))
            if len(word) > 1 and word not in LEGAL_STOP_WORDS]


def electricity_question(query: str) -> bool:
    value = normalize_text(query)
    return any(term in value for term in ("tien dien", "gia dien", "thu dien", "tinh dien", "kwh", "dinh muc dien"))


def tariff_question(query: str) -> bool:
    """Hỏi ĐƠN GIÁ theo bậc/biểu giá ("giá điện bậc 1 bao nhiêu đồng/kWh") — khác hẳn "chủ trọ được thu tiền điện thế nào".

    Trước 08/10 cả hai đều bị coi là câu hỏi tiền điện của người thuê nhà ⇒ chỉ giữ đoạn có "chủ nhà/thuê nhà" và bảng giá của
    Quyết định 1279/QĐ-BCT (đã nạp sẵn) bị loại, chatbot trả lời "nguồn chưa có mức giá" dù nguồn có.
    """
    value = normalize_text(query)
    # Câu nhắc chủ trọ/chủ nhà là câu hỏi "chủ trọ thu thế nào/có đúng không" (vd. "chủ trọ thu 4.000 đồng/kWh có đúng không?"),
    # dù có chữ đồng/kWh — vẫn đi nhánh tiền điện của người thuê nhà
    if re.search(r"\b(?:chu tro|chu nha|cho thue)\b", value):
        return False
    return electricity_question(query) and bool(re.search(
        r"\bbac\s*(?:thang\s*)?\d\b|\bbac thang\b|\bbieu gia\b|\bdong (?:mot|moi|tren)\s*kwh\b|\bdong\s*kwh\b", value))


def fine_question(query: str) -> bool:
    """Hỏi MỨC PHẠT/xử phạt hành chính. Hẹp hơn biến `penalty` trong rerank_legal (cũng bật vì 'xử lý', 'hoàn trả')."""
    return bool(re.search(r"\b(?:muc phat|xu phat|bi phat|phat bao nhieu|phat tien|phat hanh chinh|bi xu ly hanh chinh)\b",
                          normalize_text(query)))


def rental_electricity_question(query: str) -> bool:
    value = normalize_text(query)
    return (electricity_question(query) and 'student_housing' not in question_categories(query)
            and not tariff_question(query)
            and not any(term in value for term in ("trom cap", "hanh lang", "duong day")))


def water_invoice_lookup_question(query: str) -> bool:
    value = normalize_text(query)
    return ('nuoc' in value and any(term in value for term in ('tra cuu', 'doi chieu', 'ma khach hang', 'danh bo'))
            and not any(term in value for term in ('khieu nai', 'tranh chap', 'thu cao', 'thu sai', 'hoa giai', 'khong dong y')))


def expand_legal_query(query: str) -> str:
    value = normalize_text(query)
    additions: list[str] = []
    if 'nuoc' in value and any(t in value for t in ('dau nguoi', 'dung chung', 'phan chia', 'khoan')):
        additions.append('nguyên tắc tự do tự nguyện thỏa thuận nội dung hợp đồng giá phương thức thanh toán quyền người tiêu dùng hóa đơn chứng từ tiền nước')
    if 'tien dien' in value and any(t in value for t in ('thong bao', 'cach tinh', 'so dien')):
        additions.append('công khai cách tính hóa đơn chỉ số đo đếm quyền người tiêu dùng thông tin giao dịch')
    if 'tam tru' in value and 'cung cap' in value and 'trach nhiem' in value:
        additions.append('chủ hộ tạo điều kiện hướng dẫn thành viên nghĩa vụ công dân cung cấp đầy đủ chính xác thông tin khai thác cơ sở dữ liệu chỗ ở hợp pháp văn bản cho thuê không phải công chứng')
    if 'thoat nan' in value and any(t in value for t in ('khoa', 'chan')):
        additions.append('chủ nhà trọ lối thoát thông thoáng không cản trở báo cháy 114 kẹt trong phòng')
    if 'can cuoc' in value and any(t in value for t in ('luu', 'su dung')):
        additions.append('nguyên tắc bảo vệ dữ liệu thời gian lưu trữ kỹ thuật cung cấp dữ liệu cá nhân bên khác đồng ý ngoại lệ')
    from .evidence_units import human_reporting_question
    if 'criminal_law' in question_categories(query) and human_reporting_question(query):
        additions.append('khuyến cáo lưu giữ tài liệu tin nhắn chứng từ chuyển tiền lịch sử giao dịch trình báo cơ quan Công an tiếp nhận tố giác')
    if has_phrase(value, "hop dong") and any(term in value for term in ("truoc khi ky", "dieu khoan", "ghi ro")):
        additions.append("hợp đồng về nhà ở nội dung của hợp đồng giá thuê thời hạn phương thức thanh toán quyền nghĩa vụ")
    if any(term in value for term in ("tam tru", "thu tuc cu tru", "dang ky cu tru")) and not any(term in value for term in ("phat", "vi pham")):
        additions.append("đăng ký tạm trú điều kiện hồ sơ tờ khai chỗ ở hợp pháp tiếp nhận đăng ký")
        if 'cung cap' in value and 'trach nhiem' in value:
            additions.append('nghĩa vụ công dân cung cấp đầy đủ chính xác thông tin giấy tờ tài liệu về cư trú')
    if 'cu tru' in value and any(term in value for term in ('chuyen sang', 'chuyen phong', 'thay doi cho o')):
        additions.append('thay đổi chỗ ở đăng ký tạm trú mới')
    if any(term in value for term in ('phong chay', 'pccc', 'chay no')) and any(term in value for term in ('xem phong', 'dieu kien', 'nhieu phong')):
        additions.append('phòng cháy đối với nhà ở thiết bị điện bếp đun nấu phương tiện chữa cháy lối thoát nạn')
        if 'nhieu phong' in value:
            additions.append('danh mục cơ sở dịch vụ lưu trú nhà ở tập thể nhà đa năng nhà hỗn hợp')
    if any(term in value for term in ("thong tin ca nhan", "du lieu ca nhan", "anh can cuoc", "so dien thoai", "anh giay to")):
        additions.append("bảo vệ dữ liệu cá nhân quyền chủ thể sự đồng ý cung cấp tiết lộ công khai xử lý dữ liệu")
        if has_phrase(value, 'hop dong'):
            additions.append('hợp đồng về nhà ở họ tên cá nhân địa chỉ các bên nội dung hợp đồng')
        if any(has_phrase(value, phrase) for phrase in ('cu tru', 'tam tru')):
            additions.append('đăng ký tạm trú hồ sơ tờ khai thay đổi thông tin cư trú chỗ ở hợp pháp')
    if any(term in value for term in ("dau hieu rui ro", "dau hieu lua dao", "khong cho xem phong")):
        additions.append("thủ đoạn gian dối chiếm đoạt tài sản lừa đảo điều kiện giao dịch dân sự đặt cọc")
    if any(term in value for term in ("chu tro", "chu nha")):
        additions.append("người cho thuê nhà")
    if any(term in value for term in ("o ghep", "o chung", "sinh vien")):
        additions.append("người thuê nhà định mức số người sử dụng điện" if electricity_question(query)
                         else "người thuê nhà")
    if rental_electricity_question(query):
        additions.append("thu tiền điện người thuê nhà giá bán lẻ điện sinh hoạt hóa đơn")
    if 'moi gioi' in value and any(t in value for t in ('phi','giay to','thoa thuan','khac voi','thong tin')):
        additions.append('hợp đồng dịch vụ trả tiền dịch vụ giá dịch vụ quyền nghĩa vụ bên sử dụng dịch vụ')
        if any(t in value for t in ('khac voi','sai','khong dung','khong dat')):
            additions.append('chất lượng dịch vụ không đạt như thỏa thuận giảm tiền dịch vụ bồi thường thiệt hại chấm dứt dịch vụ')
    if 'nuoc' in value and 'can tho' in value:
        additions.append('Quy định giá nước sạch sinh hoạt trên địa bàn thành phố Cần Thơ giá tiêu thụ nước')
    if water_invoice_lookup_question(query):
        additions.append('tra cứu hóa đơn IDKH mã xác nhận giấy báo biên nhận')
    if user_listing_check_question(query):
        additions.append('kiểm tra tài khoản xác thực số điện thoại địa chỉ giá thấp đáng ngờ hình ảnh tương tự Google Ống kính')
    from .evidence_units import platform_reporting_question
    if platform_reporting_question(query):
        additions.append('báo cáo tin đăng bằng chứng hình ảnh trao đổi vi phạm gỡ bỏ thông tin')
    if any(t in value for t in ('chia se sai','xu ly nhu the nao','rut lai')) and 'privacy_data' in question_categories(query):
        additions.append('thực hiện quyền chủ thể dữ liệu cá nhân yêu cầu rút lại hạn chế xử lý xóa dữ liệu thủ tục thời hạn')
    if any(term in value for term in ("phat", "xu ly", "thu thua", "hoan tra")):
        additions.append("xử phạt vi phạm hoàn trả số tiền thu thừa khắc phục hậu quả")
    return query + (". " + ". ".join(additions) if additions else "")


def rental_evidence(content: str) -> bool:
    value = normalize_text(content)
    return any(term in value for term in ("tien dien", "gia dien", "gia ban le dien", "su dung dien", "mua dien")) and any(term in value for term in
                                   ("thue nha", "nha cho thue", "chu nha", "sinh vien"))


def rerank_legal(query: str, rows: list[dict], limit: int = 30) -> list[dict]:
    rental = rental_electricity_question(query)
    question = normalize_text(query)
    penalty = any(word in question for word in ("phat", "xu ly", "thu thua", "hoan tra"))
    categories = question_categories(query)
    private_rental = ("housing_contract" in categories and any(has_phrase(question, term) for term in ("thue", "tro", "phong"))
                      and not any(has_phrase(question, term) for term in ("mua ban", "thue mua", "tai san cong", "nha cong vu")))
    for row in rows:
        value = normalize_text(row["content"])
        base = float(row.get("similarity_score", 0))
        if water_invoice_lookup_question(query) and row.get('category')=='water_cantho' and any(term in value for term in ('xem xet lai so tien nuoc', 'hoa giai')):
            row['similarity_score'] = 0.0
            continue
        if rental and 'ky tuc xa' in value and 'student_housing' not in categories and 'nguoi thue nha' not in value:
            row['similarity_score']=0.0
            continue
        if row.get('category') == 'residence' and 'residence' in categories:
            collective_query = ('student_housing' in categories or any(term in question for term in ('ky tuc xa', 'khu tap trung', 'co so tap trung', 'dang ky tap the')))
            collective_rule = 'ky tuc xa' in value or ('danh sach' in value and 'don vi quan ly' in value)
            if collective_rule and not collective_query:
                row['similarity_score'] = 0.0
                continue
        if private_rental and row.get("category") == "housing_contract":
            scope_heading = normalize_text(str(row.get('heading') or ''))
            specific_other = any(has_phrase(value, term) for term in ("mua ban", "thue mua", "tai san cong", "nha cong vu"))
            ordinary_rental = re.search(r"\bthue\b(?!\s+mua)", value)
            general_contract = bool(re.search(r'\bdieu\s+\d+[a-z]?[.]?\s+hop dong ve nha o(?:\s+khoan \d+)?$', scope_heading))
            if re.search(r'^(?:\d+[.]\s*)?(?:doi voi|truong hop) (?:hop dong )?(?:mua ban|thue mua|cho thue mua)',value):
                general_contract = False
            if specific_other and not ordinary_rental and not general_contract:
                row["similarity_score"] = 0.0
                continue
        if row.get("category") and categories:
            if row["category"] not in categories:
                row["similarity_score"] = 0.0
                continue
            heading = normalize_text(str(row.get("heading") or ""))
            from .evidence_units import human_reporting_question, reporting_evidence_row
            if row['category']=='criminal_law' and human_reporting_question(query):
                if reporting_evidence_row(row):base += 1.25
                if 'dieu 146.' in heading and 'khoan 1' in heading:base += .9
                if 'dieu 145.' in heading and 'khoan 2' in heading:base += .6
                if 'kien nghi khoi to' in value and 'co quan nha nuoc' in value and 'ca nhan' not in value:base -= 1.1
                if 'thong bao bang van ban' in value and 'vien kiem sat' in value:base -= 1.0
            if row.get('source_id')=='electricity-cantho-guidance':
                if any(t in question for t in ('thong bao','so dien da su dung','cach tinh','kiem tra','hoa don','doi chieu')):
                    base += 1.2
                else:
                    base -= .7
            if str(row.get('source_id') or '').startswith(('water-cantho-invoice-', 'water-cantho2-invoice-')):
                if any(t in question for t in ('tra cuu', 'hoa don', 'doi chieu', 'ma khach hang', 'danh bo')):
                    base += 1.8
                else:
                    base -= 1.5
            meaningful = set(legal_tokens(query)) - {"sinh", "vien", "nguoi", "thue", "nha", "tro", "phong", "can", "nen", "nhung", "gi"}
            overlap = len(meaningful & set(legal_tokens(value))) / max(1, len(meaningful))
            heading_overlap = len(meaningful & set(legal_tokens(heading))) / max(1, len(meaningful))
            primary = row["category"] == categories[0]
            direct = any(has_phrase(value + " " + heading, p) for p in TOPICS.get(categories[0], ()))
            own_evidence = any(has_phrase(value + " " + heading, p) for p in TOPICS.get(row["category"], ()))
            contract_identity = (row['category'] == 'housing_contract' and 'privacy_data' in categories
                                 and 'hop dong ve nha o' in heading
                                 and any(term in value for term in ('ho va ten', 'ho ten', 'dia chi')))
            rental_authority = (row['category'] == 'housing_contract' and 'quyen cho thue' in question
                                and any(term in heading for term in ('dieu kien', 'ben tham gia'))
                                and any(term in value for term in ('chu so huu', 'uy quyen', 'cho thue')))
            from .evidence_units import listing_check_facets, practical_facets
            checking_guidance = user_listing_check_question(query) and bool(listing_check_facets(row))
            practical = bool(practical_facets(query, row))
            if not primary and not direct and not contract_identity and not rental_authority and not checking_guidance and not practical and not (own_evidence and overlap >= 0.2):
                row["similarity_score"] = 0.0
                continue
            base = 0.5 * base + 0.3 * overlap + (0.18 if primary else 0.1)
            base += 0.12 * heading_overlap
            if practical:
                base += .6
            if user_listing_check_question(query):
                if any(has_phrase(value, p) for p in ('kiem tra', 'xac minh', 'canh giac', 'tim hieu')):
                    base += .8
                if any(has_phrase(heading, p) for p in ('trach nhiem cua chu quan', 'trach nhiem cua nguoi ban')):
                    base -= .7
            elif 'ecommerce_platform' in categories and 'trach nhiem' in question:
                general_operator = 'trach nhiem cua chu quan nen tang' in heading
                if general_operator and 'khoan 1' in heading:
                    base += 1.0
                if general_operator and 'co chuc nang dat hang truc tuyen' in value:
                    if 'dat hang' not in question:
                        base -= .4
                if general_operator and 'xac thuc' in value and 'kiem duyet' in value:
                    base += .6
            if "housing_contract" in categories and any(term in question for term in ("truoc khi ky", "ghi ro")):
                if any(term in heading for term in ("noi dung cua hop dong", "hop dong ve nha o")):
                    base += 0.25
            if row['category'] == 'housing_contract':
                if 'coc' in question and 'dat coc' in heading and any(term in question for term in ('ghi ro', 'ngay thanh toan', 'ghi trong')):
                    base += .8 if 'bao dam giao ket' in value or 'bao dam giao ket' in normalize_text(str(row.get('parent_content') or '')) else .1
                if any(term in question for term in ('tien thue', 'gia thue')) and 'hop dong ve nha o' in heading and 'gia giao dich' in value:
                    base += .45
                if 'tang gia thue' in question and any(term in heading for term in ('sua doi hop dong', 'gia thue')):
                    base += .5
                if 'tien coc' in question and not any(term in question for term in ('huy hop dong','don phuong','vi pham')):
                    if 'huy bo hop dong' in heading:
                        base -= .6
            if "residence" in categories and not penalty and ("xu phat" in value or "phat tien" in value):
                base -= 0.25
            if "privacy_data" in categories and any(term in question for term in ("cong khai", "chia se", "luu", "su dung", "ca nhan")):
                if 'cong khai' in question and 'cong khai du lieu ca nhan' in heading:
                    base += 1.0
                if any(t in question for t in ('chia se sai','xu ly nhu the nao')) and 'thuc hien quyen cua chu the' in heading:
                    base += 1.0
                if any(term in heading + " " + value for term in ("quyen cua chu the", "su dong y", "hanh vi bi nghiem cam", "nguyen tac bao ve", "cung cap du lieu", "tiet lo du lieu")):
                    base += 0.3
                if "xuat nhap canh" in value:
                    base -= 0.55
                if row['category']=='privacy_data':
                    if 'tre em' in heading and not any(term in question for term in ('tre em','chua thanh nien','giam ho')):
                        base -= .65
                    if any(term in heading for term in ('tuyen dung','nguoi lao dong')) and not any(term in question for term in ('tuyen dung','lao dong','viec lam')):
                        base -= .65
                    if 'ghi am, ghi hinh tai noi cong cong' in heading and not any(term in question for term in ('camera','noi cong cong','ghi hinh')):
                        base -= .65
                    if 'nguyen tac bao ve' in heading and 'pham vi' in value and 'muc dich' in value:
                        base += .65
                    if any(term in heading for term in ('su dong y','thu thap, phan tich')):
                        if any(term in value for term in ('tru truong hop phap luat','tu nguyen','muc dich xu ly')):
                            base += .5
                    if any(term in question for term in ('cung cap','yeu cau','hop dong','thu thap','thong tin ca nhan')) and any(term in heading+' '+value for term in ('ngung xu ly','rut lai su dong y','han che xu ly')) and not any(term in question for term in ('ngung','xoa','rut lai','han che','chia se sai')):
                        base -= .5
                if "thong bao vi pham" in heading and not any(term in question for term in ("thong bao vi pham", "su co", "ro ri", "bi chia se")):
                    base -= 0.35
            if 'privacy_data' in categories and 'housing_contract' in categories and row['category'] == 'housing_contract':
                if 'hop dong ve nha o' in heading and any(term in value for term in ('ho va ten', 'ho ten', 'dia chi')):
                    base += .75
            if 'residence' in categories and row['category'] == 'residence' and any(term in question for term in ('giay to', 'thong tin', 'thu tuc', 'dang ky')):
                if 'dieu kien dang ky tam tru' in heading and 'thu tuc' in question:
                    base += .8
                if any(term in heading for term in ('dang ky tam tru', 'ho so', 'thu tuc')):
                    base += .3
                if any(term in question for term in ('giay to', 'thong tin', 'ho so')) and 'ho so' in heading:
                    base += .35
                    if any(term in value for term in ('to khai', 'giay to, tai lieu chung minh')):
                        base += .35
                if 'trach nhiem' in question and 'cung cap' in question and 'nghia vu' in heading and 'cung cap' in value:
                    base += .65
                if 'cung cap' in question and 'giay to' in question:
                    if 'van ban cho thue' in value and 'khong phai cong chung' in value:
                        base += 1.3
                    if 'khai thac' in value and 'khi co quan dang ky cu tru co yeu cau' in value:
                        base += 1.3
            if row['category']=='residence' and 'cu tru' in question and any(term in question for term in ('chuyen sang','chuyen phong','thay doi cho o')):
                if 'ho so dang ky tam tru' in value and 'noi tam tru moi' in value:
                    base += 1.25
                if 'xoa dang ky tam tru' in heading or ('sua doi' in heading and 'dieu 10. ho so, thu tuc xoa dang ky tam tru' in value):
                    base += .9
                if 'dieu chinh thong tin' in heading and 'ho tich' in value:
                    base -= .6
            if row['category'] == 'fire_safety':
                if 'nhieu phong' in question and 'phu luc i.' in heading and 'co so dich vu luu tru' in value:
                    base += 1.1
                if any(term in question for term in ('xem phong', 'dieu kien', 'nhieu phong')) and 'phong chay doi voi nha o' in heading:
                    base += .55
                    if 'ket hop' not in heading:
                        base += .25
                    if any(term in value for term in ('dieu kien an toan', 'dieu kien ve chua chay')):
                        base += .3
                if 'nhieu phong' in question and any(t in heading for t in ('phong chay doi voi co so','phong chay doi voi nha o')):
                    base += .5
                    if 'huong dan viec ket noi' in value and 'ket noi' not in question:
                        base -= .5
                if 'trach nhiem' in question and 'trach nhiem' in heading and any(term in value for term in ('nguoi thue', 'chu ho gia dinh')):
                    base += .45
            if row['category']=='criminal_law' and 'lua dao' in question and 'toi lua dao' in heading:
                if 'thu doan gian doi' in value and not any(term in question for term in ('muc phat','muc an','bao nhieu nam')):
                    base += .8
            if row['category']=='criminal_law' and any(t in question for t in ('co quan co tham quyen','trinh bao','to giac')):
                if any(t in heading for t in ('thu tuc tiep nhan to giac','trach nhiem tiep nhan','to giac, tin bao')):
                    base += .85
            if row['category'] in ('real_estate_brokerage','housing_contract') and 'moi gioi' in question and any(t in question for t in ('phi','giay to','thoa thuan','khac voi','thong tin')):
                if 'ca nhan moi gioi' in value and 'doanh nghiep' in value and 'khach hang' not in value:
                    base -= .9
                if any(t in heading for t in ('tra tien dich vu','hop dong dich vu','quyen cua ben su dung dich vu','noi dung cua hop dong')):
                    base += .85
                if 'tra tien dich vu' in heading:
                    base += .9 if 'khong dat' in value and 'giam tien dich vu' in value else -.65
                if 'quyen cua ben su dung dich vu' in heading and 'theo thoa thuan' in value:
                    base += .8
                if ('noi dung chinh cua hop dong' in heading and 'hop dong kinh doanh dich vu' in value
                        and all(t in value for t in ('phi dich vu','phuong thuc','thoi han thanh toan'))):
                    base += 1.2
            if row['category']=='criminal_law' and 'lien ket la' in question:
                if any(t in value for t in ('mat khau','otp','website gia mao','duong link la','thuc giuc')):
                    base += 1.1
            if row['category'] in ('criminal_law', 'ecommerce_platform') and 'khuyen cao' in value:
                if any(term in question for term in ('kiem tra', 'bang chung', 'cung cap thong tin', 'luu lai', 'lien ket la')):
                    base += .45
            if rental_authority:
                base += .35
                if any(term in value for term in ('chu so huu', 'uy quyen')):
                    base += .45
            preventive_risk = "criminal_law" in categories and any(term in question for term in ("truoc khi", "khong cho xem", "dau hieu rui ro"))
            if preventive_risk:
                if any(term in heading + " " + value for term in ("gian doi", "lua dao", "giao dich dan su", "chiem doat")):
                    base += 0.3
                if any(term in heading for term in ("tham quyen giai quyet", "trach nhiem tiep nhan", "kien nghi khoi to")):
                    base -= 0.4
            # Introductory editorial metadata identifies a source but is not
            # an operative legal clause answering a question about obligations.
            if not heading and any(term in value for term in ("ghi chu ngu canh", "ban trich tuyen nghien cuu")):
                row["similarity_score"] = 0.0
                continue
            if heading and any(has_phrase(heading, p) for p in TOPICS.get(categories[0], ())):
                base += 0.1
        from .evidence_units import practical_facets
        if rental and not practical_facets(query, row):
            if not rental_evidence(str(row.get("heading") or "") + " " + row["content"]):
                row["similarity_score"] = 0.0
                continue
            phrases = ("thu tien dien", "tien dien", "nguoi thue nha", "dinh muc", "hoa don")
            coverage = sum(phrase in value for phrase in phrases) / len(phrases)
            base = 0.45 * base + 0.35 + 0.2 * coverage
            if penalty and any(term in value for term in ("phat tien", "hoan tra", "thu thua")):
                base += 0.15
            elif not penalty and "vi pham" in normalize_text(str(row.get("heading") or "")):
                base -= 0.2
        # Hỏi mức phạt: điều khoản có "phạt tiền/cảnh cáo" phải đứng trước điều khoản chỉ nói về thủ tục (trước đây Luật Cư trú
        # Điều 27–29 thắng Nghị định xử phạt vì trùng nhiều từ "đăng ký tạm trú", và chatbot trích đoạn không liên quan)
        if fine_question(query) and any(term in value for term in ("phat tien", "phat canh cao")):
            base += 0.9
        # Hỏi đơn giá theo bậc: đoạn BẢNG GIÁ ("Bậc 1: Cho kWh từ 0 - 50 … 1.984") phải vào top nguồn — chỉ 5 nguồn được đưa cho mô
        # hình và bảng từng đứng thứ 6, nên mô hình "trung thực" trả lời nguồn không có giá dù kho có sẵn bảng giá QĐ 1279/QĐ-BCT
        # (normalize_text đã bỏ dấu ":" nên "Bậc 1: Cho kWh" thành "bac 1 cho kwh")
        if tariff_question(query) and re.search(r"\bbac \d cho kwh\b", value):
            base += 1.0
        row['_rerank_score'] = base
        row["similarity_score"] = round(min(1.0, base), 6)
    return sorted((row for row in rows if row["similarity_score"] > 0
                   and usable_legal_text(row["content"])),
                  key=lambda row: (-row.get('_rerank_score', row["similarity_score"]), row["chunk_id"]))[:limit]


def diversified_legal_rows(query: str, rows: list[dict], limit: int) -> list[dict]:
    """Reserve a relevant candidate for each explicit facet before extra matches."""
    categories = required_evidence_categories(query)
    reserved = []
    from .evidence_units import practical_facets
    # One high-ranked complete source for each distinct practical question facet.
    # Deduplication below prevents a whole article from consuming several slots.
    needed_facets = sorted(set().union(*(practical_facets(query, row) for row in rows)))
    for facet in needed_facets:
        candidate = next((row for row in rows if facet in practical_facets(query, row)), None)
        if candidate is not None:
            reserved.append(candidate)
    if user_listing_check_question(query):
        from .evidence_units import listing_check_facets
        for facet in ('account', 'image', 'contact', 'price'):
            candidate = next((r for r in rows if facet in listing_check_facets(r)), None)
            if candidate is not None:
                reserved.append(candidate)
    elif 'ecommerce_platform' in categories and 'trach nhiem' in normalize_text(query):
        # Start with duties for the general operator, then an authority request
        # if available. Do not begin an unspecified-platform answer with a
        # special-case clause about online ordering and returned goods.
        from .evidence_units import operator_facets
        for facet in ('moderation', 'identity', 'authority_data'):
            candidates = [r for r in rows if facet in operator_facets(r)]
            if facet == 'identity':
                # Prefer actual identity fields over a clause which only
                # points elsewhere for them. Conditions remain in the parent.
                candidates.sort(key=lambda r: not all(t in normalize_text(r.get('parent_content') or r['content'])
                                                       for t in ('ho va ten', 'so dinh danh')))
            candidate = next(iter(candidates), None)
            if candidate is not None:
                reserved.append(candidate)
    from .evidence_units import platform_reporting_question, report_proof_row
    if platform_reporting_question(query):
        for predicate in (
            lambda r: 'bao cao tin dang' in normalize_text(r['content']),
            lambda r: report_proof_row(r) and 'hinh anh' in normalize_text(r.get('parent_content') or r['content']),
            lambda r: '24 gio' in normalize_text(r.get('parent_content') or r['content'])
                and 'go bo' in normalize_text(r.get('parent_content') or r['content'])
                and 'co quan nha nuoc co tham quyen' in normalize_text(r.get('parent_content') or r['content']),
        ):
            candidate = next((r for r in rows if predicate(r)), None)
            if candidate is not None:
                reserved.append(candidate)
    from .evidence_units import requested_contract_facets, contract_facets, human_reporting_question, reporting_evidence_row
    if human_reporting_question(query):
        candidate=next((r for r in rows if reporting_evidence_row(r)),None)
        if candidate is not None:reserved.append(candidate)
    needed = requested_contract_facets(query)
    for facet in ('deposit','rent','payment'):
        if facet in needed:
            candidate = next((r for r in rows if facet in contract_facets(r)), None)
            if candidate is not None:
                reserved.append(candidate)
    if len(categories) > 1:
        for category in categories:
            candidate = next((row for row in rows if row.get('category') == category), None)
            if candidate is not None:
                reserved.append(candidate)
    unique = []
    seen = set()
    for row in reserved + rows:
        group = (row['document_id'], row.get('heading') or row['chunk_id'])
        if group not in seen:
            seen.add(group)
            unique.append(row)
    return unique[:limit]


def legal_completion_status(answer: str) -> str:
    """Report incomplete answers independently of provider or citation validity."""
    # A quoted statutory condition is evidence, not the assistant's abstention.
    visible = re.sub(r'“[^”]*”|"[^"\n]*"', '', answer, flags=re.S)
    # This fixed application notice describes provenance, not a missing answer
    # facet. Keep it visible to users, but do not conflate the two statuses.
    visible = visible.replace('Nguồn là bản Word/trích tuyển được cung cấp, chưa xác minh toàn bộ câu chữ với bản chính thức; không coi ghi chú biên tập là quy định pháp luật.', '')
    limitation = re.compile(r'\b(?:chua (?:tim thay|co (?:can cu|du lieu|thong tin|nguon)|du can cu|xac minh|ket luan|tong hop)|khong (?:du can cu|the ket luan))\b')
    if not limitation.search(normalize_text(visible)):
        return 'complete'
    supported = []
    # A citation after a multiline quotation supports its earlier lines too.
    if any(len(legal_tokens(m[1]))>=8 for m in re.finditer(r'“(.*?)”\s*\[\d+\]',answer,re.S)):
        return 'partial'
    for segment in re.split(r'\n+|(?<=[.!?])\s+', answer):
        norm = normalize_text(segment)
        if limitation.search(norm) or not re.search(r'\[\d+\]', segment):
            continue
        if any(term in norm for term in ('thong tin tham khao', 'mo nguon tham khao', 'kiem tra dieu kien', 'khong thay the tu van')):
            continue
        if len(legal_tokens(segment)) >= 8:
            supported.append(segment)
    return 'partial' if supported else 'insufficient'


def _clipped_condition(text):
    # Stripping accents conflates “trú” (residence) with “trừ” (except).
    raw=unicodedata.normalize('NFC',' '.join(text.split())).casefold()
    if re.search(r'\btrừ(?: trường(?: hợp)?)?[ .…]*$',raw): return True
    norm=normalize_text(text)
    if re.search(r'\b(?:theo quy|tru truong(?: hop)?)[ .…]*$',norm): return True
    return bool(re.search(r'\btru[ .…]*$',raw) and not re.search(r'\b(?:tam|cu|thuong|luu) tru[ .…]*$',norm))


def _citation_scope_issues(segment: str, cited: list[dict], claim_kind=None) -> list[str]:
    issues = []
    norm = normalize_text(segment)
    heading_articles = {n for row in cited for n in re.findall(r'Điều\s+(\d+)\b', str(row.get('heading') or ''), re.I)}
    claim_articles = set(re.findall(r'Điều\s+(\d+)\b', segment, re.I))
    if heading_articles and claim_articles - heading_articles:
        issues.append('Số điều được khẳng định không khớp điều khoản của nguồn trích dẫn.')
    heading_clauses = {n for row in cited for n in re.findall(r'Khoản\s+(\d+)\b', str(row.get('heading') or ''), re.I)}
    claim_clauses = set(re.findall(r'Khoản\s+(\d+)\b', segment, re.I))
    if heading_clauses and claim_clauses - heading_clauses:
        issues.append('Số khoản được khẳng định không khớp khoản của nguồn trích dẫn.')
    evidence = normalize_text(' '.join(str(row.get('heading') or '') + ' ' + row['content'] for row in cited))
    normative = re.search(r'\b(?:phai|bat buoc|co nghia vu|nghia vu cua|co trach nhiem|trach nhiem cua)\b', norm)
    if re.search(r'\bchi (?:duoc|co quyen|co the|phai|ap dung)\b',norm) and not re.search(r'\bchi\b',evidence):
        issues.append('Nguồn nêu một trường hợp cụ thể, chưa loại trừ các căn cứ khác; không tự kết luận chỉ được áp dụng trong trường hợp đó.')
    imperative_protection = ('nguyen tac bao ve du lieu ca nhan' in evidence
                             and 'thuc hien dong bo' in evidence and 'bien phap' in evidence)
    validity_conditions = 'dieu kien co hieu luc' in evidence and 'co hieu luc khi co du cac dieu kien' in evidence
    conditional_consent = ('dong y' in norm and 'khi duoc' in evidence and 'dong y' in evidence)
    # Data-entry prerequisites in an identified supplier guide are procedural,
    # not legal duties. A category label alone never permits a rights claim.
    guide_input = (claim_kind in ('procedure','source_limit')
        and 'huong dan' in evidence and re.search(r'\bbuoc [1-9]\b',evidence)
        and any(t in norm for t in ('tra cuu','quy trinh','huong dan'))
        and re.search(r'\bphai (?:co|nhap)\b.{0,80}\b(?:idkh|ma xac nhan|ma khach hang)\b',norm)
        and any(t in evidence for t in ('idkh','ma xac nhan','ma khach hang'))
        and not re.search(r'\b(?:phap luat|luat|theo quy dinh|bat buoc|nghia vu|trach nhiem|bi phat|chu tro|chu nha)\b',norm)
        and all(t not in norm or t in evidence for t in ('otp','mat khau','tai khoan ngan hang')))
    if normative and not (imperative_protection or validity_conditions or conditional_consent or guide_input) and not any(has_phrase(evidence, p) for p in ('phai', 'nghia vu', 'trach nhiem', 'bat buoc', 'khong duoc', 'nghiem cam', 'chi duoc')):
        issues.append('Nguồn mô tả nội dung/công việc chưa xác nhận nghĩa vụ được khẳng định.')
    if any(has_phrase(norm, p) for p in ('co quyen', 'duoc phep')) and not any(has_phrase(evidence, p) for p in ('quyen', 'duoc', 'cho phep')):
        issues.append('Nguồn được trích chưa xác nhận quyền hoặc sự cho phép được khẳng định.')
    tenant_obligation = (re.search(r'\b(?:nguoi thue|ben thue)\b[^,;]{0,60}\b(?:phai|bat buoc|co nghia vu|co trach nhiem)\b', norm)
                         or re.search(r'\b(?:nghia vu|trach nhiem) cua (?:nguoi thue|ben thue)\b', norm))
    if tenant_obligation:
        if any(has_phrase(evidence, p) for p in ('uy ban nhan dan', 'co quan cong an')) and not any(has_phrase(evidence, p) for p in ('nguoi thue', 'ben thue', 'nguoi su dung')):
            issues.append('Không chuyển trách nhiệm của cơ quan kiểm tra thành nghĩa vụ của người thuê.')
    if any(_clipped_condition(row['content']) for row in cited):
        issues.append('Nguồn trích dẫn bị cụt điều kiện hoặc ngoại lệ; chưa đủ để kết luận.')
    return issues


def evidence_issues(answer: str, chunks: list[dict], query: str, *, claim_records=()) -> list[str]:
    """Deterministic guard, not a claim of full semantic entailment verification."""
    issues = []
    normalized = normalize_text(answer)
    question = normalize_text(query)
    if ('nen tang' in question and 'trach nhiem' in question
            and any(t in question for t in ('thong tin nguoi', 'nguoi dang', 'nguoi ban', 'nguoi cho thue'))):
        from .evidence_units import operator_facets, OPERATOR_LABELS
        available = set().union(*(operator_facets(row) for row in chunks))
        expressed = operator_facets({'category': 'ecommerce_platform', 'content': answer})
        issues += ['Chưa trình bày nhóm trách nhiệm có trong nguồn đã chọn: ' + OPERATOR_LABELS[facet]
                   for facet in sorted(available - expressed)]
    if any(term in normalized for term in (
        "phap luat khong co quy dinh", "khong co quy dinh cu the", "khong co quy dinh ve",
        "khong co van ban nao", "luat khong quy dinh",
    )) or re.search(r"(?:phap luat|luat).{0,45}khong(?: co)? (?:quy dinh|neu)", normalized):
        issues.append("Không thể kết luận pháp luật không có quy định từ các đoạn truy xuất.")
    if rental_electricity_question(query) and not any(rental_evidence(row["content"]) for row in chunks):
        issues.append("Chưa tìm thấy nguồn trực tiếp về tiền điện của người thuê nhà.")
    evidence_text = normalize_text(" ".join(row["content"] for row in chunks))
    if rental_electricity_question(query):
        if any(term in normalized for term in ("phai bang", "phai dung bang")) and "khong duoc vuot qua" in evidence_text:
            issues.append("Giữ đúng giới hạn 'không được vượt quá'; không đổi thành 'phải bằng'.")
        if "lai suat" in normalized and "thoa thuan" not in normalized and "thoa thuan" in evidence_text:
            issues.append("Lãi suất hoàn trả phải giữ điều kiện do hai bên thỏa thuận trong hợp đồng.")
        if "khong ke khai hoac" in normalized or "khong ke khai du hoac" in normalized:
            issues.append("Không đổi điều kiện đồng thời 'dưới 12 tháng và không kê khai đủ người' thành 'hoặc'.")
        if (any(term in normalized for term in ("bac 2", "3 4", "04 nguoi", "4 nguoi", "bon nguoi"))
                and "ke tu ngay thuc hien" in evidence_text
                and not any(term in normalized for term in ("dieu chinh", "chuyen tiep", "thoi diem ap dung"))):
            issues.append("Phải nêu điều kiện hiệu lực gắn với lần điều chỉnh giá điện; chưa xác minh mốc thì không khẳng định đang áp dụng.")
    sources = {int(row["rank"]): normalize_text(row["content"] + " " + str(row.get("heading") or ""))
               for row in chunks}
    kinds={normalize_text(c['rendered']):c['kind'] for c in claim_records}
    # Each cited sentence must share meaningful vocabulary with its own sources.
    for segment in re.split(r"\n+|(?<=[.!?])\s+", answer):
        refs = [int(ref) for ref in re.findall(r"\[(\d+)\]", segment)]
        if not refs:
            segment_normalized = normalize_text(segment)
            legal_assertion = re.search(r"\b(phải|bắt buộc|được phép|có quyền|có nghĩa vụ|vi phạm|chịu trách nhiệm|bị xử lý|xử phạt|bồi thường|hoàn trả)\b", segment, re.I)
            numeric_claim = re.search(r"\b(?:\d+(?:[.,]\d+)*|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*(?:triệu|đồng|ngày|tháng|năm)\b", segment, re.I)
            # Asking for a case fact (e.g. a 12-month lease) is not asserting a
            # legal entitlement, deadline or amount. Legal premises stay checked.
            contract_fact_question = (re.search(r'\bhop dong\b.*\b(?:dieu khoan|quy dinh|thoa thuan)\b', segment_normalized)
                                      and not re.search(r'\b(?:phai|bat buoc|duoc phep|co quyen|co nghia vu)\b', segment_normalized))
            agreement_fact_question = (re.search(r'\b(?:ban|cac ben|ben cho thue|chu tro)\b', segment_normalized)
                and re.search(r'\b(?:da|hien|dang)\b.*\b(?:thoa thuan|thong nhat)\b', segment_normalized)
                and not re.search(r'\b(?:phai|bat buoc|duoc phep|co quyen|co nghia vu)\b', segment_normalized))
            if segment.rstrip().endswith('?') and (not legal_assertion or contract_fact_question or agreement_fact_question):
                continue
            limitation = any(term in segment_normalized for term in ("chua tim thay", "chua du can cu", "khong du can cu", "chua xac minh", "chua ket luan"))
            advice = any(term in segment_normalized for term in ("kiem tra", "doi chieu", "khuyen nghi", "loi khuyen"))
            if not limitation and (legal_assertion or (numeric_claim and not advice)):
                issues.append("Kết luận hoặc số liệu chưa gắn trích dẫn trực tiếp.")
            continue
        evidence = " ".join(sources.get(ref, "") for ref in refs)
        if not evidence:
            issues.append("Trích dẫn không có nguồn tương ứng.")
            continue
        segment_normalized = normalize_text(segment)
        claim_kind=kinds.get(normalize_text(re.sub(r'^\s*-\s*','',segment)))
        for address in re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', segment):
            cited_text = ' '.join(row['content'] for row in chunks if int(row['rank']) in refs)
            if address.lower() not in cited_text.lower():
                issues.append('Địa chỉ email chưa có nguyên văn trong nguồn được trích; không suy đoán địa chỉ bị che.')
        # Keep a delayed identity obligation conditional in the claim itself.
        # A footer warning cannot repair an unconditional present-tense claim.
        for row in chunks:
            warning = str(row.get('source_scope_warning') or '')
            delayed = re.search(r'quy định xác thực điện tử áp dụng từ (\d{2}/\d{2}/\d{4})', warning, re.I)
            if int(row['rank']) not in refs or not delayed or 'xac thuc' not in segment_normalized:
                continue
            from datetime import datetime
            from zoneinfo import ZoneInfo
            commencement = datetime.strptime(delayed[1], '%d/%m/%Y').date()
            if datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date() >= commencement:
                continue
            if not (str(commencement.year) in segment_normalized and any(t in segment_normalized for t in ('tu ngay', 'ke tu', 'ap dung tu'))
                    or any(t in segment_normalized for t in ('chua ap dung', 'chua bat buoc'))):
                issues.append('Quy định xác thực điện tử có mốc áp dụng muộn; phải giữ điều kiện thời gian ngay trong câu khẳng định.')
        gap_phrases = ('chua tim thay can cu', 'chua du can cu', 'chua co can cu', 'chua xac minh',
                       'khong du de xac dinh', 'khong du can cu', 'chua cung cap can cu',
                       'khong cung cap quy trinh', 'chua cung cap can cu phap ly',
                       'khong phai dieu luat', 'khong phai quy dinh bat buoc',
                       'khong phai van ban quy pham phap luat', 'khong the khang dinh',
                       'khong du de ket luan',
                       'khong cau thanh quy dinh phap luat bat buoc')
        source_gap_pattern = (r'\b(?:nguon(?: tai lieu)?|cac tai lieu|tai lieu|doan trich|bieu gia|van ban|huong dan)\b'
                              r'.{0,120}\b(?:chua|khong) (?:neu|cung cap|xac nhan|quy dinh)\b')
        source_classification_pattern = (r'\bkhong phai(?: la)? '
            r'(?:dieu luat|(?:quy dinh|dieu khoan)(?: phap luat| luat)?|van ban quy pham phap luat)\b')
        if claim_kind=='source_limit':
            source_classification_pattern=(r'\bkhong phai(?: la)? '
                r'(?:kenh|duong day|dieu luat|(?:quy dinh|dieu khoan)(?: phap luat| luat)?|van ban quy pham phap luat)\b')
        scoped_absence = (any(term in segment_normalized for term in gap_phrases)
                          or re.search(source_gap_pattern, segment_normalized)
                          or re.search(source_classification_pattern, segment_normalized))
        # A list of missing topics ("mức phạt, bồi thường, hoàn trả") is not
        # an affirmative entitlement. Keep checking any separate modal or
        # actor/action clause appended to the disclosure of missing evidence.
        # A negated classification ("không phải quy định bắt buộc") contains
        # modal vocabulary but is not an affirmative obligation. Check separate
        # actor/action clauses before exempting the source-gap disclosure.
        affirmative_text = ' ; '.join(p for p in re.split(
            r'[,;]|\b(?:nhung|tuy nhien|do do|vi vay|va)\b', segment_normalized)
            if not any(t in p for t in gap_phrases)
            and not re.search(source_gap_pattern, p) and not re.search(source_classification_pattern, p))
        additional_assertion = re.search(
            r'(?:\bnhung\b|\btuy nhien\b|\bdo do\b|\bvi vay\b|\bva\b|[,;]).*'
            r'(?:\b(?:phai|bat buoc|co quyen|co nghia vu|bi phat|chi duoc|chi ap dung|chi co the)\b'
            r'|\b(?:chu nha|chu tro|ben cho thue|nguoi thue|ben thue)\b.{0,40}\b(?:boi thuong|hoan tra|hoan lai)\b'
            r'|\b(?:duoc|se)\s+(?:boi thuong|hoan tra|hoan lai)\b)', '; '+affirmative_text)
        if scoped_absence and not additional_assertion:
            # A statement about missing evidence cannot share vocabulary with the
            # missing rule. General claims that no law exists are rejected above.
            continue
        issues.extend(_citation_scope_issues(segment, [row for row in chunks if int(row['rank']) in refs],claim_kind))
        if ('24 gio' in segment_normalized and '24 gio' in evidence
                and 'co quan nha nuoc co tham quyen' in evidence
                and any(t in segment_normalized for t in ('go bo', 'cham dut', 'tam ngung', 'khoa tai khoan', 'cung cap thong tin'))
                and not any(t in segment_normalized for t in ('co quan nha nuoc', 'co quan co tham quyen', 'yeu cau cua cong an'))):
            issues.append('Thời hạn 24 giờ trong nguồn gắn với yêu cầu của cơ quan có thẩm quyền; không chuyển thành cam kết cho mọi phản ánh của người dùng.')
        for predicates, source_terms in (
            (("xu ly hanh chinh", "xu phat", "bi phat"), ("xu ly hanh chinh", "xu phat", "bi phat", "phat tien", "canh cao")),
            (("boi thuong",), ("boi thuong",)),
            (("hoan tra", "hoan lai"), ("hoan tra", "hoan lai", "tra lai")),
        ):
            if any(term in segment_normalized for term in predicates) and not any(term in evidence for term in source_terms):
                issues.append("Nguồn trích dẫn chưa nêu căn cứ cho kết luận về xử lý, bồi thường hoặc hoàn trả.")
        terms = set(legal_tokens(re.sub(r"\[\d+\]", "", segment)))
        if terms and len(terms & set(legal_tokens(evidence))) / len(terms) < 0.18:
            issues.append("Nội dung câu trả lời không khớp từ vựng của nguồn trích dẫn.")
        amounts = re.findall(r"\b\d{1,3}(?:[.,]\d{3}){2,}\b", segment)
        for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(?:[-–]|đến)?\s*(\d+(?:[.,]\d+)?)?\s*triệu", segment, re.I):
            amounts.extend(str(round(float(value.replace(",", ".")) * 1_000_000))
                           for value in match.groups() if value)
        for amount in amounts:
            digits = re.sub(r"\D", "", amount)
            source_numbers = {re.sub(r"\D", "", n) for n in re.findall(r"\d[\d.,]*", evidence)}
            if digits not in source_numbers:
                issues.append("Số tiền nêu trong câu trả lời chưa được nguồn trích dẫn xác nhận.")
    return list(dict.fromkeys(issues))


def append_tariff_caveat(answer: str, chunks: list[dict], query: str) -> str:
    """Câu trả lời đơn giá điện luôn kèm điều kiện áp dụng của chính nguồn: giá chưa gồm VAT và mốc áp dụng.

    Chỉ thêm khi câu trả lời đã nêu số tiền theo bậc và các điều kiện này CÓ trong đoạn nguồn (trích kèm số thứ tự nguồn);
    không bao giờ tự suy ra ngày hay thuế. Giá điện đổi theo quyết định mới, nên người dùng phải được nhắc đối chiếu.
    """
    if not tariff_question(query) or not re.search(r"\d\.\d{3}\s*đồng", answer):
        return answer
    notes = []
    for row in chunks:
        value = normalize_text(row["content"])
        if "chua bao gom thue gia tri gia tang" in value and "phu luc" in value and not any("thuế giá trị gia tăng" in n for n in notes):
            notes.append(f"giá bán điện trong phụ lục chưa bao gồm thuế giá trị gia tăng [{row['rank']}]")
        match = re.search(r"áp dụng giá bán điện: từ ngày [^.\n]{5,40}", row["content"])
        if match and not any("áp dụng" in n for n in notes):
            notes.append(f"{match[0].replace('áp dụng giá bán điện', 'thời gian áp dụng giá bán điện')} [{row['rank']}]")
    if not notes:
        return answer
    caveat = "Điều kiện theo nguồn: " + "; ".join(notes) + ". Giá điện có thể được điều chỉnh bởi quyết định mới, nên đối chiếu biểu giá hiện hành do cơ quan có thẩm quyền công bố."
    # đặt trước dòng "Lưu ý: … không thay thế tư vấn pháp lý" để dòng đó vẫn là câu kết
    marker = answer.find("Lưu ý: Đây là thông tin tham khảo")
    if marker > 0:
        return answer[:marker].rstrip() + "\n\n" + caveat + "\n\n" + answer[marker:]
    return answer + "\n\n" + caveat


def append_commencement_evidence(answer: str, chunks: list[dict], query: str) -> str:
    answer = append_tariff_caveat(answer, chunks, query)
    return _append_commencement_evidence(answer, chunks, query)


def _append_commencement_evidence(answer: str, chunks: list[dict], query: str) -> str:
    """Retain an essential commencement condition verbatim, never invent a date.

    Only supplements an otherwise generated answer when its retrieved source has
    an explicit delayed-commencement phrase and the answer omitted that condition.
    """
    issues = evidence_issues(answer, chunks, query)
    if not any(issue.startswith("Phải nêu điều kiện hiệu lực") for issue in issues):
        return answer
    for row in chunks:
        match = re.search(r"có hiệu lực(?: thi hành)? k[ểê] từ ngày thực hiện[^.\n]{20,700}(?:\.|$)", row["content"], re.I)
        if match:
            return answer + f"\n\nĐiều kiện hiệu lực trong nguồn: “{match[0].rstrip('.')}” [{row['rank']}]."
    return answer

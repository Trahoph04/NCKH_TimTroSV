"""Evidence coverage and whole-unit assembly; these rules do not create legal facts."""
import re
from .providers import normalize_text


FACET_LABELS = {'deposit':'tiền cọc', 'rent':'tiền thuê', 'payment':'thanh toán'}

LISTING_CHECK_LABELS = {'account': 'kiểm tra người đăng/tài khoản',
                        'contact': 'đối chiếu địa chỉ và liên hệ',
                        'image': 'kiểm tra nguồn hình ảnh', 'price': 'kiểm tra giá bất thường'}

OPERATOR_LABELS = {'identity': 'thông tin định danh và thời điểm xác thực',
                   'moderation': 'lọc từ khóa, rà soát và gỡ thông tin vi phạm',
                   'complaints': 'tiếp nhận phản ánh theo quy trình công khai',
                   'authority_data': 'cung cấp dữ liệu theo yêu cầu cơ quan có thẩm quyền'}


def practical_facets(question, row):
    """Locate separate source facets, without supplying rules or reference facts."""
    q = normalize_text(question)
    body = normalize_text(row.get('text', row.get('parent_content') or row.get('content', '')))
    heading = normalize_text(row.get('heading') or '')
    category = row.get('category')
    found = set()
    if 'tien dien' in q and any(t in q for t in ('thong bao', 'cach tinh', 'so dien', 'minh bach')):
        if category == 'electricity' and 'hoa don' in body and 'nguoi thue' in body:
            found.add('giới hạn thu tiền điện theo hóa đơn, đúng điều kiện áp dụng')
        if 'cong khai cach tinh' in body or ('quyen cua nguoi tieu dung' in heading and 'hoa don' in body):
            found.add('thông tin cách tính và hóa đơn, phân biệt quyền với khuyến nghị')
        if category == 'electricity' and 'do dem' in heading:
            found.add('đo đếm và đối chiếu sản lượng')
    if 'nuoc' in q and any(t in q for t in ('dau nguoi', 'dung chung', 'phan chia', 'thoa thuan', 'khoan')):
        if category == 'housing_contract' and any(t in heading for t in ('nguyen tac co ban', 'noi dung cua hop dong')):
            found.add('thỏa thuận nội dung, giá và cách thanh toán')
        if category == 'housing_contract' and 'quyen cua nguoi tieu dung' in heading and 'hoa don' in body:
            found.add('đối chiếu hóa đơn và thông tin giao dịch')
        if category == 'water_cantho':
            found.add('biểu giá nước và phạm vi của nguồn giá')
        if category == 'housing_contract' and 'tien nuoc' in body and 'doc ky' in body:
            found.add('kiểm tra điều khoản tiền nước trước khi thuê')
    if 'tam tru' in q and 'cung cap' in q and 'trach nhiem' in q:
        if category == 'residence' and 'nghia vu cua cong dan' in heading and 'cung cap' in body:
            found.add('nghĩa vụ cung cấp thông tin của công dân')
        if category == 'residence' and 'chu ho co quyen va nghia vu' in body:
            found.add('phối hợp của chủ hộ, không đồng nhất với mọi chủ trọ')
        if category == 'residence' and 'ho so' in heading and 'cho o hop phap' in body:
            found.add('giấy tờ chỗ ở hợp pháp trong hồ sơ cơ bản')
        if category == 'residence' and 'van ban cho thue' in body and 'khong phai cong chung' in body:
            found.add('giấy tờ chỗ ở hợp pháp trong hồ sơ cơ bản')
        if category == 'residence' and 'khai thac' in body and 'khi co quan dang ky cu tru co yeu cau' in body:
            found.add('khai thác dữ liệu trước, cung cấp giấy tờ khi có yêu cầu đúng điều kiện')
    if 'cu tru' in q and any(t in q for t in ('chuyen sang','chuyen phong','thay doi cho o')) and category == 'residence':
        if 'noi tam tru moi' in body and 'ho so dang ky tam tru' in body:
            found.add('đăng ký tại nơi dự kiến tạm trú và cập nhật nơi mới')
        if 'xoa dang ky tam tru' in heading and 'khong dang ky tam tru tai cho o khac' in body:
            found.add('căn cứ xóa đăng ký cũ theo từng trường hợp')
        if 'sua doi' in heading and 'dieu 10. ho so, thu tuc xoa dang ky tam tru' in body:
            found.add('thủ tục xóa hiện hành và thời hạn gắn đúng trường hợp')
    if 'thoat nan' in q and any(t in q for t in ('khoa', 'chan', 'can tro')):
        if category == 'fire_safety' and 'thong thoang' in body and 'chu nha tro' in body:
            found.add('khắc phục lối thoát bị cản trở khi chưa có cháy')
        if category == 'fire_safety' and '114' in body:
            found.add('báo cháy khẩn cấp 114')
        if category == 'fire_safety' and 'ket trong phong' in body:
            found.add('thoát nạn và chờ cứu hộ khi xảy ra cháy')
    if any(t in q for t in ('anh can cuoc', 'anh cccd', 'anh giay to')) and any(t in q for t in ('luu', 'su dung')):
        if category == 'privacy_data' and 'muc dich' in body and 'pham vi' in body:
            found.add('mục đích và phạm vi xử lý dữ liệu')
        if category == 'privacy_data' and any(t in body for t in ('luu tru', 'bao ve du lieu ca nhan')) and any(t in body for t in ('khoang thoi gian', 'ky thuat')):
            found.add('thời gian lưu trữ và biện pháp bảo vệ')
        if category == 'privacy_data' and 'cung cap du lieu ca nhan' in heading and 'dong y' in body:
            found.add('điều kiện cung cấp cho bên khác và ngoại lệ pháp luật')
    if 'lien ket la' in q and category == 'criminal_law':
        if any(t in body for t in ('website gia mao','duong link la')):
            found.add('nhận diện và kiểm tra liên kết giả/lạ')
        if any(t in body for t in ('mat khau','otp')):
            found.add('bảo vệ thông tin bảo mật ngân hàng')
        if any(t in body for t in ('thuc giuc','hoi thuc','nhanh chong')):
            found.add('cảnh giác thúc ép chuyển tiền')
    if 'moi gioi' in q and category == 'housing_contract':
        if 'tra tien dich vu' in heading and 'khong dat' in body and 'giam tien dich vu' in body:
            found.add('phí dịch vụ và điều kiện giảm phí/bồi thường')
        if 'cham dut' in heading and 'dich vu' in heading:
            found.add('điều kiện chấm dứt và phí phần dịch vụ đã thực hiện')
    return found


def platform_reporting_question(question):
    q = normalize_text(question)
    return (any(t in q for t in ('bao cao', 'bao tin', 'phan anh'))
            and any(t in q for t in ('tin dang', 'thong tin sai', 'tin sai')))


def report_proof_row(row):
    body = normalize_text(row.get('text', row.get('parent_content') or row.get('content', '')))
    return row.get('category') == 'ecommerce_platform' and any(
        t in body for t in ('bang chung so bo', 'hinh anh) trao doi', 'hinh anh trao doi'))


def operator_facets(row):
    raw = row.get('text', row.get('parent_content') or row.get('content', ''))
    body = normalize_text(raw)
    if row.get('category') != 'ecommerce_platform':
        return set()
    facets = set()
    if 'xac thuc' in body and any(t in body for t in ('danh tinh', 'so dinh danh')):
        facets.add('identity')
    if 'tu khoa' in body and 'go bo' in body:
        facets.add('moderation')
    if any(t in body for t in ('phan anh', 'khieu nai')) and any(t in body for t in ('cong khai', 'tiep nhan', 'giai quyet', 'duy tri')):
        facets.add('complaints')
    # The data deadline must belong to the same point, not a neighbouring
    # point whose 24 hours concern removing a listing.
    points = [normalize_text(p) for p in re.split(r'\n\s*\n', raw)]
    if any('24 gio' in p and any(t in p for t in ('co quan nha nuoc co tham quyen', 'co quan co tham quyen', 'cong an co tham quyen')) and 'cung cap' in p for p in points):
        facets.add('authority_data')
    return facets


def listing_check_facets(row):
    text = normalize_text(row.get('text', row.get('content', '')))
    facets = set()
    if any(t in text for t in ('xac thuc so dien thoai', 'xac thuc danh tinh', 'tai khoan nguoi', 'thong tin chu nha')):
        facets.add('account')
    if any(t in text for t in ('dia chi', 'so dien thoai', 'lien he truc tiep')):
        facets.add('contact')
    if any(t in text for t in ('google ong kinh', 'hinh anh tuong tu', 'tim kiem bang hinh anh')):
        facets.add('image')
    if any(t in text for t in ('gia re', 'gia thap', 'gia qua re', 'gia chung', 're bat thuong')):
        facets.add('price')
    return facets


def human_reporting_question(question):
    q=normalize_text(question)
    return any(t in q for t in ('toi','chung toi','sinh vien','nguoi thue')) and any(
        t in q for t in ('trinh bao','luu lai bang chung','cung cap thong tin','luu chung cu'))


def reporting_evidence_row(row):
    body=normalize_text(row.get('text',row.get('content','')))
    return row.get('category')=='criminal_law' and any(t in body for t in ('luu giu','luu lai')) and any(
        t in body for t in ('tin nhan','chung tu chuyen tien','lich su giao dich'))


def requested_contract_facets(question):
    q = normalize_text(question)
    if not any(t in q for t in ('hop dong', 'dieu khoan', 'ghi ro')):
        return set()
    return {name for name, terms in {
        'deposit':('tien coc', 'dat coc', 'hoan coc'),
        'rent':('tien thue', 'gia thue'),
        'payment':('thanh toan', 'ngay tra tien', 'han tra tien'),
    }.items() if any(t in q for t in terms)}


def contract_facets(row):
    if row.get('category') != 'housing_contract':
        return set()
    value = normalize_text(' '.join(str(row.get(k) or '') for k in ('heading','text','content','parent_content')))
    return {name for name, terms in {
        'deposit':('dat coc', 'tien coc'),
        # Literal PDF OCR can split "dịch"; this changes matching only.
        'rent':('gia giao dich', 'gia giao d ich', 'gia thue', 'tien thue'),
        'payment':('thoi han thanh toan', 'phuong thuc thanh toan', 'tra tien thue', 'ngay thanh toan'),
    }.items() if any(t in value for t in terms)}


def whole_supplementary_units(rows, budget=5500):
    """Use the full parent before filtering inventories; never emit middle fragments."""
    unique = {}
    for row in rows:
        key = row.get('provision_id') or (row['document_id'], row.get('heading'))
        if key in unique:
            if row.get('parent_content'):
                unique[key]['content'] = row['parent_content']
            continue
        unit = dict(row)
        if row.get('parent_content'):
            unit['content'] = row['parent_content']
            unit['context_complete'] = True
        else:
            siblings = [r for r in rows if (r['document_id'],r.get('heading')) == key]
            unit['content'] = '\n\n'.join(r['content'] for r in sorted(siblings,key=lambda r:r['chunk_index']))
            unit['context_complete'] = bool(siblings)
        unique[key] = unit
    chosen, size = [], 0
    for row in unique.values():
        introduction=(row.get('provision_metadata') or {}).get('article_context','')
        body=row['content'][len(introduction):].lstrip() if introduction and row['content'].startswith(introduction) else row['content']
        value = normalize_text(body)
        if (not value or 'noi nhan:' in value or re.search(
                r'^(?:\d+[.,]\s*)?(?:bai bo\b|cac quy dinh sau(?: day)? het hieu luc\b)', value)):
            continue
        if size + len(row['content']) <= budget:
            chosen.append(row); size += len(row['content'])
    return chosen


def scope_issues(question, parts):
    """Reject known actor mismatches; explain gaps without supplying a legal answer."""
    q = normalize_text(question)
    body = normalize_text(' '.join(p.get('text',p.get('content','')) for p in parts))
    issues = []
    if human_reporting_question(question) and 'criminal_law' in {p.get('category') for p in parts}:
        if not any(reporting_evidence_row(p) for p in parts):
            issues.append('Thủ tục nội bộ của cơ quan tiếp nhận chưa trả lời các tài liệu, tin nhắn hoặc chứng từ người trình báo cần lưu/cung cấp.')
    if 'moi gioi' in q and any(t in q for t in ('sinh vien','nguoi thue','phi','tra')):
        with_headings=normalize_text(' '.join(str(p.get('heading') or '')+' '+str(p.get('text',p.get('content','')) or '') for p in parts))
        remuneration=('thu lao' in with_headings and 'ca nhan' in with_headings
                      and 'doanh nghiep' in with_headings)
        customer_service=any(t in with_headings for t in (
            'khach hang','nguoi thue','hop dong dich vu','ben su dung dich vu'))
        if remuneration and not customer_service:
            issues.append('Nguồn thù lao cá nhân môi giới với doanh nghiệp chưa trả lời phí người thuê trả.')
    if any(t in q for t in ('nhieu phong','nhieu tang')) and 'fire_safety' in {p.get('category') for p in parts}:
        if not any(t in body for t in ('nhieu tang','nhieu can ho','co so','kinh doanh')):
            issues.append('Cần căn cứ phân loại nhà trọ nhiều phòng và điều kiện tương ứng.')
        else:
            issues.append('Cần xác định loại hình sử dụng, số tầng, diện tích và quy chuẩn của nhà trọ để chọn đúng nhóm điều kiện; chưa kết luận chỉ từ số phòng.')
    if 'nen tang' in q and any(t in q for t in ('dang tin','thong tin','so dien thoai')):
        if 'dat hang truc tuyen' in body and not any(t in body for t in ('khong co chuc nang dat hang','dang tin','nen tang trung gian','dieu 17')):
            issues.append('Cần phân biệt nền tảng đăng tin với nền tảng có chức năng đặt hàng.')
    if 'dien' in q and any(t in q for t in ('thong bao','minh bach','san luong')):
        direct_notice=re.search(r'(?:thong bao|cong khai)[^.]{0,350}(?:nguoi thue|ben thue)',body)
        if not direct_notice or not any(t in body for t in ('san luong','luong dien','chi so')):
            issues.append('Chưa có nguồn trực tiếp về thông báo cách tính và sản lượng điện.')
    if 'nuoc' in q and any(t in q for t in ('can tho','dia phuong','uy ban')):
        if not any('cần thơ' in (p.get('document','')+' '+p.get('text','')).lower() for p in parts):
            issues.append('Cần văn bản địa phương Cần Thơ, phạm vi địa bàn và hiệu lực áp dụng.')
    if 'tam tru' in q and 'ai' in q and 'trach nhiem' in q and 'cung cap' in q:
        if not any(t in body for t in ('chu so huu co trach nhiem','chu ho co trach nhiem','nguoi cho thue co trach nhiem')):
            issues.append('Nguồn hiện có xác nhận nghĩa vụ của công dân và hồ sơ đăng ký; chưa có căn cứ riêng để kết luận toàn bộ nghĩa vụ cung cấp giấy tờ của chủ trọ.')
    if re.search(r'có hiệu lực(?: thi hành)? k[ểê] từ ngày thực hiện', ' '.join(p.get('text','') for p in parts),re.I):
        if not any(p.get('trigger_verified') for p in parts):
            issues.append('Nguồn có hiệu lực có điều kiện; chưa xác nhận văn bản/sự kiện kích hoạt.')
    return issues

"""Deterministic article/clause structure; annotations never replace quoted law."""
from dataclasses import dataclass, asdict
import hashlib
import re

ARTICLE = re.compile(r'(?m)^[ \t]*(?:#{1,6}[ \t]+)?Điều[ \t]+(\d+[a-z]?)[ \t]*[.:—–-][^\n]*', re.I)
CLAUSE = re.compile(r'(?m)^[ \t]*(\d+)\.(?:\[\d+\])*[ \t]+')
POINT = re.compile(r'(?m)^[ \t]*([a-zđ])\)[ \t]+')
EDITORIAL = re.compile(r'(?im)^\s*(?:GHI CHÚ NGỮ CẢNH|Ghi chú nguồn|Ghi chú: Đây là bản|Nguồn đối chiếu|Cách dùng trong|Cách trả lời tình huống|Lược khỏi|Giới hạn trích tuyển|BẢN TRÍCH TUYỂN NGHIÊN CỨU)\b')


@dataclass
class Provision:
    provision_id: str
    article: str | None
    clause: str | None
    heading: str
    content: str
    source_start: int
    source_end: int
    points: list[str]
    exceptions: list[str]
    cross_references: list[str]
    kind: str = 'legal_provision'
    article_context: str = ''


def structure_provisions(text: str, document_sha: str, *, advisory=False) -> list[Provision]:
    quoted_provisions = [(m.start(),m.end()) for m in re.finditer(
        r'“\s*(?:Điều\s+\d+|\d+\.|[a-zđ]\))[^“”]*”',text,re.I)]
    def outside_quote(pos, start=0):
        return not any(a<=pos<b for a,b in quoted_provisions)
    # Recognize complete quoted replacement provisions, not stray OCR punctuation.
    matches = [m for m in ARTICLE.finditer(text) if outside_quote(m.start())]
    if not matches:
        if not advisory:
            return []
        return [Provision(document_sha+':advice', None, None, 'Khuyến cáo cơ quan Công an', text.strip(),
                          0,len(text),[],[],[], 'official_advice')]
    result = []
    for i, article in enumerate(matches):
        end = matches[i+1].start() if i+1<len(matches) else len(text)
        tail = text[article.start():end]
        editorial = EDITORIAL.search(tail[article.end()-article.start():])
        if editorial:
            end = article.end()+editorial.start()
        # Mailing lists and signatories are outside legal provisions.
        stop = re.search(r'(?im)^\s*(Nơi\s+nhận\s*:|TM\. CHÍNH PHỦ|CHỦ TỊCH QUỐC HỘI|KT\. BỘ TRƯỞNG)', text[article.end():end])
        if stop: end = article.end()+stop.start()
        clauses = [m for m in CLAUSE.finditer(text,article.end(),end) if outside_quote(m.start(), article.end())]
        spans = [(None,article.end(),clauses[0].start())] if clauses and text[article.end():clauses[0].start()].strip() else []
        spans += [(m[1],m.start(),clauses[j+1].start() if j+1<len(clauses) else end) for j,m in enumerate(clauses)]
        intro = text[article.end():clauses[0].start()].strip() if clauses else ''
        # Decisions can place the operative rule directly on the article line.
        # Keeping that line prevents an empty or mutilated provision.
        if not clauses: spans = [(None,article.start(),end)]
        for number,start,finish in spans:
            content = text[start:finish].strip()
            if not content: continue
            heading = article[0].strip().lstrip('# ').strip('“"')
            if number: heading += ' | Khoản '+number
            key = f'{document_sha[:20]}:{article.start()}:{number or "body"}'
            result.append(Provision(key,article[1],number,heading,content,start,finish,
                list(dict.fromkeys(POINT.findall(content))),
                re.findall(r'[^.;\n]*(?:trừ trường hợp|ngoại trừ|không áp dụng)[^.;\n]*[.;]?',content,re.I),
                list(dict.fromkeys(re.findall(r'(?:khoản\s+\d+\s+)?Điều\s+\d+[a-z]?',content,re.I))),article_context=intro if number else ''))
    return result


def provision_json(item):
    value = asdict(item)
    value['content_sha256'] = hashlib.sha256(item.content.encode('utf-8')).hexdigest()
    return value

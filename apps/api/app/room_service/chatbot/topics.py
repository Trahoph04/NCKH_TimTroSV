"""Topic routing by whole phrases; categories narrow evidence, never supply facts."""
from __future__ import annotations

import re

from .providers import normalize_text


TOPICS = {
    "electricity": ("tien dien", "gia dien", "thu dien", "tinh dien", "kwh", "dinh muc dien"),
    "water_cantho": ("tien nuoc", "gia nuoc", "dong ho nuoc", "cap nuoc", "chi phi nuoc"),
    "residence": ("cu tru", "tam tru", "luu tru"),
    "fire_safety": ("pccc", "phong chay", "chua chay", "chay no", "thoat nan"),
    "student_housing": ("ky tuc xa", "ki tuc xa", "ktx", "nha o sinh vien"),
    "real_estate_brokerage": ("moi gioi", "nguoi gioi thieu"),
    "ecommerce_platform": ("nen tang", "truc tuyen", "lien ket la"),
    "privacy_data": ("ca nhan", "can cuoc", "so dien thoai", "anh giay to"),
    "criminal_law": ("lua dao", "gia mao", "trinh bao", "cat lien lac", "nhan coc", "chuyen coc", "dau hieu rui ro"),
    "housing_contract": ("hop dong", "dat coc", "tien coc", "hoan coc", "cham dut", "tang gia thue", "quyen cho thue"),
}


def has_phrase(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def user_listing_check_question(query: str) -> bool:
    """A renter checking a post is distinct from a platform's legal duties."""
    text = normalize_text(query)
    return (any(has_phrase(text, p) for p in ('kiem tra', 'xac minh', 'doi chieu'))
            and any(has_phrase(text, p) for p in ('nguoi dang', 'nguon tin', 'tin dang', 'tai khoan'))
            and any(has_phrase(text, p) for p in ('nen tang', 'truc tuyen', 'tren mang', 'qua mang'))
            and not any(has_phrase(text, p) for p in ('trach nhiem cua nen tang', 'nen tang co trach nhiem')))


def question_categories(query: str) -> tuple[str, ...]:
    text = normalize_text(query)
    found = [key for key, phrases in TOPICS.items() if any(has_phrase(text, p) for p in phrases)]
    if 'student_housing' in found:
        # CTU operational information comes first for explicit KTX questions.
        found = ['student_housing', *(key for key in found if key != 'student_housing')]
    if user_listing_check_question(query):
        # Include published rental/fraud checking advice; do not route a human
        # checklist exclusively to provisions imposing duties on the operator.
        found = list(dict.fromkeys(['criminal_law', *found, 'housing_contract']))
    # Contracts and identity documents often accompany a more specific question.
    # Keep them as supporting categories, rather than replacing the primary topic.
    if "criminal_law" in found and "housing_contract" not in found:
        found.append("housing_contract")
    if "water_cantho" in found and "housing_contract" not in found:
        found.append("housing_contract")
    if 'real_estate_brokerage' in found and 'housing_contract' not in found:
        found.append('housing_contract')
    if ('electricity' in found and any(t in text for t in ('thong bao', 'cach tinh', 'minh bach'))
            and 'housing_contract' not in found):
        found.append('housing_contract')
    return tuple(found)


def required_evidence_categories(query: str) -> tuple[str, ...]:
    """Explicitly requested facets, excluding incidental words like 'giấy tờ'."""
    text = normalize_text(query)
    requested = []
    for category in question_categories(query):
        if category == 'ecommerce_platform' and user_listing_check_question(query):
            # An online platform is the setting of the practical question, not
            # a request for statutory duties of its operator.
            continue
        if category=='housing_contract' and any(t in text for t in ('dau hieu rui ro','khong cho xem phong')) and not has_phrase(text,'hop dong'):
            continue
        phrases = TOPICS[category]
        if category == 'privacy_data':
            phrases = ('thong tin ca nhan', 'du lieu ca nhan', 'anh can cuoc', 'so dien thoai', 'anh giay to')
        if any(has_phrase(text, phrase) for phrase in phrases):
            requested.append(category)
    return tuple(requested)

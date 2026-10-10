"""Extract explicit financial provisions instead of paraphrasing their conditions.

No legal amounts, dates, document identifiers or answers are stored here. The
selected text is copied from the retrieved corpus and carries its own citation.
Other questions continue through the configured language model.
"""
from __future__ import annotations

import re

from .providers import GenerationResult, normalize_text
from .legal_retrieval import electricity_question


def extract_partial_provisions(question: str, chunks: list[dict]) -> GenerationResult | None:
    """Copy complete paragraphs, without inferring how a rule applies to a case."""
    from .legal_retrieval import legal_tokens
    terms = set(legal_tokens(question)) - {"nguoi", "thue", "nha", "tro", "phong", "can", "nen", "gi", "nhung"}
    candidates = []
    query=normalize_text(question)
    ordinary_rental=any(term in query for term in ('thue tro','thue phong','hop dong tro')) and not any(term in query for term in ('mua ban','thue mua'))
    for row, paragraph, normalized_paragraph in _paragraphs(chunks):
        heading = normalize_text(str(row.get("heading") or ""))
        if "hieu luc" in heading or "chuyen tiep" in heading:
            continue
        if ordinary_rental and any(term in normalized_paragraph for term in ('mua ban','thue mua','nha cong vu','tai san cong')) and not re.search(r'\bthue\b(?!\s+mua)',normalized_paragraph):
            continue
        shared = terms & set(legal_tokens(paragraph))
        if len(shared) < min(3, len(terms)) or len(shared) / max(1, len(terms)) < .18:
            continue
        candidates.append((len(shared) / max(1, len(terms)), row, paragraph))
    candidates.sort(key=lambda part: (-part[0], int(part[1]["rank"])))
    selected, seen = [], set()
    for _, row, paragraph in candidates:
        if paragraph in seen:
            continue
        seen.add(paragraph)
        selected.append((row, paragraph))
        if len(selected) == 2:
            break
    if not selected:
        return None
    lines = ["Các căn cứ liên quan tìm được trong kho (trích nguyên đoạn):"]
    for row, paragraph in selected:
        lines.append(f"- {row['title']} — {row.get('heading') or 'trích đoạn'}: “{paragraph}” [{row['rank']}].")
    lines.append("Đây là câu trả lời một phần từ nguồn; chưa kết luận cách áp dụng cho tình huống riêng của bạn. Cần đối chiếu điều kiện, hiệu lực và bản gốc.")
    return GenerationResult("\n\n".join(lines), "legal-partial-extractive")


def _paragraphs(chunks: list[dict]):
    for row in chunks:
        content = re.sub(r"\n\s*\n\s*:\s*", " ", row["content"])
        for paragraph in re.split(r"\n\s*\n", content):
            paragraph = paragraph.strip()
            if 60 <= len(paragraph) <= 1500:
                yield row, paragraph, normalize_text(paragraph)


def extract_legal_answer(question: str, chunks: list[dict]) -> GenerationResult | None:
    query = normalize_text(question)
    if not electricity_question(question) or not chunks:
        return None
    if any(term in query for term in ("ngan hang nao", "tai khoan nao")):
        # Keep accents here: legal references "tại khoản" are not bank "tài khoản".
        if not any(re.search(r"\b(?:ngân hàng|tài khoản)\b", row["content"], re.I) for row in chunks):
            refs = " ".join(f"[{row['rank']}]" for row in chunks)
            return GenerationResult(
                "Chưa tìm thấy căn cứ xác định ngân hàng hoặc số tài khoản bắt buộc để chủ trọ thu tiền điện "
                f"trong các đoạn đã truy xuất. {refs}\n\n"
                "Bạn cần kiểm tra thỏa thuận thanh toán trong hợp đồng thuê và thông tin do chủ trọ cung cấp; "
                "kết quả tìm kiếm này không đủ để kết luận pháp luật có hay không có quy định đó.",
                "legal-insufficient",
            )
    if any(term in query for term in ("ngan hang", "tai khoan", "thoi han nop", "ngay nop", "hanh lang", "trom cap")):
        return None
    mode = ""
    if any(term in query for term in ("tu khi nao", "hieu luc", "ngay nao")):
        mode = "commencement"
    elif any(term in query for term in ("xu phat", "bi phat", "xu ly")):
        mode = "penalty"
    elif any(term in query for term in ("thu thua", "hoan tra", "tra lai")):
        mode = "refund"
    elif "12 thang" in query and any(term in query for term in ("duoi", "khong ke khai", "khong ke")):
        mode = "short_lease"
    elif "dinh muc" in query or "sinh vien o chung" in query:
        mode = "quota"
    elif any(term in query for term in ("chu tro", "chu nha", "nguoi cho thue")) and any(
        term in query for term in ("thu tien dien", "thu dien", "kwh")
    ):
        mode = "invoice"
    if not mode:
        return None

    paragraphs = list(_paragraphs(chunks))
    predicates = {
        "invoice": lambda value: "tong tien dien" in value and "khong duoc vuot qua" in value,
        "quota": lambda value: "ke khai" in value and "dinh muc" in value and "3 4" in value,
        "short_lease": lambda value: "duoi 12 thang" in value and "khong" in value and "ke khai" in value,
        "penalty": lambda value: "phat tien" in value and "nguoi cho thue nha" in value and "thu tien dien" in value,
        "refund": lambda value: "nguoi cho thue nha" in value and "hoan tra" in value and "thu thua" in value,
    }
    selected = []
    if mode == "commencement":
        for row in chunks:
            match = re.search(r"có hiệu lực(?: thi hành)? k[ểê] từ ngày thực hiện[^.\n]{20,700}(?:\.|$)", row["content"], re.I)
            if match:
                selected.append((row, match[0]))
                break
    else:
        for row, paragraph, value in paragraphs:
            if predicates[mode](value):
                selected.append((row, paragraph))
                break
    if not selected:
        return None
    if mode == "penalty":
        for row, paragraph, value in paragraphs:
            if predicates["refund"](value):
                selected.append((row, paragraph))
                break
        # Preserve the complete scope sentence, including organizational exceptions.
        for row, paragraph, value in paragraphs:
            if "ca nhan thuc hien" in value and "muc phat tien" in value and paragraph.rstrip().endswith((".", ";")):
                selected.append((row, paragraph))
                break

    labels = {"invoice": "Giới hạn thu tiền điện", "quota": "Định mức theo số người thuê",
              "short_lease": "Thuê dưới 12 tháng và không kê khai đầy đủ số người",
              "penalty": "Xử phạt và hoàn trả tiền thu thừa", "refund": "Hoàn trả tiền thu thừa",
              "commencement": "Điều kiện về thời điểm áp dụng"}
    lines = [labels[mode] + ":"]
    for row, paragraph in selected:
        heading = row.get("heading") or row["title"]
        lines.append(f"- {heading}: “{paragraph.lstrip('- ').strip()}” [{row['rank']}]")
    answer = "\n\n".join(lines)
    # Even the invoice cap in the rental provision may have delayed commencement.
    if mode in {"invoice", "quota", "short_lease"}:
        for row in chunks:
            match = re.search(r"có hiệu lực(?: thi hành)? k[ểê] từ ngày thực hiện[^.\n]{20,700}(?:\.|$)", row["content"], re.I)
            if match:
                answer += f"\n\nĐiều kiện hiệu lực trong nguồn: “{match[0].rstrip('.')}” [{row['rank']}]."
                break
    if mode == "invoice" and "kwh" in query:
        answer += "\n\nCần đối chiếu hóa đơn, sản lượng và cách phân bổ thực tế để đánh giá mức thu bạn nêu."
    answer += "\n\nThông tin tham khảo từ văn bản đã trích xuất; cần đối chiếu điều kiện áp dụng và bản gốc."
    return GenerationResult(answer, "legal-extractive")

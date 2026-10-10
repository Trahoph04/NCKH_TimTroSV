"""Dựng 1 nguồn pháp lý cho chatbot từ file Word gốc: tách theo Điều/Khoản, GIỮ NGUYÊN VĂN, ghi vào manifest.

    python3 apps/api/chatbot_corpus/tools/build_word_source.py nd282

Vì sao có script: chatbot chỉ trả lời được từ các nguồn đã nạp. 08/10 phát hiện câu "mức phạt khi không đăng ký tạm trú" không trả
lời được vì Nghị định 282/2025 (xử phạt VPHC về an ninh trật tự, gồm cư trú) nằm ở thư mục Data của branch PHUC nhưng chưa nạp.
Script chỉ đọc XML trong .docx (không cần Word/antiword), không viết lại câu chữ, không thêm giải thích của nhóm.
Sau khi chạy: `docker compose exec api python -m app.room_service.legal_knowledge.index_corpus`.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SOURCES = {
    "nd282": dict(
        id="residence282-word", file="originals/nd282-2025-trich-tuyen.docx", category="residence",
        title="Nghị định 282/2025/NĐ-CP — bản Word trích tuyển cung cấp",
        source_url="https://vanban.chinhphu.vn/?classid=1&docid=219411&orggroupid=2&pageid=27160",
        effective_date="2025-12-15",
        warning=("Bản trích tuyển các Điều 1, 2, 3, 5, 6, 9, 10, 11, 69, 70 — không đủ toàn văn; chưa xác minh toàn bộ câu chữ với bản "
                 "chính thức. Bản trích ghi đã cập nhật Điều 3 khoản 6 và Điều 10 khoản 2 điểm đ, khoản 3 điểm b, khoản 4 điểm d theo "
                 "Nghị định 347/2026/NĐ-CP (hiệu lực 15/09/2026). Mức phạt ở Điều 10 là mức đối với cá nhân hay tổ chức phải đối chiếu "
                 "Điều 5 và bản chính thức."),
    ),
}


def paragraphs(docx: Path) -> list[str]:
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    out = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if text:
            out.append(text)
    return out


def split_articles(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """[(số điều, tiêu đề, các dòng thân)] — bỏ phần đầu văn bản và các dòng 'Ghi chú bản trích' (ghi chú biên tập, không phải luật)."""
    articles, current = [], None
    for line in lines:
        m = re.match(r"^Điều (\d+[a-z]?)\.\s*(.+)$", line)
        if m:
            current = (m.group(1), line, [])
            articles.append(current)
        elif current is not None and not line.startswith("Ghi chú bản trích") and not re.match(r"^Chương [IVXL]+$", line):
            current[2].append(line)
    return articles


def split_clauses(body: list[str]) -> list[tuple[str | None, str]]:
    """Khoản = dòng bắt đầu '1. ', '2. ' …; các điểm a), b)… nằm trong khoản của nó. Phần dẫn trước khoản 1 (nếu có) là khoản None."""
    clauses: list[tuple[str | None, list[str]]] = []
    for line in body:
        m = re.match(r"^(\d+)\.\s", line)
        if m and (not clauses or clauses[-1][0] is None or int(m.group(1)) == int(clauses[-1][0] or 0) + 1):
            clauses.append((m.group(1), [line]))
        elif clauses:
            clauses[-1][1].append(line)
        else:
            clauses.append((None, [line]))
    return [(num, "\n".join(parts)) for num, parts in clauses]


def build(key: str) -> None:
    spec = SOURCES[key]
    docx = ROOT / spec["file"]
    original_sha = hashlib.sha256(docx.read_bytes()).hexdigest()
    lines = paragraphs(docx)
    text_sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    provisions = []
    for article, heading, body in split_articles(lines):
        for number, content in split_clauses(body):
            sha = hashlib.sha256(content.encode()).hexdigest()
            full_heading = heading + (f" | Khoản {number}" if number else "")
            provisions.append(dict(
                provision_id=f"{spec['id']}:{sha[:20]}", article=article, clause=number, heading=full_heading, content=content,
                points=re.findall(r"^([a-zđ])\)", content, re.M), exceptions=[], cross_references=re.findall(r"(?:khoản \d+ )?Điều \d+", content)[:8],
                kind="legal_provision", article_context="", content_sha256=sha, page_from=1, page_to=1, extraction_text_sha256=text_sha))
    source = dict(
        id=spec["id"], title=spec["title"], category=spec["category"], path=spec["file"], sha256=original_sha, original_sha256=original_sha,
        source_url=spec["source_url"], publisher="Cổng thông tin điện tử Chính phủ (bản Word cung cấp)", effective_date=spec["effective_date"],
        page_kind="logical_document", pages=1, ocr_used=False, extraction="Native Word XML; no PDF or OCR execution",
        source_content_kind="provided_word_excerpt", source_scope_warning=spec["warning"], not_exhaustive=True,
        source_policy="Literal text from the supplied Word; editorial notes removed; no authored answers.")
    target = ROOT / f"{spec['id']}.json"
    target.write_text(json.dumps(dict(source=source, provisions=provisions), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path = ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = dict(id=spec["id"], file=target.name, sha256=hashlib.sha256(target.read_bytes()).hexdigest(), category=spec["category"],
                 provisions=len(provisions), title=spec["title"], origin=f"{spec['file']} (Data/ của branch PHUC, nạp 08/10/2026)")
    manifest["documents"] = [d for d in manifest["documents"] if d["id"] != spec["id"]] + [entry]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{spec['id']}: {len(provisions)} đoạn từ {len(lines)} dòng; articles = {sorted({p['article'] for p in provisions}, key=int)}")


if __name__ == "__main__":
    build(sys.argv[1])

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from .quality import text_quality


SUPPORTED_SUFFIXES = {".pdf", ".doc", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str
    ocr_used: bool = False


@dataclass(frozen=True)
class ExtractedDocument:
    path: Path
    source_path: str
    title: str
    category: str
    document_type: str
    mime_type: str
    content_sha256: str
    pages: tuple[ExtractedPage, ...]
    ocr_engine: str | None = None

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def ocr_page_count(self) -> int:
        return sum(page.ocr_used for page in self.pages)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_documents(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Thư mục dữ liệu không tồn tại: {root}")
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not any(part.startswith(".") for part in path.relative_to(root).parts)
    )


def _clean_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _ocr_image(image, language: str) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "Trang cần OCR nhưng chưa cài pytesseract/Tesseract. "
            "Dùng Docker legal-indexer hoặc cài requirements-legal.txt."
        ) from exc
    try:
        return _clean_text(pytesseract.image_to_string(image, lang=language, config="--psm 6"))
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError("Không tìm thấy chương trình Tesseract OCR trong PATH") from exc


def _extract_pdf(path: Path, *, language: str, force_ocr: bool, min_text_chars: int) -> tuple[list[ExtractedPage], str | None]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Cần cài PyMuPDF để đọc PDF") from exc

    pages: list[ExtractedPage] = []
    ocr_engine: str | None = None
    with fitz.open(path) as document:
        for index, page in enumerate(document):
            text = _clean_text(page.get_text("text"))
            visible_chars = len(re.sub(r"\s+", "", text))
            # A scanned page can have only a digital-signature text layer. A large
            # image plus sparse native text must still be read, even above 80 chars.
            image_area = max((fitz.Rect(info["bbox"]).get_area()
                              for info in page.get_image_info()), default=0)
            sparse_scan = visible_chars < 500 and image_area > page.rect.get_area() * 0.5
            needs_ocr = (force_ocr or visible_chars < min_text_chars or sparse_scan
                         or text_quality(text) < 0.72)
            if needs_ocr:
                try:
                    from PIL import Image
                except ImportError as exc:
                    raise RuntimeError("Cần cài Pillow để OCR PDF") from exc
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                ocr_text = _ocr_image(image, language)
                # Prefer readable text over a longer corrupt embedded font layer.
                if ocr_text and (not text or text_quality(ocr_text) > text_quality(text) + 0.05
                                 or (text_quality(ocr_text) >= text_quality(text) - 0.05
                                     and len(ocr_text) > visible_chars)
                                 or (sparse_scan and text_quality(ocr_text) >= 0.6)):
                    text = ocr_text
                ocr_engine = "tesseract"
                pages.append(ExtractedPage(index + 1, text, True))
            else:
                pages.append(ExtractedPage(index + 1, text, False))
    return pages, ocr_engine


def _extract_docx(path: Path) -> list[ExtractedPage]:
    # DOCX is a ZIP of XML files. The stdlib implementation keeps the indexer
    # small and preserves paragraph boundaries needed by the legal chunker.
    try:
        with zipfile.ZipFile(path) as archive:
            # Some Windows-exported documents use backslashes inside the ZIP.
            # Read in place: do not rewrite signed sources or extract paths to disk.
            parts = [
                part for part in archive.infolist()
                if part.filename.replace("\\", "/") == "word/document.xml"
            ]
            if len(parts) != 1:
                raise KeyError("Missing or ambiguous Word document part")
            xml = archive.read(parts[0])
        root = ElementTree.fromstring(xml)
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise RuntimeError(f"DOCX không hợp lệ: {path.name}") from exc
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
        if text.strip():
            paragraphs.append(text.strip())
    return [ExtractedPage(1, _clean_text("\n\n".join(paragraphs)))]


def _extract_doc(path: Path) -> list[ExtractedPage]:
    antiword = shutil.which("antiword")
    if antiword:
        completed = subprocess.run(
            [antiword, "-m", "UTF-8.txt", str(path)],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode == 0:
            text = completed.stdout.decode("utf-8", errors="replace")
            return [ExtractedPage(1, _clean_text(text))]
    raise RuntimeError(
        f"Không đọc được {path.name}; định dạng .doc cần antiword (có sẵn trong Docker legal-indexer)"
    )


def extract_document(
    path: Path,
    root: Path,
    *,
    ocr_language: str = "vie+eng",
    force_ocr: bool = False,
    min_text_chars: int = 80,
) -> ExtractedDocument:
    path = path.resolve()
    root = root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError("Tài liệu phải nằm trong thư mục dữ liệu") from exc

    suffix = path.suffix.lower()
    ocr_engine: str | None = None
    if suffix == ".pdf":
        pages, ocr_engine = _extract_pdf(
            path,
            language=ocr_language,
            force_ocr=force_ocr,
            min_text_chars=min_text_chars,
        )
    elif suffix == ".docx":
        pages = _extract_docx(path)
    elif suffix == ".doc":
        pages = _extract_doc(path)
    elif suffix in {".txt", ".md"}:
        pages = [ExtractedPage(1, _clean_text(path.read_text(encoding="utf-8", errors="replace")))]
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        try:
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Cần cài Pillow để OCR ảnh") from exc
        with Image.open(path) as image:
            pages = [ExtractedPage(1, _ocr_image(image, ocr_language), True)]
        ocr_engine = "tesseract"
    else:
        raise ValueError(f"Định dạng chưa hỗ trợ: {suffix}")

    if not any(page.text.strip() for page in pages):
        raise RuntimeError("Không trích xuất được nội dung văn bản")
    category = relative.parts[0] if len(relative.parts) > 1 else "uncategorized"
    return ExtractedDocument(
        path=path,
        source_path=relative.as_posix(),
        title=path.stem,
        category=category,
        document_type=suffix.lstrip("."),
        mime_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        content_sha256=file_sha256(path),
        pages=tuple(pages),
        ocr_engine=ocr_engine,
    )

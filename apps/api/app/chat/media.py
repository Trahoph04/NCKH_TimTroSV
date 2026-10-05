"""Xử lý ảnh gửi trong chat.

Mọi ảnh đều được GIẢI MÃ rồi MÃ HOÁ LẠI thành JPEG:
- xoá toàn bộ EXIF — quan trọng nhất là toạ độ GPS (ảnh chụp phòng trọ bằng điện
  thoại thường kèm vị trí nhà của người gửi);
- chặn file giả đuôi (không decode được ⇒ từ chối), xoay đúng chiều theo EXIF;
- thu nhỏ cạnh dài ≤ 1600px để nhẹ khi demo qua wifi trường.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from ..config import settings

MAX_SIDE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "MPO"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # chặn "decompression bomb"


class MediaError(ValueError):
    pass


def media_root() -> Path:
    root = Path(settings.media_dir) / "chat"
    root.mkdir(parents=True, exist_ok=True)
    return root


def media_path(media_id: str) -> Path:
    # media_id luôn là UUID do server sinh — parse lại để chặn path traversal
    return media_root() / f"{uuid.UUID(str(media_id))}.jpg"


def process_image(raw: bytes) -> dict:
    """Decode → xoay → thu nhỏ → JPEG sạch metadata. Trả {id, w, h, bytes} và ghi file."""
    max_bytes = settings.chat_max_image_mb * 1024 * 1024
    if len(raw) > max_bytes:
        raise MediaError(f"Ảnh vượt quá {settings.chat_max_image_mb}MB")
    try:
        img = Image.open(io.BytesIO(raw))
        fmt = img.format
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise MediaError("File không phải ảnh hợp lệ")
    if fmt not in ALLOWED_FORMATS:
        raise MediaError("Chỉ nhận ảnh JPG, PNG, WEBP hoặc GIF")

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))

    out = io.BytesIO()
    img.save(out, "JPEG", quality=82, optimize=True)  # không truyền exif ⇒ metadata bị bỏ
    data = out.getvalue()

    media_id = str(uuid.uuid4())
    media_path(media_id).write_bytes(data)
    return {"id": media_id, "w": img.width, "h": img.height, "bytes": len(data)}


def delete_files(media_ids: list[str]) -> None:
    for mid in media_ids:
        try:
            media_path(mid).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

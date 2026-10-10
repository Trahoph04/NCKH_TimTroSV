"""Chuẩn bị ảnh bộ dữ liệu khảo sát nhà trọ của nhóm → apps/web/public/khao-sat/ (web phục vụ tĩnh /khao-sat/…).

Mã hoá lại mọi ảnh (bỏ EXIF/GPS dù ảnh gốc có hay không — cùng nguyên tắc ảnh chat), xoay theo EXIF orientation,
giới hạn cạnh dài 1600 px. Tên giữ quy ước của nhóm `<STT 3 số>_<thứ tự>.jpg`. In ra manifest JSON {stt: [url…]}
để `app.crawler.import_survey` gắn ảnh vào tin.

    eval/.venv/bin/python eval/tools/prepare_survey_images.py <thư mục images> > /tmp/survey_images.json
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageOps

MAX_SIDE = 1600
OUT = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "khao-sat"


def main() -> None:
    src = Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[int, list[str]] = defaultdict(list)
    for f in sorted(src.iterdir()):
        m = re.fullmatch(r"(\d{3})_(\d+)\.(jpe?g|png|webp)", f.name, re.I)
        if not m:
            continue
        stt, idx = int(m.group(1)), int(m.group(2))
        im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        name = f"{stt:03d}_{idx}.jpg"
        im.save(OUT / name, "JPEG", quality=85, optimize=True)  # save mới: không mang theo EXIF/ICC gốc
        manifest[stt].append((idx, f"/khao-sat/{name}"))
    print(json.dumps({k: [u for _, u in sorted(v)] for k, v in sorted(manifest.items())}, ensure_ascii=False))


if __name__ == "__main__":
    main()

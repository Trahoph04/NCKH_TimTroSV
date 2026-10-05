"""In phiếu đăng nhập cho buổi thử nghiệm từ eval/data/.credentials.csv.

    python3 eval/tools/print_slips.py [--base-url http://Trahoph.local:3000]
    → eval/data/phieu_dang_nhap.html (mở bằng trình duyệt → In; 8 phiếu/trang A4, cắt theo đường kẻ)

KHÔNG in mật khẩu ra stdout, KHÔNG ghi ra ngoài eval/data/ (đã gitignore). File
HTML chứa mật khẩu — xoá cùng .credentials.csv sau nghiệm thu (ViecConLai mục 6).
Chỉ dùng thư viện chuẩn: chạy được bằng python3 hệ thống, không cần venv.
"""
from __future__ import annotations

import argparse
import csv
import html
import os
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://Trahoph.local:3000")
    ap.add_argument("--src", type=Path, default=DATA / ".credentials.csv")
    ap.add_argument("--out", type=Path, default=DATA / "phieu_dang_nhap.html")
    a = ap.parse_args()

    rows = list(csv.DictReader(a.src.open(encoding="utf-8")))
    url = html.escape(a.base_url.rstrip("/") + "/login")
    slips = []
    for r in rows:
        slips.append(f"""
<div class="slip">
  <div class="t">Trọ CTU · Buổi thử nghiệm ghép bạn ở</div>
  <div class="n">{html.escape(r.get("name") or "")}</div>
  <div class="row"><span>Trang</span><b>{url}</b></div>
  <div class="row"><span>Tab</span><b>MSSV</b></div>
  <div class="row"><span>MSSV</span><b class="m">{html.escape((r.get("mssv") or "").upper())}</b></div>
  <div class="row"><span>Mã đăng nhập</span><b class="m">{html.escape(r.get("password") or "")}</b></div>
  <div class="f">{"" if (r.get("in_pool") or "").lower() in ("1", "true", "t") else "Hồ sơ còn thiếu — vào mục Hồ sơ để điền tiếp. "}Phiếu cá nhân, đừng cho người khác xem.</div>
</div>""")
    page = f"""<!doctype html><meta charset="utf-8"><title>Phiếu đăng nhập</title>
<style>
@page {{ size: A4; margin: 10mm; }}
body {{ font-family: system-ui, sans-serif; margin: 0; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0; }}
.slip {{ border: 1px dashed #999; padding: 6mm; height: 62mm; box-sizing: border-box; break-inside: avoid; }}
.t {{ font-size: 10pt; color: #555; }} .n {{ font-size: 14pt; font-weight: 700; margin: 2mm 0 3mm; }}
.row {{ display: flex; justify-content: space-between; font-size: 11pt; margin: 1mm 0; }}
.m {{ font-family: ui-monospace, monospace; font-size: 13pt; letter-spacing: .5px; }}
.f {{ font-size: 8.5pt; color: #666; margin-top: 3mm; }}
</style><div class="grid">{''.join(slips)}</div>"""
    a.out.write_text(page, encoding="utf-8")
    os.chmod(a.out, 0o600)
    print(f"Đã ghi {len(slips)} phiếu → {a.out} (quyền 600, không commit)")


if __name__ == "__main__":
    main()

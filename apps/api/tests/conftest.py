import os
import sys
from pathlib import Path

# ── Không bao giờ chạy test trên DB dev ─────────────────────────────────────
# PHẢI đứng trước mọi `import app...`: app/config.py đọc DATABASE_URL và
# app/main.py tạo engine NGAY lúc import. Container api đặt DATABASE_URL là DB
# dev `nckh` ⇒ trỏ sang `nckh_test` (infra/db/create_test_db.sh). CI dựng DB mới
# mỗi lần nên cũng có nckh_test (initdb chạy 99-test-db.sh).
# Cố ý dùng DB dev (hiếm khi cần): PYTEST_USE_DEV_DB=1.
_url = os.environ.get("DATABASE_URL", "")
if _url and not os.environ.get("PYTEST_USE_DEV_DB"):
    _base, _, _name = _url.rpartition("/")
    if not _name.endswith("_test"):
        os.environ["DATABASE_URL"] = f"{_base}/{_name}_test"

# cho phép `import app...` khi chạy pytest từ apps/api
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def phongtro_html() -> str:
    return (FIXTURES / "phongtro123_list.html").read_text(encoding="utf-8")


@pytest.fixture
def phongtro_detail_html() -> str:
    return (FIXTURES / "phongtro123_detail.html").read_text(encoding="utf-8")


@pytest.fixture
def tromoi_html() -> str:
    return (FIXTURES / "tromoi_list.html").read_text(encoding="utf-8")


@pytest.fixture
def tromoi_detail_html() -> str:
    return (FIXTURES / "tromoi_detail.html").read_text(encoding="utf-8")


@pytest.fixture
def mogi_html() -> str:
    return (FIXTURES / "mogi_list.html").read_text(encoding="utf-8")


@pytest.fixture
def mogi_detail_html() -> str:
    return (FIXTURES / "mogi_detail.html").read_text(encoding="utf-8")

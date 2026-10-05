"""Nạp khảo sát form v2 (CSV) → tài khoản SV + hồ sơ ở ghép.

    docker cp eval/data/survey_v2.csv "$(docker compose ps -q api)":/tmp/survey.csv
    docker compose exec -T api python -m app.matching.import_survey /tmp/survey.csv --dry-run
    docker compose exec -T api python -m app.matching.import_survey /tmp/survey.csv

CSV do `eval/tools/survey_xlsx_to_csv.py` sinh (container không có openpyxl).

═══ ĐẠO ĐỨC NGHIÊN CỨU — quy tắc ai được tạo tài khoản ═══
Form có hai nhánh rẽ, và PHẢI tôn trọng cả hai:

  F1 "muốn dùng thử?" = KHÔNG  ⇒ người đó CHỈ đồng ý tham gia khảo sát, KHÔNG
     đồng ý để hồ sơ mình xuất hiện cho SV khác xem/quẹt. Họ không có tên/MSSV
     trong phản hồi, và ta KHÔNG tạo hồ sơ cho họ. Dữ liệu lối sống của họ vẫn
     dùng được để hiệu chỉnh trọng số (nằm trong phạm vi đồng ý của khảo sát) —
     nhưng chỉ ở notebook eval, đọc từ CSV, KHÔNG vào DB.

  Phần D (lối sống) bỏ trống ⇒ không tính được điểm ⇒ tạo tài khoản (họ đã đồng
     ý dùng thử) nhưng KHÔNG tạo hồ sơ ghép; app sẽ mời họ điền.

Mật khẩu sinh ngẫu nhiên mỗi người, ghi ra file CỤC BỘ không commit
(eval/data/.credentials.csv — `eval/data/` đã nằm trong .gitignore) để in phiếu
phát tại buổi thử nghiệm. Không log, không in ra stdout, xoá sau nghiệm thu.
"""
from __future__ import annotations

import argparse
import csv
import secrets
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

from ..config import settings
from . import survey_map as sm
from .profile import DEAL_BREAKER, HANH_VI

# Bỏ 0/O/1/l/I: phiếu in ra phải đọc được không nhầm, SV gõ tay lúc đăng nhập.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


def make_password(n: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def map_row(row: dict) -> dict | None:
    """CSV → giá trị cột. None = không đủ điều kiện tạo tài khoản.

    Trả kèm `has_lifestyle` để caller biết có tạo hồ sơ ghép hay không.
    """
    # /auth/login/ctu chuẩn hoá về CHỮ HOA khi tra cứu ⇒ phải lưu cùng dạng,
    # nếu không SV gõ đúng MSSV vẫn bị 401.
    mssv = (row.get("mssv") or "").strip().upper()
    email = (row.get("email") or "").strip().lower()
    name = (row.get("full_name") or "").strip()
    if not mssv or not email:
        return None  # không đồng ý dùng thử (nhánh F1 = Không)
    if not (row.get("is_ctu") or "").startswith("Có"):
        return None  # không phải SV CTU

    smoke, smoke_in_room, infer_db = sm.smoking(row.get("smoking"))
    hanh_vi, extra_hv = sm.split_multi(row.get("behaviors"), HANH_VI)
    dbs, extra_db = sm.split_multi(row.get("deal_breakers"), DEAL_BREAKER)
    dbs = sm.deal_breakers_with_smoking(dbs, infer_db)

    prof = {
        "gender": sm.gender(row.get("gender")),
        "don_vi": (row.get("don_vi") or "").strip() or None,
        "budget_band": sm.budget_band(row.get("budget")),
        "scenario": sm.scenario(row.get("plan")),
        "sleep_time": sm.sleep_time(row.get("sleep_time")),
        "cleanliness": sm.cleanliness(row.get("dishes")),
        "noise_tolerance": sm.noise_tolerance(row.get("noise_reaction")),
        "ac_usage": sm.ac_usage(row.get("ac_usage")),
        "money_style": sm.money_style(row.get("money_style")),
        "persona": sm.persona(row.get("persona")),
        "smoke": smoke,
        "smoke_in_room": smoke_in_room,
        "hanh_vi": hanh_vi or None,
        "deal_breakers": dbs or None,
        "need_from": (row.get("need_from") or "").strip()[:40] or None,
        "roommate_status": (row.get("roommate_status") or "").strip()[:60] or None,
    }
    return {
        "row_no": row.get("row_no"),
        "mssv": mssv,
        "email": email,
        "name": name,
        "profile": prof,
        # Phần D bỏ trống ⇒ chỉ tạo tài khoản, không tạo hồ sơ ghép
        "has_lifestyle": prof["sleep_time"] is not None or prof["cleanliness"] is not None,
        "unknown_tokens": extra_hv + extra_db,
    }


def run(csv_path: Path, cred_path: Path, dry_run: bool) -> int:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    mapped = [m for m in (map_row(r) for r in rows) if m]

    unknown = [(m["row_no"], m["unknown_tokens"]) for m in mapped if m["unknown_tokens"]]
    if unknown:
        # Token lạ = form đã đổi lựa chọn ⇒ deal-breaker sẽ không đối chiếu được
        # với DB_TO_HANHVI và lọc cứng âm thầm mất hiệu lực. Dừng, đừng nạp bừa.
        print("LỖI: có lựa chọn không khớp danh sách option của form v2:", file=sys.stderr)
        for rn, toks in unknown:
            print(f"  dòng {rn}: {toks}", file=sys.stderr)
        print("Cập nhật HANH_VI/DEAL_BREAKER trong matching/profile.py rồi chạy lại.", file=sys.stderr)
        return 2

    in_pool = [m for m in mapped if m["has_lifestyle"] and m["profile"]["gender"]]
    print(f"CSV            : {len(rows)} phản hồi")
    print(f"Đồng ý dùng thử: {len(mapped)} (có MSSV + email + là SV CTU)")
    print(f"Vào pool ghép  : {len(in_pool)} (có phần D + có khai giới tính)")
    by_gender: dict[str, int] = {}
    for m in in_pool:
        g = m["profile"]["gender"]
        by_gender[g] = by_gender.get(g, 0) + 1
    print(f"  theo giới    : {by_gender}")
    print(f"Chỉ tài khoản  : {len(mapped) - len(in_pool)} (chưa khai lối sống/giới tính)")

    if dry_run:
        print("\n--dry-run: không ghi gì vào DB.")
        return 0

    from ..auth.security import hash_password

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    creds: list[dict] = []
    created = updated = 0

    with engine.begin() as conn:
        for m in mapped:
            password = make_password()
            pwd_hash = hash_password(password)

            # users.email là UNIQUE NOT NULL — dùng chính email SV khai trong form.
            # email_verified=TRUE: email đến từ Google Form đã đăng nhập bằng tài
            # khoản @student.ctu.edu.vn nên đã được Google xác thực.
            uid = conn.execute(
                text(
                    "INSERT INTO users (email, name, password_hash, email_verified) "
                    "VALUES (:e, :n, :p, TRUE) "
                    "ON CONFLICT (email) DO UPDATE SET "
                    "  name = COALESCE(NULLIF(EXCLUDED.name, ''), users.name) "
                    "RETURNING id, (created_at > now() - INTERVAL '5 seconds') AS is_new"
                ),
                {"e": m["email"], "n": m["name"], "p": pwd_hash},
            ).mappings().one()
            user_id, is_new = uid["id"], uid["is_new"]
            created += 1 if is_new else 0
            updated += 0 if is_new else 1

            # Đăng nhập bằng MSSV: provider='ctu' (40_auth.sql đã hỗ trợ).
            # Giữ secret_hash riêng khỏi users.password_hash để sau này cắm SSO
            # CTU thật thì chỉ bỏ secret_hash, không đụng bảng users.
            conn.execute(
                text(
                    "INSERT INTO user_identities (user_id, provider, provider_user_id, secret_hash) "
                    "VALUES (:u, 'ctu', :mssv, :sh) "
                    "ON CONFLICT (provider, provider_user_id) DO UPDATE SET secret_hash = EXCLUDED.secret_hash"
                ),
                {"u": user_id, "mssv": m["mssv"], "sh": pwd_hash},
            )

            if m["has_lifestyle"]:
                prof = {k: v for k, v in m["profile"].items() if v is not None}
                cols = sorted(prof)
                conn.execute(
                    text(
                        f"INSERT INTO roommate_profiles (user_id, {', '.join(cols)}, "
                        "is_simulated, src, updated_at) VALUES "
                        f"(:user_id, {', '.join(':' + c for c in cols)}, FALSE, 'form', now()) "
                        "ON CONFLICT (user_id) DO UPDATE SET "
                        + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols)
                        + ", is_simulated = FALSE, src = 'form', updated_at = now()"
                    ),
                    {"user_id": user_id, **prof},
                )

            creds.append({
                "mssv": m["mssv"], "name": m["name"], "email": m["email"],
                "password": password, "user_id": user_id,
                "in_pool": "yes" if m["has_lifestyle"] else "no",
            })

    cred_path.parent.mkdir(parents=True, exist_ok=True)
    with cred_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["mssv", "name", "email", "password", "user_id", "in_pool"])
        w.writeheader()
        w.writerows(creds)
    cred_path.chmod(0o600)

    print(f"\n✓ tài khoản mới {created} · cập nhật {updated}")
    print(f"✓ mật khẩu ghi ra {cred_path} (chmod 600, KHÔNG commit, xoá sau nghiệm thu)")
    print("  Đăng nhập: POST /auth/login/ctu  {mssv, password}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path, help="CSV từ eval/tools/survey_xlsx_to_csv.py")
    ap.add_argument("--credentials", type=Path, default=Path("/tmp/.credentials.csv"))
    ap.add_argument("--dry-run", action="store_true", help="chỉ đếm, không ghi DB")
    a = ap.parse_args()
    if not a.csv.is_file():
        sys.exit(f"Không thấy CSV: {a.csv}")
    sys.exit(run(a.csv, a.credentials, a.dry_run))


if __name__ == "__main__":
    main()

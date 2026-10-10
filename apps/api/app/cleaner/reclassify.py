"""Áp classifier mới lên tin đã làm sạch (nha_mini, sửa từ khoá mặt bằng, "Trọ …").

  docker compose exec api python -m app.cleaner.reclassify           # chỉ in thay đổi
  docker compose exec api python -m app.cleaner.reclassify --apply   # ghi DB
"""
import argparse

from sqlalchemy import create_engine

from app.config import settings

from .pipeline import reclassify


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="ghi DB (mặc định chỉ in)")
    args = ap.parse_args()
    engine = create_engine(settings.database_url)
    changes = reclassify(engine, apply=args.apply)
    for (old, new), n in sorted(changes.items(), key=lambda kv: -kv[1]):
        print(f"{old:>24} → {new:<24} {n}")
    print(f"tổng {sum(changes.values())} tin {'ĐÃ GHI' if args.apply else '(dry-run, thêm --apply để ghi)'}")


if __name__ == "__main__":
    main()

"""Ảnh chụp danh mục ứng viên cho notebook 01 (offline) — đúng dữ liệu API đang xếp hạng.

  docker compose exec -T api python -m app.recommend.export_snapshot > eval/data/rec_candidates.csv

Chỉ đặc trưng tin trọ công khai (giá, phút, tiện ích nhắc tới, toạ độ…), không có liên hệ/PII.
"""
import csv
import sys

from sqlalchemy import create_engine

from app.config import settings

from .repo import RecommendRepo

COLUMNS = ["id", "price", "m0", "m1", "m2", "amenities", "free_hours", "listing_type", "gender_only",
           "lat", "lng", "market_pois", "quality"]


def main() -> None:
    w = csv.writer(sys.stdout)
    w.writerow(COLUMNS)
    for c in RecommendRepo(create_engine(settings.database_url)).candidates():
        w.writerow([c.id, c.price, *("" if m is None else m for m in c.minutes), "|".join(sorted(c.amenities)),
                    "" if c.free_hours is None else int(c.free_hours), c.listing_type or "", c.gender_only or "",
                    c.lat, c.lng, c.market_pois, c.quality])


if __name__ == "__main__":
    main()

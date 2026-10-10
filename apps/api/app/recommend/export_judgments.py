"""Xuất phán đoán của buổi đánh giá mù ra CSV cho notebook 01 (mục online).

  docker compose exec -T api python -m app.recommend.export_judgments > eval/data/rec_judgments.csv

KHÔNG có tên/email/MSSV: người chấm = mã băm của user_id (đủ để ghép các thẻ cùng một người, không lần ngược
ra danh tính nếu không có DB). Schema cố định — notebook 01 đọc đúng các cột này.
"""
import csv
import hashlib
import json
import sys

from sqlalchemy import create_engine

from app.config import settings

from .repo import RecommendRepo

COLUMNS = [
    "rater", "session_id", "algo_ver", "budget", "campus", "max_minutes", "housing", "n_required",
    "top_factors", "relaxed", "listing_id", "display_pos", "rank_proposed", "rank_price", "rank_cosine",
    "utility", "relevance", "completed",
]


def main() -> None:
    rows = RecommendRepo(create_engine(settings.database_url)).export_rows()
    w = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
    w.writeheader()
    for r in rows:
        crit = r["criteria"] if isinstance(r["criteria"], dict) else json.loads(r["criteria"])
        w.writerow({
            "rater": hashlib.sha256(f"rec:{r['user_id']}".encode()).hexdigest()[:10],
            "session_id": r["session_id"], "algo_ver": r["algo_ver"],
            "budget": crit.get("budget"), "campus": crit.get("campus"), "max_minutes": crit.get("max_minutes"),
            "housing": crit.get("housing") or "", "n_required": len(crit.get("required") or []),
            "top_factors": "|".join(crit.get("top_factors") or []), "relaxed": "|".join(r["relaxed"] or []),
            "listing_id": r["listing_id"], "display_pos": r["display_pos"],
            "rank_proposed": r["rank_proposed"] or "", "rank_price": r["rank_price"] or "",
            "rank_cosine": r["rank_cosine"] or "", "utility": "" if r["utility"] is None else round(r["utility"], 4),
            "relevance": "" if r["relevance"] is None else r["relevance"],
            "completed": int(r["completed_at"] is not None),
        })


if __name__ == "__main__":
    main()

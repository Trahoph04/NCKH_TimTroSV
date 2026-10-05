"""Xuất điểm chấm làm mù 1–5 ra CSV cho notebook 06_roommate_eval.

    docker compose exec -T api python -m app.matching.export_ratings > eval/data/ratings.csv

SCHEMA CỐ ĐỊNH — notebook đọc theo tên cột, đổi ở đây phải đổi cả notebook:
    rater_id, round, card_code, target_id, arm (algo|random), algo_rank (1..3|rỗng),
    display_pos, score, s_ab, s_ba, weights_ver, target_is_simulated (0|1),
    rater_is_simulated (0|1), rating (1..5|rỗng = chưa chấm), served_at, rated_at

Có id người dùng (không có tên/email/MSSV) ⇒ vẫn ghi vào eval/data/ (đã gitignore),
không commit.
"""
from __future__ import annotations

import csv
import sys

from sqlalchemy import create_engine, text

from ..config import settings

COLUMNS = (
    "rater_id", "round", "card_code", "target_id", "arm", "algo_rank", "display_pos",
    "score", "s_ab", "s_ba", "weights_ver", "target_is_simulated", "rater_is_simulated",
    "rating", "served_at", "rated_at",
)


def main() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT r.rater_id, r.round, r.card_code, r.target_id, r.arm, r.algo_rank, "
                "r.display_pos, r.score, r.s_ab, r.s_ba, r.weights_ver, "
                "CAST(r.target_is_simulated AS INT) AS target_is_simulated, "
                "CAST(COALESCE(rp.is_simulated, FALSE) AS INT) AS rater_is_simulated, "
                "r.rating, r.served_at, r.rated_at "
                "FROM roommate_ratings r "
                "LEFT JOIN roommate_profiles rp ON rp.user_id = r.rater_id "
                "ORDER BY r.rater_id, r.round, r.display_pos"
            )
        ).mappings().all()
    w = csv.writer(sys.stdout)
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow(["" if r[c] is None else r[c] for c in COLUMNS])


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# Crawl lại toàn bộ + trích liên hệ, địa chỉ chuẩn, review Google Maps.
#   bash recrawl_all.sh              # đầy đủ
#   bash recrawl_all.sh --no-google  # bỏ bước Google Places (chưa có API key)
#   bash recrawl_all.sh --quick      # crawl incremental thay vì full
# Log: logs/recrawl_<ngày>.log
set -uo pipefail
cd "$(dirname "$0")"
MODE="full"; GOOGLE=1
for a in "$@"; do
  [ "$a" = "--quick" ] && MODE="incremental"
  [ "$a" = "--no-google" ] && GOOGLE=0
done
mkdir -p logs; LOG="logs/recrawl_$(date +%Y%m%d_%H%M).log"
say(){ echo -e "\n=== $* ===" | tee -a "$LOG"; }
run(){ echo "\$ $*" >>"$LOG"; "$@" 2>&1 | tee -a "$LOG"; }

say "0. Build lại api với code mới"
run docker compose up -d --build api db

say "1. Migration 90 + 91 (idempotent)"
for m in 90_extras_reviews 91_contact_address; do
  docker compose exec -T db psql -U nckh -d nckh -v ON_ERROR_STOP=1 \
    < "infra/db/migrations/${m}.sql" >>"$LOG" 2>&1 \
    && echo "  ✓ $m" | tee -a "$LOG" || echo "  ✗ $m — xem $LOG" | tee -a "$LOG"
done

say "2. Chờ API sẵn sàng"
for i in $(seq 1 30); do
  curl -fsS http://localhost:8000/health >/dev/null 2>&1 && { echo "  API ok"; break; }
  sleep 2
done

say "3. Crawl lại mọi nguồn (mode=$MODE)"
for s in phongtro123 tromoi mogi bds123 nhadatcantho nhadatcantho247 nhatot; do
  echo "  → $s" | tee -a "$LOG"
  # chạy trong container (không qua HTTP): POST /crawler/run chỉ dành cho admin từ 12/10
  docker compose exec -T api python -m app.crawler.run_once --source "$s" --mode "$MODE" 2>&1 \
    | tee -a "$LOG" || echo "  ✗ $s lỗi (bỏ qua, chạy tiếp)" | tee -a "$LOG"
  echo | tee -a "$LOG"
done

say "4. Trích lại thuộc tính mềm + liên hệ + địa chỉ cho TOÀN BỘ tin"
run docker compose exec -T api python -m app.crawler.backfill_extras --all
run docker compose exec -T api python -m app.crawler.backfill_contact_address --all

if [ "$GOOGLE" = "1" ]; then
  say "5. Review + SĐT từ Google Maps (Places API New)"
  run docker compose exec -T api python -m app.reviews_crawl.google_places --grid
  docker compose cp api:/app/google_reviews.csv eval/data/google_reviews.csv 2>/dev/null \
    && echo "  ✓ eval/data/google_reviews.csv" | tee -a "$LOG"
else
  say "5. Bỏ qua Google Places (--no-google)"
fi

say "6. Xuất CSV để kiểm tra"
bash infra/db/export_data.sh | tee -a "$LOG"

say "XONG — log: $LOG"

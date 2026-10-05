#!/usr/bin/env bash
# Tạo database `nckh_test` cho pytest — tách khỏi DB dev `nckh`.
#
# Vì sao: pytest chạy thẳng trên DB dev thì mỗi lần ~600 user rác + tin trọ
# "Phong tro test" hiện trên trang tìm kiếm + deck toàn thẻ "SV · 100%" (GOTCHAS).
# tests/conftest.py tự trỏ sang nckh_test khi DATABASE_URL đang là DB dev.
#
# Chạy ở 2 chỗ:
#   · tự động khi cluster init (Dockerfile COPY thành 99-test-db.sh)
#   · tay trên DB đang chạy:  docker compose exec -T db bash /usr/local/bin/create_test_db.sh
#     (thêm --recreate để xoá và dựng lại từ đầu)
# Áp ĐÚNG các file trong /docker-entrypoint-initdb.d theo thứ tự tên — cùng
# nguồn với DB dev nên lược đồ không lệch nhau.
set -euo pipefail

DB_USER="${POSTGRES_USER:-nckh}"
TEST_DB="${TEST_DB:-nckh_test}"

if [[ "${1:-}" == "--recreate" ]]; then
    psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$TEST_DB\" WITH (FORCE)"
fi

if psql -U "$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$TEST_DB'" | grep -q 1; then
    echo "create_test_db: $TEST_DB đã có — bỏ qua (dùng --recreate để dựng lại)"
    exit 0
fi

psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d postgres -c "CREATE DATABASE \"$TEST_DB\" OWNER \"$DB_USER\""
for f in /docker-entrypoint-initdb.d/*.sql; do
    psql -q -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$TEST_DB" -f "$f" > /dev/null
done
echo "create_test_db: đã tạo $TEST_DB"

#!/usr/bin/env bash
# ====================================================================
# Reset database and load seed data for NCKH project
# ====================================================================

set -e

echo "🔄 Đang khởi tạo lại Database và nạp Seed Data..."

# Dừng container db cũ và xóa volume dữ liệu
docker compose stop db
docker compose rm -f db
docker volume rm -f nckh_pgdata

# Khởi động lại container db
echo "🚀 Đang khởi động PostgreSQL container..."
docker compose up -d db --build

# Chờ database sẵn sàng
echo "⏳ Đang đợi PostgreSQL khởi động và nạp dữ liệu mẫu..."
# KHÔNG dùng pg_isready qua unix socket: trong lúc chạy docker-entrypoint-initdb.d,
# entrypoint dựng một server TẠM chỉ nghe socket ⇒ pg_isready báo sẵn sàng khi
# migration còn đang chạy (race). Server tạm không nghe TCP, nên hỏi qua
# 127.0.0.1 rồi kiểm luôn bảng của migration CUỐI đã tồn tại.
until docker compose exec -T db psql -h 127.0.0.1 -U nckh -d nckh -tAc \
        "SELECT 1 FROM roommate_ratings LIMIT 0" > /dev/null 2>&1; do
    sleep 2
done

echo "✅ Database đã sẵn sàng với toàn bộ Migrations và Seed Data mẫu!"
echo "📊 Các tài khoản mẫu có thể dùng để test (Mật khẩu: secret):"
echo "   - Admin: admin@ctu.edu.vn"
echo "   - Sinh viên Nam: nguyenvana@ctu.edu.vn (MSSV: B2101234)"
echo "   - Sinh viên Nữ: tranthib@ctu.edu.vn (MSSV: B2205678)"
echo "   - Chủ trọ: chutro.xuanhuong@gmail.com"

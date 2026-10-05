<#
.SYNOPSIS
    Reset database và nạp dữ liệu mẫu (Seed Data) cho dự án NCKH.
.DESCRIPTION
    Script này sẽ:
    1. Rebuild / Khởi động lại container PostgreSQL db.
    2. Chạy toàn bộ migrations từ 10-init.sql đến 80_seeds.sql.
#>

Write-Host "🔄 Đang khởi tạo lại Database và nạp Seed Data..." -ForegroundColor Cyan

# Kiểm tra docker có đang chạy không
docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker chưa được bật! Vui lòng khởi động Docker Desktop trước." -ForegroundColor Red
    exit 1
}

# Dừng container db cũ và xóa volume cũ nếu muốn làm sạch hoàn toàn
docker compose stop db
docker compose rm -f db
docker volume rm -f nckh_pgdata

# Khởi động lại db container
Write-Host "🚀 Đang khởi động PostgreSQL container..." -ForegroundColor Yellow
docker compose up -d db --build

# Chờ database sẵn sàng
Write-Host "⏳ Đang đợi PostgreSQL khởi động và nạp dữ liệu mẫu..." -ForegroundColor Yellow
$retries = 15
while ($retries -gt 0) {
    $status = docker compose exec -T db pg_isready -U nckh -d nckh 2>$null
    if ($LASTEXITCODE -eq 0) {
        break
    }
    Start-Sleep -Seconds 2
    $retries--
}

if ($retries -eq 0) {
    Write-Host "⚠️ Không thể kết nối database kịp thời, vui lòng kiểm tra docker logs." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Database đã sẵn sàng với toàn bộ Migrations và Seed Data mẫu!" -ForegroundColor Green
Write-Host "📊 Các tài khoản mẫu có thể dùng để test (Mật khẩu: 123456):" -ForegroundColor Cyan
Write-Host "   - Admin: admin@ctu.edu.vn"
Write-Host "   - Sinh viên Nam: nguyenvana@ctu.edu.vn (MSSV: B2101234)"
Write-Host "   - Sinh viên Nữ: tranthib@ctu.edu.vn (MSSV: B2205678)"
Write-Host "   - Chủ trọ: chutro.xuanhuong@gmail.com"

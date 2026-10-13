# Dữ liệu database

Repo **không chứa database** — Postgres nằm trong Docker volume `pgdata`, đã gitignore.
`docker compose up -d --build` chạy các init script trong `infra/db/Dockerfile` để tạo
cấu trúc, và (từ nay) nạp luôn dữ liệu mẫu.

Có 3 nguồn dữ liệu, dùng tuỳ mục đích:

## 1. Seed mẫu tự động — `migrations/80_seeds.sql`

Lấy từ nhánh nhóm trên GitHub. Đã nối vào `infra/db/Dockerfile` nên **tự nạp khi volume rỗng**,
không cần lệnh gì thêm:

- **5 tin** quanh CTU (4 phòng trọ + 1 nhà nguyên căn), tất cả có toạ độ và
  `route_time_campus` sẵn → bản đồ hiện được "X phút tới trường" **kể cả khi chưa có `ORS_API_KEY`**
- **4 tài khoản** demo, mật khẩu `123456`: `admin@ctu.edu.vn`, `nguyenvana@ctu.edu.vn`,
  `tranthib@ctu.edu.vn`, `chutro.xuanhuong@gmail.com`
- 2 hồ sơ ghép bạn ở, 2 saved search, 5 user_interaction (data mồi cho module AI)

Dùng cho: máy mới, onboard thành viên, demo, chạy test.

## 2. Seed dữ liệu crawl thật — `seed/aggregated_listings_seed.sql`

Dump 82 tin crawl thật từ phongtro123 / mogi / tromoi (đã qua bộ làm sạch, 81 tin có toạ độ,
44 tin phòng-trọ-sạch). Không chứa bảng `users`. Nạp thủ công:

```bash
docker compose exec -T db psql -U nckh -d nckh < infra/db/seed/aggregated_listings_seed.sql
```

Id trong file đã được dịch lên dải **1001–1082** để không trùng id 1–5 của seed mẫu,
nên nạp chồng lên seed được, không lỗi trùng khoá. Kết quả: 87 tin.

Tạo lại file này sau khi crawl thêm — **nhớ dịch id**, nếu không sẽ trùng với seed mẫu:

```bash
docker compose exec -T db pg_dump -U nckh -d nckh --data-only --table=aggregated_listings > /tmp/dump.sql
```

```bash
awk 'BEGIN{FS=OFS="\t"} /^COPY public\.aggregated_listings /{i=1;print;next} i&&/^\\\.$/{i=0;print;next} i{$1=$1+1000;print;next} {print}' /tmp/dump.sql > infra/db/seed/aggregated_listings_seed.sql
```

## 3. Tự crawl — dữ liệu tươi nhất

```bash
docker compose exec -T api python -m app.crawler.run_once --source phongtro123 --mode incremental
# (HTTP POST /crawler/run cần token admin từ 12/10/2026)
```

Đổi `source` sang `mogi`, `tromoi`, `bds123`, `nhadatcantho`, `nhadatcantho247`.
Endpoint tự chạy `run_cleaner` nên data ra thẳng trạng thái `cleaned`. Scheduler cũng
tự crawl mỗi 5 giờ khi `CRAWLER_ENABLED=true`. Mỗi nguồn mất vài phút.

## Gotcha: volume cũ KHÔNG nhận init script mới

Init script **chỉ chạy lần đầu khi volume rỗng**. Volume `pgdata` đã tồn tại từ build trước
sẽ không nhận migration/seed mới → ví dụ lỗi `column "route_time_campus" does not exist`,
hoặc build xong mà bảng vẫn rỗng.

Dựng lại từ đầu (xoá hết dữ liệu hiện có):

```bash
docker compose down -v && docker compose up -d --build
```

Hoặc dùng script có sẵn của nhóm — chỉ reset riêng container db:

```bash
./infra/db/reset_and_seed.sh
```

Trên Windows PowerShell: `.\infra\db\reset_and_seed.ps1`

Muốn giữ dữ liệu, chỉ apply riêng file còn thiếu:

```bash
docker compose exec -T db psql -U nckh -d nckh < infra/db/migrations/80_seeds.sql
```

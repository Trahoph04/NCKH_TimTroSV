# Hướng Dẫn Triển Khai (Deployment Guide)
## Hệ thống tổng hợp & gợi ý nhà trọ AI — THS2026-66

**Phiên bản:** 1.0 · **Nguyên tắc P1:** chi phí 0đ trong thời gian đề tài

---

## 1. Môi trường

| Môi trường | Mục đích | Hạ tầng |
|---|---|---|
| Local (dev) | Phát triển | Docker Compose (db + redis + api + web) |
| Staging | Demo/nghiệm thu | Free-tier: Vercel (web) + Render (api) + Supabase (PG) |
| Production | Sau đề tài (tùy chọn) | VPS Ubuntu + Nginx + Let's Encrypt (~$10/tháng, ngoài phạm vi) |

---

## 2. Local — Docker Compose

```bash
# 1. cấu hình env
cp .env.example .env

# 2. build + chạy 4 service
docker compose up --build

# 3. kiểm tra
curl http://localhost:8000/health/deps   # postgis + pgvector + redis = ok
open http://localhost:3000               # web
open http://localhost:8000/docs          # API OpenAPI
```

Bật crawler tự động: set `CRAWLER_ENABLED=1` trong `.env` rồi restart api.
Trigger thủ công: `docker compose exec -T api python -m app.crawler.run_once --source phongtro123 --mode incremental`
(HTTP `POST /crawler/run` cần token **admin** từ 12/10/2026; `source` phải thuộc `ENABLED_SOURCES`, một nguồn chỉ chạy 1 lượt cùng lúc — trùng ⇒ 409).

Migration DB chạy tự động lần đầu (`infra/db/migrations/*.sql` qua initdb). Reset sạch:
```bash
docker compose down -v   # XÓA volume pgdata — mất hết data, dùng cẩn thận
```

---

## 3. Staging — Free-tier

### 3.1 Database (Supabase / Neon)
- Tạo project PostgreSQL free-tier. Bật extension: `CREATE EXTENSION postgis; CREATE EXTENSION vector;`
- Chạy `infra/db/migrations/20_listings.sql` qua SQL editor.
- Lấy connection string → `DATABASE_URL`.

### 3.2 Backend API (Render / Railway)
- Deploy `apps/api` (Dockerfile sẵn).
- Env: `DATABASE_URL`, `REDIS_URL`, `CRAWLER_ENABLED`, secret JWT, Gemini API key.
- Lưu ý: free-tier sleep khi idle — crawler scheduler có thể không chạy đều; dùng cron gọi `python -m app.crawler.run_once` trong container (HTTP `/crawler/run` cần token admin).

### 3.3 Redis (Upstash free-tier)
- Tạo Redis → lấy `REDIS_URL`.

### 3.4 Frontend (Vercel)
- Deploy `apps/web` (Next.js standalone).
- Env: `NEXT_PUBLIC_API_URL` = URL backend Render.

---

## 4. Production VPS (tùy chọn, sau đề tài)

```
Internet → Nginx (443, Let's Encrypt) ┬→ /api  → FastAPI (uvicorn, systemd)
                                       └→ /     → Next.js (node, systemd)
                                          PostgreSQL + Redis (local hoặc managed)
```

Bước chính:
1. VPS Ubuntu 22.04, cài Docker + Docker Compose.
2. Clone repo, `cp .env.example .env`, điền secret production.
3. `docker compose up -d`.
4. Nginx reverse proxy + `certbot --nginx` cấp SSL.
5. Firewall: chỉ mở 80/443; DB/Redis không expose ra ngoài.

---

## 5. Checklist bảo mật trước khi public

- [ ] `.env` không commit (đã trong `.gitignore`).
- [ ] JWT secret + DB password mạnh, không dùng default `nckh/nckh`.
- [ ] HTTPS bắt buộc (Let's Encrypt / Vercel auto).
- [ ] DB + Redis không expose port public.
- [ ] Rate-limit API public.
- [ ] OWASP ZAP scan (SQLi/XSS) pass — Sprint 5.2.
- [ ] CORS chỉ cho domain frontend.

---

## 6. Vận hành

- **Monitoring crawler:** `GET /crawler/status` xem N lần crawl gần nhất; alert khi `new_count < 10` hoặc `error != null`.
- **Backup DB:** `pg_dump` định kỳ (managed PG thường tự backup).
- **Log:** uvicorn log + crawl_runs table.
- **Cập nhật nguồn crawl:** sửa/thêm `apps/api/app/crawler/sources/<source>.json`, deploy lại — không cần đổi code.

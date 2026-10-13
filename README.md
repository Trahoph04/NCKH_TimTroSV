# Trọ CTU — Hệ thống hỗ trợ sinh viên Đại học Cần Thơ tìm nhà trọ

Đề tài nghiên cứu khoa học sinh viên **THS2026-66** — Trường Công nghệ Thông tin & Truyền thông, Đại học Cần Thơ.
_Xây dựng hệ thống có ứng dụng trí tuệ nhân tạo hỗ trợ sinh viên Đại học Cần Thơ tìm nhà trọ._

## Chức năng

- **Tìm trọ**: tin tổng hợp từ 6 nguồn + dữ liệu khảo sát thực địa của nhóm, đã làm sạch (phân loại, kiểm giá, khử trùng,
  rà soát tin hết hạn/tin mẫu); lọc theo giá, quận, khoảng cách, diện tích, loại chỗ ở.
- **Bản đồ** (MapLibre + OpenStreetMap): icon nhà trọ/tiện ích, số phút đi xe tới khu I/II/III của CTU, đường đi, tiện ích
  trong 1 km (chợ, siêu thị, ATM, nhà thuốc, bệnh viện, xe buýt); phân biệt vị trí chính xác và vị trí cấp phường.
- **Gợi ý nhà trọ** theo tiêu chí (knowledge-based: lọc + MAUT với trọng số từ khảo sát sinh viên + MMR đa dạng hoá).
- **Ghép bạn ở** (Gower có trọng số + harmonic, lọc cứng 2 tầng) và **chat realtime** (WebSocket + Redis) giữa hai người đã
  ghép, chia sẻ liên hệ khi cả hai đồng ý.
- **Trợ lý AI** (RAG: BM25 + vector E5, Gemini/Qwen): tìm phòng bằng câu hỏi tự nhiên, hỏi đáp pháp lý thuê trọ và ký túc xá
  CTU, trả lời có trích nguồn.
- **Cẩm nang**: ký túc xá CTU (nguồn chính thức của trường), lưu ý khi tìm phòng, ở ghép, pháp lý & hợp đồng.
- **Đánh giá nhà trọ** của sinh viên (sao + tag cảnh báo); **quản trị**: nhà trọ, người dùng, kiểm duyệt đánh giá.

## Kiến trúc

| Thành phần | Thư mục | Công nghệ |
|---|---|---|
| Backend | `apps/api` | FastAPI, SQLAlchemy Core, Python 3.12 |
| Frontend | `apps/web` | Next.js 14 (App Router), TypeScript, Tailwind, MapLibre GL |
| Cơ sở dữ liệu | `infra/db` | PostgreSQL 16 + PostGIS 3.4 + pgvector (migration SQL thuần) |
| Hàng đợi/pub-sub | — | Redis 7 |
| Đánh giá | `eval` | notebook gợi ý (01) và ghép bạn (06) |

## Chạy thử (Docker)

```bash
git clone git@github.com:Trahoph04/NCKH_TimTroSV.git && cd NCKH_TimTroSV
cp .env.example .env          # đặt JWT_SECRET; ORS_API_KEY (miễn phí) để có số phút + đường đi; GEMINI_API_KEY cho trợ lý AI
docker compose up -d --build  # web http://localhost:3000 · API http://localhost:8000/docs
```

Lần đầu, cơ sở dữ liệu tự tạo bảng + dữ liệu mẫu (tài khoản, tiện ích OSM). Tin trọ thật do crawler thu thập
(`docker compose exec -T api python -m app.crawler.run_once --source phongtro123 --mode incremental`) hoặc nạp gói dữ liệu
nhóm gửi riêng. Trợ lý AI cần nạp kho tài liệu: `docker compose exec api python -m app.room_service.legal_knowledge.index_corpus`.

Tài khoản mẫu (chỉ để chạy thử, đổi mật khẩu nếu triển khai thật): `admin@ctu.edu.vn` / `secret` (quản trị),
`nguyenvana@ctu.edu.vn` / `secret` (sinh viên). Chi tiết: [`docs/DEMO.md`](docs/DEMO.md),
[`docs/reference/Deployment_Guide.md`](docs/reference/Deployment_Guide.md).

Kiểm thử backend (cần Postgres thật, DB riêng `nckh_test`):

```bash
docker cp apps/api/tests/. "$(docker compose ps -q api)":/app/tests/ && docker compose exec -T api python -m pytest -q
```

## Tài liệu

- [`docs/CHECKPOINT.md`](docs/CHECKPOINT.md) — trạng thái và nhật ký từng phiên làm việc
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — quyết định kiến trúc (ADR)
- [`docs/GOTCHAS.md`](docs/GOTCHAS.md) — các bẫy đã gặp
- [`docs/report/`](docs/report) — báo cáo chức năng & phương pháp, báo cáo kiểm thử
- `docs/specs/`, `docs/tech_specs/` — thiết kế và mô tả sau triển khai từng phần

## Không có trong repo

Khoá API (`.env`), dữ liệu khảo sát có thông tin cá nhân (`eval/data/`), gói dữ liệu Chợ Tốt nội bộ, bản xuất dữ liệu có số
điện thoại chủ trọ — gửi riêng trong nhóm, không công khai.

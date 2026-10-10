# Chatbot Trọ CTU — as-built (08/10/2026)

Ghép từ branch `origin/PHUC` @445f89d (tác giả: Phúc). Quyết định ghép: ADR-023. Tài liệu gốc đầy đủ (flow agent Gemini/Qwen,
đánh giá 36 câu, RAGAS) nằm ở `docs/CHATBOT.md` **trên branch đó** — file này chỉ ghi phần khác đi khi ghép vào repo này.

## 1. Chức năng

- **Tìm trọ** bằng câu tự nhiên: parser rút giá/diện tích/quận/tiện ích/giới tính/khoảng cách/phút → lọc SQL + BM25 + vector
  E5 trên `aggregated_listings` (chỉ tin `visible_clause()`), xếp hạng có lý do ("Trong ngân sách", "Khớp ngữ nghĩa"…).
- **KTX CTU + pháp lý thuê trọ** (hợp đồng, cọc, điện nước, cư trú, PCCC, môi giới, dữ liệu cá nhân, lừa đảo): truy xuất lai
  tsvector + vector trên corpus `legal_ctu_v1`, trả lời có trích dẫn `[n]`, bộ kiểm chứng claim loại phát biểu không có căn cứ.
- **Lịch sử theo tài khoản** + dùng lại câu trả lời (riêng → dùng chung → sinh mới). Ngoài phạm vi: soạn hợp đồng, điền CT01.

## 2. Thành phần

| Phần | Đường dẫn |
|---|---|
| API | `apps/api/app/room_service/chatbot/` (router `/chatbot`, service, repo, parser, providers, history…) |
| Kho văn bản | `apps/api/app/room_service/legal_knowledge/` (+ `admin.py` → `/admin/documents`) |
| Indexer corpus | `python -m app.room_service.legal_knowledge.index_corpus [--prune]` |
| Indexer tin | `python -m app.room_service.chatbot.index_listings [--all]` |
| Corpus | `apps/api/chatbot_corpus/` — 44 JSON (40 pháp lý/hướng dẫn v16 + 4 KTX 07/10) + `manifest.json` (sha256, nguồn gốc) |
| Migration | `infra/db/migrations/100_chatbot.sql` (COPY `98c-chatbot.sql`) |
| Web | `apps/web/src/app/tro-ly/{ChatbotWidget,ChatbotAnswer,page}.tsx`, `layout.tsx` gắn widget, `api/chatbot/[...path]` |
| Test | `apps/api/tests/test_chatbot*.py`, `test_chat_history.py` (DB opt-in `RUN_CHAT_HISTORY_DB_TESTS=1`), `test_legal_*`… |

## 3. Khác branch PHUC

| Điểm | PHUC | Repo này | Vì sao |
|---|---|---|---|
| Prefix | `/chat` | `/chatbot` | `/chat/conversations` đã là chat ghép bạn |
| Rate limit | `auth.lifecycle.rate_limit` (bảng `request_buckets`) | `ratelimit.check_rate("chatbot")` | không ghép auth lifecycle |
| Lọc tin | `source='user' OR cleaned` | `visible_clause()` | không gợi ý tin UI đang ẩn |
| Loại mặc định | `phong_tro` | mọi loại đang hiện (+ `nha_mini` khi hỏi "minihouse") | catalog PHUC không có nhà mini |
| Key tiện ích | `private_bathroom`, `refrigerator`, `flexible_hours`, `mezzanine`, `pets_allowed` | `private_wc`, `fridge`, `free_hours`; bỏ gác/thú cưng | theo `crawler/normalize.parse_amenities` |
| Giới tính | `parsed_amenities->>'gender'` | cột `gender_only` | dữ liệu repo này |
| Corpus | chuỗi schema v7→v16→`legal_ctu_ktx_v2` + graph | 1 schema `legal_ctu_v1`, nạp 1 bước | các schema kia chỉ có ở DB máy Phúc |
| Tin cho chatbot | `housing_graph_word_repair_v16` (catalog riêng) | `public.aggregated_listings` | thấy đúng tin + khảo sát của nhóm |
| Graph RAG / agent | bật | tắt (cần graph + key Gemini) | |
| Ollama | `qwen3.5:9b` | `qwen2.5:7b-instruct` | model có sẵn trên máy dev |
| Web | widget `chat/ChatClient.tsx` | `tro-ly/ChatbotWidget.tsx`, màu theo token Tailwind; ẩn ở `/chat`; né nút zoom `/map` và MiniMap | |

## 4. Vận hành

```bash
docker compose up -d --build api                   # INSTALL_ML=true mặc định (torch CPU + sentence-transformers)
docker compose exec -T db psql -U nckh -d nckh -v ON_ERROR_STOP=1 < infra/db/migrations/100_chatbot.sql   # DB đang chạy
docker compose exec api python -m app.room_service.legal_knowledge.index_corpus    # 44 tài liệu / 530 đoạn / 530 vector
docker compose exec api python -m app.room_service.chatbot.index_listings          # sau mỗi crawl/import
ollama serve                                         # trên máy host; API gọi http://host.docker.internal:11434
curl localhost:8000/health/ai
```

Cấu hình (`app/config.py`, truyền qua `docker-compose.yml`): `CHATBOT_LLM_PROVIDER` (auto|qwen|gemini|template),
`CHATBOT_LEGAL_SCHEMA` (`legal_ctu_v1`), `OLLAMA_MODEL`, `GEMINI_API_KEY[_1.._3]`, `GEMINI_MODEL`, `CHATBOT_AGENTS_ENABLED`,
`CHATBOT_LLM_TIMEOUT_SECONDS` (60), `CHATBOT_LEGAL_TIMEOUT_SECONDS` (180). Key Gemini chỉ đặt trong `.env`.

### Đặt khoá Gemini (bắt buộc để chatbot đạt chất lượng demo)

1. Tạo khoá ở https://aistudio.google.com/apikey bằng tài khoản Google của nhóm (từ 2026 khoá có dạng `AQ.…`; dạng cũ `AIza…` vẫn dùng được).
2. Mở `.env`, thêm dòng `GEMINI_API_KEY=<khoá>` (không dấu ngoặc, không khoảng trắng thừa). **Không** đặt khoá vào chat, docs, commit.
3. `docker compose up -d api`, rồi `docker compose exec api python -m app.room_service.chatbot.check_llm --call`: lệnh này in khoá
   có hợp lệ không, `GEMINI_MODEL` / `GEMINI_FALLBACK_MODEL` có trong danh sách mô hình của khoá không (đổi trong `.env` nếu
   thiếu), và gọi thử một câu. Chỉ khi lệnh báo ✓ mới xem là xong.
4. Tuỳ chọn: `CHATBOT_AGENTS_ENABLED=true` bật luồng Gemini phân tích → Qwen chọn nguồn → Gemini tổng hợp/kiểm chứng (đúng luồng
   Phúc đo 36 câu); tắt thì Gemini sinh câu trả lời trực tiếp, Qwen dự phòng. Hạn mức gói miễn phí giới hạn tốc độ — mã đã
   giãn cách `GEMINI_MIN_REQUEST_INTERVAL_SECONDS=5` giữa các lần gọi.
5. Báo cáo nghiệm thu phải ghi đúng tên mô hình thật. Số liệu chatbot của Phúc (36 câu, RAGAS) tạo qua proxy cục bộ với bí
   danh `gemini-3.8-flash-high` — chính báo cáo của Phúc ghi "chưa xác minh mô hình nền", nên chỉ dùng làm tham khảo; chạy lại
   bằng mô hình có tên rõ ràng nếu cần trích số.

## 5. Kết quả kiểm 08/10

**Cập nhật tối 08/10 — đã có khoá Gemini** (`gemini-3.5-flash-lite`, Qwen dự phòng, luồng nhiều tác nhân tắt): xem CHECKPOINT mục "Chatbot — Gemini đã bật". Bảng dưới là lần đo SÁNG, chỉ có Qwen — giữ để so sánh.

### Lần đo sáng (chưa có key Gemini)

| Câu | Kết quả |
|---|---|
| "Tìm phòng trọ dưới 2 triệu ở Ninh Kiều có máy lạnh" | hybrid, 5 tin đúng giá/quận, 2,7 s (template) |
| "Có minihouse nào dưới 3 triệu gần ĐHCT" | 5 tin `nha_mini` 2,5–2,9 tr |
| "Phòng trọ mới xây có gác đường Mậu Thân khoảng 2 triệu" | tin khảo sát KS-010 đứng #1 |
| "Chủ trọ được thu tiền điện bao nhiêu theo quy định?" | trích nguyên văn K5 Đ12 TT 60/2025/TT-BCT + điều kiện hiệu lực |
| "Tân sinh viên đăng ký KTX CTU như thế nào?" | đúng 3 nguồn CTU; Qwen 7B bị bác claim ⇒ template (73 s) |
| "Đặt cọc… chủ trọ không cho thuê nữa thì sao?" | trích Điều 328 BLDS, đánh dấu trả lời một phần (85 s) |

pytest: 563 passed, 20 skip, 1 xfail (`test_incomplete_exception_is_not_safe_evidence` — fail sẵn trên code PHUC gốc).
Test lịch sử DB opt-in: 22/22.

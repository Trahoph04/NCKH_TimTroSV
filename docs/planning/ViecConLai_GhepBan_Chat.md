# Việc còn lại — Ghép bạn ở + Chat realtime

_Cập nhật: 05/10/2026 · sau các phiên 04–05/10 · Nguồn: rà soát code 04/10 (7 agent đọc toàn bộ module) + kiểm thực tế trên DB/browser_

> **Mốc thời gian** (theo `KeHoach_NghiemThu_T10.md`): buổi thử nghiệm người dùng xếp ở tuần 28/09–04/10 · **code freeze 08/10** (còn 3 ngày) · nghiệm thu 12–16/10.
> Mục 1 dưới đây là những việc **chặn buổi thử nghiệm** — làm trước mọi thứ khác.

---

## Trạng thái hiện tại (đã xong, đã kiểm)

| Phần | Trạng thái | Kiểm bằng |
|---|---|---|
| Thuật toán ghép (lọc cứng 2 tầng · Gower · harmonic · Stable Roommates) | ✅ | 51 test + chạy trên 19 hồ sơ thật |
| API `/matching/profile` `/deck` `/swipe` `/likes` `/passed` | ✅ | test + curl |
| Đăng nhập MSSV (`POST /auth/login/ctu`) — **chỉ ở API** | ⚠️ | xem 1.2 |
| 10 tài khoản từ khảo sát (9 vào pool: nam 6 / nữ 3) | ✅ | DB |
| 24 hồ sơ mô phỏng có nhãn (pool nữ 2 → 18) | ✅ | 23 test |
| Trang `/roommate` | ✅ | browser |
| Chat realtime + 6 defect backend + 2 defect FE | ✅ | test + browser |
| T3 lộ liên hệ khi cả hai đồng ý | ✅ | 11 test + browser (realtime 38 ms) |
| `pytest` | **225 passed**, 2 skip (test cần CSV trong container) | |

---

## 1. ƯU TIÊN CAO — chặn buổi thử nghiệm / nghiệm thu

### 1.1 Commit toàn bộ code ⛔
Repo chỉ có **1 commit** (`Initial commit`). Toàn bộ chat, matching, migration 92/93, trang `/roommate`, test… đều **chưa được version** (`git status` báo `??`). Mất máy hoặc một lệnh `git checkout`/`clean` sai là mất hết.
- Commit theo nhóm (`feat: matching …`, `feat: chat realtime …`, `fix: …`, `test: …`, `docs: …`) theo quy ước trong `CLAUDE.md`.
- **Kiểm trước khi `git add`**: `eval/data/` (PII + mật khẩu) và `eval/.venv/` đã nằm trong `.gitignore` — chạy `git check-ignore -v eval/data/.credentials.csv` để chắc.
- _Ước lượng: 30 phút._

### 1.2 SV thật KHÔNG đăng nhập được trên web ⛔
Tài khoản từ khảo sát chỉ có identity `provider='ctu'` (MSSV). Form `/login` chỉ có ô **email** → gọi `/auth/login` (tìm identity `local`) → **401**. Đường MSSV hiện chỉ dùng được bằng `curl`.
- Thêm tab "Đăng nhập bằng MSSV" vào `apps/web/src/app/login/LoginForm.tsx` + Route Handler proxy tới `/auth/login/ctu`.
- _Ước lượng: 30–45 phút._

### 1.3 Thẻ mô phỏng chiếm gần hết deck — cần QUYẾT ĐỊNH
Deck của SV nữ thật đang **7/8 thẻ là hồ sơ mô phỏng** (12 mô phỏng so với 3 thật). Hồ sơ mô phỏng **không bao giờ thích lại** ⇒ SV quẹt nhiều mà không ra match thật ⇒ buổi thử nghiệm vẫn không sinh dữ liệu match. Chọn một (hoặc kết hợp):
- **(a)** Ưu tiên hồ sơ thật khi xếp deck (`matching/repo.py:deck`) — đơn giản nhất.
- **(b)** Giới hạn tỉ lệ thẻ mô phỏng mỗi deck (vd. ≤ 50%).
- **(c)** Đặt sẵn quyết định swipe cho hồ sơ mô phỏng (thiết kế mục 3.5 ý 5) — để tài khoản demo chắc chắn có match bật ra trên sân khấu. Phải ghi nhãn rõ và loại khỏi mọi số liệu.

### 1.4 Chế độ `deck_mode=random` cho buổi thử nghiệm — FE chưa gọi được
Backend đã hỗ trợ (`GET /matching/deck?mode=random` ẩn %/lý do, thứ tự tất định), nhưng `/roommate` luôn gọi bản `ranked`. Thiết kế 3.6 yêu cầu buổi thử nghiệm dùng thứ tự ngẫu nhiên, **không hiện %**, để khử thiên lệch vị trí — không có thì số liệu thu được không dùng được cho đánh giá.
- Thêm cờ (vd. `/roommate?mode=random`, hoặc biến môi trường cho buổi thử nghiệm) truyền xuống `RoommateApp.tsx`.
- _Ước lượng: 20 phút._

### 1.5 Chưa có công cụ thu điểm chấm 1–5
Kế hoạch ghi "đánh giá top-3 ghép bạn 1–5"; thiết kế 2.7 dùng 5 thẻ làm mù (3 của thuật toán + 2 ngẫu nhiên trong pool) chấm 1–5 → Wilcoxon + P@3/NDCG@3. Trang `/roommate` chỉ có **thích/bỏ qua**, không có ô chấm điểm.
- Phương án nhanh nhất: Google Form in sẵn mã thẻ; hoặc một trang `/roommate/rate` nhỏ.
- **Phải chốt schema CSV trước** để notebook (1.6) đọc thẳng được.

### 1.6 Notebook `eval/notebooks/06_roommate_eval.ipynb`
Chưa có. `eval/metrics.py` đã được agent thêm `gini`, `kendall_tau`, `wilcoxon_signed_rank`, `coverage_at_least_one`, `cosine_similarity` (+212 dòng) — **chưa kiểm**, và không được làm hỏng `01_recommendation_eval.ipynb` đang import file này.
Các mục cần có, chạy được ngay với dữ liệu hôm nay:
1. Thực trạng pool theo từng tầng lọc, theo giới
2. Cosine vs Gower (đã đo: ngưỡng 0,7 cho **93%** cặp qua) — có biểu đồ
3. Harmonic vs trung bình cộng (đã đo: harmonic thấp hơn ở **171/171** cặp)
4. Bảng ablation ≥ 4 dòng (cosine/Gower · trọng số đều/khảo sát · có/không lọc cứng · cộng/harmonic) + **lọc cứng 1 tầng vs 2 tầng** (6/19 → 16/19)
5. Độ nhạy trọng số ±20% → Kendall τ thứ hạng top-5
6. Đường cong độ phủ theo N (bootstrap N = 30/60/100/200/500) — ghi rõ là mô phỏng
7. Stable Roommates theo giới (đã đo: pool nữ **có** ghép ổn định, pool nam **không**)
8. Congestion: Gini của exposure (đếm từ `deck_log`)
9. P@3 / NDCG@3 / Wilcoxon — chờ dữ liệu 1.5; dựng sẵn khung, placeholder **ghi nhãn rõ ràng**
- Cần venv riêng (`eval/.venv`, đã gitignore) vì máy không có numpy/pandas.
- _Ước lượng: 3–4 giờ._

### 1.7 Dọn dữ liệu test trước buổi thử nghiệm
- Tài khoản `trahoph0404k5@gmail.com` (id 25) còn **11 swipe** + 3 match test (với user 23, 24 — demo — và user 92 — khảo sát). Để lại sẽ lẫn vào số liệu nghiên cứu.
  ```bash
  docker compose exec -T db psql -U nckh -d nckh -c "DELETE FROM swipes WHERE user_id=25 OR target_id=25; DELETE FROM match_requests WHERE from_user=25 OR to_user=25;"
  ```
- Xoá user do `pytest` sinh sau mỗi lần chạy test (lệnh ở `docs/GOTCHAS.md`, gồm tiền tố `mt_` `chat_` `t3_`).
- In phiếu mật khẩu từ `eval/data/.credentials.csv` cho buổi thử nghiệm.

---

## 2. Thuật toán ghép — phần thiết kế chưa cài

| # | Việc | Ở đâu | Ghi chú |
|---|---|---|---|
| 2.1 | **ε-greedy** cho thứ tự deck (80% theo điểm, 20% ngoài vùng an toàn) | `matching/repo.py:deck` | Thiết kế 3.4 [R3]. Thiếu thì mô hình chỉ học vùng nó đã tin (vòng phản hồi). |
| 2.2 | Lọc cứng **thời điểm cần phòng** | `matching/filters.py` | Cột `need_from` đã thêm ở mig 93 nhưng **chưa dùng**. |
| 2.3 | Deck buổi thử nghiệm phải **có độ tản** — chèn ứng viên vượt tiêu chí MỀM (lệch ngân sách, lệch kịch bản) | `deck(mode="random")` | Thiết kế 3.6. Không bao giờ chèn ứng viên vi phạm lọc an toàn. |
| 2.4 | Mất tín hiệu `decided_ms` (thời gian quyết định) | `matching/repo.py:swipe` | Đã bỏ khỏi body (không tin client). Tính lại phía server: `swipe.created_at − deck_log.served_at`. |
| 2.5 | Đường **gửi lời mời kèm lời nhắn** | `/matching/invite`, `/invite/{id}/respond`, `/invites` | Thiết kế 2.10 + 3.5 ý 3 — giữ song song với swipe vì match 2 chiều nhân đôi tỉ lệ rụng. |
| 2.6 | `create_match` ghi đè `status='accepted'` | `matching/repo.py:create_match` | Ghép lại sau khi huỷ ⇒ **mất vết `unmatched`** trong thống kê. |
| 2.7 | `pass` sau khi đã match để lại hội thoại | `matching/repo.py:swipe` | Swipe đổi thành pass nhưng conversation vẫn còn. |
| 2.8 | Học trọng số từ swipe (hồi quy logistic, L2, leave-one-user-out CV, AUC ± CI) | notebook | Thiết kế 3.4 — **chỉ làm sau khi có dữ liệu buổi thử nghiệm**. Đưa ≤ 5–6 chiều vào mô hình. |
| 2.9 | Không có rate limit cho swipe / tin nhắn / báo cáo | router | |

---

## 3. Chat — lỗi còn tồn (từ rà soát 04/10, CHƯA sửa)

**Major**

| File | Lỗi | Hậu quả |
|---|---|---|
| `apps/web/src/middleware.ts:29` | Cổng chỉ xét cookie **tồn tại**; trang thì `redirect("/login?next=…")` | Cookie hỏng (sau `reset_and_seed`, đổi `JWT_SECRET`) ⇒ **vòng redirect vô hạn**, `ERR_TOO_MANY_REDIRECTS`, không vào được trang login. `/roommate` thừa hưởng lỗi này. |
| `apps/web/src/app/chat/MessageItem.tsx:84` | Ảnh đơn không áp `w`/`h` server trả về | Ảnh tải xong làm **trượt cuộn** khỏi đáy hội thoại. |
| `apps/web/src/lib/chat/client.ts:73,78` | `CHAT_WS_URL` không chuẩn hoá; scheme `ws/wss` lấy từ `NEXT_PUBLIC_API_URL` thay vì từ trang | **Realtime chết im lặng sau tunnel HTTPS** (cloudflared). Chặn hướng "test ngoài LAN". |
| `docs/tech_specs/Chat_Realtime.md:31,97` | Tài liệu khẳng định fan-out nhiều worker + chế độ Redis chết | **Chưa từng được test**. Hội đồng hỏi là lộ. |
| — | `CHECKPOINT.md` nói có bộ e2e Playwright | **Không tồn tại trong repo.** |

**Minor**

| File | Lỗi |
|---|---|
| `ChatApp.tsx:242` | `user_message_count` +1 **hai lần** cho mỗi tin mình gửi (response POST + tiếng vọng WS) |
| `ChatApp.tsx` (`match.new`) | Bỏ qua `conversation_id` ⇒ phía **bị động** không có khoảnh khắc "Thành đôi!" |
| `ChatThread.tsx:88` | Đổi hội thoại khi đang gõ ⇒ đối phương thấy "Đang nhập…" thêm 6s |
| `ChatApp.tsx` (`sendImages`) | Object URL ảnh xem trước bị rò khi gửi thất bại hẳn / rời trang |
| `ChatNavLink.tsx:19` | Bỏ số `likes` endpoint trả về; badge bị xoá về 0 khi vào `/chat` trước khi danh sách tải xong |
| `middleware.ts:33` | Query string trong `next` bị mã hoá vào path ⇒ 404 |
| `chat/router.py:243` + `repo.py:270` | TOCTOU: đối phương huỷ ghép giữa lúc kiểm quyền và lúc ghi ⇒ `scalar_one()` ⇒ **500** thay vì 404 |
| `chat/router.py:291` | WebSocket `accept()` **trước** khi kiểm vé; không giới hạn số socket mỗi user |
| `chat/router.py:335` | Mỗi frame "đang nhập" tốn 1 kết nối DB |
| `chat/repo.py:134` | `GET /chat/conversations` không LIMIT, không phân trang, mỗi dòng 2 subquery + LATERAL |
| `chat/router.py:201` | Upload ảnh giới hạn số byte ĐỌC nhưng không giới hạn số byte NHẬN (Starlette đã spool hết) |
| `chat/router.py:262` | Ảnh mồ côi không có GC (xoá file sau commit; xoá user cascade mất vết) |
| `chat/hub.py:112` | `_get_redis`/`_start_listener` check-then-act ngoài lock ⇒ có thể 2 worker psubscribe |
| `chat/hub.py:139` | `_on_redis_message` lấy `env['text']` không kiểm ⇒ 1 envelope hỏng làm worker pubsub ném lỗi |
| `chat/repo.py:93` | Đối phương bị xoá tài khoản ⇒ GET hội thoại 404 nhưng GET tin nhắn vẫn chạy |

**Thiếu tính năng (UI)** — ưu tiên thấp: chú thích cho ảnh (backend đã lưu) · hiện avatar (đang luôn là chữ viết tắt) · thẻ "Lời mời" hiện ít hơn dữ liệu `/likes` trả · báo cáo/chặn từ tab Lời mời · kéo-thả / dán ảnh · kiểm dung lượng ảnh phía client · tin đã chia sẻ chỉ 6 cái.

---

## 4. Dữ liệu · seed · hạ tầng

| # | Việc | Ghi chú |
|---|---|---|
| 4.1 | 2 hồ sơ cũ (user 2, 3) có `gender = NULL` ⇒ **ngoài pool vĩnh viễn** | `80_seeds.sql` chạy **trước** mig 92 (thứ tự `COPY` trong `infra/db/Dockerfile`) nên ghi `gender_pref` (cột đã ngưng dùng) mà không có `gender`. |
| 4.2 | `80_seeds.sql` ghi mật khẩu là `123456` nhưng hash là của `secret` | Đã ghi ở GOTCHAS; sửa luôn chú thích cho khỏi nhầm. |
| 4.3 | `reset_and_seed.sh:21` dùng `pg_isready` qua unix socket | Báo sẵn sàng khi entrypoint còn đang chạy init ⇒ race. |
| 4.4 | **pytest ghi thẳng vào DB dev** | Mỗi lần chạy ~60–80 user rác; đã từng tích 459 user, làm deck hiện toàn "100%". Sửa triệt để: DB test riêng hoặc rollback mỗi test (đụng `conftest.py` + engine tạo ở import-time). |
| 4.5 | 2 test `test_simulate.py` cần CSV trong container | `docker cp eval/data/survey_v2.csv "$(docker compose ps -q api)":/tmp/survey.csv` — mất sau mỗi lần rebuild api. |
| 4.6 | Test ngoài LAN (4G, máy khác mạng) | Cần tunnel + `CHAT_WS_URL`; vướng lỗi `client.ts` ở mục 3. Mạng trường có thể bật client isolation, và IP Wi-Fi đổi liên tục (đã đổi 2 lần trong vài phút) — trong LAN dùng `http://Trahoph.local:3000`. |

---

## 5. Tài liệu cần sửa cho khớp với code

| File | Sửa |
|---|---|
| `docs/planning/SRS.md` FR-5.1 | "6 câu forced-choice" → 12 câu theo form v2 |
| `docs/planning/SRS.md` FR-5.2 | "Weighted Cosine ≥ 0.7" → Gower có trọng số + harmonic mean + top-K (ADR-013) |
| `docs/planning/SRS.md` FR-5 | Thêm chính sách **chỉ ghép cùng giới** (`gender NULL` → ngoài pool) và **deal-breaker 2 tầng** (ADR-014) |
| `docs/reference/API_Specification.md` | Mục matching (`/profile` `/deck` `/swipe` `/likes` `/passed`) + `/auth/login/ctu` + mục chat (gồm `contact-consent`) |
| `docs/planning/KeHoach_NghiemThu_T10.md` mục 1.2 + kịch bản demo mục 5 | Bỏ "cắt nhắn tin, thay bằng Zalo"; demo = match → "Thành đôi!" → chat → T3 |
| `Thuyet_Minh_Bo_Sung.md` mục 10.2 | Thêm tài liệu tham khảo: [R12] RECON (Pizzato 2010) · [R13] RRS survey (Palomares 2021) · [R14] Gower (1971) · [R15] Revisiting RRS (arXiv 2408.09748, 2024) · [R16] Fair Reciprocal Recommendation (RecSys 2024) · [R17] Irving (1985) Stable Roommates · [R18] weighted Gower (BMC Med Res Methodol 2024) |
| `docs/tech_specs/Matching_Messaging_Design.md` | Cập nhật: lọc cứng 2 tầng (thay mục 2.4 bước 1), Stable Roommates, `deck_log` |
| `docs/tech_specs/Chat_Realtime.md` | Thêm `pair_dev`, `contact.consent`; gỡ hoặc test các khẳng định chưa kiểm (mục 3) |
| `Matching_Messaging_Design.md` 1.7 ↔ code | Tài liệu đạo đức hứa chat **text-only, không ảnh/file**, nhưng chat đang có gửi ảnh ⇒ phải sửa một trong hai |
| `apps/web/src/lib/chat/types.ts` | Dời `ContactState`/`ContactPartner` từ `ProfilePanel.tsx` về đây (lúc viết agent không được sửa file dùng chung) |

---

## 6. Đạo đức dữ liệu — làm SAU nghiệm thu (10/2026)

- `DELETE FROM messages;` + xoá file ảnh trong volume `media` (cam kết mục 1.7 thiết kế; ghi vào `Deployment_Guide.md`)
- Xoá `eval/data/` (CSV có họ tên · MSSV · email thật) và `eval/data/.credentials.csv`
- Xoá hồ sơ mô phỏng: `docker compose exec -T api python -m app.matching.simulate --reset --count 0`
- Xoá các tài khoản cấp cho buổi thử nghiệm nếu không còn dùng

---

## 7. Quyết định đang chờ

1. **Thẻ mô phỏng chiếm deck** — chọn (a) / (b) / (c) ở mục 1.3.
2. **3 SV thật** mà tài khoản id 25 đã "quan tâm" (user 93, 96, 98) — **không** tự bấm quan tâm ngược từ tài khoản của họ, vì như vậy là tạo ra sự quan tâm họ chưa từng bày tỏ.
3. **Chat có ảnh hay text-only** — mâu thuẫn tài liệu ↔ code ở mục 5.
4. **Rút lại đồng ý T3** — hiện đồng ý là một chiều, không có endpoint rút lại. Có cần không?
5. **`scheduler.py` từng ở chế độ read-only** (`-r--r--r--`) — đã mở quyền ghi để sửa lỗi chặn event loop. Nếu read-only là cố ý thì cần biết.

# Ghép bạn ở ghép + Nhắn tin — Phân tích & thiết kế

> **Đối chiếu as-built 06/10/2026.** Các mục dưới đây đã được sửa cho khớp code: 1.4/1.7/1.8 (chat **có gửi ảnh**,
> đã re-encode xoá EXIF — quyết định 05/10 thay cho cam kết text-only), 2.4 bước 1 (lọc cứng **2 tầng**, ADR-014),
> bổ sung 2.4b (Stable Roommates) và 2.4c (`deck_log`, chọn thẻ, ε-greedy, độ tản). Phần còn lại là thiết kế gốc.

_Lập: 26/09/2026 · Lane: Phú (matching, core) + Huy/Bảo (UI) · Mốc: code freeze 08/10, nghiệm thu 12–16/10_

> Trả lời 2 câu hỏi đang treo: (1) **nhắn tin: WebSocket hay liên kết Zalo?** (2) **ghép bạn ở: 30 hồ sơ thì làm collaborative filtering thế nào?**
> Kết luận ngắn: **không WebSocket, cũng không Zalo-một-mình** → chat HTTP polling trong app + Zalo là bước bàn giao cuối. Và **không làm collaborative filtering** — bài toán này thuộc họ *Reciprocal Recommender System*, CF là sai công cụ chứ không phải thiếu dữ liệu.

---

## 0. Bối cảnh — đối chiếu code ngày 26/09

| Đã có trong code | Chưa có |
|---|---|
| `roommate_profiles`, `match_requests` (migration `30_users.sql`) | `apps/api/app/matching/` — **chưa tồn tại** |
| Auth JWT + `get_current_user` (`auth/deps.py`) | Bảng/API nhắn tin — chưa có |
| `users.phone`, listings có `contact_zalo` (mig 91) | `import_survey.py` (CSV form → DB) |
| Form v2 chốt xong (`tao_google_form_v2.gs`, có `BANG_DOI_CHIEU`) | ~30 phản hồi vẫn nằm trên Google Sheet, chưa vào DB |
| Convention router/repo/`init_*(engine)` đã ổn định | Notebook `06_roommate_eval` |

**Thực tế lịch:** `KeHoach_NghiemThu_T10.md` xếp matching API vào tuần 1 (14–20/09). Hôm nay 26/09, `apps/api/app/` chỉ có `auth/ cleaner/ crawler/ listings/ reviews_crawl/` — tuần 1 và 2 của 4 module AI **chưa bắt đầu**. Còn **12 ngày** tới code freeze. Mọi lựa chọn dưới đây được chọn theo tiêu chí "rẻ nhất mà vẫn đủ nghiệm thu", không theo tiêu chí kỹ thuật đẹp nhất.

---

# PHẦN I — NHẮN TIN

## 1.1 Ba phương án

| | **A. WebSocket** | **B. Chỉ link Zalo** | **C. Chat HTTP polling + Zalo (đề xuất)** |
|---|---|---|---|
| Công sức | 3–5 ngày | 1 giờ | **1,5–2 ngày** |
| Hạ tầng thêm | Redis pub/sub (multi-worker), quản lý connection, reconnect, auth qua WS, presence | 0 | 0 — dùng đúng engine + Bearer token đang có |
| Rủi ro lúc demo | Cao: socket rớt trên sân khấu là chết tính năng | Thấp | Thấp: request rời rạc, rớt 1 nhịp thì nhịp sau tự bù |
| Trả lời được "Phần 5 thuyết minh" | Có | **Yếu** — 1 deep link không phải "chức năng nhắn tin" | Có |
| Giữ được lời hứa riêng tư đã cam kết trong form | Có | **Không** (xem 1.2) | Có |
| Số liệu cho báo cáo | 0 | 0 | 0 |
| Giá trị khoa học | 0 | 0 | 0 — nhưng **cơ chế lộ danh tính 3 tầng** thì có (1.4) |

Ba chữ số cột "số liệu cho báo cáo" đều là 0: **nhắn tin không sinh metric nào cho NCKH**. Nên nguyên tắc duy nhất khi chọn là *rẻ và không làm sập demo*, đừng đầu tư gì thêm vào đây. Thời gian dư dồn hết sang matching + eval.

## 1.2 Vì sao KHÔNG thể chỉ dùng link Zalo — lý do quyết định

Form khảo sát đã phát cho ~30 SV ghi nguyên văn (`tao_google_form_v2.gs`, phần F):

> "Người được ghép chỉ nhìn thấy TÊN và TÓM TẮT THÓI QUEN SINH HOẠT của bạn. MSSV và thông tin liên hệ của bạn CHỈ hiện ra sau khi CẢ HAI BÊN cùng bấm đồng ý kết nối."

Nếu kênh liên lạc duy nhất là `zalo.me/<sđt>` thì **lời mời đầu tiên đã phải lộ số điện thoại** — không có cách nào để hai người trao đổi vài câu rồi mới quyết định có cho nhau số hay không. Tức là:

- vi phạm cam kết đã gửi cho người tham gia khảo sát (vấn đề đạo đức nghiên cứu, hội đồng hỏi là mất điểm nặng);
- mâu thuẫn với FR-5.3 trong SRS ("B chấp nhận → lộ liên hệ 2 chiều") — lộ liên hệ phải là *kết quả* của kết nối, không phải *điều kiện* để bắt đầu;
- bỏ Zalo-một-mình cũng không "an toàn dữ liệu hơn" như mục 1.2 của `KeHoach_NghiemThu_T10.md` lập luận: nó chỉ chuyển dữ liệu riêng tư của SV sang **bên thứ ba** thay vì mình tự giữ. Lập luận đúng phải là *giảm thiểu* (chat text-only, có hạn lưu trữ), không phải *đẩy sang chỗ khác*.

→ **Cần một kênh trong app đủ để nói chuyện trước khi lộ liên hệ.** Rẻ nhất để có kênh đó là polling, không phải WebSocket.

## 1.3 Vì sao KHÔNG WebSocket

1. **Demo 2 tài khoản, polling 3s nhìn y như real-time.** Không ai trong hội đồng phân biệt được 0ms và 3s khi người demo tự gõ cả hai đầu.
2. Auth qua WebSocket không dùng lại được `HTTPBearer` hiện tại (header không gắn được vào `WebSocket` từ browser) → phải làm token qua query param hoặc cookie riêng = sửa vào tầng auth đang chạy ổn. Rủi ro lan sang chức năng khác.
3. Nhiều worker uvicorn thì connection nằm ở process khác nhau → cần Redis pub/sub để fan-out. Redis đang có nhưng chưa dùng cho việc gì, thêm 1 đường dữ liệu mới = thêm 1 chỗ hỏng.
4. Offline delivery / unread badge / reconnect backoff vẫn phải tự viết — WebSocket không cho không cái nào.
5. Không đổi được thành **bất kỳ dòng số liệu nào** trong Chương 4.

Nếu sau nghiệm thu muốn nâng: **SSE (`EventSource`) trước, WebSocket sau.** SSE một chiều server→client, đi qua Route Handler proxy của Next (đã có httpOnly cookie nên `EventSource` không cần header), giữ nguyên `POST /messages` để gửi. Đổi từ polling sang SSE tốn ~1 giờ và không phá API. Ghi vào "hướng phát triển".

## 1.4 Thiết kế: lộ danh tính theo 3 tầng (phần đáng viết vào báo cáo)

Đây là chỗ duy nhất của chức năng nhắn tin có nội dung để viết — trình bày nó như một **quyết định thiết kế bảo vệ quyền riêng tư**, không phải như một màn hình chat:

| Tầng | Người kia thấy gì | Mở khi nào |
|---|---|---|
| **T1 — Ẩn danh** | Tên hiển thị (tên gọi, không MSSV), giới tính, Trường/Khoa, tóm tắt thói quen, % tương thích + lý do | Ngay khi vào danh sách gợi ý |
| **T2 — Nhắn tin** | + chat 1-1 trong app (chữ, ảnh đã xoá EXIF, chia sẻ tin trọ) | **Cả hai** đã thích nhau (swipe 2 chiều, hoặc nhận lời mời) |
| **T3 — Liên hệ ngoài** | + SĐT / link `zalo.me/<sđt>` | **Cả hai** bấm "Cho phép xem liên hệ" trong khung chat (một lần nữa, riêng với tầng T2) |

Hai lần đồng ý (accept lời mời, rồi mới cho liên hệ) chính là cái Zalo-một-mình không làm được. Zalo ở đây là **đích đến**, không phải kênh duy nhất: SV nói vài câu trong app, thấy hợp thì bàn giao sang Zalo để dùng lâu dài — đúng lập luận "tận dụng kênh SV đã dùng" của kế hoạch, mà không đánh đổi quyền riêng tư.

> Zalo chỉ cần **deep link** `https://zalo.me/<sđt>`, **không** cần Zalo OA API. Lưu ý cho cả nhóm: Zalo Official Account API đòi OA đã xác minh + hồ sơ doanh nghiệp + review app — không khả thi trong 12 ngày và không cần thiết. Nếu ai trong nhóm đang hiểu "liên kết Zalo" = gọi API Zalo thì bỏ ý đó ngay.

### 1.4.1 Match → lộ liên hệ ngay, hay cần một bước đồng ý nữa? (cần chốt)

Hai lựa chọn, đều thoả lời hứa trong form ("chỉ hiện sau khi CẢ HAI BÊN đồng ý kết nối" — match *là* cả hai đồng ý):

| | **A. Match = lộ liên hệ luôn** | **B. Match mở chat; liên hệ cần đồng ý lần nữa** (đề xuất) |
|---|---|---|
| Khớp tài liệu đã công bố | **Đúng nguyên văn** SRS FR-5.3, và đúng comment schema `users.phone -- lộ khi matching accept` (`30_users.sql`) | Cần sửa 1 câu FR-5.3 |
| Kịch bản demo mục 5 | đúng y nguyên ("chấp nhận → hiện nút Zalo") | thêm 2 click |
| Công sức | ít hơn ~1–2 giờ | +1 cột `contact_consent` + 1 endpoint + 1 banner |
| Rủi ro với UX swipe | **Cao** — xem dưới | Thấp |

**Lý do đề xuất B, và lý do này chỉ mới xuất hiện sau khi chọn swipe (Phần III):** với luồng "gửi lời mời kèm lời nhắn", match là một hành vi **có cân nhắc** — gắn lộ SĐT vào đó là hợp lý. Nhưng với swipe, match trở nên **rẻ và nhiều**: một SV có thể match 5 người trong 30 giây bằng 5 cái flick. Nếu match = lộ SĐT thì nghĩa là **phát số điện thoại cho 5 người bằng 5 cái flick** — không ai chủ ý làm vậy. Thêm nữa, khi đã có chat trong app thì SĐT **không còn cần thiết để bắt đầu nói chuyện**, nên lộ nó ở bước match là lộ không cần thiết (nguyên tắc tối thiểu hoá dữ liệu).

Nếu sau này muốn quay về A: set `contact_consent = TRUE` ngay lúc tạo `conversation` — **một dòng**, đổi ý lúc nào cũng được. Nên cứ làm B trước, nó là chiều an toàn.

Demo vẫn gọn: match → màn "Thành đôi!" → vào chat → banner *"Cho phép bạn ấy xem liên hệ của bạn"*, mỗi bên 1 click → nút Zalo hiện. Thêm 2 click, vẫn nằm trong 2 phút của kịch bản.

### 1.4.2 Dữ liệu thật KHÔNG có số điện thoại → đường Zalo chết, chat trong app là kênh DUY NHẤT

**Cập nhật 26/09 (quan trọng):** 30 phản hồi khảo sát chỉ có **họ tên · MSSV · email** — **không có số điện thoại nào**. Form v2 hỏi *"Email hoặc số Zalo"* trong một ô gõ chữ, và thực tế người trả lời đều điền email.

Hệ quả phải nhìn thẳng:

1. **`zalo.me/<sđt>` không dựng được cho bất kỳ người dùng thật nào.** Không có cách nào link tới một người trên Zalo mà không có SĐT (hoặc OA đã xác minh — xem mục 1.4).
2. ⇒ Phương án "cắt nhắn tin, thay bằng kết nối Zalo" của `KeHoach_NghiemThu_T10.md` mục 1.2 **không còn là phương án yếu hơn — nó là phương án không thực hiện được** với dữ liệu đang có. Chat trong app không phải "nên có", mà là **kênh duy nhất** để hai người đã match nói chuyện được.
3. Việc này **củng cố** quyết định ở mục 1.1–1.3, không lật nó. Và nó xoá luôn rủi ro "bấm nút Zalo ra link rỗng" vì nút đó giờ là có điều kiện.

**Thiết kế tầng T3 sau cập nhật** (vẫn thoả FR-5.3 "lộ liên hệ 2 chiều"):

| Thông tin | Có sẵn? | Lộ ở T3 |
|---|---|---|
| Email | ✅ mọi người (từ form) | có, khi cả hai đồng ý |
| SĐT / Zalo | ❌ không ai có; chỉ có nếu **tự điền trong app** | có, nếu người đó đã điền |
| MSSV | ✅ | **không lộ** — chỉ dùng xác thực SV CTU nội bộ |

⇒ Form hồ sơ trong app có ô **"SĐT (không bắt buộc) — điền nếu bạn muốn dùng nút Zalo"**. Nút Zalo render **có điều kiện**; không có SĐT thì hiện *"Bạn ấy chưa cung cấp SĐT — cứ tiếp tục nhắn ở đây nhé"*, **không** hiện nút chết.

**Sửa kịch bản demo (`KeHoach_NghiemThu_T10.md` mục 5, bước 4):** bỏ *"→ hiện nút Zalo"*, thay bằng *"→ màn Thành đôi! → mở khung chat → nhắn 2 câu, tài khoản kia thấy tin ngay"*. Demo một chức năng chạy thật tốt hơn demo một cái link — và đây mới là sản phẩm thật.

### 1.4.3 Cấp tài khoản cho 20–25 SV dự buổi thử nghiệm 05/10

Không có SĐT thì không gửi OTP/SMS được, và **đừng dựng gửi email trong 12 ngày còn lại**. Dùng đúng lược đồ auth đang có:

- `user_identities` đã hỗ trợ `provider='ctu'`, `provider_user_id=<MSSV>` (`40_auth.sql`) — tạo sẵn tài khoản từ dữ liệu form, đăng nhập bằng **MSSV + mã dùng một lần**.
- `import_survey.py` sinh mật khẩu ngẫu nhiên mỗi người, ghi ra **file cục bộ không commit** (`eval/data/.credentials.csv`, thêm vào `.gitignore`) → in thành phiếu nhỏ phát tại buổi thử nghiệm.
- Không hiển thị/không log mật khẩu ở bất kỳ đâu khác. Xoá file sau buổi thử nghiệm.

### 1.4.4 CẦN ĐẾM NGAY: pool thật có thể nhỏ hơn 30 nhiều

Form v2 có **hai nhánh rẽ** cắt bớt số hồ sơ dùng được cho matching:

1. Câu "bạn có nhu cầu ở ghép?" — chọn *"Không"* thì **bỏ qua toàn bộ phần D** ⇒ không có hồ sơ lối sống.
2. Câu F1 "muốn dùng thử?" — chọn *"Không"* thì **không có tên/MSSV/email** ⇒ **không tạo được tài khoản** ⇒ không vào được pool ghép.

⇒ Số hồ sơ vào được pool = số người trả lời **Có ở cả hai nhánh** *và* khai giới tính (không chọn "Không muốn nêu"). Con số đó có thể là **15–20, không phải 30**. Ba số cần đếm từ Google Sheet trước khi code:

| Cần đếm | Ảnh hưởng |
|---|---|
| N₁ = trả lời đầy đủ phần D | cỡ tập tính điểm |
| N₂ = trong N₁, có khai F2–F4 (tên/MSSV/email) | **cỡ pool ghép thật** |
| N₃ = trong N₂, tách theo giới tính (nam / nữ) | **pool mỗi người** ≈ N₃(cùng giới) − 1, rồi trừ lọc deal-breaker |

Nếu `N₃` mỗi giới chỉ còn 6–8 thì pool sau lọc cứng ≈ 3–5, kỳ vọng match ≈ 0,3 ⇒ **bắt buộc** phải có hồ sơ mô phỏng có nhãn (mục 2.8) + swipe đồng bộ (mục 3.5.6), nếu không thì buổi thử nghiệm sẽ không sinh ra một match nào để đo.

## 1.5 Schema — `92_matching_chat.sql`

Dùng `conversations` + `conversation_members` thay cho `messages(from,to)`. Đắt hơn ~1 giờ, đổi lại **"tạo nhóm" trong thuyết minh trả lời được thật**: lược đồ hỗ trợ N thành viên, UI phiên này chỉ mở 1-1 — nói vậy trung thực, còn bảng `from/to` thì chỉ có thể nói "chưa làm".

```sql
CREATE TABLE conversations (
    id          SERIAL PRIMARY KEY,
    kind        VARCHAR(10) NOT NULL DEFAULT 'pair',   -- 'pair' | 'group' (group: chưa mở UI)
    match_id    INTEGER REFERENCES match_requests(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conversation_members (
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_read_at     TIMESTAMPTZ,
    contact_consent  BOOLEAN DEFAULT FALSE,   -- T3: tự bấm cho phép lộ liên hệ của MÌNH
    PRIMARY KEY (conversation_id, user_id)
);

CREATE TABLE messages (
    id               SERIAL PRIMARY KEY,
    conversation_id  INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body             TEXT NOT NULL,           -- thiết kế gốc text-only; as-built có kind/payload cho ảnh + tin trọ (Chat_Realtime.md)
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_messages_conv ON messages (conversation_id, id);   -- id tăng dần = cursor polling
```

Liên hệ chỉ trả về khi **mọi** thành viên có `contact_consent = TRUE` — kiểm ở tầng repo, không phụ thuộc FE ẩn nút.

## 1.6 API

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/chat/conversations` | danh sách hội thoại + unread count |
| GET | `/chat/conversations/{id}/messages?after_id=` | cursor `after_id`; FE poll 3s, chỉ lấy tin mới |
| POST | `/chat/conversations/{id}/messages` | `{body}`; 403 nếu không phải member |
| POST | `/chat/conversations/{id}/read` | cập nhật `last_read_at` |
| POST | `/chat/conversations/{id}/contact-consent` | T3; trả `{contact: {...}}` khi cả hai đã đồng ý, ngược lại `{waiting_for_other: true}` |

Hội thoại **không tạo bằng tay** — sinh tự động trong transaction lúc `match_request` chuyển `accepted`. Không có đường nào nhắn tin cho người chưa match (chống spam/quấy rối, và đó cũng là câu trả lời cho hội đồng nếu bị hỏi về an toàn).

## 1.7 Đạo đức dữ liệu — viết vào Chương 5

- Màn hình chat có dòng ghi rõ: tin nhắn được lưu trên server của nhóm nghiên cứu, **xóa sau khi nghiệm thu (10/2026)**, không dùng cho mục đích khác.
- **Có gửi ảnh** (quyết định 05/10, thay cho "text-only" ở bản thiết kế đầu): SV cần gửi ảnh phòng/hợp đồng cho nhau
  khi bàn chuyện thuê chung — cấm ảnh thì họ chuyển sang Zalo sớm, mất luôn lớp T3. Giảm thiểu rủi ro bằng:
  ảnh **re-encode JPEG, xoá toàn bộ EXIF** (kể cả toạ độ GPS) phía server; chỉ thành viên hội thoại tải được
  (`/chat/media/{id}` kiểm quyền); giới hạn 4 ảnh × 8 MB, chặn body quá lớn ở tầng ASGI; huỷ ghép ⇒ xoá file;
  `python -m app.chat.media_gc` dọn ảnh mồ côi. **Không** đọc/không trích tin nhắn hay ảnh vào báo cáo (kể cả ẩn danh).
- Có nút "Xóa hội thoại" (hard delete cả `messages`) — tôn trọng yêu cầu rút dữ liệu đã cam kết trong form.
- Chốt bằng câu lệnh `DELETE FROM messages;` **và xoá thư mục ảnh trong volume `media`** trong quy trình dọn dữ liệu
  sau nghiệm thu, ghi vào `Deployment_Guide.md`.

## 1.8 Ngoài phạm vi (nói rõ trong "Hạn chế")

Group chat (UI), push notification, chat với chủ trọ (chủ trọ không có tài khoản trong hệ thống — đây là hệ quả của mô hình Aggregator, xem `01_DanhGia_Va_DinhHuong_NCKH.md`).

---

# PHẦN II — GỢI Ý BẠN Ở GHÉP VỚI N ≈ 30

## 2.1 Collaborative filtering: không phải "thiếu dữ liệu", mà là **sai họ bài toán**

Ba lý do, nêu đúng thứ tự này khi hội đồng hỏi:

1. **Không có ma trận tương tác.** CF học từ ma trận user × item. Ở đây `match_requests` và `user_interactions` (miền ở ghép) đều **rỗng** — không có một lượt accept nào để học. CF trên ma trận rỗng không ra kết quả, chứ không phải ra kết quả kém.
2. **Item chính là user.** Ghép người–người là bài toán **hai chiều**: A phù hợp với B *và* B phải phù hợp với A. CF kinh điển (user-item) không có khái niệm sở thích của "item". Ma trận sẽ là 30×30 với mật độ ~0%.
3. **Với N=30, dù có tương tác thì cũng không học được.** Cần cỡ hàng nghìn cặp để ước lượng được latent factor. Nếu báo cáo đưa ra một con số RMSE/Precision từ CF trên 30 người, hội đồng chỉ cần hỏi "ma trận của em mật độ bao nhiêu?" là lộ.

→ **Không dùng CF. Không ép dùng. Và biến việc không dùng thành một lập luận phương pháp trong Chương 3**, không phải một lời xin lỗi trong Chương 5.

## 2.2 Đúng họ bài toán: Reciprocal Recommender System (RRS)

Ghép người–người có sở thích hai chiều là một nhánh có tên trong tài liệu khoa học, **thiết kế sẵn để chạy ở N nhỏ** vì nó dựa trên thuộc tính chứ không dựa trên lịch sử:

- [R12] Pizzato, L. et al. (2010). *RECON: a reciprocal recommender for online dating.* RecSys. — nguồn gốc của "điểm tương thích hai chiều", dùng **harmonic mean** của hai chiều.
- [R13] Palomares, I. et al. (2021). *Reciprocal Recommender Systems: Analysis of state-of-art literature, challenges and opportunities.* Information Fusion. — survey, dùng để định vị đề tài.
- [R14] Gower, J.C. (1971). *A General Coefficient of Similarity and Some of Its Properties.* Biometrics. — đo tương đồng trên dữ liệu **trộn kiểu** (thứ bậc + nhị phân + tập hợp), đúng dạng dữ liệu form v2.
- Dùng lại [R1] (cold-start), [R2] (ILS — đa dạng), [R3] (ε-greedy) đã có trong `Thuyet_Minh_Bo_Sung.md`.

Đây **mạnh hơn** CF cho đề tài này: có tên trong tài liệu, có công thức để trích dẫn, và chạy được với 30 người. Bổ sung [R12]–[R14] vào mục 10.2 thuyết minh.

## 2.3 Ba lỗi trong thiết kế hiện tại — sửa trước khi code

**(a) `Weighted Cosine Similarity ≥ 0.7` (SRS FR-5.2) gần như chắc chắn vô dụng.**
Các chiều đều dương và thang ngắn (`sleep_time` 0–2, `cleanliness` 1–5, `noise_tolerance` 1–5…). Hai vector toàn số dương trong không gian ít chiều thì **luôn cùng hướng** → cosine dồn vào một dải rất hẹp sát 1, mà cosine lại bỏ qua độ lớn — đúng cái phần chứa thông tin "bạn sạch 5, tôi sạch 2". Ngưỡng 0,7 khi đó cho *mọi người* đi qua, và `% tương thích` hiển thị lên UI sẽ toàn 90–99% → SV không tin, hội đồng hỏi là vỡ.
→ **Đo thật rồi báo số**: tính cosine cho toàn bộ 30×30 cặp, báo min/max/độ lệch chuẩn. Đây là **thí nghiệm ablation miễn phí** (không cần thêm người), và là lý do định lượng để thay công thức. Nếu dải rộng bất ngờ thì giữ cosine — nhưng phải có số mới biết.

**(b) `matching_vector VECTOR(384)` là chiều sai cho 12 câu bấm chọn.**
Nhúng một bộ câu hỏi có cấu trúc thành 384 chiều bằng model text sẽ **phá mất tính thứ bậc** ("rửa ngay" gần "rửa trong ngày" hơn "để người khác rửa" — embedding không giữ được quan hệ đó) và **giết luôn khả năng giải thích** ("vì sao gợi ý bạn này?" không trả lời được từ 384 chiều).
→ Giữ cột cho tương thích lược đồ, nhưng **tính điểm từ các trường thô**. Ghi rõ trong báo cáo: 384-dim dành cho embedding văn bản `bio` ở hướng phát triển, không dùng cho điểm tương thích.

**(c) Điểm đối xứng `score(A,B)` bỏ mất bản chất hai chiều.**
`noise_tolerance` của A đụng với hành vi "tối muộn còn hoạt động" của B thì **chỉ A bị ảnh hưởng**. Một cặp "A chịu được B nhưng B không chịu được A" phải bị điểm thấp, không phải điểm trung bình.

## 2.4 Thuật toán đề xuất — 4 bước

### Bước 1 — Lọc cứng 2 tầng (chạy trước, không vào công thức điểm) — as-built `matching/filters.py`

Bản đầu coi **mọi** deal-breaker là veto. Đo trên 19 hồ sơ thật: chỉ **6/19** người có pool > 0 — tính năng chết
(trung bình mỗi người khai 4,63/9 deal-breaker). Tách 2 tầng theo tiêu chí *có thương lượng được trong thời gian
thuê không* (ADR-014) ⇒ **16/19** (notebook 06 mục 1, 4):

| Thứ tự | Kiểm | Tầng |
|---|---|---|
| 1 | cùng giới (`gender NULL` ⇒ ngoài pool) | an toàn — tuyệt đối |
| 2 | deal-breaker CỨNG hai chiều: *hút thuốc trong phòng* (cột `smoke_in_room`), *ở bẩn* (`cleanliness ≤ 2`) | an toàn — tuyệt đối |
| 3 | ngân sách lệch > 1 bậc (NULL ⇒ bỏ qua) | khả thi |
| 4 | một trong hai khai "ở một mình" | khả thi |
| 5 | thời điểm cần phòng (câu E1) lệch > 2 tháng; "Chưa gấp" / NULL ⇒ bỏ qua | khả thi |

7 deal-breaker còn lại là **mềm**: thành chiều trừ điểm nặng nhất (`deal_breaker_soft`) **và** hiện rõ chữ trên thẻ
("bạn ấy có N điều bạn từng nói không chấp nhận: …"). Lọc được kiểm **lại** ở `POST /matching/swipe` và lời mời —
deck chỉ là gợi ý, ghi mới là hành động. Thẻ "độ tản" của buổi thử nghiệm (2.4c) chỉ được nới tầng **khả thi**,
không bao giờ nới tầng an toàn.

Lọc cứng là phần **làm cho matching an toàn** và giải thích được — đưa nó thành mục riêng trong Chương 3, đừng coi là tiền xử lý.

### Bước 2 — Khoảng cách từng chiều, theo kiểu dữ liệu (Gower)
Mỗi chiều `k` cho ra `d_k ∈ [0,1]`:

| Kiểu | Chiều | `d_k` |
|---|---|---|
| Thứ bậc | sleep_time, cleanliness, noise_tolerance, ac_usage, money_style | `|a−b| / range_k` |
| Nhị phân | cùng Trường/Khoa, cùng khu | `0` nếu giống, `1` nếu khác |
| Tập hợp | hành vi chung (`hanh_vi`) | `1 − Jaccard(A,B)` |
| **Bất đối xứng** | nhu cầu yên tĩnh của A vs hành vi ồn của B | chỉ tính vào `d(A→B)`, `0` ở chiều ngược |

### Bước 3 — Điểm có hướng + gộp hai chiều (RECON)

```
s(A→B) = 1 − Σ_k w_k · d_k(A→B) / Σ_k w_k          # B phù hợp với A bao nhiêu
S(A,B) = 2 · s(A→B) · s(B→A) / (s(A→B) + s(B→A))   # harmonic mean
```

Harmonic mean là chỗ chống được cặp một chiều: `s=0.9 / s=0.3` ra **0.45**, trong khi trung bình cộng ra 0.60. Nêu rõ phép so sánh này trong báo cáo — nó cho thấy vì sao chọn harmonic, và nó là một dòng trong bảng ablation.

### Bước 4 — Top-K + giải thích + đa dạng
- Trả **top-5** kèm `score_breakdown`, **không** dùng ngưỡng tuyệt đối 0,7. Ngưỡng cố định trên pool nhỏ sẽ có lúc trả 0 kết quả → demo chết. Nếu cần ngưỡng, dùng **phân vị** trên phân bố điểm thật.
- Mỗi ứng viên: 3 lý do mạnh nhất (`w_k·(1−d_k)` lớn nhất) + 1 lưu ý (`w_k·d_k` lớn nhất). Ví dụ: *"Cùng giờ ngủ sau 0h · cùng Trường CNTT&TT · cả hai đều rửa chén trong ngày. Lưu ý: bạn ấy hay nấu ăn trong phòng."* Rẻ, ăn điểm SUS, và là ảnh chụp cho Chương 4.
- Đo **ILS** của top-5 ([R2]) để có một dòng số về đa dạng.

### 2.4b Stable Roommates (Irving 1985) — as-built `matching/stable.py`, dùng ở eval

Ghép phòng là bài toán **không hai phía** (khác Stable Marriage) ⇒ có thể **vô nghiệm**. Preference của x là các
ứng viên qua lọc cứng, xếp theo điểm **có hướng** s(x→y) (không dùng harmonic — đã trộn ý của y), phá tie bằng
`user_id`. Vô nghiệm ⇒ trả ghép tham lam kèm số blocking pair ("almost-stable"). Kết quả trên khảo sát: pool nữ
**có** ghép ổn định, pool nam **không** (2 blocking pair) — notebook 06 mục 7. Không dùng để xếp deck (deck là
gợi ý cá nhân, không phải phân phòng toàn cục) — dùng để trả lời "nếu phải phân cặp cho cả nhóm thì có ổn định không".

### 2.4c Deck: chọn thẻ, ε-greedy, độ tản, `deck_log` — as-built `matching/repo.py:deck`

1. **Ghi `deck_log` phía server** cho mọi thẻ đã hiển thị (vị trí, điểm, s_ab, s_ba, `features` = {d_k}, mode,
   bộ trọng số, `explore`). Swipe đọc telemetry từ đây, không nhận từ body (ADR-015). `decided_ms` = thời điểm swipe
   − `served_at` (> 10 phút ⇒ NULL).
2. **Chọn thẻ**: hồ sơ thật trước; thẻ mô phỏng ≤ số thẻ thật (≤ 50% deck), sàn 2 thẻ khi không có hồ sơ thật.
   Lý do: hồ sơ mô phỏng không bao giờ thích lại ⇒ deck 7/8 thẻ mô phỏng thì buổi thử nghiệm không sinh nổi match thật.
3. **ε-greedy** (mode `ranked`): round(0,2·k) thẻ lấy ngẫu nhiên **ngoài** top, chèn vào vị trí ngẫu nhiên;
   `explore='epsilon'`. Hạt giống theo (người, ngày) — tải lại trong ngày không đổi bộ thẻ.
4. **Độ tản** (mode `random`, buổi thử nghiệm): ~20% thẻ là ứng viên chỉ vướng tầng **khả thi**
   (`filters.only_feasibility_gap`), `explore='spread'`; swipe like trên thẻ này được nới đúng tầng khả thi. Thứ tự
   xáo tất định theo người xem; ẩn %, lý do, cảnh báo.
5. **Phạt exposure** 0,02 × số người đã thấy hồ sơ đó (chống congestion, [R16]); đo bằng Gini (notebook 06 mục 8).
6. Notebook **phải** tách thẻ `explore IS NOT NULL` khi tính P@k/NDCG — chúng được chọn có chủ đích ngoài top.

## 2.5 Trọng số lấy từ khảo sát, không lấy từ cảm tính

`03_ThietKe_KyThuat_Va_AI.md` ghi 25/20/15/15/10 — hội đồng sẽ hỏi "ở đâu ra?". Lấy từ dữ liệu:

- **Chiều lọc/xung đột**: tần suất từng deal-breaker được chọn trong 30 phản hồi → chuẩn hóa thành `w_k`. Ai cũng sợ "ở bẩn" thì chiều sạch sẽ tự nặng, không cần nhóm tự quyết.
- **Chiều ngân sách / khoảng cách**: tần suất của câu C3 ("chọn đúng 3 yếu tố" trong form v2 — bản v2 đã đổi từ Likert sang ép chọn 3 chính vì Likert bị straight-lining, phương sai ≈ 0).
- Sau đó chạy **kiểm tra độ nhạy** ±20% từng trọng số → đo độ ổn định thứ hạng top-5 (Kendall τ). Nếu thứ hạng ổn định thì kết luận "kết quả không phụ thuộc vào cách chọn trọng số cụ thể" — một câu rất mạnh trong Chương 4.

## 2.6 Vấn đề thật của N=30: **pool nhỏ hơn tập kết quả**

Số học, làm trước khi viết code:

```
30 hồ sơ
→ lọc cùng giới:        ~14 ứng viên (trừ chính mình)
→ lọc deal-breaker 2 chiều + ngân sách + kịch bản:  thường mất 30–60%
→ pool còn lại:         ~6–10 người
→ hiển thị top-5
```

Tức là **top-5 gần bằng cả pool**. Hệ quả phải nhìn thẳng: ở N=30, cái gần như *không đo được* là **chất lượng xếp hạng** (top-5 trên pool 6 thì thứ tự gần như vô nghĩa), còn cái đo được là **chất lượng lọc + chất lượng điểm trên pool**. Thiết kế đánh giá ở 2.7 được chọn đúng theo ràng buộc đó.

Và một rủi ro vận hành: **có tài khoản sẽ ra 0 ứng viên** (nam ít hơn nữ trong mẫu, hoặc người khai nhiều deal-breaker). Nếu đó là tài khoản demo thì mất luôn 2 phút quan trọng nhất của kịch bản demo → xử lý ở 2.8.

## 2.7 Kế hoạch đánh giá — 6 số liệu từ **một** buổi thử nghiệm

Tất cả lấy từ đúng một buổi 20–30 SV (đã có trong kế hoạch tuần 3), không cần thêm người:

**Đo chính — so sánh trong-đối-tượng, có làm mù.**
Mỗi người nhận **5 thẻ ứng viên xếp ngẫu nhiên, không nhãn**: 3 thẻ từ top-3 của thuật toán + 2 thẻ **random lấy trong pool đã qua lọc cứng**. Chấm từng thẻ 1–5 ("bạn muốn thử ở ghép với người này mức nào").
- `Precision@3` (chấm ≥4 = phù hợp), `NDCG@3` (dùng chính điểm chấm làm gain).
- So algo vs random bằng **Wilcoxon signed-rank theo cặp** (mỗi SV là 1 cặp) + effect size `r`. N=20 cặp là đủ cho hiệu ứng vừa — đây là lý do phải chọn thiết kế *trong-đối-tượng* chứ không phải chia 2 nhóm.
- Lấy random **trong pool sau lọc** mới đo được bộ tính điểm. Báo **cả hai biến thể**: vs random-trong-pool (đo bộ điểm) và vs random-toàn-bộ (đo lọc + điểm). Hai số, cùng trung thực; số thứ hai sẽ đẹp hơn nhiều — nói rõ vì sao.

**5 số liệu còn lại, cùng bộ dữ liệu:**

| # | Số liệu | Cách lấy | Chi phí |
|---|---|---|---|
| 2 | Tương quan thứ hạng | SV xếp hạng 5 thẻ → Spearman ρ với thứ tự thuật toán | 0 (cùng buổi) |
| 3 | Độ tin cậy bộ câu hỏi | Cronbach's α cho nhóm "sạch sẽ" (D5/D6/D7) và nhóm "ồn" (D3 + ô D11) | 0 — chỉ tính trên 30 phản hồi |
| 4 | **Độ phủ & quy mô pool** | % người có ≥1 ứng viên; pool trung bình; **bootstrap resample 30 hồ sơ → mô phỏng N=60/100/200/500** → đường cong độ phủ theo N | 0 — thuần tính toán |
| 5 | Ablation (4 dòng) | (i) cosine vs khoảng cách có trọng số · (ii) trọng số đều vs từ khảo sát · (iii) có/không lọc cứng · (iv) trung bình cộng vs harmonic | 0 — dùng lại điểm chấm ở đo chính |
| 6 | Đa dạng | ILS của top-5 [R2] | 0 |

Số **#4 là câu trả lời cho chính câu hỏi "30 người thì làm được gì"**: thay vì xin lỗi vì N nhỏ, báo cáo đưa ra đường cong "mô hình cần N ≈ ? để 90% người có ứng viên" → N nhỏ biến thành **kết quả nghiên cứu** và làm nền cho mục hướng phát triển. Ghi rõ đây là mô phỏng bằng bootstrap từ 30 hồ sơ thật, **không** phải người thật.

Số **#5 đắt giá nhất trên mỗi đơn vị công sức**: một buổi thử nghiệm → 4 dòng bảng kết quả, vì ablation chỉ đổi công thức rồi tính lại trên cùng điểm chấm của người thật.

**Hạn chế phải tự ghi (đừng để hội đồng nêu trước):** tự khai có thiên lệch (T7); không có ground-truth "ở chung thật có hợp không" vì không ai kịp ở ghép trong thời gian đề tài; N nhỏ; chỉ trong SV CTU cùng giới.

## 2.8 Dữ liệu: nới ràng buộc thật + hồ sơ mô phỏng có nhãn

**Việc đòn bẩy cao nhất còn lại là tăng số hồ sơ** — pool là ràng buộc chặn, không phải thuật toán.

1. **Form hồ sơ trong app = kênh thu dữ liệu**, và **trả thưởng ngay**: điền 12 câu (~90 giây) → **hiện luôn top-3**. Hài lòng tức thì là thứ đẩy tỉ lệ hoàn thành, không phải lời hứa "sau này sẽ có".
2. Đợt đẩy tuần 3 như kế hoạch (group K49/K50, nhóm lớp, KTX). Mục tiêu thực tế trong 12 ngày: **50–60**, không phải 80.
3. **Hồ sơ mô phỏng có nhãn** cho demo: thêm cột `is_simulated BOOLEAN DEFAULT FALSE`. Sinh 30–40 hồ sơ mô phỏng bằng bootstrap từ phân bố 30 hồ sơ thật (giữ tương quan giữa các câu), **hiển thị nhãn "hồ sơ mô phỏng" trên UI**, và **loại khỏi mọi số liệu eval** (`WHERE NOT is_simulated`). Việc này cứu demo mà vẫn trung thực — kế hoạch mục 7 đã cho phép, đây là cách làm cụ thể.
4. **`import_survey.py`** (CSV Google Sheet → `roommate_profiles`) là việc chặn mọi thứ khác — làm đầu tiên. Không có nó thì không có gì để chạy.

## 2.9 Lược đồ cần bổ sung — `roommate_profiles` hiện **không chứa nổi** form v2

Bảng ở `30_users.sql` có 6 trường (`sleep_time, cleanliness, smoke, noise_tolerance, gender_pref, bio`) nhưng form v2 sinh ra nhiều hơn thế, và **thiếu đúng những trường mà lọc cứng cần**:

```sql
-- 92_matching_chat.sql (phần roommate)
ALTER TABLE roommate_profiles
    ADD COLUMN IF NOT EXISTS gender          VARCHAR(3),      -- 'nam'|'nu'; NULL = ngoài pool ghép
    ADD COLUMN IF NOT EXISTS don_vi          VARCHAR(100),    -- Trường/Khoa (cấp trường, KHÔNG cấp ngành)
    ADD COLUMN IF NOT EXISTS budget_band     SMALLINT,        -- 0..4 theo C1
    ADD COLUMN IF NOT EXISTS scenario        SMALLINT,        -- 1 mình | ghép 2 | ghép 3+
    ADD COLUMN IF NOT EXISTS hanh_vi         TEXT[],          -- khớp HANH_VI trong form .gs
    ADD COLUMN IF NOT EXISTS deal_breakers   TEXT[],          -- khớp DEAL_BREAKER
    ADD COLUMN IF NOT EXISTS smoke_in_room   BOOLEAN,         -- tách khỏi smoke: "hút NHƯNG ra ngoài" ≠ deal-breaker
    ADD COLUMN IF NOT EXISTS wake_time       SMALLINT,
    ADD COLUMN IF NOT EXISTS ac_usage        SMALLINT,
    ADD COLUMN IF NOT EXISTS money_style     SMALLINT,
    ADD COLUMN IF NOT EXISTS share_stuff     SMALLINT,
    ADD COLUMN IF NOT EXISTS persona         CHAR(1),         -- 'A'(An) | 'B'(Bình) — forced choice D12
    ADD COLUMN IF NOT EXISTS is_simulated    BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS src             VARCHAR(10);     -- 'form' | 'app'

ALTER TABLE match_requests
    ADD COLUMN IF NOT EXISTS note            TEXT,            -- lời nhắn kèm lời mời
    ADD COLUMN IF NOT EXISTS score_breakdown JSONB,           -- giải thích + vết audit cho eval
    ADD COLUMN IF NOT EXISTS responded_at    TIMESTAMPTZ;
```

Hai điểm dễ sai:
- **`gender` khác `gender_pref`.** Chính sách form v2 là *chỉ ghép cùng giới, không cho người dùng chọn* → cần trường giới tính thật. `gender_pref` trong seed `80_seeds.sql` đang mang nghĩa "muốn ghép với giới nào" — **mâu thuẫn với chính sách**. Giữ cột cho tương thích, ngừng dùng, ghi chú trong migration.
- **`smoke` nhị phân là không đủ**: form có 4 mức, chỉ mức "hút và cần hút **trong phòng**" mới đụng deal-breaker. Nhập nhèm ở đây là loại oan người hút thuốc ngoài phòng.

Thêm `92_matching_chat.sql` vào `infra/db/Dockerfile` (theo đúng lối 90/91) để volume mới tự có.

## 2.10 API matching

| Method | Path | Ghi chú |
|---|---|---|
| POST | `/matching/profile` | upsert hồ sơ (12 câu); trả luôn top-3 để có thưởng tức thì |
| GET | `/matching/candidates?limit=5` | top-K + `score` + `reasons[]` + `caveat`; 200 với `items: []` + `reason: "pool_empty"` khi hết pool (đừng để FE hiện lỗi) |
| POST | `/matching/invite` | `{to_user, note}` |
| POST | `/matching/invite/{id}/respond` | `{accept}`; accept → **tạo `conversation` trong cùng transaction** |
| GET | `/matching/invites` | hộp thư đến/đi |

Sửa `docs/reference/API_Specification.md` mục 4 cho khớp (bản hiện tại ghi `GET /matching/candidates (Weighted Cosine ≥0.7)`).

---

## 3. Lịch 12 ngày (26/09 → 08/10 code freeze)

| Ngày | Việc | Sản phẩm kiểm tra được |
|---|---|---|
| 26–27/09 | `92_matching_chat.sql` + `import_survey.py` | 30 hồ sơ thật trong DB, `SELECT count(*) FROM roommate_profiles` |
| 27/09 | **Thí nghiệm cosine** trên 30×30 cặp (2.3a) | min/max/σ — số để biện minh đổi công thức |
| 28–29/09 | `apps/api/app/matching/` — `filters.py`, `score.py`, `repo.py`, `router.py` + unit test | `GET /matching/candidates` trả top-5 + lý do; test lọc cứng theo `BANG_DOI_CHIEU` |
| 29/09 | Trọng số từ khảo sát + bootstrap sinh hồ sơ mô phỏng (`is_simulated`) | mọi tài khoản demo đều có ≥3 ứng viên |
| 30/09–01/10 | FE `/roommate`: form 12 câu · top-5 kèm % + lý do · gửi/nhận lời mời | ảnh chụp cho báo cáo |
| 02–03/10 | Chat: migration đã có → 5 endpoint + trang `/chat` polling 3s + nút Zalo sau 2 lần đồng ý | demo 2 tài khoản nhắn được, nút Zalo hiện đúng lúc |
| 04/10 | Notebook `06_roommate_eval`: độ phủ, đường cong bootstrap, độ nhạy trọng số, ILS | notebook có output + PNG |
| 05/10 | **Buổi thử nghiệm 20–30 SV** (5 thẻ làm mù, chấm 1–5, xếp hạng) | CSV điểm chấm |
| 06–07/10 | Wilcoxon + P@3/NDCG@3 + bảng ablation 4 dòng + Cronbach α → Chương 4 | bảng số liệu hoàn chỉnh |
| 08/10 | Code freeze; chỉ sửa lỗi chặn demo | |

Ngày 05/10 là **mốc không được trượt** — trượt buổi thử nghiệm là mất số liệu chính, và không có cách bù trong 3 ngày còn lại.

## 4. Tài liệu đã công bố cần sửa cho khớp

| File | Chỗ | Sửa thành |
|---|---|---|
| `docs/planning/SRS.md` | FR-5.1 "6 câu forced-choice" | 12 câu bấm chọn theo form v2 |
| `docs/planning/SRS.md` | FR-5.2 "Weighted Cosine, threshold 0.7" | khoảng cách có trọng số + gộp hai chiều (harmonic), top-K; ngưỡng theo phân vị |
| `docs/planning/SRS.md` | FR-5 | thêm chính sách **chỉ ghép cùng giới** (quyết định có chủ đích, `gender` NULL → ngoài pool) |
| `docs/reference/API_Specification.md` | mục 4 + thêm mục `/chat` | theo 1.6 và 2.10 |
| `KeHoach_NghiemThu_T10.md` | mục 1.2 "Nhắn tin → cắt, thay bằng Zalo" | chat trong app (polling) **+** Zalo là bước bàn giao; lý do = lời hứa riêng tư ở 1.2 |
| `Thuyet_Minh_Bo_Sung.md` | mục 10.2 | thêm [R12] RECON, [R13] RRS survey, [R14] Gower |
| `docs/DECISIONS.md` | — | ADR-012 (chat polling + lộ danh tính 3 tầng), ADR-013 (RRS thay CF; bác cosine-ngưỡng-tuyệt-đối) |

## 5. Ngoài phạm vi phiên này

Group chat UI, post-match feedback sau 2 tuần (không đủ thời gian — đã ghi trong kế hoạch), học trọng số bằng ML từ phản hồi (cần N lớn), embedding `bio` bằng `multilingual-e5-small`, ε-greedy exploration cho matching, ghép nhóm 3 người (bài toán khác: phân hoạch nhóm, không phải ghép cặp).

---

# PHẦN III — BIẾN THỂ "TINDER" (SWIPE) CHO GHÉP BẠN Ở

_Bổ sung 26/09/2026 — trả lời: muốn UX kiểu Tinder thì dùng thuật toán gì, làm thế nào._

## 3.1 Tách rạch ròi hai thứ đang bị gộp

"Kiểu Tinder" gồm hai phần độc lập, phải tách ra mới quyết được:

| | Cái gì | Có nên làm? |
|---|---|---|
| **UX** | một thẻ mỗi lần · bỏ qua/quan tâm · **thích 2 chiều mới thành match** | **Nên** — và nó *có lợi* cho đề tài (3.2) |
| **Thuật toán của Tinder** | Elo "độ hấp dẫn" (bản cũ) → mô hình ranking học từ hàng tỉ swipe (bản mới) | **Không** — sai mục đích và sai quy mô (3.3) |

Swipe **không thay** bộ tính điểm. Kiến trúc của Tinder thật ra vẫn là: *candidate generation (lọc) → ranking → hiển thị từng thẻ*. Tức là đúng 4 bước ở mục 2.4, chỉ khác ở tầng trình bày. **Giữ nguyên: lọc cứng → khoảng cách có trọng số (Gower) → gộp hai chiều (harmonic) → thứ tự bộ thẻ.**

## 3.2 Vì sao swipe lại *tốt hơn* danh sách cho NCKH này

Đây là lý do nên làm, chứ không phải chỉ vì trông hiện đại:

1. **Nó sinh ra dữ liệu tương tác — đúng thứ mà mục 2.1 nói là đang rỗng.** Mỗi swipe là một mẫu có nhãn (`like`/`pass`) trên một ứng viên mà ta **biết trước toàn bộ `d_k`** (khoảng cách từng chiều). Danh sách không cho tín hiệu này.
2. **Nó trả lời bài toán T7 (khai sai hồ sơ) bằng hành vi.** SV khai "mình sạch sẽ 5" có thể bịa, nhưng việc họ *bỏ qua* thẻ của người ở bẩn thì không bịa được. Đây là nền cho 3.4.
3. **Thích-2-chiều là cơ chế reciprocal có sẵn**, khớp đúng họ bài toán RRS ở mục 2.2 — không phải tính năng vay của app hẹn hò.

## 3.3 Vì sao KHÔNG dùng thuật toán của Tinder

- **Elo / điểm "độ hấp dẫn"**: Elo xếp hạng *độ được ưa thích chung* của một người. Với bài toán ở ghép, nó sai mục đích (ghép là *tương thích cặp*, không phải *ai đắt giá hơn*) và **sai về đạo đức** — một bảng xếp hạng độ hấp dẫn của SV CTU đưa vào báo cáo NCKH là tự tạo câu hỏi khó cho mình trước hội đồng. Bỏ hẳn, và ghi rõ lý do bỏ trong báo cáo (đó là một điểm cộng, không phải thiếu sót).
- **Mô hình ranking học từ swipe quy mô lớn**: Tinder có hàng tỉ swipe. Ta có tối đa vài trăm. Xem 3.4 cho phiên bản vừa cỡ dữ liệu.
- **CF trên ma trận swipe**: vẫn là mục 2.1 — 30×30 mật độ ~1%. Không.

## 3.4 Phần thuật toán MỚI đáng làm: học trọng số từ swipe (hồi quy logistic)

Đây là chỗ swipe biến thành **đóng góp khoa học thật**, và nó vừa đúng cỡ dữ liệu:

Mỗi swipe cho một mẫu `(x, y)` với `x = [d_1, d_2, …, d_m]` (khoảng cách từng chiều của cặp đó, đã tính sẵn để hiển thị lý do) và `y ∈ {1 = quan tâm, 0 = bỏ qua}`. Khớp **hồi quy logistic có regularization L2**:

```
P(like) = σ( β_0 + Σ_k β_k · d_k )
```

`β_k` học được **chính là trọng số `w_k`** — nhưng lấy từ *hành vi*, không từ *tự khai*. So sánh ba bộ trọng số thành một bảng kết quả:

| Bộ trọng số | Nguồn | Vai trò trong báo cáo |
|---|---|---|
| đều nhau | — | baseline |
| từ khảo sát (2.5) | SV tự khai mức quan trọng | cái đang thiết kế |
| **học từ swipe** | hành vi thật | **đóng góp chính** |

**Cỡ mẫu — tính thật trước khi hứa:** 20–25 người × pool ~8 thẻ ≈ **160–200 swipe**. Quy tắc ngón tay ~20 quan sát/biến ⇒ chỉ nên đưa **5–6 chiều** vào hồi quy (chọn 5–6 chiều có trọng số khảo sát cao nhất, gộp phần còn lại thành 1 chiều tổng hợp). Đừng nhồi 10–12 chiều rồi báo `β` — sẽ overfit và hội đồng có thể hỏi đúng chỗ đó.

**Bắt buộc về phương pháp:**
- Swipe **không độc lập trong cùng một người** ⇒ kiểm định chéo phải là **leave-one-user-out (grouped CV)**, không phải k-fold ngẫu nhiên. Nói rõ trong Chương 4.
- Báo **AUC ± khoảng tin cậy** (bootstrap), không báo accuracy (dữ liệu lệch lớp).
- Định vị đúng: đây là **chứng minh tính khả thi** của việc học trọng số từ hành vi ở quy mô nhỏ, không phải một mô hình sản xuất. Nói vậy là mạnh; nói quá là yếu.

**ε-greedy cho thứ tự bộ thẻ** ([R3], đã có trong thuyết minh): 80% theo điểm, 20% chèn thẻ ngoài vùng an toàn — nếu luôn hiển thị theo điểm thì mô hình chỉ học được vùng nó đã tin, không bao giờ biết mình sai (feedback loop). Một dòng code, và là một mục có tên trong báo cáo.

## 3.5 Vấn đề chí tử: bộ thẻ hết sau 10 giây, và **phần lớn người sẽ không có match nào**

Tinder sống được vì deck vô hạn và hàng triệu người swipe lệch giờ nhau. Ở N=30 thì:

```
pool sau lọc cứng ≈ 8 thẻ        (mục 2.6)
tỉ lệ "quan tâm" mỗi chiều r ≈ 0,3
⇒ số match kỳ vọng mỗi người = 8 × 0,3 × 0,3 ≈ 0,7
⇒ P(một người KHÔNG có match nào) = (1 − 0,09)^8 ≈ 47%
```

(Nếu `r = 0,5` thì khá hơn: kỳ vọng 2 match, ~10% không có match.) Tức là **gần một nửa người dùng swipe xong rồi ngồi không** — và nếu tài khoản demo rơi vào nửa đó thì mất 2 phút quan trọng nhất của kịch bản demo. Muốn kỳ vọng ≥1 match với `r = 0,3` thì cần pool ≥ 11, tương ứng **N ≈ 50–70** — khớp đúng đường cong độ phủ ở số liệu #4 mục 2.7.

**Sáu cách xử lý, làm hết:**

1. **Đừng giả vờ deck vô hạn.** Gọi là **"bộ thẻ hôm nay"** (5–10 thẻ), có trạng thái kết thúc tử tế: *"Hết thẻ hôm nay — có bạn mới tụi mình báo bạn ngay"*. Trung thực, và tạo lý do quay lại.
2. **`pass` KHÔNG vĩnh viễn.** Tinder xoá thẻ đã pass vì nguồn vô hạn; ở đây pass vĩnh viễn là **đốt pool**. Thiết kế: pass ⇒ hạ ưu tiên 7 ngày, có nút "Xem lại thẻ đã bỏ qua".
3. **Giữ song song đường "gửi lời mời kèm lời nhắn"** (mục 2.10). Match-2-chiều không nên là con đường duy nhất, vì nó nhân hai tỉ lệ rụng.
4. **Lọc reciprocal khi dựng deck**: không đưa thẻ của B cho A nếu **B sẽ loại cứng A**. Tinder không làm việc này; tài liệu RRS ([R12]) cho thấy nó tăng tỉ lệ thành công. Với pool 8 thẻ thì tiết kiệm swipe vô ích là sống còn.
5. **Hồ sơ mô phỏng có nhãn** (mục 2.8) kèm **quyết định swipe đặt trước** — để tài khoản demo luôn có ít nhất 1 match bật ra trên sân khấu. Ghi nhãn "hồ sơ mô phỏng" trên thẻ, loại khỏi mọi số liệu eval.
6. **Buổi thử nghiệm phải chạy ĐỒNG BỘ**: cho cả 20–25 SV swipe trong cùng một khung 30 phút tại buổi thử nghiệm. Nếu để họ swipe lệch ngày, thẻ "quan tâm" của A treo vì B chưa đăng nhập ⇒ **không có match nào để đo**. Swipe đồng bộ còn cho một khoảnh khắc demo rất tốt: match bật ra ngay trong buổi.

## 3.6 Điểm bắt buộc để số liệu không vô nghĩa: **thứ tự ngẫu nhiên khi thu dữ liệu**

Nếu deck xếp theo điểm thuật toán thì thẻ đầu được like nhiều hơn **vì nó ở đầu**, không vì nó hợp — đo ra sẽ là **thiên lệch vị trí**, và mô hình ở 3.4 học chính cái thiên lệch đó.

Cách làm, rẻ và sạch:

- **Trong buổi thử nghiệm**: xáo **thứ tự ngẫu nhiên** toàn bộ deck, không hiển thị `%` tương thích, không hiển thị lý do. Ghi `deck_position` cho mỗi thẻ.
- **Ngoài buổi thử nghiệm (sản phẩm thật)**: xếp theo điểm + ε-greedy, có `%` và lý do — đó là sản phẩm.
- Đánh giá thuật toán **offline như một bộ dự đoán**: nó xếp hạng đúng thứ tự swipe của người thật tới mức nào ⇒ `NDCG`, `AUC`, và kiểm tra `deck_position` **không** còn dự báo được `like` (bằng chứng đã khử thiên lệch).

Thiết kế này còn giải quyết luôn một vấn đề của mục 2.7: dữ liệu swipe *vừa* dùng huấn luyện trọng số *vừa* dùng đánh giá ⇒ **bắt buộc leave-one-user-out CV**, nói thẳng trong báo cáo.

**Cho deck của buổi thử nghiệm có đủ độ tản**: chèn thêm các ứng viên **vượt tiêu chí mềm** (lệch ngân sách >1 bậc, lệch kịch bản ở ghép) để mô hình có mẫu `d_k` lớn. **Tuyệt đối không** chèn ứng viên vi phạm lọc an toàn (khác giới, đụng deal-breaker) — an toàn không đánh đổi lấy phương sai dữ liệu.

## 3.7 Đạo đức & khác biệt với app hẹn hò — swipe trên **lối sống**, không trên **ảnh**

Ghép bạn ở không phải hẹn hò. Nếu thẻ là ảnh chân dung + nút thích thì (a) SV đọc thành "chợ tình", (b) quyết định bị ngoại hình dẫn dắt — đúng thứ làm matching sai, (c) đụng cam kết riêng tư ở tầng T1 (mục 1.4).

Thiết kế thẻ:

```
┌────────────────────────────────┐
│  Nữ · Trường CNTT&TT · Năm 3   │   ← không ảnh, không tên thật ở T1
│  ● Ngủ sau 0h   ● Rửa chén     │
│    trong ngày   ● Ít bật máy   │
│    lạnh                        │
│  "Cần yên tĩnh học bài"        │   ← trích bio, không sửa
│  ─────────────────────────────  │
│  87% tương thích               │   ← ẨN trong buổi thử nghiệm (3.6)
│  Cùng giờ ngủ · cùng Trường ·  │
│  cùng mức sạch sẽ              │
│  ⚠ Bạn ấy hay nấu ăn trong phòng│
│  [ Bỏ qua ]      [ Quan tâm ]  │
└────────────────────────────────┘
```

Đây là **điểm khác biệt đáng viết vào Chương 3**: swipe trên hồ sơ lối sống có giải thích, không trên ảnh — giảm thiên lệch ngoại hình và giữ được cam kết lộ danh tính 3 tầng. (So sánh tỉ lệ like có ảnh/không ảnh sẽ là một thí nghiệm hay, nhưng đưa ảnh vào là mở thêm vấn đề đạo đức ⇒ xếp vào hướng phát triển.)

## 3.8 Lược đồ thêm — bảng `swipes`

```sql
-- 92_matching_chat.sql (phần swipe)
CREATE TABLE IF NOT EXISTS swipes (
    id             SERIAL PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    decision       VARCHAR(6) NOT NULL,        -- 'like' | 'pass'
    score_at_swipe REAL,                       -- điểm lúc hiển thị (thuật toán có thể đổi sau)
    features       JSONB,                      -- {d_k} snapshot — BẮT BUỘC để huấn luyện & audit
    deck_position  SMALLINT,                   -- khử thiên lệch vị trí (3.6)
    deck_mode      VARCHAR(10),                -- 'ranked' | 'random' (random = buổi thử nghiệm)
    decided_ms     INTEGER,                    -- thời gian quyết định; tín hiệu phụ, không bắt buộc
    created_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, target_id)                -- 1 quyết định/cặp; đổi ý = UPDATE
);
CREATE INDEX IF NOT EXISTS idx_swipes_target ON swipes (target_id, decision);
```

`features` snapshot là trường quan trọng nhất của bảng này: không có nó thì sau buổi thử nghiệm **không thể huấn luyện lại** (hồ sơ có thể đã bị sửa, `d_k` tính lại sẽ khác) và không có vết audit cho Chương 4. Đừng bỏ để "tính lại sau".

Match vẫn đi qua `match_requests` đang có (không phá gì): hai `like` đối nhau ⇒ trong **cùng transaction**, tạo/`UPDATE` `match_requests` thành `accepted` + tạo `conversation` (mục 1.5). Tức là swipe chỉ là *cách khác* để sinh ra `match_requests`, đường "gửi lời mời" vẫn chạy song song.

## 3.9 API thêm

| Method | Path | Ghi chú |
|---|---|---|
| GET | `/matching/deck?limit=10&mode=ranked\|random` | thẻ chưa quyết định, đã lọc reciprocal (3.5.4); `mode=random` cho buổi thử nghiệm (ẩn `%` + lý do) |
| POST | `/matching/swipe` | `{target_id, decision, deck_position, decided_ms}` → `{matched: bool, conversation_id?}`; ghi `features` phía server (đừng tin FE gửi lên) |
| GET | `/matching/passed` | thẻ đã bỏ qua, để xem lại (3.5.2) |

`GET /matching/deck` trả `items: []` + `reason: "deck_empty"` khi hết — FE hiện trạng thái kết thúc, **không** hiện lỗi.

## 3.10 Frontend — nơi dễ mất 2 ngày oan

- **Làm nút trước, cử chỉ kéo sau.** Hai nút `[Bỏ qua] [Quan tâm]` + phím ←/→ là đủ để demo và **rõ nghĩa hơn** cử chỉ kéo (SV không phải đoán kéo phải nghĩa là gì). Cử chỉ drag/animation trên mobile là chỗ ngốn thời gian nhiều nhất và không đổi được thành số liệu nào — chỉ làm nếu ngày 05/10 đã xong.
- Một component thẻ + `useState` con trỏ deck + optimistic advance. Không cần thư viện swipe.
- **Màn hình "Thành đôi!"** khi `matched: true` → nút "Nhắn tin" mở thẳng `conversation_id` (mục 1.6). Đây là khoảnh khắc demo — đáng đầu tư 30 phút CSS, còn hơn 2 ngày làm physics kéo thẻ.

## 3.11 Chi phí so với bản danh sách

| | Danh sách (Phần II) | Swipe (Phần III) |
|---|---|---|
| Thuật toán lõi | như nhau | **như nhau** |
| Backend thêm | — | bảng `swipes` + 3 endpoint ≈ **+0,5 ngày** |
| Frontend | danh sách top-5 | thẻ + 2 nút ≈ **bằng nhau** |
| Eval | chấm 1–5 thủ công | **swipe = nhãn tự động**, sạch hơn, ít công hơn |
| Số liệu thêm | — | AUC dự đoán swipe, bảng 3 bộ trọng số, tỉ lệ match |

Kết luận: **nên làm swipe.** Tốn thêm ~0,5 ngày, đổi lại một đóng góp khoa học (học trọng số từ hành vi) và một buổi thu dữ liệu nhẹ hơn chấm điểm tay.

## 3.12 Lịch điều chỉnh (thay bảng mục 3 ở trên cho phần matching)

| Ngày | Thêm/đổi so với lịch cũ |
|---|---|
| 26–27/09 | `92_matching_chat.sql` **có luôn bảng `swipes`** + `import_survey.py` |
| 28–29/09 | `matching/` lõi (không đổi) + `GET /deck` với lọc reciprocal + `POST /swipe` (tạo match + conversation trong 1 transaction) |
| 30/09–01/10 | FE `/roommate` = **thẻ + 2 nút + màn "Thành đôi!"** (bỏ layout danh sách top-5, giữ trang "Lời mời") |
| 02–03/10 | Chat (không đổi) |
| 04/10 | Notebook `06_roommate_eval`: độ phủ, đường cong bootstrap, độ nhạy, ILS + **khung hồi quy logistic chạy sẵn trên dữ liệu mô phỏng** để ngày 05/10 chỉ cần đổ dữ liệu thật vào |
| **05/10** | **Buổi thử nghiệm — swipe ĐỒNG BỘ 30 phút, `mode=random`, ẩn `%`** (thay cho chấm 5 thẻ 1–5) |
| 06–07/10 | AUC leave-one-user-out + bảng 3 bộ trọng số + ablation + kiểm tra `deck_position` đã hết tác dụng dự báo → Chương 4 |

Ngày 04/10 phải chạy xong notebook **trên dữ liệu mô phỏng** — nếu để 05/10 mới viết code phân tích thì có dữ liệu thật mà không kịp ra số.

## 3.13 Cần sửa thêm trong tài liệu đã công bố

- `SRS.md` FR-5.2/5.3: thêm cơ chế **thích 2 chiều** như một đường sinh match song song với lời mời.
- `Thuyet_Minh_Bo_Sung.md` mục 10.2: thêm [R15] Hosmer & Lemeshow, *Applied Logistic Regression* (hoặc một giáo trình tương đương) cho phần học trọng số; [R12] RECON đã gánh phần reciprocal.
- `docs/DECISIONS.md` ADR-013: ghi rõ **bác Elo/điểm độ hấp dẫn** và lý do đạo đức — chủ động ghi, đừng đợi bị hỏi.

## 3.14 "Đây có phải thuật toán gợi ý?" — định danh để trả lời hội đồng

**Có.** Và đây gần như chắc chắn là một câu hỏi sẽ bị hỏi lúc nghiệm thu, nên chuẩn bị sẵn cách gọi tên.

**Sai lầm cần gỡ trước: Recommender System ≠ Collaborative Filtering.** CF chỉ là *một* họ trong phân loại chuẩn của lĩnh vực. Giáo trình tham chiếu của ngành (Aggarwal, *Recommender Systems: The Textbook*, 2016; Ricci et al., *Recommender Systems Handbook*) tách chương riêng cho: collaborative filtering · **content-based** · **knowledge-based / constraint-based** · hybrid. Hệ ở đây nằm ở hai họ giữa — vẫn là hệ gợi ý đúng nghĩa, không phải "chỉ là công thức tính điểm".

Đối chiếu 5 thành phần định nghĩa một hệ gợi ý:

| Thành phần | Trong hệ này |
|---|---|
| Mô hình người dùng | `roommate_profiles` — 12 chiều lối sống |
| Tập ứng viên | các SV khác, sau lọc cứng |
| Hàm xếp hạng cá nhân hoá | `S(A,B)` — khoảng cách có trọng số, gộp hai chiều |
| Vòng phản hồi | **swipe** → học lại trọng số (3.4) |
| Đánh giá bằng metric của ngành | Precision@K, NDCG@K, ILS, coverage — **cùng bộ metric với module gợi ý nhà trọ** |

Đủ cả 5. Tên gọi nên dùng trong Chương 3, viết đúng thứ tự này:

> **Hệ gợi ý dựa trên nội dung, hai chiều (reciprocal content-based recommender), có ràng buộc cứng và học trọng số từ phản hồi ẩn (implicit feedback).**

**Câu chốt mạnh nhất nếu bị truy:** RECON [R12] — thuật toán gợi ý hai chiều — được công bố tại **ACM RecSys**, hội nghị số một của chính lĩnh vực hệ gợi ý; survey [R13] đăng ở *Information Fusion* xếp bài toán ghép hai chiều (hẹn hò, tuyển dụng, mentor) vào hệ gợi ý. Tức là chính cộng đồng nghiên cứu hệ gợi ý coi đây là hệ gợi ý — không phải nhóm mình tự nhận.

**Một điểm tinh tế nên nói chủ động, vì nó cho thấy hiểu bài:** trọng số `β` ở mục 3.4 học từ swipe của **tất cả** người dùng, rồi áp cho từng người ⇒ hệ **có dùng tín hiệu cộng tác**, nhưng ở mức *trọng số đặc trưng*, không ở mức *ma trận user–item*. Nói chính xác: "có thành phần cộng tác, không phải collaborative filtering". Lý do chọn mức đó là định lượng — ma trận 30×30 mật độ ~1% (mục 2.1).

**Và trả lời "vì sao không dùng CF" phải có phần "khi nào thì dùng được"** — mới là câu trả lời của người làm nghiên cứu, không phải của người thiếu dữ liệu:

> CF cần lịch sử tương tác dày. Ở N=30 với ~200 swipe, mật độ ma trận ~1% ⇒ không ước lượng được latent factor. Khi hệ đạt cỡ vài nghìn swipe, hướng nâng cấp tự nhiên là matrix factorization / two-tower trên chính bảng `swipes` — lược đồ hiện tại đã lưu đủ (`user_id`, `target_id`, `decision`, `features`) để làm việc đó mà không phải thu lại dữ liệu.

Ghi đoạn đó vào **hướng phát triển** (Chương 5): nó biến "không dùng CF" từ hạn chế thành lộ trình.

> Ghi chú đối chiếu tài liệu: **không** tài liệu nào của đề tài (thuyết minh, SRS, `03_ThietKe_KyThuat_Va_AI.md`) hứa CF cho module ghép bạn ở — CF chỉ xuất hiện trong tiêu đề reference [R1] (survey cold-start, dùng cho module gợi ý nhà trọ). Nên **không có nội dung đã đăng ký nào bị cắt**. Thứ duy nhất cần sửa vẫn là `Weighted Cosine Similarity` → khoảng cách có trọng số + gộp hai chiều (SRS FR-5.2, mục 2.3a).

---

# PHẦN IV — ĐỐI CHIẾU VỚI THUYẾT MINH: "hệ thống gợi ý" ở module ghép bạn ở

_Bổ sung 26/09/2026 — trả lời: phần nào của thiết kế đáp ứng mục tiêu "thuật toán gợi ý" đã đăng ký._

## 4.1 Nguyên văn đã đăng ký (trích `Thuyết minh.md` + `Thuyet_Minh_Bo_Sung.md`)

| Mục | Nguyên văn (phần liên quan ghép bạn ở) |
|---|---|
| **13.1** Đối tượng NC | "**Thuật toán gợi ý phục vụ chức năng đề xuất bạn ở ghép.**" |
| **12.2** Mục tiêu cụ thể | "Thiết kế các chức năng tương tác, **tạo môi trường trao đổi thông tin giữa sinh viên có nhu cầu ở ghép**." |
| **15.1** Phần 3 | "…dựa trên **thuật toán gợi ý** và xử lý dữ liệu, bao gồm: gợi ý nhà trọ phù hợp, **gợi ý tìm bạn ở ghép**…" |
| **15.2** dòng 3 (sản phẩm) | "Tích hợp mô-đun AI · **Hệ thống matching** · **Báo cáo kết quả huấn luyện và đánh giá mô hình**" |
| **12.2 bổ sung** mục 5 | "Roommate Matching: **MAE feedback sau 2 tuần ≤ 1.5/5**" |

**Điểm mấu chốt: 13.1 đăng ký "thuật toán gợi ý" nhưng KHÔNG chỉ định họ thuật toán nào.** Không có chỗ nào trong thuyết minh ghi collaborative filtering, matrix factorization, hay một mô hình cụ thể. Nên chọn reciprocal content-based (mục 2.2) là **hoàn toàn nằm trong phạm vi đã đăng ký** — không phải thay thế, không phải cắt giảm, không cần biện minh ở mục "Hạn chế".

## 4.2 Bảng đối chiếu: mục tiêu đã đăng ký → thành phần → bằng chứng nghiệm thu

| Đã đăng ký | Thành phần nào đáp ứng | Bằng chứng đưa hội đồng |
|---|---|---|
| "thuật toán gợi ý" (13.1) | hàm xếp hạng `S(A,B)`: lọc cứng → khoảng cách có trọng số → gộp hai chiều harmonic → top-K (mục 2.4) | code `matching/score.py` + test; công thức trong Ch.3 |
| "gợi ý tìm bạn ở ghép" (15.1 P3) | endpoint `GET /matching/deck` + bộ thẻ xếp hạng + 3 lý do/1 lưu ý | demo + ảnh màn hình Ch.4 |
| **"Báo cáo kết quả huấn luyện…"** (15.2) | **hồi quy logistic học `β` từ swipe** (mục 3.4) | bảng 3 bộ trọng số + AUC leave-one-user-out |
| "…và đánh giá mô hình" (15.2) | notebook `06_roommate_eval` | P@K, NDCG@K, ILS, coverage, ablation 4 dòng |
| "MAE ≤1.5/5" (bổ sung 12.2 m5) | **MAE tức thời** — xem 4.4 | bảng MAE trong Ch.4 |
| "tạo môi trường trao đổi thông tin giữa SV có nhu cầu ở ghép" (12.2) | **chat 1-1 trong app** (Phần I) | demo nhắn tin 2 tài khoản |

## 4.3 Phát hiện 1: "huấn luyện" là từ đã đăng ký ⇒ phần học trọng số KHÔNG phải tuỳ chọn

Sản phẩm đăng ký ở mục 15.2 ghi rõ "**Báo cáo kết quả huấn luyện** và đánh giá mô hình". Nếu module ghép bạn chỉ là một **công thức trọng số tự gán** thì:

- không có gì được "huấn luyện" ⇒ không có "kết quả huấn luyện" để báo cáo;
- hội đồng hỏi "mô hình của em huấn luyện trên dữ liệu gì, hàm mất mát gì?" thì không có câu trả lời.

⇒ **Hồi quy logistic học `β` từ swipe (mục 3.4) chính là thành phần làm cho chữ "huấn luyện" trở thành sự thật.** Nó chuyển từ "nên có cho đẹp" sang **bắt buộc để khớp sản phẩm đã đăng ký**. Đây là lý do mạnh nhất để giữ nó trong 12 ngày còn lại, mạnh hơn cả lý do khoa học.

Cách trình bày trong Ch.3/Ch.4: bộ trọng số khảo sát là **khởi tạo** (cold-start, [R1]), `β` học từ swipe là **huấn luyện**, và bảng 3 dòng (đều / khảo sát / học) là **kết quả huấn luyện**.

## 4.4 Phát hiện 2: giữ MAE, chỉ đổi mốc thời gian — đừng bỏ hẳn

`KeHoach_NghiemThu_T10.md` mục 1.2 thay "MAE feedback sau 2 tuần" bằng "khảo sát hài lòng tức thời 20 SV" — đúng về mốc thời gian (không thể theo dõi 2 tuần), nhưng **bỏ luôn cả chỉ số MAE** thì mất một mục tiêu định lượng đã đăng ký.

Cách giữ cả hai, chi phí ~2 phút/người:

> Trong buổi 05/10, **sau** khi swipe xong (nhị phân, làm mù, thứ tự ngẫu nhiên), hỏi tiếp **điểm 1–5** cho 3–5 ứng viên đã xem. Rồi tính `MAE = mean |điểm mô hình quy về thang 1–5 − điểm SV chấm|`.

Kết quả là một con số **so trực tiếp được với ngưỡng 1,5/5 đã đăng ký**, chỉ khác "tức thời" thay vì "sau 2 tuần" — và mốc thời gian đó đã có lý do chính đáng ghi trong kế hoạch. Trong báo cáo viết: *"MAE (tức thời) = x,x/5"*, kèm một câu nói rõ khác biệt so với thuyết minh và vì sao.

**⚠ Việc này đổi thiết kế buổi 05/10** (mục 3.12): thêm bước chấm 1–5 **sau** bước swipe. Thứ tự bắt buộc — swipe trước (quyết định nhị phân không bị điểm số dẫn dắt), chấm điểm sau.

## 4.5 Phát hiện 3: mục tiêu 12.2 chỉ yêu cầu trao đổi **giữa sinh viên**

So hai chỗ:

- **12.2 (mục tiêu)**: "tạo môi trường trao đổi thông tin **giữa sinh viên có nhu cầu ở ghép**" — chỉ SV ↔ SV.
- **15.1 Phần 5 (nội dung)**: "chức năng tương tác (nhắn tin, tạo nhóm,..) giữa sinh viên **và chủ trọ**, cũng như giữa các sinh viên…"

⇒ **Chat 1-1 giữa SV đáp ứng ĐỦ mục tiêu 12.2** — tầng mục tiêu, tầng có giá trị ràng buộc cao nhất. Phần "chủ trọ" chỉ nằm ở tầng *nội dung* 15.1, và **không thể thực hiện được** trong mô hình Aggregator: chủ trọ không có tài khoản trong hệ thống (tin được crawl từ nguồn ngoài, hệ thống dẫn link về nguồn — xem `01_DanhGia_Va_DinhHuong_NCKH.md`). Đây là hệ quả trực tiếp của quyết định kiến trúc đã ghi nhận, không phải việc bị bỏ quên.

Cách viết vào "Hạn chế & hướng phát triển": *"Trao đổi với chủ trọ không triển khai vì mô hình Aggregator không có actor chủ trọ; liên hệ chủ trọ thực hiện qua thông tin/liên kết dẫn về nguồn gốc tin. Mục tiêu 12.2 (trao đổi giữa SV có nhu cầu ở ghép) đã đáp ứng bằng chat trong app."* Và "tạo nhóm": lược đồ `conversations` + `conversation_members` đã hỗ trợ N thành viên, chỉ chưa mở UI (mục 1.5) — nói được thật, không phải nói suông.

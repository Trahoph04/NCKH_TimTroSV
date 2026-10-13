# Hướng dẫn DEMO — Trọ CTU

Kịch bản trình bày khi nghiệm thu + cách cho hội đồng xem trên điện thoại/máy khác cùng mạng.

## 0. Khởi động

Trên máy chạy dự án (máy "chủ"):

```bash
cd NCKH_TimTroSV
docker compose up -d --build     # chờ ~1 phút cho web lên
docker compose ps                # 4 container api/web/db/redis đều Up
```

Mở **http://localhost:3000** trên chính máy chủ để kiểm tra trước.

## 1. Tài khoản đăng nhập (đều là tài khoản MẪU, không phải người thật)

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Admin | `admin@ctu.edu.vn` | `secret` |
| Sinh viên A | `nguyenvana@ctu.edu.vn` | `secret` |
| Sinh viên B | `tranthib@ctu.edu.vn` | `secret` |
| Chủ trọ | `chutro.xuanhuong@gmail.com` | `secret` |
| Chat / Ghép bạn (nhiều tài khoản) | `*.demo@example.com` | `demo1234` |

> Mật khẩu trong DB được lưu dạng băm; đây là mật khẩu gốc của tài khoản seed (xem `infra/db/migrations/80_seeds.sql`, `app/chat/seed_demo.py`).

## 2. Trình tự trình bày gợi ý

1. **Bản đồ** (menu *Bản đồ*) — điểm mạnh nhất:
   - Icon: hình nhà tròn xanh đậm = tin vị trí chính xác; xanh nhạt viền xanh = tin cấp phường ("vị trí tương đối");
     cụm là nhãn "🏠 + số tin" cùng quy ước đậm/nhạt; ô vuông mũ tốt nghiệp = khu CTU. Chọn tin → tiện ích hiện thành ô vuông nhỏ có icon (chợ, siêu thị, ATM,
     nhà thuốc, bệnh viện, xe buýt) — bấm icon để xem tên.
   - Bấm một tin → vẽ **đường đi tới ĐH Cần Thơ** + tiện ích trong 1 km.
   - Đổi **Khu I / II / III** → đường vẽ lại đúng khu.
   - Tick "Chỉ hiện tin vị trí chính xác" cho gọn.
   - Tin có ảnh/vị trí đẹp để demo: `1598`, `1635`, `4711`, `1595`.
2. **Trang chi tiết + bản đồ nhỏ + đánh giá** — bấm "Xem chi tiết":
   - Khu "Đánh giá của sinh viên": điểm TB, phân bố sao, tag; tag cảnh báo ≥ 2 người báo ⇒ khung "Lưu ý từ người đã ở".
     Đăng nhập (vd. `nguyenvana@ctu.edu.vn`) để viết/sửa; admin ẩn đánh giá ở **Quản lý → Đánh giá**.
   - Khung "Liên hệ chủ trọ": có số → nút gọi (tin `1215`); không → "Xem tin gốc" (1598, 1635, 4711).
   - Đánh giá: hiện chưa có dữ liệu (13/10) — demo bằng cách viết 1 đánh giá thật ngay tại chỗ, rồi admin ẩn/hiện ở
     **Quản lý → Đánh giá**. KHÔNG tạo đánh giá mẫu; muốn có sẵn dữ liệu thì thành viên đã khảo sát ghi theo quan sát thực địa.
   - **Bản đồ nhỏ hình tròn góc dưới phải** → bấm vào nhảy sang bản đồ lớn, chọn sẵn tin + vẽ sẵn đường.
3. **Gợi ý nhà trọ** (menu *Gợi ý*): nhập giá/khu/tiện ích → xếp hạng theo điểm; có màn hình đánh giá mù so 3 hệ.
4. **Ghép bạn ở**: đăng nhập `*.demo@example.com` → vuốt thẻ, gửi lời mời. Trạng thái 13/10: Thu–Hân, Thu–Linh, Huy–Đức
   ĐÃ ghép (không bật "Thành đôi!" lại được); cặp dùng được: **Trân đã thích Thu** ⇒ đăng nhập Thu, tab Lời mời/Quan tâm,
   thích lại Trân ⇒ "Thành đôi!" ở cả hai máy. Mỗi lần diễn tập ghi swipe/tin nhắn vào DB — tập xong ghi lại cặp nào còn dùng
   được; đừng `seed_demo --reset` khi chưa sao lưu.
5. **Chat realtime**: hai tài khoản demo nhắn cho nhau.
   Chatbot: câu "Chủ trọ giữ cọc không trả thì sao?" trích BLDS Điều 328 (~7 s qua Gemini — nói tiếp trong lúc chờ).
6. **Cẩm nang → Ký túc xá CTU**: thông tin KTX chính thức + khối "KTX hay thuê trọ?" (giá trọ tính từ dữ liệu hệ
   thống) → bấm "Hỏi Trợ lý về KTX" để chatbot trả lời có trích nguồn của trường.

## 3. Chạy trên thiết bị khác cùng mạng (điện thoại / laptop hội đồng)

Kiến trúc đã hỗ trợ sẵn LAN, **không cần sửa `.env` hay build lại**: trình duyệt gọi REST qua Route Handler của web (cổng 3000); chat WebSocket tự thay `localhost` bằng IP của trang đang mở nên trỏ đúng về máy chủ.

**Các bước:**

1. Hai thiết bị **cùng một WiFi** (không dùng mạng khách / không bật AP isolation).
2. Lấy IP LAN của máy chủ:
   ```bash
   ipconfig getifaddr en0        # macOS (WiFi); nếu trống thử en1
   # Windows: ipconfig  → IPv4 Address;  Linux: hostname -I
   ```
   Ví dụ máy này hiện là **10.13.130.191**.
3. Trên thiết bị khác, mở trình duyệt vào **http://10.13.130.191:3000** (thay bằng IP máy bạn).
4. Đăng nhập và demo như thường. Chat realtime cũng chạy (client tự nối `ws://10.13.130.191:8000/chat/ws`).

**Cổng cần mở sẵn** (docker đã publish ra `0.0.0.0`): `3000` (web) và `8000` (chat WebSocket). `5432`/`6379` chỉ mở cho
chính máy chủ (`127.0.0.1`, từ 12/10) — máy khác trong LAN không đọc được DB/Redis.

**Nếu thiết bị khác không vào được:**
- Kiểm tra lại đúng IP và cùng WiFi; thử `ping 10.13.130.191` từ thiết bị kia.
- macOS: *System Settings → Network → Firewall* — nếu đang bật, cho phép Docker nhận kết nối đến (hoặc tạm tắt firewall khi demo).
- Dùng `http://` chứ không phải `https://` (LAN không có chứng chỉ).
- **Bản đồ nền + tiện ích** tải từ OpenFreeMap/OpenStreetMap trên Internet ⇒ thiết bị khách vẫn cần có mạng Internet (không chỉ WiFi nội bộ).

> Muốn cho người **ngoài mạng LAN** xem (ví dụ qua `cloudflared tunnel`): đặt biến `CHAT_WS_URL` = URL tunnel rồi `docker compose up -d` lại web; LAN thì để trống.

## 4. Checklist trước buổi demo

- [ ] `docker compose ps` — 4 container Up.
- [ ] Crawl/kiểm tin còn sống (tin sàn "chết" nhanh): `docker compose exec api python -m app.cleaner.audit --network --apply --nhatot-seen-since <ISO lượt crawl full>`.
- [ ] Backfill đường đi để đọc từ cache cho mượt: `docker compose run --rm --no-deps -T api python -m app.listings.route_cache_backfill --apply` (ORS hết quota thì thêm `--engine osrm`).
- [ ] Mở thử http://<IP>:3000 trên điện thoại một lần trước khi hội đồng vào.
- [ ] Chuẩn bị sẵn vài tin đẹp (`1598`, `1635`, `4711`; KHÔNG mở đầu bằng `4712` — 2 ảnh đầu đã 404 trên CDN Chợ Tốt) và tài
      khoản demo đã đăng nhập ở 2 tab cho phần chat.
- [ ] Mở `/cam-nang#ktx`: khối "KTX hay thuê trọ?" phải có số giá trọ (nếu thấy "Chưa tải được" thì API chưa lên — tải lại
      trang sau khi `curl localhost:8000/health` trả ok).
- [ ] Hỏi thử chatbot 1 câu (kiểm khoá Gemini còn dùng được: `python -m app.room_service.chatbot.check_llm --call`).

> Lưu ý: đường đi vẽ bằng OSRM có thể lệch nhẹ so với số phút (số phút do ORS Matrix tính). Toạ độ đa số tin chỉ tới cấp phường → UI ghi "vị trí tương đối"; đây là hạn chế đã nêu trong báo cáo.

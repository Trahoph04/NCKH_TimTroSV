/**
 * ═══════════════════════════════════════════════════════════════════════════
 *  FORM KHẢO SÁT SV ĐH CẦN THƠ — đề tài THS2026-66   ·   BẢN 2 (rút gọn)
 * ═══════════════════════════════════════════════════════════════════════════
 *
 *  Thay đổi so với bản 1 (44 → 29 quyết định (~5 phút); người không ở ghép chỉ 17 câu (~3 phút)):
 *
 *   ┌ SỬA LỖI ────────────────────────────────────────────────────────────┐
 *   │ 1. Câu "ngành" ô gõ chữ BẮT BUỘC  →  dropdown Trường/Khoa (bắt buộc)│
 *   │    + ô ngành gõ tay KHÔNG bắt buộc.                                 │
 *   │    Lý do: phiếu thử đã trả lời "Trường CNTT&TT" vào ô ngành.         │
 *   │    Thuật toán matching dùng cấp TRƯỜNG (≈11 người/nhóm ở N=150),     │
 *   │    không dùng cấp ngành (≈1,5 người/ngành → không bao giờ khớp).     │
 *   │ 2. GỐC TÍNH KHOẢNG CÁCH = KHU II DUY NHẤT, không hỏi khu học.        │
 *   │    Đo từ toạ độ đã chốt trong Map_Routing.md:                        │
 *   │       Khu I ↔ II  1,84 km (~6 phút)   Khu II ↔ III 1,27 km (~4 phút) │
 *   │       Khu I ↔ III 2,54 km (~8 phút)   Khu II ↔ Hòa An 30,4 km (~68p) │
 *   │    → khu I/II/III là MỘT cụm trong bán kính 2,5 km. Lấy khu II làm   │
 *   │    gốc gây sai số tối đa ~6 phút, mà C4 chia bucket 5 phút → lệch    │
 *   │    tối đa 1 bậc. Đổi lại: bớt 1 câu hỏi và C4 hết mập mờ.            │
 *   │    Hòa An (Hậu Giang) LOẠI ở câu sàng lọc — vốn đã ngoài phạm vi     │
 *   │    SRS đã công bố ("quận Ninh Kiều và lân cận").                     │
 *   │ 3. Lưới C3 (7 hàng Likert) → "chọn đúng 3 yếu tố". Likert bị         │
 *   │    straight-lining: ai cũng chấm 4–5 → phương sai ≈0 → trọng số vô   │
 *   │    dụng. Ép chọn 3 mới sinh ra đánh đổi, mà đánh đổi mới ra trọng số.│
 *   │ 4. Lưới D11 (8 hàng) → 1 câu chọn nhiều, DÙNG CHUNG DANH SÁCH với    │
 *   │    câu deal-breaker → bộ lọc cứng chạy được (xem BANG_DOI_CHIEU cuối │
 *   │    file). Bản cũ có 2 deal-breaker KHÔNG có trường đối chiếu:        │
 *   │    "người yêu ở lại qua đêm" và "trả tiền trọ trễ" → nằm im vĩnh viễn│
 *   │ 5. Cam kết riêng tư: bản cũ hứa "không ai xem được MSSV hay số liên  │
 *   │    hệ" — MÂU THUẪN với FR-5.3 (lộ liên hệ 2 chiều sau khi cả hai     │
 *   │    đồng ý). Đã sửa thành cam kết CÓ ĐIỀU KIỆN, đúng với sản phẩm.    │
 *   │ 6. Tách "xóa dữ liệu 10/2026": dữ liệu khảo sát ẩn danh giữ cho báo  │
 *   │    cáo, tài khoản dùng thử xóa theo yêu cầu. Bản cũ hứa xóa tất cả   │
 *   │    trong khi vẫn tạo tài khoản cho họ — không thực hiện được.        │
 *   └─────────────────────────────────────────────────────────────────────┘
 *   ┌ THÊM ───────────────────────────────────────────────────────────────┐
 *   │ 7. "Khi nào cần phòng?"  → lọc cứng thời điểm                        │
 *   │ 8. "Đã có phòng hay chưa?" → lọc cứng kịch bản ghép                  │
 *   │ 9. Tách A5 thành "Nhà trọ — ở một mình" / "— ở ghép với bạn"         │
 *   │    (0đ, không tốn câu nào) → phễu tuyển cặp cho khảo sát đối chứng   │
 *   │ 9b. BỎ câu "muốn ở ghép với giới tính nào" — hệ thống CHỈ ghép cùng  │
 *   │    giới, nên câu đó không có tác dụng. Thay bằng câu cổng ý định     │
 *   │    thuần túy (vẫn giữ chức năng rẽ nhánh). Câu "giới tính của bạn"   │
 *   │    đổi vai thành LỌC CỨNG bắt buộc → thêm help text nói rõ lý do.    │
 *   │ 10. C1 ghi rõ "nếu ở ghép, ghi phần của RIÊNG BẠN" — chiều ngân sách │
 *   │     có trọng số 25%, hiểu sai là lệch gấp đôi ở chiều nặng nhất.     │
 *   │ 11. F4 (email/Zalo) → BẮT BUỘC. Email CTU không suy ra được từ MSSV  │
 *   │     (dạng <tên><mssv>@student.ctu.edu.vn) → bỏ trống là không tạo    │
 *   │     được tài khoản và không mời được vào khảo sát đối chứng đợt 2.   │
 *   └─────────────────────────────────────────────────────────────────────┘
 *   ┌ CẮT ────────────────────────────────────────────────────────────────┐
 *   │ D2 giờ dậy (tương quan mạnh với giờ ngủ) · D7 đồ đạc cá nhân (trùng  │
 *   │ chiều với chén bát) · E2 chatbot-vs-bộ-lọc (xây chatbot dù kết quả   │
 *   │ ra sao → câu trả lời không đổi quyết định nào)                       │
 *   │ 8 phần → 6 phần (mỗi phần là 1 lần tải trang, làm form CẢM GIÁC dài) │
 *   └─────────────────────────────────────────────────────────────────────┘
 *
 * ───────────────────────────────────────────────────────────────────────────
 *  CÁCH CHẠY
 *   1. https://script.google.com → Dự án mới → xóa code mẫu → dán file này
 *   2. ⚠️ SỬA MẢNG `DON_VI` bên dưới cho khớp cơ cấu CTU hiện hành
 *      (đối chiếu ctu_don_vi_dao_tao.json + đề án tuyển sinh)
 *   3. Lưu 💾 → chọn hàm `taoFormKhaoSat` → ▶ Chạy → cấp quyền
 *   4. Nhật ký thực thi in ra LINK GỬI SV + LINK CHỈNH SỬA
 *
 *  ⚠️ Script này TẠO FORM MỚI (không sửa form cũ). Form cũ mới có 1 phiếu thử
 *     nên không mất gì. Sau khi chạy: xóa/lưu trữ form cũ để khỏi phát nhầm.
 *
 *   ⚠️ SỬA HẰNG SỐ `LIEN_HE` bên dưới — form cam kết quyền xóa dữ liệu,
 *      không có kênh liên hệ thì cam kết đó vô hiệu.
 *
 *  SAU KHI CHẠY — 1 việc phải làm tay (Apps Script không đặt được):
 *     Bật "Xáo trộn thứ tự lựa chọn" cho câu B1, B2, E1
 *     (mở form → ⋮ ở góc câu → "Xáo trộn thứ tự lựa chọn")
 * ═══════════════════════════════════════════════════════════════════════════
 */

// ⚠️⚠️ KIỂM TRA LẠI DANH SÁCH NÀY TRƯỚC KHI CHẠY ⚠️⚠️
// Xem ctu_don_vi_dao_tao.json — các dòng đánh dấu "can_kiem_tra" là suy từ
// cơ cấu cũ, chưa xác minh từ nguồn chính thức. Sai tên đơn vị ở câu đầu form
// là mất uy tín ngay lập tức.
// ⚠️ ĐIỀN TRƯỚC KHI CHẠY — form đang cam kết "có thể yêu cầu xóa tài khoản bất cứ
// lúc nào"; không có kênh liên hệ thì đó là lời hứa không thực hiện được.
const LIEN_HE = 'Fanpage: fb.com/…  ·  Zalo nhóm: …  ·  Email: …';   // ← SỬA DÒNG NÀY

const DON_VI = [
  'Trường Bách khoa',
  'Trường Công nghệ Thông tin & Truyền thông',
  'Trường Kinh tế',
  'Trường Nông nghiệp',
  'Trường Sư phạm',
  'Trường Thủy sản',
  'Viện Công nghệ Sinh học & Thực phẩm',
  'Khoa Khoa học Tự nhiên',
  'Khoa Khoa học Xã hội & Nhân văn',
  'Khoa Ngoại ngữ',
  'Khoa Luật',
  'Khoa Môi trường & Tài nguyên Thiên nhiên',
  'Khoa Phát triển Nông thôn (Hòa An)',
  'Khoa Giáo dục Thể chất',
  'Khoa Chính trị',
  'Khoa Dự bị Dân tộc',
  'Khác / chưa có trong danh sách'   // BẮT BUỘC giữ — lối thoát chống chọn bừa
];

// ─── Cặp đối xứng: HÀNH VI ↔ DEAL-BREAKER ───────────────────────────────────
// Hai mảng này PHẢI khớp nhau. Sửa một bên thì sửa cả hai, và cập nhật
// BANG_DOI_CHIEU ở cuối file lẫn hàm passes_hard_filters() trong backend.
const HANH_VI = [
  'Mình hay nấu ăn trong phòng',
  'Mình hay rủ bạn bè về phòng chơi',
  'Người yêu / bạn thân thỉnh thoảng ở lại qua đêm',
  'Mình muốn nuôi thú cưng trong phòng',
  'Mình hay nhậu / tụ tập trong phòng',
  'Mình hay đi chơi về khuya',
  'Tối muộn mình hay còn hoạt động (xem phim, gọi điện, nói chuyện)',
  'Mình sẵn sàng dùng chung đồ (đồ ăn, đồ dùng)',
  'Không điều nào ở trên đúng với mình'
];

const DEAL_BREAKER = [
  'Hút thuốc trong phòng',
  'Nấu ăn trong phòng',
  'Hay dẫn bạn về phòng',
  'Người yêu ở lại qua đêm',
  'Nuôi thú cưng',
  'Nhậu nhẹt trong phòng',
  'Đi chơi về khuya',
  'Ồn ào khuya',
  'Ở bẩn, không dọn dẹp',
  'Mình dễ tính, không có điều nào'
];


function taoFormKhaoSat() {
  const form = FormApp.create('Khảo sát nhu cầu tìm nhà trọ của sinh viên ĐH Cần Thơ');

  form.setDescription(
    '🏠 Bạn đang tìm trọ ở Cần Thơ? Cho tụi mình 5 phút nhé!\n\n' +
    'Tụi mình là nhóm sinh viên Trường Công nghệ Thông tin & Truyền thông, đang làm đề tài ' +
    'nghiên cứu khoa học THS2026-66 — xây một website gom tin nhà trọ quanh CTU từ nhiều nguồn, ' +
    'có bản đồ chỉ đường tới trường, cảnh báo tin lừa đảo, và gợi ý bạn cùng phòng hợp tính.\n\n' +
    'Khảo sát này giúp tụi mình biết SV thật sự cần gì. Toàn bộ là BẤM CHỌN — chỉ có 1 ô gõ chữ, ' +
    'và ô đó không bắt buộc.\n\n' +
    '── Về thông tin của bạn ──\n' +
    '• Câu trả lời về thói quen và ý kiến của bạn chỉ được dùng ở dạng TỔNG HỢP, KHÔNG nêu tên, ' +
    'trong báo cáo nghiên cứu. Dữ liệu dùng cho báo cáo được lưu ở dạng ẩn danh, không kèm tên hay MSSV.\n' +
    '• Cuối form có phần đăng ký dùng thử (họ tên, MSSV, liên hệ) — KHÔNG BẮT BUỘC. ' +
    'Bạn bỏ qua vẫn gửi form bình thường.\n' +
    '• Nếu bạn đăng ký dùng thử: thông tin định danh chỉ nhóm nghiên cứu giữ, không công khai, ' +
    'không chia sẻ cho bên thứ ba, không dùng cho quảng cáo. Bạn có thể yêu cầu xóa tài khoản bất cứ lúc nào.\n' +
    '• Có thắc mắc, muốn rút khỏi khảo sát hoặc yêu cầu xóa dữ liệu — nhắn tụi mình qua:\n  ' + LIEN_HE + '\n\n' +
    'Cảm ơn bạn nhiều! 🙏'
  );

  form.setProgressBar(true);
  form.setCollectEmail(false);
  // Tài khoản trong Workspace 'Students of Can Tho University' tạo form mặc định
  // có thể bị giới hạn chỉ người trong tổ chức mở được → SV dùng Gmail cá nhân
  // trên điện thoại sẽ thấy 'Bạn cần có quyền truy cập' và bỏ đi. Tắt ràng buộc đó.
  form.setRequireLogin(false);
  form.setLimitOneResponsePerUser(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage(
    'Xong rồi, cảm ơn bạn siêu nhiều! 🎉\n\n' +
    'Khi website chạy được, tụi mình sẽ gửi link cho bạn dùng thử đầu tiên.\n\n' +
    'Có góp ý, thắc mắc hoặc muốn xóa dữ liệu của mình — nhắn tụi mình qua:\n' + LIEN_HE
  );

  // ═══ TRANG 0 — câu sàng lọc (đứng một mình để phân nhánh được) ═══════════
  const sangLoc = form.addMultipleChoiceItem()
    .setTitle('Bạn hiện là sinh viên Đại học Cần Thơ?')
    .setHelpText(
      'Đề tài của tụi mình giới hạn ở khu vực quanh cơ sở Cần Thơ (quận Ninh Kiều) — ' +
      'khu I, II, III nằm cách nhau chưa tới 2,5 km nên coi như một cụm. ' +
      'Khu Hòa An cách hơn 30 km nên tạm thời chưa phục vụ được, mong bạn thông cảm!'
    )
    .setRequired(true);

  // ═══ TRANG 1 — Phần A + B (gộp: cùng là "về bạn và chuyện tìm trọ") ══════
  const trang1 = form.addPageBreakItem()
    .setTitle('📋 Phần A — Vài thông tin về bạn');

  form.addMultipleChoiceItem()
    .setTitle('Bạn là sinh viên năm mấy?')
    .setChoiceValues(['Năm 1', 'Năm 2', 'Năm 3', 'Năm 4', 'Năm 5 trở lên', 'Học viên cao học'])
    .setRequired(true);

  form.addListItem()
    .setTitle('Bạn học ở Trường / Khoa / Viện nào?')
    .setChoiceValues(DON_VI)
    .setRequired(true);

  // Ô gõ chữ DUY NHẤT của phần công khai — và không bắt buộc.
  // Ngành chỉ để dành cho sau này khi hệ thống đông người; thuật toán hiện
  // dùng cấp Trường/Khoa ở trên, nên ô này bẩn cũng không ảnh hưởng gì.
  form.addTextItem()
    .setTitle('Ngành bạn đang học (không bắt buộc)')
    .setHelpText('Ví dụ: Kỹ thuật phần mềm, Kế toán, Nuôi trồng thủy sản… Bỏ trống cũng được nhé.')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('Hiện tại bạn đang ở đâu?')
    .setChoiceValues([
      'Ký túc xá',
      'Nhà trọ — ở một mình',
      'Nhà trọ — ở ghép với bạn',
      'Nhà người thân / ở nhờ',
      'Nhà riêng của gia đình',
      'Khác'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Giới tính của bạn')
    .setHelpText(
      'Tính năng ghép bạn ở của tụi mình CHỈ ghép giữa những người cùng giới tính, ' +
      'nên cần thông tin này. Bạn chọn "Không muốn nêu" vẫn gửi form bình thường — ' +
      'chỉ là tạm thời chưa dùng được tính năng ghép bạn thôi.'
    )
    .setChoiceValues(['Nam', 'Nữ', 'Không muốn nêu'])
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('🔍 Chuyện tìm trọ của bạn');

  form.addCheckboxItem()
    .setTitle('Bạn tìm phòng trọ bằng những cách nào?')
    .setHelpText('Chọn nhiều đáp án. Chưa từng tìm thì bỏ qua câu này.')
    .setChoiceValues([
      'Group Facebook (Nhà trọ Cần Thơ, Chợ SV CTU…)',
      'Hỏi bạn bè / anh chị khóa trên',
      'Chạy xe quanh khu vực xem bảng "Cho thuê phòng"',
      'Website tin đăng (Phongtro123, Chợ Tốt, Mogi…)',
      'Môi giới / cò nhà trọ',
      'Hội SV, kênh của trường',
      'Khác'
    ])
    .setRequired(false);

  const b2 = form.addCheckboxItem()
    .setTitle('Khó khăn lớn nhất khi tìm trọ là gì?')
    .setHelpText('Chọn tối đa 3 đáp án')
    .setChoiceValues([
      'Thông tin rải rác nhiều nơi, phải tìm thủ công',
      'Tin đăng đã cho thuê rồi nhưng chưa gỡ',
      'Giá đăng khác giá thực tế khi tới xem',
      'Không biết phòng cách trường bao xa / đi mất bao lâu',
      'Không có ảnh thật, ảnh không đúng phòng',
      'Sợ bị lừa đặt cọc',
      'Không tìm được người ở ghép để chia tiền',
      'Không biết khu nào an ninh tốt',
      'Khác'
    ])
    .setRequired(true);
  b2.setValidation(FormApp.createCheckboxValidation()
    .requireSelectAtMost(3).build());

  form.addCheckboxItem()
    .setTitle('Bạn từng gặp tình huống nào dưới đây chưa?')
    .setHelpText('Chọn nhiều đáp án')
    .setChoiceValues([
      'Liên hệ thì phòng đã cho thuê từ lâu',
      'Giá thực tế cao hơn giá đăng',
      'Bị đòi đặt cọc trước khi được xem phòng',
      'Bị mất tiền cọc',
      'Phòng thực tế khác hẳn ảnh',
      'Chưa gặp trường hợp nào'
    ])
    .setRequired(false);

  // ═══ TRANG 2 — Phần C: nhu cầu phòng ════════════════════════════════════
  form.addPageBreakItem()
    .setTitle('💰 Phần B — Bạn cần phòng như thế nào?');

  form.addMultipleChoiceItem()
    .setTitle('Ngân sách thuê phòng mỗi tháng — số tiền BẠN trả (chưa tính điện nước)')
    .setHelpText('Nếu ở ghép, ghi phần của riêng bạn nhé — không phải tiền cả phòng.')
    .setChoiceValues([
      'Dưới 1,5 triệu', '1,5 – 2 triệu', '2 – 2,5 triệu', '2,5 – 3,5 triệu', 'Trên 3,5 triệu'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Bạn dự định ở như thế nào?')
    .setChoiceValues([
      'Ở một mình', 'Ở ghép 2 người', 'Ở ghép 3 người trở lên',
      'Ở với người yêu / người thân', 'Chưa quyết định'
    ])
    .setRequired(true);

  // Thay lưới Likert 7 hàng. Nếu muốn nới lỏng, đổi requireSelectExactly(3)
  // thành .requireSelectAtLeast(1).requireSelectAtMost(3) — nhưng khi đó mỗi
  // người góp số phiếu khác nhau, trọng số khó so sánh giữa các yếu tố hơn.
  const c3 = form.addCheckboxItem()
    .setTitle('Ba yếu tố quan trọng NHẤT khi bạn chọn phòng?')
    .setHelpText('Chọn đúng 3 — chọn hết thì tụi mình không biết cái nào bạn coi trọng hơn 🙂')
    .setChoiceValues([
      'Giá thuê rẻ',
      'Gần trường / đi lại nhanh',
      'An ninh khu vực',
      'Tiện nghi (máy lạnh, wifi, WC riêng…)',
      'Giờ giấc tự do, chủ không ở chung',
      'Có chỗ để xe',
      'Gần chợ / quán ăn'
    ])
    .setRequired(true);
  c3.setValidation(FormApp.createCheckboxValidation()
    .requireSelectExactly(3).build());

  form.addMultipleChoiceItem()
    .setTitle('Bạn chấp nhận đi từ phòng tới trường tối đa bao lâu? (xe máy)')
    .setHelpText('Tính tới Khu II (đường 3 Tháng 2) — khu chính, nơi tập trung SV đông nhất.')
    .setChoiceValues([
      'Dưới 5 phút', '5–10 phút', '10–15 phút', '15–20 phút', 'Trên 20 phút cũng được nếu rẻ'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('Tiện ích nào là BẮT BUỘC phải có?')
    .setHelpText('Chọn nhiều đáp án')
    .setChoiceValues([
      'Wifi / internet', 'Máy lạnh', 'WC riêng trong phòng', 'Chỗ để xe',
      'Được nấu ăn / có bếp', 'Tủ lạnh', 'Máy giặt', 'Giờ giấc tự do', 'Gác lửng / có gác'
    ])
    .setRequired(false);

  // ═══ TRANG 3 — Phần D: hồ sơ ở ghép ═════════════════════════════════════
  form.addPageBreakItem()
    .setTitle('🛏️ Phần C — Bạn là kiểu bạn cùng phòng nào?')
    .setHelpText(
      'Phần quan trọng nhất đây! Hệ thống của tụi mình có tính năng gợi ý bạn cùng phòng hợp tính — ' +
      'để làm được thì cần hiểu thói quen sinh hoạt của bạn.\n\n' +
      'Không có câu trả lời đúng/sai, và đừng chọn theo kiểu "cho đẹp" nhé — ghép trúng người lệch ' +
      'giờ giấc với mình mới là cực. Cứ chọn đúng thực tế!\n\n' +
      '🔒 Hệ thống chỉ ghép giữa những người CÙNG GIỚI TÍNH và đã xác thực bằng MSSV.'
    );

  // CỔNG: người không có nhu cầu ở ghép nhảy thẳng sang Phần D, khỏi phải lội
  // 11 câu thói quen không dùng vào việc gì. Phải đứng MỘT MÌNH trên trang này —
  // Google Forms chỉ rẽ nhánh khi người trả lời rời trang.
  const cong = form.addMultipleChoiceItem()
    .setTitle('Bạn có muốn dùng tính năng tìm bạn ở ghép không?')
    .setHelpText('Chọn "Không" thì bỏ qua luôn phần này cho đỡ mất thời gian của bạn nhé.')
    .setRequired(true);

  form.addPageBreakItem()
    .setTitle('Thói quen sinh hoạt của bạn');

  form.addMultipleChoiceItem()
    .setTitle('Ngày thường, bạn đi ngủ lúc mấy giờ?')
    .setChoiceValues(['Trước 22h', '22h – 24h', 'Sau 0h'])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Bạn cùng phòng bật nhạc / xem phim lúc 23h. Bạn sẽ:')
    .setChoiceValues([
      'Không sao cả, mình vẫn ngủ được',
      'Hơi khó chịu nhưng không nói gì',
      'Nhắc nhẹ bạn vặn nhỏ lại',
      'Rất khó chịu, phải nói thẳng ngay'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Chén bát sau khi ăn xong, bạn thường:')
    .setChoiceValues([
      'Rửa ngay lập tức',
      'Rửa trong ngày hôm đó',
      'Để 1–2 ngày rồi rửa một lượt',
      'Để đến khi hết chén sạch',
      'Thường để người khác rửa'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Về thuốc lá:')
    .setChoiceValues([
      'Mình có hút và cần hút trong phòng',
      'Mình có hút nhưng ra ngoài hút',
      'Mình không hút, và KHÔNG chịu được người ở chung hút',
      'Mình không hút, nhưng người khác hút thì cũng được'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Tiền điện máy lạnh — bạn thuộc kiểu nào?')
    .setChoiceValues([
      'Bật máy lạnh gần như cả đêm, tiền điện bao nhiêu cũng được',
      'Bật lúc nóng thôi, có ý thức tiết kiệm',
      'Ít khi bật, quạt là đủ',
      'Mình rất để ý tiền điện, hay nhắc nhau tắt'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Chuyện tiền nong khi ở chung:')
    .setChoiceValues([
      'Chia sòng phẳng từng khoản, tính rõ ràng ngay',
      'Chia đều cho nhanh, không tính chi li',
      'Ai ứng trước cũng được, cuối tháng gom lại',
      'Mình ngại nói chuyện tiền bạc'
    ])
    .setRequired(true);

  // ⚠️ CẶP ĐỐI XỨNG — câu này và câu deal-breaker phía dưới phải khớp danh sách
  form.addCheckboxItem()
    .setTitle('Những điều nào ĐÚNG với bạn?')
    .setHelpText('Chọn nhiều đáp án. Cứ thành thật — ghép trúng người khó chịu với thói quen của mình mới mệt.')
    .setChoiceValues(HANH_VI)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Bạn giống người nào hơn?')
    .setHelpText('Chọn 1 người bạn thấy giống mình hơn — kể cả khi không giống hoàn toàn')
    .setChoiceValues([
      '🌙 An — ngủ trễ dậy trễ, phòng hơi bừa nhưng dễ tính, ai làm gì cũng kệ',
      '☀️ Bình — ngủ sớm dậy sớm, thích phòng gọn gàng, cần yên tĩnh để học'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('Điều bạn KHÔNG chấp nhận được ở người ở ghép:')
    .setHelpText('Chọn nhiều đáp án. Đây là bộ lọc cứng — người vi phạm sẽ không bao giờ được gợi ý cho bạn.')
    .setChoiceValues(DEAL_BREAKER)
    .setRequired(true);

  // ── 2 câu lọc cứng MỚI ──────────────────────────────────────────────────
  form.addMultipleChoiceItem()
    .setTitle('Bạn cần phòng từ khi nào?')
    .setChoiceValues([
      'Càng sớm càng tốt (trong tháng này)',
      'Đầu học kỳ tới',
      'Trong 2–3 tháng tới',
      'Chưa gấp, đang tìm hiểu trước'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('Về chuyện ở ghép, hiện tại bạn:')
    .setChoiceValues([
      'Chưa có phòng — muốn tìm người rồi cùng đi tìm phòng',
      'Đã có phòng — muốn tìm người vào ở chung',
      'Đang ở ghép rồi — muốn tìm người thay thế',
      'Chỉ tìm hiểu thôi, chưa quyết'
    ])
    .setRequired(true);

  // ═══ TRANG 4 — Phần E + câu rẽ nhánh F1 ═════════════════════════════════
  const trangD = form.addPageBreakItem()
    .setTitle('💡 Phần D — Ý kiến về hệ thống')
    .setHelpText('Sắp xong rồi! Tụi mình đang xây website gom tin trọ quanh CTU từ nhiều nguồn, có bản đồ và vài tính năng AI.');

  const e1 = form.addCheckboxItem()
    .setTitle('Tính năng nào bạn thấy hữu ích nhất?')
    .setHelpText('Chọn tối đa 3 đáp án')
    .setChoiceValues([
      'Gom tin trọ từ nhiều trang về một chỗ',
      'Bản đồ hiển thị phòng + số phút đi tới trường',
      'Cảnh báo tin có dấu hiệu rủi ro / lừa đảo',
      'Gợi ý phòng hợp gu dựa trên sở thích của bạn',
      'Tìm bạn cùng phòng phù hợp tính cách',
      'Chatbot hỏi đáp bằng tiếng Việt ("phòng 2 triệu gần khu II có máy lạnh?")',
      'Thông báo khi có phòng mới khớp tiêu chí'
    ])
    .setRequired(true);
  e1.setValidation(FormApp.createCheckboxValidation()
    .requireSelectAtMost(3).build());

  form.addSectionHeaderItem()
    .setTitle('🎓 Đăng ký dùng thử (không bắt buộc)')
    .setHelpText(
      'Tính năng ghép bạn ở của tụi mình CHỈ ghép giữa các SV CTU đã xác thực bằng MSSV, ' +
      'và CHỈ ghép giữa những người cùng giới tính — để bạn yên tâm là người được ghép cũng là ' +
      'sinh viên trường mình, không phải người lạ trên mạng.\n\n' +
      'Người được ghép chỉ nhìn thấy TÊN và TÓM TẮT THÓI QUEN SINH HOẠT của bạn. ' +
      'MSSV và thông tin liên hệ của bạn CHỈ hiện ra sau khi CẢ HAI BÊN cùng bấm đồng ý kết nối — ' +
      'trước đó không ai xem được.\n\n' +
      'Bạn chọn "Không" vẫn gửi form bình thường và phần trả lời phía trên vẫn có giá trị đầy đủ.'
    );

  const f1 = form.addMultipleChoiceItem()
    .setTitle('Bạn có muốn dùng thử website và được ghép bạn cùng phòng không?')
    .setRequired(true);

  // ═══ TRANG 5 — chỉ hiện với người chọn "Có" ở F1 ════════════════════════
  const trangF = form.addPageBreakItem()
    .setTitle('🎓 Thông tin để tạo tài khoản dùng thử')
    .setHelpText('Chỉ nhóm nghiên cứu giữ. Bạn có thể yêu cầu xóa bất cứ lúc nào.');

  form.addTextItem()
    .setTitle('Họ và tên của bạn')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Mã số sinh viên')
    .setHelpText('Ví dụ: B2105678. Dùng để xác nhận bạn là SV CTU, không hiển thị cho ai khác.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Email hoặc số Zalo để tụi mình liên hệ')
    .setHelpText('Chỉ dùng gửi link dùng thử, không spam.')
    .setRequired(true);   // Bắt buộc: không có cái này thì không tạo được tài khoản

  // ═══ NỐI NHÁNH — làm SAU CÙNG, khi mọi trang đã tồn tại ═════════════════
  sangLoc.setChoices([
    sangLoc.createChoice('Có — mình học ở cơ sở Cần Thơ (khu I, II hoặc III)',
                         FormApp.PageNavigationType.CONTINUE),
    sangLoc.createChoice('Có — nhưng mình học ở khu Hòa An (Hậu Giang)',
                         FormApp.PageNavigationType.SUBMIT),
    sangLoc.createChoice('Không phải sinh viên CTU',
                         FormApp.PageNavigationType.SUBMIT)
  ]);

  cong.setChoices([
    cong.createChoice('Có — mình đang tìm hoặc sắp tìm người ở ghép',
                      FormApp.PageNavigationType.CONTINUE),
    cong.createChoice('Không — mình không có nhu cầu ở ghép', trangD)
  ]);

  f1.setChoices([
    f1.createChoice('Có, mình muốn dùng thử', trangF),
    f1.createChoice('Không, mình chỉ tham gia khảo sát thôi', FormApp.PageNavigationType.SUBMIT)
  ]);

  Logger.log('════════════════════════════════════════════════');
  Logger.log('LINK GỬI SV   : ' + form.getPublishedUrl());
  Logger.log('LINK CHỈNH SỬA: ' + form.getEditUrl());
  Logger.log('════════════════════════════════════════════════');
  Logger.log('CÒN 1 VIỆC TAY: bật "Xáo trộn thứ tự lựa chọn" cho câu B1, B2, E1');
}


/* ═══════════════════════════════════════════════════════════════════════════
 *  BẢNG ĐỐI CHIẾU — dùng khi viết passes_hard_filters() ở backend
 * ═══════════════════════════════════════════════════════════════════════════
 *
 *  Nguyên tắc: MỖI deal-breaker A khai PHẢI có một trường của B để đối chiếu.
 *  Thiếu cặp nào thì deal-breaker đó nằm im trong DB và không bao giờ lọc được
 *  ai — lỗi âm thầm, chỉ lộ ra khi hội đồng hỏi.
 *
 *   Deal-breaker của A            ←→  Trường của B
 *   ─────────────────────────────────────────────────────────────────────────
 *   Hút thuốc trong phòng         ←→  câu thuốc lá == 'có hút và cần hút trong phòng'
 *   Nấu ăn trong phòng            ←→  hành_vi chứa 'hay nấu ăn trong phòng'
 *   Hay dẫn bạn về phòng          ←→  hành_vi chứa 'hay rủ bạn bè về phòng chơi'
 *   Người yêu ở lại qua đêm       ←→  hành_vi chứa 'người yêu / bạn thân… ở lại qua đêm'
 *   Nuôi thú cưng                 ←→  hành_vi chứa 'muốn nuôi thú cưng trong phòng'
 *   Nhậu nhẹt trong phòng         ←→  hành_vi chứa 'hay nhậu / tụ tập trong phòng'
 *   Đi chơi về khuya              ←→  hành_vi chứa 'hay đi chơi về khuya'
 *   Ồn ào khuya                   ←→  hành_vi chứa 'tối muộn… còn hoạt động'
 *   Ở bẩn, không dọn dẹp          ←→  câu chén bát ∈ {'để đến khi hết chén sạch',
 *                                                     'thường để người khác rửa'}
 *
 *  ĐÃ BỎ 'Trả tiền trọ trễ' khỏi danh sách deal-breaker: không ai tự khai mình
 *  hay trả trễ, nên không thể có trường đối chiếu. Thông tin này chỉ lấy được
 *  từ đánh giá SAU khi đã ở chung (post-match feedback), không lấy từ hồ sơ.
 *
 *  'Mình sẵn sàng dùng chung đồ' KHÔNG có deal-breaker đối ứng — đúng như thiết
 *  kế: nó là chiều TÍNH ĐIỂM (mang giá trị dương), không phải chiều LỌC.
 *
 *  Bộ lọc cứng ở backend:
 *      if set(A.hanh_vi) & set(B.deal_breakers): return REJECT
 *      if set(B.hanh_vi) & set(A.deal_breakers): return REJECT
 *      if A.gender != B.gender or A.gender is None: return REJECT   # chỉ ghép cùng giới
 *      # + ngân sách lệch >1 bậc, thời điểm cần phòng, kịch bản ở ghép
 *
 *  GIỚI TÍNH — lọc cứng tuyệt đối, KHÔNG có tùy chọn của người dùng:
 *  đề tài chỉ ghép cùng giới, nên không hỏi "muốn ghép với giới nào". Người chọn
 *  "Không muốn nêu" ở câu giới tính KHÔNG vào được pool ghép (gender IS NULL →
 *  REJECT). Trong app, nhắc họ cập nhật giới tính để bật tính năng ghép bạn.
 *  Ghi rõ chính sách này vào SRS mục FR-5 + phần đạo đức của báo cáo — đây là
 *  quyết định thiết kế có chủ đích (an toàn cho SV), không phải thiếu sót.
 * ═══════════════════════════════════════════════════════════════════════════ */

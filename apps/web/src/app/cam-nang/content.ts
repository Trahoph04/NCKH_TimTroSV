// Nội dung Cẩm nang (bản tạm 08/10/2026) — sửa/bổ sung ở file này, trang page.tsx chỉ hiển thị.
//
// Quy ước nội dung:
// - Viết lại bằng lời của nhóm, KHÔNG chép nguyên văn bài tham khảo (ghi nguồn ở REFERENCES).
// - Mọi ý pháp lý phải có `basis` trỏ tới điều khoản thật — văn bản gốc nằm ở apps/api/chatbot_corpus (chatbot dùng
//   cùng kho này). Thuyết minh mục 13.2: đề tài KHÔNG đi sâu pháp lý hợp đồng ⇒ chỉ nêu điều cần biết + dẫn nguồn.
// - Số liệu "phổ biến trên Trọ CTU" lấy từ tin đang hiển thị có ghi rõ giá (đo 08/10/2026), không phải giá quy định.

export type Basis = { label: string; href?: string };

export type Tip = {
  id: string;
  title: string;
  lead?: string;
  items: string[];
  basis?: Basis[];
};

export type Section = {
  id: "ktx" | "tim-phong" | "o-ghep" | "phap-ly";
  title: string;
  short: string;
  intro: string;
  tips: Tip[];
};

export const UPDATED_AT = "12/10/2026";

const LAW = {
  civil328: { label: "Bộ luật Dân sự 2015 — Điều 328 (Đặt cọc)", href: "https://congan.daklak.gov.vn/laws/detail/Bo-luat-Dan-su-163/" },
  housing163: { label: "Luật Nhà ở — Điều 163 (Hợp đồng về nhà ở)", href: "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-79-vbhn-vpqh-469209.htm" },
  housing170_172: { label: "Luật Nhà ở — Điều 170, 172 (Giá thuê; đơn phương chấm dứt hợp đồng)", href: "https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-79-vbhn-vpqh-469209.htm" },
  residence27_28: { label: "Luật Cư trú 2020 — Điều 27, 28 (Đăng ký tạm trú)", href: "https://congbao.chinhphu.vn/van-ban/luat-so-68-2020-qh14-32684/33716.htm" },
  decree58: { label: "Nghị định 58/2026/NĐ-CP — Điều 4 khoản 2 (giấy tờ chỗ ở thuê không cần công chứng)", href: "https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-58-2026-nd-cp-468975/62899.htm" },
  power12: { label: "Thông tư 60/2025/TT-BCT — Điều 12 khoản 5 (giá điện cho người thuê nhà)", href: "https://vanban.chinhphu.vn/?docid=216125&orggroupid=4&pageid=27160" },
  water215: { label: "Quyết định 215/QĐ-UBND TP Cần Thơ (giá nước sạch sinh hoạt)", href: "https://capnuoccantho2.com.vn/View.aspx?wc=63&wp=332" },
  fire20: { label: "Luật Phòng cháy, chữa cháy và cứu nạn, cứu hộ 2024 — Điều 20 (Phòng cháy đối với nhà ở)", href: "https://congbao.chinhphu.vn/van-ban-dang-cong-bao/quoc-hoi-c31/trang-19.htm" },
  scamWarning: { label: "Bộ Công an — Cảnh báo thủ đoạn lừa đảo tân sinh viên mùa tựu trường", href: "https://bocongan.gov.vn/bai-viet/catp-hai-phong-canh-bao-cac-thu-doan-lua-dao-bua-vay-hoc-sinh-tan-sinh-vien-mua-tuu-truong-1787629964" },
  fireWarning: { label: "Công an tỉnh Phú Thọ — An toàn PCCC và kỹ năng thoát nạn tại nhà trọ", href: "https://congan.phutho.gov.vn/article/Tang-cuong-bao-dam-an-toan-phong-chay-chua-chay-27208-57" },
} satisfies Record<string, Basis>;

// Nguồn chính thức của ĐH Cần Thơ về KTX — cùng 4 tài liệu chatbot dùng (apps/api/chatbot_corpus/ctu-*.json, tải 04–07/10/2026)
const CTU = {
  facilities: { label: "TT. Phục vụ Sinh viên ĐHCT — Cơ sở vật chất, loại phòng và mức phí KTX", href: "https://ssc.ctu.edu.vn/hoat/160-cs1.html" },
  rules: { label: "Nội quy Ký túc xá Trường ĐH Cần Thơ (bản trích 09/2025)", href: "https://ssc.ctu.edu.vn/images/upload/Noiquy_KTX_trich_092025.pdf" },
  registration: { label: "Thông báo 307/TB-CTSV ngày 21/7/2026 — Đăng ký ở KTX học kỳ 1 năm học 2026–2027", href: "https://ssc.ctu.edu.vn/thong-bao/226-dang-ky-o-ky-tuc-xa-hoc-ky-1-nam-hoc-2026-2027.html" },
  newStudents: { label: "Cổng tân sinh viên ĐHCT — Hướng dẫn đăng ký ở Ký túc xá", href: "https://tansinhvien.ctu.edu.vn/sinh-hoat/huong-dan-tan-sinh-vien-dang-ky-o-ky-tuc-xa" },
} satisfies Record<string, Basis>;

// Mức phí công bố (ssc.ctu.edu.vn, đọc 07/10/2026) — dùng cho khối "KTX hay thuê trọ?" ở page.tsx
export const KTX_FEE = { min: 220_000, max: 475_000 };

export const SECTIONS: Section[] = [
  {
    id: "ktx",
    title: "Ký túc xá Đại học Cần Thơ",
    short: "Ký túc xá CTU",
    intro:
      "Trước khi đi tìm trọ, xem KTX của trường có hợp với bạn không: rẻ nhất, an ninh, ngay trong khu II — đổi lại phải theo nội quy và đăng ký lại mỗi học kỳ. Thông tin tóm từ các trang chính thức của trường; hạn đăng ký thay đổi theo từng học kỳ nên luôn xem thông báo mới nhất.",
    tips: [
      {
        id: "tong-quan",
        title: "KTX có những khu nào",
        items: [
          "3 khu, sức chứa khoảng 8.780 sinh viên. Khu A và khu B nằm ngay trong khu II (đường 3/2); khu C ở cơ sở Hậu Giang (khoảng 250 chỗ, chỉ xếp sinh viên năm nhất và năm cuối học tại cơ sở này).",
          "Phòng 3–8 sinh viên, mỗi người có giường và tủ riêng, phòng có khu vệ sinh và wifi riêng.",
          "Có hàng rào, camera, bảo vệ chuyên nghiệp; trong khuôn viên có căn tin, nhà ăn và siêu thị mini.",
          "Liên hệ: văn phòng KTX khu A (02923) 872 178 · khu B (02923) 872 275.",
        ],
        basis: [CTU.facilities, CTU.registration],
      },
      {
        id: "chi-phi",
        title: "Chi phí ở KTX",
        items: [
          "Phí chỗ ở 220.000–475.000 đ/sinh viên/tháng tuỳ loại phòng, nộp một lần cho cả học kỳ (học kỳ 1 năm 2026–2027 tính 3,5 tháng, từ 07/9 đến 18/12/2026).",
          "Điện, nước tính theo đồng hồ riêng của từng phòng, cả phòng nộp hàng tháng theo số thực tế.",
          "Xe đạp gửi miễn phí; xe máy, xe điện 25.000 đ/tháng (mỗi người ưu đãi 1 xe).",
          "Ở lại trong kỳ nghỉ Tết phải đóng thêm phí 2 tuần.",
        ],
        basis: [CTU.facilities, CTU.newStudents, CTU.registration],
      },
      {
        id: "loai-phong",
        title: "Phòng được nấu ăn và không được nấu ăn",
        items: [
          "Phòng không nấu ăn (4 hoặc 8 người, có ở cả khu A và B): chỉ được dùng ấm đun siêu tốc, không dùng nồi đa năng.",
          "Phòng được nấu ăn (3, 4, 5, 6 hoặc 8 người, chủ yếu ở khu A): sinh viên tự trang bị dụng cụ nấu.",
          "Chọn loại phòng ngay lúc đăng ký — muốn tự nấu cho tiết kiệm thì ghi nguyện vọng phòng được nấu ăn.",
        ],
        basis: [CTU.facilities, CTU.newStudents, { label: "Nội quy KTX — Điều 3 khoản 8", href: CTU.rules.href }],
      },
      {
        id: "dang-ky",
        title: "Đăng ký ở KTX",
        items: [
          "Đăng ký theo từng học kỳ qua Hệ thống Quản lý KTX của trường (hoặc qua email, trực tiếp tại văn phòng Trung tâm Phục vụ Sinh viên). Tân sinh viên chưa có tài khoản điền mẫu đăng ký nhu cầu trên cổng tân sinh viên.",
          "Có thể đăng ký theo nhóm và ghi nguyện vọng phòng; trường ưu tiên nhóm đủ người cho một phòng và nộp phí đúng hạn — rủ bạn cùng lớp đăng ký chung.",
          "Sinh viên đang ở chỉ cần nộp phí đúng hạn cho học kỳ sau. Quá hạn nộp phí, chỗ đã xếp bị huỷ.",
          "Học kỳ 1 năm 2026–2027: nộp phí 04–07/8/2026, sinh viên mới nhận chỗ từ 07/9/2026 — học kỳ sau xem thông báo mới.",
        ],
        basis: [CTU.registration, CTU.newStudents, { label: "Nội quy KTX — Điều 2 khoản 2, 4", href: CTU.rules.href }],
      },
      {
        id: "tra-cho",
        title: "Chuyển chỗ, trả chỗ và hoàn phí",
        items: [
          "Trả chỗ trước hạn KHÔNG được hoàn phí — trừ khi trả trong 7 ngày kể từ ngày được duyệt chỗ trên hệ thống và có lý do chính đáng.",
          "Muốn đổi sang phòng khác phải được Trung tâm Phục vụ Sinh viên đồng ý, khi còn chỗ trống.",
          "Hết hạn ở: bàn giao chỗ, vệ sinh phòng; tốt nghiệp mà chưa trả chỗ thì hệ thống còn báo nợ.",
        ],
        basis: [CTU.newStudents, CTU.registration, { label: "Nội quy KTX — Điều 2, Điều 4 khoản 8", href: CTU.rules.href }],
      },
      {
        id: "noi-quy",
        title: "Nội quy nên biết trước khi chọn KTX",
        items: [
          "Giờ yên tĩnh 12–13 giờ và 23 giờ đến 5 giờ sáng; ra vào khu KTX mang thẻ sinh viên.",
          "Không qua khu ở của giới khác, không tiếp khách trong phòng; người thân muốn ở lại qua đêm phải đăng ký với văn phòng.",
          "Không hút thuốc, không uống rượu bia, không nấu ăn ngoài các dãy cho phép; không nuôi vật nuôi, không tự ý thêm kệ tủ hay dán giấy lên tường.",
          "Được dùng máy tính, máy in, bàn ủi, ấm nước công suất nhỏ, quạt bàn; vắng khỏi KTX nhiều ngày phải báo phòng trưởng.",
        ],
        basis: [{ label: "Nội quy KTX — Điều 2 đến Điều 5", href: CTU.rules.href }],
      },
    ],
  },
  {
    id: "tim-phong",
    title: "Lưu ý khi tìm phòng",
    short: "Tìm phòng",
    intro:
      "Từ lúc tính ngân sách tới ngày nhận phòng. Nguyên tắc chung: xem tận nơi, hỏi rõ mọi khoản phí và không chuyển tiền khi chưa chắc chắn.",
    tips: [
      {
        id: "ngan-sach",
        title: "Tính đủ chi phí và chọn khu vực",
        items: [
          "Cộng tổng chi phí mỗi tháng: tiền phòng + điện + nước + wifi, rác, giữ xe — đừng chỉ nhìn giá phòng.",
          "Chuẩn bị sẵn tiền cọc (phổ biến 1 tháng) và tiền phòng tháng đầu.",
          "Ưu tiên chỗ đi tới trường dưới 10 phút; trên Trọ CTU có số phút đi xe tới khu I, II, III và bản đồ tiện ích quanh phòng.",
          "Hỏi người dân xung quanh: khu đó có ngập khi mưa lớn hoặc triều cường không, an ninh hẻm ra sao, đường về buổi tối có sáng không.",
          "Cân nhắc kỹ chỗ quá vắng, hẻm sâu không đèn, hoặc sát quán nhậu, karaoke nếu bạn cần yên tĩnh để học.",
        ],
      },
      {
        id: "xem-phong",
        title: "Đi xem phòng: kiểm tra những gì",
        lead: "Luôn xem tận nơi, nên rủ thêm một người đi cùng; nếu được hãy ghé lại một lần vào buổi tối.",
        items: [
          "Cửa, khóa, cửa sổ, độ thông thoáng, mùi ẩm mốc, tường thấm; nhà vệ sinh, nước nóng, ổ cắm điện.",
          "Tắt hết thiết bị rồi xem đồng hồ điện có còn chạy không; mở vòi để thử áp lực nước.",
          "Chỗ để xe, cổng có khóa riêng hoặc vân tay, camera, lối thoát hiểm, bình chữa cháy.",
          "Ở chung chủ hay không, giờ giấc ra vào, có được nấu ăn, bạn bè đến chơi, nuôi thú cưng không.",
          "Hỏi nhỏ người đang ở trọ: chủ trọ có dễ chịu không, có khoản phí nào phát sinh, có từng mất đồ không.",
        ],
      },
      {
        id: "chi-phi",
        title: "Hỏi rõ các khoản phí trước khi cọc",
        items: [
          "Điện tính bao nhiêu một số (kWh); nước tính theo khối (m³) hay theo đầu người; wifi, rác, giữ xe thu thế nào.",
          "Đồng hồ điện, nước riêng từng phòng hay dùng chung, chia ra sao.",
          "Giá phòng có giữ nguyên trong suốt thời hạn hợp đồng không, khi nào được tăng.",
          "Mức phổ biến trên Trọ CTU (tin có ghi rõ, 10/2026): điện 4.000đ/kWh; nước 10.000–12.000đ/m³ hoặc 70.000–100.000đ/người/tháng; cọc 1 tháng. Cao hơn nhiều thì hỏi lý do.",
          "Cân nhắc kỹ nơi đòi trả trước nhiều tháng tiền phòng ngay từ đầu — ở không hợp thì rất khó lấy lại.",
        ],
        basis: [LAW.power12, LAW.water215],
      },
      {
        id: "lua-dao",
        title: "Dấu hiệu lừa đảo cần tránh",
        items: [
          "Giá rẻ bất thường, ảnh đẹp như khách sạn, rồi thúc “nhiều người hỏi lắm, chuyển cọc giữ chỗ ngay” — không chuyển tiền khi chưa xem phòng tận mắt.",
          "Người đăng không phải chủ trọ, không cho xem phòng, hoặc hẹn gặp ở chỗ khác.",
          "Gửi đường link lạ để “xác nhận đặt cọc”, xin ảnh CCCD, mã OTP, mật khẩu ngân hàng — dừng lại ngay.",
          "Trên Trọ CTU: ưu tiên tin có “vị trí chính xác” hoặc tin nhóm đã khảo sát thực địa; với tin crawl, bấm “Xem tin gốc” để đối chiếu.",
          "Nghi bị lừa: giữ lại tin nhắn, biên lai chuyển khoản và báo công an phường nơi bạn ở.",
        ],
        basis: [LAW.scamWarning],
      },
      {
        id: "nhan-phong",
        title: "Ngày nhận phòng",
        items: [
          "Quay video, chụp ảnh từng góc phòng và đồ đạc hư hỏng sẵn có, gửi cho chủ trọ qua tin nhắn để có mốc thời gian — tránh bị bắt đền khi trả phòng.",
          "Chụp chỉ số đồng hồ điện, nước ngày nhận phòng để không trả tiền thay người ở trước.",
          "Nhận đủ chìa khóa phòng và cổng; hỏi vị trí cầu dao điện, bình chữa cháy, lối thoát hiểm.",
          "Nhờ chủ trọ hỗ trợ đăng ký tạm trú (xem mục Pháp lý).",
        ],
      },
      {
        id: "nguon-tim",
        title: "Tìm trọ ở đâu cho đáng tin",
        items: [
          "Hỏi bạn bè, anh chị khóa trên đang ở gần trường — họ biết khu nào an ninh, chủ nào dễ chịu.",
          "Ký túc xá CTU: phí theo học kỳ, có thông báo đăng ký mỗi đầu năm học — hỏi Trợ lý AI của Trọ CTU để xem thông tin KTX kèm nguồn.",
          "Nhóm Facebook tìm trọ: dùng để tham khảo, tuyệt đối không cọc online cho người chưa gặp.",
          "Trên Trọ CTU: lọc theo giá, khu vực, số phút tới trường; mục Gợi ý xếp hạng phòng theo tiêu chí của bạn.",
        ],
      },
    ],
  },
  {
    id: "o-ghep",
    title: "Lưu ý khi ở ghép",
    short: "Ở ghép",
    intro:
      "Phần lớn mâu thuẫn khi ở ghép đến từ tiền điện, giờ giấc, vệ sinh và khách đến chơi. Thống nhất từ đầu — và ghi lại — sẽ đỡ hơn nhiều so với giải quyết khi đã căng thẳng.",
    tips: [
      {
        id: "chon-ban",
        title: "Chọn bạn ở ghép",
        items: [
          "Gặp trực tiếp ở nơi công cộng trước khi quyết định; nói chuyện thẳng về giờ ngủ, nấu ăn, hút thuốc, khách đến chơi, thú cưng, mức sạch sẽ.",
          "Mục Ghép bạn ở trên Trọ CTU cho thấy mức hợp nhau theo thói quen sinh hoạt — dùng để lọc, nhưng vẫn nên gặp mặt.",
          "Báo người thân biết bạn sẽ ở với ai, ở đâu.",
          "Không gửi ảnh CCCD, mật khẩu hay chuyển tiền cho người mới quen trước khi cùng ký hợp đồng và nhận phòng.",
        ],
      },
      {
        id: "thoa-thuan",
        title: "Thống nhất trước khi dọn vào",
        lead: "Viết ra (ghi chú chung hoặc tin nhắn nhóm) để cả phòng cùng xác nhận.",
        items: [
          "Tiền phòng, wifi, rác chia đều theo người. Tiền điện: nếu người dùng máy lạnh nhiều, người dùng ít thì thỏa thuận tỷ lệ hoặc gắn đồng hồ phụ.",
          "Ai đứng ra đóng tiền cho chủ trọ, hạn chuyển khoản mỗi tháng; giữ biên nhận.",
          "Lịch trực quét dọn, đổ rác, rửa chén; đồ dùng nào chung, đồ nào riêng.",
          "Giờ yên tĩnh (ví dụ sau 23 giờ dùng tai nghe, tắt đèn chính).",
          "Khách đến chơi: báo trước; giới hạn số đêm ngủ lại mỗi tuần; khách ở dài ngày thì góp tiền điện nước.",
        ],
      },
      {
        id: "hop-dong-coc",
        title: "Hợp đồng và tiền cọc khi ở ghép",
        items: [
          "Tốt nhất mọi người cùng có tên trong hợp đồng (hoặc phụ lục) — người không có tên rất khó đòi quyền lợi khi có tranh chấp.",
          "Ghi rõ mỗi người góp bao nhiêu tiền cọc và tiền cọc được trả lại cho ai.",
          "Mỗi người đều đăng ký tạm trú tại phòng — cũng giúp chủ trọ kê khai đủ người để được tính giá điện theo định mức.",
          "Thống nhất trước khi có người chuyển đi: báo trước ít nhất 30 ngày; tự tìm người thay hoặc chịu phần tiền theo thỏa thuận.",
        ],
        basis: [LAW.housing163, LAW.power12],
      },
      {
        id: "mau-thuan",
        title: "Khi có mâu thuẫn hoặc không an toàn",
        items: [
          "Nói sớm, nói trực tiếp và dựa trên những gì cả phòng đã thống nhất; cần thì nhờ chủ trọ hoặc anh chị khóa trên làm trung gian.",
          "Bị đe dọa, quấy rối, mất đồ: báo chủ trọ và công an phường; trong chat của Trọ CTU dùng chức năng báo cáo, chặn.",
          "Không ở lại với người có hành vi bạo lực — ưu tiên an toàn của bạn trước tiền cọc.",
        ],
      },
    ],
  },
  {
    id: "phap-ly",
    title: "Thông tin pháp lý & hợp đồng",
    short: "Pháp lý & hợp đồng",
    intro:
      "Những điều nên biết, kèm điều luật gốc. Đây là thông tin tham khảo, không thay cho tư vấn pháp lý — cần chi tiết hơn, hãy hỏi Trợ lý AI (trả lời có trích dẫn điều khoản).",
    tips: [
      {
        id: "dat-coc",
        title: "Tiền cọc và giấy đặt cọc",
        items: [
          "Đặt cọc là để bảo đảm hai bên sẽ ký và thực hiện hợp đồng thuê.",
          "Nếu bạn đổi ý không thuê nữa thì mất cọc; nếu chủ trọ đổi ý không cho thuê thì phải trả lại cọc và thêm một khoản bằng tiền cọc — trừ khi giấy cọc có thỏa thuận khác, nên đọc kỹ phần này.",
          "Giấy cọc nên ghi: họ tên, số điện thoại hai bên; địa chỉ phòng; giá thuê; số tiền cọc; ngày dọn vào; khi nào được trả hoặc mất cọc; chữ ký hai bên.",
          "Nên chuyển khoản với nội dung rõ ràng (ví dụ “Coc phong 12 hem 58 duong 3/2”) để có bằng chứng.",
        ],
        basis: [LAW.civil328],
      },
      {
        id: "hop-dong",
        title: "Hợp đồng thuê cần có gì",
        items: [
          "Hợp đồng về nhà ở phải lập thành văn bản, gồm: thông tin các bên, mô tả phòng, giá thuê, thời hạn và cách thanh toán, thời gian giao nhận và thời hạn thuê, quyền và nghĩa vụ, cam kết, ngày ký và chữ ký.",
          "Nên ghi thêm: giá điện, nước, các phí dịch vụ; giá có cố định trong thời hạn thuê không; ai chịu sửa chữa khi hư hỏng; điều kiện trả cọc khi hết hạn; danh sách đồ đạc kèm tình trạng.",
          "Mỗi bên giữ một bản. Chụp lại hợp đồng lưu trong điện thoại.",
          "Thời hạn và giá thuê do hai bên thỏa thuận; bạn chỉ được cho người khác thuê lại khi chủ trọ đồng ý.",
        ],
        basis: [LAW.housing163, LAW.housing170_172],
      },
      {
        id: "cham-dut",
        title: "Chấm dứt hợp đồng trước hạn",
        items: [
          "Trong thời hạn thuê, chủ trọ không được tự ý lấy lại phòng, trừ một số trường hợp luật nêu (ví dụ bên thuê không trả tiền thuê từ 3 tháng trở lên mà không có lý do đã thỏa thuận, dùng phòng sai mục đích, tự ý đục phá, cơi nới).",
          "Bạn được đơn phương chấm dứt khi chủ trọ không sửa chữa lúc phòng hư hỏng nặng, tăng giá bất hợp lý hoặc tăng giá mà không báo trước theo hợp đồng.",
          "Bên chấm dứt phải báo trước ít nhất 30 ngày (trừ khi hợp đồng thỏa thuận khác); không báo mà gây thiệt hại thì phải bồi thường.",
        ],
        basis: [LAW.housing170_172],
      },
      {
        id: "dien-nuoc",
        title: "Tiền điện, nước",
        items: [
          "Nếu bạn không trực tiếp ký hợp đồng mua điện, tổng tiền điện chủ trọ thu của người thuê không được vượt quá số tiền trên hóa đơn điện hằng tháng.",
          "Chủ trọ kê khai đủ số người ở (theo thông tin cư trú) thì cứ 4 người được tính một định mức giá điện sinh hoạt — rẻ hơn. Vì vậy đăng ký tạm trú có lợi cho chính bạn.",
          "Thuê dưới 12 tháng mà chủ trọ không kê khai đủ số người thì toàn bộ điện bị tính theo giá bậc 2 (101–200 kWh). Thuê từ 12 tháng và có đăng ký tạm trú thì chủ trọ hoặc đại diện người thuê ký hợp đồng mua điện.",
          "Giá nước sạch sinh hoạt cho hộ dân khu vực đô thị Cần Thơ (bảng giá năm 2024) là 9.020đ/m³.",
        ],
        basis: [LAW.power12, LAW.water215],
      },
      {
        id: "tam-tru",
        title: "Đăng ký tạm trú",
        items: [
          "Ở trọ ngoài xã/phường nơi bạn thường trú từ 30 ngày trở lên để học tập thì phải đăng ký tạm trú; thời hạn tối đa 2 năm, gia hạn được nhiều lần.",
          "Hồ sơ: tờ khai thay đổi thông tin cư trú + giấy tờ chứng minh chỗ ở hợp pháp; với phòng thuê, văn bản cho thuê của chủ trọ là đủ và không cần công chứng hay chứng thực.",
          "Nộp tại cơ quan đăng ký cư trú nơi bạn ở trọ; cơ quan này có 3 ngày làm việc để cập nhật khi hồ sơ đầy đủ. Sắp hết hạn thì gia hạn trong 15 ngày trước khi hết hạn.",
        ],
        basis: [LAW.residence27_28, LAW.decree58],
      },
      {
        id: "thong-tin-ca-nhan",
        title: "Giữ an toàn thông tin cá nhân",
        items: [
          "Chỉ đưa CCCD khi làm hợp đồng hoặc đăng ký tạm trú với chủ trọ bạn đã gặp trực tiếp; có thể ghi lên bản photo “chỉ dùng để làm hợp đồng thuê trọ”.",
          "Không gửi ảnh CCCD, số tài khoản kèm mã OTP, mật khẩu qua tin nhắn cho người lạ; không bấm đường link lạ gửi đến.",
        ],
        basis: [LAW.scamWarning],
      },
      {
        id: "pccc",
        title: "An toàn cháy nổ ở phòng trọ",
        items: [
          "Không sạc xe điện, điện thoại qua đêm; không câu nối điện tùy tiện hay cắm quá nhiều thiết bị vào một ổ.",
          "Để bếp xa đồ dễ cháy; không chất đồ chắn lối thoát hiểm.",
          "Nhà ở phải có phương tiện chữa cháy phù hợp và giữ lối thoát nạn — hỏi chủ trọ vị trí bình chữa cháy. Khi có cháy gọi 114.",
        ],
        basis: [LAW.fire20, LAW.fireWarning],
      },
    ],
  },
];

// Bài tham khảo — ý được viết lại, không chép nguyên văn
export const REFERENCES: Basis[] = [
  ...Object.values(CTU),
  { label: "Nhà Minh Bạch — Cẩm nang thuê nhà (thỏa thuận ở ghép; 5 bước kiểm tra trước khi cọc)", href: "https://nhaminhbach.com/tips" },
  { label: "“Cẩm nang thuê phòng trọ cho sinh viên năm nhất” — H.Mai (tổng hợp)" },
  { label: "Văn bản pháp luật trong kho tri thức của Trợ lý Trọ CTU (44 văn bản, cập nhật 07/10/2026)" },
  { label: "Số liệu điện, nước, tiền cọc: tin trọ đang hiển thị trên Trọ CTU có ghi rõ giá (08/10/2026)" },
];

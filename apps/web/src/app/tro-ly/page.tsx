import Link from "next/link";
import SiteHeader from "../SiteHeader";

export const metadata = { title: "Trợ lý AI | Trọ CTU" };

// Trang dẫn vào widget (widget gắn ở layout, tự mở khi vào /tro-ly) — nội dung trò chuyện không nằm ở đây.
export default function ChatbotPage() {
  return (
    <>
      <SiteHeader />
      <main className="min-h-[calc(100vh-76px)] bg-gradient-to-br from-primary-soft via-white to-paper px-5 py-12 sm:px-10">
        <div className="mx-auto max-w-5xl">
          <Link href="/" className="text-sm font-semibold text-primary hover:underline">← Về trang tìm trọ</Link>
          <div className="mt-14 max-w-2xl">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-primary">Đại học Cần Thơ</p>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight text-ink sm:text-5xl">
              Hỏi Trợ lý Trọ CTU
            </h1>
            <p className="mt-6 text-lg leading-8 text-ink-soft">
              Mô tả ngân sách, khu vực và tiện ích bạn cần — trợ lý tìm trong các tin trọ đang hiển thị trên Trọ CTU.
              Bạn cũng có thể hỏi về ký túc xá CTU hoặc quy định thuê trọ: hợp đồng, tiền cọc, điện nước, đăng ký
              tạm trú, PCCC, dấu hiệu lừa đảo. Nguồn tham khảo nằm ngay dưới mỗi câu trả lời.
            </p>
            <div className="mt-8 flex flex-wrap gap-3 text-sm font-semibold text-ink-soft">
              <span className="rounded-full bg-white px-4 py-2 shadow-sm ring-1 ring-line">✓ Trả lời kèm nguồn</span>
              <span className="rounded-full bg-white px-4 py-2 shadow-sm ring-1 ring-line">✓ Lịch sử lưu theo tài khoản</span>
              <span className="rounded-full bg-white px-4 py-2 shadow-sm ring-1 ring-line">✓ Chạy được với AI local</span>
            </div>
            <p className="mt-8 text-sm text-ink-muted">
              Cửa sổ trò chuyện đã mở ở góc phải. Thông tin pháp lý chỉ để tham khảo — giá và phòng trống cần xác
              nhận với chủ trọ trước khi đặt cọc.
            </p>
          </div>
        </div>
      </main>
    </>
  );
}

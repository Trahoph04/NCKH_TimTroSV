import { requireAdminPage } from "@/lib/current-user";
import SiteHeader from "@/app/SiteHeader";
import QuanLyTabs from "../QuanLyTabs";
import ReviewsAdmin from "./ReviewsAdmin";

export const dynamic = "force-dynamic";

// Kiểm duyệt đánh giá nhà trọ: ẩn đánh giá vi phạm/sai sự thật (không xoá — giữ làm bằng chứng nếu có khiếu nại).
export default async function ManageReviewsPage() {
  await requireAdminPage("/quan-ly/danh-gia");
  return (
    <>
      <SiteHeader />
      <main className="min-h-[calc(100vh-76px)] bg-paper px-5 py-8 sm:px-10">
        <div className="mx-auto max-w-5xl">
          <QuanLyTabs active="/quan-ly/danh-gia" />
          <h1 className="text-2xl font-extrabold text-ink">Kiểm duyệt đánh giá</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Đánh giá hiện ngay khi sinh viên gửi. Ẩn những đánh giá xúc phạm, quảng cáo hoặc sai sự thật — đánh giá bị ẩn
            không tính vào điểm và người viết sửa lại cũng không tự hiện.
          </p>
          <ReviewsAdmin />
        </div>
      </main>
    </>
  );
}

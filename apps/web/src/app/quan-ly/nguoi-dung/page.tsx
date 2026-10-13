import { requireAdminPage } from "@/lib/current-user";
import SiteHeader from "@/app/SiteHeader";
import QuanLyTabs from "../QuanLyTabs";
import UsersAdmin from "./UsersAdmin";

export const dynamic = "force-dynamic";

// Quản lý người dùng (admin): tìm theo email/tên/MSSV, cấp/bỏ quyền admin, khoá/mở khoá (mig 101). Không xoá tài khoản:
// lịch sử chat và phiếu chấm mù là số liệu nghiên cứu.
export default async function ManageUsersPage() {
  const me = await requireAdminPage("/quan-ly/nguoi-dung");
  return (
    <>
      <SiteHeader />
      <main className="min-h-[calc(100vh-76px)] bg-paper px-5 py-8 sm:px-10">
        <div className="mx-auto max-w-5xl">
          <QuanLyTabs active="/quan-ly/nguoi-dung" />
          <h1 className="text-2xl font-extrabold text-ink">Quản lý người dùng</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Khoá tài khoản vi phạm (spam tin nhắn, lời mời quấy rối): mọi thao tác của người bị khoá bị từ chối ngay, kênh
            chat đang mở bị ngắt, không đăng nhập lại được và họ ra khỏi bộ thẻ ghép bạn. Tài khoản không bị xoá để giữ lịch
            sử; đánh giá cũ của họ vẫn hiện — ẩn riêng ở tab Đánh giá nếu cần.
          </p>
          <UsersAdmin currentUserId={me.id} />
        </div>
      </main>
    </>
  );
}

import Link from "next/link";
import { getManagedListings, type ApiError, type ListingOut } from "@/lib/api";
import { getServerAccessToken, requireAdminPage } from "@/lib/current-user";
import ListingCard from "@/app/ListingCard";
import SiteHeader from "@/app/SiteHeader";
import QuanLyTabs from "../QuanLyTabs";

export const dynamic = "force-dynamic";

// Thay trang "Tin của tôi": sinh viên không đăng tin (ADR-024), chỉ admin nhập tin tay cho nhóm.
// Tin crawl/khảo sát không có ở đây — chúng cập nhật bằng pipeline, admin chỉ ẩn được từ trang chi tiết.
export default async function ManageListingsPage() {
  await requireAdminPage("/quan-ly/nha-tro");

  const token = await getServerAccessToken();
  let items: ListingOut[] = [];
  let errorMessage: string | null = null;
  try {
    if (token) items = await getManagedListings(token);
    else errorMessage = "Phiên đăng nhập hết hạn — tải lại trang hoặc đăng nhập lại.";
  } catch (e) {
    errorMessage = (e as ApiError).detail ?? "Không thể tải danh sách";
  }

  return (
    <>
      <SiteHeader />
      <main className="min-h-[calc(100vh-76px)] bg-paper px-5 py-8 sm:px-10">
        <div className="mx-auto max-w-5xl">
          <QuanLyTabs active="/quan-ly/nha-tro" />
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="text-2xl font-extrabold text-ink">Quản lý nhà trọ</h1>
              <p className="mt-1 text-sm text-ink-muted">
                Tin do nhóm nhập tay. Tin crawl và tin khảo sát cập nhật qua pipeline — muốn gỡ thì bấm “Ẩn tin” ở
                trang chi tiết của tin đó.
              </p>
            </div>
            <Link
              href="/listings/new"
              className="rounded-[10px] bg-primary px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-navy"
            >
              + Thêm nhà trọ
            </Link>
          </div>

          {errorMessage && (
            <p className="mt-6 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{errorMessage}</p>
          )}

          {!errorMessage && items.length === 0 && (
            <p className="mt-10 text-center text-ink-muted">Chưa có tin nhập tay nào.</p>
          )}

          {items.length > 0 && (
            <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((listing) => (
                <div key={listing.id} className="relative">
                  <ListingCard listing={listing} />
                  <Link
                    href={`/listings/${listing.id}/edit`}
                    className="absolute right-2 top-2 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-primary shadow-sm hover:bg-white"
                  >
                    Sửa
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </>
  );
}

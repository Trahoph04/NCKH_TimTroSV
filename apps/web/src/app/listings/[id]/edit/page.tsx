import Link from "next/link";
import { notFound } from "next/navigation";
import { getListing, type ApiError } from "@/lib/api";
import { requireAdminPage } from "@/lib/current-user";
import ListingForm from "../../ListingForm";

export const dynamic = "force-dynamic";

export default async function EditListingPage({
  params,
}: {
  params: { id: string };
}) {
  await requireAdminPage(`/listings/${params.id}/edit`);

  let listing;
  try {
    listing = await getListing(params.id);
  } catch (e) {
    if ((e as ApiError).status === 404) notFound();
    throw e;
  }

  // API trả 409 cho tin crawl/khảo sát (pipeline sẽ ghi đè) — báo trước thay vì để form lỗi khi lưu
  if (listing.source !== "user") {
    return (
      <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
        <div className="mx-auto max-w-2xl rounded-lg border border-slate-200 bg-white p-6 text-slate-700 shadow-sm">
          <h1 className="text-xl font-bold text-slate-800">Không sửa tay được tin này</h1>
          <p className="mt-3 text-sm">
            Tin lấy từ crawl hoặc khảo sát thực địa được cập nhật qua pipeline nhập dữ liệu — sửa tay sẽ bị ghi đè ở lần
            nạp sau. Hãy sửa ở nguồn (file khảo sát) rồi nạp lại, hoặc ẩn tin ở trang chi tiết.
          </p>
          <Link href={`/listings/${listing.id}`} className="mt-4 inline-block text-sm font-medium text-primary">
            ← Về trang tin
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="mx-auto max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-800">Sửa tin</h1>
        <div className="mt-6">
          <ListingForm
            mode="edit"
            listingId={listing.id}
            initial={{
              title: listing.title,
              price: listing.price,
              area: listing.area,
              address: listing.address,
              district: listing.district,
              description: listing.description,
              images: listing.images,
            }}
          />
        </div>
      </div>
    </main>
  );
}

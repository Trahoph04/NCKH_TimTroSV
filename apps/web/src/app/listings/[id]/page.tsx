import Link from "next/link";
import { notFound } from "next/navigation";
import { getListing, getListingContact, type ApiError, type ContactOut } from "@/lib/api";
import { getCurrentUser } from "@/lib/current-user";
import { formatArea, formatDistance, formatPrice, isLocationPrecise, riskBadge } from "@/lib/format";
import ContactBox from "./ContactBox";
import MiniMap from "./MiniMap";
import ReviewSection from "./ReviewSection";
import DeleteListingButton from "./DeleteListingButton";

export const dynamic = "force-dynamic";

export default async function ListingDetailPage({
  params,
}: {
  params: { id: string };
}) {
  // link cũ /listings/mine ("Tin của tôi", đã bỏ — ADR-024) rơi vào route này; API trả 422 ⇒ trước đây thành 500
  if (!/^\d+$/.test(params.id)) notFound();
  let listing;
  try {
    listing = await getListing(params.id);
  } catch (e) {
    if ((e as ApiError).status === 404) notFound();
    throw e;
  }

  // liên hệ lỗi không được làm hỏng cả trang chi tiết
  const contact: ContactOut | null = await getListingContact(params.id).catch(() => null);
  const user = await getCurrentUser();
  // chỉ admin quản lý tin (ADR-024): ẩn được mọi tin; sửa chỉ tin nhập tay (tin crawl/khảo sát do pipeline ghi đè)
  const isAdmin = user?.role === "admin";
  const canEdit = isAdmin && listing.source === "user";
  const badge = riskBadge(listing.risk_level);

  return (
    <main className="min-h-screen bg-slate-50 p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <Link href="/" className="text-sm text-emerald-600 hover:text-emerald-700">
          ← Về danh sách
        </Link>

        <div className="mt-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          {listing.images.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {listing.images.map((src, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  src={src}
                  alt={`${listing.title} - ảnh ${i + 1}`}
                  className="h-40 w-full rounded object-cover"
                />
              ))}
            </div>
          ) : (
            <div className="flex h-40 w-full items-center justify-center rounded bg-slate-100 text-sm text-slate-400">
              Không có ảnh
            </div>
          )}

          <div className="mt-4 flex items-start justify-between gap-3">
            <h1 className="text-2xl font-bold text-slate-800">{listing.title}</h1>
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
            >
              {badge.label}
            </span>
          </div>

          <p className="mt-2 text-xl font-semibold text-emerald-700">
            {formatPrice(listing.price)}
          </p>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
            {listing.area != null && <span>{formatArea(listing.area)}</span>}
            {listing.district && <span>{listing.district}</span>}
            {listing.distance_to_ctu != null && (
              <span>{formatDistance(listing.distance_to_ctu)}</span>
            )}
          </div>

          {listing.address && (
            <p className="mt-2 text-sm text-slate-600">Địa chỉ: {listing.address}</p>
          )}

          {listing.freshness_label && (
            <p className="mt-1 text-xs text-slate-400">{listing.freshness_label}</p>
          )}

          {listing.description && (
            <p className="mt-4 whitespace-pre-line text-slate-700">
              {listing.description}
            </p>
          )}

          <ContactBox contact={contact} />

          {/* nhắc đúng lúc sắp liên hệ/đặt cọc — đầy đủ ở /cam-nang (thay cho badge "AI cảnh báo rủi ro") */}
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-semibold">Trước khi đặt cọc</p>
            <ul className="mt-1.5 list-disc space-y-1 pl-5">
              <li>Xem phòng tận nơi — không chuyển tiền “giữ chỗ” khi chưa thấy phòng.</li>
              <li>Hỏi rõ giá điện, nước, các phí khác và ghi vào giấy cọc, hợp đồng.</li>
              <li>Ngày nhận phòng: chụp hiện trạng phòng và chỉ số đồng hồ điện, nước.</li>
            </ul>
            <Link href="/cam-nang#tim-phong" className="mt-2 inline-block font-semibold text-amber-900 underline">
              Đọc cẩm nang →
            </Link>
          </div>

          <ReviewSection listingId={listing.id} loggedIn={user != null} />

          {listing.lat != null && listing.lng != null && (
            <MiniMap
              id={listing.id}
              lat={listing.lat}
              lng={listing.lng}
              precise={isLocationPrecise(listing)}
              routeTimes={listing.route_time_campus}
            />
          )}

          {listing.quality_score != null && (
            <p className="mt-2 text-xs text-slate-400">
              Điểm chất lượng: {(listing.quality_score * 100).toFixed(0)}%
            </p>
          )}

          {isAdmin && (
            <div className="mt-6 flex gap-3">
              {canEdit && (
                <Link
                  href={`/listings/${listing.id}/edit`}
                  className="rounded border border-slate-300 px-4 py-2 font-medium text-slate-700 hover:bg-slate-100"
                >
                  Sửa
                </Link>
              )}
              <DeleteListingButton id={listing.id} />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

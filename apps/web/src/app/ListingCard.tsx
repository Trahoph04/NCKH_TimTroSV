import Link from "next/link";
import type { ListingOut } from "@/lib/api";
import { formatArea, formatDistance, formatPriceShort, listingTags, riskBadge } from "@/lib/format";

// Card tin theo mockup 01 UI_NCKH.html: ảnh + badge, giá xanh to, meta, footer phút tới khu II.
export default function ListingCard({ listing }: { listing: ListingOut }) {
  const badge = riskBadge(listing.risk_level);
  const tags = listingTags(listing);
  const cover = listing.images[0];
  const minutes = listing.route_time_campus?.[1]; // khu II — khu chính gần nhất với đa số tin

  return (
    <Link
      href={`/listings/${listing.id}`}
      className="group flex flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-[0_1px_2px_rgba(16,36,58,.04)] transition hover:-translate-y-0.5 hover:shadow-lg"
    >
      <div className="relative h-44 w-full shrink-0">
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={cover} alt={listing.title} className="h-full w-full object-cover" />
        ) : (
          <div className="photo-placeholder flex h-full w-full items-center justify-center text-xs text-ink-faint">
            Chưa có ảnh
          </div>
        )}
        <span
          className={`absolute left-3 top-3 rounded-lg px-2.5 py-1 text-[12.5px] font-semibold ${badge.className}`}
        >
          {badge.label}
        </span>
        {tags.length > 0 && (
          <span className="absolute right-3 top-3 flex gap-1.5">
            {tags.map((t) => (
              <span key={t.label} className={`rounded-lg px-2.5 py-1 text-[12.5px] font-semibold ${t.className}`}>
                {t.label}
              </span>
            ))}
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <h3 className="line-clamp-2 text-[16px] font-semibold leading-snug text-ink">
          {listing.title}
        </h3>

        <p className="flex items-baseline gap-1.5">
          <span className="text-[20px] font-bold text-primary">
            {formatPriceShort(listing.price)}
          </span>
          {listing.price != null && <span className="text-[13px] text-ink-muted">/ tháng</span>}
        </p>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[14px] text-ink-soft">
          {listing.area != null && <span>{formatArea(listing.area)}</span>}
          {listing.district && <span>{listing.district}</span>}
          {listing.distance_to_ctu != null && (
            <span>{formatDistance(listing.distance_to_ctu)}</span>
          )}
        </div>

        <div className="mt-auto flex items-center justify-between gap-2 border-t border-line-soft pt-3">
          <span className="text-[13px] text-ink-muted">
            {minutes != null
              ? `${Math.round(minutes)} phút xe máy tới khu II`
              : listing.freshness_label || " "}
          </span>
          <span className="shrink-0 text-sm font-semibold text-primary-bright group-hover:underline">
            Xem chi tiết
          </span>
        </div>
      </div>
    </Link>
  );
}

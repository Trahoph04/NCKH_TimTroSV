import Link from "next/link";
import { apiFetch, getNearby, searchListings, type ListingOut, type SearchResult } from "@/lib/api";
import ListingCard from "./ListingCard";
import SiteHeader from "./SiteHeader";
import { HomeFilters, SortSelect, type HomeParams } from "./HomeControls";

export const dynamic = "force-dynamic";

// Tâm thống kê "quanh CTU" = khu II, khớp CAMPUSES[1] backend.
const CTU_LAT = 10.0322;
const CTU_LNG = 105.7683;

const PAGE_SIZE = 12;

// Chip gợi ý nhanh — map vào filter thật của backend.
const QUICK_CHIPS: { label: string; params: Record<string, string> }[] = [
  { label: "Dưới 1.5 triệu", params: { max_price: "1500000" } },
  { label: "Có gác", params: { q: "gác" } },
  { label: "Giờ tự do", params: { q: "giờ tự do" } },
  { label: "Gần CTU ≤ 1 km", params: { max_distance_ctu: "1000" } },
  { label: "Rộng ≥ 25 m²", params: { min_area: "25" } },
];

type SearchParamsShape = HomeParams & { page?: string };

function chipHref(params: Record<string, string>): string {
  return `/?${new URLSearchParams(params).toString()}`;
}

function medianPrice(items: ListingOut[]): number | null {
  const prices = items
    .map((l) => l.price)
    .filter((p): p is number => p != null && p > 0)
    .sort((a, b) => a - b);
  if (prices.length === 0) return null;
  return prices[Math.floor(prices.length / 2)];
}

const HOUSING_VALUES = ["phong_tro", "nha_mini"];
const SORT_VALUES = ["price_asc", "price_desc", "newest", "nearest", "freshness", "quality"];

// URL người dùng tự sửa / link cũ: tham số sai kiểu bị BỎ thay vì đẩy "NaN" hay giá trị ngoài enum xuống API — API trả
// 422 kèm detail là mảng, trước 12/10 làm trang chủ 500 ("Objects are not valid as a React child").
function cleanParams(raw: SearchParamsShape): SearchParamsShape {
  const first = (v: unknown) => (Array.isArray(v) ? v[0] : v) as string | undefined;
  const int = (v: unknown) => (/^\d+$/.test(first(v) ?? "") ? first(v) : undefined);
  const num = (v: unknown) => {
    const s = first(v);
    return s && Number.isFinite(Number(s)) && Number(s) >= 0 ? s : undefined;
  };
  const oneOf = (v: unknown, values: string[]) => (values.includes(first(v) ?? "") ? first(v) : undefined);
  return {
    q: first(raw.q),
    district: first(raw.district),
    min_price: int(raw.min_price),
    max_price: int(raw.max_price),
    min_area: num(raw.min_area),
    max_distance_ctu: num(raw.max_distance_ctu),
    housing: oneOf(raw.housing, HOUSING_VALUES),
    sort: oneOf(raw.sort, SORT_VALUES),
    page: int(raw.page),
  };
}

export default async function Home({
  searchParams: rawParams,
}: {
  searchParams: SearchParamsShape;
}) {
  const searchParams = cleanParams(rawParams);
  const page = Math.max(1, Number(searchParams.page) || 1);

  const [resultRes, totalRes, nearbyRes, crawlRes] = await Promise.allSettled([
    searchListings({
      q: searchParams.q,
      district: searchParams.district,
      min_price: searchParams.min_price ? Number(searchParams.min_price) : undefined,
      max_price: searchParams.max_price ? Number(searchParams.max_price) : undefined,
      min_area: searchParams.min_area ? Number(searchParams.min_area) : undefined,
      max_distance_ctu: searchParams.max_distance_ctu
        ? Number(searchParams.max_distance_ctu)
        : undefined,
      housing: searchParams.housing,
      sort: searchParams.sort,
      page,
      size: PAGE_SIZE,
    }),
    searchListings({ page: 1, size: 1 }),
    getNearby(CTU_LAT, CTU_LNG, 3000),
    apiFetch<{ runs: { finished_at: string | null }[] }>("/crawler/status?limit=20"),
  ]);
  // Ngày dữ liệu thật thay câu cố định "tự cập nhật mỗi 5 giờ": lịch crawl có thể đang tắt/dừng (lần cuối 10/10 khi
  // đo 13/10) — hội đồng đối chiếu với tin trên trang nguồn là thấy ngay câu cố định sai
  const lastCrawl =
    crawlRes.status === "fulfilled"
      ? crawlRes.value.runs
          .map((r) => r.finished_at)
          .filter((t): t is string => Boolean(t))
          .sort()
          .at(-1) ?? null
      : null;
  const lastCrawlLabel = lastCrawl
    ? new Date(lastCrawl).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Asia/Ho_Chi_Minh" })
    : null;

  let result: SearchResult;
  let errorMessage: string | null = null;
  if (resultRes.status === "fulfilled") {
    result = resultRes.value;
  } else {
    errorMessage =
      (resultRes.reason as { detail?: string })?.detail ?? "Không thể tải danh sách tin";
    result = { total: 0, page, size: PAGE_SIZE, items: [] };
  }

  const totalAll = totalRes.status === "fulfilled" ? totalRes.value.total : null;
  const nearbyItems = nearbyRes.status === "fulfilled" ? nearbyRes.value : null;
  const median = nearbyItems ? medianPrice(nearbyItems) : null;

  const stats: { label: string; value: string }[] = [
    { label: "Tin đang hiển thị", value: totalAll != null ? String(totalAll) : "—" },
    { label: "Nguồn tổng hợp", value: "6" },
    {
      label: "Trong 3 km quanh CTU",
      value: nearbyItems ? String(nearbyItems.length) : "—",
    },
    {
      label: "Giá phổ biến",
      value: median != null ? `${(median / 1_000_000).toFixed(1)}tr` : "—",
    },
  ];

  const totalPages = Math.max(1, Math.ceil(result.total / PAGE_SIZE));
  const hasFilter = Boolean(
    searchParams.q ||
      searchParams.district ||
      searchParams.min_price ||
      searchParams.max_price ||
      searchParams.min_area ||
      searchParams.max_distance_ctu ||
      searchParams.housing,
  );

  return (
    <div className="min-h-screen bg-paper">
      {/* Topbar giới thiệu đề tài (mockup 01) */}
      <div className="bg-navy px-5 py-2 text-[12.5px] text-[#b9d3ec] sm:px-10">
        Sản phẩm nghiên cứu khoa học sinh viên · Trường Công nghệ Thông tin &amp; Truyền thông,
        ĐH Cần Thơ
      </div>

      <SiteHeader />

      {/* HERO */}
      <section className="relative overflow-hidden bg-primary text-white">
        <div className="pointer-events-none absolute -top-[120px] right-[-80px] h-[460px] w-[460px] rounded-full bg-white/5" />
        <div className="pointer-events-none absolute -bottom-[180px] right-[120px] h-[300px] w-[300px] rounded-full bg-white/[.04]" />

        <div className="relative mx-auto grid max-w-[1160px] gap-10 px-5 py-12 sm:px-10 sm:py-14 lg:grid-cols-[1fr_330px] lg:gap-14">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[13px] font-medium">
              <span className="block h-[7px] w-[7px] rounded-full bg-[#7fe0b0]" />
              {totalAll != null ? `${totalAll} tin` : "Tin"} đã lọc sạch từ 6 nguồn và khảo sát thực địa
              {lastCrawlLabel ? ` · cập nhật ${lastCrawlLabel}` : ""}
            </div>

            <h1 className="mt-4 max-w-[17ch] text-balance text-[34px] font-extrabold leading-[1.1] tracking-[-0.03em] sm:text-[46px]">
              Ở gần trường, đúng giá sinh viên.
            </h1>
            <p className="mt-4 max-w-[52ch] text-[15px] leading-relaxed text-[#cfe1f4] sm:text-[17px]">
              Hệ thống tổng hợp tin trọ từ 6 trang, tự loại tin ảo, tin trùng và tính số phút xe
              máy tới từng khu của ĐH Cần Thơ.
            </p>

            {/* Ô tìm kiếm — GET / giữ nguyên các filter đang bật */}
            <form
              action="/"
              method="get"
              className="mt-7 flex items-center gap-2 rounded-2xl bg-white p-2.5 shadow-[0_18px_40px_-20px_rgba(0,0,0,.5)]"
            >
              <div className="flex flex-1 items-center gap-2.5 pl-3">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="shrink-0">
                  <circle cx="9" cy="9" r="6.2" stroke="#5b7189" strokeWidth="1.8" />
                  <line
                    x1="13.6"
                    y1="13.6"
                    x2="17.5"
                    y2="17.5"
                    stroke="#5b7189"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
                <input
                  type="text"
                  name="q"
                  defaultValue={searchParams.q ?? ""}
                  placeholder="trọ dưới 2 triệu, có gác, gần khu II..."
                  className="w-full bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-faint"
                />
              </div>
              <span className="hidden border-l border-line pl-3.5 pr-2 text-sm text-ink-muted sm:block">
                Cần Thơ
              </span>
              {searchParams.district && (
                <input type="hidden" name="district" value={searchParams.district} />
              )}
              {searchParams.min_price && (
                <input type="hidden" name="min_price" value={searchParams.min_price} />
              )}
              {searchParams.max_price && (
                <input type="hidden" name="max_price" value={searchParams.max_price} />
              )}
              {searchParams.min_area && (
                <input type="hidden" name="min_area" value={searchParams.min_area} />
              )}
              {searchParams.max_distance_ctu && (
                <input type="hidden" name="max_distance_ctu" value={searchParams.max_distance_ctu} />
              )}
              {searchParams.housing && (
                <input type="hidden" name="housing" value={searchParams.housing} />
              )}
              {searchParams.sort && <input type="hidden" name="sort" value={searchParams.sort} />}
              <button
                type="submit"
                className="rounded-[11px] bg-primary-bright px-6 py-3 text-[16px] font-semibold text-white transition hover:bg-primary"
              >
                Tìm trọ
              </button>
            </form>

            <div className="mt-3.5 flex flex-wrap items-center gap-2">
              <span className="mr-1 text-[13px] text-[#a9c7e4]">Sinh viên hay tìm:</span>
              {QUICK_CHIPS.map((chip) => (
                <Link
                  key={chip.label}
                  href={chipHref(chip.params)}
                  className="rounded-full border border-white/[.22] bg-white/10 px-3.5 py-1.5 text-[13.5px] text-[#eaf3fb] transition hover:bg-white/20"
                >
                  {chip.label}
                </Link>
              ))}
            </div>

            <Link
              href="/goi-y"
              className="mt-5 inline-flex items-center gap-2 rounded-[11px] bg-white px-4 py-2.5 text-[14.5px] font-semibold text-primary transition hover:bg-[#eaf3fb]"
            >
              Chưa biết chọn gì? Nhận gợi ý theo nhu cầu của bạn →
            </Link>
          </div>

          {/* Panel dữ liệu hệ thống */}
          <div className="rounded-[18px] border border-white/[.18] bg-white/[.08] p-6">
            <div className="text-[13px] font-semibold uppercase tracking-[.06em] text-[#a9c7e4]">
              Dữ liệu hệ thống
            </div>
            <div className="mt-4 flex flex-col gap-4">
              {stats.map((s) => (
                <div
                  key={s.label}
                  className="flex items-baseline justify-between gap-3 border-b border-white/10 pb-3.5"
                >
                  <span className="text-[14.5px] text-[#cfe1f4]">{s.label}</span>
                  <span className="text-[22px] font-bold">{s.value}</span>
                </div>
              ))}
            </div>
            <p className="mt-3.5 text-[12.5px] leading-normal text-[#a9c7e4]">
              Tin rác, tin bán nhà và tin trùng đã bị loại bởi bộ làm sạch 5 tầng.
            </p>
          </div>
        </div>
      </section>

      {/* KẾT QUẢ */}
      <section className="mx-auto grid max-w-[1160px] items-start gap-7 px-5 py-9 sm:px-10 lg:grid-cols-[292px_minmax(0,1fr)]">
        {/* key theo query: chip nhanh / Xoá hết / phân trang đổi URL mà client component giữ state cũ */}
        <HomeFilters key={JSON.stringify(searchParams)} current={searchParams} />

        <div className="flex flex-col gap-[18px]">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-[22px] font-bold tracking-[-0.01em] text-ink">
                {result.total} {searchParams.housing === "nha_mini" ? "nhà mini" : "phòng trọ"}{" "}
                {hasFilter ? "phù hợp bộ lọc" : "tại Cần Thơ"}
              </h2>
              <p className="mt-1 text-sm text-ink-muted">
                Đã ẩn tin hết hạn, tin trùng và nhà nguyên căn / mặt bằng
              </p>
            </div>
            <SortSelect current={searchParams} />
          </div>

          {errorMessage && (
            <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{errorMessage}</p>
          )}

          {!errorMessage && result.items.length === 0 && (
            <p className="py-14 text-center text-ink-muted">Không tìm thấy tin phù hợp</p>
          )}

          {result.items.length > 0 && (
            <div className="mt-1 grid grid-cols-1 gap-[18px] sm:grid-cols-2">
              {result.items.map((listing) => (
                <ListingCard key={listing.id} listing={listing} />
              ))}
            </div>
          )}

          {result.total > PAGE_SIZE && (
            <Pagination searchParams={searchParams} page={page} totalPages={totalPages} />
          )}
        </div>
      </section>

      <footer className="bg-navy px-5 py-8 text-[13.5px] text-[#a9c7e4] sm:px-10">
        <div className="mx-auto flex max-w-[1160px] flex-wrap items-center justify-between gap-3">
          <span>Trọ CTU · Đề tài NCKH sinh viên 2026 · Trường CNTT&amp;TT, ĐH Cần Thơ</span>
          <span className="flex gap-6">
            <Link href="/map" className="transition hover:text-white">
              Bản đồ
            </Link>
            <Link href="/cam-nang" className="transition hover:text-white">
              Cẩm nang
            </Link>
          </span>
        </div>
      </footer>
    </div>
  );
}

function pageWindow(current: number, total: number): number[] {
  const start = Math.max(1, Math.min(current - 2, total - 4));
  const end = Math.min(total, start + 4);
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

function pageHref(searchParams: SearchParamsShape, page: number): string {
  const params = new URLSearchParams();
  Object.entries(searchParams).forEach(([key, value]) => {
    if (value && key !== "page") params.set(key, value);
  });
  if (page > 1) params.set("page", String(page));
  const qs = params.toString();
  return qs ? `/?${qs}` : "/";
}

function Pagination({
  searchParams,
  page,
  totalPages,
}: {
  searchParams: SearchParamsShape;
  page: number;
  totalPages: number;
}) {
  const numberBase =
    "w-10 rounded-[10px] py-2.5 text-center text-[14.5px] transition";
  const edgeBase = "rounded-[10px] px-4 py-2.5 text-[14.5px] transition";

  return (
    <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
      {page > 1 ? (
        <Link
          href={pageHref(searchParams, page - 1)}
          className={`${edgeBase} border border-line text-ink-soft hover:bg-white`}
        >
          Trước
        </Link>
      ) : (
        <span className={`${edgeBase} cursor-not-allowed border border-line-soft text-ink-faint`}>
          Trước
        </span>
      )}

      {pageWindow(page, totalPages).map((n) =>
        n === page ? (
          <span key={n} className={`${numberBase} bg-primary font-semibold text-white`}>
            {n}
          </span>
        ) : (
          <Link
            key={n}
            href={pageHref(searchParams, n)}
            className={`${numberBase} border border-line text-ink-soft hover:bg-white`}
          >
            {n}
          </Link>
        ),
      )}

      {page < totalPages ? (
        <Link
          href={pageHref(searchParams, page + 1)}
          className={`${edgeBase} border border-line text-ink-soft hover:bg-white`}
        >
          Sau
        </Link>
      ) : (
        <span className={`${edgeBase} cursor-not-allowed border border-line-soft text-ink-faint`}>
          Sau
        </span>
      )}
    </div>
  );
}

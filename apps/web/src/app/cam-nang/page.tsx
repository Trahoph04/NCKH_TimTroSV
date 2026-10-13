import Link from "next/link";
import { unstable_cache } from "next/cache";
import type { ListingOut } from "@/lib/api";
import { CAMPUSES } from "@/lib/campus";
import { API_URL } from "@/lib/config";
import { formatPriceShort } from "@/lib/format";
import SiteHeader from "../SiteHeader";
import { KTX_FEE, REFERENCES, SECTIONS, UPDATED_AT, type Basis } from "./content";

export const metadata = {
  title: "Cẩm nang | Trọ CTU",
  description:
    "Ký túc xá ĐH Cần Thơ, lưu ý khi tìm phòng, khi ở ghép và thông tin pháp lý, hợp đồng thuê trọ cho sinh viên ĐH Cần Thơ",
};

// Trang dựng mỗi request; riêng 2 con số phòng trọ quanh khu II cache 1 giờ qua unstable_cache. Trước đây cả trang ISR
// revalidate 3600: web khởi động trước API ⇒ lần dựng đầu lỗi fetch và trang "Chưa tải được số liệu" bị cache cả giờ.
export const dynamic = "force-dynamic";
const RENT_TTL = 3600;

const NEAR_RADIUS = 2000;
const KTX_QUESTION = "Phí ở ký túc xá CTU bao nhiêu và đăng ký thế nào?";

// Giá giữa (trung vị) phòng trọ đang hiển thị trong 2 km quanh khu II — cùng cách tính ô "Giá phổ biến" trang chủ.
// API lỗi ⇒ null: khối so sánh chỉ hiện phí KTX, không đoán số.
// Chỉ cache KẾT QUẢ (2 số), và chỉ khi tính được: lỗi ⇒ throw ⇒ unstable_cache không lưu ⇒ request sau thử lại.
const cachedRentStats = unstable_cache(
  async (): Promise<{ median: number; count: number }> => {
    const [lat, lng] = CAMPUSES[1];
    const res = await fetch(`${API_URL}/listings/nearby?lat=${lat}&lng=${lng}&radius=${NEAR_RADIUS}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`nearby ${res.status}`);
    const prices = ((await res.json()) as ListingOut[])
      .map((l) => l.price)
      .filter((p): p is number => p != null && p > 0)
      .sort((a, b) => a - b);
    if (prices.length === 0) throw new Error("no prices");
    return { median: prices[Math.floor(prices.length / 2)], count: prices.length };
  },
  ["cam-nang-rent-near-khu-ii"],
  { revalidate: RENT_TTL },
);

async function rentNearKhuII(): Promise<{ median: number; count: number } | null> {
  try {
    return await cachedRentStats();
  } catch {
    return null;
  }
}

function KtxVsRent({ rent }: { rent: { median: number; count: number } | null }) {
  return (
    <div className="mt-6 rounded-2xl border border-primary-ring bg-white p-5 shadow-sm">
      <h3 className="text-lg font-bold text-ink">KTX hay thuê trọ?</h3>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-primary-soft p-4">
          <p className="text-[13px] font-semibold uppercase tracking-wide text-primary">KTX khu A, B (trong khu II)</p>
          <p className="mt-1 text-2xl font-extrabold text-ink">
            {formatPriceShort(KTX_FEE.min)} – {formatPriceShort(KTX_FEE.max)}
          </p>
          <p className="text-[13px] text-ink-muted">mỗi sinh viên/tháng, nộp theo học kỳ, chưa gồm điện nước</p>
          <ul className="mt-3 space-y-1 text-[14px] leading-6 text-ink-soft">
            <li>+ Rẻ nhất, an ninh, đi bộ tới lớp</li>
            <li>− Ở 3–8 người, giờ giấc theo nội quy, đăng ký lại mỗi kỳ, số chỗ có hạn</li>
          </ul>
        </div>
        <div className="rounded-xl bg-tint p-4">
          <p className="text-[13px] font-semibold uppercase tracking-wide text-ink-soft">
            Phòng trọ trong {NEAR_RADIUS / 1000} km quanh khu II
          </p>
          {rent ? (
            <>
              <p className="mt-1 text-2xl font-extrabold text-ink">{formatPriceShort(rent.median)}</p>
              <p className="text-[13px] text-ink-muted">
                giá giữa mỗi phòng/tháng của {rent.count} tin đang hiển thị trên Trọ CTU · ở ghép 2 người ≈{" "}
                {formatPriceShort(Math.round(rent.median / 2 / 10_000) * 10_000)}/người · chưa gồm điện nước
              </p>
            </>
          ) : (
            <p className="mt-1 text-[14px] text-ink-muted">Chưa tải được số liệu phòng trọ lúc này.</p>
          )}
          <ul className="mt-3 space-y-1 text-[14px] leading-6 text-ink-soft">
            <li>+ Tự do giờ giấc, chọn được bạn ở cùng, phòng riêng hoặc ở ghép</li>
            <li>− Tốn hơn, phải tự kiểm tra cọc, hợp đồng, giá điện nước</li>
          </ul>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-sm font-semibold">
        <Link href="/map?campus=1&radius=2000" className="rounded-[10px] bg-primary px-4 py-2 text-white transition hover:bg-navy">
          Xem phòng trọ quanh khu II
        </Link>
        <Link href="/roommate" className="rounded-[10px] border border-line px-4 py-2 text-ink-soft transition hover:border-primary-ring hover:text-primary">
          Tìm bạn ở ghép
        </Link>
        <Link
          href={`/tro-ly?hoi=${encodeURIComponent(KTX_QUESTION)}`}
          className="rounded-[10px] border border-line px-4 py-2 text-ink-soft transition hover:border-primary-ring hover:text-primary"
        >
          Hỏi Trợ lý về KTX
        </Link>
      </div>
      <p className="mt-3 text-[12px] text-ink-faint">
        Phí KTX theo trang Trung tâm Phục vụ Sinh viên ĐHCT (đọc 07/10/2026); giá phòng trọ là giá đăng của các tin còn hiển
        thị, tính lại mỗi giờ.
      </p>
    </div>
  );
}

function BasisLinks({ basis }: { basis: Basis[] }) {
  return (
    <div className="mt-4 border-t border-line-soft pt-3 text-[12.5px] leading-5 text-ink-muted">
      <span className="font-semibold text-ink-soft">Căn cứ: </span>
      {basis.map((b, i) => (
        <span key={b.label}>
          {i > 0 && " · "}
          {b.href ? (
            <a href={b.href} target="_blank" rel="noopener noreferrer" className="underline decoration-line hover:text-primary">
              {b.label}
            </a>
          ) : (
            b.label
          )}
        </span>
      ))}
    </div>
  );
}

// Cẩm nang thay cho "AI cảnh báo rủi ro" (dữ liệu tin không có nhãn lừa đảo để học) — nội dung ở content.ts
export default async function HandbookPage() {
  const rent = await rentNearKhuII();
  return (
    <>
      <SiteHeader />
      <main className="bg-paper pb-16">
        <section className="bg-gradient-to-br from-primary-soft via-white to-paper px-5 pb-10 pt-12 sm:px-10">
          <div className="mx-auto max-w-5xl">
            <p className="text-sm font-bold uppercase tracking-[0.2em] text-primary">Cẩm nang</p>
            <h1 className="mt-3 text-3xl font-extrabold leading-tight text-ink sm:text-5xl">Thuê trọ an toàn cho sinh viên</h1>
            <p className="mt-5 max-w-2xl text-[17px] leading-8 text-ink-soft">
              Ký túc xá của trường, những điều nên kiểm tra khi tìm phòng, khi ở ghép và khi ký giấy tờ — gom từ trang chính
              thức của ĐH Cần Thơ, kinh nghiệm của sinh viên đi trước, cảnh báo của cơ quan công an và văn bản pháp luật.
            </p>
            <p className="mt-3 text-sm text-ink-muted">Bản tạm, cập nhật {UPDATED_AT} · nội dung sẽ được bổ sung thêm.</p>
          </div>
        </section>

        <nav aria-label="Mục lục cẩm nang" className="sticky top-0 z-20 border-y border-line bg-white/95 px-5 backdrop-blur sm:px-10">
          <div className="mx-auto flex max-w-5xl gap-1 overflow-x-auto py-2 text-[15px] font-semibold">
            {SECTIONS.map((section, index) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                className="shrink-0 rounded-full px-4 py-2 text-ink-soft transition hover:bg-tint hover:text-primary"
              >
                {index + 1}. {section.short}
              </a>
            ))}
          </div>
        </nav>

        <div className="mx-auto max-w-5xl px-5 sm:px-0">
          {SECTIONS.map((section, index) => (
            <section key={section.id} id={section.id} className="scroll-mt-20 pt-12">
              <h2 className="text-2xl font-extrabold text-ink sm:text-3xl">
                <span className="mr-2 text-primary">{index + 1}.</span>
                {section.title}
              </h2>
              <p className="mt-3 max-w-3xl leading-7 text-ink-soft">{section.intro}</p>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {section.tips.map((tip) => (
                  <article
                    key={tip.id}
                    id={`${section.id}-${tip.id}`}
                    className="scroll-mt-20 rounded-2xl border border-line bg-white p-5 shadow-sm"
                  >
                    <h3 className="text-lg font-bold text-ink">{tip.title}</h3>
                    {tip.lead && <p className="mt-2 text-[14.5px] leading-6 text-ink-muted">{tip.lead}</p>}
                    <ul className="mt-3 space-y-2.5">
                      {tip.items.map((item) => (
                        <li key={item} className="flex gap-2.5 text-[14.5px] leading-6 text-ink-soft">
                          <span aria-hidden="true" className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">
                            ✓
                          </span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                    {tip.basis && <BasisLinks basis={tip.basis} />}
                  </article>
                ))}
              </div>

              {section.id === "ktx" && <KtxVsRent rent={rent} />}

              {section.id === "phap-ly" && (
                <div className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-primary px-5 py-4 text-white">
                  <p className="text-[15px]">Tình huống cụ thể của bạn? Trợ lý AI trả lời kèm trích dẫn điều luật.</p>
                  <Link href="/tro-ly" className="rounded-[10px] bg-white px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary-soft">
                    Hỏi Trợ lý AI
                  </Link>
                </div>
              )}
            </section>
          ))}

          <section className="mt-14 border-t border-line pt-6 text-[13px] leading-6 text-ink-muted">
            <h2 className="font-semibold text-ink-soft">Nguồn tham khảo</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {REFERENCES.map((r) => (
                <li key={r.label}>
                  {r.href ? (
                    <a href={r.href} target="_blank" rel="noopener noreferrer" className="underline decoration-line hover:text-primary">
                      {r.label}
                    </a>
                  ) : (
                    r.label
                  )}
                </li>
              ))}
            </ul>
            <p className="mt-3">
              Nội dung mang tính tham khảo, không thay thế tư vấn pháp lý. Luôn đối chiếu với hợp đồng thực tế và văn bản
              gốc.
            </p>
          </section>
        </div>
      </main>
    </>
  );
}

import type { ReactNode } from "react";
import { MapBadge } from "@/lib/map-icons";
import SiteHeader from "./SiteHeader";

// Khung chung cho /login, /register — cùng header, màu và kiểu khối với phần còn lại của web (trước 12/10 hai trang này
// còn bảng màu slate/emerald của bản đầu). Màn rộng: khối giới thiệu xanh bên trái giống hero trang chủ.
export const authInput =
  "w-full rounded-[10px] border border-line bg-white px-3.5 py-2.5 text-[15px] text-ink outline-none transition placeholder:text-ink-faint focus:border-primary focus:ring-2 focus:ring-primary-ring";
export const authLabel = "mb-1.5 block text-[13.5px] font-semibold text-ink-soft";
export const authFieldError = "mt-1 text-[13px] text-rose-600";
export const authFormError = "rounded-[10px] bg-rose-50 px-3 py-2 text-sm text-rose-600";
export const authButton =
  "w-full rounded-[11px] bg-primary px-4 py-3 text-[15px] font-semibold text-white transition hover:bg-navy disabled:cursor-not-allowed disabled:opacity-60";

const FEATURES: { glyph: "house" | "campus" | "market"; text: string }[] = [
  { glyph: "house", text: "Tin trọ đã lọc sạch từ 6 nguồn và nhóm khảo sát thực địa" },
  { glyph: "campus", text: "Bản đồ, số phút xe máy tới 3 khu Đại học Cần Thơ" },
  { glyph: "market", text: "Tiện ích quanh phòng, gợi ý theo tiêu chí, ghép bạn ở" },
];

export default function AuthShell({
  title,
  subtitle,
  footer,
  children,
}: {
  title: string;
  subtitle: string;
  footer: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <SiteHeader />
      <main className="min-h-[calc(100vh-76px)] bg-paper px-4 py-8 sm:px-10 sm:py-12">
        <div className="mx-auto grid max-w-md overflow-hidden rounded-2xl border border-line bg-white shadow-sm lg:max-w-[980px] lg:grid-cols-[1fr_460px]">
          <section className="relative hidden overflow-hidden bg-primary p-10 text-white lg:flex lg:flex-col lg:justify-between">
            <div className="pointer-events-none absolute -right-24 -top-28 h-[360px] w-[360px] rounded-full bg-white/5" />
            <div className="pointer-events-none absolute -bottom-32 left-10 h-[260px] w-[260px] rounded-full bg-white/[.04]" />
            <div className="relative">
              <p className="text-[13px] font-medium uppercase tracking-[0.12em] text-[#b9d3ec]">Trọ CTU</p>
              <h2 className="mt-3 max-w-[16ch] text-[32px] font-extrabold leading-[1.15] tracking-[-0.02em]">
                Ở gần trường, đúng giá sinh viên.
              </h2>
            </div>
            <ul className="relative mt-10 flex flex-col gap-4">
              {FEATURES.map((f) => (
                <li key={f.text} className="flex items-start gap-3 text-[14.5px] leading-snug text-white/90">
                  <MapBadge badge="poi" glyph={f.glyph} size={26} className="mt-[-2px] shrink-0" />
                  {f.text}
                </li>
              ))}
            </ul>
          </section>

          <section className="p-6 sm:p-10">
            <h1 className="text-[26px] font-extrabold tracking-[-0.02em] text-ink">{title}</h1>
            <p className="mt-1 text-[14.5px] text-ink-muted">{subtitle}</p>
            <div className="mt-6">{children}</div>
            <div className="mt-6 border-t border-line-soft pt-5 text-center text-sm text-ink-muted">{footer}</div>
          </section>
        </div>
      </main>
    </>
  );
}

import Link from "next/link";

// Chuyển giữa các trang quản trị (thuyết minh dòng 4: quản lý người dùng, nhà trọ; dòng 6: đánh giá).
const TABS = [
  { href: "/quan-ly/nha-tro", label: "Nhà trọ" },
  { href: "/quan-ly/nguoi-dung", label: "Người dùng" },
  { href: "/quan-ly/danh-gia", label: "Đánh giá" },
];

export default function QuanLyTabs({ active }: { active: string }) {
  return (
    <nav className="mb-6 flex gap-1.5 rounded-[11px] bg-tint p-1 sm:w-fit" aria-label="Trang quản lý">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          aria-current={active === t.href ? "page" : undefined}
          className={`flex-1 rounded-lg px-4 py-2 text-center text-sm transition sm:flex-none ${
            active === t.href ? "bg-primary font-semibold text-white" : "text-ink-soft hover:bg-white/70"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}

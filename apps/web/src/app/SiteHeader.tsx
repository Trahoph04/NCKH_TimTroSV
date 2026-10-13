"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ChatNavLink from "./ChatNavLink";

const NAV = [
  { href: "/", label: "Tìm trọ" },
  { href: "/map", label: "Bản đồ" },
  { href: "/goi-y", label: "Gợi ý" },
  { href: "/cam-nang", label: "Cẩm nang" },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function SiteHeader() {
  const pathname = usePathname();
  // cookie là httpOnly nên phải hỏi server; null = chưa biết, false = chưa đăng nhập
  const [me, setMe] = useState<{ name: string | null; email: string; role: string } | false | null>(null);
  // Menu gập cho màn < md: thanh điều hướng ẩn dưới md, trước 12/10 trên điện thoại không có đường tới bản đồ/chat
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : false))
      .then(setMe)
      .catch(() => setMe(false));
  }, []);

  return (
    <header className="relative flex h-[76px] shrink-0 items-center justify-between border-b border-line bg-white px-5 sm:px-10">
      {/* logo tách từ ảnh gốc của nhóm: hình ngôi nhà + chữ (public/brand) — chữ là ảnh để giữ đúng font/màu logo */}
      <Link href="/" className="flex shrink-0 items-center gap-2.5">
        <img src="/brand/logo-mark.png" alt="" width={253} height={256} className="h-9 w-auto sm:h-11" />
        <span className="flex flex-col gap-1 leading-tight">
          <img src="/brand/logo-wordmark.png" alt="NhàTrọ CTU" width={529} height={96} className="h-[18px] w-auto sm:h-[22px]" />
          <span className="text-xs text-ink-muted">Tìm phòng trọ gần trường</span>
        </span>
      </Link>

      <nav className="hidden items-center gap-7 text-[15px] font-medium md:flex">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={
              isActive(pathname, item.href)
                ? "border-b-2 border-primary pb-0.5 font-semibold text-primary"
                : "text-ink-soft transition hover:text-primary"
            }
          >
            {item.label}
          </Link>
        ))}
        <ChatNavLink
          active={pathname.startsWith("/chat")}
          className={
            pathname.startsWith("/chat")
              ? "border-b-2 border-primary pb-0.5 font-semibold text-primary"
              : "text-ink-soft transition hover:text-primary"
          }
        />
        <Link
          href="/roommate"
          className={
            pathname.startsWith("/roommate")
              ? "border-b-2 border-primary pb-0.5 font-semibold text-primary"
              : "text-ink-soft transition hover:text-primary"
          }
        >
          Ghép bạn ở
        </Link>
      </nav>

      <div className="flex items-center gap-3">
        {me ? (
          <Link
            href="/me"
            title={me.email}
            className="hidden max-w-[180px] truncate text-[15px] font-medium text-ink-soft transition hover:text-primary sm:block"
          >
            {me.name || me.email}
          </Link>
        ) : me === false ? (
          <Link
            href="/login"
            className="hidden text-[15px] font-medium text-ink-soft transition hover:text-primary sm:block"
          >
            Đăng nhập
          </Link>
        ) : null}
        {me && me.role === "admin" && (
          <Link
            href="/quan-ly/nha-tro"
            className="hidden text-[15px] font-medium text-ink-soft transition hover:text-primary lg:block"
          >
            Quản lý
          </Link>
        )}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Đóng menu" : "Mở menu"}
          aria-expanded={open}
          aria-controls="mobile-nav"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-ink-soft hover:bg-tint md:hidden"
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden>
            {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
        </button>
      </div>

      {open && (
        <nav
          id="mobile-nav"
          className="absolute inset-x-0 top-full z-[1100] flex flex-col border-b border-line bg-white px-5 py-2 text-[15px] font-medium shadow-lg md:hidden"
        >
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`py-2.5 ${isActive(pathname, item.href) ? "font-semibold text-primary" : "text-ink-soft"}`}
            >
              {item.label}
            </Link>
          ))}
          <ChatNavLink
            active={pathname.startsWith("/chat")}
            className={`py-2.5 ${pathname.startsWith("/chat") ? "font-semibold text-primary" : "text-ink-soft"}`}
          />
          <Link
            href="/roommate"
            className={`py-2.5 ${pathname.startsWith("/roommate") ? "font-semibold text-primary" : "text-ink-soft"}`}
          >
            Ghép bạn ở
          </Link>
          <div className="mt-1 border-t border-line-soft pt-1">
            {me ? (
              <Link href="/me" className="block truncate py-2.5 text-ink-soft">
                Tài khoản: {me.name || me.email}
              </Link>
            ) : me === false ? (
              <Link href="/login" className="block py-2.5 font-semibold text-primary">
                Đăng nhập
              </Link>
            ) : null}
            {me && me.role === "admin" && (
              <Link href="/quan-ly/nha-tro" className="block py-2.5 text-ink-soft">
                Quản lý nhà trọ
              </Link>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}

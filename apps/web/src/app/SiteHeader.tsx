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
  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : false))
      .then(setMe)
      .catch(() => setMe(false));
  }, []);

  return (
    <header className="flex h-[76px] shrink-0 items-center justify-between border-b border-line bg-white px-5 sm:px-10">
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
      </div>
    </header>
  );
}

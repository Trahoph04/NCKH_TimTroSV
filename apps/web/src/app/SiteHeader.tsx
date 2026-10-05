"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import ChatNavLink from "./ChatNavLink";

const NAV = [
  { href: "/", label: "Tìm trọ" },
  { href: "/map", label: "Bản đồ" },
  { href: "/listings/mine", label: "Tin của tôi" },
];

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export default function SiteHeader() {
  const pathname = usePathname();
  // cookie là httpOnly nên phải hỏi server; null = chưa biết, false = chưa đăng nhập
  const [me, setMe] = useState<{ name: string | null; email: string } | false | null>(null);
  useEffect(() => {
    fetch("/api/auth/me", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : false))
      .then(setMe)
      .catch(() => setMe(false));
  }, []);

  return (
    <header className="flex h-[76px] shrink-0 items-center justify-between border-b border-line bg-white px-5 sm:px-10">
      <Link href="/" className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-primary text-lg font-extrabold text-white">
          T
        </span>
        <span className="flex flex-col leading-tight">
          <span className="text-lg font-extrabold tracking-tight text-ink">Trọ CTU</span>
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
        <Link
          href="/listings/new"
          className="rounded-[10px] bg-primary px-4 py-2.5 text-[15px] font-semibold text-white transition hover:bg-navy"
        >
          Đăng tin miễn phí
        </Link>
      </div>
    </header>
  );
}

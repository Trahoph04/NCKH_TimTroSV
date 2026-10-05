"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Mục "Tin nhắn" trên header + badge số tin chưa đọc.
// Trang /chat đẩy số mới qua sự kiện window "chat:unread" (realtime);
// các trang khác hỏi /api/chat/unread mỗi 30s. Chưa đăng nhập ⇒ không hiện badge.
export default function ChatNavLink({ active, className }: { active: boolean; className: string }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch("/api/chat/unread", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { messages: number };
        if (alive) setCount(data.messages);
      } catch {
        /* offline: giữ số cũ */
      }
    };
    const onPush = (e: Event) => setCount((e as CustomEvent<number>).detail);
    window.addEventListener("chat:unread", onPush);
    if (!active) load();
    const t = active ? undefined : setInterval(load, 30_000);
    return () => {
      alive = false;
      window.removeEventListener("chat:unread", onPush);
      if (t) clearInterval(t);
    };
  }, [active]);

  return (
    <Link href="/chat" className={`inline-flex items-center gap-1.5 ${className}`}>
      Tin nhắn
      {count > 0 && (
        <span className="rounded-full bg-primary-bright px-1.5 text-[11px] font-bold leading-[18px] text-white">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}

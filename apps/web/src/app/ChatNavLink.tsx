"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Mục "Tin nhắn" trên header + badge = tin chưa đọc + lời mời ghép đang chờ.
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
        // Cộng cả `likes`: bản trước bỏ số này nên có người thích mình mà header
        // không báo gì, trong khi tab Lời mời trong /chat thì có.
        const data = (await res.json()) as { messages: number; likes?: number };
        if (alive) setCount(data.messages + (data.likes ?? 0));
      } catch {
        /* offline: giữ số cũ */
      }
    };
    const onPush = (e: Event) => setCount((e as CustomEvent<number>).detail);
    window.addEventListener("chat:unread", onPush);
    // Vào /chat: vẫn tải 1 lần để có số ngay; ChatApp chỉ đẩy số khi danh sách đã tải xong.
    load();
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

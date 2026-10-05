import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/current-user";
import SiteHeader from "../SiteHeader";
import ChatApp from "./ChatApp";

export const dynamic = "force-dynamic";
export const metadata = { title: "Tin nhắn — Trọ CTU" };

// Mockup 06 (UI_NCKH.html) — tin nhắn realtime giữa hai SV đã ghép ở.
export default async function ChatPage({ searchParams }: { searchParams: { c?: string } }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/chat");

  const c = Number(searchParams.c);
  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <SiteHeader />
      <ChatApp
        me={{ id: user.id, name: user.name || "Bạn" }}
        initialConversationId={Number.isInteger(c) && c > 0 ? c : null}
      />
    </div>
  );
}

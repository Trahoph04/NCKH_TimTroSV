import { redirect } from "next/navigation";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import SiteHeader from "../SiteHeader";
import RoommateApp from "./RoommateApp";
import type { DeckMode } from "./types";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ghép bạn ở — Trọ CTU" };

// Reciprocal Recommender: lọc cứng → Gower có trọng số → harmonic mean → top-K
// kèm lý do. Thuật toán ở apps/api/app/matching/.
//
// Chế độ deck: ?mode=random cho buổi thử nghiệm (link phát cho SV), hoặc đặt
// ROOMMATE_DECK_MODE=random trong môi trường của web để ép cho MỌI người suốt
// buổi — đọc lúc chạy, không bake lúc build. Query thắng biến môi trường để
// người điều phối vẫn xem được bản ranked khi cần.
export default async function RoommatePage({ searchParams }: { searchParams: { mode?: string } }) {
  const user = await getCurrentUser();
  if (!user) redirect(reauthUrl("/roommate"));

  const raw = searchParams.mode ?? process.env.ROOMMATE_DECK_MODE ?? "ranked";
  const mode: DeckMode = raw === "random" ? "random" : "ranked";

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <SiteHeader />
      <RoommateApp key={mode} me={{ id: user.id, name: user.name || "Bạn" }} mode={mode} />
    </div>
  );
}

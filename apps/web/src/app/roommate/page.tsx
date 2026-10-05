import { redirect } from "next/navigation";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import SiteHeader from "../SiteHeader";
import RoommateApp from "./RoommateApp";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ghép bạn ở — Trọ CTU" };

// Reciprocal Recommender: lọc cứng → Gower có trọng số → harmonic mean → top-K
// kèm lý do. Thuật toán ở apps/api/app/matching/.
export default async function RoommatePage() {
  const user = await getCurrentUser();
  if (!user) redirect(reauthUrl("/roommate"));

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <SiteHeader />
      <RoommateApp me={{ id: user.id, name: user.name || "Bạn" }} />
    </div>
  );
}

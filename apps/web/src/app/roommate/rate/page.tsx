import { redirect } from "next/navigation";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import SiteHeader from "../../SiteHeader";
import RateApp from "./RateApp";

export const dynamic = "force-dynamic";
export const metadata = { title: "Chấm điểm ghép bạn — Trọ CTU" };

// Thu điểm 1–5 cho đánh giá thuật toán (thiết kế 2.7): 5 thẻ = 3 của thuật toán
// + 2 ngẫu nhiên trong pool, xáo trộn, KHÔNG hiện % — người chấm không biết thẻ
// nào thuộc nhóm nào. Xuất CSV: python -m app.matching.export_ratings
export default async function RatePage() {
  const user = await getCurrentUser();
  if (!user) redirect(reauthUrl("/roommate/rate"));

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden">
      <SiteHeader />
      <RateApp />
    </div>
  );
}

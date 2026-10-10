import { redirect } from "next/navigation";
import { getCurrentUser, reauthUrl } from "@/lib/current-user";
import SiteHeader from "../../SiteHeader";
import EvalApp from "./EvalApp";

export const dynamic = "force-dynamic";
export const metadata = { title: "Đánh giá gợi ý phòng — Trọ CTU" };

// Đánh giá mù hệ gợi ý (docs/specs/Recommendation.md R10): gộp top-10 của 3 hệ, xáo trộn, thẻ giống hệt nhau —
// người chấm không biết tin nào do hệ nào xếp. Xuất CSV: python -m app.recommend.export_judgments
export default async function RecommendEvalPage() {
  const user = await getCurrentUser();
  if (!user) redirect(reauthUrl("/goi-y/danh-gia"));

  return (
    <div className="min-h-screen bg-paper">
      <SiteHeader />
      <EvalApp />
    </div>
  );
}

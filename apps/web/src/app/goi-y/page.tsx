import SiteHeader from "../SiteHeader";
import RecommendApp from "./RecommendApp";

export const metadata = { title: "Gợi ý phòng — Trọ CTU" };

// Gợi ý nhà trọ (FR-4): knowledge-based + MAUT + MMR — docs/specs/Recommendation.md.
export default function RecommendPage() {
  return (
    <div className="min-h-screen bg-paper">
      <SiteHeader />
      <RecommendApp />
    </div>
  );
}

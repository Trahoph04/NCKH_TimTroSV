import { proxyToApi } from "@/lib/proxy";

// Danh sách đánh giá cho trang kiểm duyệt /quan-ly/danh-gia (API tự kiểm quyền admin).
export async function GET(req: Request) {
  return proxyToApi(req, "/admin/reviews");
}

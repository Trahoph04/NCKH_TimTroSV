import { proxyToApi } from "@/lib/proxy";

// Danh sách người dùng cho trang /quan-ly/nguoi-dung (API tự kiểm quyền admin).
export async function GET(req: Request) {
  return proxyToApi(req, "/admin/users");
}

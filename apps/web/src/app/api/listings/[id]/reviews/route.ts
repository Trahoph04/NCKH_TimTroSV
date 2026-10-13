import { NextResponse } from "next/server";
import { API_URL } from "@/lib/config";
import { proxyToApi } from "@/lib/proxy";

// Đánh giá của 1 tin: đọc công khai (không cần đăng nhập), viết qua proxyToApi (gắn token, tự refresh).
export async function GET(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  try {
    const res = await fetch(`${API_URL}/listings/${params.id}/reviews${new URL(req.url).search}`, { cache: "no-store" });
    return new NextResponse(res.body, { status: res.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "Không kết nối được máy chủ" }, { status: 502 });
  }
}

export async function POST(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy tin" }, { status: 404 });
  return proxyToApi(req, `/listings/${params.id}/reviews`);
}

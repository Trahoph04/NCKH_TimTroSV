import { NextResponse } from "next/server";
import { API_URL } from "@/lib/config";

// POST /api/recommend → FastAPI /recommend. Public (không cần đăng nhập); proxy để browser không gọi khác origin.
export async function POST(req: Request) {
  try {
    const res = await fetch(`${API_URL}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await req.text(),
      cache: "no-store",
    });
    return new NextResponse(res.body, { status: res.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "Không kết nối được máy chủ" }, { status: 502 });
  }
}

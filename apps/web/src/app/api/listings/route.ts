import { NextResponse } from "next/server";
import { searchListings, type ApiError } from "@/lib/api";
import { proxyToApi } from "@/lib/proxy";

// Tìm tin cho client component (vd. chọn tin trọ để chia sẻ trong chat).
// API listings là public, chỉ cần proxy để browser không phải gọi khác origin.
export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const size = Math.min(Number(sp.get("size")) || 8, 20);
  try {
    const result = await searchListings({ q: sp.get("q") || undefined, size, sort: "newest" });
    return NextResponse.json(result);
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json({ detail: err.detail ?? "Lỗi tìm tin" }, { status: err.status ?? 500 });
  }
}

// Thêm nhà trọ (admin) — qua proxyToApi để tự refresh token hết hạn giữa lúc điền form; API tự validate (422).
export async function POST(req: Request) {
  return proxyToApi(req, "/listings");
}

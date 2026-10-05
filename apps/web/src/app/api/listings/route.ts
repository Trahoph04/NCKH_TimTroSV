import { NextResponse } from "next/server";
import { createListing, searchListings, type ApiError, type ListingInput } from "@/lib/api";
import { getAccessToken } from "@/lib/session";

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

export async function POST(req: Request) {
  const token = getAccessToken();
  if (!token) {
    return NextResponse.json({ detail: "Chưa đăng nhập" }, { status: 401 });
  }

  let body: Partial<ListingInput>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Body không hợp lệ" }, { status: 400 });
  }

  if (!body.title) {
    return NextResponse.json({ detail: "Thiếu tiêu đề" }, { status: 400 });
  }

  try {
    const listing = await createListing(token, body as ListingInput);
    return NextResponse.json(listing, { status: 201 });
  } catch (e) {
    const err = e as ApiError;
    return NextResponse.json(
      { detail: err.detail ?? "Đăng tin thất bại" },
      { status: err.status ?? 500 },
    );
  }
}

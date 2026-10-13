import { NextResponse } from "next/server";
import { proxyToApi } from "@/lib/proxy";

// Ẩn / hiện một đánh giá. id phải là số — proxy ghép thẳng vào path API.
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  if (!/^\d+$/.test(params.id)) return NextResponse.json({ detail: "Không tìm thấy đánh giá" }, { status: 404 });
  return proxyToApi(req, `/admin/reviews/${params.id}`);
}

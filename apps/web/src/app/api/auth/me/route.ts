import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/current-user";

// Cho client component (header) biết đang đăng nhập ai — cookie là httpOnly nên JS không tự đọc được.
// Route Handler được set cookie ⇒ canRefresh=true: access hết hạn thì refresh luôn.
export const dynamic = "force-dynamic";

export async function GET() {
  const user = await getCurrentUser(true);
  if (!user) return NextResponse.json({ detail: "Chưa đăng nhập" }, { status: 401 });
  return NextResponse.json({ id: user.id, name: user.name, email: user.email });
}

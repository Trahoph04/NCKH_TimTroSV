import { NextResponse } from "next/server";
import { loginCtu, type ApiError } from "@/lib/api";
import { setAuthCookies } from "@/lib/session";

export async function POST(req: Request) {
  let body: { mssv?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: "Body không hợp lệ" }, { status: 400 });
  }

  const mssv = body.mssv?.trim();
  const { password } = body;
  if (!mssv || !password) {
    return NextResponse.json({ detail: "Thiếu MSSV hoặc mã đăng nhập" }, { status: 400 });
  }

  try {
    const tokens = await loginCtu(mssv, password);
    setAuthCookies(tokens.access_token, tokens.refresh_token);
    return NextResponse.json({ ok: true });
  } catch (e) {
    const err = e as ApiError;
    // 422 của FastAPI có detail là mảng — không đưa thẳng lên UI
    const detail =
      typeof err.detail === "string" ? err.detail : "MSSV hoặc mã đăng nhập sai";
    return NextResponse.json({ detail }, { status: err.status ?? 500 });
  }
}

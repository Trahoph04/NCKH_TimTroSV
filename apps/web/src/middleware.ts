import { NextResponse, type NextRequest } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/config";

// Gate nhẹ theo sự tồn tại của cookie (không verify chữ ký ở đây — page tự
// gọi /me để xác thực thật). Middleware chỉ điều hướng UX: chặn vào trang cần
// login khi thiếu token, và đẩy user đã login khỏi trang login/register.
const PROTECTED = ["/me", "/dashboard", "/listings/new", "/listings/mine", "/chat", "/roommate"];
const AUTH_PAGES = ["/login", "/register"];

// Route dynamic /listings/[id]/edit không match được bằng startsWith cố định
// vì id nằm giữa path — check riêng bằng regex.
const EDIT_LISTING_RE = /^\/listings\/[^/]+\/edit(\/|$)/;

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession =
    req.cookies.has(ACCESS_COOKIE) || req.cookies.has(REFRESH_COOKIE);

  const isProtected =
    PROTECTED.some((p) => pathname.startsWith(p)) || EDIT_LISTING_RE.test(pathname);

  if (isProtected && !hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  if (AUTH_PAGES.some((p) => pathname.startsWith(p)) && hasSession) {
    // đã đăng nhập mà vào /login?next=/chat ⇒ đi thẳng tới /chat (trước đây luôn về /me)
    const raw = req.nextUrl.searchParams.get("next") || "/";
    const url = req.nextUrl.clone();
    url.pathname = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/me/:path*",
    "/dashboard/:path*",
    "/login",
    "/register",
    "/listings/new",
    "/listings/mine",
    "/listings/:id/edit",
    "/chat/:path*",
    // Thiếu dòng này thì middleware KHÔNG chạy cho /roommate và cả PROTECTED ở
    // trên cũng vô hiệu — phải khai ở cả hai nơi.
    "/roommate/:path*",
  ],
};

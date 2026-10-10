import { NextResponse, type NextRequest } from "next/server";
import { ACCESS_COOKIE, REFRESH_COOKIE } from "@/lib/config";

// Gate nhẹ theo sự tồn tại của cookie (không verify chữ ký ở đây — page tự
// gọi /me để xác thực thật). Middleware chỉ điều hướng UX: chặn vào trang cần
// login khi thiếu token, và đẩy user đã login khỏi trang login/register.
const PROTECTED = ["/me", "/dashboard", "/listings/new", "/quan-ly", "/chat", "/roommate"];
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
    url.search = "";
    url.searchParams.set("next", pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }

  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p));

  // Page server-side đã gọi /me và thấy token không dùng được (đổi JWT_SECRET,
  // reset_and_seed xoá user…) ⇒ redirect về /login?reauth=1. Cookie vẫn CÒN nên
  // nếu nhánh dưới đẩy tiếp về `next` là vòng redirect vô hạn
  // (ERR_TOO_MANY_REDIRECTS). Xoá cookie ở đây và cho trang login hiện ra.
  if (isAuthPage && req.nextUrl.searchParams.has("reauth")) {
    const url = req.nextUrl.clone();
    url.searchParams.delete("reauth");
    const res = NextResponse.redirect(url);
    res.cookies.delete(ACCESS_COOKIE);
    res.cookies.delete(REFRESH_COOKIE);
    return res;
  }

  if (isAuthPage && hasSession) {
    // đã đăng nhập mà vào /login?next=/chat ⇒ đi thẳng tới /chat (trước đây luôn về /me)
    const raw = req.nextUrl.searchParams.get("next") || "/";
    const safe = raw.startsWith("/") && !raw.startsWith("//") ? raw : "/";
    // `next` có thể mang query (/roommate?mode=random) — gán thẳng vào pathname
    // sẽ mã hoá "?" thành %3F ⇒ 404. Tách bằng URL rồi kiểm lại cùng origin.
    const target = new URL(safe, req.nextUrl.origin);
    if (target.origin !== req.nextUrl.origin) target.href = new URL("/", req.nextUrl.origin).href;
    return NextResponse.redirect(target);
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
    "/quan-ly/:path*",
    "/listings/:id/edit",
    "/chat/:path*",
    // Thiếu dòng này thì middleware KHÔNG chạy cho /roommate và cả PROTECTED ở
    // trên cũng vô hiệu — phải khai ở cả hai nơi.
    "/roommate/:path*",
  ],
};

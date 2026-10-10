import { notFound, redirect } from "next/navigation";
import { getMe, refresh, type ApiError, type User } from "./api";
import {
  getAccessToken,
  getRefreshToken,
  setAuthCookies,
} from "./session";

// Lấy user hiện tại từ cookie. Nếu access hết hạn (401) thử refresh 1 lần.
// LƯU Ý: setAuthCookies chỉ hiệu lực trong Route Handler / Server Action —
// gọi từ Server Component render sẽ throw (Next không cho set cookie khi render).
// Server Component chỉ đọc: dùng canRefresh=false để tránh throw.
export async function getCurrentUser(
  canRefresh = false,
): Promise<User | null> {
  const access = getAccessToken();
  if (access) {
    try {
      return await getMe(access);
    } catch (e) {
      if ((e as ApiError).status !== 401) return null;
      // access hết hạn → rơi xuống refresh
    }
  }

  const refreshTok = getRefreshToken();
  if (!refreshTok) return null;

  try {
    const tokens = await refresh(refreshTok);
    if (canRefresh) {
      setAuthCookies(tokens.access_token, tokens.refresh_token);
    }
    return await getMe(tokens.access_token);
  } catch {
    return null;
  }
}

// URL cho page server-side khi getCurrentUser() trả null. Tới được page nghĩa
// là middleware đã thấy cookie ⇒ cookie đó không dùng được; `reauth=1` báo
// middleware xoá cookie trước khi hiện /login, nếu không sẽ vòng redirect
// /login → next → /login… vô hạn.
export function reauthUrl(next: string): string {
  return `/login?reauth=1&next=${encodeURIComponent(next)}`;
}

// Trang quản trị: chưa đăng nhập ⇒ về login; đăng nhập mà không phải admin ⇒ 404 (không quảng cáo là có trang này).
// Backend vẫn tự chặn bằng require_admin — đây chỉ là UX.
export async function requireAdminPage(next: string): Promise<User> {
  const user = await getCurrentUser();
  if (!user) redirect(reauthUrl(next));
  if (user.role !== "admin") notFound();
  return user;
}

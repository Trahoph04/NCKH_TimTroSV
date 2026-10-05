import { cookies } from "next/headers";
import {
  ACCESS_COOKIE,
  ACCESS_MAX_AGE,
  REFRESH_COOKIE,
  REFRESH_MAX_AGE,
} from "./config";

// httpOnly cookie — JS client không đọc được token (chống XSS đánh cắp token).
// secure=false ở dev (http localhost); prod bật qua NODE_ENV.
// COOKIE_SECURE ghi đè: chạy bản build production qua HTTP trong mạng LAN
// (máy khác mở http://<IP>:3000) thì PHẢI đặt COOKIE_SECURE=false — trình duyệt
// bỏ cookie `secure` trên http (trừ localhost) ⇒ đăng nhập xong vẫn bị đá ra.
const isProd = process.env.NODE_ENV === "production";
const secureCookie =
  process.env.COOKIE_SECURE != null ? process.env.COOKIE_SECURE === "true" : isProd;

const baseOpts = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: secureCookie,
  path: "/",
};

export function setAuthCookies(access: string, refresh: string): void {
  const jar = cookies();
  jar.set(ACCESS_COOKIE, access, { ...baseOpts, maxAge: ACCESS_MAX_AGE });
  jar.set(REFRESH_COOKIE, refresh, { ...baseOpts, maxAge: REFRESH_MAX_AGE });
}

export function clearAuthCookies(): void {
  const jar = cookies();
  jar.delete(ACCESS_COOKIE);
  jar.delete(REFRESH_COOKIE);
}

export function getAccessToken(): string | undefined {
  return cookies().get(ACCESS_COOKIE)?.value;
}

export function getRefreshToken(): string | undefined {
  return cookies().get(REFRESH_COOKIE)?.value;
}

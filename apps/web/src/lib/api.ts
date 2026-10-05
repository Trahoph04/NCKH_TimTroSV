import { API_URL } from "./config";

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: number;
  email: string;
  name: string | null;
  role: string;
  avatar_url: string | null;
};

export type ApiError = { status: number; detail: string };

// Gọi FastAPI từ server (route handler / server component). KHÔNG dùng ở client.
export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    cache: "no-store",
  });

  if (!res.ok) {
    let detail = `Lỗi ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      // body không phải JSON — giữ message mặc định
    }
    throw { status: res.status, detail } satisfies ApiError;
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function login(email: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

// Tài khoản cấp trước cho buổi thử nghiệm chỉ có identity provider='ctu'
// (không có 'local') ⇒ phải đi đường riêng, /auth/login sẽ trả 401.
export function loginCtu(mssv: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>("/auth/login/ctu", {
    method: "POST",
    body: JSON.stringify({ mssv, password }),
  });
}

export function register(
  email: string,
  password: string,
  name?: string,
): Promise<TokenPair> {
  return apiFetch<TokenPair>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, name: name || null }),
  });
}

export function refresh(refreshToken: string): Promise<TokenPair> {
  return apiFetch<TokenPair>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export function getMe(accessToken: string): Promise<User> {
  return apiFetch<User>("/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

// ---- Listings ----

export type ListingOut = {
  id: number;
  title: string;
  price: number | null;
  area: number | null;
  address: string | null;
  district: string | null;
  lat: number | null;
  lng: number | null;
  distance_to_ctu: number | null;
  description: string | null;
  images: string[];
  source: string;
  source_url: string | null;
  risk_score: number | null;
  risk_level: string;
  geocode_confidence: string | null;
  freshness_score: number | null;
  freshness_label: string;
  quality_score: number | null;
  last_seen: string | null;
  route_time_campus: number[] | null; // [khuI, khuII, khuIII] phút, null = chưa route
};

export type SearchResult = {
  total: number;
  page: number;
  size: number;
  items: ListingOut[];
};

export type SearchListingsParams = {
  q?: string;
  min_price?: number;
  max_price?: number;
  min_area?: number;
  district?: string;
  max_distance_ctu?: number;
  sort?: string;
  page?: number;
  size?: number;
};

export type ListingInput = {
  title: string;
  price?: number | null;
  area?: number | null;
  address?: string | null;
  district?: string | null;
  description?: string | null;
  images?: string[];
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export function searchListings(params: SearchListingsParams): Promise<SearchResult> {
  return apiFetch<SearchResult>(`/listings${buildQuery(params)}`);
}

export function getListing(id: number | string): Promise<ListingOut> {
  return apiFetch<ListingOut>(`/listings/${id}`);
}

export function getNearby(lat: number, lng: number, radius: number): Promise<ListingOut[]> {
  return apiFetch<ListingOut[]>(`/listings/nearby${buildQuery({ lat, lng, radius })}`);
}

// campus: 0=khu I, 1=khu II, 2=khu III. Trả polyline [lat,lng] campus→tin (FR-M.8).
export function getListingRoute(id: number | string, campus: number): Promise<number[][]> {
  return apiFetch<number[][]>(`/listings/${id}/route${buildQuery({ campus })}`);
}

export function getMyListings(token: string): Promise<ListingOut[]> {
  return apiFetch<ListingOut[]>("/listings/mine", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function createListing(token: string, data: ListingInput): Promise<ListingOut> {
  return apiFetch<ListingOut>("/listings", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
}

export function updateListing(
  token: string,
  id: number | string,
  data: Partial<ListingInput>,
): Promise<ListingOut> {
  return apiFetch<ListingOut>(`/listings/${id}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
}

export function deleteListing(token: string, id: number | string): Promise<void> {
  return apiFetch<void>(`/listings/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

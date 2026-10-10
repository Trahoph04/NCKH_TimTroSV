"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { ContactOut, ListingOut, PoiOut, PoiSummary } from "@/lib/api";
import { formatPhone, formatPrice, isLocationPrecise, listingTags, sourceName } from "@/lib/format";
import { formatMeters, POI_CATEGORIES } from "@/lib/pois";

// maplibre-gl đụng window ngay khi import → phải tắt SSR, nếu không build
// Next lỗi "window is not defined" lúc render phía server.
const MapCanvas = dynamic(() => import("./MapCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-tint text-sm text-ink-faint">
      Đang tải bản đồ...
    </div>
  ),
});

// Index khớp CAMPUSES trong apps/api/app/listings/routing.py (0=khu I,1=khu II,2=khu III).
const CAMPUS_LABELS = ["Khu I", "Khu II", "Khu III"];
const HOUSING_TABS = [
  { value: "", label: "Tất cả" },
  { value: "phong_tro", label: "Phòng trọ" },
  { value: "nha_mini", label: "Nhà mini" },
];
const POI_RADIUS = 1000;

export type ListingWithCoords = ListingOut & { lat: number; lng: number };

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export default function MapScreen({
  items,
  radius,
  housing,
  error,
  focusId = null,
  initialCampus = 1,
}: {
  items: ListingOut[];
  radius: number;
  housing: string;
  error: string | null;
  focusId?: number | null; // ?focus=<id>: mở bản đồ với tin đã chọn (từ bản đồ nhỏ ở trang chi tiết)
  initialCampus?: number; // ?campus=0|1|2: khu bản đồ nhỏ đang hiện, để 2 nơi cùng số phút
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [campus, setCampus] = useState(initialCampus); // mặc định khu II (FR-M.3)
  const [radiusDraft, setRadiusDraft] = useState(radius);
  const [selected, setSelected] = useState<ListingWithCoords | null>(null);
  const [route, setRoute] = useState<[number, number][] | null>(null);
  const [routeStatus, setRouteStatus] = useState<"idle" | "loading" | "ok" | "fail">("idle");
  const [group, setGroup] = useState<number[] | null>(null);
  const [pois, setPois] = useState<PoiOut[]>([]);
  const [poiSummary, setPoiSummary] = useState<PoiSummary | null>(null);
  const [contact, setContact] = useState<ContactOut | null>(null);
  const [hiddenPoiCats, setHiddenPoiCats] = useState<string[]>([]);
  // Mặc định hiện cả tin cấp phường (chỉ tin chính xác thì quá ít — 26 tin/5 km); MapCanvas vẽ chúng thành lớp
  // riêng (chấm rỗng, cụm xám) nằm dưới tin chính xác. Bật "chỉ chính xác" khi cần demo gọn.
  const [preciseOnly, setPreciseOnly] = useState(false);
  // Bấm nhanh qua nhiều tin: response về muộn của tin cũ không được ghi đè tin mới.
  const latestId = useRef<number | null>(null);

  const allWithCoords = useMemo(
    () => items.filter((l): l is ListingWithCoords => l.lat != null && l.lng != null),
    [items],
  );
  const preciseCount = useMemo(() => allWithCoords.filter(isLocationPrecise).length, [allWithCoords]);
  const withCoords = useMemo(
    () => (preciseOnly ? allWithCoords.filter(isLocationPrecise) : allWithCoords),
    [allWithCoords, preciseOnly],
  );
  const listed = useMemo(
    () => (group ? withCoords.filter((l) => group.includes(l.id)) : withCoords),
    [withCoords, group],
  );

  // Đổi bán kính/loại/bật tin gần đúng → nhóm + tin đang chọn có thể không còn trên bản đồ.
  useEffect(() => {
    setGroup(null);
    setSelected((cur) => (cur && withCoords.some((l) => l.id === cur.id) ? cur : null));
  }, [withCoords]);

  async function drawRoute(listing: ListingWithCoords, campusIdx: number) {
    setRouteStatus("loading");
    try {
      const path = await getJson<[number, number][]>(
        `/api/listings/${listing.id}/route?campus=${campusIdx}`,
      );
      if (latestId.current === listing.id) {
        setRoute(path);
        setRouteStatus("ok");
      }
    } catch {
      // cả ORS lẫn OSRM dự phòng đều lỗi và cache chưa có — không chặn UI, nhưng báo cho người dùng biết (FR-M.8)
      if (latestId.current === listing.id) {
        setRoute(null);
        setRouteStatus("fail");
      }
    }
  }

  async function loadPois(listing: ListingWithCoords) {
    const qs = `lat=${listing.lat}&lng=${listing.lng}&radius=${POI_RADIUS}`;
    try {
      const [list, summary] = await Promise.all([
        getJson<PoiOut[]>(`/api/pois?${qs}`),
        getJson<PoiSummary>(`/api/pois/summary?${qs}`),
      ]);
      if (latestId.current !== listing.id) return;
      setPois(list);
      setPoiSummary(summary);
    } catch {
      // bảng pois trống / API lỗi → card chỉ không có phần tiện ích
    }
  }

  async function loadContact(listing: ListingWithCoords) {
    try {
      const c = await getJson<ContactOut>(`/api/listings/${listing.id}/contact`);
      if (latestId.current === listing.id) setContact(c);
    } catch {
      // không lấy được liên hệ → card vẫn còn nút "Xem chi tiết"
    }
  }

  function selectListing(listing: ListingWithCoords) {
    latestId.current = listing.id;
    setSelected(listing);
    setRoute(null);
    setPois([]);
    setPoiSummary(null);
    setContact(null);
    void drawRoute(listing, campus);
    void loadPois(listing);
    void loadContact(listing);
  }

  // Mở từ bản đồ nhỏ ở trang chi tiết: chọn sẵn tin (chỉ 1 lần, khi tin nằm trong danh sách đã tải)
  const focused = useRef(false);
  useEffect(() => {
    if (focused.current || focusId == null) return;
    const target = allWithCoords.find((l) => l.id === focusId);
    if (target) {
      focused.current = true;
      selectListing(target);
    }
    // selectListing đổi mỗi render nhưng chỉ cần chạy lần đầu có dữ liệu
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, allWithCoords]);

  function clearSelection() {
    latestId.current = null;
    setRouteStatus("idle");
    setSelected(null);
    setRoute(null);
    setPois([]);
    setPoiSummary(null);
    setContact(null);
  }

  function changeCampus(idx: number) {
    setCampus(idx);
    setRoute(null);
    if (selected) void drawRoute(selected, idx);
  }

  function navigate(nextRadius: number, nextHousing: string) {
    const qs = new URLSearchParams({ radius: String(nextRadius) });
    if (nextHousing) qs.set("housing", nextHousing);
    startTransition(() => router.replace(`/map?${qs.toString()}`, { scroll: false }));
  }

  function commitRadius() {
    if (radiusDraft !== radius) navigate(radiusDraft, housing);
  }

  function togglePoiCat(key: string) {
    setHiddenPoiCats((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]));
  }

  function minutesLabel(listing: ListingOut): string | null {
    const minutes = listing.route_time_campus?.[campus];
    if (minutes == null) return null;
    return `${Math.round(minutes)} phút tới ${CAMPUS_LABELS[campus].replace("Khu", "khu")}`;
  }

  const approximate = selected?.geocode_confidence !== "high";
  const tags = selected ? listingTags(selected) : [];

  return (
    <div className="flex min-h-0 flex-1 flex-col-reverse lg:grid lg:grid-cols-[400px_minmax(0,1fr)]">
      {/* Sidebar danh sách tin (mockup 03) */}
      <aside className="flex min-h-0 flex-1 flex-col border-t border-line bg-white lg:border-r lg:border-t-0">
        <div className="border-b border-line-soft px-5 py-4">
          {group ? (
            <>
              <h1 className="text-[17px] font-bold text-ink">{listed.length} tin chung một vị trí</h1>
              <p className="mt-1 text-[13px] text-ink-muted">
                Nguồn tin chỉ cho vị trí gần đúng (cấp phường) nên các tin này trùng toạ độ trên bản đồ.
              </p>
              <button
                type="button"
                onClick={() => setGroup(null)}
                className="mt-2 text-[13.5px] font-medium text-primary-bright hover:underline"
              >
                ← Xem tất cả {withCoords.length} tin
              </button>
            </>
          ) : (
            <h1 className="text-[17px] font-bold text-ink">
              {withCoords.length} tin {preciseOnly ? "vị trí chính xác " : ""}trong bán kính{" "}
              {(radius / 1000).toFixed(1)} km
            </h1>
          )}

          {preciseCount < allWithCoords.length && (
            <label className="mt-2 flex cursor-pointer items-start gap-2 text-[13px] text-ink-muted">
              <input
                type="checkbox"
                checked={preciseOnly}
                onChange={(e) => setPreciseOnly(e.target.checked)}
                className="mt-0.5 accent-[#0b4d8f]"
              />
              <span>
                Chỉ hiện {preciseCount} tin vị trí chính xác (ẩn {allWithCoords.length - preciseCount} tin sàn chỉ cho
                toạ độ cấp phường)
              </span>
            </label>
          )}

          <div className="mt-3 flex gap-1.5" role="group" aria-label="Loại chỗ ở">
            {HOUSING_TABS.map((tab) => (
              <button
                key={tab.value || "all"}
                type="button"
                onClick={() => tab.value !== housing && navigate(radius, tab.value)}
                className={`rounded-full border px-3 py-1 text-[13px] transition ${
                  housing === tab.value
                    ? "border-primary bg-primary-soft font-semibold text-primary"
                    : "border-line text-ink-soft hover:border-primary-ring"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="mt-3 flex gap-1.5 rounded-[11px] bg-tint p-1">
            {CAMPUS_LABELS.map((label, i) => (
              <button
                key={label}
                type="button"
                onClick={() => changeCampus(i)}
                className={`flex-1 rounded-lg py-2 text-sm transition ${
                  campus === i
                    ? "bg-primary font-semibold text-white"
                    : "text-ink-soft hover:bg-white/70"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2.5 text-[13px] text-ink-muted">
            Bấm một tin để vẽ đường đi từ {CAMPUS_LABELS[campus].replace("Khu", "khu")} tới phòng và xem tiện
            ích xung quanh.
          </p>
        </div>

        {error && (
          <p className="mx-3 mt-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</p>
        )}
        {!error && withCoords.length === 0 && (
          <p className="mt-10 px-4 text-center text-ink-muted">
            Không tìm thấy tin nào trong bán kính này
          </p>
        )}

        <div
          className={`flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-3 ${
            isPending ? "opacity-50" : ""
          }`}
        >
          {listed.map((listing) => {
            const isSelected = selected?.id === listing.id;
            const meta = [
              listing.area != null ? `${listing.area} m²` : null,
              listing.district,
              minutesLabel(listing),
            ]
              .filter(Boolean)
              .join(" · ");
            const rowTags = listingTags(listing);

            return (
              <button
                key={listing.id}
                type="button"
                onClick={() => selectListing(listing)}
                className={`flex gap-3 rounded-[13px] border p-3 text-left transition ${
                  isSelected
                    ? "border-primary-ring bg-primary-soft"
                    : "border-line-soft hover:border-primary-ring hover:bg-paper"
                }`}
              >
                {listing.images[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={listing.images[0]}
                    alt=""
                    loading="lazy"
                    className="h-[74px] w-[84px] shrink-0 rounded-[10px] object-cover"
                  />
                ) : (
                  <span className="photo-placeholder h-[74px] w-[84px] shrink-0 rounded-[10px]" />
                )}
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="line-clamp-2 text-[14.5px] font-semibold leading-tight text-ink">
                    {listing.title}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="text-base font-bold text-primary">
                      {formatPrice(listing.price)}
                    </span>
                    {rowTags.map((t) => (
                      <span key={t.label} className={`rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold ${t.className}`}>
                        {t.label}
                      </span>
                    ))}
                  </span>
                  {meta && <span className="truncate text-[13px] text-ink-muted">{meta}</span>}
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Bản đồ + các control nổi */}
      <div className="relative h-[52vh] min-h-0 lg:h-auto">
        <MapCanvas
          items={withCoords}
          campus={campus}
          radius={radius}
          selected={selected}
          route={route}
          pois={pois}
          hiddenPoiCats={hiddenPoiCats}
          onSelect={selectListing}
          onPickGroup={setGroup}
        />

        {/* Chú giải 2 lớp tin — hình dạng (đặc/rỗng) + chữ, không chỉ dựa vào màu */}
        {!preciseOnly && preciseCount < allWithCoords.length && (
          <div className="absolute left-4 top-4 z-10 flex flex-col gap-1 rounded-xl border border-line bg-white/95 px-3 py-2 text-[12px] text-ink-soft shadow-md">
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full border-2 border-white bg-[#1069bd] shadow" /> Vị trí chính xác
            </span>
            <span className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full border-2 border-[#64748b] bg-white" /> Vị trí gần đúng (cấp phường)
            </span>
          </div>
        )}

        {/* Điều khiển bán kính — góc phải trên theo mockup */}
        <div className="absolute right-4 top-4 z-10 flex w-[180px] flex-col gap-2 rounded-xl border border-line bg-white px-3.5 py-3 shadow-md">
          <span className="text-[13.5px] font-bold text-ink">
            Bán kính {(radiusDraft / 1000).toFixed(1)} km
          </span>
          <input
            type="range"
            min={500}
            max={5000}
            step={250}
            value={radiusDraft}
            onChange={(e) => setRadiusDraft(Number(e.target.value))}
            onPointerUp={commitRadius}
            onKeyUp={commitRadius}
            className="accent-[#0b4d8f]"
            aria-label="Bán kính tìm kiếm"
          />
        </div>

        {/* Card tin đang chọn — thay Popup vì nhiều tin trùng toạ độ nằm trong cluster,
            popup không mở được từ danh sách bên trái. */}
        {selected && (
          <div className="absolute bottom-5 left-4 z-10 flex max-h-[calc(100%-2.5rem)] w-[300px] flex-col overflow-y-auto rounded-[14px] border border-line bg-white p-3.5 shadow-xl">
            <button
              type="button"
              onClick={clearSelection}
              className="absolute right-2.5 top-2.5 z-10 flex h-7 w-7 items-center justify-center rounded-full bg-white/90 text-lg text-ink-muted shadow-sm hover:text-ink"
              aria-label="Đóng"
            >
              ×
            </button>
            {selected.images[0] ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={selected.images[0]}
                alt=""
                className="h-[96px] w-full shrink-0 rounded-[9px] object-cover"
              />
            ) : (
              <div className="photo-placeholder h-[72px] w-full shrink-0 rounded-[9px]" />
            )}
            {tags.length > 0 && (
              <div className="mt-2 flex gap-1.5">
                {tags.map((t) => (
                  <span key={t.label} className={`rounded-md px-2 py-0.5 text-[12px] font-semibold ${t.className}`}>
                    {t.label}
                  </span>
                ))}
              </div>
            )}
            <p className="mt-2 line-clamp-2 text-[14.5px] font-semibold leading-tight text-ink">
              {selected.title}
            </p>
            <p className="mt-1 text-[17px] font-bold text-primary">{formatPrice(selected.price)}</p>
            {selected.address && (
              <p className="mt-1 line-clamp-2 text-[13px] text-ink-muted">{selected.address}</p>
            )}
            <p className="mt-1 text-[13px] text-ink-muted">
              {minutesLabel(selected) ?? "Chưa có thời gian di chuyển"}
            </p>
            {routeStatus === "loading" && (
              <p className="mt-0.5 text-xs text-ink-faint">Đang vẽ đường đi…</p>
            )}
            {routeStatus === "fail" && (
              <p className="mt-0.5 text-xs text-amber-700">
                Chưa vẽ được đường đi tới {CAMPUS_LABELS[campus].replace("Khu", "khu")} lúc này
              </p>
            )}
            {approximate && (
              <p className="mt-1 text-xs text-ink-faint">Vị trí tương đối (chính xác tới cấp đường/phường)</p>
            )}

            {poiSummary && (
              <div className="mt-3 border-t border-line-soft pt-2.5">
                <p className="text-[13px] font-semibold text-ink">
                  {approximate ? "Tiện ích quanh khu vực" : "Tiện ích"} trong {POI_RADIUS / 1000} km
                </p>
                <ul className="mt-1.5 flex flex-col gap-0.5">
                  {POI_CATEGORIES.map((cat) => {
                    const row = poiSummary.categories.find((c) => c.category === cat.key);
                    const hidden = hiddenPoiCats.includes(cat.key);
                    return (
                      <li key={cat.key}>
                        <button
                          type="button"
                          onClick={() => togglePoiCat(cat.key)}
                          aria-pressed={!hidden}
                          title={hidden ? "Hiện trên bản đồ" : "Ẩn khỏi bản đồ"}
                          className={`flex w-full items-center gap-2 rounded-md px-1 py-0.5 text-left text-[12.5px] transition hover:bg-paper ${
                            hidden ? "opacity-45" : ""
                          }`}
                        >
                          <span
                            className="h-2.5 w-2.5 shrink-0 rounded-full"
                            style={{ background: cat.color }}
                          />
                          <span className="flex-1 truncate text-ink-soft">{cat.label}</span>
                          <span className="font-semibold text-ink">{row?.count ?? 0}</span>
                          <span className="w-[76px] whitespace-nowrap text-right text-ink-muted">
                            {row?.nearest ? `gần ${formatMeters(row.nearest.distance_m)}` : "—"}
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-1.5 text-[11px] leading-snug text-ink-faint">
                  Khoảng cách đường chim bay · Dữ liệu © OpenStreetMap
                </p>
              </div>
            )}

            {/* Liên hệ: có số thì gọi thẳng, không có số thì sang tin gốc trên trang nguồn */}
            {contact && (contact.phone || contact.facebook || contact.source_url) && (
              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line-soft pt-2.5 text-[13px]">
                {contact.phone ? (
                  <a href={`tel:${contact.phone}`} className="font-semibold text-primary hover:underline">
                    📞 {formatPhone(contact.phone)}
                  </a>
                ) : contact.facebook ? (
                  <a href={contact.facebook} target="_blank" rel="noopener noreferrer" className="font-semibold text-primary hover:underline">
                    Facebook chủ trọ ↗
                  </a>
                ) : (
                  <a href={contact.source_url!} target="_blank" rel="noopener noreferrer" className="font-semibold text-primary hover:underline">
                    Xem tin gốc trên {sourceName(contact.source_url)} ↗
                  </a>
                )}
              </div>
            )}

            <Link
              href={`/listings/${selected.id}`}
              className="mt-3 block shrink-0 rounded-[9px] bg-primary py-2.5 text-center text-sm font-semibold text-white transition hover:bg-navy"
            >
              Xem chi tiết
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

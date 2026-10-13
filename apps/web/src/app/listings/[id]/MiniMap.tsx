"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useState } from "react";
import { CAMPUS_MARKER_LABELS, minutesToCampusText, nearestCampus } from "@/lib/campus";

// maplibre-gl đụng window ngay khi import → tắt SSR (như map/MapScreen.tsx)
const MiniMapCanvas = dynamic(() => import("./MiniMapCanvas"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-tint" />,
});

// Bản đồ nhỏ hình tròn ở góc dưới bên phải trang chi tiết: ghim tin + khu CTU gần nhất (theo phút đi thật).
// Bấm vào → /map với tin đã chọn sẵn (vẽ đường đi, tiện ích xung quanh, liên hệ). Màn hẹp (< sm) nằm trong dòng
// nội dung thay vì nổi: khung 128 px cố định góc màn hình che mất giá/địa chỉ trên điện thoại.
export default function MiniMap({
  id,
  lat,
  lng,
  precise,
  routeTimes,
}: {
  id: number;
  lat: number;
  lng: number;
  precise: boolean;
  routeTimes: (number | null)[] | null;
}) {
  const [hidden, setHidden] = useState(false);
  const campus = nearestCampus(routeTimes);
  const minutes = routeTimes?.[campus];

  if (hidden) {
    return (
      <button
        type="button"
        onClick={() => setHidden(false)}
        className="mt-4 rounded-full bg-white px-4 py-2 text-sm font-semibold text-primary shadow-lg ring-1 ring-line hover:bg-tint sm:fixed sm:bottom-5 sm:right-5 sm:z-40 sm:mt-0"
      >
        🗺 Bản đồ
      </button>
    );
  }

  return (
    <div className="mt-5 flex flex-col items-center gap-1.5 sm:fixed sm:bottom-5 sm:right-5 sm:z-40 sm:mt-0">
      <div className="relative h-40 w-40 overflow-hidden rounded-full border-4 border-white shadow-xl ring-1 ring-black/10 sm:h-44 sm:w-44">
        <MiniMapCanvas lat={lat} lng={lng} campus={campus} precise={precise} />
        <Link
          href={`/map?radius=5000&focus=${id}&campus=${campus}`}
          className="absolute inset-0 z-10 rounded-full transition hover:bg-white/10"
          aria-label="Mở bản đồ lớn và chỉ đường tới trường"
          title="Mở bản đồ lớn và chỉ đường tới trường"
        />
        <button
          type="button"
          onClick={() => setHidden(true)}
          className="absolute right-[18%] top-[6%] z-20 flex h-6 w-6 items-center justify-center rounded-full bg-white/95 text-sm text-ink-muted shadow hover:text-ink"
          aria-label="Ẩn bản đồ nhỏ"
        >
          ×
        </button>
      </div>
      <div className="rounded-lg bg-white/95 px-2.5 py-1 text-center text-[11.5px] leading-tight text-ink-soft shadow">
        {minutes != null && (
          <span className="block font-semibold text-ink">
            {minutesToCampusText(minutes, CAMPUS_MARKER_LABELS[campus].replace("CTU ", ""))}
          </span>
        )}
        {!precise && <span className="block text-ink-faint">vị trí tương đối</span>}
        <span className="block text-[10px] text-ink-faint">© OpenStreetMap · OpenFreeMap</span>
      </div>
    </div>
  );
}

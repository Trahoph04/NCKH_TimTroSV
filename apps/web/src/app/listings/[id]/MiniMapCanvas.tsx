"use client";

import { Map as MapGL, Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { CAMPUSES, CAMPUS_MARKER_LABELS } from "@/lib/campus";

// Bản đồ nhỏ KHÔNG tương tác (chỉ để nhìn vị trí tin so với trường); bấm vào thì mở /map — xem MiniMap.tsx.
export default function MiniMapCanvas({
  lat,
  lng,
  campus,
  precise,
}: {
  lat: number;
  lng: number;
  campus: number;
  precise: boolean;
}) {
  const [cLat, cLng] = CAMPUSES[campus];
  return (
    <MapGL
      mapStyle="https://tiles.openfreemap.org/styles/liberty"
      initialViewState={{
        // khung vừa đủ tin + khu CTU gần nhất ⇒ thấy ngay "cách trường bao xa"
        bounds: [
          [Math.min(lng, cLng), Math.min(lat, cLat)],
          [Math.max(lng, cLng), Math.max(lat, cLat)],
        ],
        fitBoundsOptions: { padding: 34, maxZoom: 16 },
      }}
      interactive={false}
      attributionControl={false}
      style={{ width: "100%", height: "100%" }}
    >
      <Marker latitude={cLat} longitude={cLng} anchor="center">
        <span
          className="block h-[14px] w-[14px] border-2 border-white bg-navy shadow"
          title={CAMPUS_MARKER_LABELS[campus]}
        />
      </Marker>
      <Marker latitude={lat} longitude={lng} anchor="center">
        <span
          className={`block h-[16px] w-[16px] rounded-full border-[3px] shadow-[0_2px_6px_rgba(0,0,0,.35)] ${
            precise ? "border-white bg-[#1069bd]" : "border-[#64748b] bg-white"
          }`}
        />
      </Marker>
    </MapGL>
  );
}

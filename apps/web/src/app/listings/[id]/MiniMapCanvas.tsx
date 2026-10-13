"use client";

import { Map as MapGL, Marker } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { CAMPUSES, CAMPUS_MARKER_LABELS } from "@/lib/campus";
import { MapBadge } from "@/lib/map-icons";

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
      {/* cùng icon với bản đồ lớn (lib/map-icons.tsx), thu nhỏ cho khung tròn */}
      <Marker latitude={cLat} longitude={cLng} anchor="center">
        <MapBadge
          badge="campus"
          glyph="campus"
          size={22}
          title={CAMPUS_MARKER_LABELS[campus]}
          className="block drop-shadow-[0_1px_3px_rgba(0,0,0,.3)]"
        />
      </Marker>
      <Marker latitude={lat} longitude={lng} anchor="center">
        <MapBadge
          badge={precise ? "precise" : "approx"}
          glyph="house"
          size={24}
          className="block drop-shadow-[0_2px_4px_rgba(0,0,0,.3)]"
        />
      </Marker>
    </MapGL>
  );
}

"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Layer,
  Map as MapGL,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type MapLayerMouseEvent,
  type MapRef,
} from "react-map-gl/maplibre";
import type { GeoJSONSource } from "maplibre-gl";
import type { Feature, FeatureCollection, LineString, Point } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import type { PoiOut } from "@/lib/api";
import { CAMPUSES, CAMPUS_MARKER_LABELS } from "@/lib/campus";
import { isLocationPrecise } from "@/lib/format";
import { formatMeters, POI_CATEGORIES, POI_COLOR } from "@/lib/pois";
import type { ListingWithCoords } from "./MapScreen";

// Vector tile miễn phí, không key (ADR-019). Style tự mang attribution OpenFreeMap/OpenMapTiles/OSM
// — giữ nguyên control attribution mặc định (bắt buộc theo giấy phép ODbL).
const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const MAX_ZOOM = 18;


// Màu chấm theo risk_level — hôm nay mọi tin 'unknown' (xanh như mockup 03); khi module rủi ro của
// nhóm ghi risk_score, bản đồ tự đổi màu mà không phải sửa lại file này.
const RISK_COLOR = [
  "match",
  ["get", "risk"],
  "suspicious",
  "#dc2626",
  "caution",
  "#d97706",
  "safe",
  "#16a34a",
  "#1069bd",
] as const;

// Vòng bán kính tìm kiếm: đa giác 64 đỉnh xấp xỉ trên mặt phẳng địa phương (sai số < 0,5% ở 5 km).
function circleLine(lat: number, lng: number, radiusM: number): Feature<LineString> {
  const dLat = radiusM / 111_320;
  const dLng = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180));
  const coordinates = Array.from({ length: 65 }, (_, i) => {
    const t = (2 * Math.PI * i) / 64;
    return [lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)];
  });
  return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } };
}

export default function MapCanvas({
  items,
  campus,
  radius,
  selected,
  route,
  pois,
  hiddenPoiCats,
  onSelect,
  onPickGroup,
}: {
  items: ListingWithCoords[];
  campus: number;
  radius: number;
  selected: ListingWithCoords | null;
  route: [number, number][] | null;
  pois: PoiOut[];
  hiddenPoiCats: string[];
  onSelect: (listing: ListingWithCoords) => void;
  onPickGroup: (ids: number[]) => void;
}) {
  const mapRef = useRef<MapRef>(null);
  const [cursor, setCursor] = useState<string>("");
  const [poiPopup, setPoiPopup] = useState<PoiOut | null>(null);
  const center = CAMPUSES[1]; // tâm tìm kiếm cố định = khu II, khớp map/page.tsx

  const byId = useMemo(() => new Map(items.map((l) => [l.id, l])), [items]);

  // Hai lớp riêng: tin vị trí chính xác (chấm đặc, cụm xanh) nằm TRÊN tin cấp phường (chấm rỗng, cụm xám) — nếu gộp
  // chung 1 source, vài tin chính xác gần điểm mặc định của phường sẽ bị nuốt vào cụm hàng trăm tin.
  const [preciseGeo, approxGeo] = useMemo(() => {
    const toFc = (ls: ListingWithCoords[]): FeatureCollection<Point> => ({
      type: "FeatureCollection",
      features: ls.map((l) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [l.lng, l.lat] },
        properties: { id: l.id, risk: l.risk_level },
      })),
    });
    return [toFc(items.filter(isLocationPrecise)), toFc(items.filter((l) => !isLocationPrecise(l)))];
  }, [items]);

  const poisGeo = useMemo<FeatureCollection<Point>>(
    () => ({
      type: "FeatureCollection",
      features: pois
        .filter((p) => !hiddenPoiCats.includes(p.category))
        .map((p) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [p.lng, p.lat] },
          properties: { id: p.id, category: p.category },
        })),
    }),
    [pois, hiddenPoiCats],
  );
  const poiById = useMemo(() => new Map(pois.map((p) => [p.id, p])), [pois]);

  const radiusGeo = useMemo(() => circleLine(center[0], center[1], radius), [center, radius]);

  const routeGeo = useMemo<Feature<LineString> | null>(
    () =>
      route
        ? {
            type: "Feature",
            properties: {},
            // API trả [lat, lng]; GeoJSON cần [lng, lat]
            geometry: { type: "LineString", coordinates: route.map(([lat, lng]) => [lng, lat]) },
          }
        : null,
    [route],
  );

  // Chọn tin từ danh sách bên trái → bay tới vị trí tin.
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !selected) return;
    map.flyTo({ center: [selected.lng, selected.lat], zoom: Math.max(map.getZoom(), 15), duration: 600 });
  }, [selected]);

  // POI của tin cũ không còn liên quan khi đổi tin
  useEffect(() => setPoiPopup(null), [selected?.id]);

  async function handleClick(e: MapLayerMouseEvent) {
    const feature = e.features?.[0];
    const map = mapRef.current?.getMap();
    if (!feature || !map) return;
    const props = feature.properties ?? {};

    if (feature.layer.id === "clusters-precise" || feature.layer.id === "clusters-approx") {
      const source = map.getSource(
        feature.layer.id === "clusters-precise" ? "listings-precise" : "listings-approx",
      ) as GeoJSONSource;
      const clusterId = props.cluster_id as number;
      const [lng, lat] = (feature.geometry as Point).coordinates;
      const zoom = await source.getClusterExpansionZoom(clusterId);
      if (zoom <= MAX_ZOOM && zoom > map.getZoom() + 0.01) {
        map.easeTo({ center: [lng, lat], zoom });
        return;
      }
      // Không tách được nữa: các tin chung 1 toạ độ (điểm mặc định của phường) → đưa ra sidebar.
      const leaves = await source.getClusterLeaves(clusterId, 1000, 0);
      onPickGroup(leaves.map((f) => f.properties?.id as number));
      return;
    }
    if (feature.layer.id === "points-precise" || feature.layer.id === "points-approx") {
      const listing = byId.get(props.id as number);
      if (listing) onSelect(listing);
      return;
    }
    if (feature.layer.id === "poi-points") {
      setPoiPopup(poiById.get(props.id as number) ?? null);
    }
  }

  const campusPos = CAMPUSES[campus];

  return (
    <MapGL
      ref={mapRef}
      mapStyle={MAP_STYLE}
      initialViewState={{ latitude: center[0], longitude: center[1], zoom: 13.3 }}
      maxZoom={MAX_ZOOM}
      style={{ width: "100%", height: "100%" }}
      interactiveLayerIds={["clusters-precise", "points-precise", "clusters-approx", "points-approx", "poi-points"]}
      cursor={cursor}
      onMouseEnter={() => setCursor("pointer")}
      onMouseLeave={() => setCursor("")}
      onClick={handleClick}
    >
      <NavigationControl position="bottom-right" showCompass={false} />

      {/* Vòng bán kính tìm kiếm — nét đứt xanh theo mockup */}
      <Source id="radius" type="geojson" data={radiusGeo}>
        <Layer
          id="radius-line"
          type="line"
          paint={{ "line-color": "#1069bd", "line-opacity": 0.5, "line-width": 2, "line-dasharray": [3, 3] }}
        />
      </Source>

      {routeGeo && (
        <Source id="route" type="geojson" data={routeGeo}>
          <Layer
            id="route-casing"
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{ "line-color": "#ffffff", "line-width": 8 }}
          />
          <Layer
            id="route-line"
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{ "line-color": "#1069bd", "line-width": 4.5 }}
          />
        </Source>
      )}

      <Source id="pois" type="geojson" data={poisGeo}>
        <Layer
          id="poi-points"
          type="circle"
          paint={{
            "circle-radius": 6,
            "circle-color": [
              "match",
              ["get", "category"],
              ...POI_CATEGORIES.flatMap((c) => [c.key, c.color]),
              "#64748b",
            ] as never,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#ffffff",
          }}
        />
      </Source>

      {/* Cluster của MapLibre (thay react-leaflet-cluster). clusterMaxZoom = MAX_ZOOM để các tin
          chung 1 toạ độ luôn hiện thành bong bóng có số, không đè khít lên nhau ở zoom cao nhất.
          Lớp cấp phường vẽ trước (nằm dưới), lớp chính xác vẽ sau (nằm trên). */}
      <Source
        id="listings-approx"
        type="geojson"
        data={approxGeo}
        cluster
        clusterRadius={45}
        clusterMaxZoom={MAX_ZOOM}
        maxzoom={MAX_ZOOM + 2}
      >
        <Layer
          id="clusters-approx"
          type="circle"
          filter={["has", "point_count"]}
          paint={{
            "circle-color": "rgba(100,116,139,0.85)",
            "circle-radius": ["step", ["get", "point_count"], 15, 10, 18, 100, 22],
            "circle-stroke-width": 3,
            "circle-stroke-color": "rgba(255,255,255,0.85)",
          }}
        />
        <Layer
          id="cluster-count-approx"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Noto Sans Bold"],
            "text-size": 12,
            "text-allow-overlap": true,
          }}
          paint={{ "text-color": "#ffffff" }}
        />
        <Layer
          id="points-approx"
          type="circle"
          filter={["!", ["has", "point_count"]]}
          paint={{
            "circle-radius": 6,
            "circle-color": "#ffffff",
            "circle-stroke-width": 2.5,
            "circle-stroke-color": "#64748b",
          }}
        />
      </Source>

      <Source
        id="listings-precise"
        type="geojson"
        data={preciseGeo}
        cluster
        clusterRadius={30}
        clusterMaxZoom={MAX_ZOOM}
        maxzoom={MAX_ZOOM + 2}
      >
        <Layer
          id="clusters-precise"
          type="circle"
          filter={["has", "point_count"]}
          paint={{
            "circle-color": "rgba(16,105,189,0.95)",
            "circle-radius": ["step", ["get", "point_count"], 14, 10, 18],
            "circle-stroke-width": 3,
            "circle-stroke-color": "#ffffff",
          }}
        />
        <Layer
          id="cluster-count-precise"
          type="symbol"
          filter={["has", "point_count"]}
          layout={{
            "text-field": ["get", "point_count_abbreviated"],
            "text-font": ["Noto Sans Bold"],
            "text-size": 12,
            "text-allow-overlap": true,
          }}
          paint={{ "text-color": "#ffffff" }}
        />
        <Layer
          id="points-precise"
          type="circle"
          filter={["!", ["has", "point_count"]]}
          paint={{
            "circle-radius": 7.5,
            "circle-color": RISK_COLOR as never,
            "circle-stroke-width": 3,
            "circle-stroke-color": "#ffffff",
          }}
        />
      </Source>

      {/* Campus: ô vuông navy + nhãn bên dưới (mockup 03); anchor top + offset để TÂM ô vuông
          trùng toạ độ dù nhãn rộng hơn ô. */}
      <Marker latitude={campusPos[0]} longitude={campusPos[1]} anchor="top" offset={[0, -11]}>
        <div className="flex flex-col items-center gap-[5px]">
          <span className="block h-[22px] w-[22px] border-[3px] border-white bg-navy shadow-[0_3px_8px_rgba(0,0,0,.3)]" />
          <span className="whitespace-nowrap rounded-[7px] bg-white/90 px-2 py-[3px] text-[12.5px] font-bold text-navy">
            {CAMPUS_MARKER_LABELS[campus]}
          </span>
        </div>
      </Marker>

      {/* Tin đang chọn: marker HTML riêng để vẫn thấy khi tin nằm trong cluster */}
      {selected && (
        <Marker latitude={selected.lat} longitude={selected.lng} anchor="center">
          <span className="block h-[22px] w-[22px] rounded-full border-[3px] border-white bg-navy shadow-[0_2px_8px_rgba(0,0,0,.35)]" />
        </Marker>
      )}

      {poiPopup && (
        <Popup
          latitude={poiPopup.lat}
          longitude={poiPopup.lng}
          anchor="bottom"
          offset={10}
          closeButton={false}
          onClose={() => setPoiPopup(null)}
        >
          <div className="text-[13px] leading-snug">
            <p className="font-semibold text-ink">{poiPopup.name ?? "Chưa có tên trên OSM"}</p>
            <p className="text-ink-muted">
              <span style={{ color: POI_COLOR[poiPopup.category] }}>●</span>{" "}
              {POI_CATEGORIES.find((c) => c.key === poiPopup.category)?.label} ·{" "}
              {formatMeters(poiPopup.distance_m)} chim bay
            </p>
          </div>
        </Popup>
      )}
    </MapGL>
  );
}

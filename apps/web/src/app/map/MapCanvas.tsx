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
  type MapStyleDataEvent,
} from "react-map-gl/maplibre";
import type { ExpressionSpecification, GeoJSONSource, SymbolLayerSpecification } from "maplibre-gl";
import type { Feature, FeatureCollection, LineString, Point } from "geojson";
import "maplibre-gl/dist/maplibre-gl.css";
import type { PoiOut } from "@/lib/api";
import { CAMPUSES, CAMPUS_MARKER_LABELS } from "@/lib/campus";
import { isLocationPrecise } from "@/lib/format";
import {
  CLUSTER_STYLES,
  CLUSTER_TEXT_OFFSET,
  MAP_ICON,
  MapBadge,
  POI_GLYPH,
  RISK_FILL,
  registerMapIcons,
} from "@/lib/map-icons";
import { formatMeters, POI_CATEGORIES } from "@/lib/pois";
import type { ListingWithCoords } from "./MapScreen";

// Vector tile miễn phí, không key (ADR-019). Style tự mang attribution OpenFreeMap/OpenMapTiles/OSM
// — giữ nguyên control attribution mặc định (bắt buộc theo giấy phép ODbL).
const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const MAX_ZOOM = 18;

// Icon tin vị trí chính xác theo risk_level — hôm nay mọi tin 'unknown' (xanh); khi module rủi ro của nhóm ghi
// risk_score, icon tự đổi màu (ảnh từng mức nạp sẵn trong registerMapIcons) mà không phải sửa file này.
const PRECISE_ICON = [
  "match",
  ["get", "risk"],
  ...Object.keys(RISK_FILL).flatMap((risk) => [risk, MAP_ICON.riskPrecise(risk)]),
  MAP_ICON.precise,
] as unknown as ExpressionSpecification;
// Thu nhỏ icon khi nhìn xa để vài chục tin chính xác không chồng kín bản đồ ở mức zoom mặc định (13,3)
const ICON_SIZE: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 12, 0.72, 15, 1];

// Cụm tin = nhãn "🏠 + số" (ảnh co giãn theo độ dài số, xem map-icons.tsx). Luôn hiện, không bị ẩn vì va chạm.
function clusterLayout(icon: string): SymbolLayerSpecification["layout"] {
  return {
    "icon-image": icon,
    "icon-text-fit": "width",
    "icon-text-fit-padding": [0, 3, 0, 3],
    "icon-allow-overlap": true,
    "text-allow-overlap": true,
    "text-field": ["get", "point_count_abbreviated"],
    "text-font": ["Noto Sans Bold"],
    "text-size": 12,
    "text-offset": CLUSTER_TEXT_OFFSET,
  };
}

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
          // dist: tiện ích gần tin hơn được đặt trước khi icon va nhau (symbol-sort-key)
          properties: { id: p.id, category: p.category, dist: p.distance_m },
        })),
    }),
    [pois, hiddenPoiCats],
  );
  const poiById = useMemo(() => new Map(pois.map((p) => [p.id, p])), [pois]);

  const radiusGeo = useMemo(() => circleLine(center[0], center[1], radius), [center, radius]);

  // Source đường đi luôn có mặt (rỗng khi chưa chọn tin) để lớp đường giữ đúng thứ tự: nằm DƯỚI icon tiện ích/tin.
  // Mount có điều kiện thì lớp được thêm sau cùng ⇒ đè lên icon.
  const routeGeo = useMemo<FeatureCollection<LineString>>(
    () => ({
      type: "FeatureCollection",
      features: route
        ? [
            {
              type: "Feature",
              properties: {},
              // API trả [lat, lng]; GeoJSON cần [lng, lat]
              geometry: { type: "LineString", coordinates: route.map(([lat, lng]) => [lng, lat]) },
            },
          ]
        : [],
    }),
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

  // Icon phải có trong style TRƯỚC khi lớp symbol được dựng: styledata đầu tiên bắn ngay khi style nạp xong, trước
  // lượt render mà react-map-gl gọi addLayer. styleimagemissing là lưới an toàn nếu thứ tự đó đổi ở bản sau.
  const iconsHooked = useRef(false);
  function handleStyleData(e: MapStyleDataEvent) {
    const map = e.target;
    registerMapIcons(map);
    if (!iconsHooked.current) {
      iconsHooked.current = true;
      map.on("styleimagemissing", (ev: { id: string }) => {
        if (ev.id.startsWith("tro-")) registerMapIcons(map);
      });
    }
  }

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
      onStyleData={handleStyleData}
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

      {/* Tiện ích: icon theo nhóm. Không cho chồng nhau — hàng trăm tiện ích trong 1 km sẽ phủ kín bản đồ; cái gần
          tin nhất được đặt trước, phóng to thì hiện thêm (số đếm đầy đủ nằm ở card bên trái). */}
      <Source id="pois" type="geojson" data={poisGeo}>
        <Layer
          id="poi-points"
          type="symbol"
          layout={{
            "icon-image": ["concat", "tro-poi-", ["get", "category"]],
            "icon-size": ICON_SIZE,
            "icon-padding": 1,
            "symbol-sort-key": ["get", "dist"],
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
          type="symbol"
          filter={["has", "point_count"]}
          layout={clusterLayout(MAP_ICON.clusterApprox)}
          paint={{ "text-color": CLUSTER_STYLES.approx.text }}
        />
        <Layer
          id="points-approx"
          type="symbol"
          filter={["!", ["has", "point_count"]]}
          layout={{
            "icon-image": MAP_ICON.approx,
            "icon-size": ICON_SIZE,
            // tin luôn hiện (không bị ẩn vì va chạm) và vẫn chiếm chỗ ⇒ tiện ích/nhãn đường tự né
            "icon-allow-overlap": true,
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
          type="symbol"
          filter={["has", "point_count"]}
          layout={clusterLayout(MAP_ICON.clusterPrecise)}
          paint={{ "text-color": CLUSTER_STYLES.precise.text }}
        />
        <Layer
          id="points-precise"
          type="symbol"
          filter={["!", ["has", "point_count"]]}
          layout={{
            "icon-image": PRECISE_ICON,
            "icon-size": ICON_SIZE,
            "icon-allow-overlap": true,
          }}
        />
      </Source>

      {/* Campus: ô vuông navy có mũ tốt nghiệp + nhãn bên dưới (mockup 03); anchor top + offset để TÂM ô vuông
          trùng toạ độ dù nhãn rộng hơn ô. */}
      <Marker latitude={campusPos[0]} longitude={campusPos[1]} anchor="top" offset={[0, -14]}>
        <div className="flex flex-col items-center gap-1">
          <MapBadge badge="campus" glyph="campus" className="drop-shadow-[0_2px_4px_rgba(0,0,0,.3)]" />
          <span className="whitespace-nowrap rounded-[7px] bg-white/90 px-2 py-[3px] text-[12.5px] font-bold text-navy">
            {CAMPUS_MARKER_LABELS[campus]}
          </span>
        </div>
      </Marker>

      {/* Tin đang chọn: marker HTML riêng (to hơn, có quầng) để vẫn thấy khi tin nằm trong cluster */}
      {selected && (
        <Marker latitude={selected.lat} longitude={selected.lng} anchor="center">
          <span className="block rounded-full shadow-[0_0_0_5px_rgba(6,48,92,.22),0_3px_8px_rgba(0,0,0,.35)]">
            <MapBadge badge="selected" glyph="house" className="block" />
          </span>
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
            <p className="mt-0.5 flex items-center gap-1.5 text-ink-muted">
              {POI_GLYPH[poiPopup.category] && (
                <MapBadge badge="poi" glyph={POI_GLYPH[poiPopup.category]} size={18} className="shrink-0" />
              )}
              <span>
                {POI_CATEGORIES.find((c) => c.key === poiPopup.category)?.label} ·{" "}
                {formatMeters(poiPopup.distance_m)} chim bay
              </span>
            </p>
          </div>
        </Popup>
      )}
    </MapGL>
  );
}

import type { Map as MaplibreMap } from "maplibre-gl";

// Icon bản đồ: glyph nét đơn trên lưới 24×24, MỘT màu, không chi tiết thừa — để đọc được ở cỡ 14–16 px.
// Cùng một bộ path vẽ ra 2 nơi: canvas → map.addImage (lớp symbol MapLibre, hàng trăm điểm mà không cần marker
// HTML) và <svg> (chú giải, danh sách tiện ích, marker HTML) ⇒ icon trên bản đồ và trong chú giải luôn khớp nhau.
export type GlyphName = "house" | "market" | "store" | "atm" | "pharmacy" | "hospital" | "bus" | "campus";

export const GLYPHS: Record<GlyphName, string[]> = {
  // nhà trọ: mái + tường + cửa
  house: ["M3.5 11.5 12 4.5l8.5 7", "M6 10v9.5h12V10", "M10.25 19.5v-5h3.5v5"],
  // chợ: sạp có mái bạt răng cưa
  market: [
    "M4 9.5 5.5 5h13L20 9.5",
    "M4 9.5a2 2 0 0 0 4 0a2 2 0 0 0 4 0a2 2 0 0 0 4 0a2 2 0 0 0 4 0",
    "M6 12.5v7M18 12.5v7M4 19.5h16",
  ],
  // siêu thị, cửa hàng tiện lợi: xe đẩy
  store: [
    "M3 4.5h2.5L8 15.5h10l2-7.5H6.6",
    "M8.25 19.5a1.25 1.25 0 1 0 2.5 0a1.25 1.25 0 1 0-2.5 0",
    "M15.25 19.5a1.25 1.25 0 1 0 2.5 0a1.25 1.25 0 1 0-2.5 0",
  ],
  // ATM, ngân hàng: tờ tiền
  atm: [
    "M5 7h14a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 19 17H5a1.5 1.5 0 0 1-1.5-1.5v-7A1.5 1.5 0 0 1 5 7z",
    "M9.75 12a2.25 2.25 0 1 0 4.5 0a2.25 2.25 0 1 0-4.5 0",
    "M6.75 12h.01M17.25 12h.01",
  ],
  // nhà thuốc: viên thuốc con nhộng (khác dấu cộng của bệnh viện)
  pharmacy: [
    "M10.23 18.71 18.71 10.23A3.5 3.5 0 0 0 13.77 5.29L5.29 13.77a3.5 3.5 0 0 0 4.94 4.94z",
    "M9.53 9.53l4.94 4.94",
  ],
  // bệnh viện, phòng khám: chữ thập
  hospital: ["M9.5 4.5h5v5h5v5h-5v5h-5v-5h-5v-5h5z"],
  // trạm xe buýt: đầu xe buýt
  bus: [
    "M6.5 3.5h11a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2v-11a2 2 0 0 1 2-2z",
    "M4.5 11h15",
    "M7.5 18.5v2M16.5 18.5v2",
    "M8 15h.01M16 15h.01",
  ],
  // khu CTU: mũ tốt nghiệp
  campus: [
    "M12 4.5 2.5 9.5l9.5 5 9.5-5z",
    "M6.5 11.8V16c0 1.5 2.5 2.8 5.5 2.8s5.5-1.3 5.5-2.8v-4.2",
    "M21.5 9.5v5",
  ],
};

// Nhóm tiện ích (key khớp apps/api/app/pois/categories.py) → glyph
export const POI_GLYPH: Record<string, GlyphName> = {
  cho: "market",
  sieu_thi: "store",
  atm: "atm",
  nha_thuoc: "pharmacy",
  y_te: "hospital",
  xe_buyt: "bus",
};

type Shape = "circle" | "square";
type BadgeStyle = {
  shape: Shape;
  size: number; // đường kính / cạnh, CSS px
  fill: string;
  ring: string;
  ringWidth: number;
  glyph: string;
  glyphSize: number;
};

// Màu tiết chế: mọi tin trọ (chấm lẻ lẫn cụm) cùng họ xanh của trang — xanh ĐẬM đặc = vị trí chính xác, xanh NHẠT viền
// xanh = cấp phường (trước 12/10 lớp cấp phường màu xám, ~88% bản đồ trông như "tắt"); tiện ích = ô vuông trắng nét xám
// (hình dạng khác hẳn tin trọ, không cần màu riêng từng nhóm); khu trường = navy.
const LISTING_BLUE = "#1069bd";
const APPROX_FILL = "#e3effb";
const POI_INK = "#3d5871";
const NAVY = "#06305c";

export const BADGES = {
  precise: { shape: "circle", size: 28, fill: LISTING_BLUE, ring: "#ffffff", ringWidth: 2, glyph: "#ffffff", glyphSize: 16 },
  approx: { shape: "circle", size: 24, fill: APPROX_FILL, ring: LISTING_BLUE, ringWidth: 2, glyph: LISTING_BLUE, glyphSize: 14 },
  poi: { shape: "square", size: 22, fill: "#ffffff", ring: "#b4c1cf", ringWidth: 1, glyph: POI_INK, glyphSize: 14 },
  campus: { shape: "square", size: 28, fill: NAVY, ring: "#ffffff", ringWidth: 2, glyph: "#ffffff", glyphSize: 18 },
  selected: { shape: "circle", size: 34, fill: NAVY, ring: "#ffffff", ringWidth: 3, glyph: "#ffffff", glyphSize: 19 },
} satisfies Record<string, BadgeStyle>;
export type BadgeName = keyof typeof BADGES;

// Màu theo risk_level — mọi tin hiện là 'unknown' (xanh); nếu nhánh rủi ro của nhóm ghi risk_score thì bản đồ tự đổi
// màu icon mà không phải sửa MapCanvas.
export const RISK_FILL: Record<string, string> = { suspicious: "#dc2626", caution: "#d97706", safe: "#16a34a" };

// ---- Canvas → MapLibre ----

const SHADOW_PAD = 3; // chừa chỗ cho bóng đổ quanh icon

function drawBadge(style: BadgeStyle, glyph: GlyphName, ratio: number): ImageData | null {
  const box = style.size + SHADOW_PAD * 2;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = Math.round(box * ratio);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(ratio, ratio);

  const c = box / 2;
  const half = style.size / 2 - style.ringWidth / 2;
  const outline = new Path2D();
  if (style.shape === "circle") {
    outline.arc(c, c, half, 0, Math.PI * 2);
  } else {
    // arcTo thay Path2D.roundRect — roundRect chỉ có từ Safari 16
    const r = style.size * 0.26;
    const [x0, y0, x1, y1] = [c - half, c - half, c + half, c + half];
    outline.moveTo(x0 + r, y0);
    outline.arcTo(x1, y0, x1, y1, r);
    outline.arcTo(x1, y1, x0, y1, r);
    outline.arcTo(x0, y1, x0, y0, r);
    outline.arcTo(x0, y0, x1, y0, r);
    outline.closePath();
  }

  ctx.save();
  ctx.shadowColor = "rgba(15, 23, 42, 0.28)";
  ctx.shadowBlur = 3;
  ctx.shadowOffsetY = 1;
  ctx.fillStyle = style.fill;
  ctx.fill(outline);
  ctx.restore();

  ctx.lineWidth = style.ringWidth;
  ctx.strokeStyle = style.ring;
  ctx.stroke(outline);

  const k = style.glyphSize / 24;
  ctx.save();
  ctx.translate(c - style.glyphSize / 2, c - style.glyphSize / 2);
  ctx.scale(k, k);
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = style.glyph;
  for (const d of GLYPHS[glyph]) ctx.stroke(new Path2D(d));
  ctx.restore();

  return ctx.getImageData(0, 0, canvas.width, canvas.height);
}

// ---- Nhãn cụm "🏠 268" ----
// Ảnh co giãn (stretchX + content) dùng với icon-text-fit "width": phần icon nhà bên trái giữ nguyên, phần nền bên phải
// giãn theo độ dài số. Một ảnh cho mọi cụm thay vì vẽ sẵn từng số.
const CLUSTER = { height: 28, width: 54, glyphSize: 15, contentLeft: 27, contentRight: 12, ringWidth: 2 };
export const CLUSTER_STYLES = {
  precise: { fill: LISTING_BLUE, ring: "#ffffff", glyph: "#ffffff", text: "#ffffff" },
  approx: { fill: APPROX_FILL, ring: LISTING_BLUE, glyph: LISTING_BLUE, text: "#0b4d8f" },
};

function drawClusterPill(style: (typeof CLUSTER_STYLES)["precise"], ratio: number) {
  const { height: h, width: w, glyphSize: g, contentLeft, contentRight, ringWidth } = CLUSTER;
  const pad = SHADOW_PAD;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round((w + pad * 2) * ratio);
  canvas.height = Math.round((h + pad * 2) * ratio);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(ratio, ratio);

  const x0 = pad + ringWidth / 2, y0 = pad + ringWidth / 2;
  const x1 = pad + w - ringWidth / 2, y1 = pad + h - ringWidth / 2;
  const r = (y1 - y0) / 2;
  const pill = new Path2D();
  pill.moveTo(x0 + r, y0);
  pill.lineTo(x1 - r, y0);
  pill.arc(x1 - r, y0 + r, r, -Math.PI / 2, Math.PI / 2);
  pill.lineTo(x0 + r, y1);
  pill.arc(x0 + r, y0 + r, r, Math.PI / 2, (Math.PI * 3) / 2);
  pill.closePath();

  ctx.save();
  ctx.shadowColor = "rgba(15, 23, 42, 0.28)";
  ctx.shadowBlur = 3;
  ctx.shadowOffsetY = 1;
  ctx.fillStyle = style.fill;
  ctx.fill(pill);
  ctx.restore();
  ctx.lineWidth = ringWidth;
  ctx.strokeStyle = style.ring;
  ctx.stroke(pill);

  const k = g / 24;
  ctx.save();
  ctx.translate(pad + 7, pad + (h - g) / 2);
  ctx.scale(k, k);
  ctx.lineWidth = 2.2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = style.glyph;
  for (const d of GLYPHS.house) ctx.stroke(new Path2D(d));
  ctx.restore();

  const px = (v: number) => Math.round(v * ratio);
  const contentX1 = pad + contentLeft, contentX2 = pad + w - contentRight;
  return {
    image: ctx.getImageData(0, 0, canvas.width, canvas.height),
    options: {
      pixelRatio: ratio,
      // chỉ giãn đoạn nền phẳng ở giữa vùng chữ — không giãn qua icon nhà hay hai đầu bo tròn
      stretchX: [[px(contentX1 + 2), px(contentX2 - 2)]] as [number, number][],
      // content phủ HẾT chiều cao: với icon-text-fit "width", chiều không fit được map vùng content vào chiều cao icon —
      // content thấp hơn ảnh thì cả nhãn bị kéo dọc (icon nhà méo)
      content: [px(contentX1), 0, px(contentX2), canvas.height] as [number, number, number, number],
    },
  };
}

// Phần trái (icon nhà) dài hơn phần phải ⇒ dời chữ sang phải nửa chênh lệch để cả nhãn nằm giữa toạ độ cụm (em, cỡ chữ 12)
export const CLUSTER_TEXT_OFFSET: [number, number] = [
  (CLUSTER.contentLeft - CLUSTER.contentRight) / 2 / 12,
  0,
];

/** Tên ảnh trong style — tiền tố riêng để không đụng sprite của style OpenFreeMap. */
export const MAP_ICON = {
  precise: "tro-house-precise",
  approx: "tro-house-approx",
  clusterPrecise: "tro-cluster-precise",
  clusterApprox: "tro-cluster-approx",
  poi: (category: string) => `tro-poi-${category}`,
  riskPrecise: (risk: string) => `tro-house-precise-${risk}`,
};

function iconSpecs(): [string, BadgeStyle, GlyphName][] {
  const specs: [string, BadgeStyle, GlyphName][] = [
    [MAP_ICON.precise, BADGES.precise, "house"],
    [MAP_ICON.approx, BADGES.approx, "house"],
  ];
  for (const [risk, fill] of Object.entries(RISK_FILL)) {
    specs.push([MAP_ICON.riskPrecise(risk), { ...BADGES.precise, fill }, "house"]);
  }
  for (const [category, glyph] of Object.entries(POI_GLYPH)) {
    specs.push([MAP_ICON.poi(category), BADGES.poi, glyph]);
  }
  return specs;
}

/**
 * Nạp icon vào style. Gọi được nhiều lần (bỏ qua ảnh đã có). Phải chạy TRƯỚC khi lớp symbol cần ảnh được dựng —
 * MapCanvas gọi ở sự kiện styledata đầu tiên, kèm listener styleimagemissing làm lưới an toàn.
 */
export function registerMapIcons(map: MaplibreMap): void {
  // tối thiểu 2x để nét 1–2 px không nhoè trên màn thường
  const ratio = Math.min(3, Math.max(2, Math.ceil(window.devicePixelRatio || 1)));
  for (const [id, style, glyph] of iconSpecs()) {
    if (map.hasImage(id)) continue;
    const image = drawBadge(style, glyph, ratio);
    if (image) map.addImage(id, image, { pixelRatio: ratio });
  }
  for (const [id, style] of [
    [MAP_ICON.clusterPrecise, CLUSTER_STYLES.precise],
    [MAP_ICON.clusterApprox, CLUSTER_STYLES.approx],
  ] as const) {
    if (map.hasImage(id)) continue;
    const pill = drawClusterPill(style, ratio);
    if (pill) map.addImage(id, pill.image, pill.options);
  }
}

// ---- SVG cho HTML (chú giải, danh sách, marker) ----

export function MapBadge({
  badge,
  glyph,
  size,
  className,
  title,
}: {
  badge: BadgeName;
  glyph: GlyphName;
  size?: number;
  className?: string;
  title?: string;
}) {
  const style: BadgeStyle = BADGES[badge];
  const px = size ?? style.size;
  // vẽ trong hệ toạ độ = cỡ thật của badge rồi để <svg> co giãn ⇒ tỉ lệ nét viền/glyph giống hệt bản canvas
  const s = style.size;
  const half = s / 2 - style.ringWidth / 2;
  const k = style.glyphSize / 24;
  const offset = (s - style.glyphSize) / 2;
  return (
    <svg
      width={px}
      height={px}
      viewBox={`0 0 ${s} ${s}`}
      className={className}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      {style.shape === "circle" ? (
        <circle cx={s / 2} cy={s / 2} r={half} fill={style.fill} stroke={style.ring} strokeWidth={style.ringWidth} />
      ) : (
        <rect
          x={s / 2 - half}
          y={s / 2 - half}
          width={half * 2}
          height={half * 2}
          rx={s * 0.26}
          fill={style.fill}
          stroke={style.ring}
          strokeWidth={style.ringWidth}
        />
      )}
      <g
        transform={`translate(${offset} ${offset}) scale(${k})`}
        fill="none"
        stroke={style.glyph}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {GLYPHS[glyph].map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
    </svg>
  );
}

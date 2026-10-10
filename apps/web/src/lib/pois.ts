// Nhóm tiện ích — key khớp apps/api/app/pois/categories.py (đổi nhóm thì đổi cả hai nơi).
// Màu chọn để phân biệt với chấm tin trọ (xanh dương) và màu rủi ro đỏ/vàng/xanh lá trên marker.
export const POI_CATEGORIES: { key: string; label: string; color: string }[] = [
  { key: "cho", label: "Chợ", color: "#c2410c" },
  { key: "sieu_thi", label: "Siêu thị, tiện lợi", color: "#0f766e" },
  { key: "atm", label: "ATM, ngân hàng", color: "#6d28d9" },
  { key: "nha_thuoc", label: "Nhà thuốc", color: "#be185d" },
  { key: "y_te", label: "Bệnh viện, phòng khám", color: "#b91c1c" },
  { key: "xe_buyt", label: "Trạm xe buýt", color: "#0369a1" },
];

export const POI_COLOR: Record<string, string> = Object.fromEntries(
  POI_CATEGORIES.map((c) => [c.key, c.color]),
);

export function formatMeters(m: number): string {
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}

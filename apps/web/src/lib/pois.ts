// Nhóm tiện ích — key khớp apps/api/app/pois/categories.py (đổi nhóm thì đổi cả hai nơi). Icon từng nhóm ở
// lib/map-icons.tsx (POI_GLYPH): phân biệt bằng hình icon, không dùng màu riêng mỗi nhóm.
export const POI_CATEGORIES: { key: string; label: string }[] = [
  { key: "cho", label: "Chợ" },
  { key: "sieu_thi", label: "Siêu thị, tiện lợi" },
  { key: "atm", label: "ATM, ngân hàng" },
  { key: "nha_thuoc", label: "Nhà thuốc" },
  { key: "y_te", label: "Bệnh viện, phòng khám" },
  { key: "xe_buyt", label: "Trạm xe buýt" },
];

export function formatMeters(m: number): string {
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}

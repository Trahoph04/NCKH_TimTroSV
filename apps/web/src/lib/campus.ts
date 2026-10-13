// Toạ độ 3 khu CTU — khớp CAMPUSES backend (apps/api/app/listings/routing.py). Index 0/1/2 = khu I/II/III,
// trùng thứ tự mảng route_time_campus.
export const CAMPUSES: [number, number][] = [
  [10.0159, 105.7656], // khu I
  [10.0322, 105.7683], // khu II
  [10.034, 105.7798], // khu III
];
export const CAMPUS_MARKER_LABELS = ["CTU khu I", "CTU khu II", "CTU khu III"];

// Khu gần nhất theo phút đi thật (route_time_campus); chưa route thì mặc định khu II
export function nearestCampus(routeTimes: (number | null)[] | null | undefined): number {
  if (!routeTimes) return 1;
  let best = 1;
  routeTimes.forEach((m, i) => {
    if (m != null && (routeTimes[best] == null || m < (routeTimes[best] as number))) best = i;
  });
  return best;
}

// Phút tới trường dạng chữ. < 1 phút gần như chỉ xảy ra khi toạ độ là tâm phường trùng khuôn viên (phường Tân An ↔
// khu II, 4 tin 12/10) — "0 phút" đọc như "nằm trong trường", nên nói "quanh khu II" cho đúng độ chính xác cấp phường.
export function minutesToCampusText(minutes: number, campusLabel: string, verb = "tới"): string {
  const m = Math.round(minutes);
  return m < 1 ? `quanh ${campusLabel}` : `${m} phút ${verb} ${campusLabel}`;
}

// Nhãn tiếng Việt cho các thang số. PHẢI khớp cực tính trong
// apps/api/app/matching/profile.py — lệch là hiển thị ngược nghĩa cho người dùng.

export const SLEEP = ["Trước 22h", "22h – 24h", "Sau 0h"];
export const CLEAN = [
  "", "Để đến khi hết chén sạch", "Để 1–2 ngày rồi rửa",
  "Rửa trong ngày", "Rửa trong ngày", "Rửa chén ngay",
];
export const NOISE = [
  "", "Rất khó chịu, phải nói ngay", "Hơi khó chịu nhưng không nói",
  "Nhắc nhẹ vặn nhỏ lại", "Khá dễ tính", "Không sao cả, vẫn ngủ được",
];
export const AC = ["Ít khi bật, quạt là đủ", "Bật lúc nóng, có tiết kiệm", "Bật gần như cả đêm"];
export const MONEY = ["", "Chia sòng phẳng từng khoản", "Chia đều cho nhanh"];
export const BUDGET = ["Dưới 1,5 triệu", "1,5 – 2 triệu", "2 – 2,5 triệu", "2,5 – 3,5 triệu", "Trên 3,5 triệu"];
export const SCENARIO = ["", "Ở một mình", "Ở ghép 2 người", "Ở ghép 3 người trở lên"];
export const PERSONA: Record<string, string> = {
  A: "Ngủ sớm dậy sớm, phòng gọn gàng, cần yên tĩnh",
  B: "Ngủ trễ dậy trễ, dễ tính, ai làm gì cũng được",
};

export const DON_VI = [
  "Trường Bách khoa",
  "Trường Công nghệ Thông tin & Truyền thông",
  "Trường Kinh tế",
  "Trường Nông nghiệp",
  "Trường Thủy sản",
  "Trường Sư phạm",
  "Khoa Ngoại ngữ",
  "Khoa Khoa học Tự nhiên",
  "Khoa Khoa học Xã hội & Nhân văn",
  "Viện Công nghệ Sinh học & Thực phẩm",
  "Khác / chưa có trong danh sách",
];

export function at(arr: string[], i: number | null | undefined): string {
  return i === null || i === undefined ? "—" : arr[i] || "—";
}

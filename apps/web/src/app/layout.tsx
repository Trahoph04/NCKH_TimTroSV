import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import "./globals.css";
import ChatbotWidget from "./tro-ly/ChatbotWidget";

const beVietnamPro = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Trọ CTU — Tìm phòng trọ gần ĐH Cần Thơ",
  description: "Hệ thống tổng hợp & gợi ý nhà trọ AI cho sinh viên ĐH Cần Thơ",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" className={beVietnamPro.variable}>
      <body className="bg-paper font-sans text-ink antialiased">
        {children}
        {/* trợ lý nổi trên mọi trang (trừ /chat) — giữ hội thoại khi chuyển trang vì nằm ngoài page */}
        <ChatbotWidget />
      </body>
    </html>
  );
}

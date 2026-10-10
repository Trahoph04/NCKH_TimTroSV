"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function DeleteListingButton({ id }: { id: number }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    // ẩn (status='hidden'), không xoá — khôi phục được bằng SQL, crawler không tự bật lại
    if (!confirm("Ẩn tin này khỏi tìm kiếm, bản đồ và gợi ý?")) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/listings/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(body.detail ?? "Ẩn tin thất bại");
        setLoading(false);
        return;
      }
      router.push("/");
      router.refresh();
    } catch {
      setError("Không thể kết nối tới máy chủ");
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={handleDelete}
        disabled={loading}
        className="rounded bg-rose-600 px-4 py-2 font-medium text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Đang xử lý..." : "Ẩn tin"}
      </button>
      {error && <p className="mt-2 text-sm text-rose-600">{error}</p>}
    </div>
  );
}

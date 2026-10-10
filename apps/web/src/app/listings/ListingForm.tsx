"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";

const DISTRICTS = [
  "Ninh Kiều",
  "Bình Thủy",
  "Cái Răng",
  "Ô Môn",
  "Thốt Nốt",
  "Phong Điền",
];

const listingSchema = z.object({
  title: z.string().min(1, "Nhập tiêu đề"),
  price: z.union([z.coerce.number().positive("Giá phải > 0"), z.literal("")]).optional(),
  area: z.union([z.coerce.number().positive("Diện tích phải > 0"), z.literal("")]).optional(),
  address: z.string().optional(),
  district: z.string().optional(),
  description: z.string().optional(),
  images: z.string().optional(),
});

type ListingFormValues = z.infer<typeof listingSchema>;

export type ListingFormInitial = {
  title?: string;
  price?: number | null;
  area?: number | null;
  address?: string | null;
  district?: string | null;
  description?: string | null;
  images?: string[] | null;
};

export default function ListingForm({
  mode,
  listingId,
  initial,
}: {
  mode: "create" | "edit";
  listingId?: number;
  initial?: ListingFormInitial;
}) {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ListingFormValues>({
    resolver: zodResolver(listingSchema),
    defaultValues: {
      title: initial?.title ?? "",
      price: initial?.price ?? undefined,
      area: initial?.area ?? undefined,
      address: initial?.address ?? "",
      district: initial?.district ?? "",
      description: initial?.description ?? "",
      images: initial?.images?.join("\n") ?? "",
    },
  });

  const onSubmit = async (data: ListingFormValues) => {
    setFormError(null);
    const images = (data.images ?? "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      title: data.title,
      price: data.price === "" || data.price == null ? null : Number(data.price),
      area: data.area === "" || data.area == null ? null : Number(data.area),
      address: data.address || null,
      district: data.district || null,
      description: data.description || null,
      images,
    };

    try {
      const url = mode === "create" ? "/api/listings" : `/api/listings/${listingId}`;
      const method = mode === "create" ? "POST" : "PUT";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const body = (await res.json()) as { id: number };
        const targetId = mode === "create" ? body.id : listingId;
        router.push(`/listings/${targetId}`);
        router.refresh();
        return;
      }

      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      setFormError(body.detail ?? "Lưu tin thất bại");
    } catch {
      setFormError("Không thể kết nối tới máy chủ");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {formError && (
        <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-600">
          {formError}
        </p>
      )}

      <div>
        <label htmlFor="title" className="block text-sm font-medium text-slate-700">
          Tiêu đề
        </label>
        <input
          id="title"
          type="text"
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
          {...register("title")}
        />
        {errors.title && (
          <p className="mt-1 text-sm text-red-600">{errors.title.message}</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="price" className="block text-sm font-medium text-slate-700">
            Giá (VND/tháng)
          </label>
          <input
            id="price"
            type="number"
            min={0}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
            {...register("price")}
          />
          {errors.price && (
            <p className="mt-1 text-sm text-red-600">{errors.price.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="area" className="block text-sm font-medium text-slate-700">
            Diện tích (m²)
          </label>
          <input
            id="area"
            type="number"
            min={0}
            step="0.1"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
            {...register("area")}
          />
          {errors.area && (
            <p className="mt-1 text-sm text-red-600">{errors.area.message}</p>
          )}
        </div>
      </div>

      <div>
        <label htmlFor="address" className="block text-sm font-medium text-slate-700">
          Địa chỉ
        </label>
        <input
          id="address"
          type="text"
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
          {...register("address")}
        />
      </div>

      <div>
        <label htmlFor="district" className="block text-sm font-medium text-slate-700">
          Quận/huyện
        </label>
        <select
          id="district"
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
          {...register("district")}
        >
          <option value="">Chọn quận/huyện</option>
          {DISTRICTS.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-medium text-slate-700">
          Mô tả
        </label>
        <textarea
          id="description"
          rows={5}
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
          {...register("description")}
        />
      </div>

      <div>
        <label htmlFor="images" className="block text-sm font-medium text-slate-700">
          Ảnh (mỗi URL một dòng)
        </label>
        <textarea
          id="images"
          rows={4}
          placeholder={"https://example.com/anh1.jpg\nhttps://example.com/anh2.jpg"}
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-slate-800 focus:border-emerald-500 focus:outline-none"
          {...register("images")}
        />
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? "Đang xử lý..." : mode === "create" ? "Thêm nhà trọ" : "Lưu thay đổi"}
      </button>
    </form>
  );
}

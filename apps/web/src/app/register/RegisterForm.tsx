"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import { authButton, authFieldError, authFormError, authInput, authLabel } from "../AuthShell";

const registerSchema = z.object({
  name: z.union([z.string().max(100), z.literal("")]).optional(),
  email: z.string().email("Email không hợp lệ"),
  password: z.string().min(8, "Mật khẩu tối thiểu 8 ký tự").max(128, "Mật khẩu tối đa 128 ký tự"),
});

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterForm() {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterFormValues) => {
    setFormError(null);
    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        router.push("/");
        router.refresh();
        return;
      }

      // 422 (vd. email đuôi .local qua được zod nhưng pydantic từ chối) có detail là mảng — render thẳng làm form sập
      const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
      setFormError(typeof body.detail === "string" ? body.detail : "Email hoặc mật khẩu không hợp lệ");
    } catch {
      setFormError("Không thể kết nối tới máy chủ");
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {formError && (
        <p className={authFormError}>
          {formError}
        </p>
      )}

      <div>
        <label htmlFor="name" className={authLabel}>
          Họ tên (tùy chọn)
        </label>
        <input
          id="name"
          type="text"
          autoComplete="name"
          className={authInput}
          {...register("name")}
        />
        {errors.name && (
          <p className={authFieldError}>{errors.name.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="email" className={authLabel}>
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className={authInput}
          {...register("email")}
        />
        {errors.email && (
          <p className={authFieldError}>{errors.email.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="password" className={authLabel}>
          Mật khẩu
        </label>
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          className={authInput}
          {...register("password")}
        />
        {errors.password && (
          <p className={authFieldError}>{errors.password.message}</p>
        )}
      </div>

      <button
        type="submit"
        disabled={isSubmitting}
        className={authButton}
      >
        {isSubmitting ? "Đang xử lý..." : "Đăng ký"}
      </button>
    </form>
  );
}

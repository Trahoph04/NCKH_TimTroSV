"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter, useSearchParams } from "next/navigation";
import { authButton, authFieldError, authFormError, authInput, authLabel } from "../AuthShell";

const emailSchema = z.object({
  email: z.string().email("Email không hợp lệ"),
  password: z.string().min(1, "Nhập mật khẩu"),
});

// Khớp CtuLoginIn phía API (4–20 ký tự) để lỗi bắt ngay ở client, không ra 422
const mssvSchema = z.object({
  mssv: z
    .string()
    .trim()
    .min(4, "MSSV không hợp lệ")
    .max(20, "MSSV không hợp lệ"),
  password: z.string().min(4, "Mã đăng nhập ít nhất 4 ký tự"),
});

type EmailValues = z.infer<typeof emailSchema>;
type MssvValues = z.infer<typeof mssvSchema>;
type Mode = "mssv" | "email";

const inputCls = authInput;

function useLoginSubmit() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (endpoint: string, data: unknown) => {
    setFormError(null);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        // chỉ cho phép đường dẫn nội bộ (chặn open-redirect kiểu ?next=//evil.com)
        // "/\evil.com" qua được kiểu kiểm startsWith (trình duyệt hiểu "\" như "/") ⇒ phân giải rồi so origin
        const raw = searchParams.get("next") || "/";
        const target = new URL(raw, window.location.origin);
        const next = target.origin === window.location.origin && !raw.includes("\\") ? target.pathname + target.search : "/";
        router.push(next);
        router.refresh();
        return;
      }

      const body = (await res.json().catch(() => ({}))) as {
        detail?: unknown;
      };
      setFormError(
        typeof body.detail === "string" ? body.detail : "Đăng nhập thất bại",
      );
    } catch {
      setFormError("Không thể kết nối tới máy chủ");
    }
  };

  return { formError, submit };
}

function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className={authFormError}>
      {message}
    </p>
  );
}

function SubmitButton({ busy }: { busy: boolean }) {
  return (
    <button
      type="submit"
      disabled={busy}
      className={authButton}
    >
      {busy ? "Đang xử lý..." : "Đăng nhập"}
    </button>
  );
}

function EmailLogin() {
  const { formError, submit } = useLoginSubmit();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<EmailValues>({ resolver: zodResolver(emailSchema) });

  return (
    <form
      onSubmit={handleSubmit((d) => submit("/api/auth/login", d))}
      className="space-y-4"
    >
      <FormError message={formError} />

      <div>
        <label htmlFor="email" className={authLabel}>
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className={inputCls}
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
          autoComplete="current-password"
          className={inputCls}
          {...register("password")}
        />
        {errors.password && (
          <p className={authFieldError}>{errors.password.message}</p>
        )}
      </div>

      <SubmitButton busy={isSubmitting} />
    </form>
  );
}

function MssvLogin() {
  const { formError, submit } = useLoginSubmit();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<MssvValues>({ resolver: zodResolver(mssvSchema) });

  return (
    <form
      onSubmit={handleSubmit((d) => submit("/api/auth/login/ctu", d))}
      className="space-y-4"
    >
      <FormError message={formError} />

      <div>
        <label htmlFor="mssv" className={authLabel}>
          Mã số sinh viên
        </label>
        <input
          id="mssv"
          type="text"
          autoComplete="username"
          autoCapitalize="characters"
          placeholder="B2300000"
          className={`${inputCls} uppercase`}
          {...register("mssv")}
        />
        {errors.mssv && (
          <p className={authFieldError}>{errors.mssv.message}</p>
        )}
      </div>

      <div>
        <label htmlFor="mssv-password" className={authLabel}>
          Mã đăng nhập
        </label>
        <input
          id="mssv-password"
          type="password"
          autoComplete="current-password"
          className={inputCls}
          {...register("password")}
        />
        {errors.password && (
          <p className={authFieldError}>{errors.password.message}</p>
        )}
        <p className="mt-1.5 text-[12.5px] text-ink-muted">
          Mã đăng nhập do nhóm nghiên cứu cấp kèm MSSV.
        </p>
      </div>

      <SubmitButton busy={isSubmitting} />
    </form>
  );
}

export default function LoginForm() {
  const searchParams = useSearchParams();
  // ?via=email để link cũ/tài khoản email vào thẳng tab email
  const [mode, setMode] = useState<Mode>(
    searchParams.get("via") === "email" ? "email" : "mssv",
  );

  const tab = (m: Mode, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={mode === m}
      onClick={() => setMode(m)}
      className={`flex-1 rounded-lg py-2 text-sm transition ${
        mode === m ? "bg-primary font-semibold text-white" : "text-ink-soft hover:bg-white/70"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="space-y-4">
      <div role="tablist" className="flex gap-1.5 rounded-[11px] bg-tint p-1" aria-label="Cách đăng nhập">
        {tab("mssv", "MSSV")}
        {tab("email", "Email")}
      </div>
      {mode === "mssv" ? <MssvLogin /> : <EmailLogin />}
    </div>
  );
}

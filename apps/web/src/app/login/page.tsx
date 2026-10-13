import Link from "next/link";
import { Suspense } from "react";
import AuthShell from "../AuthShell";
import LoginForm from "./LoginForm";

export default function LoginPage() {
  return (
    <AuthShell
      title="Đăng nhập"
      subtitle="Đăng nhập bằng MSSV (tài khoản do nhóm nghiên cứu cấp) hoặc email đã đăng ký."
      footer={
        <>
          Chưa có tài khoản?{" "}
          <Link href="/register" className="font-semibold text-primary hover:underline">
            Đăng ký
          </Link>
        </>
      }
    >
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}

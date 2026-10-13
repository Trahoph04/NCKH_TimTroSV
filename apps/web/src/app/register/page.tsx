import Link from "next/link";
import AuthShell from "../AuthShell";
import RegisterForm from "./RegisterForm";

export default function RegisterPage() {
  return (
    <AuthShell
      title="Đăng ký"
      subtitle="Tạo tài khoản để lưu tiêu chí, ghép bạn ở, nhắn tin và đánh giá nhà trọ."
      footer={
        <>
          Đã có tài khoản?{" "}
          <Link href="/login" className="font-semibold text-primary hover:underline">
            Đăng nhập
          </Link>
        </>
      }
    >
      <RegisterForm />
    </AuthShell>
  );
}

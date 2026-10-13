-- Quản lý người dùng cho admin (thuyết minh THS2026-66, sản phẩm dòng 4 "quản lý người dùng, nhà trọ").
-- Khoá tài khoản vi phạm (spam chat, lời mời quấy rối): locked_at khác NULL ⇒ không đăng nhập/refresh được và mọi
-- request có token bị từ chối (auth/deps.get_current_user đọc DB mỗi request, nên khoá có hiệu lực ngay, không chờ
-- access token 15 phút hết hạn). Không xoá tài khoản để giữ lịch sử chat/đánh giá mù làm số liệu nghiên cứu.
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ;

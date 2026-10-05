from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = Field(default=None, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginIn(BaseModel):
    id_token: str  # Google ID token từ client (GIS)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    role: str
    avatar_url: str | None = None


class CtuLoginIn(BaseModel):
    """Đăng nhập bằng MSSV cho tài khoản cấp trước ở buổi thử nghiệm.

    MSSV chuẩn CTU dạng 'B2303891'; không ràng buộc regex chặt để không chặn oan
    các dạng mã khác (cao học, liên kết) — sai thì vẫn 401 như thường.
    """

    mssv: str = Field(min_length=4, max_length=20)
    password: str = Field(min_length=4, max_length=128)

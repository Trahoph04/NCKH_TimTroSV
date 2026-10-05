"""Chặn upload ảnh chat quá lớn TRƯỚC khi Starlette đọc body.

Giới hạn trong send_images (`f.file.read(max+1)`) chỉ giới hạn số byte ĐỌC RA
từ file tạm — lúc handler chạy thì Starlette đã nhận và spool HẾT multipart
xuống đĩa. Một request 2 GB vẫn chiếm 2 GB đĩa/băng thông rồi mới bị 422.
Middleware ASGI này cắt ở tầng nhận: Content-Length vượt ⇒ 413 ngay; không có
Content-Length (chunked) ⇒ đếm từng chunk, vượt thì ngắt.
"""
from __future__ import annotations

import re

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ..config import settings

_UPLOAD_PATH = re.compile(r"^/chat/conversations/\d+/images/?$")
# phần dư cho boundary/header multipart + trường body/client_id
_OVERHEAD = 256 * 1024


def max_upload_bytes() -> int:
    return settings.chat_max_images_per_message * settings.chat_max_image_mb * 1024 * 1024 + _OVERHEAD


class _TooLarge(Exception):
    pass


class ChatUploadLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or not _UPLOAD_PATH.match(scope["path"]):
            await self.app(scope, receive, send)
            return
        limit = max_upload_bytes()
        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    if int(v) > limit:
                        await _reject(send)
                        return
                except ValueError:
                    pass
                break

        seen = 0
        started = False

        async def limited_receive() -> Message:
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return msg

        async def tracking_send(msg: Message) -> None:
            nonlocal started
            if msg["type"] == "http.response.start":
                started = True
            await send(msg)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _reject(send)


async def _reject(send: Send) -> None:
    body = '{"detail":"Ảnh quá lớn"}'.encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})

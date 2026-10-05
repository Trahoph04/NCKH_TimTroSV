"""Chat realtime giữa sinh viên đã ghép — REST (gửi/đọc/đồng bộ) + WebSocket (đẩy sự kiện).

Nguyên tắc: GHI luôn qua REST (lưu DB trước) rồi mới publish qua hub. WebSocket
chỉ để ĐẨY sự kiện xuống client và nhận tín hiệu nhẹ (đang nhập, ping). Vì vậy
khi socket rớt, FE chuyển sang polling `GET .../messages?after_id=` mà không
mất tin nào.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Literal

import anyio
import jwt
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from ..auth import get_current_user
from ..auth.schemas import UserOut
from ..auth.security import decode_token, make_ws_ticket
from ..config import settings
from ..matching.repo import MatchRepo
from ..ratelimit import check_rate
from .hub import MAX_SOCKETS_PER_USER, ChatHub, Connection, dumps
from .media import MediaError, delete_files, media_path, process_image
from .repo import ChatRepo, ConversationGone

log = logging.getLogger("chat.router")

router = APIRouter(prefix="/chat", tags=["chat"])

_engine: Engine | None = None
_hub: ChatHub | None = None

WS_TICKET_TTL_S = 60
MAX_BODY = 2000
TYPING_PEERS_TTL_S = 30.0


def init_chat(engine: Engine, hub: ChatHub) -> None:
    global _engine, _hub
    _engine, _hub = engine, hub


def get_repo() -> ChatRepo:
    if _engine is None:
        raise HTTPException(503, "Chat repo chưa khởi tạo")
    return ChatRepo(_engine)


def get_hub() -> ChatHub:
    if _hub is None:
        raise HTTPException(503, "Chat hub chưa khởi tạo")
    return _hub


def _require_member(repo: ChatRepo, conv_id: int, user_id: int) -> None:
    # 404 (không phải 403) để không lộ hội thoại nào tồn tại
    if not repo.is_member(conv_id, user_id):
        raise HTTPException(404, "Không tìm thấy hội thoại")


def _with_online(conv: dict, hub: ChatHub) -> dict:
    conv["partner"]["online"] = hub.is_online(conv["partner"]["id"])
    return conv


# ---------------------------------------------------------------- schemas
class MessageIn(BaseModel):
    kind: Literal["text", "listing"] = "text"
    body: str | None = Field(default=None, max_length=MAX_BODY)
    listing_id: int | None = None
    client_id: str | None = Field(default=None, max_length=40)


class ReadIn(BaseModel):
    message_id: int = Field(ge=0)


class ReportIn(BaseModel):
    reason: Literal["spam", "harass", "fake", "scam", "other"]
    note: str | None = Field(default=None, max_length=1000)


# ------------------------------------------------------------------- REST
@router.post("/ws-ticket")
def ws_ticket(user: UserOut = Depends(get_current_user)):
    """Vé 60s để mở WebSocket (xem auth/security.make_ws_ticket)."""
    return {"ticket": make_ws_ticket(user.id, WS_TICKET_TTL_S), "expires_in": WS_TICKET_TTL_S}


@router.get("/unread")
def unread(user: UserOut = Depends(get_current_user), repo: ChatRepo = Depends(get_repo)):
    """Badge header: số tin chưa đọc + số người đã thích mình (tab Lời mời)."""
    likes = MatchRepo(repo.engine).count_likes_received(user.id)
    return {"messages": repo.total_unread(user.id), "likes": likes}


@router.get("/conversations")
def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    before: datetime | None = Query(default=None, description="last_message_at của dòng cuối trang trước"),
    before_id: int | None = Query(default=None, ge=1),
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    """Trang hội thoại mới nhất. Trang sau: truyền `next` của trang trước
    (before + before_id). `has_more=false` ⇒ đã hết."""
    if (before is None) != (before_id is None):
        raise HTTPException(422, "before và before_id phải đi cùng nhau")
    items, has_more = repo.list_conversations(
        user.id, limit=limit, before=(before, before_id) if before is not None else None
    )
    online = hub.online_map(c["partner"]["id"] for c in items)
    for c in items:
        c["partner"]["online"] = online.get(c["partner"]["id"], False)
    nxt = None
    if has_more and items:
        nxt = {"before": items[-1]["last_message_at"], "before_id": items[-1]["id"]}
    return {"items": items, "has_more": has_more, "next": nxt}


@router.get("/conversations/{conv_id}")
def get_conversation(
    conv_id: int,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    conv = repo.get_conversation(conv_id, user.id)
    if conv is None:
        raise HTTPException(404, "Không tìm thấy hội thoại")
    return _with_online(conv, hub)


@router.get("/conversations/{conv_id}/messages")
def list_messages(
    conv_id: int,
    after_id: int | None = Query(default=None, ge=0),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
):
    _require_member(repo, conv_id, user.id)
    items, has_more = repo.list_messages(conv_id, after_id=after_id, before_id=before_id, limit=limit)
    return {"items": items, "has_more": has_more}


def _broadcast_message(repo: ChatRepo, hub: ChatHub, conv_id: int, msg: dict) -> None:
    members = repo.member_ids(conv_id)
    hub.publish(members, {"type": "message.new", "conversation_id": conv_id, "message": msg})
    # Gửi tin ⇒ repo đã đẩy con trỏ đã-đọc của NGƯỜI GỬI lên tới tin vừa gửi
    # (send_message), nhưng trước đây không phát sự kiện 'read' nào. Hệ quả:
    # "Đã xem" ở phía người kia đứng ở tin cũ cho tới lần mark_read tiếp theo —
    # trông như người gửi chưa đọc tin mà họ vừa trả lời.
    sender_id = msg.get("sender_id")
    if sender_id:
        # Chỉ phát cho NGƯỜI KHÁC, không phát lại cho chính người gửi: họ không
        # cần được báo là mình đã đọc tin mình vừa gửi, và phát lại làm mọi
        # listener 'read' ở tab của họ nhận một sự kiện vô nghĩa đứng trước sự
        # kiện thật của đối phương. Tab khác của người gửi vẫn đồng bộ được con
        # trỏ từ 'message.new' ở trên.
        others = [m for m in members if m != sender_id]
        if others:
            hub.publish(others, {
                "type": "read",
                "conversation_id": conv_id,
                "user_id": sender_id,
                "message_id": msg["id"],
            })


@router.post("/conversations/{conv_id}/messages", status_code=201)
def send_message(
    conv_id: int,
    body: MessageIn,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    _require_member(repo, conv_id, user.id)
    check_rate("message", user.id)
    payload = None
    text_body = (body.body or "").strip() or None
    if body.kind == "text":
        if not text_body:
            raise HTTPException(422, "Tin nhắn trống")
    else:  # listing — chụp snapshot phía server, không tin dữ liệu FE gửi
        if body.listing_id is None:
            raise HTTPException(422, "Thiếu listing_id")
        payload = repo.listing_snapshot(body.listing_id)
        if payload is None:
            raise HTTPException(404, "Tin trọ không tồn tại hoặc đã ẩn")
    try:
        msg, is_new = repo.create_message(conv_id, user.id, body.kind, text_body, payload, body.client_id)
    except ConversationGone:
        raise HTTPException(404, "Không tìm thấy hội thoại")
    if is_new:
        _broadcast_message(repo, hub, conv_id, msg)
    return msg


@router.post("/conversations/{conv_id}/images", status_code=201)
def send_images(
    conv_id: int,
    files: list[UploadFile] = File(...),
    body: str | None = Form(default=None, max_length=MAX_BODY),
    client_id: str | None = Form(default=None, max_length=40),
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    _require_member(repo, conv_id, user.id)
    check_rate("upload", user.id)
    if not files:
        raise HTTPException(422, "Chưa chọn ảnh")
    if len(files) > settings.chat_max_images_per_message:
        raise HTTPException(422, f"Tối đa {settings.chat_max_images_per_message} ảnh mỗi lần gửi")
    media: list[dict] = []
    try:
        for f in files:
            media.append(process_image(f.file.read(settings.chat_max_image_mb * 1024 * 1024 + 1)))
    except MediaError as e:
        delete_files([m["id"] for m in media])
        raise HTTPException(422, str(e))
    payload = {"images": [{"id": m["id"], "w": m["w"], "h": m["h"]} for m in media]}
    try:
        msg, is_new = repo.create_message(
            conv_id, user.id, "image", (body or "").strip() or None, payload, client_id, media
        )
    except ConversationGone:
        delete_files([m["id"] for m in media])
        raise HTTPException(404, "Không tìm thấy hội thoại")
    except Exception:
        delete_files([m["id"] for m in media])
        raise
    if not is_new:  # gửi lại cùng client_id: bỏ bản vừa xử lý
        delete_files([m["id"] for m in media])
    else:
        _broadcast_message(repo, hub, conv_id, msg)
    return msg


@router.get("/media/{media_id}")
def get_media(
    media_id: str,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
):
    try:
        path = media_path(media_id)
    except ValueError:
        raise HTTPException(404, "Không tìm thấy ảnh")
    if repo.media_conversation(media_id, user.id) is None or not path.exists():
        raise HTTPException(404, "Không tìm thấy ảnh")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})


@router.post("/conversations/{conv_id}/read")
def mark_read(
    conv_id: int,
    body: ReadIn,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    _require_member(repo, conv_id, user.id)
    try:
        pointer, changed = repo.mark_read(conv_id, user.id, body.message_id)
    except ConversationGone:
        raise HTTPException(404, "Không tìm thấy hội thoại")
    if changed:
        hub.publish(
            repo.member_ids(conv_id),
            {"type": "read", "conversation_id": conv_id, "user_id": user.id, "message_id": pointer},
        )
    return {"last_read_message_id": pointer}


@router.get("/conversations/{conv_id}/contact-consent")
def get_contact_consent(
    conv_id: int,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
):
    """Trạng thái T3 tách riêng để FE hỏi lại cho nhẹ.

    `GET /chat/conversations/{id}` đã trả cùng khối `contact` này, nhưng kèm hồ sơ
    ở ghép + tin đã chia sẻ; panel đang ở trạng thái "chờ bên kia" chỉ cần đúng
    khối này nên không bắt nó kéo lại cả gói mỗi nhịp.
    """
    state = repo.contact_state(conv_id, user.id)
    if state is None:
        raise HTTPException(404, "Không tìm thấy hội thoại")
    return state


@router.post("/conversations/{conv_id}/contact-consent")
def post_contact_consent(
    conv_id: int,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    """T3: đồng ý cho người kia xem liên hệ CỦA MÌNH (không phải xin xem của họ).

    Liên hệ của đối phương chỉ trả về khi MỌI thành viên đã đồng ý; điều kiện đó
    kiểm trong SQL (`chat/repo.py:_CONTACT_SQL`), không dựa vào việc FE ẩn nút.
    Gọi lại nhiều lần không lỗi.
    """
    _require_member(repo, conv_id, user.id)
    out = repo.grant_contact_consent(conv_id, user.id)
    if out is None:  # bị huỷ ghép ngay giữa lúc kiểm quyền và lúc ghi
        raise HTTPException(404, "Không tìm thấy hội thoại")
    state, newly = out
    if newly:
        # Chỉ phát cho NGƯỜI KHÁC: mình vừa nhận state trong response rồi. Đây là
        # tín hiệu "bên kia vừa đồng ý" để panel của họ đổi trạng thái không cần
        # đợi nhịp hỏi lại; realtime là best-effort (hub.publish tự nuốt lỗi) nên
        # FE vẫn phải tự hỏi lại, không được coi sự kiện này là bắt buộc tới.
        others = [m for m in repo.member_ids(conv_id) if m != user.id]
        hub.publish(
            others,
            {
                "type": "contact.consent",
                "conversation_id": conv_id,
                "user_id": user.id,
                "unlocked": state["unlocked"],
            },
        )
    return state


@router.delete("/conversations/{conv_id}", status_code=204)
def unmatch(
    conv_id: int,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
    hub: ChatHub = Depends(get_hub),
):
    """Huỷ ghép + xoá cứng hội thoại (tin nhắn, ảnh) cho CẢ HAI bên."""
    _require_member(repo, conv_id, user.id)
    members, media = repo.unmatch(conv_id, user.id)
    delete_files(media)
    hub.publish(members, {"type": "conversation.removed", "conversation_id": conv_id, "by_user_id": user.id})


@router.post("/conversations/{conv_id}/report", status_code=201)
def report(
    conv_id: int,
    body: ReportIn,
    user: UserOut = Depends(get_current_user),
    repo: ChatRepo = Depends(get_repo),
):
    _require_member(repo, conv_id, user.id)
    check_rate("report", user.id)
    others = [m for m in repo.member_ids(conv_id) if m != user.id]
    if not others:
        raise HTTPException(404, "Không tìm thấy người cần báo cáo")
    rid = repo.report(conv_id, user.id, others[0], body.reason, body.note)
    return {"id": rid}


# -------------------------------------------------------------- WebSocket
@router.websocket("/ws")
async def chat_ws(websocket: WebSocket, ticket: str = ""):
    """Kênh đẩy sự kiện. Client gửi: {type:'ping'} · {type:'typing', conversation_id, is_typing}.

    Server đẩy: hello · pong · message.new · read · typing · presence ·
    match.new · like.new · conversation.removed · contact.consent.
    Vé sai/hết hạn ⇒ từ chối NGAY ở bước bắt tay (HTTP 403, chưa accept): kiểm
    vé chỉ tốn CPU, không có lý do gì cấp socket cho kẻ không có vé. FE không
    dựa vào mã đóng — mỗi lần nối lại nó luôn xin vé mới (useChatSocket).
    Quá MAX_SOCKETS_PER_USER ⇒ đóng 4429.
    """
    try:
        user_id = int(decode_token(ticket, "ws")["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        await websocket.close(code=4401)
        return
    if _engine is None or _hub is None:
        await websocket.close(code=1013)
        return
    if _hub.socket_count(user_id) >= MAX_SOCKETS_PER_USER:
        await websocket.close(code=4429)
        return
    await websocket.accept()

    repo, hub = ChatRepo(_engine), _hub
    # Cache "ai cùng hội thoại" cho frame typing: mỗi phím gõ là một frame, bản
    # trước tốn 1 kết nối DB cho MỖI frame. TTL ngắn để huỷ ghép giữa chừng
    # không tiếp tục báo "đang nhập" cho người đã bị huỷ quá lâu.
    peers: dict[int, tuple[float, list[int]]] = {}
    conn = Connection(user_id=user_id, websocket=websocket, loop=asyncio.get_running_loop())
    conn.conv_ids = await run_in_threadpool(repo.conversation_ids, user_id)
    became_online = await run_in_threadpool(hub.register, conn)
    try:
        partners = await run_in_threadpool(repo.partner_ids, user_id)
        online = await run_in_threadpool(hub.online_map, partners)
        await websocket.send_text(
            dumps({"type": "hello", "user_id": user_id, "online": [p for p, o in online.items() if o]})
        )
        if became_online:
            await run_in_threadpool(
                hub.publish, partners, {"type": "presence", "user_id": user_id, "online": True}
            )

        while True:
            raw = await websocket.receive_text()
            try:
                frame = json.loads(raw)
            except ValueError:
                continue
            kind = frame.get("type") if isinstance(frame, dict) else None
            if kind == "ping":
                await run_in_threadpool(hub.heartbeat, user_id)
                await websocket.send_text('{"type":"pong"}')
            elif kind == "typing":
                try:
                    cid = int(frame.get("conversation_id"))
                except (TypeError, ValueError):
                    continue
                now = time.monotonic()
                cached = peers.get(cid)
                if cached is not None and cached[0] > now:
                    others = cached[1]
                else:
                    if cid not in conn.conv_ids:  # hội thoại mới ghép sau khi mở socket
                        conn.conv_ids = await run_in_threadpool(repo.conversation_ids, user_id)
                        if cid not in conn.conv_ids:
                            continue
                    members = await run_in_threadpool(repo.member_ids, cid)
                    if user_id not in members:   # đã bị huỷ ghép
                        conn.conv_ids.discard(cid)
                        peers.pop(cid, None)
                        continue
                    others = [m for m in members if m != user_id]
                    peers[cid] = (now + TYPING_PEERS_TTL_S, others)
                await run_in_threadpool(
                    hub.publish,
                    others,
                    {
                        "type": "typing",
                        "conversation_id": cid,
                        "user_id": user_id,
                        "is_typing": bool(frame.get("is_typing", True)),
                    },
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.warning("chat ws error user=%s: %s", user_id, exc)
    finally:
        # shield: server tắt / client rớt kiểu bị huỷ task vẫn phải dọn presence,
        # nếu không người kia thấy "Đang hoạt động" mãi tới khi TTL Redis hết.
        with anyio.CancelScope(shield=True):
            went_offline = await run_in_threadpool(hub.unregister, conn)
            if went_offline:
                try:
                    await run_in_threadpool(repo.touch_last_seen, user_id)
                    partners = await run_in_threadpool(repo.partner_ids, user_id)
                    await run_in_threadpool(
                        hub.publish,
                        partners,
                        {
                            "type": "presence",
                            "user_id": user_id,
                            "online": False,
                            "last_seen_at": datetime.now(timezone.utc),
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    log.warning("chat ws cleanup error user=%s: %s", user_id, exc)

"""API ghép bạn ở (Reciprocal Recommender).

    GET  /matching/profile   : hồ sơ 12 câu của mình
    POST /matching/profile   : lưu hồ sơ → trả LUÔN top-3 (thưởng tức thì)
    GET  /matching/deck      : bộ thẻ hôm nay — lọc cứng → điểm 2 chiều → xếp hạng
    POST /matching/swipe     : thích / bỏ qua; 2 chiều thích ⇒ match + hội thoại
    GET  /matching/likes     : tab "Lời mời" — ai đã thích mình, mình chưa quyết
    GET  /matching/passed    : thẻ đã bỏ qua (pass KHÔNG vĩnh viễn)
    POST /matching/invite                 : gửi lời mời kèm lời nhắn (= like + note)
    GET  /matching/invites                : lời mời đang chờ (nhận được + đã gửi)
    POST /matching/invites/{id}/respond   : nhận / từ chối lời mời
    GET  /matching/rate      : 5 thẻ chấm điểm làm mù (3 thuật toán + 2 ngẫu nhiên)
    POST /matching/rate      : chấm 1–5 một thẻ

Thuật toán: filters.py (lọc cứng 2 tầng) · score.py (Gower + harmonic mean) ·
weights.py (trọng số dẫn từ khảo sát) · stable.py (Stable Roommates, dùng ở eval).
Thiết kế: docs/tech_specs/Matching_Messaging_Design.md Phần II/III.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.engine import Engine

from ..auth import get_current_user
from ..auth.schemas import UserOut
from ..chat.hub import ChatHub
from ..ratelimit import check_rate
from .profile import DEAL_BREAKER, GENDERS, HANH_VI
from .repo import MatchError, MatchRepo

router = APIRouter(prefix="/matching", tags=["matching"])

_engine: Engine | None = None
_hub: ChatHub | None = None


def init_matching(engine: Engine, hub: ChatHub) -> None:
    global _engine, _hub
    _engine, _hub = engine, hub


def get_repo() -> MatchRepo:
    if _engine is None:
        raise HTTPException(503, "Matching repo chưa khởi tạo")
    return MatchRepo(_engine)


class ProfileIn(BaseModel):
    """12 câu của form v2. Mọi trường optional để lưu được hồ sơ dở dang —
    nhưng `in_pool` (profile.py) đòi gender + ít nhất một chiều lối sống mới
    vào được pool ghép, nên FE phải nói rõ còn thiếu gì."""

    gender: Literal["nam", "nu"] | None = None
    don_vi: str | None = Field(default=None, max_length=100)
    budget_band: int | None = Field(default=None, ge=0, le=4)
    scenario: int | None = Field(default=None, ge=1, le=3)
    sleep_time: int | None = Field(default=None, ge=0, le=2)
    wake_time: int | None = Field(default=None, ge=0, le=2)
    cleanliness: int | None = Field(default=None, ge=1, le=5)
    noise_tolerance: int | None = Field(default=None, ge=1, le=5)
    ac_usage: int | None = Field(default=None, ge=0, le=2)
    money_style: int | None = Field(default=None, ge=1, le=2)
    share_stuff: int | None = Field(default=None, ge=0, le=1)
    smoke: bool | None = None
    smoke_in_room: bool | None = None
    hanh_vi: list[str] | None = None
    deal_breakers: list[str] | None = None
    persona: Literal["A", "B"] | None = None
    bio: str | None = Field(default=None, max_length=500)
    need_from: str | None = Field(default=None, max_length=40)
    roommate_status: str | None = Field(default=None, max_length=60)

    @field_validator("hanh_vi")
    @classmethod
    def _check_hanh_vi(cls, v):
        return _only_known(v, HANH_VI, "hành vi")

    @field_validator("deal_breakers")
    @classmethod
    def _check_deal_breakers(cls, v):
        return _only_known(v, DEAL_BREAKER, "deal-breaker")


def _only_known(v: list[str] | None, allowed: tuple[str, ...], what: str):
    """Chặn giá trị lạ ngay ở biên.

    Một lựa chọn sai chính tả lọt vào TEXT[] sẽ KHÔNG đối chiếu được với
    DB_TO_HANHVI ⇒ deal-breaker nằm im trong DB, lọc cứng thành vô hiệu mà không
    báo lỗi. Thà 422 ở đây còn hơn mất lớp an toàn trong im lặng.
    """
    if v is None:
        return None
    bad = [x for x in v if x not in allowed]
    if bad:
        raise ValueError(f"Giá trị {what} không hợp lệ: {bad}")
    return sorted(set(v))


class InviteIn(BaseModel):
    target_id: int
    note: str | None = Field(default=None, max_length=300)


class RespondIn(BaseModel):
    accept: bool


class RateIn(BaseModel):
    card_code: str = Field(min_length=4, max_length=8)
    rating: int = Field(ge=1, le=5)


class SwipeIn(BaseModel):
    target_id: int
    decision: Literal["like", "pass"]
    # KHÔNG có deck_position / deck_mode / score_at_swipe: server đọc từ deck_log
    # (93_matching_deck.sql). Client tự khai vị trí thẻ thì bằng chứng khử thiên
    # lệch vị trí ở doc 3.6 mất hết giá trị.


@router.get("/profile")
def get_profile(user: UserOut = Depends(get_current_user), repo: MatchRepo = Depends(get_repo)):
    prof = repo.get_profile(user.id)
    return {
        "profile": prof,
        "in_pool": bool(prof and prof.get("gender") in GENDERS
                        and (prof.get("sleep_time") is not None
                             or prof.get("cleanliness") is not None)),
        "options": {"hanh_vi": list(HANH_VI), "deal_breakers": list(DEAL_BREAKER)},
    }


@router.post("/profile")
def save_profile(
    body: ProfileIn,
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    """Lưu hồ sơ và trả NGAY top-3.

    Thưởng tức thì là thứ đẩy tỉ lệ hoàn thành form, không phải lời hứa "sau này
    sẽ có" (doc 2.8 mục 1).
    """
    try:
        prof = repo.upsert_profile(user.id, body.model_dump(exclude_unset=True))
    except MatchError as e:
        raise HTTPException(e.status, e.detail)
    deck = repo.deck(user.id, limit=3)
    return {"profile": prof, "preview": deck}


@router.get("/deck")
def deck(
    limit: int = Query(default=10, ge=1, le=30),
    mode: Literal["ranked", "random"] = "ranked",
    weights_ver: Literal["survey", "uniform"] = "survey",
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    """200 kèm items: [] khi hết pool — KHÔNG 404.

    `reason` nói rõ vì sao rỗng (no_profile | profile_incomplete | pool_empty |
    deck_done) để FE hiện đúng hướng dẫn thay vì màn hình lỗi.
    """
    return repo.deck(user.id, limit=limit, mode=mode, weights_ver=weights_ver)


def _publish_swipe(user_id: int, target_id: int, decision: str, res: dict) -> None:
    """Đẩy sự kiện realtime sau swipe / lời mời. Hub chết không được chặn luồng chính."""
    if res.get("unmatch_conversation_id") is not None and _engine is not None:
        # 'pass' một người đang ghép = huỷ ghép: dùng ĐÚNG đường của nút "Huỷ
        # ghép" trong chat (xoá cứng hội thoại + ảnh, báo cho cả hai bên).
        # import muộn: chat.repo import matching.repo ở cấp module ⇒ import ở đầu
        # file này là vòng import (chat.repo → matching → router → chat.repo).
        from ..chat.media import delete_files
        from ..chat.repo import ChatRepo

        conv_id = res["unmatch_conversation_id"]
        members, media = ChatRepo(_engine).unmatch(conv_id, user_id)
        delete_files(media)
        if _hub is not None:
            _hub.publish(members, {"type": "conversation.removed",
                                   "conversation_id": conv_id, "by_user_id": user_id})
    if _hub is None:
        return
    if res["matched"] and res["created"]:
        _hub.publish(
            [user_id, target_id],
            {"type": "match.new", "conversation_id": res["conversation_id"]},
        )
    elif decision == "like" and not res["matched"]:
        # chỉ báo "có người thích bạn", KHÔNG nói là ai — tab Lời mời tự tải lại
        _hub.publish([target_id], {"type": "like.new"})


@router.post("/swipe")
def swipe(
    body: SwipeIn,
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    check_rate("swipe", user.id)
    try:
        res = repo.swipe(user.id, body.target_id, body.decision)
    except MatchError as e:
        raise HTTPException(e.status, e.detail)
    _publish_swipe(user.id, body.target_id, body.decision, res)
    out = {"matched": res["matched"], "conversation_id": res["conversation_id"]}
    if res.get("unmatch_conversation_id") is not None:
        out["unmatched"] = True  # chỉ có khi pass người đang ghép — giữ nguyên shape cũ
    return out


@router.post("/invite")
def invite(
    body: InviteIn,
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    """Gửi lời mời kèm lời nhắn. Người kia đã thích mình ⇒ thành đôi ngay."""
    check_rate("invite", user.id)
    try:
        res = repo.invite(user.id, body.target_id, body.note)
    except MatchError as e:
        raise HTTPException(e.status, e.detail)
    _publish_swipe(user.id, body.target_id, "like", res)
    return {"matched": res["matched"], "conversation_id": res["conversation_id"],
            "invite_id": res["invite_id"]}


@router.get("/invites")
def invites(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    return repo.invites(user.id, limit=limit)


@router.post("/invites/{invite_id}/respond")
def respond_invite(
    invite_id: int,
    body: RespondIn,
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    check_rate("swipe", user.id)
    try:
        res = repo.respond_invite(user.id, invite_id, body.accept)
    except MatchError as e:
        raise HTTPException(e.status, e.detail)
    _publish_swipe(user.id, res["from_user"], "like" if body.accept else "pass", res)
    return {"matched": res["matched"], "conversation_id": res["conversation_id"]}


@router.get("/rate")
def rating_cards(
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    """Thẻ chấm điểm làm mù. Không có score/arm trong response — có chủ đích."""
    return repo.rating_cards(user.id)


@router.post("/rate", status_code=204)
def rate(
    body: RateIn,
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    check_rate("rate", user.id)
    try:
        repo.rate(user.id, body.card_code, body.rating)
    except MatchError as e:
        raise HTTPException(e.status, e.detail)


@router.get("/likes")
def likes(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    return {"items": repo.likes_received(user.id, limit=limit)}


@router.get("/passed")
def passed(
    limit: int = Query(default=50, ge=1, le=200),
    user: UserOut = Depends(get_current_user),
    repo: MatchRepo = Depends(get_repo),
):
    """Thẻ đã bỏ qua. 'pass' chỉ hạ ưu tiên 7 ngày, không xoá vĩnh viễn — ở pool
    nhỏ xoá vĩnh viễn là đốt pool (doc 3.5 mục 2)."""
    return {"items": repo.passed(user.id, limit=limit)}

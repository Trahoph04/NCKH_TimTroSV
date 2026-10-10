"""Gợi ý nhà trọ (FR-4) — docs/specs/Recommendation.md, ADR-021.

    POST /recommend               : 10 tin + lý do + điều cần hỏi (public)
    GET  /recommend/prefill       : ngân sách/giới tính từ hồ sơ ghép bạn (đăng nhập)
    POST /recommend/eval/session  : tạo lượt đánh giá mù — gộp top-10 của 3 hệ, xáo trộn
    GET  /recommend/eval/session  : lượt gần nhất (để làm tiếp)
    POST /recommend/eval/judge    : chấm 0–2 một thẻ
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Engine

from ..auth import get_current_user
from ..auth.schemas import UserOut
from ..listings.repo import ListingQueryRepo
from ..ratelimit import check_rate
from .core import ALGO_VERSION, Query, baseline_cosine, baseline_price, explain, recommend, weights
from .repo import RecommendRepo
from .schemas import (
    EvalCard, EvalSession, JudgeIn, Prefill, RecommendIn, RecommendItem, RecommendOut,
)

router = APIRouter(prefix="/recommend", tags=["recommend"])

_engine: Engine | None = None


def init_recommend(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_repo() -> RecommendRepo:
    if _engine is None:
        raise HTTPException(503, "Recommend repo chưa khởi tạo")
    return RecommendRepo(_engine)


def _query(body: RecommendIn) -> Query:
    return Query(
        budget=body.budget, campus=body.campus, max_minutes=body.max_minutes,
        housing=body.housing.value if body.housing else None,
        required=tuple(body.required), top_factors=tuple(body.top_factors), gender=body.gender,
    )


@router.post("", response_model=RecommendOut)
def recommend_listings(body: RecommendIn, repo: RecommendRepo = Depends(get_repo)):
    q = _query(body)
    cands = repo.candidates()
    top, relaxed, n_pool = recommend(cands, q, k=10)
    listings = ListingQueryRepo(_engine).get_many([s.c.id for s in top])
    items = []
    for s in top:
        if s.c.id not in listings:
            continue  # tin vừa bị ẩn giữa 2 lần làm mới cache
        reasons, ask = explain(s, q)
        items.append(RecommendItem(listing=listings[s.c.id], match=round(s.utility * 100),
                                   reasons=reasons, ask=ask))
    return RecommendOut(items=items, relaxed=relaxed, candidates=n_pool,
                        weights={k: round(v, 3) for k, v in weights(q.top_factors).items()},
                        algo_ver=ALGO_VERSION)


@router.get("/prefill", response_model=Prefill)
def prefill(user: UserOut = Depends(get_current_user), repo: RecommendRepo = Depends(get_repo)):
    return Prefill(**repo.prefill(user.id))


def _session_out(sess: dict, campus: int) -> EvalSession:
    listings = ListingQueryRepo(_engine).get_many([c["listing_id"] for c in sess["cards"]])
    cards = [
        EvalCard(card_code=c["card_code"], listing=listings[c["listing_id"]],
                 minutes=(listings[c["listing_id"]].route_time_campus or [None] * 3)[campus],
                 relevance=c["relevance"])
        for c in sess["cards"] if c["listing_id"] in listings
    ]
    judged = sum(1 for c in cards if c.relevance is not None)
    return EvalSession(session_id=sess["id"], campus=campus, cards=cards, judged=judged,
                       completed=sess["completed"])


@router.post("/eval/session", response_model=EvalSession)
def create_eval_session(
    body: RecommendIn,
    user: UserOut = Depends(get_current_user),
    repo: RecommendRepo = Depends(get_repo),
):
    check_rate("rec_session", user.id)
    q = _query(body)
    cands = repo.candidates()
    top, relaxed, _ = recommend(cands, q, k=10)
    rankings = {
        "proposed": [s.c.id for s in top],
        "price": [c.id for c in baseline_price(cands, q, k=10)],
        "cosine": [c.id for c in baseline_cosine(cands, q, k=10)],
    }
    repo.create_session(user.id, body.model_dump(mode="json"), relaxed, ALGO_VERSION, rankings,
                        {s.c.id: s.utility for s in top})
    return _session_out(repo.latest_session(user.id), q.campus)


@router.get("/eval/session", response_model=EvalSession | None)
def get_eval_session(user: UserOut = Depends(get_current_user), repo: RecommendRepo = Depends(get_repo)):
    sess = repo.latest_session(user.id)
    if sess is None:
        return None
    return _session_out(sess, int(sess["criteria"].get("campus", 1)))


@router.post("/eval/judge", status_code=204)
def judge(body: JudgeIn, user: UserOut = Depends(get_current_user), repo: RecommendRepo = Depends(get_repo)):
    check_rate("rec_judge", user.id)
    if not repo.judge(user.id, body.card_code, body.relevance):
        raise HTTPException(404, "Không tìm thấy thẻ")

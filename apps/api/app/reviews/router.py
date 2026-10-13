from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.engine import Engine

from ..auth.deps import get_current_user, require_admin
from ..auth.schemas import UserOut
from ..ratelimit import check_rate
from .repo import ReviewRepo
from .schemas import AdminReviewPage, ReviewIn, ReviewList, ReviewModerationIn, ReviewOut

router = APIRouter(tags=["reviews"])

# engine được set bởi main.py qua init_reviews(engine)
_engine: Engine | None = None


def init_reviews(engine: Engine) -> None:
    global _engine
    _engine = engine


def get_repo() -> ReviewRepo:
    if _engine is None:
        raise HTTPException(503, "Review repo chưa khởi tạo")
    return ReviewRepo(_engine)


@router.get("/listings/{listing_id}/reviews", response_model=ReviewList)
def list_reviews(
    listing_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    repo: ReviewRepo = Depends(get_repo),
):
    """Công khai: tóm tắt (điểm TB, phân bố sao, đếm tag) + đánh giá đang hiện. Tin ẩn/hết hạn ⇒ 404."""
    if not repo.listing_reviewable(listing_id):
        raise HTTPException(404, "Không tìm thấy tin")
    return ReviewList(summary=repo.summary(listing_id), items=repo.visible(listing_id, page, size), page=page, size=size)


# /mine khai TRƯỚC các route động khác cùng prefix (quy ước repo)
@router.get("/listings/{listing_id}/reviews/mine", response_model=ReviewOut | None)
def my_review(listing_id: int, user: UserOut = Depends(get_current_user), repo: ReviewRepo = Depends(get_repo)):
    """Đánh giá của chính mình (kể cả bị admin ẩn — để biết vì sao không thấy trên trang)."""
    return repo.mine(listing_id, user.id)


@router.post("/listings/{listing_id}/reviews", response_model=ReviewOut)
def upsert_review(
    listing_id: int,
    body: ReviewIn,
    user: UserOut = Depends(get_current_user),
    repo: ReviewRepo = Depends(get_repo),
):
    """Mỗi tài khoản một đánh giá/tin: gửi lại = sửa (mig 102)."""
    check_rate("review", user.id)
    owner = repo.listing_owner(listing_id)
    if owner is False:
        raise HTTPException(404, "Không tìm thấy tin")
    if owner == user.id:
        raise HTTPException(403, "Không tự đánh giá tin do chính mình đăng")
    repo.upsert(listing_id, user.id, body)
    return repo.mine(listing_id, user.id)


@router.delete("/listings/{listing_id}/reviews/mine", status_code=204)
def delete_my_review(listing_id: int, user: UserOut = Depends(get_current_user), repo: ReviewRepo = Depends(get_repo)):
    if not repo.delete_mine(listing_id, user.id):
        mine = repo.mine(listing_id, user.id)
        if mine is not None and mine.status == "hidden":
            raise HTTPException(409, "Đánh giá đang bị quản trị viên ẩn nên không xoá được")
        raise HTTPException(404, "Bạn chưa đánh giá tin này")
    return Response(status_code=204)


@router.get("/admin/reviews", response_model=AdminReviewPage)
def admin_reviews(
    status: str | None = Query(None, pattern="^(visible|hidden)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _admin: UserOut = Depends(require_admin),
    repo: ReviewRepo = Depends(get_repo),
):
    total, items = repo.admin_search(status, page, size)
    return AdminReviewPage(total=total, page=page, size=size, items=items)


@router.patch("/admin/reviews/{review_id}", status_code=204)
def moderate_review(
    review_id: int,
    body: ReviewModerationIn,
    _admin: UserOut = Depends(require_admin),
    repo: ReviewRepo = Depends(get_repo),
):
    """Ẩn/hiện một đánh giá (vi phạm, sai sự thật). Không xoá — giữ làm bằng chứng nếu có khiếu nại."""
    if not repo.set_status(review_id, body.status):
        raise HTTPException(404, "Không tìm thấy đánh giá")
    return Response(status_code=204)

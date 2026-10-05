"""Ghép bạn ở ghép — Reciprocal Recommender System.

Tầng thuật toán THUẦN (không DB, không FastAPI) để test bằng pytest mà không cần
Postgres, và để notebook eval gọi đúng hàm API đang dùng:
    profile.py  hằng số form v2 + chuẩn hoá hồ sơ
    filters.py  lọc cứng 2 tầng (an toàn = cứng · nội quy nhà = mềm)
    score.py    Gower có trọng số + điểm có hướng + harmonic mean [R12][R14]
    weights.py  trọng số dẫn từ khảo sát, ghi rõ nguồn từng con số
    stable.py   Stable Roommates (non-bipartite — có thể VÔ NGHIỆM)
"""
from .filters import eligible_pool, hard_filter_reason, passes_hard_filters, soft_violations
from .profile import Profile
from .repo import MatchError, MatchRepo, create_match, lock_pair
from .router import init_matching, router as matching_router
from .score import harmonic, pair_score
from .stable import stable_roommates

__all__ = [
    "MatchError", "MatchRepo", "Profile",
    # lock_pair đi KÈM create_match: mọi đường sinh match mới phải giữ advisory
    # lock của cặp trước khi gọi create_match, nếu không hai người bấm thích cùng
    # lúc sẽ ra hai hội thoại. Bản trước chỉ export create_match.
    "create_match", "lock_pair",
    "eligible_pool", "hard_filter_reason", "passes_hard_filters", "soft_violations",
    "harmonic", "pair_score", "stable_roommates",
    "init_matching", "matching_router",
]

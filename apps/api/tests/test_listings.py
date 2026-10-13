from datetime import datetime, timedelta, timezone

from app.listings.schemas import (
    SearchParams,
    SortBy,
    freshness_label,
    risk_level,
)
from app.listings.repo import build_filters, _SORT_SQL


# ── risk_level ──
def test_risk_level_thresholds():
    assert risk_level(0.0) == "unknown"
    assert risk_level(0.01) == "safe"
    assert risk_level(0.29) == "safe"
    assert risk_level(0.3) == "caution"
    assert risk_level(0.59) == "caution"
    assert risk_level(0.6) == "suspicious"
    assert risk_level(None) == "unknown"


# ── freshness_label ──
def test_freshness_label():
    now = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)
    assert "phút" in freshness_label(now - timedelta(minutes=30), now)
    assert "giờ" in freshness_label(now - timedelta(hours=5), now)
    assert "ngày" in freshness_label(now - timedelta(days=3), now)
    assert freshness_label(None) == "không rõ"


# ── build_filters: luôn ẩn expired và hidden ──
def test_build_filters_hides_expired_and_hidden():
    where, params = build_filters(SearchParams())
    assert "status NOT IN ('expired', 'hidden')" in where
    assert params == {}


def test_build_filters_price_district():
    p = SearchParams(min_price=1_000_000, max_price=3_000_000, district="Ninh Kiều")
    where, params = build_filters(p)
    assert "price >= :min_price" in where
    assert "price <= :max_price" in where
    assert "COALESCE(NULLIF(district_norm, ''), district) ILIKE :district" in where
    assert params["min_price"] == 1_000_000
    assert params["district"] == "%Ninh Kiều%"


def test_build_filters_query_search():
    where, params = build_filters(SearchParams(q="gần CTU"))
    assert "title ILIKE :q" in where
    assert params["q"] == "%gần CTU%"


def test_build_filters_amenities():
    where, params = build_filters(SearchParams(amenities=["wifi", "air_conditioner"]))
    assert "(parsed_amenities ->> :am0)::boolean IS TRUE" in where
    assert "(parsed_amenities ->> :am1)::boolean IS TRUE" in where
    assert params["am0"] == "wifi"
    assert params["am1"] == "air_conditioner"


def test_build_filters_distance():
    where, params = build_filters(SearchParams(max_distance_ctu=1500))
    assert "distance_to_ctu <= :max_dist" in where
    assert params["max_dist"] == 1500


# ── sort mapping đủ mọi enum ──
def test_all_sort_options_mapped():
    for s in SortBy:
        assert s in _SORT_SQL
        assert _SORT_SQL[s]


def test_search_params_validation():
    # size bị kẹp, page >= 1
    p = SearchParams(page=2, size=50)
    assert p.page == 2 and p.size == 50

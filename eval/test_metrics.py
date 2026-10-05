"""Đối chiếu metrics.py với scipy — chạy: eval/.venv/bin/python -m pytest eval/test_metrics.py
(hoặc `eval/.venv/bin/python eval/test_metrics.py`). metrics.py cố ý không phụ
thuộc scipy nên phải có chỗ chứng minh nó tính ra cùng số."""
from __future__ import annotations

import random

import numpy as np
from scipy import stats

import metrics as M


def _close(a, b, tol=1e-9):
    assert abs(a - b) <= tol, (a, b)


def test_kendall_tau_b_khop_scipy_ke_ca_ties():
    rng = random.Random(0)
    for _ in range(200):
        n = rng.randint(2, 12)
        a = [rng.randint(0, 4) for _ in range(n)]
        b = [rng.randint(0, 4) for _ in range(n)]
        ours = M.kendall_tau(a, b)
        ref = stats.kendalltau(a, b, variant="b").statistic
        if np.isnan(ref):
            assert ours is None
        else:
            _close(ours, ref)


def test_wilcoxon_khop_scipy_approx():
    rng = random.Random(1)
    for _ in range(200):
        n = rng.randint(6, 30)
        x = [rng.choice([0, 1 / 3, 2 / 3, 1]) for _ in range(n)]
        y = [rng.choice([0, 1 / 3, 2 / 3, 1]) for _ in range(n)]
        ours = M.wilcoxon_signed_rank(x, y)
        if ours["n"] == 0 or ours["p_two_sided"] is None:
            continue
        ref = stats.wilcoxon(x, y, zero_method="wilcox", correction=False, method="approx")
        _close(ours["p_two_sided"], ref.pvalue, 1e-9)
        _close(ours["w"], ref.statistic, 1e-9)


def test_gini_khop_cong_thuc_sap_xep():
    rng = random.Random(2)
    for _ in range(200):
        xs = [rng.randint(0, 20) for _ in range(rng.randint(1, 25))]
        if sum(xs) == 0:
            assert M.gini(xs) == 0.0
            continue
        s = np.sort(np.array(xs, float))
        n = len(s)
        ref = (2 * np.sum(np.arange(1, n + 1) * s) / (n * s.sum())) - (n + 1) / n
        _close(M.gini(xs), ref)
    assert M.gini([5, 5, 5]) == 0.0
    _close(M.gini([0, 0, 0, 10]), 0.75)


def test_cosine_bo_qua_chieu_thieu_va_khop_numpy():
    a, b = [1.0, None, 3.0, 2.0], [2.0, 5.0, 1.0, None]
    ref = np.dot([1, 3], [2, 1]) / (np.linalg.norm([1, 3]) * np.linalg.norm([2, 1]))
    _close(M.cosine_similarity(a, b), ref)
    assert M.cosine_similarity([None], [1.0]) is None
    assert M.cosine_similarity([0.0, 0.0], [1.0, 2.0]) is None


def test_coverage_va_metric_cu_cua_notebook_01_khong_doi():
    assert M.coverage_at_least_one([0, 2, 0, 5]) == 0.5
    assert M.precision_at_k([1, 2, 3], {1, 3}, k=3) == 2 / 3
    assert 0.0 <= M.ndcg_at_k([1, 2, 3], {1: 3, 3: 1}, k=3) <= 1.0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)

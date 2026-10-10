# 📊 NCKH/eval — Đánh giá thực nghiệm

Notebook + script đo metric cho báo cáo nghiệm thu (THS2026-66).

## Cấu trúc
```
eval/
├── data/            # ground-truth: listings, scam labels, user-mock, Q&A test
├── notebooks/       # notebook eval từng module
└── metrics.py       # hàm metric dùng chung (P@K, NDCG, ILS)
```

## Mapping notebook → metric → ngưỡng

| Notebook | Module | Metric | Ngưỡng đạt |
|---|---|---|---|
| `01_recommendation_eval.ipynb` | Recommendation (sinh từ `tools/build_nb01.py`, gọi `recommend_lib.py`) | Precision@10, NDCG@10, ILS | ≥0.6 / ≥0.65 / ≤0.7 |
| `02_dedup_eval.ipynb` | Dedup | recall, false-merge | ≥90% / ≤5% |
| `03_geocoding_eval.ipynb` | Geocoding | %confidence≥medium, sai >1km | ≥80% / 0 trên 50 mẫu |
| `04_risk_eval.ipynb` | Risk | recall scam | ≥85% |
| `05_rag_eval.ipynb` | Chatbot RAG | Faithfulness, AnsRel (RAGAS) | ≥0.7 / ≥0.75 |
| `06_roommate_eval.ipynb` | Matching (ghép bạn ở) | pool theo tầng lọc · cosine vs Gower · harmonic vs cộng · ablation · độ nhạy τ · độ phủ theo N (mô phỏng) · Stable Roommates · Gini exposure · P@3/NDCG@3/Wilcoxon (chấm làm mù 1–5) | P@3 thuật toán > ngẫu nhiên, Wilcoxon p < 0,05 |

## Dataset cần chuẩn bị (Sprint 0–1)

| File | Mô tả | Kích thước tối thiểu |
|---|---|---|
| `data/listings_groundtruth.json` | Listing đã verify thủ công | 100 |
| `data/scam_labels.csv` | Tin gán nhãn scam/clean | 100 (≥30 scam) |
| `data/dup_pairs.csv` | Cặp trùng/không trùng | 200 cặp |
| `data/user_mock.json` | User-mock + relevance phòng | 30 user |
| `data/qa_test.json` | Câu hỏi + answer kỳ vọng | 50 Q&A |

## Chạy

Máy dev không có numpy/pandas ở Python hệ thống ⇒ venv riêng `eval/.venv` (đã gitignore):

```bash
python3 -m venv eval/.venv
eval/.venv/bin/pip install numpy pandas scipy matplotlib "sqlalchemy>=2" pydantic-settings nbformat nbclient ipykernel jupyterlab
eval/.venv/bin/python eval/test_metrics.py          # metrics.py khớp scipy (kendall τ-b, Wilcoxon, Gini, cosine)
eval/.venv/bin/jupyter lab eval/notebooks/
```

Notebook 06 được **sinh từ mã nguồn** `eval/tools/build_nb06.py` (dễ review hơn JSON) và gọi thẳng thuật toán sản
phẩm qua `eval/roommate_lib.py`. Dữ liệu (đều trong `eval/data/`, gitignored — có PII):

| File | Từ đâu |
|---|---|
| `survey_v2.csv` | `eval/tools/survey_xlsx_to_csv.py` từ file xuất Google Form |
| `ratings.csv` | `docker compose exec -T api python -m app.matching.export_ratings > eval/data/ratings.csv` (sau buổi thử nghiệm) |
| `deck_log.csv` | lệnh in ở notebook 06 mục 8 |
| `.credentials.csv` → `phieu_dang_nhap.html` | `import_survey` → `python3 eval/tools/print_slips.py` |

**Không** in họ tên/email/MSSV trong notebook — output notebook có thể bị commit.

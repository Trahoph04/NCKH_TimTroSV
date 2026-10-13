# Kế Hoạch Kiểm Thử (Test Plan)
## Hệ thống tổng hợp & gợi ý nhà trọ AI — THS2026-66

**Phiên bản:** 1.0 · **Mục tiêu coverage:** ≥60% (nghiệm thu)

---

## 1. Phạm vi & chiến lược

Kim tự tháp test: nhiều unit, vừa integration, ít E2E.

| Tầng | Công cụ | Phạm vi |
|---|---|---|
| Unit | pytest (backend), Vitest (frontend) | Hàm thuần: normalize, dedup, freshness, scoring |
| Integration | pytest + testcontainers/DB thật | API + DB: upsert, query, auth flow |
| E2E | Playwright | Luồng người dùng: tìm kiếm → chi tiết → lưu tin |
| AI eval | notebook (`NCKH/eval/`) | Precision@K, NDCG, Faithfulness, Risk recall |
| Security | OWASP ZAP | SQLi, XSS (Sprint 5) |

---

## 2. Test case theo module

### 2.1 Crawler (đã có — `apps/api/tests/test_crawler.py`)
| ID | Test | Kỳ vọng | TT |
|---|---|---|---|
| TC-CR-01 | parse_list_page từ fixture | 3 item, đúng source_id/url | ✅ |
| TC-CR-02 | parse_price các biến thể VN | 2,5tr→2.5M, 1.8tr→1.8M, 800 nghìn→800K | ✅ |
| TC-CR-03 | parse_area | "25 m²"→25, "20m2"→20 | ✅ |
| TC-CR-04 | parse_amenities | wifi/máy lạnh/WC riêng/để xe = true | ✅ |
| TC-CR-05 | content_hash ổn định + nhạy | cùng input cùng hash; đổi giá → khác | ✅ |
| TC-CR-06 | dedup near-duplicate | 100001≈100003 → còn 2/3 | ✅ |
| TC-CR-07 | freshness decay | 7 ngày → ~0.368 (exp(-1)) | ✅ |
| TC-CR-08 | expired threshold | miss≥2 → expired; flagged giữ nguyên | ✅ |

### 2.2 Auth (Sprint 1)
| ID | Test | Kỳ vọng |
|---|---|---|
| TC-AU-01 | Login sai | 401 "Invalid email or password" |
| TC-AU-02 | Login đúng | 200 + access/refresh token, cookie HTTP-only |
| TC-AU-03 | Empty submission | 400 validate (zod/pydantic) |
| TC-AU-04 | Access token hết hạn → refresh | 200 token mới |
| TC-AU-05 | Truy cập route ✓ không token | 401 |

### 2.3 Search/Listings (Sprint 1-2)
| ID | Test | Kỳ vọng |
|---|---|---|
| TC-LS-01 | Filter giá + quận | chỉ trả tin khớp |
| TC-LS-02 | Sort freshness | tin last_seen mới đứng trước |
| TC-LS-03 | Ẩn expired | status=expired không xuất hiện |
| TC-LS-04 | Nearby bán kính | PostGIS trả đúng trong R |

### 2.4 Recommendation (Sprint 3)
| ID | Test | Kỳ vọng |
|---|---|---|
| TC-RC-01 | Cold-start chưa quiz | fallback popularity, ≥10 item |
| TC-RC-02 | Sau quiz | Precision@10 ≥0.6 (tập mock) |
| TC-RC-03 | Feedback ghi nhận | user_interactions có dòng mới |

### 2.5 Chatbot RAG (Sprint 4)
| ID | Test | Kỳ vọng |
|---|---|---|
| TC-CB-01 | Câu hỏi có data | confidence high + sources |
| TC-CB-02 | Câu hỏi ngoài data | confidence low, KHÔNG bịa (T8) |
| TC-CB-03 | Multi-turn | nhớ ngữ cảnh 5 lượt |

### 2.6 Risk (Sprint 2)
| ID | Test | Kỳ vọng |
|---|---|---|
| TC-RK-01 | Tin scam nhãn truth | recall ≥85% / 100 mẫu |
| TC-RK-02 | Badge reasons | mỗi badge có risk_reasons[] |

---

## 3. Chạy test

```bash
# backend unit (offline, không cần Docker)
cd apps/api && python -m pytest -q

# với coverage
cd apps/api && python -m pytest --cov=app --cov-report=term-missing

# frontend
cd apps/web && npm test

# E2E (cần app chạy)
npx playwright test
```

---

## 4. Tiêu chí Done
- Mọi PR phải pass test hiện có + không giảm coverage.
- Module mới đi kèm unit test trước khi handoff QA.
- AI module: notebook eval đạt ngưỡng nghiệm thu (mục 2.4-2.6).
- Coverage tổng ≥60% trước nghiệm thu (Sprint 5).

> Kết quả thực hiện: xem `docs/report/BaoCao_KiemThu_13-10-2026.md` (645 ca tự động, smoke 3 vai, kiểm thử trình duyệt,
> dựng DB từ volume rỗng, rà soát chất lượng 12–13/10).

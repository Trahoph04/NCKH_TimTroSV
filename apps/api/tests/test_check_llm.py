"""check_llm là công cụ chẩn đoán đụng tới khoá API — test tập trung vào việc KHÔNG làm lộ khoá."""
from app.room_service.chatbot.check_llm import key_hint, mask, redact

KEY = "AIza-khoa-gia-chi-de-test-0000"


def test_mask_never_contains_the_key():
    shown = mask(KEY)
    assert KEY not in shown and KEY[8:] not in shown
    assert shown.startswith("AIza") and str(len(KEY)) in shown


def test_redact_removes_every_occurrence_and_ignores_empty_secrets():
    text = f"API key {KEY} invalid; retried with {KEY}"
    cleaned = redact(text, [KEY, ""])
    assert KEY not in cleaned and cleaned.count("<khoá>") == 2
    assert redact("không có gì", [""]) == "không có gì"


def test_hint_does_not_judge_key_by_shape_and_never_echoes_the_key():
    # cả `AIza…` lẫn `AQ.…` đều là khoá Gemini API hợp lệ (xác nhận 08/10/2026) — không được bảo người dùng "sai dạng"
    for key in ("AQ.khoa-gia-chi-de-test-0000", KEY):
        hint = key_hint(400, "API key not valid. Please pass a valid API key.", key)
        assert "sai dạng" not in hint and "không phải khoá" not in hint
        assert key[:4] in hint                      # chỉ 4 ký tự đầu để nhận diện
        assert key not in hint and key[4:] not in hint  # không bao giờ lặp lại khoá


def test_hint_for_each_status_is_actionable():
    assert "OAuth" in key_hint(401, "", "AQ.xxx")  # 401 chỉ gợi ý nguyên nhân, không khẳng định
    assert "quyền" in key_hint(403, "", KEY)
    assert "GEMINI_MODEL" in key_hint(404, "", KEY)
    assert "quota" in key_hint(429, "", KEY).lower()
    assert key_hint(500, "", KEY) == ""

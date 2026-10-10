"""Kiểm tra nhanh các nhà cung cấp của chatbot (Gemini, Ollama/Qwen, embedding E5) — chạy sau mỗi lần đổi `.env`.

    docker compose exec api python -m app.room_service.chatbot.check_llm          # chỉ hỏi danh sách mô hình
    docker compose exec api python -m app.room_service.chatbot.check_llm --call   # + gọi thử 1 câu ngắn mỗi nhà cung cấp

Vì sao có file này: khoá sai/hết hạn không làm API lỗi — `FallbackResponseGenerator` lặng lẽ rơi sang Qwen/template, nên
chatbot "chạy" nhưng chậm và chất lượng thấp mà không ai biết tại sao. Lệnh này nói thẳng khoá có dùng được không, tên mô
hình trong cấu hình có tồn tại với khoá đó không (tên do Phúc chọn, chưa từng kiểm với khoá của nhóm), và gợi ý mô hình
thay thế. KHÔNG bao giờ in khoá: chỉ 4 ký tự đầu + độ dài; mọi thông báo lỗi từ Google được che khoá trước khi in.
Thoát mã 0 khi có ít nhất một bộ sinh câu trả lời dùng được (Gemini hoặc Qwen), 1 nếu không có cái nào.
"""
from __future__ import annotations

import argparse
import sys
import time

import httpx

from ...config import settings

CALL_PROMPT = "Trả lời đúng một từ tiếng Việt: xin chào"


def mask(key: str) -> str:
    """Nhận diện khoá mà không lộ nó: 4 ký tự đầu + độ dài."""
    return f"{key[:4]}… ({len(key)} ký tự)"


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<khoá>")
    return text


def key_hint(status: int, message: str, key: str) -> str:
    """Nguyên nhân thường gặp theo mã lỗi — để người dùng sửa được mà không phải đọc tài liệu Google."""
    if status == 400 and "API key not valid" in message:
        # Gemini API có cả khoá dạng cũ `AIza…` lẫn dạng mới `AQ.…` (đã gặp 08/10/2026) — KHÔNG suy ra khoá sai từ hình dạng.
        # Nguyên nhân thật gặp ở lần đầu: chuỗi dán kèm ký tự thừa ở đầu/cuối.
        return ("Khoá bị từ chối (sai, đã bị thu hồi, hoặc copy thừa/thiếu ký tự). Copy lại từ aistudio.google.com/apikey, "
                f"không để khoảng trắng hay ký tự lạ ở hai đầu (khoá này bắt đầu `{key[:4]}`, dài {len(key)} ký tự).")
    if status == 401:
        return ("Máy chủ trả 'cần OAuth': khoá không được endpoint Gemini API chấp nhận — có thể là khoá của dịch vụ khác "
                "(vd. Vertex AI/Cloud), đã bị thu hồi hoặc bị cắt bớt khi copy. Tạo lại ở aistudio.google.com/apikey.")
    if status == 403:
        return "Khoá không có quyền: Generative Language API chưa bật cho project, hoặc khoá bị giới hạn theo IP/ứng dụng/vùng."
    if status == 404:
        return "Mô hình không tồn tại với khoá/endpoint này — đổi GEMINI_MODEL sang tên có trong danh sách ở trên."
    if status == 429:
        return "Hết hạn mức (quota) hoặc gọi quá nhanh — chờ rồi thử lại, hoặc xem hạn mức ở AI Studio."
    return ""


def check_gemini(call: bool) -> bool:
    keys = settings.configured_gemini_keys
    print("== Gemini ==")
    if not keys:
        print("  Chưa cấu hình khoá (GEMINI_API_KEY trống) → chatbot dùng Qwen local/câu trả lời mẫu.")
        return False
    wanted = [m for m in dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]) if m]
    print(f"  endpoint: {settings.gemini_base_url}")
    print(f"  mô hình cấu hình: {', '.join(wanted)}")
    ok = False
    for number, key in enumerate(keys, 1):
        print(f"  khoá #{number}: {mask(key)}")
        try:
            listed = httpx.get(f"{settings.gemini_base_url.rstrip('/')}/models", params={"pageSize": 200},
                               headers={"x-goog-api-key": key}, timeout=20)
        except httpx.HTTPError as exc:
            print(f"    ✗ không kết nối được: {type(exc).__name__}")
            continue
        if listed.status_code != 200:
            try:
                message = redact(listed.json().get("error", {}).get("message", ""), keys)
            except ValueError:
                message = ""
            print(f"    ✗ HTTP {listed.status_code}: {message[:200]}")
            hint = key_hint(listed.status_code, message, key)
            if hint:
                print(f"      → {hint}")
            continue
        names = sorted(
            m["name"].removeprefix("models/") for m in listed.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )
        print(f"    ✓ khoá hợp lệ, {len(names)} mô hình hỗ trợ generateContent")
        missing = [m for m in wanted if m not in names]
        for model in wanted:
            print(f"      {'✓' if model in names else '✗ KHÔNG CÓ'} {model}")
        if missing:
            alternatives = [n for n in names if "flash" in n and "preview" not in n and "image" not in n
                            and "tts" not in n and "live" not in n][:8]
            print(f"      → đổi GEMINI_MODEL/GEMINI_FALLBACK_MODEL trong .env. Gợi ý (flash): {', '.join(alternatives) or 'xem danh sách đầy đủ ở AI Studio'}")
        usable = [m for m in wanted if m in names]
        if usable:
            ok = True
        if call and usable:
            started = time.monotonic()
            reply = httpx.post(
                f"{settings.gemini_base_url.rstrip('/')}/models/{usable[0]}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"contents": [{"role": "user", "parts": [{"text": CALL_PROMPT}]}],
                      "generationConfig": {"maxOutputTokens": 32}},
                timeout=60,
            )
            took = time.monotonic() - started
            if reply.status_code == 200:
                parts = reply.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                print(f"      ✓ gọi thử {usable[0]}: {took:.1f}s → {parts[0].get('text', '').strip()[:40]!r}")
            else:
                print(f"      ✗ gọi thử {usable[0]}: HTTP {reply.status_code} {key_hint(reply.status_code, '', key)}")
                ok = False
    return ok


def check_ollama(call: bool) -> bool:
    print("== Qwen qua Ollama ==")
    base = settings.ollama_base_url.rstrip("/")
    try:
        tags = httpx.get(f"{base}/api/tags", timeout=5)
        tags.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"  ✗ không thấy Ollama tại {base} ({type(exc).__name__}) — chạy `ollama serve` trên máy host.")
        return False
    names = {m.get("name") for m in tags.json().get("models", [])}
    if settings.ollama_model not in names:
        print(f"  ✗ chưa có mô hình {settings.ollama_model}; đang có: {', '.join(sorted(n for n in names if n)) or 'không có'}"
              f" → `ollama pull {settings.ollama_model}`")
        return False
    print(f"  ✓ {settings.ollama_model} sẵn sàng tại {base}")
    if call:
        started = time.monotonic()
        reply = httpx.post(f"{base}/api/generate", json={"model": settings.ollama_model, "prompt": CALL_PROMPT,
                                                        "stream": False, "options": {"num_predict": 16}}, timeout=300)
        print(f"      gọi thử: {time.monotonic() - started:.1f}s → {reply.json().get('response', '').strip()[:40]!r}")
    return True


def check_embedding() -> bool:
    print("== Embedding (tìm kiếm ngữ nghĩa) ==")
    from .providers import E5EmbeddingProvider

    result = E5EmbeddingProvider(settings.chatbot_embedding_model).embed_query("phòng trọ gần trường")
    if result.vector is None:
        print(f"  ✗ {result.degraded_reason or 'không nạp được mô hình'} — chatbot chạy BM25, không có tìm kiếm ngữ nghĩa")
        return False
    print(f"  ✓ {settings.chatbot_embedding_model}: vector {len(result.vector)} chiều")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Kiểm tra Gemini / Ollama / embedding của chatbot")
    parser.add_argument("--call", action="store_true", help="gọi thử một câu ngắn (tốn một ít quota/thời gian)")
    args = parser.parse_args()
    print(f"Chế độ chọn mô hình: CHATBOT_LLM_PROVIDER={settings.chatbot_llm_provider}, "
          f"agents={'bật' if settings.chatbot_agents_enabled else 'tắt'}\n")
    gemini = check_gemini(args.call)
    print()
    qwen = check_ollama(args.call)
    print()
    embedding = check_embedding()
    print("\n== Kết luận ==")
    if gemini:
        print("  Gemini dùng được → câu trả lời ưu tiên Gemini, Qwen làm dự phòng.")
    elif qwen:
        print("  Chỉ có Qwen local → câu pháp lý/KTX chậm và hay rơi về câu trả lời mẫu.")
    else:
        print("  Không có mô hình sinh nào → chatbot chỉ trả lời mẫu/trích nguyên văn nguồn.")
    if not embedding:
        print("  Thiếu embedding: chạy `index_corpus` hoặc khởi động lại api nếu vừa tải model.")
    sys.exit(0 if (gemini or qwen) else 1)


if __name__ == "__main__":
    main()

"""Chatbot tìm trọ / KTX / pháp lý thuê trọ — ghép từ branch PHUC (07/10), chỉ phần chatbot.

Module risk/reports/engagement của branch đó KHÔNG ghép (ADR-023); chatbot chỉ đọc
`risk_score`/`risk_evaluated_at` và coi tin chưa chấm risk là trung tính.
"""

from .chatbot import chatbot_router, init_chatbot

__all__ = ["chatbot_router", "init_chatbot"]

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    database_url: str = "postgresql+psycopg://nckh:nckh@db:5432/nckh"
    redis_url: str = "redis://redis:6379/0"

    # bật scheduler crawler trong app (tắt mặc định: dev/test không tự crawl ra mạng)
    crawler_enabled: bool = False

    # auth (Sprint 1.9). Secret THẬT đặt trong .env, KHÔNG commit.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30
    google_client_id: str = ""  # bắt buộc khi dùng Google login

    ors_api_key: str = ""  # OpenRouteService — route time/geometry; rỗng = tắt routing
    google_places_api_key: str = ""  # Places API (New) — review nhà trọ từ Google Maps; rỗng = tắt

    # chat realtime — ảnh gửi trong chat lưu ở <media_dir>/chat (volume docker `media`)
    media_dir: str = "/app/media"
    chat_max_image_mb: int = 8
    chat_max_images_per_message: int = 4

    # chatbot (room_service/chatbot, ghép từ branch PHUC — ADR-023). `auto`: Gemini nếu có key → Qwen
    # qua Ollama trên máy host → câu trả lời template theo nguồn. Thiếu model/LLM thì degrade, không 500.
    chatbot_embedding_model: str = "intfloat/multilingual-e5-small"
    chatbot_confidence_threshold: float = 0.65
    chatbot_max_results: int = 5
    # corpus pháp lý + KTX nằm ở schema riêng do `legal_knowledge.index_corpus` dựng; listing đọc thẳng public
    chatbot_legal_schema: str = Field(default="legal_ctu_v1", pattern=r"^(public|legal_[a-z0-9_]{1,48})$")
    chatbot_listing_schema: str = Field(default="public", pattern=r"^(public|housing_[a-z0-9_]{1,48})$")
    # Graph RAG cần catalog housing_* + graph_* của branch PHUC — chưa dựng ở repo này
    chatbot_graph_enabled: bool = False
    chatbot_graph_schema: str = Field(default="graph_rag_v1", pattern=r"^graph_[a-z0-9_]{1,48}$")
    # agent (Gemini phân tích → Qwen chọn nguồn → Gemini tổng hợp) cần key Gemini
    chatbot_agents_enabled: bool = False
    chatbot_question_analysis_model: str = "gemini-3.1-flash-lite"
    chatbot_question_analysis_timeout_seconds: float = Field(default=30, gt=0, le=120)
    chatbot_answer_synthesis_enabled: bool = True
    chatbot_answer_synthesis_model: str = ""  # rỗng = GEMINI_MODEL
    chatbot_answer_synthesis_timeout_seconds: float = Field(default=60, gt=0, le=180)
    chatbot_llm_provider: Literal["auto", "qwen", "gemini", "template"] = "auto"
    chatbot_llm_timeout_seconds: float = 60.0
    chatbot_legal_timeout_seconds: float = Field(default=180.0, gt=0, le=300)
    chatbot_max_output_tokens: int = Field(default=1536, ge=128, le=4096)
    chatbot_warmup_enabled: bool = True
    chatbot_warmup_timeout_seconds: float = Field(default=30, gt=0, le=120)

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_context_length: int = 8192
    ollama_keep_alive: str = "30m"

    # Key THẬT chỉ đặt trong .env. Nhiều key = xoay vòng khi một key hết quota.
    gemini_api_key: str = ""
    gemini_api_key_1: SecretStr = SecretStr("")
    gemini_api_key_2: SecretStr = SecretStr("")
    gemini_api_key_3: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_min_request_interval_seconds: float = Field(default=5.0, ge=0, le=60)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def configured_gemini_keys(self) -> list[str]:
        # key mới nhất trước; giữ tương thích GEMINI_API_KEY đơn
        values = [self.gemini_api_key_3.get_secret_value(), self.gemini_api_key_2.get_secret_value(),
                  self.gemini_api_key_1.get_secret_value(), self.gemini_api_key]
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


settings = Settings()

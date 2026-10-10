import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from uuid import UUID
from sqlalchemy.engine import Engine

from ...config import settings
from ...auth import get_current_user
from ...auth.schemas import UserOut
from ...ratelimit import check_rate
from sqlalchemy import text
from .providers import (
    E5EmbeddingProvider,
    FallbackResponseGenerator,
    GeminiGenerator,
    GroundedTemplateGenerator,
    OllamaQwenGenerator,
)
from .repo import ChatRepository
from .schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatFeedbackCreate,
    ChatFeedbackOut,
    ChatConversationList,
    ChatConversationDetail,
)
from .service import ChatService

# /chatbot, không phải /chat như branch PHUC: /chat/conversations… đã là chat realtime ghép bạn (ADR-023).
router = APIRouter(prefix="/chatbot", tags=["chatbot"])
_service: ChatService | None = None


def init_chatbot(engine: Engine) -> None:
    global _service
    providers = []
    degraded_reasons: list[str] = []

    if settings.chatbot_agents_enabled or settings.chatbot_llm_provider in ("auto", "qwen"):
        providers.append(
            OllamaQwenGenerator(
                settings.ollama_base_url,
                settings.ollama_model,
                settings.chatbot_llm_timeout_seconds,
                context_length=settings.ollama_context_length,
                max_output_tokens=settings.chatbot_max_output_tokens,
                keep_alive=settings.ollama_keep_alive,
                legal_timeout_seconds=settings.chatbot_legal_timeout_seconds,
                legal_answer_mode='source_select' if settings.chatbot_agents_enabled else 'synthesize',
            )
        )

    if not settings.chatbot_agents_enabled and settings.chatbot_llm_provider in ("auto", "gemini"):
        if settings.configured_gemini_keys:
            for model in dict.fromkeys([settings.gemini_model, settings.gemini_fallback_model]):
                if not model:
                    continue
                providers.append(GeminiGenerator(
                    settings.configured_gemini_keys[0],
                    model,
                    settings.gemini_base_url,
                    settings.chatbot_llm_timeout_seconds,
                    max_output_tokens=settings.chatbot_max_output_tokens,
                    api_keys=settings.configured_gemini_keys,
                    legal_timeout_seconds=settings.chatbot_legal_timeout_seconds,
                    min_request_interval_seconds=settings.gemini_min_request_interval_seconds,
                ))
        elif settings.chatbot_llm_provider == "gemini":
            degraded_reasons.append(
                "Gemini được chọn nhưng chưa cấu hình key"
            )

    providers.sort(key=lambda provider: 0 if isinstance(provider, GeminiGenerator) else 1)
    generator = FallbackResponseGenerator(providers, GroundedTemplateGenerator(), initial_degraded_reasons=degraded_reasons)
    analyzer = None
    if settings.chatbot_agents_enabled:
        from .agents import QuestionAnalysisAgent, QwenAnswerAgent
        analysis_client = GeminiGenerator("", settings.chatbot_question_analysis_model,
            base_url=settings.gemini_base_url, api_keys=settings.configured_gemini_keys,
            legal_timeout_seconds=settings.chatbot_question_analysis_timeout_seconds,
            per_request_timeout_seconds=settings.chatbot_question_analysis_timeout_seconds,
            min_request_interval_seconds=settings.gemini_min_request_interval_seconds) if settings.configured_gemini_keys else None
        analyzer = QuestionAnalysisAgent(analysis_client)
        if settings.chatbot_answer_synthesis_enabled:
            from .agent_workflow import GeminiAnswerSynthesisAgent, LegalAgentWorkflow
            synthesis_client = GeminiGenerator("",
                settings.chatbot_answer_synthesis_model or settings.gemini_model,
                base_url=settings.gemini_base_url, api_keys=settings.configured_gemini_keys,
                legal_timeout_seconds=settings.chatbot_answer_synthesis_timeout_seconds,
                per_request_timeout_seconds=settings.chatbot_answer_synthesis_timeout_seconds,
                min_request_interval_seconds=settings.gemini_min_request_interval_seconds)
            generator = LegalAgentWorkflow(generator, GeminiAnswerSynthesisAgent(synthesis_client), synthesis_client)
        else:
            generator = QwenAnswerAgent(generator, verifier=analysis_client)
    _service = ChatService(
        _repository(engine),
        E5EmbeddingProvider(settings.chatbot_embedding_model),
        generator,
        confidence_threshold=settings.chatbot_confidence_threshold,
        max_results=settings.chatbot_max_results,
        question_analyzer=analyzer,
    )


def _repository(engine: Engine):
    if settings.chatbot_graph_enabled:
        from .graph_retrieval import GraphChatRepository
        return GraphChatRepository(engine, settings.chatbot_legal_schema,
                                   settings.chatbot_listing_schema, settings.chatbot_graph_schema)
    return ChatRepository(engine, settings.chatbot_legal_schema, settings.chatbot_listing_schema)


def get_service() -> ChatService:
    if _service is None:
        raise HTTPException(503, "Chatbot chưa khởi tạo")
    return _service


def warmup_chatbot() -> None:
    service = get_service()
    for provider in service.generator.providers:
        if isinstance(provider, OllamaQwenGenerator):
            try:
                provider.warmup(settings.chatbot_warmup_timeout_seconds)
            except Exception:
                logging.getLogger(__name__).warning("Chat model warmup unavailable")
    try:
        service.embedder.warmup()
    except Exception:
        logging.getLogger(__name__).info("Embedding warmup skipped; model not available locally")


def close_chatbot() -> None:
    if _service:
        for provider in _service.generator.providers:
            if hasattr(provider, "close"):
                provider.close()
        clients = [getattr(_service.question_analyzer, 'client', None),
                   getattr(_service.generator, 'verifier', None),
                   getattr(getattr(_service.generator, 'writer', None), 'client', None)]
        unique_clients = {id(client): client for client in clients if client is not None}
        for client in unique_clients.values():
            client.close()


@router.post("/ask", response_model=ChatAskResponse)
def ask_chatbot(
    body: ChatAskRequest,
    user: UserOut = Depends(get_current_user),
    service: ChatService = Depends(get_service),
):
    check_rate("chatbot", user.id)
    if body.include_evaluation_contexts and user.role != "admin":
        raise HTTPException(403, "Chỉ admin được lấy dữ liệu đánh giá")
    from .history import ask_with_history
    return ask_with_history(service, user.id, body)


@router.get("/conversations", response_model=ChatConversationList)
def list_conversations(
    user: UserOut = Depends(get_current_user), service: ChatService = Depends(get_service),
    limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
):
    from .history import ChatHistoryStore
    return ChatHistoryStore(service.repo.engine).conversations(user.id, limit, offset)


@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetail)
def read_conversation(
    conversation_id: UUID, user: UserOut = Depends(get_current_user),
    service: ChatService = Depends(get_service), limit: int = Query(50, ge=1, le=100),
    before_id: int | None = Query(None, gt=0),
):
    from .history import ChatHistoryStore
    return ChatHistoryStore(service.repo.engine).conversation(user.id, conversation_id, limit, before_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: UUID, user: UserOut = Depends(get_current_user),
    service: ChatService = Depends(get_service),
):
    from .history import ChatHistoryStore
    ChatHistoryStore(service.repo.engine).delete(user.id, conversation_id)
    return Response(status_code=204)


@router.post("/feedback", response_model=ChatFeedbackOut, status_code=201)
def submit_chat_feedback(
    body: ChatFeedbackCreate, user: UserOut = Depends(get_current_user)
):
    """Anonymous-safe feedback: no message content and no client-supplied user id."""
    if _service is None:
        raise HTTPException(503, "Chatbot chưa khởi tạo")
    check_rate("chatbot_feedback", user.id)
    with _service.repo.engine.connect() as conn:
        owned = conn.execute(
            text("SELECT 1 FROM chatbot_events WHERE id=:id AND user_id=:uid"),
            {"id": body.event_id, "uid": user.id},
        ).first()
    if not owned:
        raise HTTPException(404, "Không tìm thấy lượt chat của bạn")
    feedback_id = _service.repo.add_feedback(body.model_dump())
    return ChatFeedbackOut(id=feedback_id)

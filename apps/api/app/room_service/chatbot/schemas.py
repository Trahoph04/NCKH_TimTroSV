from typing import Any, Literal
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ChatFilters(BaseModel):
    max_price_exclusive: bool = False
    sort_by: Literal["price_asc"] | None = None
    listing_ids: list[int] = Field(default_factory=list, max_length=5)
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    min_area: float | None = Field(default=None, ge=0)
    district: str | None = None
    amenities: list[str] = Field(default_factory=list)
    gender: str | None = None
    max_distance_ctu: float | None = Field(default=None, ge=0)
    max_route_minutes: float | None = Field(default=None, ge=0)
    listing_type: str | None = None

    @model_validator(mode="after")
    def validate_price_range(self):
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price không được lớn hơn max_price")
        return self


class ChatConversationState(BaseModel):
    filters: ChatFilters = Field(default_factory=ChatFilters)
    listing_ids: list[int] = Field(default_factory=list, max_length=5)
    selected_listing_id: int | None = Field(default=None, gt=0)


class ChatAskRequest(BaseModel):
    """Authenticated turns may belong to a saved conversation."""

    conversation_id: UUID | None = None

    message: str = Field(min_length=2, max_length=2000)
    filters: ChatFilters | None = None
    conversation_state: ChatConversationState | None = None
    conversation_history: list["ChatHistoryMessage"] = Field(
        default_factory=list, max_length=10
    )
    include_evaluation_contexts: bool = False


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatListing(BaseModel):
    id: int
    corpus_schema: str = "public"
    title: str
    price: int | None = None
    area: float | None = None
    address: str | None = None
    district: str | None = None
    amenities: dict[str, Any] = Field(default_factory=dict)
    distance_to_ctu: float | None = None
    route_time_campus: list[float] | None = None
    source: str
    source_url: str | None = None
    similarity_score: float = 0.0
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rank: int = 0
    match_reasons: list[str] = Field(default_factory=list)
    risk_score: float | None = None
    risk_level: str = "unknown"


class ChatSource(BaseModel):
    kind: Literal["listing", "legal_document"] = "listing"
    listing_id: int | None = None
    document_id: int | None = None
    chunk_id: int | None = None
    rank: int
    similarity_score: float
    title: str
    source: str
    source_url: str | None = None
    source_path: str | None = None
    category: str | None = None
    page_kind: Literal['physical_pdf', 'logical_document', 'web_excerpt', 'editorial_guidance'] | None = None
    page_from: int | None = None
    page_to: int | None = None
    heading: str | None = None
    excerpt: str | None = Field(default=None, max_length=1801)


class ChatEvaluationContext(BaseModel):
    kind: Literal["listing", "legal_document"] = "listing"
    listing_id: int | None = None
    chunk_id: int | None = None
    rank: int
    content: str


class ChatFeedbackCreate(BaseModel):
    event_id: int = Field(gt=0)
    rating: Literal[-1, 1]
    reason: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=1000)


class ChatFeedbackOut(BaseModel):
    id: int
    accepted: bool = True


class ChatAskResponse(BaseModel):
    conversation_id: UUID | None = None
    turn_id: int | None = None
    reused_answer: bool = False
    agent_trace: list[dict] = Field(default_factory=list)
    corpus_schema: str | None = None
    partial_answer: bool = False
    conversation_state: ChatConversationState | None = None
    applied_filters: ChatFilters | None = None
    citation_applicable: bool = False
    answer: str
    intent: str
    confidence: float
    listings: list[ChatListing] = Field(default_factory=list, max_length=5)
    sources: list[ChatSource] = Field(default_factory=list, max_length=5)
    no_answer: bool = False
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    retrieval_mode: str = "hybrid"
    generation_provider: str = "template"
    generation_model: str | None = None
    latency_ms: int
    event_id: int | None = None
    citation_accuracy: float = Field(default=0, ge=0, le=1)
    evaluation_contexts: list[ChatEvaluationContext] = Field(default_factory=list)


class ChatConversationSummary(BaseModel):
    id: UUID
    title: str
    updated_at: datetime
    turn_count: int


class ChatConversationList(BaseModel):
    items: list[ChatConversationSummary]
    has_more: bool


class ChatSavedTurn(BaseModel):
    id: int
    question: str
    response: ChatAskResponse
    created_at: datetime


class ChatConversationDetail(BaseModel):
    id: UUID
    title: str
    turns: list[ChatSavedTurn]
    has_more: bool

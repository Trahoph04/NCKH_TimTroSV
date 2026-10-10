"""Persist private conversations and reuse independent public answers.

The generation workflow stays stateless. History, ownership and cache checks
live at the HTTP boundary; short follow-ups use server-loaded context.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
import time
import unicodedata
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import text

from ...config import settings
from .parser import parse_query
from .schemas import ChatAskRequest, ChatAskResponse, ChatHistoryMessage, ChatConversationState
from .service import rewrite_query
from .providers import normalize_text


def normalized_question(value: str) -> str:
    # Keep accents, numbers and punctuation: similar wording is not necessarily
    # the same question. NFC accommodates Vietnamese combining characters.
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def answer_key(body: ChatAskRequest) -> tuple[str, bool]:
    resolved = rewrite_query(body.message, body.conversation_history)
    legal = parse_query(resolved).intent == "legal_question"
    if legal and resolved == body.message:
        # A self-contained legal/KTX question is independent of the earlier
        # conversation; repeating it in the same conversation should hit cache.
        return digest({"question": normalized_question(body.message), "legal": True,
                       "filters": body.filters.model_dump() if body.filters else None}), True
    context = body.model_dump(mode="json", exclude={"conversation_id", "include_evaluation_contexts"})
    context["message"] = normalized_question(body.message)
    return digest(context), legal


def reusable(result: ChatAskResponse) -> bool:
    if result.generation_provider in {"template", "legal-insufficient", "rule"}:
        return False
    if result.intent == "legal_question":
        if not result.sources or (result.no_answer and not result.partial_answer):
            return False
        checks = [step for step in result.agent_trace if step.get("agent") == "source_verification"]
        rules = [step for step in result.agent_trace if step.get("agent") == "citation_and_rule_checks"]
        if rules and rules[-1].get("status") != "accepted":
            return False
        if checks:
            final = checks[-1]
            if final.get("status") == "accepted":
                return True
            # ChatService already discarded the rejected claims and checked
            # the retained answer again. Only that final subset is reusable.
            return bool(result.partial_answer and final.get("status") == "partial_retained"
                        and final.get("retained_claim_ids") and rules
                        and rules[-1].get("status") == "accepted")
        return result.generation_provider == "legal-extractive" and not result.degraded
    return bool(result.listings) and not result.degraded and not result.no_answer


def shared_answer_key(body: ChatAskRequest) -> str | None:
    """Conservative admission: no conversational context or personal details."""
    if body.include_evaluation_contexts or body.conversation_history or body.conversation_state:
        return None
    value = normalize_text(body.message)
    if re.search(r"\b(toi|minh|em|ban toi|cua ban|ten|cccd|cmnd|mssv|email|sdt|dien thoai|dia chi)\b", value):
        return None
    if re.search(r"@|https?://|\b\d[\d .-]{7,}\d\b", body.message, re.I):
        return None
    if any(marker in value for marker in ("phong do", "quy dinh nay", "dieu khoan nay", "muc phat nay", "ap dung tu khi nao", "trong so do")):
        return None
    if body.filters and body.filters.listing_ids:
        return None
    return digest({"question": normalized_question(body.message),
                   "filters": body.filters.model_dump() if body.filters else None})


def public_answer(result: ChatAskResponse) -> dict:
    # Never copy another user's conversation, event, trace or evaluation context.
    fields = {"answer", "intent", "confidence", "listings", "sources", "no_answer", "degraded",
              "retrieval_mode", "generation_provider", "generation_model", "citation_accuracy",
              "citation_applicable", "partial_answer", "corpus_schema", "applied_filters"}
    return result.model_dump(mode="json", include=fields) | {"latency_ms": 0}


class ChatHistoryStore:
    def __init__(self, engine):
        self.engine = engine

    def _owned(self, conn, user_id, conversation_id, *, lock=False):
        row = conn.execute(text(
            "SELECT id, title FROM chatbot_conversations WHERE id=:id AND user_id=:uid"
            + (" FOR UPDATE" if lock else "")
        ), {"id": conversation_id, "uid": user_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "Không tìm thấy cuộc trò chuyện của bạn")
        return row

    def context(self, user_id, conversation_id):
        with self.engine.connect() as conn:
            self._owned(conn, user_id, conversation_id)
            rows = conn.execute(text(
                "SELECT question, response FROM chatbot_turns WHERE conversation_id=:id ORDER BY id DESC LIMIT 5"
            ), {"id": conversation_id}).mappings().all()
        history = []
        state = None
        for row in reversed(rows):
            history.extend([ChatHistoryMessage(role="user", content=row["question"][:2000]),
                            ChatHistoryMessage(role="assistant", content=row["response"]["answer"][:2000])])
            state = row["response"].get("conversation_state") or state
        return history, state

    def scope(self, repo, *, legal):
        # Settings contain validated schema identifiers. Corpus content and
        # timestamps invalidate answers even if a schema is reindexed in place.
        schema = repo.legal_schema if legal else repo.listing_schema
        with self.engine.connect() as conn:
            if legal:
                revision = conn.execute(text(
                    f"SELECT md5(string_agg(id::text || content_sha256 || status || admin_enabled::text || updated_at::text, ',' ORDER BY id)) "
                    f"FROM {schema}.legal_documents"
                )).scalar_one()
            else:
                revision = tuple(conn.execute(text(
                    f"SELECT count(*), max(updated_at), max(last_seen) FROM {schema}.aggregated_listings"
                )).one())
        config = {key: value for key, value in settings.model_dump().items()
                  if key.startswith("chatbot_") or key in {"gemini_model", "gemini_fallback_model", "ollama_model"}}
        return digest({"pipeline": "gemini-qwen-shared-v3", "schema": schema, "config": config, "revision": revision,
                       "day": datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()})

    def cached(self, user_id, key, scope):
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT t.response FROM chatbot_turns t JOIN chatbot_conversations c ON c.id=t.conversation_id "
                "WHERE c.user_id=:uid AND t.cache_key=:key AND t.cache_scope=:scope "
                "AND t.cache_expires_at>now() ORDER BY t.id DESC LIMIT 1"
            ), {"uid": user_id, "key": key, "scope": scope}).first()
        return ChatAskResponse.model_validate(row[0]) if row else None

    def shared_cached(self, key, scope):
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT response FROM chatbot_shared_answers WHERE cache_key=:key AND cache_scope=:scope "
                "AND expires_at>now()"
            ), {"key": key, "scope": scope}).first()
        if row is None:
            return None
        result = ChatAskResponse.model_validate(row[0])
        if result.listings:
            from .schemas import ChatFilters
            ids = [item.id for item in result.listings]
            result.conversation_state = ChatConversationState(
                filters=result.applied_filters or ChatFilters(), listing_ids=ids, selected_listing_id=ids[0])
        return result

    def save_shared(self, key, scope, result, ttl_seconds):
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM chatbot_shared_answers WHERE expires_at<=now()"))
            conn.execute(text(
                "INSERT INTO chatbot_shared_answers (cache_key,cache_scope,response,expires_at) "
                "VALUES (:key,:scope,CAST(:response AS jsonb),:expires) "
                "ON CONFLICT (cache_key,cache_scope) DO UPDATE SET response=EXCLUDED.response, "
                "expires_at=EXCLUDED.expires_at,created_at=now()"
            ), {"key": key, "scope": scope, "response": json.dumps(public_answer(result), ensure_ascii=False),
                "expires": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)})

    def save(self, user_id, body, result, key, scope, ttl_seconds):
        conversation_id = body.conversation_id or uuid4()
        with self.engine.begin() as conn:
            if body.conversation_id:
                self._owned(conn, user_id, conversation_id, lock=True)
            else:
                conn.execute(text(
                    "INSERT INTO chatbot_conversations (id,user_id,title) VALUES (:id,:uid,:title)"
                ), {"id": conversation_id, "uid": user_id, "title": body.message.strip()[:120]})
            result.conversation_id = conversation_id
            stored = result.model_dump(mode="json", exclude={"evaluation_contexts", "turn_id"})
            turn_id = conn.execute(text(
                "INSERT INTO chatbot_turns (conversation_id,question,response,cache_key,cache_scope,cache_expires_at) "
                "VALUES (:id,:question,CAST(:response AS jsonb),:key,:scope,:expires) RETURNING id"
            ), {"id": conversation_id, "question": body.message, "response": json.dumps(stored, ensure_ascii=False),
                "key": key if reusable(result) else None, "scope": scope,
                "expires": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)}).scalar_one()
            result.turn_id = turn_id
            conn.execute(text("UPDATE chatbot_conversations SET updated_at=now() WHERE id=:id"), {"id": conversation_id})
        return result

    def conversations(self, user_id, limit, offset):
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT c.id,c.title,c.updated_at,(SELECT count(*) FROM chatbot_turns t WHERE t.conversation_id=c.id) AS turn_count "
                "FROM chatbot_conversations c WHERE c.user_id=:uid ORDER BY c.updated_at DESC,c.id "
                "LIMIT :limit OFFSET :offset"
            ), {"uid": user_id, "limit": limit + 1, "offset": offset}).mappings().all()
        return {"items": [dict(row) for row in rows[:limit]], "has_more": len(rows) > limit}

    def conversation(self, user_id, conversation_id, limit, before_id):
        with self.engine.connect() as conn:
            conversation = dict(self._owned(conn, user_id, conversation_id))
            rows = conn.execute(text(
                "SELECT id,question,response,created_at FROM chatbot_turns WHERE conversation_id=:id "
                "AND (CAST(:before AS bigint) IS NULL OR id<CAST(:before AS bigint)) ORDER BY id DESC LIMIT :limit"
            ), {"id": conversation_id, "before": before_id, "limit": limit + 1}).mappings().all()
        conversation.update(turns=[dict(row) for row in reversed(rows[:limit])], has_more=len(rows) > limit)
        return conversation

    def delete(self, user_id, conversation_id):
        with self.engine.begin() as conn:
            self._owned(conn, user_id, conversation_id, lock=True)
            conn.execute(text("DELETE FROM chatbot_conversations WHERE id=:id AND user_id=:uid"),
                         {"id": conversation_id, "uid": user_id})


def ask_with_history(service, user_id: int, body: ChatAskRequest) -> ChatAskResponse:
    started = time.perf_counter()
    store = ChatHistoryStore(service.repo.engine)
    effective = body
    if body.conversation_id:
        history, state = store.context(user_id, body.conversation_id)
        effective = body.model_copy(update={"conversation_history": history,
            "conversation_state": ChatConversationState.model_validate(state) if state else None})
        # Validate the deserialized state, including listing id limits.
        effective = ChatAskRequest.model_validate(effective.model_dump())
    key, legal = answer_key(effective)
    scope = store.scope(service.repo, legal=legal)
    shared_key = shared_answer_key(effective)
    provider = "user_history"
    result = None if body.include_evaluation_contexts else store.cached(user_id, key, scope)
    if result is None and shared_key:
        result = store.shared_cached(shared_key, scope)
        provider = "shared_cache"
    if result is None:
        result = service.ask(effective)
        if shared_key and reusable(result):
            store.save_shared(shared_key, scope, result, 86400 if legal else 300)
    else:
        result.reused_answer = True
        result.latency_ms = round((time.perf_counter() - started) * 1000)
        result.agent_trace.append({"agent": "saved_answer", "provider": provider, "status": "reused"})
        # A repeated turn receives its own event for ratings and telemetry.
        result.event_id = service.repo.record_event({
            "intent": result.intent, "confidence": result.confidence, "no_answer": result.no_answer,
            "degraded": result.degraded, "retrieval_mode": result.retrieval_mode,
            "generation_provider": result.generation_provider, "result_count": len(result.listings) or len(result.sources),
            "latency_ms": result.latency_ms,
        })
    if result.event_id:
        with service.repo.engine.begin() as conn:
            conn.execute(text("UPDATE chatbot_events SET user_id=:uid WHERE id=:id"),
                         {"uid": user_id, "id": result.event_id})
    # Reuse does not extend the cache's age indefinitely: only fresh generation
    # becomes a cache candidate. Every repeated question is still saved.
    return store.save(user_id, body, result, None if result.reused_answer or body.include_evaluation_contexts else key,
                      scope, 86400 if legal else 300)

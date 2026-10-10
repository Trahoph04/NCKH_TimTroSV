from __future__ import annotations

import re
import json
import time
from dataclasses import replace

from .parser import merge_filters, parse_query
from .scope import EMERGENCY_ANSWERS, comparative_updates, emergency_kind, out_of_area_answer, out_of_area_place
from .providers import EmbeddingProvider, ResponseGenerator, GroundedTemplateGenerator, normalize_text, GenerationResult
from .repo import ChatRepository
from .legal_retrieval import evidence_issues, expand_legal_query, append_commencement_evidence, legal_completion_status
from .legal_answer import extract_legal_answer, extract_partial_provisions
from .schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatEvaluationContext,
    ChatHistoryMessage,
    ChatListing,
    ChatSource,
    ChatConversationState,
    ChatFilters,
)

FOLLOW_UP_MARKERS = (
    "phòng vừa", "phòng đó", "phòng nào rẻ nhất", "các phòng vừa", "các tin vừa", "tất cả điều kiện",
    "còn phòng nào",
    "rẻ hơn",
    "gần hơn",
    "rộng hơn",
    "phòng đầu",
    "phòng thứ",
    "trong số đó",
    "có máy lạnh không",
)


def rewrite_query(message: str, history: list[ChatHistoryMessage | dict]) -> str:
    """Resolve short follow-ups from at most five client-side turns."""
    if not history:
        return message
    if any(marker in message.lower() for marker in ("quy định này", "điều khoản này", "mức phạt này", "áp dụng từ khi nào")):
        for item in reversed(history[-10:]):
            role = item.role if isinstance(item, ChatHistoryMessage) else item.get("role")
            content = item.content if isinstance(item, ChatHistoryMessage) else item.get("content", "")
            if role == "user":
                if parse_query(content).intent == "legal_question":
                    return f"Câu hỏi pháp lý trước: {content}. Câu hỏi tiếp theo: {message}"
                break
    if parse_query(message).intent in {"out_of_scope", "legal_question"}:
        return message
    normalized = message.strip().lower()
    is_follow_up = len(normalized.split()) <= 8 or any(
        marker in normalized for marker in FOLLOW_UP_MARKERS
    )
    if not is_follow_up:
        return message
    previous_users: list[str] = []
    for item in history[-10:]:
        role = item.role if isinstance(item, ChatHistoryMessage) else item.get("role")
        content = (
            item.content
            if isinstance(item, ChatHistoryMessage)
            else item.get("content")
        )
        if role == "user" and content:
            previous_users.append(str(content))
    if not previous_users:
        return message
    return f"{' . '.join(previous_users[-5:])}. Yêu cầu tiếp theo: {message}"


def _risk_level(item: dict) -> str:
    if item.get("risk_evaluated_at") is None:
        return "unknown"
    score = float(item.get("risk_score") or 0.0)
    if score < 0.3:
        return "safe"
    if score < 0.6:
        return "caution"
    return "suspicious"


def _citation_accuracy(answer: str, listings: list[dict]) -> float:
    if not listings:
        return 0.0
    # Bracketed numbers inside copied legal quotations are document footnotes,
    # e.g. [98], rather than a citation to retrieval rank 98.
    citation_text = re.sub(r"“[^”]*”", "", answer, flags=re.S)
    citations = [int(value) for value in re.findall(r"\[(\d+)\]", citation_text)]
    if not citations:
        return 0.0
    valid = {int(item["rank"]) for item in listings}
    return round(sum(citation in valid for citation in citations) / len(citations), 4)


def _evaluation_context(item: dict) -> str:
    amenities = ", ".join(
        key
        for key, enabled in (item.get("parsed_amenities") or {}).items()
        if enabled is True
    )
    return " | ".join(
        str(value)
        for value in (
            item.get("title"),
            item.get("price"),
            item.get("area"),
            item.get("address") or item.get("district"),
            amenities,
            item.get("description"),
            item.get("last_seen"),
            item.get("updated_at"),
        )
        if value not in (None, "")
    )


def listing_evidence_issues(answer: str, listings: list[dict]) -> list[str]:
    """Reject unsupported listing numbers, names, and attribute assertions."""
    from .parser import AMENITIES
    issues = []
    sources = {int(item["rank"]): item for item in listings}
    for segment in re.split(r"\n+|(?<=[.!?])\s+", answer):
        refs = [int(value) for value in re.findall(r"\[(\d+)\]", segment)]
        if not refs:
            if re.search(r"\d+\s*(?:triệu|đồng|m²|m2|km)", segment):
                issues.append("Số liệu tin trọ chưa gắn nguồn.")
            continue
        rows = [sources[ref] for ref in refs if ref in sources]
        text = normalize_text(segment)
        if "ten phong" in text or "ten nha" in text:
            issues.append("Câu trả lời dùng tên phòng giữ chỗ.")
        if not any(term in text for term in ("chua", "khong", "can xac nhan", "kiem tra")):
            for phrase, key in AMENITIES.items():
                if phrase in text and not any((row.get("parsed_amenities") or {}).get(key) is True or phrase in normalize_text(str(row.get("description") or "")) for row in rows):
                    issues.append("Tiện ích khẳng định chưa có trong tin được trích dẫn.")
        for match in re.finditer(r"(\d+(?:[.,]\d+)?)\s*triệu", segment, re.I):
            amount = round(float(match[1].replace(",", ".")) * 1_000_000)
            if not any(row.get("price") == amount for row in rows):
                issues.append("Giá nêu trong câu trả lời khác giá nguồn.")
    return list(dict.fromkeys(issues))


class ChatService:
    """Stateless orchestration: parse, hybrid retrieve, rerank, answer."""

    def __init__(
        self,
        repo: ChatRepository,
        embedder: EmbeddingProvider,
        generator: ResponseGenerator,
        confidence_threshold: float = 0.65,
        max_results: int = 5,
        question_analyzer=None,
    ):
        self.repo = repo
        self.embedder = embedder
        self.generator = generator
        self.confidence_threshold = confidence_threshold
        self.max_results = min(max_results, 5)
        self.question_analyzer = question_analyzer

    def _ask_legal(
        self,
        query: str,
        body: ChatAskRequest,
        started: float,
    ) -> ChatAskResponse:
        degraded_reasons: list[str] = []
        agent_trace = []
        question_plan = None
        generation_trace = []
        if self.question_analyzer is not None:
            from .agents import LegalRetrievalAgent
            analyzed = self.question_analyzer.analyze(query)
            question_plan = analyzed.plan
            degraded_reasons.extend(analyzed.degraded_reasons)
            agent_trace.append(analyzed.step)
            chunks, embedded, step = LegalRetrievalAgent(self.repo, self.embedder, self.max_results).retrieve(query, analyzed.plan)
            agent_trace.append(step)
        else:
            embedded = self.embedder.embed_query(query)
            chunks = self.repo.retrieve_legal(query, embedded.vector, limit=self.max_results)
        if embedded.degraded_reason:
            degraded_reasons.append(embedded.degraded_reason)
        if not chunks:
            # Second pass uses lexical retrieval with legal vocabulary even if
            # the query embedding failed or the semantic pool was irrelevant.
            chunks = self.repo.retrieve_legal(expand_legal_query(query), None, limit=self.max_results)
        retrieval_mode = (
            "legal_hybrid" if embedded.vector is not None else "legal_lexical"
        )
        if getattr(self.repo, "graph_enabled", False):
            retrieval_mode = "legal_graph_hybrid" if embedded.vector is not None else "legal_graph_lexical"
            if chunks and chunks[0].get("_graph_trace"):
                agent_trace.append(chunks[0]["_graph_trace"])
        top_score = float(chunks[0]["similarity_score"]) if chunks else 0.0
        confidence = min(0.97, 0.22 + 0.75 * top_score) if chunks else 0.0
        # Legal BM25 scores are normalized inside the candidate corpus and should
        # not inherit the stricter listing recommendation threshold.
        if confidence < self.confidence_threshold:
            chunks = []
        if hasattr(self.generator, 'generate_legal'):
            generated = self.generator.generate_legal(query, chunks, question_plan=question_plan)
        else:
            generated = (extract_legal_answer(query, chunks) if self.question_analyzer is None else None) or self.generator.generate(query, chunks, context_kind="legal")
        generation_trace.extend(generated.agent_trace)
        # Synthesized claims may use only the selected evidence, not other
        # retrieved rows that Qwen omitted. Keep original ranks for the UI.
        verification_chunks = list(generated.selected_evidence) or chunks
        attempted_provider, attempted_model = generated.provider, generated.model
        # Record verification in the same per-request stream as generation so
        # a repair appears after its rejection, in execution order.
        verification_trace = generation_trace
        if chunks and generated.provider != "template" and not generated.literal_source_answer:
            generated = replace(generated, text=append_commencement_evidence(generated.text, verification_chunks, query))
        issues = evidence_issues(generated.text_for_verification, verification_chunks, query, claim_records=generated.claim_records) if chunks and not generated.literal_source_answer else []
        if generated.literal_source_answer:
            verification_trace.append({'agent':'source_verification','provider':'exact_source_match',
                'status':'accepted','scope':'verbatim source text only; no legal application inferred'})
        repairable = bool(issues)
        deterministic_issues = list(issues)
        from .claim_verification import identify_rule_issues
        rule_records = identify_rule_issues(issues, generated, verification_chunks) if generated.claim_records else []
        if rule_records:
            issues = [json.dumps(r, ensure_ascii=False) for r in rule_records]
        checked = None
        def verify(current):
            kwargs = {'claim_records': current.claim_records} if getattr(self.generator, 'supports_claim_records', False) else {}
            return self.generator.check_legal_evidence(query, current.text_for_verification, verification_chunks, **kwargs)
        if chunks and not generated.literal_source_answer and generated.provider not in {"template", "legal-extractive", "legal-insufficient"} and hasattr(self.generator, "check_legal_evidence"):
            checked = verify(generated)
            if hasattr(checked,'trace'):
                verification_trace.append(checked.trace)
                degraded_reasons.extend(checked.degraded_reasons)
            issues.extend(checked)
            repairable = repairable or (bool(checked) and not getattr(checked, "unavailable", False))
        if issues and repairable and generated.provider not in {"template", "legal-extractive", "legal-insufficient"}:
            if generated.source_fallback is not None and hasattr(self.generator, 'repair_legal_answer'):
                blocked_ids = {r['claim_id'] for r in rule_records}
                accepted_ids = [v['claim_id'] for v in getattr(checked, 'verdicts', ()) if v['supported'] and v['claim_id'] not in blocked_ids] if 'answer' not in blocked_ids else []
                generated = self.generator.repair_legal_answer(query, generated,
                    question_plan=question_plan, issues=issues, accepted_ids=accepted_ids)
            else:
                generated = self.generator.generate(
                    query + "\nYêu cầu kiểm tra lại: " + " ".join(issues)
                + " Sửa đúng các kết luận bị chỉ ra, không thêm quyền/nghĩa vụ hoặc từ 'chỉ' nếu nguồn chưa loại trừ ngoại lệ. "
                + "Giới hạn của một tài liệu không phải giới hạn của toàn bộ pháp luật. "
                + "Chỉ kết luận theo nguồn trực tiếp; nếu thiếu hãy nói chưa tìm thấy căn cứ.",
                    chunks, context_kind="legal",
                )
            generation_trace.extend(generated.agent_trace)
            verification_chunks = list(generated.selected_evidence) or chunks
            if generated.provider != "template" and not generated.literal_source_answer:
                generated = replace(generated, text=append_commencement_evidence(generated.text, verification_chunks, query))
            issues = evidence_issues(generated.text_for_verification, verification_chunks, query, claim_records=generated.claim_records) if not generated.literal_source_answer else []
            deterministic_issues = list(issues)
            rule_records = identify_rule_issues(issues, generated, verification_chunks) if generated.claim_records else []
            if rule_records:
                issues = [json.dumps(r, ensure_ascii=False) for r in rule_records]
            checked = None
            if generated.literal_source_answer:
                verification_trace.append({'agent': 'source_verification', 'provider': 'exact_source_match',
                    'status': 'accepted', 'fallback': True, 'scope': 'verbatim source text only; no legal application inferred'})
            if not generated.literal_source_answer and generated.provider not in {"template", "legal-extractive", "legal-insufficient"} and hasattr(self.generator, "check_legal_evidence"):
                checked = verify(generated)
                issues.extend(checked)
                if hasattr(checked,'trace'):
                    verification_trace.append(checked.trace)
                    degraded_reasons.extend(checked.degraded_reasons)
        rejected = bool(issues) or _citation_accuracy(generated.text, verification_chunks) < 1
        if rejected and generated.claim_records and checked is not None and 'answer' not in {r['claim_id'] for r in rule_records}:
            from .claim_verification import retained_answer, ClaimIssues
            blocked_ids = {r['claim_id'] for r in rule_records}
            partial_check = ClaimIssues([dict(v, supported=False) if v['claim_id'] in blocked_ids else v
                                        for v in getattr(checked, 'verdicts', ())])
            retained = retained_answer(generated, partial_check)
            if retained and not evidence_issues(retained.text_for_verification, verification_chunks, query, claim_records=retained.claim_records) and _citation_accuracy(retained.text, verification_chunks) == 1:
                degraded_reasons.extend(issues)
                generated = retained
                rejected = False
                verification_trace.append(dict(agent='source_verification', provider='gemini', status='partial_retained',
                    retained_claim_ids=[c['claim_id'] for c in retained.claim_records],
                    rejected_claim_ids=[v['claim_id'] for v in partial_check.verdicts if not v['supported']]))
        if rejected and generated.source_fallback is not None:
            fallback = generated.source_fallback
            if fallback.literal_source_answer and _citation_accuracy(fallback.text, verification_chunks) == 1:
                degraded_reasons.extend(issues)
                degraded_reasons.append('Bản tổng hợp chưa được nguồn xác nhận sau lần sửa; dùng trích đoạn Qwen đã chọn.')
                generated = fallback
                rejected = False
                verification_trace.append({'agent': 'source_verification', 'provider': 'exact_source_match',
                    'status': 'accepted', 'fallback': True, 'scope': 'verbatim source text only; no legal application inferred'})
        partial = None
        if chunks and (rejected or generated.provider == "template"):
            partial = extract_partial_provisions(query, chunks)
        if not chunks or rejected:
            generated = partial or GroundedTemplateGenerator().generate(
                query, chunks, context_kind="legal"
            )
            degraded_reasons.append(
                "Câu trả lời dùng mẫu theo nguồn vì chưa đủ bằng chứng hoặc trích dẫn không hợp lệ"
            )
            degraded_reasons.extend(issues)
        elif partial:
            generated = partial
        # Keep full clauses for selection, synthesis and verification, but never
        # dump them into a long user-facing fallback. No legal unit is sliced.
        if generated.literal_source_answer and len(generated.text) > 3500 and generated.selected_evidence:
            from .source_selection import render_source_fallback
            parts = [dict(document=row.get('title'), heading=row.get('heading'),
                          rank=row['rank'], text=row['content']) for row in generated.selected_evidence]
            generated = replace(generated, text=render_source_fallback(
                parts, generated.evidence_limitations,
                insufficient=legal_completion_status(generated.text) != 'complete'))
            generation_trace.append({'agent': 'answer_display', 'provider': 'rules',
                                     'status': 'compact_source_fallback',
                                     'full_evidence_retained': True})
        degraded_reasons.extend(generated.degraded_reasons)
        completion = legal_completion_status(generated.text)
        if completion != 'complete' and generated.provider not in {'template', 'legal-insufficient', 'legal-partial-extractive'}:
            degraded_reasons.append('Phản hồi chưa đáp ứng đầy đủ yêu cầu chính; đánh dấu theo nội dung thay vì provider.')
        sources = [
            ChatSource(
                kind="legal_document",
                document_id=int(item["document_id"]),
                chunk_id=int(item["chunk_id"]),
                rank=int(item["rank"]),
                similarity_score=float(item["similarity_score"]),
                title=str(item["title"]),
                source="legal_corpus",
                source_path=item.get("source_path"),
                source_url=item.get("source_url"),
                category=item.get("category"),
                page_kind=item.get('page_kind'),
                page_from=item.get("page_from"),
                page_to=item.get("page_to"),
                heading=item.get("heading"),
                excerpt=(str(item.get("content") or "")[:1800]
                         + ("…" if len(str(item.get("content") or "")) > 1800 else "")),
            )
            for item in chunks
        ]
        contexts = (
            [
                ChatEvaluationContext(
                    kind="legal_document",
                    chunk_id=int(item["chunk_id"]),
                    rank=int(item["rank"]),
                    content=str(item["content"]),
                )
                for item in chunks
            ]
            if body.include_evaluation_contexts
            else []
        )
        response = ChatAskResponse(
            agent_trace=agent_trace + generation_trace + ([{"agent": "answer", "provider": generated.provider,
                "model": generated.model, "status": completion,
                "attempted_provider":attempted_provider,"attempted_model":attempted_model},
                {"agent": "citation_and_rule_checks", "provider": "rules",
                 "status": "rejected" if rejected else "accepted"}]
                if self.question_analyzer is not None else []),
            corpus_schema=getattr(self.repo, "legal_schema", None),
            answer=generated.text,
            intent="legal_question",
            confidence=round(confidence, 4),
            listings=[],
            sources=sources,
            no_answer=not chunks or rejected or completion != 'complete' or generated.provider in {"template", "legal-insufficient", "legal-partial-extractive"},
            partial_answer=generated.provider == "legal-partial-extractive" or completion == 'partial',
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
            retrieval_mode=retrieval_mode,
            generation_provider=generated.provider,
            generation_model=generated.model,
            latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
            citation_accuracy=_citation_accuracy(generated.text, chunks),
            evaluation_contexts=contexts,
            citation_applicable=bool(chunks),
        )
        if hasattr(self.repo, "record_event"):
            response.event_id = self.repo.record_event(
                {
                    "intent": response.intent,
                    "confidence": response.confidence,
                    "no_answer": response.no_answer,
                    "degraded": response.degraded,
                    "retrieval_mode": response.retrieval_mode,
                    "generation_provider": response.generation_provider,
                    "result_count": len(chunks),
                    "latency_ms": response.latency_ms,
                }
            )
        return response

    def ask(self, body: ChatAskRequest) -> ChatAskResponse:
        started = time.perf_counter()
        query = rewrite_query(body.message, body.conversation_history)
        parsed = parse_query(query)
        # Khẩn cấp xét trên tin nhắn GỐC: câu đã nối ngữ cảnh có thể mang chữ "đe doạ" từ lượt cũ khiến mọi câu sau thành khẩn cấp
        if parsed.intent == "emergency" and not emergency_kind(normalize_text(body.message)):
            parsed = parse_query(body.message)
        if parsed.intent == "legal_question":
            return self._ask_legal(query, body, started)
        # Parse each turn separately so a newer budget replaces the older budget.
        # Assistant text is never treated as a source of user preferences.
        filters = parsed.filters
        if query != body.message:
            from .schemas import ChatFilters

            filters = ChatFilters()
            for turn in body.conversation_history[-10:]:
                if turn.role == "user":
                    incoming = parse_query(turn.content).filters
                    if incoming.min_price is not None or incoming.max_price is not None:
                        filters = filters.model_copy(
                            update={"min_price": None, "max_price": None}
                        )
                    filters = merge_filters(filters, incoming)
            incoming = parse_query(body.message).filters
            if incoming.min_price is not None or incoming.max_price is not None:
                filters = filters.model_copy(
                    update={"min_price": None, "max_price": None}
                )
            filters = merge_filters(filters, incoming)
        filters = merge_filters(filters, body.filters)
        state = body.conversation_state
        normalized_message = normalize_text(body.message)
        follow_up = query != body.message or any(marker in body.message.lower() for marker in FOLLOW_UP_MARKERS)
        detail = state is not None and "phong do" in normalized_message
        if state and follow_up:
            filters = merge_filters(state.filters, parse_query(body.message).filters)
            # A detail question reads the selected record, without interpreting
            # requested attributes as filters and silently substituting a room.
            ids = state.listing_ids
            if not detail and ids:
                # "rẻ hơn / gần hơn / rộng hơn" so với các tin lượt trước (trước đây bị bỏ qua, trả giá không hề rẻ hơn)
                updates = comparative_updates(body.message, self.repo.shown_stats(ids))
                if updates:
                    filters = filters.model_copy(update=updates)
            if detail:
                ids = [state.selected_listing_id] if state.selected_listing_id in ids else ids[:1]
                filters = ChatFilters(listing_ids=ids)
            elif "cac phong vua" in normalized_message or "cac tin vua" in normalized_message or "tat ca dieu kien" in normalized_message:
                filters = filters.model_copy(update={"listing_ids": ids})

        degraded_reasons: list[str] = []
        listings: list[dict] = []
        graph_trace = None
        retrieval_mode = "rule"
        if parsed.intent == "out_of_scope":
            answer = "Mình hỗ trợ tìm, so sánh nhà trọ quanh Đại học Cần Thơ và giải thích pháp lý thuê trọ cơ bản; không soạn hợp đồng, điền tờ khai hoặc thực hiện thủ tục pháp lý chuyên sâu."
            confidence = 0.0
            generation_provider = "rule"
            generation_model = None
        elif parsed.intent == "emergency":
            answer = EMERGENCY_ANSWERS[emergency_kind(normalized_message) or "violence"]
            confidence = 0.0
            generation_provider = "rule"
            generation_model = None
        elif parsed.intent == "out_of_area":
            answer = out_of_area_answer(out_of_area_place(normalize_text(query)) or "khu vực này")
            confidence = 0.0
            generation_provider = "rule"
            generation_model = None
        elif parsed.intent == "clarify":
            answer = "Bạn muốn tìm phòng ở khu vực nào, khoảng giá bao nhiêu và cần tiện ích gì?"
            confidence = 0.0
            generation_provider = "rule"
            generation_model = None
        else:
            embedded = self.embedder.embed_query(query)
            if embedded.degraded_reason:
                degraded_reasons.append(embedded.degraded_reason)
            listings = self.repo.retrieve(
                query, filters, embedded.vector, limit=self.max_results
            )
            retrieval_mode = (
                "hybrid" if embedded.vector is not None else "lexical_structured"
            )
            graph_trace = listings[0].get("_graph_trace") if listings else None
            if getattr(self.repo, "graph_enabled", False):
                retrieval_mode = "graph_hybrid" if embedded.vector is not None else "graph_lexical_structured"
            filter_count = sum(
                value not in (None, False, [], "phong_tro")
                for value in filters.model_dump().values()
            )
            # A verified location graph intersection is one applied constraint,
            # including when the user names two alternatives. Count it once,
            # using the same weight as the existing structured filter policy.
            if graph_trace and any(key.startswith('location:') for key in graph_trace.get('seed_entities', [])):
                filter_count += 1
            top_score = listings[0]["similarity_score"] if listings else 0.0
            second_score = listings[1]["similarity_score"] if len(listings) > 1 else 0.0
            margin = max(0.0, top_score - second_score)
            confidence = (
                min(
                    0.97,
                    0.10
                    + 0.46 * top_score
                    + 0.24 * parsed.confidence
                    + 0.04 * min(filter_count, 3)
                    + 0.08 * min(1.0, margin * 4),
                )
                if listings
                else 0.0
            )
            if confidence < self.confidence_threshold and not (filters.listing_ids or filters.sort_by):
                listings = []
            if detail and listings:
                item = listings[0]
                amenities = item.get("parsed_amenities") or {}
                def status(key):
                    value = amenities.get(key)
                    return "có" if value is True else "không có" if value is False else "tin chưa nêu rõ"
                generated = GenerationResult(
                    text=f"{item['title']}: chỗ để xe — {status('parking')}; Wi-Fi — {status('wifi')} [1]. Hãy xác nhận lại với người cho thuê.",
                    provider="structured",
                )
            elif listings and "cac tin vua" in normalized_message:
                lines = []
                for item in listings:
                    lines.append(f"- {item['title']}: lần ghi nhận nguồn {item.get('last_seen') or 'chưa có thời gian'}; cập nhật bản ghi {item.get('updated_at') or 'chưa có thời gian'} [{item['rank']}].")
                generated = GenerationResult(text="\n".join(lines) + "\nThời gian ghi nhận không xác nhận phòng còn trống; mở nguồn tin để kiểm tra.", provider="structured")
            elif "tat ca dieu kien" in normalized_message and listings:
                generated = GenerationResult(text="Các tin này đang khớp các bộ lọc đã áp dụng; chưa cần nới điều kiện. " + " ".join(f"[{item['rank']}]" for item in listings), provider="structured")
            elif filters.sort_by == "price_asc" and listings:
                item = listings[0]
                generated = GenerationResult(text=f"Tin có giá thuê thấp nhất trong tập tin hợp lệ khớp bộ lọc: {item['title']} — {item['price'] / 1_000_000:g} triệu đồng/tháng [1]. Giá này chưa bao gồm các chi phí mà tin không nêu.", provider="structured")
            elif getattr(self.repo, 'graph_enabled', False):
                # Render verified housing fields directly, avoiding model
                # timeouts and re-writing numbers, amenities or distances.
                generated = GroundedTemplateGenerator().generate(query, listings)
            else:
                generated = self.generator.generate(query, listings)
            listing_issues = listing_evidence_issues(generated.text, listings) if listings and generated.provider not in {"template", "structured"} else []
            if not listings or _citation_accuracy(generated.text, listings) < 1 or listing_issues:
                generated = GroundedTemplateGenerator().generate(query, listings)
                degraded_reasons.append(
                    "Câu trả lời dùng mẫu theo nguồn vì chưa đủ bằng chứng hoặc trích dẫn không hợp lệ"
                )
                degraded_reasons.extend(listing_issues)
            answer = generated.text
            generation_provider = generated.provider
            generation_model = generated.model
            degraded_reasons.extend(generated.degraded_reasons)

        latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        listing_models = [
            ChatListing(
                id=item["id"],
                corpus_schema=getattr(self.repo, "listing_schema", "public"),
                title=item["title"],
                price=item.get("price"),
                area=item.get("area"),
                address=item.get("address"),
                district=item.get("district"),
                amenities=item.get("parsed_amenities") or {},
                distance_to_ctu=item.get("distance_to_ctu"),
                route_time_campus=item.get("route_time_campus"),
                source=item["source"],
                source_url=item.get("source_url"),
                similarity_score=item["similarity_score"],
                vector_score=float(item.get("vector_score") or 0.0),
                bm25_score=float(item.get("bm25_score") or 0.0),
                rank=item["rank"],
                match_reasons=item.get("match_reasons") or [],
                risk_score=(
                    float(item.get("risk_score") or 0.0)
                    if item.get("risk_evaluated_at") is not None
                    else None
                ),
                risk_level=_risk_level(item),
            )
            for item in listings
        ]
        sources = [
            ChatSource(
                listing_id=item.id,
                rank=item.rank,
                similarity_score=item.similarity_score,
                title=item.title,
                source=item.source,
                source_url=item.source_url,
            )
            for item in listing_models
        ]
        citation_accuracy = _citation_accuracy(answer, listings)
        contexts = (
            [
                ChatEvaluationContext(
                    listing_id=int(item["id"]),
                    rank=int(item["rank"]),
                    content=_evaluation_context(item),
                )
                for item in listings
            ]
            if body.include_evaluation_contexts
            else []
        )
        response = ChatAskResponse(
            answer=answer,
            intent=parsed.intent,
            agent_trace=[graph_trace] if parsed.intent not in {"out_of_scope", "clarify", "emergency", "out_of_area"} and graph_trace else [],
            confidence=round(confidence, 4),
            listings=listing_models,
            sources=sources,
            no_answer=not listings,
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
            retrieval_mode=retrieval_mode,
            generation_provider=generation_provider,
            generation_model=generation_model,
            latency_ms=latency_ms,
            citation_accuracy=citation_accuracy,
            evaluation_contexts=contexts,
            citation_applicable=bool(listings),
            applied_filters=filters,
            conversation_state=ChatConversationState(
                filters=state.filters if detail and state else filters.model_copy(update={"listing_ids": []}),
                listing_ids=[item["id"] for item in listings],
                selected_listing_id=listings[0]["id"] if listings and (detail or filters.sort_by) else None,
            ),
        )
        if hasattr(self.repo, "record_event"):
            response.event_id = self.repo.record_event(
                {
                    "intent": response.intent,
                    "confidence": response.confidence,
                    "no_answer": response.no_answer,
                    "degraded": response.degraded,
                    "retrieval_mode": response.retrieval_mode,
                    "generation_provider": response.generation_provider,
                    "result_count": len(response.listings),
                    "latency_ms": response.latency_ms,
                }
            )
        return response

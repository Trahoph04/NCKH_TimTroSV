from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from ...listings.repo import visible_clause
from .providers import normalize_text
from .schemas import ChatFilters
from .legal_retrieval import expand_legal_query, legal_tokens, rerank_legal, electricity_question, rental_electricity_question
from ..legal_knowledge.quality import usable_legal_text
from .topics import question_categories


STOP_WORDS = {
    "anh", "ban", "can", "cho", "co", "cua", "duoc", "giup", "la",
    "minh", "nha", "phong", "tim", "toi", "tro", "va", "voi",
}


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.9g}" for value in vector) + "]"


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in normalize_text(value).split()
        if len(token) > 1 and token not in STOP_WORDS
    ]


def _listing_document(item: dict[str, Any]) -> str:
    amenities = item.get("parsed_amenities") or {}
    enabled_amenities = " ".join(
        key.replace("_", " ") for key, enabled in amenities.items() if enabled is True
    )
    # Repeating title and district gives important short fields more BM25 weight.
    return " ".join(
        str(value or "")
        for value in (
            item.get("title"), item.get("title"), item.get("description"),
            item.get("address"), item.get("district"), item.get("district"),
            enabled_amenities, item.get("listing_type"),
        )
    )


def bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    tokenizer=None,
) -> list[float]:
    """BM25 from the old Hybrid project, adapted to live listing rows."""

    if not documents:
        return []
    tokenize = tokenizer or _tokens
    query_terms = Counter(tokenize(query))
    tokenized = [tokenize(document) for document in documents]
    if not query_terms or not any(tokenized):
        return [0.0] * len(documents)

    document_frequency: Counter[str] = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))
    average_length = sum(len(tokens) for tokens in tokenized) / len(tokenized) or 1.0
    total = len(tokenized)
    raw_scores: list[float] = []
    for tokens in tokenized:
        frequencies = Counter(tokens)
        length_norm = k1 * (1 - b + b * len(tokens) / average_length)
        score = 0.0
        for term, query_count in query_terms.items():
            frequency = frequencies.get(term, 0)
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            score += query_count * inverse_frequency * (frequency * (k1 + 1)) / (
                frequency + length_norm
            )
        raw_scores.append(score)
    maximum = max(raw_scores, default=0.0)
    return [score / maximum if maximum > 0 else 0.0 for score in raw_scores]


def _preference_score(
    filters: ChatFilters, item: dict[str, Any]
) -> tuple[float, list[str]]:
    checks: list[tuple[bool, str]] = []
    price = item.get("price")
    area = item.get("area")
    distance = item.get("distance_to_ctu")
    route_times = [
        value for value in (item.get("route_time_campus") or []) if value is not None
    ]
    amenities = item.get("parsed_amenities") or {}

    if filters.min_price is not None:
        checks.append((price is not None and price >= filters.min_price, "Đúng mức giá"))
    if filters.max_price is not None:
        checks.append((price is not None and price <= filters.max_price, "Trong ngân sách"))
    if filters.min_area is not None:
        checks.append((area is not None and area >= filters.min_area, "Đủ diện tích"))
    if filters.district:
        checks.append(
            (
                filters.district.lower() in str(item.get("district") or "").lower(),
                f"Khu vực {filters.district}",
            )
        )
    if filters.max_distance_ctu is not None:
        checks.append(
            (distance is not None and distance <= filters.max_distance_ctu, "Gần CTU")
        )
    if filters.max_route_minutes is not None:
        checks.append(
            (
                bool(route_times) and min(route_times) <= filters.max_route_minutes,
                "Đúng thời gian di chuyển",
            )
        )
    for amenity in filters.amenities:
        checks.append((amenities.get(amenity) is True, "Đủ tiện ích yêu cầu"))

    if not checks:
        return 0.55, []
    matched = [reason for passed, reason in checks if passed]
    return sum(passed for passed, _ in checks) / len(checks), list(dict.fromkeys(matched))


class ChatRepository:
    """Read-only repository for stateless hybrid housing retrieval."""

    def __init__(self, engine: Engine, legal_schema: str = "public", listing_schema: str = "public"):
        self.engine = engine
        if not re.fullmatch(r"public|housing_[a-z0-9_]{1,48}", listing_schema):
            raise ValueError("Invalid listing schema")
        self.listing_schema = listing_schema
        from ..legal_knowledge.storage import legal_schema as validate_schema
        self.legal_schema = validate_schema(legal_schema)

    def _legal_sql(self, statement: str):
        from ..legal_knowledge.storage import legal_sql
        return legal_sql(statement, self.legal_schema)

    def retrieve(
        self,
        query: str,
        filters: ChatFilters,
        vector: list[float] | None,
        limit: int = 5,
    ) -> list[dict]:
        # cùng visible_clause() của /listings: chatbot không được gợi ý tin mà UI đang ẩn
        # (mặt bằng, nhà nguyên căn, 'khac') — link "Xem chi tiết" sẽ dẫn tới tin không tìm thấy trong list/map
        clauses = [
            "status = 'active'",
            visible_clause(None),
        ]
        params: dict[str, Any] = {"candidate_limit": 250}
        if filters.listing_ids:
            clauses.append("id = ANY(:listing_ids)")
            params["listing_ids"] = filters.listing_ids
        if filters.listing_type:
            clauses.append("listing_type = CAST(:listing_type AS listing_type_enum)")
            params["listing_type"] = filters.listing_type
        if filters.min_price is not None:
            clauses.append("price >= :min_price")
            params["min_price"] = filters.min_price
        if filters.max_price is not None:
            clauses.append("price < :max_price" if filters.max_price_exclusive else "price <= :max_price")
            params["max_price"] = filters.max_price
        if filters.min_area is not None:
            clauses.append("area >= :min_area")
            params["min_area"] = filters.min_area
        if filters.district:
            clauses.append("district ILIKE :district")
            params["district"] = f"%{filters.district}%"
        if filters.max_distance_ctu is not None:
            clauses.append("distance_to_ctu <= :max_distance")
            params["max_distance"] = filters.max_distance_ctu
        if filters.max_route_minutes is not None:
            clauses.append(
                "LEAST(COALESCE(route_time_campus[1], 1e9), "
                "COALESCE(route_time_campus[2], 1e9), COALESCE(route_time_campus[3], 1e9)) "
                "<= :max_minutes"
            )
            params["max_minutes"] = filters.max_route_minutes
        for index, amenity in enumerate(filters.amenities):
            key = f"amenity_{index}"
            clauses.append(
                f"COALESCE((parsed_amenities ->> :{key})::boolean, false) IS TRUE"
            )
            params[key] = amenity
        if filters.gender in ("female", "male"):
            # repo này lưu giới tính ở cột gender_only ('nam'/'nu', NULL = không giới hạn) — không phải
            # parsed_amenities->'gender' như catalog branch PHUC
            clauses.append("(gender_only IS NULL OR gender_only = :gender)")
            params["gender"] = "nu" if filters.gender == "female" else "nam"

        if vector is not None:
            vector_sql = (
                "CASE WHEN embedding_vector IS NULL THEN 0 ELSE "
                "GREATEST(0, LEAST(1, 1 - (embedding_vector <=> CAST(:query_vector AS vector)))) END"
            )
            params["query_vector"] = _vector_literal(vector)
            order_sql = "vector_score DESC, quality_score DESC NULLS LAST"
        else:
            vector_sql = "0"
            order_sql = "quality_score DESC NULLS LAST, freshness_score DESC NULLS LAST"
        if filters.sort_by == "price_asc":
            clauses.append("price IS NOT NULL")
            order_sql = "price ASC, id ASC"
            params["candidate_limit"] = limit

        sql = text(
            "SELECT id, title, price, area, address, district, description, parsed_amenities, "
            "distance_to_ctu, route_time_campus, source, source_url, quality_score, "
            "freshness_score, risk_score, risk_evaluated_at, listing_type, first_seen, last_seen, updated_at, "
            f"{vector_sql} AS vector_score FROM {self.listing_schema}.aggregated_listings "
            f"WHERE {' AND '.join(clauses)} ORDER BY {order_sql} LIMIT :candidate_limit"
        )
        with self.engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).mappings().all()]

        lexical_scores = bm25_scores(query, [_listing_document(item) for item in rows])
        for item, bm25_score in zip(rows, lexical_scores):
            vector_score = float(item.get("vector_score") or 0.0)
            quality = max(0.0, min(1.0, float(item.get("quality_score") or 0.0)))
            freshness = max(0.0, min(1.0, float(item.get("freshness_score") or 0.0)))
            # Unknown risk is neutral, never treated as safer than an evaluated listing.
            safety = (
                0.5
                if item.get("risk_evaluated_at") is None
                else 1.0 - max(0.0, min(1.0, float(item.get("risk_score") or 0.0)))
            )
            distance = item.get("distance_to_ctu")
            proximity = (
                1.0 / (1.0 + max(0.0, float(distance)) / 2000)
                if distance is not None
                else 0.25
            )
            preference, reasons = _preference_score(filters, item)

            if vector is None:
                final_score = (
                    0.45 * bm25_score
                    + 0.22 * preference
                    + 0.14 * quality
                    + 0.10 * freshness
                    + 0.06 * safety
                    + 0.03 * proximity
                )
            else:
                final_score = (
                    0.35 * vector_score
                    + 0.25 * bm25_score
                    + 0.15 * preference
                    + 0.10 * quality
                    + 0.08 * freshness
                    + 0.05 * safety
                    + 0.02 * proximity
                )
            if vector_score >= 0.6:
                reasons.insert(0, "Khớp ngữ nghĩa")
            if bm25_score >= 0.5:
                reasons.insert(0, "Khớp từ khóa")
            if quality >= 0.75:
                reasons.append("Tin chất lượng tốt")
            item["bm25_score"] = round(bm25_score, 6)
            item["similarity_score"] = round(max(0.0, min(1.0, final_score)), 6)
            item["match_reasons"] = list(dict.fromkeys(reasons))[:3]

        rows.sort(
            key=lambda item: (
                float(item.get("price") or 0) if filters.sort_by == "price_asc" else -item["similarity_score"],
                -float(item.get("quality_score") or 0.0),
                item["id"],
            )
        )
        for rank, item in enumerate(rows[:limit], 1):
            item["rank"] = rank
        return rows[:limit]

    def shown_stats(self, ids: list[int]) -> dict:
        """Giá thấp nhất / khoảng cách gần nhất / diện tích ĐO lớn nhất của các tin đã hiện lượt trước — cho câu "rẻ hơn / gần hơn / rộng hơn".

        Diện tích chỉ tính tin có số đo thật (is_imputed_area = FALSE): so với số hệ thống tự đoán theo giá thì vô nghĩa.
        """
        if not ids:
            return {}
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT min(price) AS min_price, min(distance_to_ctu) AS min_distance, "
                "max(area) FILTER (WHERE NOT COALESCE(is_imputed_area, false)) AS max_area "
                f"FROM {self.listing_schema}.aggregated_listings WHERE id = ANY(:ids)"), {"ids": ids}).mappings().one()
        return dict(row)

    def retrieve_legal(
        self,
        query: str,
        vector: list[float] | None,
        limit: int = 5,
        search_queries: list[str] | None = None,
        categories_override: list[str] | None = None,
    ) -> list[dict]:
        """Hybrid retrieval over OCR/indexed legal chunks.

        Missing migration/data is treated as an empty knowledge base so a rolling
        deployment never makes the existing housing chatbot unavailable.
        """
        expanded = expand_legal_query(query) + " " + " ".join(search_queries or [])
        # Independent lexical and vector pools avoid excluding a relevant law
        # merely because it was indexed earlier than 600 other chunks.
        terms = list(dict.fromkeys(term for term in re.findall(r"[^\W_]{2,}", expanded.lower()) if legal_tokens(term)))
        categories = tuple(dict.fromkeys([*question_categories(query), *(categories_override or [])]))
        params: dict[str, Any] = {"candidate_limit": 120, "category_limit": 40, "tsquery": " | ".join(terms) or "empty",
                                  "categories": list(categories), "has_categories": bool(categories), "rental_query": rental_electricity_question(query),
                                  "identity_query": 'privacy_data' in categories and 'housing_contract' in categories}
        params['privacy_query'] = 'privacy_data' in categories
        params['contract_contents_query'] = 'housing_contract' in categories
        from .evidence_units import requested_contract_facets, whole_supplementary_units, human_reporting_question
        params['deposit_query'] = 'deposit' in requested_contract_facets(query)
        params['reporting_query'] = 'criminal_law' in categories and human_reporting_question(query)
        if vector is not None:
            vector_sql = (
                "CASE WHEN c.embedding_vector IS NULL THEN 0 ELSE "
                "GREATEST(0, LEAST(1, 1 - (c.embedding_vector <=> CAST(:query_vector AS vector)))) END"
            )
            params["query_vector"] = _vector_literal(vector)
        else:
            vector_sql = "0"
        metadata_sql = "d.source_metadata->>'source_url' AS source_url,d.source_metadata->>'page_kind' AS page_kind,d.source_metadata->>'id' AS source_id,d.source_metadata->>'source_content_kind' AS source_content_kind,d.source_metadata->>'source_scope_warning' AS source_scope_warning," if self.legal_schema != "public" else ""
        provision_sql = "c.parent_content,c.provision_id,c.source_metadata AS provision_metadata," if self.legal_schema != "public" else ""
        base_sql = (
            "SELECT c.id AS chunk_id,c.chunk_index,d.id AS document_id,d.title,d.category,d.source_path,"
            + metadata_sql + provision_sql + "c.page_from,c.page_to,c.heading,c.content,"
            f"{vector_sql} AS vector_score,"
            "ts_rank_cd(c.content_tsv,to_tsquery('simple',:tsquery)) AS lexical_rank "
            "FROM legal_chunks c JOIN legal_documents d ON d.id=c.document_id WHERE d.status='ready' AND d.admin_enabled "
            "AND (NOT :has_categories OR d.category=ANY(:categories)) "
        )
        sql = self._legal_sql("WITH candidates AS (" + base_sql + "), lexical_ids AS ("
                   "SELECT chunk_id,ROW_NUMBER() OVER(PARTITION BY category ORDER BY lexical_rank DESC,chunk_id) AS position "
                   "FROM candidates WHERE lexical_rank > 0), lexical AS ("
                   "SELECT c.* FROM candidates c JOIN lexical_ids r ON c.chunk_id=r.chunk_id WHERE r.position<=:category_limit), "
                   "phrases AS (SELECT * FROM candidates WHERE :rental_query AND (content ILIKE '%thu tiền điện%' "
                   "OR content ILIKE '%người thuê nhà%' OR content ILIKE '%định mức%') "
                   "ORDER BY lexical_rank DESC,chunk_id LIMIT :candidate_limit), "
                   "identity AS (SELECT * FROM candidates WHERE :identity_query AND category='housing_contract' "
                   "AND heading ILIKE '%hợp đồng về nhà ở%' AND (content ILIKE '%Họ và tên%' OR content ILIKE '%họ tên%')), "
                   "privacy AS (SELECT * FROM candidates WHERE :privacy_query AND category='privacy_data' "
                   "AND (heading ILIKE '%Nguyên tắc bảo vệ%' OR heading ILIKE '%Sự đồng ý%' OR heading ILIKE '%Thu thập, phân tích%')) "
                   ", contract_contents AS (SELECT * FROM candidates WHERE :contract_contents_query AND category='housing_contract' "
                   "AND (heading ILIKE '%Hợp đồng về nhà ở%' OR heading ILIKE '%Nội dung của hợp đồng%')) "
                   ", deposits AS (SELECT * FROM candidates WHERE :deposit_query AND category='housing_contract' AND heading ILIKE '%Đặt cọc%') "
                   ", reporting AS (SELECT * FROM candidates WHERE :reporting_query AND category='criminal_law' "
                   "AND heading ILIKE '%Khuyến cáo%' AND (content ILIKE '%chứng từ chuyển tiền%' OR content ILIKE '%lịch sử giao dịch%')) "
                   + (", semantic_ids AS (SELECT chunk_id,ROW_NUMBER() OVER(PARTITION BY category ORDER BY vector_score DESC,chunk_id) AS position FROM candidates), "
                      "semantic AS (SELECT c.* FROM candidates c JOIN semantic_ids r ON c.chunk_id=r.chunk_id WHERE r.position<=:category_limit) "
                      "SELECT * FROM lexical UNION SELECT * FROM semantic UNION SELECT * FROM phrases UNION SELECT * FROM identity UNION SELECT * FROM privacy UNION SELECT * FROM contract_contents UNION SELECT * FROM deposits UNION SELECT * FROM reporting" if vector is not None
                      else "SELECT * FROM lexical UNION SELECT * FROM phrases UNION SELECT * FROM identity UNION SELECT * FROM privacy UNION SELECT * FROM contract_contents UNION SELECT * FROM deposits UNION SELECT * FROM reporting"))
        try:
            with self.engine.connect() as conn:
                rows = [dict(row) for row in conn.execute(sql, params).mappings().all()]
        except SQLAlchemyError:
            return []

        documents = [
            " ".join(
                str(value or "")
                for value in (item.get("title"), item.get("heading"), item.get("content"))
            )
            for item in rows
        ]
        lexical_scores = bm25_scores(expanded, documents, tokenizer=legal_tokens)
        for item, bm25_score in zip(rows, lexical_scores):
            vector_score = float(item.get("vector_score") or 0.0)
            item["bm25_score"] = round(bm25_score, 6)
            item["similarity_score"] = round(
                max(
                    0.0,
                    min(
                        1.0,
                        0.55 * vector_score + 0.45 * bm25_score
                        if vector is not None
                        else bm25_score,
                    ),
                ),
                6,
            )
        # With lexical-only retrieval, zero-score rows are arbitrary and unsafe to cite.
        if vector is None:
            rows = [item for item in rows if item["bm25_score"] > 0]
        else:
            rows = [
                item
                for item in rows
                if item["bm25_score"] > 0 or float(item.get("vector_score") or 0) >= 0.35
            ]
        # Preserve each category's relevant candidates until facet reservation.
        rows = rerank_legal(query, rows, limit=max(30, len(categories) * 80))
        from .legal_retrieval import diversified_legal_rows
        core_limit = min(2, max(1, limit - 1)) if rental_electricity_question(query) else max(1, limit - 2)
        from .topics import user_listing_check_question
        from .evidence_units import platform_reporting_question
        from .evidence_units import practical_facets
        # Hỏi mức phạt: các khoản của cùng một Điều là các BẬC phạt liền kề (500k–1tr / 2–4tr / 4–8tr…) — thiếu khoản đầu thì mô
        # hình thấy toàn bậc cao, không có khoản trả lời đúng hành vi hỏi (08/10: "không đăng ký tạm trú" mất khoản 1)
        from .legal_retrieval import fine_question
        if user_listing_check_question(query) or platform_reporting_question(query) or fine_question(query) or any(practical_facets(query, r) for r in rows):
            core_limit = max(1, limit - 1)
        # Relevance filtering runs first; diversity never introduces an unrelated row.
        rows = diversified_legal_rows(query, rows, core_limit) + rows
        selected = []
        seen: set[tuple] = set()
        general_contract_contents = ('housing_contract' in categories and
            any(term in normalize_text(query) for term in ('truoc khi ky', 'nhung dieu khoan', 'noi dung hop dong', 'ghi ro', 'ghi trong')))
        # Keep complete clauses and associated effectiveness/transition provisions.
        with self.engine.connect() as conn:
            for item in rows:
                article_heading = re.sub(r' \| Khoản .*$', '', item.get('heading') or '')
                whole_heading = normalize_text(article_heading)
                include_article = (self.legal_schema != 'public' and (
                    (general_contract_contents and any(term in whole_heading for term in ('hop dong ve nha o', 'noi dung cua hop dong')))
                    or (item.get('category')=='housing_contract' and 'coc' in normalize_text(query) and 'dat coc' in whole_heading)
                    or (item.get('category')=='fire_safety' and any(term in whole_heading for term in ('phong chay doi voi nha o','phong chay doi voi co so')))
                    or (item.get('category')=='privacy_data' and any(term in whole_heading for term in ('yeu cau rut lai','thuc hien quyen cua chu the','cung cap du lieu ca nhan','cong khai du lieu ca nhan')))))
                if item.get('category') == 'privacy_data' and 'nguyen tac bao ve' in whole_heading and any(
                        t in normalize_text(query) for t in ('luu', 'su dung', 'anh can cuoc')):
                    include_article = self.legal_schema != 'public'
                group = (item["document_id"], article_heading if include_article else re.sub(r' \| Điểm [a-zđ]$', '', item.get('heading') or '') or item['chunk_id'])
                if group in seen:
                    continue
                seen.add(group)
                item = dict(item)
                if include_article:
                    article_rows = [dict(r) for r in conn.execute(self._legal_sql(
                        'SELECT content,parent_content,page_from,page_to,provision_id,source_metadata '
                        'FROM legal_chunks WHERE document_id=:doc AND (heading=:heading OR heading LIKE :clauses) '
                        'ORDER BY chunk_index'), {'doc':item['document_id'], 'heading':article_heading,
                                                  'clauses':article_heading+' | Khoản %'}).mappings()]
                    unique_parts = list({r['provision_id']:r for r in article_rows}.values())
                    # Each clause's parent contains the same article introduction. Retain it once.
                    introduction = next((r['source_metadata'].get('article_context') for r in unique_parts
                                         if r['source_metadata'].get('article_context')), '')
                    bodies = [r['parent_content'][len(introduction):].lstrip() if introduction and
                              r['parent_content'].startswith(introduction) else r['parent_content']
                              for r in unique_parts]
                    bodies = [body for body in bodies if body and body != introduction]
                    article_text = ((introduction+'\n\n') if introduction else '')+'\n\n'.join(bodies)
                    if article_text and len(article_text)<=5500:
                        item.update(content=article_text, heading=article_heading, context_complete=True,
                                    provision_ids=[r['provision_id'] for r in unique_parts])
                        item['page_from'] = min((r['page_from'] for r in unique_parts if r['page_from'] is not None), default=None)
                        item['page_to'] = max((r['page_to'] for r in unique_parts if r['page_to'] is not None), default=None)
                    else:
                        item['content'] = (item.get('parent_content') or item['content'])[:5500]
                        item['context_complete'] = False
                elif item.get("parent_content") and len(item['parent_content']) <= 5500:
                    item['content'] = item['parent_content']
                    item['context_complete'] = not (item.get('provision_metadata') or {}).get('selected_points_only',False)
                elif item.get('parent_content'):
                    # Do not represent a bounded fragment as a complete clause.
                    item['context_complete'] = False
                elif item.get("heading"):
                    # A point's meaning often depends on its clause introduction
                    # and other required items in the same dossier/checklist.
                    clause_heading = re.sub(r' \| Điểm [a-zđ]$', '', item['heading'])
                    siblings = [dict(row) for row in conn.execute(self._legal_sql(
                        "SELECT id AS chunk_id,chunk_index,content,page_from,page_to FROM legal_chunks "
                        "WHERE document_id=:doc AND (heading=:heading OR heading LIKE :points) ORDER BY chunk_index"
                    ), {"doc": item["document_id"], "heading": clause_heading,
                        "points": clause_heading + ' | Điểm %'}).mappings()]
                    # Nearest continuation first; never drop the matching chunk.
                    siblings.sort(key=lambda row: abs(row["chunk_index"] - item["chunk_index"]))
                    included = []
                    size = 0
                    for sibling in siblings:
                        if not usable_legal_text(sibling["content"]) or size + len(sibling["content"]) > 5500:
                            continue
                        included.append(sibling)
                        size += len(sibling["content"])
                    if included:
                        included.sort(key=lambda row: row["chunk_index"])
                        item["content"] = "\n\n".join(row["content"] for row in included)
                        item['heading'] = clause_heading
                        item["page_from"] = min((row["page_from"] for row in included if row["page_from"] is not None), default=None)
                        item["page_to"] = max((row["page_to"] for row in included if row["page_to"] is not None), default=None)
                if self.legal_schema != 'public':
                    # Resolve only unambiguous references within this document.
                    # Never substitute an article from a different cited law.
                    matches=re.findall(r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+(?:của\s+)?(?:Luật|Thông tư|Nghị định)\s+này',item['content'],re.I)
                    for clause,article in list(dict.fromkeys(matches))[:4]:
                        referenced=[dict(r) for r in conn.execute(self._legal_sql(
                            'SELECT parent_content,provision_id,source_metadata,page_from,page_to,heading FROM legal_chunks '
                            'WHERE document_id=:doc AND source_metadata->>\'article\'=:article '
                            'AND (:clause=\'\' OR source_metadata->>\'clause\'=:clause) ORDER BY chunk_index'),
                            {'doc':item['document_id'],'article':article,'clause':clause}).mappings()]
                        refs=list({r['provision_id']:r for r in referenced}.values())
                        supplement='\n\n'.join(r['heading']+'\n'+r['parent_content'] for r in refs)
                        if refs and all(r['parent_content'] in item['content'] for r in refs):continue
                        if supplement and len(item['content'])+len(supplement)+2<=5500:
                            item['content']+='\n\n'+supplement
                            item.setdefault('resolved_references',[]).append({'article':article,'clause':clause or None,'provision_ids':[r['provision_id'] for r in refs]})
                            item['page_from']=min([n for n in [item.get('page_from'),*(r['page_from'] for r in refs)] if n is not None],default=None)
                            item['page_to']=max([n for n in [item.get('page_to'),*(r['page_to'] for r in refs)] if n is not None],default=None)
                        else:
                            item.setdefault('unresolved_references',[]).append({'article':article,'clause':clause or None})
                selected.append(item)
                if len(selected) >= core_limit:
                    break
            # Named external law references get their own real document citation.
            external=[]
            for item in selected:
                for clause,article in re.findall(r'(?:khoản\s+(\d+)\s+)?Điều\s+(\d+)\s+(?:của\s+)?Luật\s+Bảo vệ dữ liệu cá nhân',item['content'],re.I):
                    refs=[dict(r) for r in conn.execute(self._legal_sql(
                        'SELECT c.id AS chunk_id,c.chunk_index,d.id AS document_id,d.title,d.category,d.source_path,'
                        +metadata_sql+provision_sql+'c.page_from,c.page_to,c.heading,c.content FROM legal_chunks c '
                        'JOIN legal_documents d ON d.id=c.document_id WHERE d.status=\'ready\' AND d.admin_enabled '
                        'AND d.source_metadata->>\'id\'=\'privacy91-cb\' AND c.source_metadata->>\'article\'=:article '
                        'AND (:clause=\'\' OR c.source_metadata->>\'clause\'=:clause) ORDER BY c.chunk_index'),
                        {'article':article,'clause':clause}).mappings()] if self.legal_schema!='public' else []
                    parts=list({r['provision_id']:r for r in refs}.values())
                    if not parts or all(any(r['parent_content'] in s['content'] for s in selected) for r in parts):continue
                    body='\n\n'.join(r['heading']+'\n'+r['parent_content'] for r in parts)
                    if len(body)>5500:continue
                    citation=dict(parts[0],content=body,context_complete=True,similarity_score=item['similarity_score'])
                    citation['page_from']=min((r['page_from'] for r in parts if r['page_from'] is not None),default=None)
                    citation['page_to']=max((r['page_to'] for r in parts if r['page_to'] is not None),default=None)
                    external.append(citation)
            for item in external:
                if len(selected)>=limit-1:break
                if not any(item['content']==s['content'] for s in selected):selected.append(item)
            doc_ids = list(dict.fromkeys(item["document_id"] for item in selected))
            if doc_ids and len(selected) < limit:
                effect_rows = [dict(row) for row in conn.execute(self._legal_sql(
                    "SELECT c.id AS chunk_id,c.chunk_index,d.id AS document_id,d.title,d.category,d.source_path,"
                    + metadata_sql + provision_sql + "c.page_from,c.page_to,c.heading,c.content FROM legal_chunks c "
                    "JOIN legal_documents d ON d.id=c.document_id WHERE d.status='ready' AND d.admin_enabled AND d.id=ANY(:ids) "
                    "AND (c.heading ILIKE '%Hiệu lực%' OR c.heading ILIKE '%Điều khoản thi hành%' OR c.heading ILIKE '%chuyển tiếp%' "
                    "OR c.heading ILIKE '%hình thức xử phạt%' OR c.heading ILIKE '%Mức phạt tiền%') "
                    "ORDER BY d.id,c.chunk_index"
                ), {"ids": doc_ids}).mappings()]
                for doc_id in doc_ids:
                    effects = [row for row in effect_rows if row["document_id"] == doc_id
                               and usable_legal_text(row["content"])
                               and 'hop dong' not in normalize_text(row.get('heading') or '')
                               and row["chunk_id"] not in {part["chunk_id"] for part in selected}]
                    # Effectiveness first (contains delayed commencement), then
                    # transition clauses. Each document gets its own citation.
                    def effect_priority(row):
                        heading=normalize_text(row.get('heading') or '')
                        return (0 if any(t in heading for t in ('hieu luc', 'dieu khoan thi hanh')) else 1 if 'muc phat tien' in heading else 2 if 'chuyen tiep' in heading else 3,row['chunk_index'])
                    effects.sort(key=effect_priority)
                    effects = whole_supplementary_units(effects)
                    included = []
                    size = 0
                    for row in effects:
                        # Commencement conditions are essential; mailing lists,
                        # repeal inventories and annex tables are not context.
                        normalized_content = normalize_text(row["content"])
                        if not row['content'].strip() or "noi nhan:" in normalized_content:
                            continue
                        if re.search(r'^(?:\d+[.,]\s*)?(?:bai bo\b|cac quy dinh sau(?: day)? het hieu luc\b)',normalized_content):
                            continue
                        if size + len(row["content"]) <= 5500:
                            included.append(row)
                            size += len(row["content"])
                    if included:
                        item = dict(included[0])
                        item["content"] = "\n\n".join((row["heading"] or "") + "\n" + row["content"] for row in included)
                        item["heading"] = "Hiệu lực, phạm vi mức phạt và điều khoản chuyển tiếp"
                        item["page_from"] = min((row["page_from"] for row in included if row["page_from"] is not None), default=None)
                        item["page_to"] = max((row["page_to"] for row in included if row["page_to"] is not None), default=None)
                        item["similarity_score"] = selected[0]["similarity_score"]
                        selected.append(item)
                    if len(selected) >= limit:
                        break
        for rank, item in enumerate(selected, 1):
            item["rank"] = rank
        return selected

    def record_event(self, payload: dict[str, Any]) -> int | None:
        """Store aggregate research telemetry; never stores the user's message."""
        try:
            with self.engine.begin() as conn:
                return int(
                    conn.execute(
                        text(
                            "INSERT INTO chatbot_events "
                            "(intent, confidence, no_answer, degraded, retrieval_mode, "
                            "generation_provider, result_count, latency_ms) "
                            "VALUES (:intent, :confidence, :no_answer, :degraded, :retrieval_mode, "
                            ":generation_provider, :result_count, :latency_ms) RETURNING id"
                        ),
                        payload,
                    ).scalar_one()
                )
        except Exception:
            # Telemetry is optional during rolling migration and must not break chat.
            return None

    def add_feedback(self, payload: dict[str, Any]) -> int:
        with self.engine.begin() as conn:
            return int(
                conn.execute(
                    text(
                        "INSERT INTO chatbot_feedback (event_id, rating, reason, comment) "
                        "VALUES (:event_id, :rating, :reason, :comment) RETURNING id"
                    ),
                    payload,
                ).scalar_one()
            )

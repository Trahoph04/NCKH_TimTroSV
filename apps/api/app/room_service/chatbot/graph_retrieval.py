"""Local Graph RAG: typed entity links select records and expand cited provisions.

Every expansion is bounded and keeps the originating record/document citation.
The graph is an immutable release tied to the housing and legal corpus hashes.
"""
from __future__ import annotations

import re
from sqlalchemy import text
from .repo import ChatRepository
from .providers import normalize_text


LOCATION_ALIASES = {
    "xuan_khanh": ("xuan khanh",),
    "street_3_2": ("duong 3/2", "duong 3 thang 2", "duong 3-2"),
}


def graph_schema(value: str) -> str:
    if not re.fullmatch(r"graph_[a-z0-9_]{1,48}", value):
        raise ValueError("Invalid graph schema")
    return value


def location_entities(value: str) -> list[str]:
    normalized = normalize_text(value)
    return ["location:" + key for key, aliases in LOCATION_ALIASES.items()
            if any(re.search(r"(?<!\w)" + re.escape(normalize_text(alias)) + r"(?!\w)", normalized)
                   for alias in aliases)]


class GraphChatRepository(ChatRepository):
    graph_enabled = True

    def __init__(self, engine, legal_schema, listing_schema, schema="graph_rag_v1"):
        super().__init__(engine, legal_schema, listing_schema)
        self.graph_schema = graph_schema(schema)
        # Fail closed on stale or incomplete releases; never silently serve an
        # unrelated graph under a new source configuration.
        with engine.connect() as conn:
            release = conn.execute(text(f"SELECT * FROM {self.graph_schema}.release WHERE id=1")).mappings().one()
            housing_hash = conn.execute(text(f"SELECT catalog_sha256 FROM {self.listing_schema}.release WHERE id=1")).scalar_one()
            legal_hash = conn.execute(text("SELECT manifest_sha256 FROM public.legal_corpus_releases WHERE schema_name=:schema"),
                                      {"schema": self.legal_schema}).scalar_one()
        if (release["listing_schema"] != self.listing_schema or release["legal_schema"] != self.legal_schema
                or release["housing_sha256"] != housing_hash or release["legal_sha256"] != legal_hash):
            raise ValueError("Graph release does not match source corpora")

    def retrieve(self, query, filters, vector, limit=5):
        locations = location_entities(query)
        entity_keys = ["amenity:" + key for key in filters.amenities]
        # Graph location alternatives are OR (e.g. street 3/2 OR Xuan Khanh).
        # Amenities remain an intersection enforced by the structured SQL.
        if locations:
            with self.engine.connect() as conn:
                ids = list(conn.execute(text(
                    f"SELECT DISTINCT n.record_id FROM {self.graph_schema}.edges e "
                    f"JOIN {self.graph_schema}.nodes n ON n.id=e.source "
                    "WHERE e.target=ANY(:locations) AND e.relation='located_in' "
                    "AND n.kind='listing' ORDER BY n.record_id"), {"locations": locations}).scalars())
            if filters.listing_ids:
                ids = [identifier for identifier in ids if identifier in filters.listing_ids]
            if not ids:
                return []
            # Model validation caps conversation IDs at 5; internal graph pools
            # are bounded by the source release and never serialized as filters.
            filters = filters.model_copy(update={"listing_ids": ids})
        rows = super().retrieve(query, filters, vector, limit)
        ids = [f"housing:{row['id']}" for row in rows]
        with self.engine.connect() as conn:
            facts = [dict(row) for row in conn.execute(text(
                f"SELECT source,target,relation,evidence FROM {self.graph_schema}.edges "
                "WHERE source=ANY(:ids) ORDER BY source,relation,target"), {"ids": ids}).mappings()]
        trace = {"stage": "graph_retrieval", "domain": "housing", "max_hops": 1,
                 "seed_entities": locations + entity_keys, "selected_nodes": ids,
                 "traversed_edges": len(facts), "source_schema": self.listing_schema}
        for row in rows:
            row["graph_facts"] = [fact for fact in facts if fact["source"] == f"housing:{row['id']}"]
            row["_graph_trace"] = trace
        return rows

    def retrieve_legal(self, query, vector, limit=5, search_queries=None, categories_override=None):
        rows = super().retrieve_legal(query, vector, limit, search_queries, categories_override)
        seed_ids = list(dict.fromkeys(f"legal:{row['document_id']}:{row['provision_id']}"
                                     for row in rows if row.get("provision_id")))
        if not seed_ids:
            return rows
        with self.engine.connect() as conn:
            # Two outgoing citation hops; path-local cycle guard. Membership
            # edges never fan out to every article in a law or every topic.
            links = [dict(row) for row in conn.execute(text(
                f"WITH RECURSIVE walk AS (SELECT e.source AS seed,e.target,ARRAY[e.source,e.target] AS path,1 AS depth "
                f"FROM {self.graph_schema}.edges e WHERE e.source=ANY(:ids) AND e.relation='cites' "
                f"UNION ALL SELECT w.seed,e.target,w.path||e.target,w.depth+1 FROM walk w "
                f"JOIN {self.graph_schema}.edges e ON e.source=w.target "
                "WHERE e.relation='cites' AND w.depth<2 AND NOT e.target=ANY(w.path)) "
                f"SELECT DISTINCT w.seed,n.document_id,n.provision_id,w.depth FROM walk w "
                f"JOIN {self.graph_schema}.nodes n ON n.id=w.target ORDER BY w.depth,w.seed,n.provision_id LIMIT 24"
            ), {"ids": seed_ids}).mappings()]
            for row in rows:
                seed = f"legal:{row['document_id']}:{row.get('provision_id')}"
                additions = [link for link in links if link["seed"] == seed
                             and link["document_id"] == row["document_id"]]
                included = []
                for link in additions:
                    part = conn.execute(self._legal_sql(
                        "SELECT heading,parent_content,page_from,page_to FROM legal_chunks WHERE document_id=:doc "
                        "AND provision_id=:pid ORDER BY chunk_index LIMIT 1"),
                        {"doc": link["document_id"], "pid": link["provision_id"]}).mappings().first()
                    if not part or not part["parent_content"]:
                        continue
                    if part["parent_content"] in row["content"]:
                        included.append(link["provision_id"])
                        continue
                    supplement = "\n\n" + (part["heading"] or "") + "\n" + part["parent_content"]
                    if len(row["content"]) + len(supplement) <= 5500:
                        row["content"] += supplement
                        for field, reducer in (('page_from', min), ('page_to', max)):
                            bounds = [v for v in (row.get(field), part.get(field)) if v is not None]
                            row[field] = reducer(bounds) if bounds else None
                        included.append(link["provision_id"])
                row["graph_provision_ids"] = included
                row["_graph_trace"] = {"stage": "graph_retrieval", "domain": "legal",
                    "max_hops": 2, "seed_nodes": seed_ids, "traversed_edges": len(links),
                    "included_provisions": included, "source_schema": self.legal_schema}
        return rows

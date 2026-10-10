"""Admin control of the active chatbot corpus; all writes are audited."""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from ...auth import require_admin
from ..chatbot.router import get_service
from .storage import legal_sql

router = APIRouter(prefix="/admin/documents", tags=["admin-documents"])


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    admin_enabled: bool | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Cần ít nhất một thay đổi")
        return self


def document(conn, schema, document_id, lock=False):
    row = conn.execute(legal_sql(
        "SELECT d.*, (SELECT count(*) FROM legal_chunks c WHERE c.document_id=d.id) AS chunk_count "
        "FROM legal_documents d WHERE d.id=:id" + (" FOR UPDATE OF d" if lock else ""), schema
    ), {"id": document_id}).mappings().first()
    if row is None:
        raise HTTPException(404, "Không tìm thấy tài liệu trong bộ dữ liệu đang sử dụng")
    return dict(row)


@router.get("")
def list_documents(q: str = Query("", max_length=200), status: str | None = Query(None, pattern="^(ready|indexing|failed)$"),
                   enabled: bool | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   admin=Depends(require_admin), service=Depends(get_service)):
    schema = service.repo.legal_schema
    # Escape LIKE wildcards so user search text is literal.
    pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    where = ("WHERE (d.title ILIKE :q OR d.category ILIKE :q OR d.source_path ILIKE :q) "
             "AND (CAST(:status AS text) IS NULL OR d.status=:status) "
             "AND (CAST(:enabled AS boolean) IS NULL OR d.admin_enabled=:enabled)")
    params = {"q": pattern, "status": status, "enabled": enabled, "limit": limit, "offset": offset}
    with service.repo.engine.connect() as conn:
        total = conn.execute(legal_sql("SELECT count(*) FROM legal_documents d " + where, schema), params).scalar_one()
        rows = conn.execute(legal_sql(
            "SELECT d.*, (SELECT count(*) FROM legal_chunks c WHERE c.document_id=d.id) AS chunk_count "
            "FROM legal_documents d " + where + " ORDER BY d.updated_at DESC,d.id DESC LIMIT :limit OFFSET :offset", schema
        ), params).mappings().all()
    return {"corpus_schema": schema, "items": [dict(row) for row in rows], "total": total,
            "has_more": offset + len(rows) < total}


@router.get("/{document_id}")
def read_document(document_id: int, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                  admin=Depends(require_admin), service=Depends(get_service)):
    schema = service.repo.legal_schema
    with service.repo.engine.connect() as conn:
        row = document(conn, schema, document_id)
        chunks = conn.execute(legal_sql(
            "SELECT id,chunk_index,page_from,page_to,heading,content,text_quality,quality_warning "
            "FROM legal_chunks WHERE document_id=:id ORDER BY chunk_index LIMIT :limit OFFSET :offset", schema
        ), {"id": document_id, "limit": limit, "offset": offset}).mappings().all()
    return {"corpus_schema": schema, "document": row, "chunks": [dict(c) for c in chunks],
            "has_more": offset + len(chunks) < row["chunk_count"]}


@router.patch("/{document_id}")
def update_document(document_id: int, body: DocumentUpdate, admin=Depends(require_admin), service=Depends(get_service)):
    schema = service.repo.legal_schema
    changes = body.model_dump(exclude_none=True)
    with service.repo.engine.begin() as conn:
        before = document(conn, schema, document_id, lock=True)
        if changes.get("admin_enabled") and (before["status"] != "ready" or before["chunk_count"] == 0):
            raise HTTPException(409, "Chỉ bật tài liệu đã lập chỉ mục thành công và có nội dung")
        fields = ",".join(f"{key}=:{key}" for key in changes)  # keys are constrained by DocumentUpdate
        conn.execute(legal_sql("UPDATE legal_documents SET " + fields + ",updated_at=now() WHERE id=:id", schema),
                     changes | {"id": document_id})
        after = document(conn, schema, document_id)
        conn.execute(text(
            "INSERT INTO legal_document_admin_audit (actor_id,corpus_schema,document_id,before_data,after_data) "
            "VALUES (:actor,:schema,:id,CAST(:before AS jsonb),CAST(:after AS jsonb))"
        ), {"actor": admin.id, "schema": schema, "id": document_id,
            "before": json.dumps(before, default=str, ensure_ascii=False),
            "after": json.dumps(after, default=str, ensure_ascii=False)})
    return {"corpus_schema": schema, "document": after}

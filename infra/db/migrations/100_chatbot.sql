-- Chatbot tìm trọ / KTX / pháp lý thuê trọ (room_service/chatbot, ghép từ branch PHUC — ADR-023).
--
-- Branch PHUC rải phần này ở migration 90/93/94/95/97/98/99/100/101 — trùng số với 90–99 của repo
-- này (extras, contact, matching, map v2…) nên gộp lại 1 file, CHỈ lấy bảng/cột chatbot dùng
-- (bỏ risk, reports, saved_searches, auth_sessions… của các module không ghép).
-- Additive + idempotent: chạy lại trên DB đang có dữ liệu được.

-- ── listing: vector E5 cho truy xuất ngữ nghĩa (embedding_vector VECTOR(384) có sẵn từ 20_listings) ──
ALTER TABLE aggregated_listings
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(120),
    ADD COLUMN IF NOT EXISTS embedded_content_hash CHAR(64),
    ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ,
    -- module risk của PHUC ghi cột này; ở đây luôn NULL ⇒ chatbot coi risk là "chưa đánh giá" (trung tính),
    -- không coi risk_score mặc định 0 là "an toàn"
    ADD COLUMN IF NOT EXISTS risk_evaluated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_listings_chatbot_candidates
    ON aggregated_listings (listing_type, quality_score DESC, freshness_score DESC)
    WHERE status = 'active' AND cleaning_status = 'cleaned';

-- ── kho văn bản pháp lý / KTX (schema public = khung; corpus phục vụ nằm ở schema legal_* riêng) ──
CREATE TABLE IF NOT EXISTS legal_documents (
    id                  BIGSERIAL PRIMARY KEY,
    source_path         TEXT NOT NULL UNIQUE,
    title               TEXT NOT NULL,
    category            VARCHAR(80) NOT NULL DEFAULT 'uncategorized',
    document_type       VARCHAR(16) NOT NULL,
    content_sha256      CHAR(64) NOT NULL,
    page_count          INTEGER NOT NULL DEFAULT 0 CHECK (page_count >= 0),
    ocr_page_count      INTEGER NOT NULL DEFAULT 0 CHECK (ocr_page_count >= 0),
    ocr_engine          VARCHAR(80),
    status              VARCHAR(20) NOT NULL DEFAULT 'ready'
                        CHECK (status IN ('indexing', 'ready', 'failed')),
    error_message       TEXT,
    indexed_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    extraction_version  TEXT,
    -- admin tắt nguồn mà không xoá đoạn/vector; indexer không tự bật lại
    admin_enabled       BOOLEAN NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_legal_documents_category_status
    ON legal_documents (category, status);

CREATE TABLE IF NOT EXISTS legal_chunks (
    id                  BIGSERIAL PRIMARY KEY,
    document_id         BIGINT NOT NULL REFERENCES legal_documents(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL CHECK (chunk_index >= 0),
    page_from           INTEGER CHECK (page_from IS NULL OR page_from >= 1),
    page_to             INTEGER CHECK (page_to IS NULL OR page_to >= 1),
    heading             TEXT,
    content             TEXT NOT NULL,
    content_sha256      CHAR(64) NOT NULL,
    content_tsv         TSVECTOR GENERATED ALWAYS AS (
                            to_tsvector('simple', coalesce(heading, '') || ' ' || content)
                        ) STORED,
    embedding_vector    VECTOR(384),
    embedding_model     VARCHAR(120),
    embedded_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    text_quality        REAL,
    quality_warning     TEXT,
    UNIQUE (document_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_legal_chunks_document ON legal_chunks (document_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_legal_chunks_tsv ON legal_chunks USING GIN (content_tsv);

-- DB đã có bảng từ trước (vd. thử branch PHUC) ⇒ CREATE TABLE ở trên bỏ qua, phải bù cột
ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS extraction_version TEXT;
ALTER TABLE legal_documents ADD COLUMN IF NOT EXISTS admin_enabled BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE legal_chunks ADD COLUMN IF NOT EXISTS text_quality REAL;
ALTER TABLE legal_chunks ADD COLUMN IF NOT EXISTS quality_warning TEXT;

-- sổ phát hành corpus: index_corpus ghi hash manifest để chạy lại bỏ qua nguồn không đổi
CREATE TABLE IF NOT EXISTS legal_corpus_releases (
    schema_name     TEXT PRIMARY KEY,
    status          TEXT NOT NULL CHECK (status IN ('staging', 'validated', 'active', 'retired')),
    manifest_sha256 TEXT,
    validation      JSONB NOT NULL DEFAULT '{}',
    activated_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS legal_document_admin_audit (
    id              BIGSERIAL PRIMARY KEY,
    actor_id        INTEGER NOT NULL REFERENCES users(id),
    corpus_schema   TEXT NOT NULL,
    document_id     BIGINT NOT NULL,
    before_data     JSONB NOT NULL,
    after_data      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── telemetry + phản hồi: không lưu nội dung câu hỏi ở đây (nội dung chỉ ở lịch sử của chủ tài khoản) ──
CREATE TABLE IF NOT EXISTS chatbot_events (
    id                  BIGSERIAL PRIMARY KEY,
    intent              VARCHAR(40) NOT NULL,
    confidence          REAL NOT NULL,
    no_answer           BOOLEAN NOT NULL,
    degraded            BOOLEAN NOT NULL,
    retrieval_mode      VARCHAR(40) NOT NULL,
    generation_provider VARCHAR(40) NOT NULL,
    result_count        INTEGER NOT NULL,
    latency_ms          INTEGER NOT NULL,
    user_id             INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chatbot_events_created ON chatbot_events (created_at DESC);

CREATE TABLE IF NOT EXISTS chatbot_feedback (
    id          BIGSERIAL PRIMARY KEY,
    event_id    BIGINT REFERENCES chatbot_events(id) ON DELETE SET NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating      SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    reason      VARCHAR(80),
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chatbot_feedback_created ON chatbot_feedback (created_at DESC);

-- ── lịch sử theo tài khoản + cache câu trả lời (xoá hội thoại ⇒ xoá luôn cache riêng của nó) ──
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id          UUID PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(120) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_conversations_owner
    ON chatbot_conversations (user_id, updated_at DESC, id);

CREATE TABLE IF NOT EXISTS chatbot_turns (
    id                  BIGSERIAL PRIMARY KEY,
    conversation_id     UUID NOT NULL REFERENCES chatbot_conversations(id) ON DELETE CASCADE,
    question            TEXT NOT NULL CHECK (length(question) BETWEEN 2 AND 2000),
    response            JSONB NOT NULL,
    cache_key           CHAR(64),
    cache_scope         CHAR(64) NOT NULL,
    cache_expires_at    TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_turns_conversation ON chatbot_turns (conversation_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_chat_turns_cache
    ON chatbot_turns (cache_key, cache_scope, cache_expires_at DESC)
    WHERE cache_key IS NOT NULL;

-- cache dùng chung giữa tài khoản cho câu hỏi độc lập (không ngữ cảnh, không thông tin cá nhân)
CREATE TABLE IF NOT EXISTS chatbot_shared_answers (
    cache_key   CHAR(64) NOT NULL,
    cache_scope CHAR(64) NOT NULL,
    response    JSONB NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cache_key, cache_scope)
);
CREATE INDEX IF NOT EXISTS idx_chat_shared_expiry ON chatbot_shared_answers (expires_at);

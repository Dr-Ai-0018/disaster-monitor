CREATE TABLE IF NOT EXISTS workflow_items (
    uuid TEXT PRIMARY KEY,
    current_pool TEXT NOT NULL DEFAULT 'event_pool',
    pool_status TEXT NOT NULL DEFAULT 'pending',
    auto_stage TEXT DEFAULT 'event_ingest',
    manual_stage TEXT DEFAULT 'image_review',
    selected_image_type TEXT,
    last_transition_at INTEGER,
    last_operator TEXT,
    notes TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_items_pool ON workflow_items(current_pool);
CREATE INDEX IF NOT EXISTS idx_workflow_items_status ON workflow_items(pool_status);
CREATE INDEX IF NOT EXISTS idx_workflow_items_pool_updated ON workflow_items(current_pool, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_items_updated ON workflow_items(updated_at DESC);

CREATE TABLE IF NOT EXISTS image_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    selected_image_type TEXT NOT NULL DEFAULT 'post',
    ai_model TEXT,
    ai_score REAL,
    ai_decision TEXT,
    ai_reason TEXT,
    human_decision TEXT,
    review_status TEXT DEFAULT 'pending',
    reviewed_by TEXT,
    reviewed_at INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_image_reviews_uuid ON image_reviews(uuid);
CREATE INDEX IF NOT EXISTS idx_image_reviews_status ON image_reviews(review_status);
CREATE INDEX IF NOT EXISTS idx_image_reviews_uuid_updated ON image_reviews(uuid, updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS summary_reviews (
    uuid TEXT PRIMARY KEY,
    summary_text TEXT,
    summary_status TEXT DEFAULT 'pending',
    approved_by TEXT,
    approved_at INTEGER,
    rejected_reason TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_summary_reviews_status ON summary_reviews(summary_status);

CREATE TABLE IF NOT EXISTS report_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    report_date TEXT NOT NULL,
    included INTEGER DEFAULT 1,
    approved_by TEXT,
    approved_at INTEGER,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_report_candidates_date ON report_candidates(report_date);
CREATE INDEX IF NOT EXISTS idx_report_candidates_uuid ON report_candidates(uuid);
CREATE INDEX IF NOT EXISTS idx_report_candidates_uuid_updated ON report_candidates(uuid, included, updated_at DESC, id DESC);

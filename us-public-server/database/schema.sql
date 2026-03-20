-- ==============================================
-- 灾害监测与分析系统 - 数据库 Schema
-- ==============================================

-- 1. 灾害事件总表
CREATE TABLE IF NOT EXISTS events (
    uuid TEXT PRIMARY KEY,
    event_id INTEGER NOT NULL,
    sub_id INTEGER DEFAULT 0,
    title TEXT NOT NULL,
    category TEXT,
    category_name TEXT,
    country TEXT,
    continent TEXT,
    severity TEXT,
    longitude REAL,
    latitude REAL,
    address TEXT,
    event_date INTEGER,
    last_update INTEGER,
    details_json TEXT,
    source_url TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    pre_image_path TEXT,
    pre_image_date INTEGER,
    pre_image_downloaded INTEGER DEFAULT 0,
    pre_image_source TEXT,
    post_image_path TEXT,
    post_image_date INTEGER,
    post_image_downloaded INTEGER DEFAULT 0,
    post_image_source TEXT,
    quality_score REAL,
    quality_assessment TEXT,
    quality_checked INTEGER DEFAULT 0,
    quality_pass INTEGER DEFAULT 0,
    quality_check_time INTEGER,
    -- 动态影像追踪字段
    pre_window_days INTEGER DEFAULT 7,
    pre_imagery_last_check INTEGER,
    pre_imagery_exhausted INTEGER DEFAULT 0,
    post_window_days INTEGER DEFAULT 7,
    post_imagery_last_check INTEGER,
    post_imagery_open INTEGER DEFAULT 1,
    imagery_check_count INTEGER DEFAULT 0,
    UNIQUE(event_id, sub_id)
);

CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_events_quality_pass ON events(quality_pass);
CREATE INDEX IF NOT EXISTS idx_events_country ON events(country);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_post_imagery_open ON events(post_imagery_open);
CREATE INDEX IF NOT EXISTS idx_events_post_imagery_check ON events(post_imagery_last_check);

-- 2. GEE 影像下载任务表
CREATE TABLE IF NOT EXISTS gee_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    task_id TEXT,
    task_type TEXT NOT NULL,
    status TEXT DEFAULT 'PENDING',
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    roi_geojson TEXT,
    start_date TEXT,
    end_date TEXT,
    cloud_threshold REAL DEFAULT 20.0,
    image_date INTEGER,
    image_source TEXT,
    download_url TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    started_at INTEGER,
    completed_at INTEGER,
    FOREIGN KEY (uuid) REFERENCES events(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gee_tasks_uuid ON gee_tasks(uuid);
CREATE INDEX IF NOT EXISTS idx_gee_tasks_status ON gee_tasks(status);
CREATE INDEX IF NOT EXISTS idx_gee_tasks_task_id ON gee_tasks(task_id);

-- 3. GPU 任务队列表
CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    task_data TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    locked_by TEXT,
    locked_at INTEGER,
    locked_until INTEGER,
    lock_duration INTEGER DEFAULT 7200,
    heartbeat INTEGER,
    heartbeat_interval INTEGER DEFAULT 300,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    failure_reason TEXT,
    last_error_details TEXT,
    progress_stage TEXT DEFAULT 'queued',
    progress_message TEXT,
    progress_percent INTEGER DEFAULT 0,
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    step_details TEXT,
    pause_requested INTEGER DEFAULT 0,
    paused_at INTEGER,
    manual_resume_count INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    completed_at INTEGER,
    FOREIGN KEY (uuid) REFERENCES events(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);
CREATE INDEX IF NOT EXISTS idx_task_queue_priority ON task_queue(priority DESC);
CREATE INDEX IF NOT EXISTS idx_task_queue_locked_until ON task_queue(locked_until);
CREATE INDEX IF NOT EXISTS idx_task_queue_locked_by ON task_queue(locked_by);
CREATE INDEX IF NOT EXISTS idx_task_queue_created_at ON task_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_task_queue_pause_requested ON task_queue(pause_requested);

-- 4. 成品池表
CREATE TABLE IF NOT EXISTS products (
    uuid TEXT PRIMARY KEY,
    inference_result TEXT NOT NULL,
    event_details TEXT NOT NULL,
    event_title TEXT,
    event_category TEXT,
    event_country TEXT,
    summary TEXT,
    summary_generated INTEGER DEFAULT 0,
    summary_generated_at INTEGER,
    pre_image_date INTEGER,
    post_image_date INTEGER,
    inference_quality_score REAL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    FOREIGN KEY (uuid) REFERENCES events(uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_products_summary_generated ON products(summary_generated);
CREATE INDEX IF NOT EXISTS idx_products_created_at ON products(created_at);
CREATE INDEX IF NOT EXISTS idx_products_event_category ON products(event_category);
CREATE INDEX IF NOT EXISTS idx_products_event_country ON products(event_country);

-- 5. 日报存档表
CREATE TABLE IF NOT EXISTS daily_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT NOT NULL UNIQUE,
    report_content TEXT NOT NULL,
    report_title TEXT,
    event_count INTEGER DEFAULT 0,
    category_stats TEXT,
    severity_stats TEXT,
    country_stats TEXT,
    generated_at INTEGER NOT NULL,
    generated_by TEXT DEFAULT 'gemini-flash',
    generation_time_seconds REAL,
    published INTEGER DEFAULT 0,
    published_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports(report_date);
CREATE INDEX IF NOT EXISTS idx_daily_reports_published ON daily_reports(published);

-- 6. 管理员表
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    full_name TEXT,
    role TEXT DEFAULT 'admin',
    permissions TEXT,
    is_active INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL,
    last_login INTEGER,
    login_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_is_active ON admin_users(is_active);

-- 7. API 令牌表
CREATE TABLE IF NOT EXISTS api_tokens (
    token TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    scopes TEXT,
    is_active INTEGER DEFAULT 1,
    last_used INTEGER,
    usage_count INTEGER DEFAULT 0,
    created_at INTEGER NOT NULL,
    expires_at INTEGER,
    created_by INTEGER,
    FOREIGN KEY (created_by) REFERENCES admin_users(id)
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_is_active ON api_tokens(is_active);
CREATE INDEX IF NOT EXISTS idx_api_tokens_name ON api_tokens(name);

-- 8. 全局事件池表（去重后的所有事件总池）
CREATE TABLE IF NOT EXISTS event_pool (
    event_id INTEGER NOT NULL,
    sub_id INTEGER DEFAULT 0,
    title TEXT NOT NULL,
    category TEXT,
    category_name TEXT,
    country TEXT,
    continent TEXT,
    severity TEXT,
    longitude REAL,
    latitude REAL,
    address TEXT,
    event_date INTEGER,
    last_update INTEGER,
    details_json TEXT,
    source_url TEXT,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    fetch_count INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    deactivated_at INTEGER,
    related_uuid TEXT,
    PRIMARY KEY (event_id, sub_id)
);

CREATE INDEX IF NOT EXISTS idx_event_pool_is_active ON event_pool(is_active);
CREATE INDEX IF NOT EXISTS idx_event_pool_last_update ON event_pool(last_update);
CREATE INDEX IF NOT EXISTS idx_event_pool_category ON event_pool(category);
CREATE INDEX IF NOT EXISTS idx_event_pool_country ON event_pool(country);
CREATE INDEX IF NOT EXISTS idx_event_pool_severity ON event_pool(severity);
CREATE INDEX IF NOT EXISTS idx_event_pool_last_seen ON event_pool(last_seen);

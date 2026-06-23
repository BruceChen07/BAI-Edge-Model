from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import config


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    language TEXT NOT NULL DEFAULT 'zh-CN',
    theme TEXT NOT NULL DEFAULT 'light',
    default_model TEXT NOT NULL DEFAULT 'qwen-local',
    embedding_model TEXT NOT NULL DEFAULT 'bge-small-zh-v1.5',
    ocr_enabled INTEGER NOT NULL DEFAULT 1,
    storage_root TEXT NOT NULL,
    web_search_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    file_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    kb_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    ocr_status TEXT NOT NULL DEFAULT 'pending',
    index_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_sha256 ON documents(sha256);
CREATE INDEX IF NOT EXISTS idx_documents_kb ON documents(kb_id, parse_status, index_status);

CREATE TABLE IF NOT EXISTS parse_tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL NOT NULL DEFAULT 0,
    error_code TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    kb_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    page_no INTEGER,
    sheet_name TEXT DEFAULT '',
    slide_no INTEGER,
    heading_path TEXT DEFAULT '',
    token_count INTEGER NOT NULL DEFAULT 0,
    vector_ref TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(document_id) REFERENCES documents(id),
    FOREIGN KEY(kb_id) REFERENCES knowledge_bases(id)
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON document_chunks(document_id, chunk_index);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'chat',
    language TEXT NOT NULL DEFAULT 'zh-CN',
    rag_enabled INTEGER NOT NULL DEFAULT 1,
    agent_enabled INTEGER NOT NULL DEFAULT 0,
    last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_last_message_at ON sessions(last_message_at);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    model_name TEXT DEFAULT '',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'done',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS message_citations (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    page_no INTEGER,
    sheet_name TEXT DEFAULT '',
    slide_no INTEGER,
    quote_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    memory_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    importance REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.5,
    write_mode TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'active',
    source_session_id TEXT DEFAULT '',
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT DEFAULT '',
    expires_at TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(memory_type, status, importance);
CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash);
CREATE INDEX IF NOT EXISTS idx_memories_session ON memories(source_session_id);
-- FTS5 virtual table for full-text memory search
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    title, content, tags,
    content='memories',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    step_count INTEGER NOT NULL DEFAULT 0,
    final_answer TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_steps (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_no INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    tool_name TEXT DEFAULT '',
    tool_input TEXT DEFAULT '',
    tool_output TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'done',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_steps_run ON agent_steps(run_id, step_no);

CREATE TABLE IF NOT EXISTS model_catalog (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT 'unknown',
    param_size TEXT NOT NULL DEFAULT 'unknown',
    version TEXT DEFAULT '',
    score_total REAL NOT NULL DEFAULT 0,
    score_quality REAL NOT NULL DEFAULT 0,
    score_speed REAL NOT NULL DEFAULT 0,
    score_fit REAL NOT NULL DEFAULT 0,
    score_context REAL NOT NULL DEFAULT 0,
    fit_level TEXT NOT NULL DEFAULT 'unknown',
    estimated_tps REAL NOT NULL DEFAULT 0,
    quantization TEXT NOT NULL DEFAULT 'Q4_K_M',
    memory_required_gb REAL NOT NULL DEFAULT 0,
    vram_required_gb REAL NOT NULL DEFAULT 0,
    run_mode TEXT NOT NULL DEFAULT 'CPU',
    use_case TEXT NOT NULL DEFAULT 'general',
    max_context INTEGER NOT NULL DEFAULT 8192,
    is_moe INTEGER NOT NULL DEFAULT 0,
    available INTEGER NOT NULL DEFAULT 0,
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'manual',
    raw_json TEXT DEFAULT '',
    last_synced_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_catalog_name ON model_catalog(model_name);
CREATE INDEX IF NOT EXISTS idx_catalog_provider ON model_catalog(provider);
CREATE INDEX IF NOT EXISTS idx_catalog_param_size ON model_catalog(param_size);
CREATE INDEX IF NOT EXISTS idx_catalog_fit ON model_catalog(fit_level, score_total);
CREATE INDEX IF NOT EXISTS idx_catalog_use_case ON model_catalog(use_case);

CREATE TABLE IF NOT EXISTS download_jobs (
    id TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    total_bytes INTEGER NOT NULL DEFAULT 0,
    downloaded_bytes INTEGER NOT NULL DEFAULT 0,
    chunk_size INTEGER NOT NULL DEFAULT 1048576,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    priority INTEGER NOT NULL DEFAULT 2,
    output_path TEXT NOT NULL DEFAULT '',
    started_at TEXT DEFAULT '',
    completed_at TEXT DEFAULT '',
    last_progress_at TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status);
CREATE INDEX IF NOT EXISTS idx_download_jobs_model ON download_jobs(model_name);

CREATE TABLE IF NOT EXISTS exports (
    id TEXT PRIMARY KEY,
    export_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exports_status ON exports(status, created_at);

CREATE TABLE IF NOT EXISTS operation_logs (
    id TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    action TEXT NOT NULL,
    target_id TEXT NOT NULL,
    result TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_directories() -> None:
    for path in [config.storage_root, config.files_root, config.exports_root, config.logs_root, config.indexes_root]:
        path.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_directories()
    with sqlite3.connect(config.db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            """
            INSERT INTO app_settings (id, storage_root)
            VALUES (1, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (str(config.storage_root),),
        )
        conn.commit()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

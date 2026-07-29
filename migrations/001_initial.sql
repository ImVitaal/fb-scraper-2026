CREATE TABLE session_profiles (
    profile_id TEXT PRIMARY KEY,
    session_class TEXT NOT NULL,
    source_browser TEXT,
    health TEXT NOT NULL,
    created_at TEXT NOT NULL,
    inspected_at TEXT NOT NULL
);

CREATE TABLE discovery_campaigns (
    campaign_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE discovery_queries (
    query_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(campaign_id),
    keyword TEXT NOT NULL,
    location TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE candidate_hits (
    hit_id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL REFERENCES discovery_queries(query_id),
    group_id TEXT NOT NULL,
    rank INTEGER NOT NULL CHECK (rank >= 1),
    raw_capture_id TEXT,
    observed_at TEXT NOT NULL
);

CREATE TABLE selected_targets (
    selection_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(campaign_id),
    group_id TEXT NOT NULL,
    selected_at TEXT NOT NULL
);

CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    state TEXT NOT NULL CHECK (
        state IN (
            'planned', 'running', 'partial', 'succeeded', 'failed',
            'interrupted', 'cancelled'
        )
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL UNIQUE,
    surface TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    health TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    UNIQUE(task_id, attempt_number)
);

CREATE TABLE failures (
    failure_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL REFERENCES attempts(attempt_id) ON DELETE CASCADE,
    failure_class TEXT NOT NULL,
    message TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE raw_captures (
    capture_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL CHECK (
        length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    source_url TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    storage_path TEXT,
    byte_count INTEGER CHECK (byte_count IS NULL OR byte_count >= 0)
);

CREATE TABLE pagination_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    raw_capture_id TEXT NOT NULL REFERENCES raw_captures(capture_id),
    cursor TEXT,
    interaction_number INTEGER NOT NULL CHECK (interaction_number >= 0),
    durable_at TEXT NOT NULL,
    UNIQUE(task_id, interaction_number)
);

CREATE TABLE groups (
    group_id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    raw_capture_id TEXT NOT NULL REFERENCES raw_captures(capture_id),
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);

CREATE TABLE posts (
    post_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES groups(group_id),
    canonical_url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    raw_capture_id TEXT NOT NULL REFERENCES raw_captures(capture_id),
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);

CREATE TABLE comments (
    comment_id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES posts(post_id),
    group_id TEXT NOT NULL REFERENCES groups(group_id),
    parent_comment_id TEXT CHECK (parent_comment_id IS NULL),
    observed_at TEXT NOT NULL,
    raw_capture_id TEXT NOT NULL REFERENCES raw_captures(capture_id),
    schema_version TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);

CREATE TABLE counter_observations (
    observation_id INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('group', 'post', 'comment')),
    entity_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    value INTEGER NOT NULL CHECK (value >= 0),
    raw_capture_id TEXT NOT NULL REFERENCES raw_captures(capture_id),
    UNIQUE(entity_type, entity_id, metric, observed_at)
);

CREATE TABLE export_manifests (
    manifest_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    schema_version TEXT NOT NULL,
    output_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE cleanup_receipts (
    receipt_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    cutoff_at TEXT NOT NULL,
    dry_run INTEGER NOT NULL CHECK (dry_run IN (0, 1)),
    deleted_count INTEGER NOT NULL CHECK (deleted_count >= 0),
    created_at TEXT NOT NULL
);

CREATE INDEX idx_candidate_hits_query_rank
ON candidate_hits(query_id, rank);

CREATE INDEX idx_tasks_job_state
ON tasks(job_id, state);

CREATE INDEX idx_posts_group_observed
ON posts(group_id, observed_at);

CREATE INDEX idx_comments_post_observed
ON comments(post_id, observed_at);

CREATE INDEX idx_counter_observations_entity_metric
ON counter_observations(entity_type, entity_id, metric, observed_at);

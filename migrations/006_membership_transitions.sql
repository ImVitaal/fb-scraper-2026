ALTER TABLE candidate_hits ADD COLUMN membership_state TEXT NOT NULL DEFAULT 'joined'
CHECK (membership_state IN ('joined', 'join_available', 'join_requested'));

CREATE TABLE membership_transitions (
    transition_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(campaign_id),
    candidate_hit_id TEXT NOT NULL REFERENCES candidate_hits(hit_id),
    group_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action = 'join'),
    state TEXT NOT NULL CHECK (state IN ('planned', 'joined', 'pending', 'rejected', 'stopped')),
    planned_at TEXT NOT NULL,
    actioned_at TEXT,
    completed_at TEXT,
    confirmation_capture_id TEXT REFERENCES raw_captures(capture_id),
    telemetry_json TEXT NOT NULL CHECK (json_valid(telemetry_json)),
    UNIQUE(campaign_id),
    UNIQUE(candidate_hit_id)
);

CREATE INDEX idx_membership_transitions_group_state
ON membership_transitions(group_id, state);

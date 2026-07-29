CREATE TABLE live_runs (
    job_id TEXT PRIMARY KEY REFERENCES jobs(job_id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL REFERENCES session_profiles(profile_id),
    campaign_id TEXT NOT NULL REFERENCES discovery_campaigns(campaign_id),
    group_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    lower_bound TEXT NOT NULL,
    adapter_version TEXT NOT NULL
);

CREATE UNIQUE INDEX live_runs_profile_campaign
ON live_runs(profile_id, campaign_id);
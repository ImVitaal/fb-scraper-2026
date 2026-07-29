ALTER TABLE candidate_hits ADD COLUMN source TEXT NOT NULL DEFAULT 'discovery';
ALTER TABLE candidate_hits ADD COLUMN canonical_url TEXT;
ALTER TABLE candidate_hits ADD COLUMN name TEXT;
ALTER TABLE selected_targets ADD COLUMN candidate_hit_id TEXT REFERENCES candidate_hits(hit_id);

CREATE UNIQUE INDEX candidate_once_per_query
ON candidate_hits(query_id, group_id);

CREATE UNIQUE INDEX one_selected_target_per_campaign
ON selected_targets(campaign_id);

CREATE TRIGGER validate_candidate_source_insert
BEFORE INSERT ON candidate_hits
WHEN NEW.source NOT IN ('discovery', 'direct_url', 'csv')
  OR (NEW.source IN ('direct_url', 'csv') AND NEW.canonical_url IS NULL)
BEGIN
    SELECT RAISE(ABORT, 'invalid candidate source or URL');
END;

CREATE TRIGGER validate_selected_target_insert
BEFORE INSERT ON selected_targets
WHEN NEW.candidate_hit_id IS NULL
  OR NOT EXISTS (
      SELECT 1
      FROM candidate_hits AS hit
      JOIN discovery_queries AS query ON query.query_id = hit.query_id
      WHERE hit.hit_id = NEW.candidate_hit_id
        AND query.campaign_id = NEW.campaign_id
        AND hit.group_id = NEW.group_id
  )
BEGIN
    SELECT RAISE(ABORT, 'selected candidate does not belong to campaign');
END;
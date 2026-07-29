CREATE TEMP TABLE p1_02_integrity_guard (
    value INTEGER NOT NULL CHECK (value = 0)
);

INSERT INTO p1_02_integrity_guard(value)
SELECT 1
WHERE EXISTS (
    SELECT 1
    FROM session_profiles
    WHERE session_class NOT IN ('imported', 'guided_login', 'fixture', 'replay')
       OR health NOT IN (
            'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
            'membership_required', 'login_required', 'session_invalid',
            'session_expired', 'session_challenged', 'session_restricted',
            'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
       )
    UNION ALL
    SELECT 1
    FROM tasks
    WHERE state NOT IN (
        'planned', 'running', 'partial', 'succeeded', 'failed',
        'interrupted', 'cancelled'
    )
    UNION ALL
    SELECT 1
    FROM attempts
    WHERE health NOT IN (
        'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
        'membership_required', 'login_required', 'session_invalid',
        'session_expired', 'session_challenged', 'session_restricted',
        'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
    )
    UNION ALL
    SELECT 1
    FROM candidate_hits
    WHERE raw_capture_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1
          FROM raw_captures
          WHERE raw_captures.capture_id = candidate_hits.raw_capture_id
      )
);

DROP TABLE p1_02_integrity_guard;

CREATE TRIGGER validate_session_profile_insert
BEFORE INSERT ON session_profiles
WHEN NEW.session_class NOT IN ('imported', 'guided_login', 'fixture', 'replay')
  OR NEW.health NOT IN (
      'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
      'membership_required', 'login_required', 'session_invalid',
      'session_expired', 'session_challenged', 'session_restricted',
      'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
  )
BEGIN
    SELECT RAISE(ABORT, 'invalid session profile state');
END;

CREATE TRIGGER validate_session_profile_update
BEFORE UPDATE OF session_class, health ON session_profiles
WHEN NEW.session_class NOT IN ('imported', 'guided_login', 'fixture', 'replay')
  OR NEW.health NOT IN (
      'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
      'membership_required', 'login_required', 'session_invalid',
      'session_expired', 'session_challenged', 'session_restricted',
      'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
  )
BEGIN
    SELECT RAISE(ABORT, 'invalid session profile state');
END;

CREATE TRIGGER validate_task_state_insert
BEFORE INSERT ON tasks
WHEN NEW.state NOT IN (
    'planned', 'running', 'partial', 'succeeded', 'failed',
    'interrupted', 'cancelled'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid task state');
END;

CREATE TRIGGER validate_task_state_update
BEFORE UPDATE OF state ON tasks
WHEN NEW.state NOT IN (
    'planned', 'running', 'partial', 'succeeded', 'failed',
    'interrupted', 'cancelled'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid task state');
END;

CREATE TRIGGER validate_attempt_health_insert
BEFORE INSERT ON attempts
WHEN NEW.health NOT IN (
    'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
    'membership_required', 'login_required', 'session_invalid',
    'session_expired', 'session_challenged', 'session_restricted',
    'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid attempt health');
END;

CREATE TRIGGER validate_attempt_health_update
BEFORE UPDATE OF health ON attempts
WHEN NEW.health NOT IN (
    'observed', 'unchanged', 'partial', 'unavailable', 'access_limited',
    'membership_required', 'login_required', 'session_invalid',
    'session_expired', 'session_challenged', 'session_restricted',
    'temporarily_blocked', 'rate_limited', 'parser_drift', 'network_failed'
)
BEGIN
    SELECT RAISE(ABORT, 'invalid attempt health');
END;

CREATE TRIGGER validate_candidate_capture_insert
BEFORE INSERT ON candidate_hits
WHEN NEW.raw_capture_id IS NOT NULL
 AND NOT EXISTS (
     SELECT 1 FROM raw_captures WHERE capture_id = NEW.raw_capture_id
 )
BEGIN
    SELECT RAISE(ABORT, 'candidate raw capture does not exist');
END;

CREATE TRIGGER validate_candidate_capture_update
BEFORE UPDATE OF raw_capture_id ON candidate_hits
WHEN NEW.raw_capture_id IS NOT NULL
 AND NOT EXISTS (
     SELECT 1 FROM raw_captures WHERE capture_id = NEW.raw_capture_id
 )
BEGIN
    SELECT RAISE(ABORT, 'candidate raw capture does not exist');
END;

CREATE TRIGGER restrict_candidate_capture_delete
BEFORE DELETE ON raw_captures
WHEN EXISTS (
    SELECT 1 FROM candidate_hits WHERE raw_capture_id = OLD.capture_id
)
BEGIN
    SELECT RAISE(ABORT, 'raw capture is referenced by a candidate hit');
END;

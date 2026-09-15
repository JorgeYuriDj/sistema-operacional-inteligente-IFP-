CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS responses (
 id TEXT PRIMARY KEY,
 submission_key TEXT NOT NULL UNIQUE,
 payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 survey_version TEXT NOT NULL,
 privacy_version TEXT NOT NULL,
 stage TEXT NOT NULL CHECK(stage IN ('s12','s34','s56','s78','graduate')),
 area TEXT NOT NULL CHECK(area IN ('gym','group','personal','sport','health','management','unsure')),
 format TEXT NOT NULL CHECK(format IN ('short','workshops','events','mentoring','complete','online','combined')),
 private_data TEXT NOT NULL,
 contact_consent INTEGER NOT NULL CHECK(contact_consent IN (0,1)),
 research_consent INTEGER NOT NULL CHECK(research_consent=1)
);
CREATE INDEX IF NOT EXISTS responses_created ON responses(created_at);
CREATE INDEX IF NOT EXISTS responses_stage ON responses(stage,created_at);
CREATE TABLE IF NOT EXISTS response_gaps (
 response_id TEXT NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
 gap TEXT NOT NULL CHECK(gap IN ('training','classes','service','communication','sales','leadership','business','all')),
 PRIMARY KEY(response_id,gap)
);
CREATE TRIGGER IF NOT EXISTS gaps_max_two BEFORE INSERT ON response_gaps
 WHEN (SELECT COUNT(*) FROM response_gaps WHERE response_id=NEW.response_id)>=2
 BEGIN SELECT RAISE(ABORT,'maximum_two_choices'); END;
CREATE TRIGGER IF NOT EXISTS gaps_exclusive BEFORE INSERT ON response_gaps
 WHEN EXISTS(SELECT 1 FROM response_gaps WHERE response_id=NEW.response_id AND (gap='all' OR NEW.gap='all'))
 BEGIN SELECT RAISE(ABORT,'exclusive_choice'); END;
CREATE TABLE IF NOT EXISTS administrators (
 username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, totp_encrypted TEXT NOT NULL,
 last_totp_step INTEGER NOT NULL DEFAULT -1
);
CREATE TABLE IF NOT EXISTS admin_sessions (
 token_hash TEXT PRIMARY KEY, username TEXT NOT NULL REFERENCES administrators(username),
 expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_limits (
 bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
 action TEXT NOT NULL, record_id TEXT, actor TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_version VALUES(1,strftime('%Y-%m-%dT%H:%M:%SZ','now'));

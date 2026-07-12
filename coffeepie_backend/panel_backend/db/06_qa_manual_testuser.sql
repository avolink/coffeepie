-- Coffee Pie Panel — QA-ONLY manual test user requested for ad-hoc panel checks.
--
-- 'testuser@testuser.com' / 'testuser', role: admin (sees everything, like
-- testing@coffeepie.co). QA-only — honored only when QA_LOCAL_AUTH=true.
--
-- ⚠️ QA ONLY. Depends on 01_schema.sql, 02_seed.sql, 03_qa_auth.sql.
-- Not applied by db/qa_up.sh's default loop (01-03 only) — apply manually
-- after a fresh qa_up.sh run if this user needs to persist across resets.

BEGIN;

INSERT INTO app_user (id, email, display_name) VALUES
    ('00000000-0000-0000-0000-0000000000c9', 'testuser@testuser.com', 'Manual Test User')
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_role (user_id, role) VALUES
    ('00000000-0000-0000-0000-0000000000c9', 'admin')
ON CONFLICT DO NOTHING;

INSERT INTO qa_credential (user_id, password_hash) VALUES
    ('00000000-0000-0000-0000-0000000000c9',
     'pbkdf2_sha256$100000$0b59812fc426c68665ce370928a045c6$6fb808cd8dad8756da4d65208549c6e47cbb0575dda2d3ec642972992e524d45')
ON CONFLICT (user_id) DO UPDATE SET password_hash = EXCLUDED.password_hash;

COMMIT;

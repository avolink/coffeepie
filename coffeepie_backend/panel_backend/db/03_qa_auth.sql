-- Coffee Pie Panel — QA-ONLY local authentication.
--
-- ⚠️  QA / LOCAL TESTING ONLY. This table exists so the prototype login can be
-- validated end-to-end without standing up Supabase/Firebase. Production auth is
-- Supabase (the backend stores NO passwords). This file must NEVER be applied to
-- any database holding real users. The backend only honors these credentials
-- when QA_LOCAL_AUTH=true.
--
-- Password format: PBKDF2-HMAC-SHA256, 100000 iterations, stored as
-- "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>".

BEGIN;

CREATE TABLE IF NOT EXISTS qa_credential (
    user_id       UUID PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL
);

-- The memorable QA login: testing@coffeepie.co / testing  (admin, sees everything)
INSERT INTO app_user (id, email, display_name) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'testing@coffeepie.co', 'QA Testing User')
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_role (user_id, role) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'admin')
ON CONFLICT DO NOTHING;

INSERT INTO qa_credential (user_id, password_hash) VALUES
    ('00000000-0000-0000-0000-0000000000ff',
     'pbkdf2_sha256$100000$c0ffee1e5a17c0ffee1e5a1700000001$06a9f4fd75fb92fbb2ba6da2be18d18bc2ac6eaf7b51cd6097638901b2ac0fa6')
ON CONFLICT (user_id) DO UPDATE SET password_hash = EXCLUDED.password_hash;

-- Also give every seeded role-user the same password ("testing") so QA can log
-- in as any role and exercise the panel's role-specific views.
INSERT INTO qa_credential (user_id, password_hash)
SELECT id,
       'pbkdf2_sha256$100000$c0ffee1e5a17c0ffee1e5a1700000001$06a9f4fd75fb92fbb2ba6da2be18d18bc2ac6eaf7b51cd6097638901b2ac0fa6'
FROM app_user
WHERE email LIKE '%@qa.coffeepie.co'
ON CONFLICT (user_id) DO NOTHING;

COMMIT;

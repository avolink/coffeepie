-- Coffee Pie Panel — Custom Access Token Hook.
--
-- Problem this fixes: SupabaseIdentityProvider.verify() (app/auth/supabase_provider.py)
-- reads roles from the JWT's app_metadata.roles claim — by design, so
-- verification never needs a DB round-trip. But Supabase's GoTrue mints that
-- JWT from auth.users.raw_app_meta_data, which has NO idea our own `user_role`
-- table exists. Granting a role via `user_role` alone (e.g. through the panel,
-- or an admin SQL statement) had zero effect on a real user's access — the
-- role only ever showed up in the DB, never in the token.
--
-- Fix: a Custom Access Token Hook — a Postgres function GoTrue calls on every
-- login/refresh to build the JWT's claims — that reads `user_role` LIVE and
-- injects it as app_metadata.roles. `user_role` stays the single source of
-- truth; nothing needs to keep two copies in sync.
--
-- Apply via SQL Editor / psql, THEN wire it up in the Dashboard:
--   Authentication → Hooks → Custom Access Token Hook → select
--   public.custom_access_token_hook. (Supabase does not auto-enable a hook
--   just because the function exists — this last step is manual, dashboard-
--   or Management-API-only, no SQL for it.)
--
-- Idempotent: safe to re-run.

BEGIN;

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
-- supabase_auth_admin's search_path does not include `public` — every
-- unqualified reference silently resolved to nothing and GoTrue reported it
-- only as an opaque "Error running hook", no real detail. Schema-qualifying
-- user_role AND pinning search_path here (belt and suspenders) is what
-- actually fixed it; found by calling the function directly as different
-- roles until it reproduced.
SET search_path = public
AS $$
DECLARE
    claims     jsonb;
    user_roles jsonb;
BEGIN
    SELECT COALESCE(jsonb_agg(role), '[]'::jsonb)
    INTO user_roles
    FROM public.user_role
    WHERE user_id = (event ->> 'user_id')::uuid;

    claims := event -> 'claims';
    -- Merge into the existing app_metadata object (keeps provider/providers
    -- etc. that Supabase already put there) rather than replacing it.
    -- coalesce claims itself too: a token with no app_metadata at all would
    -- otherwise make the jsonb_set no-op (jsonb_set can't create more than
    -- one missing nesting level at a time).
    claims := jsonb_set(
        COALESCE(claims, '{}'::jsonb),
        '{app_metadata,roles}',
        user_roles,
        true
    );
    event := jsonb_set(event, '{claims}', claims);
    RETURN event;
END;
$$;

-- GoTrue calls this AS supabase_auth_admin — it must be able to execute the
-- function and read user_role, but no one else should be able to call a
-- function that reaches into arbitrary users' role data.
GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM authenticated, anon, public;

GRANT SELECT ON public.user_role TO supabase_auth_admin;
DROP POLICY IF EXISTS allow_auth_admin_read_roles ON user_role;
CREATE POLICY allow_auth_admin_read_roles ON user_role
    FOR SELECT TO supabase_auth_admin USING (true);

COMMIT;

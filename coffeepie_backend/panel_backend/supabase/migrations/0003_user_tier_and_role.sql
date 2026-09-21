-- Coffee Pie Panel — consumer 'user' role + account tier (streaming entitlement).
--
-- Adds:
--   * 'user' to cofp_role — the base consumer class (advertiser/provider/etc.
--     are supply-side; 'user' is a plain end consumer, distinct from 'admin').
--   * app_user.tier — the package tier that gates premium features. Browser
--     streaming is entitled to 'Big_Package'; lower/free tiers use the Codec
--     Terminal. Stored on the account (not derived from invoices) so it is an
--     explicit, auditable attribute.
--   * tier is injected into the JWT (app_metadata.tier) by the custom access
--     token hook, exactly like roles, so the backend/frontend can gate on it
--     without a DB round-trip.
--   * RLS SELECT policy on app_user for supabase_auth_admin — the hook runs as
--     that role and RLS would otherwise hide the row, making tier read NULL.
--
-- ALTER TYPE ADD VALUE cannot run inside a txn block; keep it outside BEGIN.
-- Idempotent.

ALTER TYPE cofp_role ADD VALUE IF NOT EXISTS 'user';

BEGIN;

ALTER TABLE app_user ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'free';

DROP POLICY IF EXISTS allow_auth_admin_read_profile ON app_user;
CREATE POLICY allow_auth_admin_read_profile ON app_user
    FOR SELECT TO supabase_auth_admin USING (true);
GRANT SELECT ON public.app_user TO supabase_auth_admin;

CREATE OR REPLACE FUNCTION public.custom_access_token_hook(event jsonb)
RETURNS jsonb LANGUAGE plpgsql STABLE SET search_path = public AS $fn$
DECLARE
    claims     jsonb;
    user_roles jsonb;
    user_tier  text;
BEGIN
    SELECT COALESCE(jsonb_agg(role), '[]'::jsonb) INTO user_roles
    FROM public.user_role WHERE user_id = (event ->> 'user_id')::uuid;

    SELECT tier INTO user_tier
    FROM public.app_user WHERE id = (event ->> 'user_id')::uuid;

    claims := jsonb_set(COALESCE(event -> 'claims', '{}'::jsonb),
                        '{app_metadata,roles}', user_roles, true);
    claims := jsonb_set(claims, '{app_metadata,tier}',
                        to_jsonb(COALESCE(user_tier, 'free')), true);
    event := jsonb_set(event, '{claims}', claims);
    RETURN event;
END;
$fn$;

GRANT EXECUTE ON FUNCTION public.custom_access_token_hook TO supabase_auth_admin;
REVOKE EXECUTE ON FUNCTION public.custom_access_token_hook FROM authenticated, anon, public;

COMMIT;

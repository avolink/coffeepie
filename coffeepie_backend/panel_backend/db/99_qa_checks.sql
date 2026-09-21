-- QA verification queries. Run after schema + seed. Not part of deploy init.
\echo '== balances (expect a3=240.000000, a4=500.000000) =='
SELECT account_id, balance FROM account_balance ORDER BY account_id;

\echo '== roles per user =='
SELECT u.email, array_agg(r.role ORDER BY r.role) AS roles
FROM app_user u JOIN user_role r ON r.user_id = u.id
GROUP BY u.email ORDER BY u.email;

\echo '== dedup guard: re-inserting an existing dedup_key must NOT add a row =='
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, instance_id, dedup_key)
VALUES ('00000000-0000-0000-0000-0000000000a3', 'accrual', 999, 'double-mint attempt',
        'cp-qa-instance-1', 'cp-qa-instance-1:2026-06-11T10:00')
ON CONFLICT (dedup_key) DO NOTHING;

\echo '== balance after dup attempt (a3 must STILL be 240, not 1239) =='
SELECT account_id, balance FROM account_balance WHERE account_id = '00000000-0000-0000-0000-0000000000a3';

\echo '== nodes =='
SELECT name, status, vcores, ram_gb, gpu_vram_mb, location FROM node ORDER BY name;

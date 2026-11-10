-- Run after setup.sql to check it worked. Each query should return what the comment says.

-- Should return TRUE for both tables
select relname, relrowsecurity from pg_class where relname in ('journal_state', 'broker_fills') order by relname;

-- journal_state: your 3 original policies plus "Scanner can read the journal for backups" (4 rows)
select policyname, cmd from pg_policies where tablename = 'journal_state' order by policyname;

-- broker_fills: 4 policies (Owner reads fills, Owner marks fills imported, Scanner adds fills, Scanner reads fills)
select policyname, cmd from pg_policies where tablename = 'broker_fills' order by policyname;

-- Should list your scanner user (and you)
select email, created_at, email_confirmed_at is not null as confirmed from auth.users order by created_at;

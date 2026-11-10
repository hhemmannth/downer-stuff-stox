-- OPTIONAL, and only AFTER two-factor is working for you.
-- Order: 1) turn on two-factor in the app (Settings > Two-factor sign-in), 2) sign out, sign in again WITH your code and check
-- the journal loads, 3) only then run this. It makes the database itself refuse your journal unless the session passed the code check,
-- so a stolen password alone is not enough, even if someone calls the API directly. The scanner user is exempt (it has no phone).
--
-- If you ever get locked out: open Supabase > SQL Editor and run the three "drop policy" lines at the bottom (the dashboard is not affected by these rules).

drop policy if exists "Require two-factor" on public.journal_state;
create policy "Require two-factor" on public.journal_state as restrictive for all to authenticated
  using ((auth.jwt() ->> 'aal') = 'aal2' or public.is_scanner())
  with check ((auth.jwt() ->> 'aal') = 'aal2' or public.is_scanner());

drop policy if exists "Require two-factor" on public.broker_fills;
create policy "Require two-factor" on public.broker_fills as restrictive for all to authenticated
  using ((auth.jwt() ->> 'aal') = 'aal2' or public.is_scanner())
  with check ((auth.jwt() ->> 'aal') = 'aal2' or public.is_scanner());

-- TO UNDO (run these if you are locked out):
-- drop policy if exists "Require two-factor" on public.journal_state;
-- drop policy if exists "Require two-factor" on public.broker_fills;

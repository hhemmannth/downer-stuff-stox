-- DownerStuff: Supabase setup. Run this ONCE in Supabase > SQL Editor > New query > paste > Run.
-- It is safe to run again. It does not change or remove anything you already have:
-- your three journal_state policies stay exactly as they are.
--
-- BEFORE YOU RUN IT: if your scanner user's email is not hhemmannth+scanner@gmail.com, change it in the function below.

-- 1) Who is the scanner? (the second login used only by the GitHub jobs)
create or replace function public.is_scanner()
returns boolean
language sql
stable
as $$
  select lower(coalesce(auth.jwt() ->> 'email', '')) = lower('hhemmannth+scanner@gmail.com')
$$;

-- 2) The scanner may READ your journal (for the nightly encrypted backup). It cannot change or delete it.
drop policy if exists "Scanner can read the journal for backups" on public.journal_state;
create policy "Scanner can read the journal for backups"
  on public.journal_state for select to authenticated
  using (public.is_scanner());

-- 3) Broker fills: what Angel One reports after the close. The scanner adds rows; only you can read and mark them.
create table if not exists public.broker_fills (
  fill_id     text primary key,
  user_id     uuid not null references auth.users (id) on delete cascade,
  source      text not null default 'angelone',
  symbol      text not null,
  exchange    text,
  product     text,
  instrument  text,
  side        text not null check (side in ('BUY', 'SELL')),
  qty         numeric not null,
  price       numeric not null,
  lot         numeric,
  option_type text,
  strike      numeric,
  expiry      text,
  filled_at   timestamptz not null,
  imported    boolean not null default false,
  raw         jsonb,
  created_at  timestamptz not null default now()
);
create index if not exists broker_fills_user_time on public.broker_fills (user_id, filled_at desc);
alter table public.broker_fills enable row level security;
grant select, insert, update on public.broker_fills to authenticated;

drop policy if exists "Owner reads fills" on public.broker_fills;
create policy "Owner reads fills" on public.broker_fills for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Owner marks fills imported" on public.broker_fills;
create policy "Owner marks fills imported" on public.broker_fills for update to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Scanner adds fills" on public.broker_fills;
create policy "Scanner adds fills" on public.broker_fills for insert to authenticated with check (public.is_scanner());

drop policy if exists "Scanner reads fills" on public.broker_fills;
create policy "Scanner reads fills" on public.broker_fills for select to authenticated using (public.is_scanner());

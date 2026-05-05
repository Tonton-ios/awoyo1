-- AWOYO - Correctif permissions admin + Realtime
-- A coller dans Supabase > SQL Editor, puis Run.
--
-- Corrige l'erreur admin:
-- "Impossible de charger les logs. Verifie les permissions Supabase sur scan_logs."
--
-- Pourquoi:
-- admin.html lit maintenant des vues publiques limitees:
--   public.awoyo_admin_scan_logs
--   public.awoyo_admin_bracelets
-- Les vues n'exposent pas la colonne sensible bracelets.token.

-- 1) Activer RLS sur les tables originales.
alter table public.scan_logs enable row level security;
alter table public.bracelets enable row level security;

-- 2) Creer des vues speciales admin avec seulement les colonnes utiles.
drop view if exists public.awoyo_admin_scan_logs;
drop view if exists public.awoyo_admin_bracelets;

create view public.awoyo_admin_scan_logs as
select
  scanned_at,
  bracelet_uid,
  status,
  scanned_by
from public.scan_logs;

create view public.awoyo_admin_bracelets as
select
  uid,
  bracelet_num,
  scanned,
  scanned_at,
  scanned_by
from public.bracelets;

-- 3) Donner l'acces lecture aux vues, pas au token.
grant usage on schema public to anon, authenticated;

grant select on public.awoyo_admin_scan_logs to anon, authenticated;
grant select on public.awoyo_admin_bracelets to anon, authenticated;

-- Petite permission directe utile a Supabase Realtime/PostgREST quand RLS verifie les tables.
grant select (scanned_at, bracelet_uid, status, scanned_by) on public.scan_logs to anon, authenticated;
grant select (uid, bracelet_num, scanned, scanned_at, scanned_by) on public.bracelets to anon, authenticated;

-- La fonction scan_bracelet doit pouvoir etre appelee par le scanner.
grant execute on function public.scan_bracelet(text, text)
to anon, authenticated;

-- Optionnel, pour les anciennes parties du scanner qui lisent encore dashboard_stats.
do $$
begin
  if to_regclass('public.dashboard_stats') is not null then
    grant select on public.dashboard_stats to anon, authenticated;
  end if;
end
$$;

-- 4) Policies RLS: lecture autorisee pour le dashboard admin et Realtime.
do $$
begin
  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'scan_logs'
      and policyname = 'awoyo_admin_read_scan_logs'
  ) then
    create policy awoyo_admin_read_scan_logs
    on public.scan_logs
    for select
    to anon, authenticated
    using (true);
  end if;

  if not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = 'bracelets'
      and policyname = 'awoyo_admin_read_bracelets'
  ) then
    create policy awoyo_admin_read_bracelets
    on public.bracelets
    for select
    to anon, authenticated
    using (true);
  end if;
end
$$;

-- 5) Realtime: ajoute les deux tables a la publication Supabase si absent.
-- Si cette partie echoue avec un message de permission, active Realtime a la main:
-- Supabase Dashboard > Database > Replication > active scan_logs et bracelets.
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    if not exists (
      select 1
      from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = 'scan_logs'
    ) then
      begin
        alter publication supabase_realtime add table public.scan_logs;
      exception when others then
        raise notice 'Realtime scan_logs non active automatiquement: %', sqlerrm;
      end;
    end if;

    if not exists (
      select 1
      from pg_publication_tables
      where pubname = 'supabase_realtime'
        and schemaname = 'public'
        and tablename = 'bracelets'
    ) then
      begin
        alter publication supabase_realtime add table public.bracelets;
      exception when others then
        raise notice 'Realtime bracelets non active automatiquement: %', sqlerrm;
      end;
    end if;
  end if;
end
$$;

-- 6) Verification rapide apres execution:
select 'scan_logs_view' as test, count(*) from public.awoyo_admin_scan_logs;
select 'bracelets_view' as test, count(*) from public.awoyo_admin_bracelets;

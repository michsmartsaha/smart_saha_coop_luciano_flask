-- ============================================================================
-- SMARTSAHABIO - POLITIQUES DE SÉCURITÉ POSTGRESQL (RLS) POUR AUDITEUR BIO
-- À exécuter dans le SQL Editor de Supabase (https://supabase.com/dashboard)
-- ============================================================================

-- 1. Fonction sécurisée de détection du rôle Auditeur Bio
create or replace function public.is_bio_auditor()
returns boolean
language sql
security definer
set search_path = public
as $$
  select (
    coalesce((auth.jwt() -> 'user_metadata' ->> 'role'), '') = 'bio_auditor'
    or exists (
      select 1 from public.user_profiles
      where id = auth.uid() and role = 'bio_auditor'
    )
  );
$$;

-- 2. Lecture seule de toutes les coopératives pour l'auditeur bio
drop policy if exists "Bio auditors can view all cooperatives" on public.cooperatives;
create policy "Bio auditors can view all cooperatives"
  on public.cooperatives
  for select
  using (public.is_bio_auditor());

-- 3. Lecture seule de tous les agriculteurs pour l'auditeur bio
drop policy if exists "Bio auditors can view all farmers" on public.farmers;
create policy "Bio auditors can view all farmers"
  on public.farmers
  for select
  using (public.is_bio_auditor());

-- 4. Lecture seule de toutes les parcelles pour l'auditeur bio
drop policy if exists "Bio auditors can view all parcels" on public.parcels;
create policy "Bio auditors can view all parcels"
  on public.parcels
  for select
  using (public.is_bio_auditor());

-- 5. Accès complet aux audits biologiques pour l'auditeur bio (visualisation et création)
drop policy if exists "Bio auditors can view all bio audits" on public.audits_bio;
create policy "Bio auditors can view all bio audits"
  on public.audits_bio
  for select
  using (public.is_bio_auditor());

drop policy if exists "Bio auditors can create bio audits" on public.audits_bio;
create policy "Bio auditors can create bio audits"
  on public.audits_bio
  for insert
  with check (public.is_bio_auditor());

drop policy if exists "Bio auditors can update bio audits" on public.audits_bio;
create policy "Bio auditors can update bio audits"
  on public.audits_bio
  for update
  using (public.is_bio_auditor())
  with check (public.is_bio_auditor());

drop policy if exists "Bio auditors can delete bio audits" on public.audits_bio;
create policy "Bio auditors can delete bio audits"
  on public.audits_bio
  for delete
  using (public.is_bio_auditor());

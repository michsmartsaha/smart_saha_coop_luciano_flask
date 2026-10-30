create extension if not exists postgis;
create extension if not exists pgcrypto;

create table if not exists public.cooperatives (
  uuid              uuid primary key default gen_random_uuid(),
  name              text not null,
  president_name    text not null,
  email             text,
  mobile            text,
  address           text,
  legal_status      text not null
                    check (legal_status in ('cooperative', 'group', 'other')),
  year_of_creation  int not null
                    check (year_of_creation between 1900 and 2100),
  status            text not null
                    check (status in ('active', 'not_active', 'na')),
  main_crop         text not null,
  second_crop       text,
  third_crop        text,
  owner             uuid not null
                    references auth.users(id)
                    on delete cascade,
  created_at        timestamptz not null default now()
);

alter table public.cooperatives enable row level security;

create policy "Owners manage their own cooperative"
  on public.cooperatives
  for all
  using (auth.uid() = owner)
  with check (auth.uid() = owner);



create table if not exists public.user_profiles (
    id uuid primary key
        references auth.users(id)
        on delete cascade,

    first_name text not null,

    last_name text not null,

    phone text,

    role text not null
        check (
            role in (
                'admin',
                'cooperative_manager',
                'field_agent',
                'bio_auditor',
                'consultant'
            )
        ),

    created_at timestamptz not null default now(),

    updated_at timestamptz not null default now()
);

alter table public.user_profiles
enable row level security;

create policy "Users can view their own profile"
on public.user_profiles
for select
using (auth.uid() = id);

create policy "Users can update their own profile"
on public.user_profiles
for update
using (auth.uid() = id)
with check (auth.uid() = id);


create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.user_profiles (
        id,
        first_name,
        last_name,
        phone,
        role
    )
    values (
        new.id,
        coalesce(new.raw_user_meta_data ->> 'first_name', ''),
        coalesce(new.raw_user_meta_data ->> 'last_name', ''),
        new.raw_user_meta_data ->> 'phone',
        coalesce(
            new.raw_user_meta_data ->> 'role',
            'field_agent'
        )
    );

    return new;
end;
$$;

drop trigger if exists on_auth_user_created
on auth.users;

create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_new_user();


create table if not exists public.farmers (

  uuid              uuid primary key default gen_random_uuid(),
  cooperative_id    uuid not null
                    references public.cooperatives(uuid)
                    on delete cascade,
  full_name         text not null,
  year_of_birth     int not null
                    check (year_of_birth between 1900 and 2025),
  gender            text not null
                    check (gender in ('male', 'female', 'other')),
  id_card           text not null,
  phone             text,
  handicap          boolean not null default false,
  marital_status    text not null
                    check (
                      marital_status in (
                        'single',
                        'married',
                        'divorced',
                        'widowed',
                        'other'
                      )
                    ),
  household_number  int not null
                    check (household_number >= 0),
  status            text not null
                    check (
                      status in (
                        'active',
                        'not_active',
                        'na'
                      )
                    ),

  owner             uuid not null
                    references auth.users(id)
                    on delete cascade,

  created_at        timestamptz not null default now()

);

create index if not exists farmers_cooperative_idx
on public.farmers (cooperative_id);

alter table public.farmers enable row level security;

create policy "Owners manage their own farmers"

on public.farmers
for all

using (auth.uid() = owner)

with check (auth.uid() = owner);



create table if not exists public.parcels (

  uuid              uuid primary key default gen_random_uuid(),

  cooperative_id    uuid not null
                    references public.cooperatives(uuid)
                    on delete cascade,

  farmer_id         uuid not null
                    references public.farmers(uuid)
                    on delete cascade,

  geom              geometry(Geometry, 4326) not null,

  area_ha           numeric,

  owner             uuid not null
                    references auth.users(id)
                    on delete cascade,

  name              text,

  created_at        timestamptz not null default now()

);

create index if not exists parcels_geom_gix
on public.parcels
using gist (geom);

create index if not exists parcels_cooperative_idx
on public.parcels (cooperative_id);

create index if not exists parcels_farmer_idx
on public.parcels (farmer_id);

-- Contrainte d'unicité sur le nom de la parcelle par coopérative
create unique index if not exists parcels_cooperative_name_unique_idx
on public.parcels (cooperative_id, lower(trim(name)))
where name is not null and trim(name) != '';

alter table public.parcels enable row level security;

create policy "Owners manage their own parcels"
on public.parcels
for all
using (auth.uid() = owner)
with check (auth.uid() = owner);


create or replace function public.calculate_parcel_area()
returns trigger
language plpgsql
as $$
begin

    if new.geom is not null then

        new.area_ha :=
            ST_Area(new.geom::geography) / 10000;

    else

        new.area_ha := null;

    end if;

    return new;

end;
$$;

drop trigger if exists parcels_calculate_area
on public.parcels;

create trigger parcels_calculate_area
before insert or update of geom
on public.parcels
for each row
execute function public.calculate_parcel_area();


create or replace function public.insert_parcel(
    p_cooperative_id uuid,
    p_farmer_id uuid,
    p_geom jsonb,
    p_owner uuid,
    p_name text default null
)
returns public.parcels
language plpgsql
security definer
set search_path = public
as $$
declare
    v_parcel public.parcels;
begin

    -- L'utilisateur connecté doit être le propriétaire demandé
    if auth.uid() is null
       or auth.uid() <> p_owner then

        raise exception 'Utilisateur non autorisé';
    end if;


    -- La coopérative doit appartenir à l'utilisateur
    if not exists (
        select 1
        from public.cooperatives
        where uuid = p_cooperative_id
          and owner = auth.uid()
    ) then

        raise exception 'Coopérative non autorisée';
    end if;


    -- L'agriculteur doit appartenir à cette coopérative
    if not exists (
        select 1
        from public.farmers
        where uuid = p_farmer_id
          and cooperative_id = p_cooperative_id
          and owner = auth.uid()
    ) then

        raise exception 'Agriculteur non autorisé';
    end if;


    insert into public.parcels (
        cooperative_id,
        farmer_id,
        geom,
        owner,
        name
    )
    values (
        p_cooperative_id,
        p_farmer_id,
        ST_SetSRID(
            ST_GeomFromGeoJSON(p_geom::text),
            4326
        ),
        p_owner,
        p_name
    )
    returning * into v_parcel;


    return v_parcel;

end;
$$;


create or replace function public.update_parcel(
    p_parcel_id uuid,
    p_cooperative_id uuid,
    p_geom jsonb
)
returns public.parcels
language plpgsql
security definer
set search_path = public
as $$
declare
    v_parcel public.parcels;
begin

    -- La parcelle doit appartenir à l'utilisateur connecté
    if not exists (
        select 1
        from public.parcels
        where uuid = p_parcel_id
          and cooperative_id = p_cooperative_id
          and owner = auth.uid()
    ) then

        raise exception 'Parcelle non autorisée';
    end if;


    update public.parcels
    set
        geom = ST_SetSRID(
            ST_GeomFromGeoJSON(p_geom::text),
            4326
        )
    where uuid = p_parcel_id
      and cooperative_id = p_cooperative_id
      and owner = auth.uid();


    select *
    into v_parcel
    from public.parcels
    where uuid = p_parcel_id
      and cooperative_id = p_cooperative_id
      and owner = auth.uid();


    return v_parcel;

end;
$$;


create or replace function public.get_parcel_details(
    p_parcel_id uuid,
    p_cooperative_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_parcel jsonb;
begin

    select jsonb_build_object(
        'uuid', p.uuid,
        'cooperative_id', p.cooperative_id,
        'farmer_id', p.farmer_id,
        'name', p.name,
        'area_ha', p.area_ha,
        'owner', p.owner,
        'created_at', p.created_at,

        'geom', ST_AsGeoJSON(p.geom)::jsonb,

        'cooperative', jsonb_build_object(
            'uuid', c.uuid,
            'name', c.name,
            'president_name', c.president_name
        ),

        'farmer', jsonb_build_object(
            'uuid', f.uuid,
            'full_name', f.full_name,
            'gender', f.gender,
            'year_of_birth', f.year_of_birth,
            'id_card', f.id_card,
            'status', f.status
        )
    )
    into v_parcel

    from public.parcels p

    join public.cooperatives c
        on c.uuid = p.cooperative_id

    join public.farmers f
        on f.uuid = p.farmer_id

    where p.uuid = p_parcel_id
      and p.cooperative_id = p_cooperative_id
      and p.owner = auth.uid();

    if v_parcel is null then
        raise exception 'Parcelle introuvable ou non autorisée';
    end if;

    return v_parcel;

end;
$$;


-- ============================================================================
-- SMARTSAHABIO - SUIVI DES FEUX
-- Source : NASA FIRMS
-- ============================================================================

create table if not exists public.fire_detections (

    uuid uuid primary key default gen_random_uuid(),

    latitude double precision not null,

    longitude double precision not null,

    geom geometry(Point, 4326) not null,

    detected_at timestamptz not null,

    satellite text,

    instrument text,

    confidence text,

    frp numeric,

    daynight text,

    source text not null default 'NASA_FIRMS',

    external_id text,

    created_at timestamptz not null default now()
);

create index if not exists fire_detections_geom_gix
on public.fire_detections
using gist (geom);

create index if not exists fire_detections_detected_at_idx
on public.fire_detections (detected_at);

create unique index if not exists fire_detections_external_id_idx
on public.fire_detections (external_id)
where external_id is not null;

alter table public.fire_detections
enable row level security;

create policy "Authenticated users can view fire detections"
on public.fire_detections for select to authenticated using (true);


-- ============================================================================
-- SMARTSAHABIO - SUIVI DES ALERTES DE FEUX
-- ============================================================================
create table if not exists public.fire_alerts (

    uuid uuid primary key default gen_random_uuid(),
    fire_id uuid not null
        references public.fire_detections(uuid)
        on delete cascade,
    parcel_id uuid not null
        references public.parcels(uuid)
        on delete cascade,
    distance_m numeric not null,
    radius_m numeric not null,
    alert_type text not null
        check (
            alert_type in (
                'email',
                'notification',
                'sms'
            )
        ),
    recipient text,
    status text not null default 'pending'
        check (
            status in (
                'pending',
                'sent',
                'failed'
            )
        ),
    sent_at timestamptz,
    error_message text,
    created_at timestamptz not null default now()
);

create index if not exists fire_alerts_fire_idx
on public.fire_alerts (fire_id);

create index if not exists fire_alerts_parcel_idx
on public.fire_alerts (parcel_id);

create index if not exists fire_alerts_created_at_idx
on public.fire_alerts (created_at);

alter table public.fire_alerts
enable row level security;

create policy "Owners can view their fire alerts"
on public.fire_alerts
for select
using (
    exists (
        select 1
        from public.parcels p
        where p.uuid = fire_alerts.parcel_id
          and p.owner = auth.uid()
    )
);

create policy "Owners can update their fire alerts"
on public.fire_alerts
for update
using (
    exists (
        select 1
        from public.parcels p
        where p.uuid = fire_alerts.parcel_id
          and p.owner = auth.uid()
    )
)
with check (
    exists (
        select 1
        from public.parcels p
        where p.uuid = fire_alerts.parcel_id
          and p.owner = auth.uid()
    )
);

create unique index if not exists fire_alerts_unique_detection_parcel_type
on public.fire_alerts (
    fire_id,
    parcel_id,
    alert_type
);


create or replace function public.get_fire_history(
    p_period_hours integer
)
returns setof public.fire_detections
language sql
security invoker
set search_path = public
as $$
    select f.*
    from public.fire_detections f
    where f.detected_at >= now() - make_interval(
        hours => p_period_hours
    )
    order by f.detected_at desc;
$$;


-- ============================================================================
-- SMARTSAHABIO - MIGRATION FIRE_DETECTIONS
-- Ajout des informations complémentaires provenant de NASA FIRMS
-- ============================================================================

alter table public.fire_detections
    add column if not exists bright_ti4 numeric;

alter table public.fire_detections
    add column if not exists bright_ti5 numeric;

alter table public.fire_detections
    add column if not exists scan numeric;

alter table public.fire_detections
    add column if not exists track numeric;

alter table public.fire_detections
    add column if not exists version text;


-- ============================================================================
-- CONTRAINTES SUR LES COORDONNÉES
-- ============================================================================

alter table public.fire_detections
    drop constraint if exists fire_detections_latitude_check;

alter table public.fire_detections
    add constraint fire_detections_latitude_check
    check (latitude between -90 and 90);

alter table public.fire_detections
    drop constraint if exists fire_detections_longitude_check;

alter table public.fire_detections
    add constraint fire_detections_longitude_check
    check (longitude between -180 and 180);


-- ============================================================================
-- FONCTION D'INSERTION DES DÉTECTIONS DE FEUX
-- ============================================================================
CREATE OR REPLACE FUNCTION public.insert_fire_detection(
    p_latitude double precision,
    p_longitude double precision,
    p_detected_at timestamptz,
    p_satellite text,
    p_instrument text,
    p_confidence text,
    p_frp numeric,
    p_daynight text,
    p_source text,
    p_external_id text,
    p_bright_ti4 numeric,
    p_bright_ti5 numeric,
    p_scan numeric,
    p_track numeric,
    p_version text
)
RETURNS public.fire_detections
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_fire public.fire_detections;
BEGIN

    -- Vérification de la latitude
    IF p_latitude < -90 OR p_latitude > 90 THEN
        RAISE EXCEPTION 'Latitude invalide : %', p_latitude;
    END IF;

    -- Vérification de la longitude
    IF p_longitude < -180 OR p_longitude > 180 THEN
        RAISE EXCEPTION 'Longitude invalide : %', p_longitude;
    END IF;

    -- Insertion ou mise à jour
    INSERT INTO public.fire_detections (
        latitude,
        longitude,
        geom,
        detected_at,
        satellite,
        instrument,
        confidence,
        frp,
        daynight,
        source,
        external_id,
        bright_ti4,
        bright_ti5,
        scan,
        track,
        version
    )
    VALUES (
        p_latitude,
        p_longitude,

        ST_SetSRID(
            ST_MakePoint(
                p_longitude,
                p_latitude
            ),
            4326
        ),

        p_detected_at,
        p_satellite,
        p_instrument,
        p_confidence,
        p_frp,
        p_daynight,
        COALESCE(p_source, 'NASA_FIRMS'),
        p_external_id,
        p_bright_ti4,
        p_bright_ti5,
        p_scan,
        p_track,
        p_version
    )

    ON CONFLICT (external_id)
    DO UPDATE SET
        latitude = EXCLUDED.latitude,
        longitude = EXCLUDED.longitude,
        geom = EXCLUDED.geom,
        detected_at = EXCLUDED.detected_at,
        satellite = EXCLUDED.satellite,
        instrument = EXCLUDED.instrument,
        confidence = EXCLUDED.confidence,
        frp = EXCLUDED.frp,
        daynight = EXCLUDED.daynight,
        source = EXCLUDED.source,
        bright_ti4 = EXCLUDED.bright_ti4,
        bright_ti5 = EXCLUDED.bright_ti5,
        scan = EXCLUDED.scan,
        track = EXCLUDED.track,
        version = EXCLUDED.version

    RETURNING *
    INTO v_fire;

    RETURN v_fire;

END;
$$;

DROP INDEX IF EXISTS public.fire_detections_external_id_idx;

ALTER TABLE public.fire_detections
ADD CONSTRAINT fire_detections_external_id_unique
UNIQUE (external_id);


-- ============================================================================
-- FONCTION POUR RÉCUPÉRER LES PARCELLES À PROXIMITÉ DES DÉTECTIONS DE FEUX
-- ============================================================================
DROP FUNCTION IF EXISTS public.get_nearby_fire_parcels(numeric);

CREATE OR REPLACE FUNCTION public.get_nearby_fire_parcels(
    p_radius_m numeric DEFAULT 5000,
    p_period_hours integer DEFAULT 168
)
RETURNS TABLE (
    fire_id uuid,
    parcel_id uuid,
    cooperative_id uuid,
    distance_m numeric,
    fire_latitude double precision,
    fire_longitude double precision,
    fire_detected_at timestamptz,
    fire_confidence text,
    fire_frp numeric,
    parcel_geometry jsonb
)
LANGUAGE sql
SECURITY INVOKER
SET search_path = public
AS $$
    SELECT
        f.uuid AS fire_id,
        p.uuid AS parcel_id,
        p.cooperative_id AS cooperative_id,

        ROUND(
            ST_Distance(
                f.geom::geography,
                p.geom::geography
            )::numeric,
            2
        ) AS distance_m,

        f.latitude AS fire_latitude,
        f.longitude AS fire_longitude,
        f.detected_at AS fire_detected_at,
        f.confidence AS fire_confidence,
        f.frp AS fire_frp,

        ST_AsGeoJSON(p.geom)::jsonb AS parcel_geometry

    FROM public.fire_detections f

    INNER JOIN public.parcels p
        ON ST_DWithin(
            f.geom::geography,
            p.geom::geography,
            p_radius_m
        )

    WHERE
        p.owner = auth.uid()
        AND f.detected_at >= now() - make_interval(hours => p_period_hours)

    ORDER BY distance_m ASC;
$$;


create unique index if not exists fire_alerts_fire_parcel_type_idx
on public.fire_alerts (
    fire_id,
    parcel_id,
    alert_type
);


create or replace function public.create_fire_alerts(
    p_radius_m numeric default 5000,
    p_period_hours integer default 168
)
returns integer
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_count integer := 0;
begin

    insert into public.fire_alerts (
        fire_id,
        parcel_id,
        distance_m,
        radius_m,
        alert_type,
        recipient,
        status
    )
    select
        f.uuid,
        p.uuid,
        round(
            st_distance(
                f.geom::geography,
                p.geom::geography
            )::numeric,
            2
        ),
        p_radius_m,
        'notification',
        null,
        'pending'
    from public.fire_detections f
    inner join public.parcels p
        on st_dwithin(
            f.geom::geography,
            p.geom::geography,
            p_radius_m
        )
    where
        p.owner = auth.uid()
        and f.detected_at >= now()
            - make_interval(hours => p_period_hours)
    on conflict (
        fire_id,
        parcel_id,
        alert_type
    )
    do nothing;

    get diagnostics v_count = row_count;

    return v_count;

end;
$$;



create or replace function public.create_fire_alerts(
    p_radius_m numeric default 5000,
    p_period_hours integer default 168
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
    v_count integer := 0;
begin

    insert into public.fire_alerts (
        fire_id,
        parcel_id,
        distance_m,
        radius_m,
        alert_type,
        recipient,
        status
    )
    select
        f.uuid,
        p.uuid,
        round(
            st_distance(
                f.geom::geography,
                p.geom::geography
            )::numeric,
            2
        ),
        p_radius_m,
        'notification',
        null,
        'pending'
    from public.fire_detections f
    inner join public.parcels p
        on st_dwithin(
            f.geom::geography,
            p.geom::geography,
            p_radius_m
        )
    where
        p.owner = auth.uid()
        and f.detected_at >= now()
            - make_interval(hours => p_period_hours)
    on conflict (
        fire_id,
        parcel_id,
        alert_type
    )
    do nothing;

    get diagnostics v_count = row_count;

    return v_count;

end;
$$;


grant execute
on function public.create_fire_alerts(numeric, integer)
to authenticated;



-- ============================================================================
-- SmartSahaBio
-- Table : audits_bio
-- Formulaire d'audit biologique statique
-- ============================================================================

create table if not exists public.audits_bio (

  uuid uuid primary key default gen_random_uuid(),

  parcel_id uuid not null
    references public.parcels(uuid)
    on delete cascade,

  auditor_name text not null,

  audit_date date not null default current_date,


  -- --------------------------------------------------------------------------
  -- Historique de conversion biologique
  -- --------------------------------------------------------------------------

  conversion_start_date date,

  conversion_status text not null default 'not_started'
    check (
      conversion_status in (
        'not_started',
        'in_conversion',
        'certified'
      )
    ),


  -- --------------------------------------------------------------------------
  -- Pratiques agricoles
  -- --------------------------------------------------------------------------

  inputs_used text,

  seed_origin text,

  pest_management_method text,

  -- Cultures présentes dans les parcelles voisines
  neighboring_crops text,

  -- Distance de la zone tampon en mètres
  buffer_zone_distance_m numeric,

  -- Niveau de risque de contamination
  contamination_risk text not null default 'low'
    check (
      contamination_risk in (
        'low',
        'medium',
        'high'
      )
    ),


  -- --------------------------------------------------------------------------
  -- Traçabilité
  -- --------------------------------------------------------------------------

  -- Registre de la parcelle tenu
  parcel_register_kept boolean not null default false,

  -- Registre des intrants tenu
  inputs_register_kept boolean not null default false,

  -- Registre des récoltes tenu
  harvest_register_kept boolean not null default false,

  -- Registre des ventes tenu
  sales_register_kept boolean not null default false,

  -- Séparation des flux biologiques / non biologiques
  bio_nonbio_separation text,


  -- --------------------------------------------------------------------------
  -- Stockage et manutention post-récolte
  -- --------------------------------------------------------------------------

  storage_handling_notes text,


  -- --------------------------------------------------------------------------
  -- Constat de conformité
  -- --------------------------------------------------------------------------

  -- Description des non-conformités constatées
  non_conformities text,

  -- Gravité de la non-conformité
  non_conformity_severity text not null default 'none'
    check (
      non_conformity_severity in (
        'none',
        'minor',
        'major',
        'critical'
      )
    ),

  -- Plan d'actions correctives
  corrective_action_plan text,

  -- Date limite pour les actions correctives
  corrective_action_deadline date,

  overall_status text not null default 'compliant'
    check (
      overall_status in (
        'compliant',
        'non_compliant',
        'compliant_with_reservations'
      )
    ),

  -- Signature de l'auditeur
  -- Stockée sous forme de Data URL PNG Base64
  auditor_signature text,

  owner uuid not null
    references auth.users(id)
    on delete cascade,

  created_at timestamptz not null default now(),

  updated_at timestamptz not null default now()

);


-- ============================================================================
-- 2. INDEX
-- ============================================================================

-- Recherche des audits par parcelle
create index if not exists audits_bio_parcel_idx
  on public.audits_bio (parcel_id);

-- Recherche des audits appartenant à un utilisateur
create index if not exists audits_bio_owner_idx
  on public.audits_bio (owner);

-- Recherche par date d'audit
create index if not exists audits_bio_date_idx
  on public.audits_bio (audit_date);

-- Recherche par statut global
create index if not exists audits_bio_status_idx
  on public.audits_bio (overall_status);


-- ============================================================================
-- 3. TRIGGER : updated_at
-- ============================================================================

create or replace function public.update_audits_bio_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;


drop trigger if exists set_audits_bio_updated_at
on public.audits_bio;


create trigger set_audits_bio_updated_at
before update on public.audits_bio
for each row
execute function public.update_audits_bio_updated_at();

alter table public.audits_bio enable row level security;

drop policy if exists "Owners manage their own bio audits"
on public.audits_bio;


create policy "Owners manage their own bio audits"
on public.audits_bio
for all
using (
  auth.uid() = owner
)
with check (
  auth.uid() = owner
);


-- ============================================================================
-- 6. COMMENTAIRES
-- ============================================================================

comment on table public.audits_bio
is 'Audits biologiques réalisés sur les parcelles des coopératives.';


comment on column public.audits_bio.parcel_id
is 'Parcelle concernée par l''audit.';


comment on column public.audits_bio.conversion_status
is 'Statut de conversion vers l''agriculture biologique.';


comment on column public.audits_bio.contamination_risk
is 'Niveau de risque de contamination croisée.';


comment on column public.audits_bio.non_conformity_severity
is 'Niveau de gravité des non-conformités constatées.';


comment on column public.audits_bio.overall_status
is 'Conclusion globale de l''audit.';


comment on column public.audits_bio.auditor_signature
is 'Signature de l''auditeur sous forme de Data URL PNG Base64.';


-- ============================================================================
-- LOT 2 : FORMULAIRES D'ENQUÊTE DYNAMIQUES & RÉPONSES
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Table des formulaires d'enquête
-- ----------------------------------------------------------------------------
create table if not exists public.survey_forms (
  uuid              uuid primary key default gen_random_uuid(),
  title             text not null,
  description       text,
  campaign          text not null,
  cooperative_id    uuid not null
                    references public.cooperatives(uuid)
                    on delete cascade,
  version           int not null default 1 check (version >= 1),
  status            text not null default 'draft'
                    check (status in ('draft', 'published', 'archived')),
  fields            jsonb not null default '[]'::jsonb,
  owner             uuid not null
                    references auth.users(id)
                    on delete cascade,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- Index pour survey_forms
create index if not exists survey_forms_cooperative_idx
  on public.survey_forms (cooperative_id);

create index if not exists survey_forms_campaign_idx
  on public.survey_forms (campaign);

create index if not exists survey_forms_owner_idx
  on public.survey_forms (owner);

create index if not exists survey_forms_status_idx
  on public.survey_forms (status);

-- Trigger updated_at pour survey_forms
create or replace function public.update_survey_forms_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_survey_forms_updated_at on public.survey_forms;
create trigger set_survey_forms_updated_at
before update on public.survey_forms
for each row
execute function public.update_survey_forms_updated_at();

-- RLS pour survey_forms
alter table public.survey_forms enable row level security;

drop policy if exists "Users manage their own survey forms" on public.survey_forms;
drop policy if exists "Owners manage their survey forms" on public.survey_forms;
drop policy if exists "Users can read published survey forms" on public.survey_forms;

create policy "Owners manage their survey forms"
on public.survey_forms
for all
using (auth.uid() = owner)
with check (auth.uid() = owner);

create policy "Users can read published survey forms"
on public.survey_forms
for select
using (
  auth.uid() = owner
  or status = 'published'
);


-- ----------------------------------------------------------------------------
-- 2. Table des réponses aux enquêtes
-- ----------------------------------------------------------------------------
create table if not exists public.survey_responses (
  uuid              uuid primary key default gen_random_uuid(),
  form_id           uuid not null
                    references public.survey_forms(uuid)
                    on delete cascade,
  form_version      int not null default 1,
  cooperative_id    uuid not null
                    references public.cooperatives(uuid)
                    on delete cascade,
  farmer_id         uuid
                    references public.farmers(uuid)
                    on delete set null,
  parcel_id         uuid
                    references public.parcels(uuid)
                    on delete set null,
  answers           jsonb not null default '{}'::jsonb,
  latitude          double precision,
  longitude         double precision,
  submitted_by      uuid not null
                    references auth.users(id)
                    on delete cascade,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- Index pour survey_responses
create index if not exists survey_responses_form_idx
  on public.survey_responses (form_id);

create index if not exists survey_responses_cooperative_idx
  on public.survey_responses (cooperative_id);

create index if not exists survey_responses_farmer_idx
  on public.survey_responses (farmer_id);

create index if not exists survey_responses_submitted_by_idx
  on public.survey_responses (submitted_by);

create index if not exists survey_responses_created_at_idx
  on public.survey_responses (created_at desc);

-- Trigger updated_at pour survey_responses
create or replace function public.update_survey_responses_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_survey_responses_updated_at on public.survey_responses;
create trigger set_survey_responses_updated_at
before update on public.survey_responses
for each row
execute function public.update_survey_responses_updated_at();

-- RLS pour survey_responses
alter table public.survey_responses enable row level security;

drop policy if exists "Users manage their own survey responses" on public.survey_responses;
drop policy if exists "Users can view survey responses" on public.survey_responses;
drop policy if exists "Users can insert their own survey responses" on public.survey_responses;
drop policy if exists "Users can update their own survey responses" on public.survey_responses;
drop policy if exists "Users or form owners can delete survey responses" on public.survey_responses;

create policy "Users can view survey responses"
on public.survey_responses
for select
using (
  auth.uid() = submitted_by
  or exists (
    select 1 from public.survey_forms sf
    where sf.uuid = survey_responses.form_id
    and sf.owner = auth.uid()
  )
  or exists (
    select 1 from public.cooperatives c
    where c.uuid = survey_responses.cooperative_id
    and c.owner = auth.uid()
  )
);

create policy "Users can insert their own survey responses"
on public.survey_responses
for insert
with check (auth.uid() = submitted_by);

create policy "Users can update their own survey responses"
on public.survey_responses
for update
using (auth.uid() = submitted_by)
with check (auth.uid() = submitted_by);

create policy "Users or form owners can delete survey responses"
on public.survey_responses
for delete
using (
  auth.uid() = submitted_by
  or exists (
    select 1 from public.survey_forms sf
    where sf.uuid = survey_responses.form_id
    and sf.owner = auth.uid()
  )
);

-- Commentaires
comment on table public.survey_forms
is 'Formulaires d''enquête dynamiques paramétrés par les coopératives et campagnes.';

comment on table public.survey_responses
is 'Réponses collectées lors des enquêtes sur le terrain ou sur l''application web.';



-- 1. Politique RLS permettant aux propriétaires de mettre à jour le statut de leurs alertes
create policy "Owners can update their fire alerts"
on public.fire_alerts
for update
using (
    exists (
        select 1
        from public.parcels p
        where p.uuid = fire_alerts.parcel_id
          and p.owner = auth.uid()
    )
)
with check (
    exists (
        select 1
        from public.parcels p
        where p.uuid = fire_alerts.parcel_id
          and p.owner = auth.uid()
    )
);

-- 2. Fonction RPC sécurisée pour marquer une alerte comme transmise
create or replace function public.send_fire_alert(
    p_alert_id uuid,
    p_recipient text default null
)
returns public.fire_alerts
language plpgsql
security definer
set search_path = public
as $$
declare
    v_alert public.fire_alerts;
begin
    update public.fire_alerts
    set status = 'sent',
        sent_at = now(),
        recipient = coalesce(p_recipient, recipient)
    where uuid = p_alert_id
    returning * into v_alert;

    return v_alert;
end;
$$;

grant execute on function public.send_fire_alert(uuid, text) to authenticated;


-- ============================================================================
-- POLICIES POUR LE RÔLE ADMINISTRATEUR ('admin')
-- ============================================================================

-- Fonction utilitaire pour vérifier si l'utilisateur connecté est administrateur
create or replace function public.is_admin()
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.user_profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- Accès complet de l'admin sur user_profiles
create policy "Admins can view and manage all profiles"
  on public.user_profiles
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- Accès complet de l'admin sur cooperatives
create policy "Admins can view and manage all cooperatives"
  on public.cooperatives
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- Accès complet de l'admin sur farmers
create policy "Admins can view and manage all farmers"
  on public.farmers
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- Accès complet de l'admin sur parcels
create policy "Admins can view and manage all parcels"
  on public.parcels
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- Accès complet de l'admin sur audits_bio
create policy "Admins can view and manage all bio audits"
  on public.audits_bio
  for all
  using (public.is_admin())
  with check (public.is_admin());

-- Accès complet de l'admin sur survey_forms
create policy "Admins can view and manage all survey forms"
  on public.survey_forms
  for all
  using (public.is_admin())
  with check (public.is_admin());


-- ============================================================================
-- POLITIQUES RLS POUR LE RÔLE AUDITEUR BIO (BIO_AUDITOR)
-- ============================================================================

create or replace function public.is_bio_auditor()
returns boolean
language sql
security definer
as $$
  select (
    coalesce((auth.jwt() -> 'user_metadata' ->> 'role'), '') = 'bio_auditor'
    or exists (
      select 1 from public.user_profiles
      where id = auth.uid() and role = 'bio_auditor'
    )
  );
$$;

-- 1. Lecture seule de toutes les coopératives
drop policy if exists "Bio auditors can view all cooperatives" on public.cooperatives;
create policy "Bio auditors can view all cooperatives"
  on public.cooperatives
  for select
  using (public.is_bio_auditor());

-- 2. Lecture seule de tous les agriculteurs
drop policy if exists "Bio auditors can view all farmers" on public.farmers;
create policy "Bio auditors can view all farmers"
  on public.farmers
  for select
  using (public.is_bio_auditor());

-- 3. Lecture seule de toutes les parcelles
drop policy if exists "Bio auditors can view all parcels" on public.parcels;
create policy "Bio auditors can view all parcels"
  on public.parcels
  for select
  using (public.is_bio_auditor());

-- 4. Accès aux audits biologiques (lecture et création/gestion)
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



DO $$
DECLARE
  new_admin_id uuid := gen_random_uuid();
  admin_email text := 'admin@smartsaha.bio';     
  admin_password text := 'MotDePasseAdmin123!';  
  admin_first_name text := 'Administrateur';
  admin_last_name text := 'SmartSahaBio';
  admin_phone text := '0340000000';
BEGIN
  -- 1. Insertion dans auth.users
  INSERT INTO auth.users (
    id,
    instance_id,
    email,
    encrypted_password,
    email_confirmed_at,
    raw_app_meta_data,
    raw_user_meta_data,
    aud,
    role,
    created_at,
    updated_at
  )
  VALUES (
    new_admin_id,
    '00000000-0000-0000-0000-000000000000'::uuid,
    admin_email,
    crypt(admin_password, gen_salt('bf')),
    now(),
    '{"provider": "email", "providers": ["email"]}'::jsonb,
    jsonb_build_object(
      'first_name', admin_first_name,
      'last_name', admin_last_name,
      'phone', admin_phone,
      'role', 'admin'
    ),
    'authenticated',
    'authenticated',
    now(),
    now()
  );

  -- 2. Insertion / Mise à jour dans public.user_profiles
  INSERT INTO public.user_profiles (
    id,
    first_name,
    last_name,
    phone,
    role,
    created_at,
    updated_at
  )
  VALUES (
    new_admin_id,
    admin_first_name,
    admin_last_name,
    admin_phone,
    'admin',
    now(),
    now()
  )
  ON CONFLICT (id) DO UPDATE
  SET 
    role = 'admin',
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    updated_at = now();

END $$;

ALTER TABLE public.farmers ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE public.fire_alerts DROP CONSTRAINT IF EXISTS fire_alerts_alert_type_check;
ALTER TABLE public.fire_alerts ADD CONSTRAINT fire_alerts_alert_type_check CHECK (alert_type IN ('email', 'notification', 'sms'));


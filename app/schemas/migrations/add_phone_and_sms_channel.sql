-- ============================================================================
-- MIGRATION: AJOUT DU TÉLÉPHONE AUX AGRICULTEURS ET CANAL SMS (sms.mg)
-- ============================================================================

-- 1. Ajout de la colonne téléphone à la table farmers
ALTER TABLE public.farmers
ADD COLUMN IF NOT EXISTS phone text;

-- Index optionnel pour recherche rapide par téléphone
CREATE INDEX IF NOT EXISTS farmers_phone_idx
ON public.farmers (phone);

-- 2. Mise à jour de la contrainte check sur fire_alerts pour autoriser le canal 'sms'
ALTER TABLE public.fire_alerts
DROP CONSTRAINT IF EXISTS fire_alerts_alert_type_check;

ALTER TABLE public.fire_alerts
ADD CONSTRAINT fire_alerts_alert_type_check
CHECK (alert_type IN ('email', 'notification', 'sms'));

-- 3. Mise à jour de la fonction RPC create_fire_alerts pour utiliser 'sms' par défaut ou selon le paramètre
CREATE OR REPLACE FUNCTION public.create_fire_alerts(
    p_radius_m numeric DEFAULT 5000,
    p_period_hours integer DEFAULT 168
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_count integer := 0;
BEGIN
    INSERT INTO public.fire_alerts (
        fire_id,
        parcel_id,
        distance_m,
        radius_m,
        alert_type,
        recipient,
        status
    )
    SELECT
        f.uuid,
        p.uuid,
        ROUND(
            ST_Distance(
                f.geom::geography,
                p.geom::geography
            )::numeric,
            2
        ),
        p_radius_m,
        'sms',
        fm.phone,
        'pending'
    FROM public.fire_detections f
    INNER JOIN public.parcels p
        ON ST_DWithin(
            f.geom::geography,
            p.geom::geography,
            p_radius_m
        )
    LEFT JOIN public.farmers fm
        ON fm.uuid = p.farmer_id
    WHERE
        p.owner = auth.uid()
        AND f.detected_at >= now() - make_interval(hours => p_period_hours)
    ON CONFLICT (
        fire_id,
        parcel_id,
        alert_type
    )
    DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

from datetime import datetime, timedelta, timezone
from flask import current_app


class ReportService:
    """
    Service de reporting statistique et analytique (Lot 4 - 4.6).
    Agrège les données multi-sources (coopératives, producteurs, parcelles, audits bio, alertes feux)
    avec filtrage multicritères et comparaison temporelle.
    """

    @staticmethod
    def _parse_iso(iso_str):
        if not iso_str:
            return None
        try:
            # Remplacement éventuel du format Z
            clean_str = str(iso_str).replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            try:
                parts = str(iso_str).split(".")[0].strip()
                return datetime.strptime(parts[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            except Exception:
                return None

    @staticmethod
    def _safe_query(query, default=None):
        try:
            res = query.execute()
            return res.data or []
        except Exception as e:
            print("⚠️ Erreur safe_query dashboard (résilience réseau) :", repr(e))
            return default if default is not None else []

    @staticmethod
    def get_dashboard_reports(
        user_id,
        is_admin=False,
        cooperative_id=None,
        period="30d",
        crop=None,
        status=None,
        date_start=None,
        date_end=None,
    ):
        supabase = current_app.supabase
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. Définition des bornes temporelles
        # -------------------------------------------------------------
        start_dt = None
        end_dt = now

        if date_start:
            try:
                start_dt = datetime.fromisoformat(date_start).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        if date_end:
            try:
                end_dt = datetime.fromisoformat(date_end).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        period_days = None
        if not start_dt:
            if period == "7d":
                period_days = 7
                start_dt = now - timedelta(days=7)
            elif period == "30d":
                period_days = 30
                start_dt = now - timedelta(days=30)
            elif period == "90d":
                period_days = 90
                start_dt = now - timedelta(days=90)
            elif period == "1y":
                period_days = 365
                start_dt = now - timedelta(days=365)
            else:
                # "all"
                start_dt = None

        # Période précédente pour calcul d'évolution (%)
        prior_start_dt = None
        prior_end_dt = None
        if start_dt and period_days:
            prior_end_dt = start_dt
            prior_start_dt = start_dt - timedelta(days=period_days)

        # -------------------------------------------------------------
        # 2. Récupération des données brutes avec résilience réseau
        # -------------------------------------------------------------
        # Coopératives :
        # L'administrateur a accès à toutes les coopératives.
        # Le gestionnaire filtre sur ses coopératives (owner = user_id).
        coop_query = supabase.table("cooperatives").select("*")
        if not is_admin and user_id:
            coop_query = coop_query.eq("owner", user_id)
        if cooperative_id:
            coop_query = coop_query.eq("uuid", cooperative_id)
        cooperatives = ReportService._safe_query(coop_query)
        coop_ids = {c["uuid"] for c in cooperatives}
        coop_map = {c["uuid"]: c for c in cooperatives}

        # Agriculteurs :
        # Si une coopérative est ciblée, filtrer par cooperative_id.
        # Si non-admin, filtrer par ses coopératives ou son identifiant.
        farmer_query = supabase.table("farmers").select("*")
        if cooperative_id:
            farmer_query = farmer_query.eq("cooperative_id", cooperative_id)
        elif not is_admin:
            if coop_ids:
                farmer_query = farmer_query.in_("cooperative_id", list(coop_ids))
            elif user_id:
                farmer_query = farmer_query.eq("owner", user_id)
        farmers = ReportService._safe_query(farmer_query)

        # Parcelles :
        parcel_query = supabase.table("parcels").select(
            "uuid, cooperative_id, farmer_id, area_ha, created_at, name"
        )
        if cooperative_id:
            parcel_query = parcel_query.eq("cooperative_id", cooperative_id)
        elif not is_admin:
            if coop_ids:
                parcel_query = parcel_query.in_("cooperative_id", list(coop_ids))
            elif user_id:
                parcel_query = parcel_query.eq("owner", user_id)
        parcels = ReportService._safe_query(parcel_query)
        parcel_ids = {p["uuid"] for p in parcels}

        # Audits Bio :
        audit_query = supabase.table("audits_bio").select("*")
        raw_audits = ReportService._safe_query(audit_query)
        if cooperative_id or not is_admin:
            audits = [a for a in raw_audits if a.get("parcel_id") in parcel_ids]
        else:
            audits = raw_audits

        # Alertes Feux :
        alerts_query = supabase.table("fire_alerts").select("*")
        raw_alerts = ReportService._safe_query(alerts_query)
        if cooperative_id or not is_admin:
            alerts = [a for a in raw_alerts if a.get("parcel_id") in parcel_ids]
        else:
            alerts = raw_alerts

        # Formulaires d'enquêtes :
        surveys_query = supabase.table("survey_forms").select("uuid, title, created_at")
        if not is_admin and user_id:
            surveys_query = surveys_query.eq("owner", user_id)
        surveys = ReportService._safe_query(surveys_query)
        responses_query = supabase.table("survey_responses").select("uuid, form_id, submitted_at")
        survey_responses = ReportService._safe_query(responses_query)

        # -------------------------------------------------------------
        # 3. Filtrages secondaires (Culture, Statut)
        # -------------------------------------------------------------
        if crop:
            crop_clean = crop.strip().lower()
            matching_coop_ids = {
                c["uuid"] for c in cooperatives
                if crop_clean in (c.get("main_crop") or "").lower()
                or crop_clean in (c.get("second_crop") or "").lower()
                or crop_clean in (c.get("third_crop") or "").lower()
            }
            cooperatives = [c for c in cooperatives if c.get("uuid") in matching_coop_ids]
            parcels = [p for p in parcels if p.get("cooperative_id") in matching_coop_ids]
            farmers = [f for f in farmers if f.get("cooperative_id") in matching_coop_ids]
            parcel_ids = {p["uuid"] for p in parcels}
            audits = [a for a in audits if a.get("parcel_id") in parcel_ids]
            alerts = [a for a in alerts if a.get("parcel_id") in parcel_ids]

        if status:
            st_clean = status.strip().lower()
            # Dans le dashboard, le filtre de statut est le statut de conversion bio (certified, in_conversion, not_started)
            if st_clean in ("certified", "in_conversion", "not_started"):
                audits = [
                    a for a in audits
                    if (a.get("conversion_status") or "not_started").lower() == st_clean
                ]
                matching_parcel_ids = {a.get("parcel_id") for a in audits if a.get("parcel_id")}
                if matching_parcel_ids:
                    parcels = [p for p in parcels if p.get("uuid") in matching_parcel_ids]
                    parcel_ids = {p["uuid"] for p in parcels}
                    farmer_ids_in_parcels = {p.get("farmer_id") for p in parcels if p.get("farmer_id")}
                    farmers = [f for f in farmers if f.get("uuid") in farmer_ids_in_parcels]
                    coop_ids_in_parcels = {p.get("cooperative_id") for p in parcels if p.get("cooperative_id")}
                    cooperatives = [c for c in cooperatives if c.get("uuid") in coop_ids_in_parcels]
                else:
                    parcels = []
                    parcel_ids = set()
                    farmers = []
            elif st_clean in ("active", "not_active", "inactive"):
                farmers = [f for f in farmers if (f.get("status") or "").lower() == st_clean]

        # -------------------------------------------------------------
        # 4. Calculs des KPI & Totaux
        # -------------------------------------------------------------
        total_coops = len(cooperatives)
        active_coops = len([c for c in cooperatives if c.get("status") == "active"])

        total_farmers = len(farmers)
        active_farmers = len([f for f in farmers if f.get("status") == "active"])
        female_farmers = len([f for f in farmers if (f.get("gender") or "").lower() == "female"])
        male_farmers = len([f for f in farmers if (f.get("gender") or "").lower() == "male"])
        handicap_farmers = len([f for f in farmers if f.get("handicap") is True])

        total_parcels = len(parcels)
        total_area_ha = sum(float(p.get("area_ha") or 0) for p in parcels)
        avg_area_ha = (total_area_ha / total_parcels) if total_parcels > 0 else 0

        # Audits Bio
        total_audits = len(audits)
        compliant_audits = len([a for a in audits if a.get("overall_status") == "compliant"])
        reservations_audits = len([a for a in audits if a.get("overall_status") == "compliant_with_reservations"])
        non_compliant_audits = len([a for a in audits if a.get("overall_status") == "non_compliant"])

        compliance_rate = round(
            ((compliant_audits + (0.5 * reservations_audits)) / total_audits * 100), 1
        ) if total_audits > 0 else 0

        certified_count = len([a for a in audits if a.get("conversion_status") == "certified"])
        in_conversion_count = len([a for a in audits if a.get("conversion_status") == "in_conversion"])
        not_started_count = len([a for a in audits if a.get("conversion_status") in ("not_started", None)])

        # Non-conformités et gravité
        severity_counts = {
            "critical": len([a for a in audits if a.get("non_conformity_severity") == "critical"]),
            "major": len([a for a in audits if a.get("non_conformity_severity") == "major"]),
            "minor": len([a for a in audits if a.get("non_conformity_severity") == "minor"]),
            "none": len([a for a in audits if a.get("non_conformity_severity") in ("none", None)]),
        }

        # Échéances de renouvellement / actions correctives
        upcoming_deadlines = []
        for a in audits:
            dl = a.get("corrective_action_deadline")
            if dl:
                upcoming_deadlines.append({
                    "audit_uuid": a.get("uuid"),
                    "parcel_id": a.get("parcel_id"),
                    "deadline": dl,
                    "severity": a.get("non_conformity_severity"),
                    "corrective_action_plan": a.get("corrective_action_plan"),
                    "overall_status": a.get("overall_status")
                })
        upcoming_deadlines = sorted(upcoming_deadlines, key=lambda x: x["deadline"])[:5]

        # Alertes Incendie
        total_fire_alerts = len(alerts)
        pending_fire_alerts = len([a for a in alerts if a.get("status") == "pending"])
        sent_fire_alerts = len([a for a in alerts if a.get("status") == "sent"])
        threatened_parcels_set = {a.get("parcel_id") for a in alerts if a.get("status") == "pending"}
        threatened_parcels_count = len(threatened_parcels_set)

        # -------------------------------------------------------------
        # 5. Répartitions et Distributions
        # -------------------------------------------------------------
        # Par culture principale
        crops_distribution = {}
        for c in cooperatives:
            crop_name = c.get("main_crop") or "Non spécifié"
            c_id = c.get("uuid")
            c_parcels = [p for p in parcels if p.get("cooperative_id") == c_id]
            c_area = sum(float(p.get("area_ha") or 0) for p in c_parcels)

            if crop_name not in crops_distribution:
                crops_distribution[crop_name] = {
                    "crop": crop_name,
                    "cooperatives_count": 0,
                    "parcels_count": 0,
                    "total_area_ha": 0.0,
                }
            crops_distribution[crop_name]["cooperatives_count"] += 1
            crops_distribution[crop_name]["parcels_count"] += len(c_parcels)
            crops_distribution[crop_name]["total_area_ha"] += c_area

        crops_list = sorted(
            crops_distribution.values(),
            key=lambda x: x["total_area_ha"],
            reverse=True
        )

        # Par coopérative
        cooperatives_summary = []
        for c in cooperatives:
            cid = c.get("uuid")
            c_farmers = [f for f in farmers if f.get("cooperative_id") == cid]
            c_parcels = [p for p in parcels if p.get("cooperative_id") == cid]
            c_area = sum(float(p.get("area_ha") or 0) for p in c_parcels)
            c_audits = [a for a in audits if a.get("parcel_id") in {p["uuid"] for p in c_parcels}]
            c_comp = len([a for a in c_audits if a.get("overall_status") == "compliant"])
            c_rate = round((c_comp / len(c_audits) * 100), 1) if c_audits else 0

            cooperatives_summary.append({
                "uuid": cid,
                "name": c.get("name"),
                "president_name": c.get("president_name"),
                "main_crop": c.get("main_crop"),
                "legal_status": c.get("legal_status"),
                "farmers_count": len(c_farmers),
                "parcels_count": len(c_parcels),
                "total_area_ha": round(c_area, 2),
                "audits_count": len(c_audits),
                "compliance_rate": c_rate,
            })

        # -------------------------------------------------------------
        # 6. Suivi de l'évolution dans le temps (comparaison temporelle)
        # -------------------------------------------------------------
        growth = {
            "parcels": 0.0,
            "area": 0.0,
            "farmers": 0.0,
            "audits": 0.0,
        }

        if start_dt and prior_start_dt and prior_end_dt:
            # Éléments créés dans la période courante
            cur_parcels = [p for p in parcels if ReportService._in_interval(p.get("created_at"), start_dt, end_dt)]
            cur_farmers = [f for f in farmers if ReportService._in_interval(f.get("created_at"), start_dt, end_dt)]
            cur_audits = [a for a in audits if ReportService._in_interval(a.get("created_at"), start_dt, end_dt)]
            cur_area = sum(float(p.get("area_ha") or 0) for p in cur_parcels)

            # Éléments créés dans la période précédente
            prev_parcels = [p for p in parcels if ReportService._in_interval(p.get("created_at"), prior_start_dt, prior_end_dt)]
            prev_farmers = [f for f in farmers if ReportService._in_interval(f.get("created_at"), prior_start_dt, prior_end_dt)]
            prev_audits = [a for a in audits if ReportService._in_interval(a.get("created_at"), prior_start_dt, prior_end_dt)]
            prev_area = sum(float(p.get("area_ha") or 0) for p in prev_parcels)

            growth["parcels"] = ReportService._calc_growth(len(cur_parcels), len(prev_parcels))
            growth["area"] = ReportService._calc_growth(cur_area, prev_area)
            growth["farmers"] = ReportService._calc_growth(len(cur_farmers), len(prev_farmers))
            growth["audits"] = ReportService._calc_growth(len(cur_audits), len(prev_audits))

        return {
            "filters": {
                "cooperative_id": cooperative_id,
                "period": period,
                "crop": crop,
                "status": status,
                "date_start": start_dt.isoformat() if start_dt else None,
                "date_end": end_dt.isoformat() if end_dt else None,
            },
            "summary": {
                "cooperatives": {
                    "total": total_coops,
                    "active": active_coops,
                },
                "farmers": {
                    "total": total_farmers,
                    "active": active_farmers,
                    "female": female_farmers,
                    "male": male_farmers,
                    "female_percentage": round((female_farmers / total_farmers * 100), 1) if total_farmers > 0 else 0,
                    "handicap_count": handicap_farmers,
                },
                "parcels": {
                    "total": total_parcels,
                    "total_area_ha": round(total_area_ha, 2),
                    "avg_area_ha": round(avg_area_ha, 2),
                },
                "bio_audits": {
                    "total": total_audits,
                    "compliance_rate": compliance_rate,
                    "compliant": compliant_audits,
                    "compliant_with_reservations": reservations_audits,
                    "non_compliant": non_compliant_audits,
                    "certified": certified_count,
                    "in_conversion": in_conversion_count,
                    "not_started": not_started_count,
                    "severities": severity_counts,
                },
                "fire_alerts": {
                    "total": total_fire_alerts,
                    "pending": pending_fire_alerts,
                    "sent": sent_fire_alerts,
                    "threatened_parcels": threatened_parcels_count,
                },
                "surveys": {
                    "total_forms": len(surveys),
                    "total_responses": len(survey_responses),
                },
            },
            "growth": growth,
            "crops_distribution": crops_list,
            "cooperatives_summary": cooperatives_summary,
            "upcoming_deadlines": upcoming_deadlines,
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _in_interval(date_str, start_dt, end_dt):
        if not date_str:
            return False
        dt = ReportService._parse_iso(date_str)
        if not dt:
            return False
        return start_dt <= dt <= end_dt

    @staticmethod
    def _calc_growth(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

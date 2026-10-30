import io
import csv
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app, Response

from app.services.report_service import ReportService
from app.utils.auth import get_current_user_and_role

reports_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/api/reports"
)


@reports_bp.get("/dashboard")
def get_dashboard_reports():
    user, role, _ = get_current_user_and_role()
    if not user:
        return jsonify({"error": "Utilisateur non authentifié"}), 401

    try:
        cooperative_id = request.args.get("cooperative_id")
        period = request.args.get("period", "30d")
        crop = request.args.get("crop")
        status = request.args.get("status")
        date_start = request.args.get("date_start")
        date_end = request.args.get("date_end")

        is_admin = role in ("admin", "bio_auditor")

        data = ReportService.get_dashboard_reports(
            user_id=user.id,
            is_admin=is_admin,
            cooperative_id=cooperative_id,
            period=period,
            crop=crop,
            status=status,
            date_start=date_start,
            date_end=date_end,
        )

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        current_app.logger.error("Erreur get_dashboard_reports: %s", repr(e))
        return jsonify({
            "success": False,
            "error": "Liaison avec la base de données instable. Veuillez réactualiser ou réessayer dans un instant."
        }), 500


@reports_bp.get("/export/csv")
def export_reports_csv():
    user, role, _ = get_current_user_and_role()
    if not user:
        return jsonify({"error": "Utilisateur non authentifié"}), 401

    try:
        cooperative_id = request.args.get("cooperative_id")
        period = request.args.get("period", "30d")
        crop = request.args.get("crop")
        status = request.args.get("status")

        is_admin = role in ("admin", "bio_auditor")

        data = ReportService.get_dashboard_reports(
            user_id=user.id,
            is_admin=is_admin,
            cooperative_id=cooperative_id,
            period=period,
            crop=crop,
            status=status,
        )

        # Génération du flux CSV compatible Excel
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        # 1. En-tête du rapport
        writer.writerow(["SMARTSAHA - RAPPORT D'ACTIVITE ET DE CONFORMITE BIOLOGIQUE"])
        writer.writerow(["Date de generation", datetime.now().strftime("%d/%m/%Y %H:%M")])
        writer.writerow(["Periode d'analyse", period])
        writer.writerow([])

        # 2. Synthèse globale
        writer.writerow(["1. SYNTHESE GENERALE"])
        writer.writerow(["Indicateur", "Valeur"])
        s = data["summary"]
        writer.writerow(["Coopératives totales", s["cooperatives"]["total"]])
        writer.writerow(["Coopératives actives", s["cooperatives"]["active"]])
        writer.writerow(["Producteurs totaux", s["farmers"]["total"]])
        writer.writerow(["Producteurs actifs", s["farmers"]["active"]])
        writer.writerow(["Femmes (%)", f"{s['farmers']['female_percentage']}%"])
        writer.writerow(["Parcelles totales", s["parcels"]["total"]])
        writer.writerow(["Superficie totale (ha)", s["parcels"]["total_area_ha"]])
        writer.writerow(["Superficie moyenne (ha)", s["parcels"]["avg_area_ha"]])
        writer.writerow(["Audits bio réalisés", s["bio_audits"]["total"]])
        writer.writerow(["Taux de conformité bio (%)", f"{s['bio_audits']['compliance_rate']}%"])
        writer.writerow(["Audits conformes", s["bio_audits"]["compliant"]])
        writer.writerow(["Audits avec réserves", s["bio_audits"]["compliant_with_reservations"]])
        writer.writerow(["Audits non conformes", s["bio_audits"]["non_compliant"]])
        writer.writerow(["Alertes feux totales", s["fire_alerts"]["total"]])
        writer.writerow(["Parcelles menacées par feux", s["fire_alerts"]["threatened_parcels"]])
        writer.writerow([])

        # 3. Répartition par culture
        writer.writerow(["2. REPARTITION PAR CULTURE"])
        writer.writerow(["Culture", "Nombre de coopératives", "Nombre de parcelles", "Superficie totale (ha)"])
        for c in data.get("crops_distribution", []):
            writer.writerow([c["crop"], c["cooperatives_count"], c["parcels_count"], c["total_area_ha"]])
        writer.writerow([])

        # 4. Détail par coopérative
        writer.writerow(["3. DETAIL PAR COOPERATIVE"])
        writer.writerow(["Nom", "President", "Culture principale", "Statut juridique", "Producteurs", "Parcelles", "Superficie (ha)", "Audits bio", "Taux conformite (%)"])
        for coop in data.get("cooperatives_summary", []):
            writer.writerow([
                coop["name"],
                coop["president_name"],
                coop["main_crop"],
                coop["legal_status"],
                coop["farmers_count"],
                coop["parcels_count"],
                coop["total_area_ha"],
                coop["audits_count"],
                f"{coop['compliance_rate']}%"
            ])

        csv_text = output.getvalue()
        # Encodage BOM UTF-8 pour ouverture directe dans Excel
        response_bytes = "\ufeff" + csv_text

        filename = f"rapport_smartsaha_{datetime.now().strftime('%Y%m%d')}_{period}.csv"
        return Response(
            response_bytes,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        current_app.logger.error("Erreur export_reports_csv: %s", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

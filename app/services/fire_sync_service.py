import os
import threading
import time
from datetime import datetime, timezone
from flask import current_app

from app.services.firms_service import FirmsService
from app.services.fire_service import FireService
from app.repositories.fire_alert_repository import FireAlertRepository


class FireSyncService:
    """
    Service de synchronisation en arrière-plan des détections NASA FIRMS
    vers la base de données PostGIS (table fire_detections).
    """

    _last_sync_time = None
    _last_sync_count = 0
    _is_syncing = False
    _tracked_owners = {}

    @classmethod
    def has_synced_owner(cls, owner_id):
        return owner_id in cls._tracked_owners

    @classmethod
    def get_sync_status(cls):
        return {
            "last_sync_at": cls._last_sync_time.isoformat() if cls._last_sync_time else None,
            "last_count": cls._last_sync_count,
            "is_syncing": cls._is_syncing,
            "interval_minutes": 30,
            "tracked_cooperatives": len(cls._tracked_owners),
        }

    @classmethod
    def sync_for_owner(cls, owner_id, days=2, radius_km=10):
        """
        Synchronise les données NASA FIRMS spécifiquement pour l'emprise
        des parcelles appartenant à un utilisateur (coopérative).
        """
        if cls._is_syncing:
            print("⏳ Synchronisation NASA déjà en cours, attente...")
            return {"status": "in_progress", "saved": 0}

        try:
            cls._is_syncing = True
            parcels = FireService.get_parcels(owner_id)
            if not parcels:
                return {"status": "no_parcels", "saved": 0}

            # Emprise globale des parcelles avec marge de sécurité
            min_x = min(item["geometry"].bounds[0] for item in parcels)
            min_y = min(item["geometry"].bounds[1] for item in parcels)
            max_x = max(item["geometry"].bounds[2] for item in parcels)
            max_y = max(item["geometry"].bounds[3] for item in parcels)

            # Marge de sécurité en degrés (rayon demandé + 15 km de marge)
            margin_deg = (radius_km + 15) / 111.0

            west = max(min_x - margin_deg, 43.0)
            south = max(min_y - margin_deg, -26.0)
            east = min(max_x + margin_deg, 51.0)
            north = min(max_y + margin_deg, -11.5)

            # Enregistrement de l'emprise pour les cycles périodiques de 30 min
            cls._tracked_owners[owner_id] = {
                "bbox": (west, south, east, north),
                "radius_km": radius_km,
                "last_sync": datetime.now(timezone.utc),
            }

            print(f"🛰️ Synchronisation NASA ciblée pour l'utilisateur : emprise [{west:.2f}, {south:.2f}, {east:.2f}, {north:.2f}] sur {days} jours")
            fires = FirmsService.get_fires(
                west=round(west, 3),
                south=round(south, 3),
                east=round(east, 3),
                north=round(north, 3),
                days=days
            )

            saved_count = 0
            for f in fires:
                try:
                    FireService.save_fire(f)
                    saved_count += 1
                except Exception as err:
                    print("⚠️ Erreur insertion feu sync :", err)

            cls._last_sync_time = datetime.now(timezone.utc)
            cls._last_sync_count = saved_count

            # Déclenchement automatique des alertes en base
            if saved_count > 0:
                try:
                    FireAlertRepository.create_alerts(
                        radius_m=radius_km * 1000,
                        period_hours=days * 24
                    )
                except Exception as alert_err:
                    print("⚠️ Erreur génération alertes après sync :", alert_err)

            print(f"✅ Synchronisation NASA terminée : {saved_count} feux enregistrés dans PostGIS.")
            return {
                "status": "success",
                "fetched": len(fires),
                "saved": saved_count,
                "synced_at": cls._last_sync_time.isoformat()
            }
        except Exception as e:
            print("❌ Erreur pendant sync_for_owner :", e)
            return {"status": "error", "error": str(e), "saved": 0}
        finally:
            cls._is_syncing = False

    @classmethod
    def sync_registered_areas(cls, days=2):
        """
        Cycle de synchronisation automatique exécuté toutes les 30 minutes.
        Interroge NASA FIRMS pour toutes les coopératives et parcelles enregistrées
        puis insère les nouveaux foyers dans PostGIS.
        """
        if cls._is_syncing:
            return {"status": "in_progress", "saved": 0}

        try:
            cls._is_syncing = True
            print(f"⏰ [FIRE-SYNC] Cycle automatique 30 min démarré à {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}...")

            total_saved = 0

            if cls._tracked_owners:
                for owner_id, data in list(cls._tracked_owners.items()):
                    west, south, east, north = data["bbox"]
                    r_km = data.get("radius_km", 10)
                    try:
                        print(f"🛰️ Synchronisation zone coopérative [{west:.2f}, {south:.2f}, {east:.2f}, {north:.2f}] sur {days} jours...")
                        fires = FirmsService.get_fires(
                            west=round(west, 3),
                            south=round(south, 3),
                            east=round(east, 3),
                            north=round(north, 3),
                            days=days
                        )
                        for f in fires:
                            try:
                                FireService.save_fire(f)
                                total_saved += 1
                            except Exception:
                                pass

                        # Mise à jour des alertes pour cette zone
                        try:
                            FireAlertRepository.create_alerts(
                                radius_m=r_km * 1000,
                                period_hours=days * 24
                            )
                        except Exception:
                            pass
                    except Exception as err:
                        print(f"⚠️ Erreur sync zone {owner_id} :", err)
            else:
                # Zone par défaut (centre de Madagascar) si aucune coopérative n'a encore ouvert la page
                print("ℹ️ Aucune zone coopérative en mémoire, interrogation zone agricole principale...")
                try:
                    fires = FirmsService.get_fires(
                        west=46.5,
                        south=-20.5,
                        east=48.5,
                        north=-18.0,
                        days=1
                    )
                    for f in fires:
                        try:
                            FireService.save_fire(f)
                            total_saved += 1
                        except Exception:
                            pass
                except Exception as err:
                    print("⚠️ Erreur sync zone par défaut :", err)

            cls._last_sync_time = datetime.now(timezone.utc)
            cls._last_sync_count = total_saved

            print(f"🎉 [FIRE-SYNC] Synchronisation automatique réussie : {total_saved} feux traités à {cls._last_sync_time.strftime('%H:%M:%S UTC')}.")
            return {
                "status": "success",
                "saved": total_saved,
                "synced_at": cls._last_sync_time.isoformat()
            }
        except Exception as e:
            print("❌ [FIRE-SYNC] Erreur synchronisation cycle 30 min :", e)
            return {"status": "error", "error": str(e), "saved": 0}
        finally:
            cls._is_syncing = False


class FireSyncScheduler:
    """
    Planificateur d'arrière-plan exécuté dans le processus Flask.
    Exécute automatiquement la synchronisation NASA toutes les 30 minutes.
    """

    _thread = None
    _stop_event = threading.Event()
    _started = False

    @classmethod
    def start(cls, app, interval_seconds=1800):  # 1800 secondes = 30 minutes
        if cls._started:
            return

        # Évite le double démarrage lors du reload de Flask en mode debug
        is_reloader_parent = app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
        if is_reloader_parent:
            return

        cls._started = True
        cls._stop_event.clear()

        def run_loop():
            print(f"🚀 Planificateur automatique NASA FIRMS démarré (Fréquence : toutes les {interval_seconds // 60} minutes).")
            # Première synchronisation différée de 5 secondes au démarrage
            time.sleep(5)

            with app.app_context():
                try:
                    FireSyncService.sync_registered_areas(days=2)
                except Exception as e:
                    print("⚠️ Erreur lors de la synchronisation au démarrage :", e)

            while not cls._stop_event.is_set():
                # Attente interruptible de 30 minutes (1800s)
                if cls._stop_event.wait(timeout=interval_seconds):
                    break

                with app.app_context():
                    try:
                        FireSyncService.sync_registered_areas(days=2)
                    except Exception as e:
                        print("⚠️ Erreur lors de la synchronisation périodique de 30 min :", e)

        cls._thread = threading.Thread(
            target=run_loop,
            daemon=True,
            name="FireSyncSchedulerThread"
        )
        cls._thread.start()

    @classmethod
    def stop(cls):
        if cls._started:
            cls._stop_event.set()
            cls._started = False
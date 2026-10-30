import sys
from app import create_app

def setup_admin(email="admin@gmail.com", password="admin@gmail.com"):
    app = create_app()

    with app.app_context():
        print(f"\n==================================================")
        print(f" Configuration du compte Administrateur : {email}")
        print(f"==================================================")

        supabase = app.supabase

        # 1. Tenter l'inscription propre via l'API Supabase
        try:
            res = supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "first_name": "Administrateur",
                        "last_name": "SmartSahaBio",
                        "phone": "0340000000",
                        "role": "admin"
                    }
                }
            })

            user = res.user
            if user:
                print("✅ Compte créé dans Supabase Auth !")
                # Forcer le profil dans public.user_profiles
                supabase.table("user_profiles").upsert({
                    "id": user.id,
                    "first_name": "Administrateur",
                    "last_name": "SmartSahaBio",
                    "phone": "0340000000",
                    "role": "admin"
                }).execute()
                print("✅ Rôle 'admin' configuré dans user_profiles !")
                print("\n🎉 Terminé ! Vous pouvez maintenant vous connecter.")
                return

        except Exception as e:
            err = str(e)
            if "already registered" in err or "User already exists" in err:
                print("ℹ️ Le compte existe déjà dans Supabase Auth.")
                print("Tentative de connexion pour vérifier le mot de passe...")
                try:
                    login_res = supabase.auth.sign_in_with_password({
                        "email": email,
                        "password": password
                    })
                    if login_res.user:
                        print("✅ Mot de passe correct !")
                        supabase.table("user_profiles").upsert({
                            "id": login_res.user.id,
                            "first_name": "Administrateur",
                            "last_name": "SmartSahaBio",
                            "phone": "0340000000",
                            "role": "admin"
                        }).execute()
                        print("✅ Rôle 'admin' mis à jour avec succès dans user_profiles !")
                        print("\n🎉 Terminé ! Vous pouvez vous connecter.")
                        return
                except Exception as login_err:
                    print(f"❌ Échec de connexion : {login_err}")
                    print("\n⚠️ Solution :")
                    print("Le compte existant a été créé via SQL avec un hash non reconnu par Supabase.")
                    print("👉 Dans le dashboard Supabase : allez dans Authentication > Users, supprimez 'admin@gmail.com', puis relancez ce script.")
            else:
                print(f"❌ Erreur lors de la création : {err}")

if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "admin@gmail.com"
    setup_admin(email, password)

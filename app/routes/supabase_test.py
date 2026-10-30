from flask import Blueprint, current_app

supabase_test_bp = Blueprint(
    "supabase_test",
    __name__,
    url_prefix="/api/supabase"
)


@supabase_test_bp.get("/test")
def test_supabase():
    try:
        response = current_app.supabase.table(
            "cooperatives"
        ).select("*").limit(5).execute()

        return {
            "success": True,
            "data": response.data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }, 500
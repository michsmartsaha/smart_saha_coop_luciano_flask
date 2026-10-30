from flask import Blueprint


health_bp = Blueprint(
    "health",
    __name__,
    url_prefix="/api/health"
)


@health_bp.get("/")
def health_check():
    return {
        "success": True,
        "message": "Smart Saha API is running",
        "status": "healthy"
    }
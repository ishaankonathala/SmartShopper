"""Health-check business logic kept outside route handlers."""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.health import HealthResponse

DatabaseStatus = Literal["connected", "unavailable"]


def check_database(db: Session) -> DatabaseStatus:
    """Run a lightweight query to verify database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return "connected"
    except Exception:
        return "unavailable"


def build_health_response(db: Session, settings: Settings) -> HealthResponse:
    """Compose the health response from settings and a DB probe."""
    database_status = check_database(db)
    status: Literal["ok", "degraded"] = (
        "ok" if database_status == "connected" else "degraded"
    )
    return HealthResponse(
        status=status,
        app=settings.app_name,
        environment=settings.app_env,
        database=database_status,
        version="0.1.0",
    )

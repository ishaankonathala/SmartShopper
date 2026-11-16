"""Schemas for health-check responses."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Public health payload returned by GET /api/health."""

    status: Literal["ok", "degraded"] = Field(description="Overall service status")
    app: str = Field(description="Application name")
    environment: str = Field(description="Runtime environment label")
    database: Literal["connected", "unavailable"] = Field(
        description="Result of a live database connectivity check"
    )
    version: str = Field(default="0.1.0", description="API version")

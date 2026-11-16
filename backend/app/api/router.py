"""Aggregate API routers under a shared prefix."""

from fastapi import APIRouter

from app.api import health, history, products, profiles, recommendations

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(profiles.router)
api_router.include_router(products.router)
api_router.include_router(history.router)
api_router.include_router(recommendations.router)

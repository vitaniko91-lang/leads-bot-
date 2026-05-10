"""Route registration for the dashboard API.

`register_all(app)` is called from create_app() after the FastAPI instance
exists, to avoid circular imports.
"""
from fastapi import FastAPI


def register_all(app: FastAPI) -> None:
    from leads_bot.dashboard.routes import (
        discovery,
        leads,
        profile,
        settings as settings_route,
        sources,
        stats,
        stream,
        templates,
    )
    app.include_router(stats.router)
    app.include_router(leads.router)
    app.include_router(sources.router)
    app.include_router(profile.router)
    app.include_router(settings_route.router)
    app.include_router(stream.router)
    app.include_router(templates.router)
    app.include_router(discovery.router)

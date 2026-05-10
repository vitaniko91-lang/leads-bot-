"""Run the dashboard FastAPI app via uvicorn.

Usage:
    python -m leads_bot.dashboard.main
"""
import uvicorn

from leads_bot.config import get_settings


def main() -> None:
    get_settings()
    uvicorn.run(
        "leads_bot.dashboard.app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()

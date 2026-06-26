"""HTTP deprecation headers for legacy queue endpoints."""
from fastapi import Response


def mark_deprecated(response: Response, successor_path: str, *, sunset: str = "2026-12-31") -> None:
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = sunset
    response.headers["Link"] = f'<{successor_path}>; rel="successor-version"'
    response.headers["X-API-Warn"] = (
        f"This endpoint is deprecated. Use {successor_path} instead."
    )

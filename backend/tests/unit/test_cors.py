"""CORS safety: explicit origins, no wildcard while credentials enabled."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_cors_has_no_wildcard_with_credentials():
    from app.main import create_app

    app = create_app()
    mw = [m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"]
    assert mw, "CORSMiddleware must be configured"
    opts = mw[0].kwargs
    assert "*" not in opts.get("allow_origins", []), "wildcard origin forbidden with credentials"
    assert opts.get("allow_credentials") is True
    assert len(opts.get("allow_origins", [])) > 0, "explicit dev origins must remain"


def test_cors_origins_come_from_env():
    from app.core.config import get_settings

    origins = get_settings().cors_origins
    assert all(o.startswith("http") for o in origins)
    assert "*" not in origins

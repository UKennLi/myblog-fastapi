from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import ROOT, Settings
from app.core.exceptions import BindingError, CompatibilityError
from app.core.middleware import HeadMiddleware, SecurityMiddleware, error_response
from app.core.security import SessionStore
from app.core.static_cache import StaticCacheMiddleware
from app.db.session import make_database
from app.repositories.blog import BlogRepository
from app.services.options import OptionCache
from app.services.views import make_templates
from app.routers import admin, auth, public


def create_app(settings=None):
    settings = settings or Settings()
    engine, factory = make_database(settings)

    @asynccontextmanager
    async def lifespan(app):
        from starlette.concurrency import run_in_threadpool
        def load():
            with factory() as session:
                app.state.options.reload(BlogRepository(session, settings))
        await run_in_threadpool(load)
        # Original Spring in-memory sessions expire on application restart.
        await run_in_threadpool(app.state.sessions.clear)
        yield
        engine.dispose()

    app = FastAPI(title="MyBlog-butterfly", docs_url=None, redoc_url=None, openapi_url=None,
                  redirect_slashes=False, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine, app.state.session_factory = engine, factory
    app.state.sessions = SessionStore(settings)
    app.state.options = OptionCache()
    app.state.templates = make_templates()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(HeadMiddleware)
    app.add_middleware(StaticCacheMiddleware)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(BindingError)
    async def binding_error(request, error):
        return error_response(request, 400)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, error):
        response = error_response(request, error.status_code)
        if error.headers:
            response.headers.update(error.headers)
        return response

    @app.exception_handler(CompatibilityError)
    async def compatibility_error(request, error):
        return error_response(request, 500)

    # Static and reserved framework paths precede the one-segment PAGE catch-all.
    for name in ("butterfly", "plugins", "webjars"):
        app.mount("/" + name, StaticFiles(directory=ROOT / "static" / name), name=name)

    @app.get("/upload/{filename:path}")
    def uploaded(filename: str):
        path = (settings.uploads_dir / filename).resolve()
        if not path.is_relative_to(settings.uploads_dir.resolve()) or not path.is_file():
            raise HTTPException(404)
        headers = {}
        # Historical files remain available without allowing active HTML/SVG execution.
        if path.suffix.lower() in (".html", ".htm", ".svg", ".xml", ".js", ".mjs"):
            headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
            headers["Content-Disposition"] = "attachment"
        return FileResponse(path, headers=headers)

    @app.get("/default-ui.css")
    def default_css():
        return FileResponse(ROOT / "static/default-ui.css", media_type="text/css")

    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(public.router)
    return app


app = create_app()

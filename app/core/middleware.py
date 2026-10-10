import logging
from datetime import datetime, timezone
from http import HTTPStatus
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool
from app.core.security import valid_csrf

logger = logging.getLogger("myblog")


class HeadMiddleware:
    """Serve GET metadata for HEAD while suppressing the response body."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "HEAD":
            return await self.app(scope, receive, send)
        scope = dict(scope, method="GET")

        async def send_head(message):
            if message["type"] == "http.response.body":
                message = dict(message, body=b"")
            await send(message)

        await self.app(scope, receive, send_head)


def error_response(request, status):
    title = HTTPStatus(status).phrase
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse('<html><body><h1>Whitelabel Error Page</h1><p>This application has no explicit mapping for /error, so you are seeing this as a fallback.</p>'
                            + f"<div id='created'>{datetime.now(timezone.utc).strftime('%a %b %d %H:%M:%S UTC %Y')}</div>"
                            + f'<div>There was an unexpected error (type={title}, status={status}).</div></body></html>', status_code=status)
    return JSONResponse(dict(timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                             status=status, error=title, path=request.url.path), status_code=status)


def public_path(path):
    # Explicitly protect /admin as well as descendants (authorized security repair).
    if path == "/admin" or path.startswith("/admin/"):
        return False
    if path in ("/", "/login", "/logout", "/search", "/links", "/favicon.ico"):
        return True
    if path.startswith(("/post/", "/category/", "/tag/", "/archive/", "/comment/", "/butterfly/", "/plugins/", "/upload/")):
        return True
    return path.count("/") == 1


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        app = request.app
        settings, store = app.state.settings, app.state.sessions
        token = request.cookies.get("JSESSIONID")
        session = await run_in_threadpool(store.get, token)
        request.state.delete_cookie = False
        if session is None:
            token, session = await run_in_threadpool(store.create)
            request.state.new_cookie = token
        request.state.session = session
        unsafe = request.method not in ("GET", "HEAD", "OPTIONS", "TRACE")
        exempt = request.url.path.startswith(("/comment/", "/admin/api/"))
        response = None
        if request.headers.get("content-type", "").startswith("multipart/"):
            try:
                excessive = int(request.headers.get("content-length", "0")) > settings.max_upload_bytes
            except ValueError:
                excessive = True
            if excessive:
                response = error_response(request, 413)
        if response is None and unsafe and not exempt:
            await request.body()  # Preserve the body for the downstream Request.
            try:
                form = await request.form(max_part_size=settings.max_upload_bytes)
                value = request.headers.get("x-csrf-token") or form.get("_csrf")
                # Spring allows a raw token only in the header; form values use XOR masking.
                valid = valid_csrf(value, session["csrf"])
                if request.headers.get("x-csrf-token"):
                    import hmac
                    valid = valid or hmac.compare_digest(str(value), session["csrf"])
            except Exception:
                valid = False
            if not valid:
                response = error_response(request, 403)
        if response is None and not public_path(request.url.path) and session["user_id"] is None:
            response = RedirectResponse(str(request.base_url).rstrip("/") + "/login", status_code=302)
        if response is None:
            try:
                response = await call_next(request)
            except Exception:
                # Do not expose credentials, SQL parameters, or exception messages to clients.
                logger.exception("Request failed for %s %s", request.method, request.url.path)
                response = error_response(request, 500)
        if response.status_code == 302 and response.headers.get("location", "").startswith("/"):
            response.headers["location"] = str(request.base_url).rstrip("/") + response.headers["location"]
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
                                 "X-XSS-Protection": "0", "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
                                 "Pragma": "no-cache", "Expires": "0"})
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000 ; includeSubDomains"
        if request.state.delete_cookie:
            response.delete_cookie("JSESSIONID", path="/", httponly=True, secure=settings.cookie_secure, samesite=None)
        elif getattr(request.state, "new_cookie", None):
            response.set_cookie("JSESSIONID", request.state.new_cookie, path="/", httponly=True,
                                secure=settings.cookie_secure, samesite=None)
        return response

from starlette.datastructures import MutableHeaders


class StaticCacheMiddleware:
    """Short browser-only cache: never publicly cache responses with sessions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        static = path.startswith(("/butterfly/", "/plugins/", "/webjars/", "/upload/")) or path == "/default-ui.css"

        async def cached_send(message):
            if scope["type"] == "http" and static and scope.get("method") in ("GET", "HEAD") and message["type"] == "http.response.start" and message["status"] in (200, 304):
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "private, max-age=300, must-revalidate"
                if "pragma" in headers:
                    del headers["pragma"]
                if "expires" in headers:
                    del headers["expires"]
            await send(message)

        await self.app(scope, receive, cached_send)

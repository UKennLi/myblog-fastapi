from fastapi import Request
from app.repositories.blog import BlogRepository


def repository(request: Request):
    with request.app.state.session_factory() as session:
        yield BlogRepository(session, request.app.state.settings)

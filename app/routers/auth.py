from typing import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from app.dependencies.database import repository
from app.repositories.blog import BlogRepository
from app.core.security import verify_password
from app.core.exceptions import CompatibilityError
from app.services.views import render

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    return render(request, "login.html")


@router.post("/login")
async def login(request: Request, repo: Annotated[BlogRepository, Depends(repository)]):
    data = await request.form()
    username = str(data.get("username", "")).strip()
    user = await run_in_threadpool(repo.user_by_username, username)
    authenticated = user is not None and await run_in_threadpool(verify_password, str(data.get("password", "")), user["password"])
    if not authenticated:
        return RedirectResponse("/login?error", status_code=302)
    store = request.app.state.sessions
    await run_in_threadpool(store.delete, request.cookies.get("JSESSIONID"))
    token, session = await run_in_threadpool(store.create, user["id"], user["username"])
    request.state.new_cookie = token
    request.state.session = session
    return RedirectResponse("/admin", status_code=302)


@router.get("/logout")
def logout_page(request: Request):
    return render(request, "logout.html")


@router.post("/logout")
def logout(request: Request):
    request.app.state.sessions.delete(request.cookies.get("JSESSIONID"))
    request.state.delete_cookie = True
    return RedirectResponse("/", status_code=302)

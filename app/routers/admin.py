import io
import uuid
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from app.dependencies.database import repository
from app.repositories.blog import BlogRepository
from app.schemas.forms import PostForm, LinkForm, UserForm
from app.services import views, posts, catalog, users
from app.core.exceptions import BindingError, CompatibilityError

router = APIRouter(prefix="/admin")
Repo = Annotated[BlogRepository, Depends(repository)]


def redirect(path):
    return RedirectResponse(path, status_code=302)


@router.get("")
@router.get("/")
@router.get("/index")
def dashboard(request: Request, repo: Repo):
    return views.render(request, "admin/dashboard.html", username=request.state.session["username"], postCount=repo.published_count())


@router.get("/posts")
def post_list(request: Request, repo: Repo, page: int = 1, size: int = 10):
    items, total = repo.page_posts("published", page, size)
    return views.render(request, "admin/posts.html", pageInfo=views.page_info(items, total, page, size))


@router.get("/drafts")
def drafts(request: Request, repo: Repo, page: int = 1, size: int = 10):
    items, total = repo.page_posts("drafts", page, size)
    return views.render(request, "admin/drafts.html", pageInfo=views.page_info(items, total, page, size))


@router.get("/posts/new")
def new_post(request: Request, repo: Repo):
    return views.render(request, "admin/post_edit.html", post=PostForm(type="POST").model_dump(), categories=repo.categories())


@router.get("/posts/edit/{id}")
def edit_post(request: Request, id: int, repo: Repo):
    item = repo.post_by_id(id)
    if item is None:
        raise CompatibilityError("Original editor cannot render a null Post")
    return views.render(request, "admin/post_edit.html", post=item, categories=repo.categories())


@router.post("/posts/save")
async def save_post(request: Request, repo: Repo):
    form = PostForm.bind(await request.form())
    _, status = await run_in_threadpool(posts.PostService(repo).save, form)
    return redirect("/admin/drafts" if status == "DRAFT" else "/admin/posts")


@router.post("/posts/delete/{id}")
def move_to_draft(id: int, repo: Repo):
    repo.move_to_draft(id); repo.db.commit()
    return redirect("/admin/posts")


@router.post("/drafts/delete/{id}")
def delete_post(id: int, repo: Repo):
    repo.delete_post(id); repo.db.commit()
    return redirect("/admin/drafts")


@router.get("/posts/download/{id}")
def download(id: int, repo: Repo):
    result = posts.PostService(repo).download(id)
    if result is None:
        return Response(b"", status_code=200)
    body, disposition = result
    return Response(body, media_type="application/zip", headers={"Content-Disposition": disposition})


@router.get("/about")
def about(request: Request, repo: Repo):
    return views.render(request, "admin/about_edit.html", post=posts.PostService(repo).about())


@router.post("/about/save")
async def save_about(request: Request, repo: Repo):
    form = PostForm.bind(await request.form())
    form.type, form.slug, form.status = "PAGE", "about", "PUBLISHED"
    await run_in_threadpool(posts.PostService(repo).save, form)
    return redirect("/admin/about?success=true")


@router.get("/categories")
def categories(request: Request):
    raise CompatibilityError("Original admin/categories template is absent")


@router.get("/comments")
def comments(request: Request, repo: Repo, page: int = 1, size: int = 10):
    items = repo.admin_comments()
    visible = items[max(0, (page - 1) * size):max(0, (page - 1) * size) + size] if page > 0 and size > 0 else []
    return views.render(request, "admin/comments.html", pageInfo=views.page_info(visible, len(items), page, size))


@router.post("/comments/delete/{id}")
def delete_comment(id: int, repo: Repo):
    repo.delete_comment(id); repo.db.commit()
    return redirect("/admin/comments")


@router.get("/links")
def links(request: Request, repo: Repo, page: int = 1, size: int = 10):
    items = repo.links()
    visible = items[max(0, (page - 1) * size):max(0, (page - 1) * size) + size] if page > 0 and size > 0 else []
    return views.render(request, "admin/links.html", pageInfo=views.page_info(visible, len(items), page, size))


@router.get("/links/new")
def new_link(request: Request):
    return views.render(request, "admin/link_edit.html", link=LinkForm().model_dump())


@router.get("/links/edit/{id}")
def edit_link(request: Request, id: int, repo: Repo):
    item = repo.link_by_id(id)
    if item is None:
        raise CompatibilityError("Original editor cannot render a null Link")
    return views.render(request, "admin/link_edit.html", link=item)


@router.post("/links/save")
async def save_link(request: Request, repo: Repo):
    await run_in_threadpool(catalog.save_link, repo, LinkForm.bind(await request.form()))
    return redirect("/admin/links")


@router.post("/links/delete/{id}")
def delete_link(id: int, repo: Repo):
    repo.delete_link(id); repo.db.commit()
    return redirect("/admin/links")


@router.get("/options")
def options(request: Request):
    return views.render(request, "admin/options.html")


@router.post("/options/save")
async def save_options(request: Request, repo: Repo):
    data = dict(await request.form())
    await run_in_threadpool(request.app.state.options.save, repo, data)
    return redirect("/admin/options")


@router.get("/profile")
def profile(request: Request, repo: Repo):
    item = repo.user_by_username(request.state.session["username"])
    if item is None:
        raise CompatibilityError("Original authenticated principal username no longer exists")
    return views.render(request, "admin/profile.html", user=item)


@router.post("/profile/save")
async def save_profile(request: Request, repo: Repo):
    await run_in_threadpool(users.save_profile, repo, UserForm.bind(await request.form()), request)
    return redirect("/admin/profile?success=profile")


@router.post("/profile/password")
async def password(request: Request, repo: Repo):
    data = await request.form()
    try:
        id, old, new = int(data["userId"]), data["oldPassword"], data["newPassword"]
    except (KeyError, ValueError, TypeError) as error:
        raise BindingError("Missing or invalid password form parameters") from error
    success = await run_in_threadpool(users.change_password, repo, request, id, old, new)
    return redirect("/logout" if success else "/admin/profile?error=password")


@router.post("/api/upload")
async def upload(request: Request):
    data = await request.form()
    file = data.get("editormd-image-file")
    if file is None or not hasattr(file, "read"):
        return JSONResponse(dict(success=0, message="文件不能为空"))
    payload = await file.read(request.app.state.settings.max_upload_bytes + 1)
    await file.close()
    if not payload:
        return JSONResponse(dict(success=0, message="文件不能为空"))
    if len(payload) > request.app.state.settings.max_upload_bytes:
        raise HTTPException(413, "Upload exceeds 10 MiB")
    suffix = Path(file.filename or "").suffix
    allowed = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".gif": "GIF", ".bmp": "BMP", ".webp": "WEBP"}
    if suffix.lower() not in allowed:
        return JSONResponse(dict(success=0, message="不支持的图片格式"))
    try:
        with Image.open(io.BytesIO(payload)) as image:
            if image.format != allowed[suffix.lower()]:
                raise ValueError("Mismatched image format")
            image.verify()
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
        return JSONResponse(dict(success=0, message="无效的图片文件"))
    name = str(uuid.uuid4()) + suffix
    destination = request.app.state.settings.uploads_dir / name
    try:
        await run_in_threadpool(destination.write_bytes, payload)
    except OSError:
        return JSONResponse(dict(success=0, message="上传失败: 文件无法写入"))
    return JSONResponse(dict(success=1, message="上传成功", url="/upload/" + name))

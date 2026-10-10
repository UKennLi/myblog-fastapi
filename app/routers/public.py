from typing import Annotated
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import RedirectResponse
from app.dependencies.database import repository
from app.repositories.blog import BlogRepository
from app.schemas.forms import CommentForm
from app.services import views, posts, comments
from app.core.exceptions import CompatibilityError

router = APIRouter()
Repo = Annotated[BlogRepository, Depends(repository)]


def listing(request, repo, kind, value, page, size, **extra):
    items, total = repo.page_posts(kind, page, size, value)
    return views.render(request, "index.html", repo, public=True,
                        recentPosts=items, pageInfo=views.page_info(items, total, page, size), **extra)


@router.get("/")
def index(request: Request, repo: Repo, page: int = 1, size: int = 10):
    return listing(request, repo, "published", None, page, size, paginationUrl="/")


@router.get("/post/{slug}")
def post(request: Request, slug: str, repo: Repo):
    item = repo.post_by_slug(slug)
    if item is None:
        return views.render(request, "error/404.html")
    item["content"] = posts.render_markdown(item["content"]) if item["content"] is not None else None
    return views.render(request, "post.html", repo, public=True, post=item,
                        comments=comments.comment_tree(repo.comments_for_post(item["id"])))


@router.get("/category/{slug}")
def category(request: Request, slug: str, repo: Repo, page: int = 1, size: int = 10):
    category = repo.category_by_slug(slug)
    if category is None:
        return views.render(request, "error/404.html")
    return listing(request, repo, "category", slug, page, size, currentCategory=category, paginationUrl="/category/" + slug)


@router.get("/tag/{slug}")
def tag(request: Request, slug: str, repo: Repo, page: int = 1, size: int = 10):
    tag = repo.tag_by_slug(slug)
    if tag is None:
        return views.render(request, "error/404.html")
    return listing(request, repo, "tag", slug, page, size, currentTag=tag, paginationUrl="/tag/" + slug)


@router.get("/archive")
def archive(request: Request, repo: Repo, page: int = 1, size: int = 30):
    items, total = repo.page_posts("archives", page, size)
    return views.render(request, "archives.html", repo, public=True, posts=items,
                        articleCount=total, pageInfo=views.page_info(items, total, page, size))


@router.get("/search")
def search(request: Request, repo: Repo, keyword: str = Query(...), page: int = 1, size: int = 10):
    return listing(request, repo, "search", keyword, page, size, keyword=keyword, paginationUrl="/search?keyword=" + keyword)


@router.get("/links")
def links(request: Request, repo: Repo):
    return views.render(request, "links.html", repo, public=True, linkMap=repo.link_groups())


@router.post("/comment/submit")
async def submit_comment(request: Request, repo: Repo):
    from starlette.concurrency import run_in_threadpool
    form = CommentForm.bind(await request.form())
    await run_in_threadpool(comments.submit_comment, repo, form, request)
    from urllib.parse import urlsplit
    target = request.headers.get("referer", "/")
    parts = urlsplit(target)
    if parts.scheme not in ("", "http", "https") or (parts.netloc and parts.netloc != request.url.netloc):
        target = "/"
    return RedirectResponse(target, status_code=302)


@router.get("/{slug}")
def page(request: Request, slug: str, repo: Repo):
    if slug == "error":
        raise CompatibilityError("Original /error has no explicit status")
    item = repo.page_by_slug(slug)
    if item is None:
        return views.render(request, "error/404.html")
    item["content"] = posts.render_markdown(item["content"])
    return views.render(request, "page.html", repo, public=True, post=item,
                        comments=comments.comment_tree(repo.comments_for_post(item["id"])))

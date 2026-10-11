from typing import Annotated
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import RedirectResponse, Response
from app.dependencies.database import repository
from app.repositories.blog import BlogRepository
from app.schemas.forms import CommentForm
from app.services import views, posts, comments
from app.core.exceptions import CompatibilityError
from app.services.site_url import public_site_url, public_url

RESERVED_PAGES = {"admin", "login", "logout", "search", "archive", "links", "error", "robots.txt", "sitemap.xml", "favicon.ico", "default-ui.css", "butterfly", "plugins", "webjars", "upload", "post", "category", "tag"}

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
        return views.render(request, "error/404.html", status=404)
    item["content"] = posts.render_markdown(item["content"]) if item["content"] is not None else None
    return views.render(request, "post.html", repo, public=True, post=item,
                        comments=comments.comment_tree(repo.comments_for_post(item["id"])))


@router.get("/category/{slug}")
def category(request: Request, slug: str, repo: Repo, page: int = 1, size: int = 10):
    category = repo.category_by_slug(slug)
    if category is None:
        return views.render(request, "error/404.html", status=404)
    return listing(request, repo, "category", slug, page, size, currentCategory=category, paginationUrl="/category/" + slug)


@router.get("/tag/{slug}")
def tag(request: Request, slug: str, repo: Repo, page: int = 1, size: int = 10):
    tag = repo.tag_by_slug(slug)
    if tag is None:
        return views.render(request, "error/404.html", status=404)
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


@router.get("/robots.txt")
def robots(request: Request):
    base = public_site_url(request.app.state.settings, request.app.state.options.get())
    content = "User-agent: *\nDisallow: /admin\nDisallow: /login\nDisallow: /logout\nDisallow: /search\n"
    if base:
        content += "Sitemap: " + public_url(base, "/sitemap.xml") + "\n"
    return Response(content, media_type="text/plain", headers={"Cache-Control": "no-cache"})


@router.get("/sitemap.xml")
def sitemap(request: Request, repo: Repo):
    from xml.etree.ElementTree import Element, SubElement, tostring
    base = public_site_url(request.app.state.settings, request.app.state.options.get())
    if not base:
        raise HTTPException(503, "Configure PUBLIC_SITE_URL before publishing sitemap")
    # Read fresh published records: no cache invalidation delay, no draft URLs.
    items = repo.rows("SELECT slug,type,modified FROM t_post WHERE status='PUBLISHED' AND type IN ('POST','PAGE') ORDER BY created DESC LIMIT 50001")
    paths = [(path, None) for path in ("/", "/archive", "/links")]
    for item in items:
        slug = item["slug"]
        if not slug or (item["type"] == "PAGE" and (slug in RESERVED_PAGES or "/" in slug)):
            continue
        paths.append((("/post/" if item["type"] == "POST" else "/") + slug, item["modified"]))
    if len(paths) > 50000:
        raise HTTPException(503, "Sitemap index required for more than 50000 URLs")
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    seen = set()
    for path, modified in paths:
        url = public_url(base, path)
        if url in seen:
            continue
        seen.add(url)
        node = SubElement(root, "url")
        SubElement(node, "loc").text = url
        if modified:
            SubElement(node, "lastmod").text = modified.date().isoformat()
    return Response(tostring(root, encoding="utf-8", xml_declaration=True), media_type="application/xml", headers={"Cache-Control": "no-cache"})


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
        return views.render(request, "error/404.html", status=404)
    item["content"] = posts.render_markdown(item["content"])
    return views.render(request, "page.html", repo, public=True, post=item,
                        comments=comments.comment_tree(repo.comments_for_post(item["id"])))

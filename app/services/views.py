from datetime import datetime
from math import ceil
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from fastapi.templating import Jinja2Templates
from jinja2 import StrictUndefined
from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup
import re
from app.core.config import ROOT
from app.core.security import masked_csrf
from app.services.site_url import public_site_url, public_url
from app.services.posts import display_summary


def date_format(value, pattern):
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    for original, replacement in [("yyyy", "%Y"), ("MM", "%m"), ("dd", "%d"), ("HH", "%H"), ("mm", "%M")]:
        pattern = pattern.replace(original, replacement)
    return value.strftime(pattern)


def page_url(url, page):
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    query.append(("page", str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def page_info(items, total, page=1, size=10):
    pages = ceil(total / size) if size > 0 else 0
    start = max(1, page - 4)
    end = min(pages, start + 7)
    start = max(1, end - 7)
    numbers = list(range(start, end + 1))
    return dict(list=items, total=total, pages=pages, pageNum=page, pageSize=size,
                prePage=page - 1 if page > 1 else 0,
                nextPage=page + 1 if page < pages else 0,
                hasPreviousPage=page > 1, hasNextPage=page < pages,
                navigateFirstPage=numbers[0] if numbers else 0,
                navigateLastPage=numbers[-1] if numbers else 0,
                navigatepageNums=numbers)


def make_templates():
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    templates.env.undefined = StrictUndefined
    templates.env.finalize = lambda value: "" if value is None else value
    # Thymeleaf's JavaScript serializer emits uppercase Unicode escape digits.
    templates.env.filters["tojson"] = lambda value: Markup(re.sub(
        r"\\u([0-9a-fA-F]{4})", lambda match: "\\u" + match[1].upper(),
        str(htmlsafe_json_dumps(value))))
    templates.env.globals.update(date_format=date_format, date_year=lambda value: int(date_format(value, "yyyy")),
                                 date_now=datetime.now, is_empty=lambda value: not value,
                                 display_summary=display_summary,
                                 string_contains=lambda value, substring: substring in (value or ""), page_url=page_url)
    return templates


def context(request, repo=None, public=False, **values):
    result = dict.fromkeys([
        "site_title", "site_description", "site_logo", "site_favicon", "icp_beian", "author_name",
        "author_avatar", "author_description", "site_announcement", "statsArticleCount", "statsTagCount",
        "statsCategoryCount", "siteUrl", "isPost", "currentCategory", "currentTag", "keyword",
    ])
    result.update(request.app.state.options.get())
    result["siteUrl"] = public_site_url(request.app.state.settings, result)
    result["public_url"] = lambda path: public_url(result["siteUrl"], path)
    result.update(currentURI=request.url.path,
                  param=dict(success=request.query_params.get("success"), error="error" in request.query_params,
                             logout="logout" in request.query_params),
                  csrf_token=masked_csrf(request.state.session["csrf"]),
                  root_js='""\\/""' if request.app.state.settings.legacy_template_js else '"/"')
    if public:
        # Sidebar template only uses title/slug/created/thumbnail, not relations/count.
        sidebar = repo.post_list_views(repo.rows("SELECT id,title,slug,created,thumbnail FROM t_post WHERE type='POST' AND status='PUBLISHED' ORDER BY created DESC LIMIT 5"), relationships=False)
        result.update(categories=repo.categories(counts=True), tags=repo.tags(), sidebarRecentPosts=sidebar,
                      siteArticleCount=repo.published_count(), menuItems=[
                          dict(name="归档", url="/archive", icon="fas fa-archive"),
                          dict(name="友链", url="/links", icon="fas fa-link"),
                          dict(name="关于", url="/about", icon="fas fa-user"),
                      ])
    result.update(values)
    item = values.get("post")
    result["seo_description"] = display_summary((item.get("summary") or item.get("content")) if item else result.get("site_description"))[:160]
    result["seo_noindex"] = request.url.path == "/search" or bool(item and item.get("status") != "PUBLISHED")
    result["canonical_url"] = public_url(result["siteUrl"], request.url.path) if result["siteUrl"] else ""
    if result["canonical_url"] and not item and request.query_params.get("page", "1").isdigit() and int(request.query_params.get("page", "1")) > 1:
        result["canonical_url"] += "?page=" + str(int(request.query_params["page"]))
    result["og_type"] = "article" if item and item.get("type") == "POST" else "website"
    result["og_image"] = ""
    if item and item.get("thumbnail"):
        image = item["thumbnail"]
        parts = urlsplit(image)
        if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password:
            result["og_image"] = image
        elif image.startswith("/") and not image.startswith("//") and result["siteUrl"]:
            result["og_image"] = public_url(result["siteUrl"], image)
    return result


def render(request, template, repo=None, public=False, status=200, **values):
    return request.app.state.templates.TemplateResponse(request=request, name=template,
        context=context(request, repo, public, **values), status_code=status)

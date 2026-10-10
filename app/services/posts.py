import io
import re
import time
import zipfile
from urllib.parse import quote_plus
from markdown_it import MarkdownIt
from sqlalchemy.exc import IntegrityError

markdown = MarkdownIt("commonmark", {"html": True}).enable("table")


def table_cell(renderer, tokens, index, options, env):
    token = tokens[index]
    style = token.attrs.pop("style", None)
    if style and style.startswith("text-align:"):
        token.attrSet("align", style.removeprefix("text-align:"))
    return renderer.renderToken(tokens, index, options, env)


markdown.add_render_rule("th_open", table_cell)
markdown.add_render_rule("td_open", table_cell)


def render_markdown(content):
    return markdown.render(content) if content is not None else ""


def java_summary(content):
    cleaned = re.sub(r"[#*>\n`]", " ", content)
    encoded = cleaned.encode("utf-16-le", errors="surrogatepass")
    if len(encoded) <= 300:
        return cleaned
    truncated = encoded[:300].decode("utf-16-le", errors="surrogatepass")
    # Connector/J substitutes '?' when UTF-16 substring cuts an emoji surrogate pair.
    return truncated.encode("utf-8", errors="replace").decode("utf-8") + "..."


class PostService:
    def __init__(self, repository):
        self.repo = repository

    def about(self):
        return self.repo.page_by_slug("about") or dict(id=None, title="关于我", slug="about", type="PAGE", status="PUBLISHED", content=None, summary=None, thumbnail=None, categoryId=None, tagsStr=None)

    def save(self, form):
        data = form.model_dump()
        if not data["summary"]:
            data["summary"] = java_summary(data["content"])
        if not data["slug"]:
            data["slug"] = str(int(time.time() * 1000))
        if data["thumbnail"] is None or not data["thumbnail"].strip():
            image = re.search(r"!\[.*?\]\((.*?)\)", data["content"] or "") or re.search(r"<img.*?src=[\"'](.*?)[\"']", data["content"] or "")
            if image:
                data["thumbnail"] = image.group(1)
        data["status"] = data["status"] or "PUBLISHED"
        data["type"] = data["type"] or "POST"
        id = self.repo.save_post(data)
        if data["tagsStr"] is not None:
            self.repo.clear_post_tags(id)
            for name in re.split("[,，]", data["tagsStr"]):
                # Java String.trim removes <= U+0020, not all Unicode whitespace.
                name = name.strip("\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f ")
                if not name:
                    continue
                tag = self.repo.one("SELECT * FROM t_tag WHERE name=:name", name=name)
                if tag is None:
                    tag_id = self.repo.execute("INSERT INTO t_tag(name,slug) VALUES(:name,:name)", name=name).lastrowid
                else:
                    tag_id = tag["id"]
                # Original ignores duplicate relations without discarding other writes.
                try:
                    with self.repo.db.begin_nested():
                        self.repo.execute("INSERT INTO t_post_tag(post_id,tag_id) VALUES(:post,:tag)", post=id, tag=tag_id)
                except IntegrityError:
                    pass
        self.repo.db.commit()
        return id, data["status"]

    def download(self, id):
        post = self.repo.post_by_id(id)
        if post is None:
            return None
        stem = str(post["id"]) + "_" + re.sub(r'[\\/:*?"<>|]', "_", post["title"])
        images = set()

        def image(match):
            alt, url = match.groups()
            if url.startswith("/upload/"):
                name = url.rsplit("/", 1)[-1]
                images.add(name)
                return f"![{alt}](images/{name})"
            return match.group(0)

        content = re.sub(r"!\[(.*?)\]\((.*?)\)", image, post["content"])
        front = "---\ntitle: " + post["title"] + "\ndate: " + post["created"].strftime("%Y-%m-%d %H:%M:%S") + "\n"
        if post["category"] is not None:
            front += "categories: [" + post["category"]["name"] + "]\n"
        if post["tags"]:
            front += "tags: [" + ", ".join(t["name"] for t in post["tags"]) + "]\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(stem + ".md", front + "---\n\n" + content)
            for name in sorted(images):
                path = (self.repo.settings.uploads_dir / name).resolve()
                if path.parent == self.repo.settings.uploads_dir.resolve() and path.is_file():
                    archive.write(path, "images/" + name)
        return buffer.getvalue(), 'attachment; filename="' + quote_plus(stem) + '.zip"'

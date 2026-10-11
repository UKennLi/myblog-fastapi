import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from PIL import Image
from app.core.config import ROOT
from app.core.security import encode_password, verify_password
from app.repositories.blog import BlogRepository
from app.services.catalog import save_category
from app.services.posts import render_markdown
from conftest import login, post, query, token, write


def test_public_read_routes_and_binding(application):
    app, client = application
    for path in ["/", "/post/hello-world", "/post/springboot-is-good", "/about", "/archive", "/links", "/category/default", "/category/dev-think", "/search?keyword=Spring"]:
        assert client.get(path).status_code == 200, path
    assert "你好，世界！" in client.get("/post/hello-world").text
    assert client.get("/search").status_code == 400
    assert client.get("/?page=invalid").status_code == 400
    assert "recent-post-item" not in client.get("/?page=0&size=1").text
    assert client.head("/").status_code == 200
    assert client.get("/post/missing").status_code == 404
    assert client.get("/error").status_code == 500


def test_authentication_csrf_session_rotation_and_revocation(application):
    app, client = application
    assert client.get("/admin", follow_redirects=False).status_code == 302
    assert client.get("/admin/posts", follow_redirects=False).status_code == 302
    assert client.post("/login", data={"username": "riuken", "password": "123456"}, follow_redirects=False).status_code == 403
    csrf = token(client)
    anonymous = client.cookies.get("JSESSIONID")
    wrong = client.post("/login", data={"username": "riuken", "password": "wrong", "_csrf": csrf}, follow_redirects=False)
    assert wrong.headers["location"].endswith("/login?error")
    login(client, username="RIUKEN")
    assert app.state.sessions.get(client.cookies.get("JSESSIONID"))["username"] == "riuken"
    authenticated = client.cookies.get("JSESSIONID")
    assert authenticated != anonymous
    assert app.state.sessions.get(anonymous) is None
    assert client.get("/admin").status_code == 200
    assert client.post("/admin/posts/delete/2", data={"_csrf": csrf}, follow_redirects=False).status_code == 403
    assert client.get("/logout").status_code == 200
    logout = client.post("/logout", data={"_csrf": token(client, "/logout")}, follow_redirects=False)
    assert logout.status_code == 302 and logout.headers["location"].endswith("/")
    assert app.state.sessions.get(authenticated) is None
    client.cookies.set("JSESSIONID", authenticated)
    assert client.get("/admin/posts", follow_redirects=False).status_code == 302


def test_post_publish_edit_tags_draft_and_delete(application):
    app, client = application
    login(client)
    response = post(client, "/admin/posts/save", dict(title="迁移测试", content="# 测试\n![封面](/upload/example.png)", categoryId="1", tagsStr="Python，FastAPI,Python, ", status="PUBLISHED"))
    assert response.status_code == 302 and response.headers["location"].endswith("/admin/posts")
    row = query(app, "SELECT * FROM t_post WHERE title=:title", title="迁移测试")[0]
    assert row["slug"].isdigit() and row["thumbnail"] == "/upload/example.png"
    assert row["summary"] == "测试"
    assert row["content_html"] is None
    assert len(query(app, "SELECT * FROM t_post_tag WHERE post_id=:id", id=row["id"])) == 2
    assert "Python" in client.get("/tag/Python").text
    assert "selected" in client.get("/admin/posts/edit/" + str(row["id"])).text
    post(client, "/admin/posts/save", dict(id=row["id"], title="已更新", content="新正文", slug=row["slug"], summary="指定摘要", categoryId=1, tagsStr="", type="PAGE", status="PUBLISHED"))
    updated = query(app, "SELECT * FROM t_post WHERE id=:id", id=row["id"])[0]
    assert updated["type"] == "POST" and updated["summary"] == "指定摘要"
    assert query(app, "SELECT * FROM t_post_tag WHERE post_id=:id", id=row["id"]) == []
    post(client, "/admin/posts/delete/" + str(row["id"]))
    assert query(app, "SELECT status FROM t_post WHERE id=:id", id=row["id"])[0]["status"] == "DRAFT"
    assert "已更新" in client.get("/admin/drafts").text
    assert "已更新" not in client.get("/post/" + row["slug"]).text
    post(client, "/admin/drafts/delete/" + str(row["id"]))
    assert query(app, "SELECT id FROM t_post WHERE id=:id", id=row["id"]) == []
    assert len(query(app, "SELECT * FROM t_tag WHERE name IN ('Python','FastAPI')")) == 2


def test_atomic_post_tag_failure_rolls_back(application):
    app, client = application
    login(client)
    response = post(client, "/admin/posts/save", dict(title="应回滚", slug="rollback-check", content="正文", tagsStr="x" * 60))
    assert response.status_code == 500
    assert query(app, "SELECT * FROM t_post WHERE slug='rollback-check'") == []


def test_about_page_save_and_empty_about_model(application):
    app, client = application
    login(client)
    response = post(client, "/admin/about/save", dict(id=1, title="关于更新", content="## 关于正文", thumbnail=""))
    assert response.headers["location"].endswith("/admin/about?success=true")
    row = query(app, "SELECT * FROM t_post WHERE id=1")[0]
    assert row["type"] == "PAGE" and row["slug"] == "about" and row["status"] == "PUBLISHED"
    assert "<h2>关于正文</h2>" in client.get("/about").text
    write(app, "DELETE FROM t_post WHERE id=1")
    assert client.get("/admin/about").status_code == 200
    assert query(app, "SELECT * FROM t_post WHERE slug='about'") == []


def test_comments_tree_status_admin_guard_and_deletion(application):
    app, client = application
    result = client.post("/comment/submit", data=dict(postId=2, parentId="", author="访客<script>", email="Test@Example.com", content="<script>alert(1)</script>"), headers={"Referer": "http://testserver/post/hello-world"}, follow_redirects=False)
    assert result.status_code == 302
    root = query(app, "SELECT * FROM t_comment WHERE post_id=2")[0]
    assert root["status"] == "APPROVED" and root["is_admin"] == 0
    client.post("/comment/submit", data=dict(postId=2, parentId=root["id"], author="回复", email="", content="嵌套评论"), follow_redirects=False)
    client.post("/comment/submit", data=dict(postId=2, author="审核", email="", content="待审核", status="WAITING"), follow_redirects=False)
    text = client.get("/post/hello-world").text
    assert "嵌套评论" in text and "待审核" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert hashlib.md5(b"test@example.com").hexdigest() in text
    assert client.post("/comment/submit", data=dict(postId=2, author="伪造", email="", content="伪造", isAdmin="true"), follow_redirects=False).status_code == 403
    login(client)
    assert "待审核" in client.get("/admin/comments").text
    post(client, "/admin/comments/delete/" + str(root["id"]))
    assert "嵌套评论" not in client.get("/post/hello-world").text
    assert len(query(app, "SELECT * FROM t_comment WHERE parent_id=:id", id=root["id"])) == 1


def test_comment_missing_email_matches_database_constraint(application):
    app, client = application
    assert client.post("/comment/submit", data=dict(postId=2, author="无邮箱字段", content="test"), follow_redirects=False).status_code == 500


def test_links_crud_defaults_and_order(application):
    app, client = application
    login(client)
    response = post(client, "/admin/links/save", dict(name="新增友链", url="https://example.com", logo="", description="说明", team="", sort=""))
    assert response.status_code == 302
    row = query(app, "SELECT * FROM t_link WHERE name='新增友链'")[0]
    assert row["team"] == "Friends" and row["sort"] == 0
    post(client, "/admin/links/save", dict(id=row["id"], name="更新友链", url="https://example.com/new", logo="", description="新说明", team="测试组", sort="999"))
    assert "测试组" in client.get("/links").text
    assert "更新友链" in client.get("/admin/links/edit/" + str(row["id"])).text
    post(client, "/admin/links/delete/" + str(row["id"]))
    assert query(app, "SELECT * FROM t_link WHERE id=:id", id=row["id"]) == []


def test_option_upsert_cache_and_no_csrf_persistence(application):
    app, client = application
    login(client)
    response = post(client, "/admin/options/save", dict(site_title="新站点标题", site_announcement="<strong>公告</strong>"))
    assert response.status_code == 302
    assert "新站点标题" in client.get("/").text
    assert "<strong>公告</strong>" in client.get("/").text
    assert query(app, "SELECT * FROM t_option WHERE option_key='_csrf'") == []


def test_profile_idor_and_bcrypt_password_compatibility(application):
    app, client = application
    login(client)
    assert post(client, "/admin/profile/save", dict(id=999, username="riuken", nickname="x")).status_code == 403
    assert post(client, "/admin/profile/password", dict(userId=999, oldPassword="123456", newPassword="abcdef")).status_code == 403
    assert post(client, "/admin/profile/save", dict(id=1, username="riuken", nickname="新昵称", email="new@example.com", avatar="/butterfly/img/avatar.jpg")).status_code == 302
    assert "新昵称" in client.get("/admin/profile").text
    bad = post(client, "/admin/profile/password", dict(userId=1, oldPassword="wrong", newPassword="abcdef"))
    assert bad.headers["location"].endswith("/admin/profile?error=password")
    changed = post(client, "/admin/profile/password", dict(userId=1, oldPassword="123456", newPassword="abcdef"))
    assert changed.headers["location"].endswith("/logout")
    stored = query(app, "SELECT password FROM t_user WHERE id=1")[0]["password"]
    assert stored.startswith("$2a$10$") and verify_password("abcdef", stored)
    assert not verify_password("123456", stored)
    login(client, password="abcdef")


def test_upload_real_images_and_reject_active_or_invalid_content(application):
    app, client = application
    assert client.post("/admin/api/upload", follow_redirects=False).status_code == 302
    login(client)
    assert client.post("/admin/api/upload").json() == dict(success=0, message="文件不能为空")
    buffer = io.BytesIO(); Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    payload = buffer.getvalue()
    result = client.post("/admin/api/upload", files={"editormd-image-file": ("example.png", payload, "image/png")}).json()
    assert result["success"] == 1 and result["message"] == "上传成功"
    assert client.get(result["url"]).content == payload
    assert list(app.state.settings.uploads_dir.iterdir())[0].read_bytes() == payload
    assert client.post("/admin/api/upload", files={"editormd-image-file": ("attack.html", b"<script>alert(1)</script>", "text/html")}).json()["success"] == 0
    assert client.post("/admin/api/upload", files={"editormd-image-file": ("attack.png", b"<script>alert(1)</script>", "image/png")}).json()["success"] == 0
    assert client.post("/admin/api/upload", files={"editormd-image-file": ("big.png", b"x" * (10 * 1024 * 1024 + 1), "image/png")}).status_code == 413
    assert client.get("/upload/%2e%2e/static/default-ui.css").status_code == 404


def test_download_markdown_local_images_headers_and_missing_id(application):
    app, client = application
    login(client)
    file = app.state.settings.uploads_dir / "test.png"; file.write_bytes(b"local image bytes")
    post(client, "/admin/posts/save", dict(title="备份 标题/测试", slug="download-test", content="![本地](/upload/test.png)\n![远程](https://example.com/a.png)", categoryId=1, tagsStr="Java,Python"))
    row = query(app, "SELECT * FROM t_post WHERE slug='download-test'")[0]
    response = client.get("/admin/posts/download/" + str(row["id"]))
    assert response.headers["content-type"] == "application/zip"
    assert "+" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.read("images/test.png") == b"local image bytes"
        md = archive.read(next(name for name in archive.namelist() if name.endswith(".md"))).decode()
        assert "![本地](images/test.png)" in md and "tags: [Java, Python]" in md
        assert "categories:" not in md
    missing = client.get("/admin/posts/download/999999999")
    assert missing.status_code == 200 and missing.content == b""


def test_schema_unchanged_and_account_has_no_ddl(application):
    app, client = application
    inspector = inspect(app.state.engine)
    before = {table: [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspector.get_columns(table)] for table in inspector.get_table_names()}
    assert set(before) == {"t_user", "t_category", "t_post", "t_tag", "t_post_tag", "t_comment", "t_option", "t_link"}
    assert "content_html" in {column[0] for column in before["t_post"]}
    login(client)
    post(client, "/admin/posts/save", dict(title="Schema检查", slug="schema-check", content="检查"))
    inspector.clear_cache()
    after = {table: [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspector.get_columns(table)] for table in inspector.get_table_names()}
    assert before == after
    with app.state.session_factory() as db:
        with pytest.raises(DBAPIError):
            db.execute(text("CREATE TABLE migration_must_not_create(id INT)"))


def test_category_service_and_counts_preserve_unexposed_mapper_behavior(application):
    app, client = application
    login(client)
    assert client.get("/admin/categories").status_code == 500
    with app.state.session_factory() as db:
        repo = BlogRepository(db, app.state.settings)
        id = save_category(repo, dict(id=None, name="新分类", slug="new-category"))
        save_category(repo, dict(id=id, name="改分类", slug="new-category"))
        assert repo.category_by_id(id)["name"] == "改分类"
        repo.delete_category(id); db.commit()
        assert repo.category_by_id(id) is None
        assert repo.categories(counts=True)[0]["count"] == 2


def test_sql_injection_special_characters_and_error_routes(application):
    app, client = application
    assert client.get("/search", params={"keyword": "' OR 1=1 --"}).status_code == 200
    assert "recent-post-item" not in client.get("/search", params={"keyword": "' OR 1=1 --"}).text
    assert client.get("/login?logout").status_code == 200
    login(client)
    assert client.get("/admin/posts/edit/not-a-number").status_code == 400
    assert client.get("/admin/posts/edit/999999").status_code == 500
    assert client.get("/admin/links/edit/999999").status_code == 500
    assert client.post("/admin/posts/delete/2", data={"_csrf": "fake"}, follow_redirects=False).status_code == 403
    assert client.get("/webjars/bootstrap/5.3.2/css/bootstrap.min.css").status_code == 200
    assert client.get("/webjars/bootstrap-icons/1.11.3/font/bootstrap-icons.css").status_code == 404


def test_static_files_unchanged_and_markdown_commonmark(application):
    app, client = application
    manifest = json.loads((ROOT / "docs/asset-manifest.json").read_text())
    for item in manifest["assets"]:
        if item["path"].startswith("upload/"):
            continue
        file = ROOT / "static" / item["path"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item["sha256"]
    assert render_markdown("# 标题\n\n**粗体**") == "<h1>标题</h1>\n<p><strong>粗体</strong></p>\n"
    assert "<table>" in render_markdown("|a|b|\n|-|-|\n|1|2|")
    assert "<div>原HTML</div>" in render_markdown("<div>原HTML</div>")


def test_markdown_matches_original_commonmark_fixtures():
    cases = json.loads((ROOT / "reports/markdown-comparison.json").read_text())
    for case in cases:
        assert render_markdown(case["source"]) == case["original"], case["name"]


def test_comment_active_urls_and_cross_origin_redirects(application):
    app, client = application
    form = dict(postId=2, author='访客', email='', content='评论')
    assert client.post('/comment/submit', data={**form, 'url':'java\tscript:alert(1)'}, follow_redirects=False).status_code == 403
    response = client.post('/comment/submit', data={**form, 'url':'https://example.com'}, headers={'Referer':'https://other.example/post/hello-world'}, follow_redirects=False)
    assert response.status_code == 302 and response.headers['location'] == 'http://testserver/'
    write(app, "INSERT INTO t_comment(post_id,author,email,content,url) VALUES(2,'old','','historical','javascript:alert(1)')")
    assert 'href="javascript:' not in client.get('/post/hello-world').text


def test_summary_unicode_boundary_preserves_whole_emoji(application):
    app, client = application
    login(client)
    response = post(client, '/admin/posts/save', dict(title='Emoji边界',slug='emoji-boundary',content='a'+'😀'*150))
    assert response.status_code == 302
    assert query(app,"SELECT summary FROM t_post WHERE slug='emoji-boundary'")[0]['summary'] == 'a'+'😀'*149+'...'


def test_application_restart_invalidates_session_like_spring(application):
    app, client = application
    login(client)
    session = client.cookies.get("JSESSIONID")
    from app.main import create_app
    from fastapi.testclient import TestClient
    restarted = create_app(app.state.settings)
    with TestClient(restarted) as new_client:
        new_client.cookies.set("JSESSIONID", session)
        assert new_client.get("/admin/posts", follow_redirects=False).status_code == 302
    assert app.state.sessions.get(session) is None

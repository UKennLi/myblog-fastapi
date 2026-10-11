import pytest
from conftest import write
from app.services.site_url import normalize_site_url


@pytest.mark.parametrize("value", [None, "", "null", "javascript:alert(1)", "http://127.0.0.1:8000", "http://localhost", "https://user:pass@example.com", "https://example.com/?x=1", "https://example.com/#x", "https://example.com\n", "http://10.0.0.1", "https://example.com:bad"])
def test_invalid_public_origins(value):
    # Surrounding whitespace is harmless; embedded control characters are not.
    if value == "https://example.com\n":
        assert normalize_site_url(value) == "https://example.com"
    else:
        assert normalize_site_url(value) == ""


def test_copyright_configuration_and_no_header_fallback(application):
    app, client = application
    app.state.settings.public_site_url = "https://riuken.com/"
    response = client.get('/post/hello-world')
    assert 'href="https://riuken.com/post/hello-world"' in response.text
    assert 'FastAPI</a>' in response.text and 'Theme - Butterfly' in response.text
    app.state.settings.public_site_url = ''
    with app.state.options.lock:
        app.state.options.options['siteUrl'] = 'https://configured.example/'
    assert 'https://configured.example/post/hello-world' in client.get('/post/hello-world').text
    with app.state.options.lock:
        app.state.options.options['siteUrl'] = None
    response = client.get('/post/hello-world', headers={'Host':'attacker.example', 'Forwarded':'host=attacker.example;proto=https'})
    assert 'href="/post/hello-world">/post/hello-world</a>' in response.text
    assert 'null/post/' not in response.text and 'https://attacker.example/post/' not in response.text


def test_comment_renders_each_level_once(application):
    app, client = application
    root = write(app, "INSERT INTO t_comment(post_id,author,email,content) VALUES(2,'root','','unique-root')")
    child = write(app, "INSERT INTO t_comment(post_id,parent_id,author,email,content) VALUES(2,:parent,'child','','unique-child')", parent=root)
    html = client.get('/post/hello-world').text
    assert html.count(f'id="comment-{root}"') == 1
    assert html.count(f'id="comment-{child}"') == 1
    assert html.count('id="comment-form"') == 1
    assert 'vchildren' in html and f'reply({root},' in html


def test_legacy_fixes_and_missing_status(application):
    app, client = application
    for path in ['/post/missing','/category/missing','/tag/missing','/missing']:
        assert client.get(path).status_code == 404
    assert 'You have been signed out' in client.get('/login?logout').text
    assert 'root: "/"' in client.get('/').text
    from conftest import login
    login(client)
    assert '/bootstrap-icons/1.13.1/' in client.get('/admin').text
    assert client.get('/webjars/bootstrap-icons/1.13.1/font/bootstrap-icons.css').status_code == 200


def test_summary_non_destructive_and_manual_value_preserved(application):
    from app.services.posts import automatic_summary, display_summary
    from conftest import login,post,query
    assert automatic_summary('# 中文 日本語 English\n![图片](https://example.com/a.png)\n[链接](https://example.com) **正文**') == '中文 日本語 English 链接 正文'
    assert display_summary('历史 ![图片](https://example.com/truncated') == '历史'
    assert '<script>' not in display_summary('<script>alert(1)</script>正文')
    app,client=application
    old='历史 ![图片](https://example.com/a.png) [正文](https://example.com)'
    write(app,'UPDATE t_post SET summary=:summary WHERE id=2',summary=old)
    assert 'https://example.com/a.png' not in client.get('/').text
    assert query(app,'SELECT summary FROM t_post WHERE id=2')[0]['summary']==old
    login(client)
    post(client,'/admin/posts/save',dict(title='手写',slug='manual-summary',content='正文',summary='保留 **手写** 摘要'))
    assert query(app,"SELECT summary FROM t_post WHERE slug='manual-summary'")[0]['summary']=='保留 **手写** 摘要'


def test_batched_relationships_match_existing_lookup(application):
    from app.repositories.blog import BlogRepository
    from sqlalchemy import event
    app,client=application
    with app.state.session_factory() as db:
        repo=BlogRepository(db,app.state.settings)
        for kind,value in [('published',None),('category','default'),('tag','Spring Boot'),('search','Spring')]:
            sql,params=repo.post_query(kind,value)
            rows=repo.rows(sql,**params)
            expected=[repo.post_view(row) for row in rows]
            actual,total=repo.page_posts(kind,1,10,value)
            assert actual==expected and total==len(expected)
    calls=[]
    def count(*args): calls.append(args[2])
    event.listen(app.state.engine,'before_cursor_execute',count)
    try:
        assert client.get('/').status_code==200
    finally:
        event.remove(app.state.engine,'before_cursor_execute',count)
    assert len(calls)<=9, calls


def test_markdown_cache_updates_and_keeps_html_security_contract():
    from app.services.posts import render_markdown,_cached_markdown
    _cached_markdown.cache_clear()
    assert render_markdown('# before')=='<h1>before</h1>\n'
    assert render_markdown('# before')=='<h1>before</h1>\n'
    assert _cached_markdown.cache_info().hits==1
    assert render_markdown('# after')=='<h1>after</h1>\n'
    assert '<div>trusted author</div>' in render_markdown('<div>trusted author</div>')
    before=_cached_markdown.cache_info().currsize
    render_markdown('x'*65537)
    assert _cached_markdown.cache_info().currsize==before


def test_page_comments_unique_native_container_and_styles(application):
    app,client=application
    root=write(app,"INSERT INTO t_comment(post_id,author,email,content) VALUES(1,'page visitor','','page comment')")
    html=client.get('/about').text
    assert html.count(f'id="comment-{root}"')==1
    assert html.count('id="comment-form"')==1
    assert '#post-comment .comment-wrap > .vlist' in client.get('/butterfly/css/comment.css').text

import pytest
from conftest import write
from app.services.site_url import normalize_site_url


@pytest.mark.parametrize("value", [None, "", "null", "javascript:alert(1)", "http://127.0.0.1:8000", "http://localhost", "https://user:pass@example.com", "https://example.com/?x=1", "https://example.com/#x", "https://example.com\n", "http://10.0.0.1", "https://example.com:bad", "http://127.1", "https://bad_host.example"])
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


def test_seo_sitemap_fresh_published_only_and_unconfigured_safe(application):
    import xml.etree.ElementTree as ET
    from conftest import login,post
    app,client=application
    with app.state.options.lock: app.state.options.options.pop('siteUrl',None)
    app.state.settings.public_site_url=''
    assert client.get('/sitemap.xml').status_code==503
    assert 'Sitemap:' not in client.get('/robots.txt').text
    assert 'rel="canonical"' not in client.get('/').text
    app.state.settings.public_site_url='https://riuken.com'
    html=client.get('/post/hello-world').text
    assert 'rel="canonical" href="https://riuken.com/post/hello-world"' in html
    assert 'property="og:type" content="article"' in html
    assert 'name="description"' in html
    assert 'name="robots" content="noindex,follow"' in client.get('/search?keyword=Spring').text
    assert 'https://riuken.com/?page=2' in client.get('/?page=2').text
    assert 'Disallow: /admin' in client.get('/robots.txt').text
    assert 'Sitemap: https://riuken.com/sitemap.xml' in client.get('/robots.txt').text
    login(client)
    for slug,kind,status in [('seo-live','POST','PUBLISHED'),('seo-draft','POST','DRAFT'),('seo-page','PAGE','PUBLISHED'),('seo-page-draft','PAGE','DRAFT')]:
        post(client,'/admin/posts/save',dict(title='SEO',slug=slug,content='正文',type=kind,status=status))
    def urls():
        r=client.get('/sitemap.xml');assert r.status_code==200
        return [n.text for n in ET.fromstring(r.content).findall('.//{*}loc')]
    paths=urls()
    assert 'https://riuken.com/post/seo-live' in paths and 'https://riuken.com/seo-page' in paths
    assert not any('draft' in u or '/admin' in u or '/login' in u or '127.0.0.1' in u for u in paths)
    from conftest import query
    id=query(app,"SELECT id FROM t_post WHERE slug='seo-live'")[0]['id']
    post(client,f'/admin/posts/delete/{id}')
    assert 'https://riuken.com/post/seo-live' not in urls()


def test_static_browser_cache_and_lazy_non_hero_images(application):
    app,client=application
    r=client.get('/butterfly/css/index.css')
    assert r.headers['cache-control']=='private, max-age=300, must-revalidate'
    assert client.get('/butterfly/css/index.css',headers={'If-None-Match':r.headers['etag']}).status_code==304
    assert 'no-store' in client.get('/').headers['cache-control']
    assert client.get('/butterfly/missing.css').status_code==404
    assert 'no-store' in client.get('/butterfly/missing.css').headers['cache-control']
    html=client.get('/').text
    assert 'loading="lazy"' in html and 'decoding="async"' in html


def test_backup_preview_and_mocked_export(tmp_path):
    import os,subprocess
    from pathlib import Path
    from app.core.config import ROOT
    project=tmp_path/'project';project.mkdir();(project/'uploads').mkdir();(project/'uploads'/'kept.png').write_bytes(b'fixture')
    (project/'.env').write_text('TEST_ONLY=fixture\n')
    subprocess.run(['git','init','-q',str(project)],check=True)
    subprocess.run(['git','-C',str(project),'-c','user.name=Test','-c','user.email=test@example.com','commit','--allow-empty','-qm','fixture'],check=True)
    cnf=tmp_path/'client.cnf';cnf.write_text('[client]\nuser=fixture\n');cnf.chmod(0o600)
    backups=tmp_path/'backups';script=ROOT/'scripts/production_backup.sh'
    subprocess.run(['bash',str(script),str(project),str(backups),str(cnf)],check=True,capture_output=True)
    assert not backups.exists()
    bad=subprocess.run(['bash',str(script),str(project),str(project/'backup'),str(cnf)],capture_output=True)
    assert bad.returncode!=0
    tools=tmp_path/'bin';tools.mkdir();dump=tools/'mysqldump'
    dump.write_text('#!/bin/sh\nfor arg in "$@"; do echo "$arg" >> "$TEST_ARGS_FILE"; done\necho "INSERT INTO t_option VALUES (1);"\n');dump.chmod(0o700)
    args_file=tmp_path/'args';env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'TEST_ARGS_FILE':str(args_file)}
    subprocess.run(['bash',str(script),'--execute',str(project),str(backups),str(cnf)],check=True,capture_output=True,env=env)
    args=args_file.read_text()
    assert all(flag in args for flag in ['--no-create-info','--skip-add-drop-table','--single-transaction','--skip-disable-keys','--skip-add-locks'])
    destination=next(backups.iterdir())
    assert (destination/'uploads.tar.gz').is_file() and (destination/'private.env').is_file()
    assert destination.stat().st_mode & 0o077==0
    subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=destination,check=True,capture_output=True)
    assert (project/'uploads'/'kept.png').read_bytes()==b'fixture'


def test_page_comments_unique_native_container_and_styles(application):
    app,client=application
    root=write(app,"INSERT INTO t_comment(post_id,author,email,content) VALUES(1,'page visitor','','page comment')")
    html=client.get('/about').text
    assert html.count(f'id="comment-{root}"')==1
    assert html.count('id="comment-form"')==1
    assert '#post-comment .comment-wrap > .vlist' in client.get('/butterfly/css/comment.css').text


def test_existing_favicon_option_is_rendered_after_cache_reload(application):
    from conftest import login,post,query
    app,client=application
    login(client)
    response=post(client,'/admin/options/save',dict(site_favicon='/butterfly/img/1d.png',site_logo='/butterfly/img/logo.png'))
    assert response.status_code==302
    assert query(app,"SELECT option_value FROM t_option WHERE option_key='site_favicon'")[0]['option_value']=='/butterfly/img/1d.png'
    assert '<link rel="icon" href="/butterfly/img/1d.png">' in client.get('/').text

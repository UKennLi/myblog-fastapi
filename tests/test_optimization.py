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

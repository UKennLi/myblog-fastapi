import os
import re
from pathlib import Path
import pytest
from dotenv import load_dotenv
from sqlalchemy import text
from fastapi.testclient import TestClient

if os.environ.get("MIGRATION_ENV_FILE"):
    load_dotenv(os.environ["MIGRATION_ENV_FILE"], override=True)

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def application(tmp_path):
    settings = Settings(session_file=tmp_path / "sessions.sqlite3", uploads_dir=tmp_path / "uploads")
    app = create_app(settings)
    with app.state.session_factory() as db:
        identity = db.execute(text("SELECT @@server_uuid")).scalar_one()
    if os.environ.get("TEST_DATABASE_IS_DISPOSABLE") != "1" or identity != os.environ.get("TEST_MYSQL_SERVER_UUID"):
        pytest.fail("Refusing writes: set a disposable MySQL instance and its exact TEST_MYSQL_SERVER_UUID")
    # Preserve all test-instance records; restoration is DML only, never DDL.
    names = ["t_post_tag", "t_comment", "t_post", "t_tag", "t_category", "t_link", "t_option", "t_user"]
    with app.state.session_factory() as db:
        snapshot = {table: [dict(row) for row in db.execute(text("SELECT * FROM " + table)).mappings()] for table in names}
    with TestClient(app, raise_server_exceptions=False) as client:
        yield app, client
    with app.state.session_factory() as db:
        for table in names:
            db.execute(text("DELETE FROM " + table))
        for table in reversed(names):
            for row in snapshot[table]:
                columns = ",".join("`" + key + "`" for key in row)
                placeholders = ",".join(":" + key for key in row)
                db.execute(text("INSERT INTO " + table + " (" + columns + ") VALUES (" + placeholders + ")"), row)
        db.commit()


def token(client, path="/login"):
    response = client.get(path)
    assert response.status_code == 200
    match = re.search(r'name="_csrf"[^>]*value="([^"]+)"', response.text)
    assert match, path
    return match[1]


def login(client, username="riuken", password="123456"):
    response = client.post("/login", data={"username": username, "password": password, "_csrf": token(client)}, follow_redirects=False)
    assert response.status_code == 302 and response.headers["location"].endswith("/admin")


def post(client, path, data=None):
    values = dict(data or {})
    values["_csrf"] = token(client, "/admin/profile")
    return client.post(path, data=values, follow_redirects=False)


def query(app, sql, **parameters):
    with app.state.session_factory() as db:
        return [dict(row) for row in db.execute(text(sql), parameters).mappings()]


def write(app, sql, **parameters):
    with app.state.session_factory() as db:
        result = db.execute(text(sql), parameters)
        db.commit()
        return result.lastrowid

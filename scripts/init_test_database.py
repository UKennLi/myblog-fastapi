"""Explicit one-time setup of a NEW disposable database. Never resets databases."""
import argparse
import os
import re
from pathlib import Path
import pymysql
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--server-uuid", required=True)
    parser.add_argument("--disposable", action="store_true", required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    name = os.environ.get("DB_NAME", "myblog_db")
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit("Invalid database name")
    db = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)),
                         user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], autocommit=True)
    root = Path(__file__).resolve().parents[1]
    with db.cursor() as cursor:
        cursor.execute("SELECT @@server_uuid")
        if cursor.fetchone()[0] != args.server_uuid:
            raise SystemExit("Refusing unexpected MySQL server")
        cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
        if cursor.fetchone():
            raise SystemExit("Refusing existing database; this script never resets data")
        cursor.execute("CREATE DATABASE `" + name + "` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
        cursor.execute("USE `" + name + "`")
        for source in [root / "docs/schema.sql", root / "tests/demo_seed.sql"]:
            # Original seed contains no semicolons inside quoted content.
            sql = re.sub(r"^--.*$", "", source.read_text(), flags=re.M)
            for statement in sql.split(";"):
                if statement.strip():
                    cursor.execute(statement)
    db.close()
    print("Created the explicitly identified NEW disposable demo database")


if __name__ == "__main__":
    main()

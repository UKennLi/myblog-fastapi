"""Read-only inventory of the existing schema; never creates or changes tables."""
import argparse
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--output", default="reports/database-inspection.json")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    from app.core.config import Settings
    from app.db.session import make_database
    from app.models.tables import tables
    engine, factory = make_database(Settings())
    result = {}
    with factory() as db:
        for name in tables:
            create = db.execute(text("SHOW CREATE TABLE " + name)).one()[1]
            result[name] = dict(ddl=re.sub(r"AUTO_INCREMENT=\d+", "AUTO_INCREMENT=COUNTER", create),
                                rows=db.execute(text("SELECT COUNT(*) FROM " + name)).scalar_one())
    engine.dispose()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Inspected 8 existing tables without schema changes:", path)


if __name__ == "__main__":
    main()

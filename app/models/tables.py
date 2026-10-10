"""Mappings only: never call create_all or execute DDL in the application."""
from sqlalchemy import Column, MetaData, Table, String, DateTime, text, UniqueConstraint, Index
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT, LONGTEXT, TEXT
from sqlalchemy.orm import registry

metadata = MetaData()
mapper_registry = registry(metadata=metadata)


def ident():
    return Column("id", BIGINT, primary_key=True, autoincrement=True)


def created():
    return Column("created", DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=True)


tables = {
    "t_user": Table("t_user", metadata, ident(), Column("username", String(50), nullable=False),
                    Column("password", String(100), nullable=False), Column("nickname", String(50)),
                    Column("email", String(100)), Column("avatar", String(255)), created(), UniqueConstraint("username", name="uk_username")),
    "t_category": Table("t_category", metadata, ident(), Column("name", String(50), nullable=False),
                        Column("slug", String(50), nullable=False), UniqueConstraint("slug", name="uk_slug")),
    "t_post": Table("t_post", metadata, ident(), Column("title", String(255), nullable=False),
                    Column("slug", String(255)), Column("content", LONGTEXT),
                    Column("content_html", LONGTEXT), Column("summary", String(500)), Column("thumbnail", String(255)),
                    Column("category_id", BIGINT, server_default=text("1")),
                    Column("status", String(20), server_default=text("'PUBLISHED'")),
                    Column("type", String(20), server_default=text("'POST'")), created(),
                    Column("modified", DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")), UniqueConstraint("slug", name="uk_slug")),
    "t_tag": Table("t_tag", metadata, ident(), Column("name", String(50), nullable=False),
                   Column("slug", String(50), nullable=False), UniqueConstraint("name", name="uk_name"), UniqueConstraint("slug", name="uk_slug")),
    "t_post_tag": Table("t_post_tag", metadata, Column("post_id", BIGINT, primary_key=True),
                        Column("tag_id", BIGINT, primary_key=True)),
    "t_comment": Table("t_comment", metadata, ident(), Column("post_id", BIGINT, nullable=False),
                       Column("parent_id", BIGINT), Column("author", String(50), nullable=False),
                       Column("email", String(100), nullable=False), Column("url", String(200)),
                       Column("ip", String(50)), Column("user_agent", String(500)), Column("content", TEXT, nullable=False),
                       Column("status", String(20), server_default=text("'APPROVED'")),
                       Column("is_admin", TINYINT(1), server_default=text("0")), created(), Index("idx_post_id", "post_id"), Index("idx_parent_id", "parent_id")),
    "t_option": Table("t_option", metadata, Column("option_key", String(50), primary_key=True), Column("option_value", LONGTEXT)),
    "t_link": Table("t_link", metadata, ident(), Column("name", String(50), nullable=False),
                    Column("url", String(1024), nullable=False), Column("logo", String(1024)),
                    Column("description", String(1024)), Column("team", String(50), server_default=text("'Friends'")),
                    Column("sort", INTEGER, server_default=text("0")), created()),
}

for name, table in tables.items():
    table.dialect_options["mysql"]["engine"] = "INNODB"
    table.dialect_options["mysql"]["charset"] = "utf8mb4"
    table.dialect_options["mysql"]["collate"] = "utf8mb4_general_ci"
    class_name = {"t_post_tag": "PostTag", "t_option": "Option"}.get(name, name[2:].capitalize())
    model = type(class_name, (), {})
    mapper_registry.map_imperatively(model, table)
    globals()[class_name] = model

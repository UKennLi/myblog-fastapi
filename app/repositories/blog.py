"""Parameterized SQL equivalents of the original seven MyBatis mappers."""
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import text
from app.core.security import active_url


class BlogRepository:
    def __init__(self, session, settings):
        self.db, self.settings = session, settings

    def execute(self, sql, **parameters):
        return self.db.execute(text(sql), parameters)

    def rows(self, sql, **parameters):
        return [dict(row) for row in self.execute(sql, **parameters).mappings()]

    def one(self, sql, **parameters):
        row = self.execute(sql, **parameters).mappings().first()
        return dict(row) if row is not None else None

    def display_date(self, value):
        if value is None:
            return None
        return value.replace(tzinfo=ZoneInfo(self.settings.db_timezone)).astimezone(ZoneInfo(self.settings.display_timezone)).replace(tzinfo=None)

    def post_view(self, row, include_category=True, include_tags=True):
        if row is None:
            return None
        row = dict(row)
        row["categoryId"] = row.get("category_id")
        row["created"] = self.display_date(row.get("created"))
        row["category"] = self.category_by_id(row["categoryId"]) if include_category and row["categoryId"] is not None else None
        row["tags"] = self.tags_for_post(row["id"]) if include_tags else []
        row["tagsStr"] = ", ".join(tag["name"] for tag in row["tags"]) if include_tags else None
        return row

    def category_by_id(self, id):
        return self.one("SELECT * FROM t_category WHERE id=:id", id=id)

    def categories(self, counts=False):
        return self.rows("SELECT c.*, COUNT(p.id) AS count FROM t_category c LEFT JOIN t_post p ON c.id=p.category_id GROUP BY c.id" if counts else "SELECT * FROM t_category")

    def category_by_slug(self, slug):
        return self.one("SELECT * FROM t_category WHERE slug=:slug", slug=slug)

    def save_category(self, category):
        if category.get("id") is not None:
            return self.execute("UPDATE t_category SET name=:name,slug=:slug WHERE id=:id", **category)
        return self.execute("INSERT INTO t_category(name,slug) VALUES(:name,:slug)", **category).lastrowid

    def delete_category(self, id):
        self.execute("DELETE FROM t_category WHERE id=:id", id=id)

    def tags(self):
        return self.rows("SELECT t.*,COUNT(pt.post_id) AS count FROM t_tag t LEFT JOIN t_post_tag pt ON t.id=pt.tag_id GROUP BY t.id")

    def tag_by_slug(self, slug):
        return self.one("SELECT * FROM t_tag WHERE slug=:slug", slug=slug)

    def tags_for_post(self, id):
        return self.rows("SELECT t.* FROM t_tag t INNER JOIN t_post_tag pt ON t.id=pt.tag_id WHERE pt.post_id=:id", id=id)

    def published_count(self):
        return self.execute("SELECT COUNT(*) FROM t_post WHERE type='POST' AND status='PUBLISHED'").scalar_one()

    def post_by_id(self, id):
        # findById does NOT load category in the original mapper.
        return self.post_view(self.one("SELECT * FROM t_post WHERE id=:id", id=id), include_category=False)

    def post_by_slug(self, slug):
        return self.post_view(self.one("SELECT * FROM t_post WHERE slug=:slug AND type='POST' AND status='PUBLISHED'", slug=slug))

    def page_by_slug(self, slug):
        return self.post_view(self.one("SELECT * FROM t_post WHERE slug=:slug AND type='PAGE'", slug=slug), False, False)

    def all_pages(self):
        return [self.post_view(row, False, False) for row in self.rows("SELECT * FROM t_post WHERE type='PAGE' ORDER BY created DESC")]

    def post_query(self, kind="published", value=None):
        parameters = {}
        if kind in ("published", "drafts", "archives"):
            status = "DRAFT" if kind == "drafts" else "PUBLISHED"
            columns = "id,title,slug,created,thumbnail" if kind == "archives" else "*"
            sql = f"SELECT {columns} FROM t_post WHERE type='POST' AND status=:status"
            parameters["status"] = status
        elif kind == "category":
            sql = "SELECT p.* FROM t_post p INNER JOIN t_category c ON p.category_id=c.id WHERE c.slug=:value AND p.status='PUBLISHED' AND p.type='POST'"
            parameters["value"] = value
        elif kind == "tag":
            sql = "SELECT p.* FROM t_post p INNER JOIN t_post_tag pt ON p.id=pt.post_id INNER JOIN t_tag t ON pt.tag_id=t.id WHERE t.slug=:value AND p.status='PUBLISHED' AND p.type='POST'"
            parameters["value"] = value
        elif kind == "search":
            sql = "SELECT * FROM t_post WHERE status='PUBLISHED' AND type='POST' AND (title LIKE CONCAT('%',:value,'%') OR content LIKE CONCAT('%',:value,'%'))"
            parameters["value"] = value
        else:
            raise ValueError("Unknown query kind")
        return sql + " ORDER BY created DESC", parameters

    def page_posts(self, kind, page, size, value=None):
        sql, parameters = self.post_query(kind, value)
        total = self.execute("SELECT COUNT(*) FROM (" + sql.rsplit(" ORDER BY", 1)[0] + ") source", **parameters).scalar_one()
        offset = max(0, (page - 1) * size)
        if page <= 0 or size <= 0:
            rows = []
        elif size > 0:
            rows = self.rows(sql + " LIMIT :limit OFFSET :offset", **parameters, limit=size, offset=offset)
        else:
            rows = self.rows(sql, **parameters)
        posts = self.post_list_views(rows, relationships=kind != "archives")
        return posts, total

    def post_list_views(self, rows, relationships=True):
        posts = [self.post_view(row, False, False) for row in rows]
        if not posts or not relationships:
            return posts
        parameters = {f"id{i}": post["id"] for i, post in enumerate(posts)}
        placeholders = ",".join(":" + key for key in parameters)
        tag_rows = self.rows("SELECT pt.post_id,t.* FROM t_post_tag pt INNER JOIN t_tag t ON pt.tag_id=t.id WHERE pt.post_id IN (" + placeholders + ")", **parameters)
        by_id = {post["id"]: post for post in posts}
        for tag in tag_rows:
            post_id = tag.pop("post_id")
            by_id[post_id]["tags"].append(tag)
        category_ids = set(post["categoryId"] for post in posts if post["categoryId"] is not None)
        category_map = {}
        if category_ids:
            params = {f"cat{i}": id for i, id in enumerate(sorted(category_ids))}
            category_map = {row["id"]: row for row in self.rows("SELECT * FROM t_category WHERE id IN (" + ",".join(":" + key for key in params) + ")", **params)}
        for post in posts:
            post["category"] = category_map.get(post["categoryId"])
            post["tagsStr"] = ", ".join(tag["name"] for tag in post["tags"])
        return posts

    def save_post(self, data):
        if data["id"] is None:
            result = self.execute("INSERT INTO t_post(title,slug,content,summary,thumbnail,category_id,status,type,created,modified) VALUES(:title,:slug,:content,:summary,:thumbnail,:categoryId,:status,:type,NOW(),NOW())", **data)
            return result.lastrowid
        self.execute("UPDATE t_post SET title=:title,slug=:slug,content=:content,summary=:summary,thumbnail=:thumbnail,category_id=:categoryId,status=:status,modified=NOW() WHERE id=:id", **data)
        return data["id"]

    def clear_post_tags(self, id):
        self.execute("DELETE FROM t_post_tag WHERE post_id=:id", id=id)

    def move_to_draft(self, id):
        self.execute("UPDATE t_post SET status='DRAFT' WHERE id=:id", id=id)

    def delete_post(self, id):
        self.clear_post_tags(id)
        self.execute("DELETE FROM t_post WHERE id=:id", id=id)

    def user_by_username(self, username):
        return self.one("SELECT * FROM t_user WHERE username=:username", username=username)

    def user_by_id(self, id):
        return self.one("SELECT * FROM t_user WHERE id=:id", id=id)

    def update_user(self, user):
        self.execute("UPDATE t_user SET username=:username,nickname=:nickname,email=:email,avatar=:avatar WHERE id=:id", **user)

    def update_password(self, id, password):
        self.execute("UPDATE t_user SET password=:password WHERE id=:id", id=id, password=password)

    def options(self):
        return {row["option_key"]: row["option_value"] for row in self.rows("SELECT * FROM t_option")}

    def option_value(self, key):
        row = self.one("SELECT option_value FROM t_option WHERE option_key=:key", key=key)
        return row["option_value"] if row else None

    def save_options(self, options):
        for key, value in options.items():
            self.execute("INSERT INTO t_option(option_key,option_value) VALUES(:key,:value) ON DUPLICATE KEY UPDATE option_value=:value", key=key, value=value)

    def links(self):
        return self.rows("SELECT * FROM t_link ORDER BY sort DESC,id ASC")

    def link_by_id(self, id):
        return self.one("SELECT * FROM t_link WHERE id=:id", id=id)

    def link_groups(self):
        groups = self.rows("SELECT team FROM t_link GROUP BY team ORDER BY MAX(sort) DESC")
        return {row["team"]: self.rows("SELECT * FROM t_link WHERE team=:team ORDER BY sort DESC,id ASC", team=row["team"]) for row in groups}

    def save_link(self, data):
        if data["id"] is None:
            return self.execute("INSERT INTO t_link(name,url,logo,description,team,sort,created) VALUES(:name,:url,:logo,:description,:team,:sort,NOW())", **data).lastrowid
        self.execute("UPDATE t_link SET name=:name,url=:url,logo=:logo,description=:description,team=:team,sort=:sort WHERE id=:id", **data)
        return data["id"]

    def delete_link(self, id):
        self.execute("DELETE FROM t_link WHERE id=:id", id=id)

    def comment_view(self, row):
        row = dict(row)
        if active_url(row.get("url")):
            row["url"] = ""
        row.update(postId=row["post_id"], parentId=row["parent_id"], isAdmin=bool(row["is_admin"]),
                   created=self.display_date(row["created"]), parent=None, children=[], post=None)
        email = row.get("email")
        row["gravatarMd5"] = hashlib.md5(email.lower().strip("".join(chr(i) for i in range(33))).encode(), usedforsecurity=False).hexdigest() if email else ""
        return row

    def comments_for_post(self, id):
        return [self.comment_view(row) for row in self.rows("SELECT * FROM t_comment WHERE post_id=:id AND status='APPROVED' ORDER BY created ASC", id=id)]

    def comment_by_id(self, id):
        row = self.one("SELECT * FROM t_comment WHERE id=:id", id=id)
        return self.comment_view(row) if row else None

    def admin_comments(self):
        rows = self.rows("SELECT c.*,p.id AS joined_post_id,p.title AS post_title,p.slug AS post_slug,p.type AS post_type FROM t_comment c LEFT JOIN t_post p ON c.post_id=p.id ORDER BY c.created DESC")
        results = []
        for row in rows:
            comment = self.comment_view(row)
            comment["postId"] = row["joined_post_id"]
            if row["joined_post_id"] is not None:
                comment["post"] = dict(id=row["joined_post_id"], title=row["post_title"], slug=row["post_slug"], type=row["post_type"])
            results.append(comment)
        return results

    def insert_comment(self, data):
        return self.execute("INSERT INTO t_comment(post_id,parent_id,author,email,url,ip,user_agent,content,status,is_admin,created) VALUES(:postId,:parentId,:author,:email,:url,:ip,:userAgent,:content,:status,:isAdmin,NOW())", **data).lastrowid

    def delete_comment(self, id):
        self.execute("DELETE FROM t_comment WHERE id=:id", id=id)

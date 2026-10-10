from fastapi import HTTPException
from app.core.security import active_url


def comment_tree(comments):
    indexed = {comment["id"]: comment for comment in comments}
    roots = []
    for comment in comments:
        parent_id = comment["parentId"]
        if parent_id is not None and parent_id > 0:
            parent = indexed.get(parent_id)
            if parent is not None:
                comment["parent"] = parent
                parent["children"].append(comment)
        else:
            roots.append(comment)
    return roots


def submit_comment(repo, form, request):
    data = form.model_dump()
    if data["isAdmin"]:
        raise HTTPException(403, "Visitor comments cannot claim administrator identity")
    if active_url(data["url"]):
        raise HTTPException(403, "Active content URLs are not allowed in visitor comments")
    data["status"] = data["status"] if data["status"] is not None else "APPROVED"
    data["isAdmin"] = False
    data["ip"] = request.client.host if request.client else None
    data["userAgent"] = request.headers.get("user-agent")
    id = repo.insert_comment(data)
    repo.db.commit()
    return id

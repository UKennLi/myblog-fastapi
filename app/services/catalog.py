def save_link(repo, form):
    data = form.model_dump()
    if data["id"] is None:
        if data["sort"] is None:
            data["sort"] = 0
        if data["team"] is None or data["team"] == "":
            data["team"] = "Friends"
    id = repo.save_link(data)
    repo.db.commit()
    return id


def save_category(repo, data):
    id = repo.save_category(data)
    repo.db.commit()
    return id

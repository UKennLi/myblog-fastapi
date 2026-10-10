from fastapi import HTTPException
from app.core.security import encode_password, verify_password


def require_own_id(request, id):
    if id != request.state.session["user_id"]:
        raise HTTPException(403, "Cannot modify another user's account")


def save_profile(repo, form, request):
    require_own_id(request, form.id)
    repo.update_user(form.model_dump())
    repo.db.commit()


def change_password(repo, request, id, old, new):
    require_own_id(request, id)
    user = repo.user_by_id(id)
    if not verify_password(old, user["password"]):
        return False
    repo.update_password(id, encode_password(new))
    repo.db.commit()
    return True

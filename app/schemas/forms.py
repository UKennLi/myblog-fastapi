from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from app.core.exceptions import BindingError


class BoundForm(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("id", "categoryId", "postId", "parentId", "sort", check_fields=False, mode="before")
    @classmethod
    def empty_numbers(cls, value):
        return None if value == "" else value

    @classmethod
    def bind(cls, data):
        try:
            return cls.model_validate(dict(data))
        except ValidationError as error:
            raise BindingError("Invalid form parameter") from error


class PostForm(BoundForm):
    id: int | None = None
    title: str | None = None
    slug: str | None = None
    content: str | None = None
    summary: str | None = None
    thumbnail: str | None = None
    categoryId: int | None = None
    status: str | None = None
    type: str | None = None
    tagsStr: str | None = None


class LinkForm(BoundForm):
    id: int | None = None
    name: str | None = None
    url: str | None = None
    logo: str | None = None
    description: str | None = None
    team: str | None = None
    sort: int | None = None


class CommentForm(BoundForm):
    postId: int | None = None
    parentId: int | None = None
    author: str | None = None
    email: str | None = None
    url: str | None = None
    content: str | None = None
    status: str | None = None
    isAdmin: bool | None = None


class UserForm(BoundForm):
    id: int | None = None
    username: str | None = None
    nickname: str | None = None
    email: str | None = None
    avatar: str | None = None

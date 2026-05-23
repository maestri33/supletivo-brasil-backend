"""Schemas para UserRole."""

from app.schemas import CustomModel


class UserRolesResponse(CustomModel):
    external_id: str
    roles: list[str]


class UserSummary(CustomModel):
    external_id: str
    roles: list[str]


class UsersListResponse(CustomModel):
    total: int
    users: list[UserSummary]

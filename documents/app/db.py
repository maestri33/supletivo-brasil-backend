from tortoise.contrib.fastapi import register_tortoise
from app.config import settings


def init_orm(app):
    register_tortoise(
        app,
        db_url=settings.database_url,
        modules={
            "models": [
                "app.models.document",
                "app.models.rg",
                "app.models.cnh",
                "app.models.carteira_trabalho",
                "app.models.passaporte",
            ]
        },
        generate_schemas=True,
        add_exception_handlers=True,
    )

from pydantic import BaseModel


class CustomModel(BaseModel):
    model_config = {"from_attributes": True}

from pydantic import BaseModel, Field


class AdminLoginModel(BaseModel):
    email: str = Field(...)
    password: str = Field(...)

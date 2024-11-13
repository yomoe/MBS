from typing import Optional

from pydantic import BaseModel


class UserInfo(BaseModel):
    user_id: int
    username: Optional[str] = None
    lastname: Optional[str] = None
    firstname: Optional[str] = None
    age_verified: bool = False
    language_code: str = 'en'
    is_bot: bool = False


class UserResponse(BaseModel):
    user_id: int
    username: Optional[str] = None
    lastname: Optional[str] = None
    firstname: Optional[str] = None
    # Добавьте другие поля по необходимости


# Модель ответа для валидации
class APIUserResponse(BaseModel):
    status: str
    message: str
    data: Optional[UserResponse] = None
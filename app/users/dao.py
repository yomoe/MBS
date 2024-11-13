from app.dao.base import BaseDAO
from app.models import User, UserLinks


class UserDAO(BaseDAO):
    model = User


class UserLinksDAO(BaseDAO):
    model = UserLinks

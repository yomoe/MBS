# app/models/__init__.py

from app.database import Base

# Импортируйте все модели, чтобы они были зарегистрированы в Base.metadata
from app.models.users import User
from app.models.links import LinksTable
from app.models.files import FilesTable
from app.models.userlinks import UserLinks

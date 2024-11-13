from app.dao.base import BaseDAO
from app.models import FilesTable, LinksTable


class LinksDAO(BaseDAO):
    model = LinksTable


class FilesDAO(BaseDAO):
    model = FilesTable

import logging

from sqlalchemy import insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BaseDAO:
    model = None

    @classmethod
    async def find_one_or_none(cls, session: AsyncSession, **filter_by):
        query = select(cls.model).filter_by(**filter_by)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @classmethod
    async def add(cls, session: AsyncSession, **data):
        try:
            query = insert(cls.model).values(**data).returning(cls.model)
            result = await session.execute(query)
            await session.commit()
            return result.scalar_one()
        except SQLAlchemyError as e:
            logger.error(
                "Database Error: Cannot insert data into table",
                extra={"table": cls.model.__tablename__}, exc_info=True)
            raise

    @classmethod
    async def update(cls, session: AsyncSession, filter_by: dict, **data):
        try:
            query = (
                update(cls.model)
                .filter_by(**filter_by)
                .values(**data)
                .returning(cls.model)
            )
            result = await session.execute(query)
            await session.commit()
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error("Database Error: Cannot update data", exc_info=True)
            raise

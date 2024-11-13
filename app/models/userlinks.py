from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.database import Base


class UserLinks(Base):
    __tablename__ = 'user_links'
    user_id = Column(
        BigInteger,
        ForeignKey('users.user_id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        index=True
    )
    link_id = Column(
        BigInteger,
        ForeignKey('links_table.link_id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        index=True
    )
    request_date = Column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False
    )

    # Дополнительные индексы
    __table_args__ = (
        Index('ix_user_links_user_id', 'user_id'),
        Index('ix_user_links_link_id', 'link_id'),
    )

from sqlalchemy import BigInteger, Boolean, Column, DateTime, func, String
from sqlalchemy.orm import relationship

from app.database import Base


class LinksTable(Base):
    __tablename__ = 'links_table'

    link_id = Column(BigInteger, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, nullable=False, index=True)
    caption = Column(String, nullable=True)
    subreddit = Column(String, nullable=True)
    nsfw_flag = Column(Boolean, default=False, nullable=False)
    date_added = Column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False
    )

    # Связь с FilesTable
    files = relationship('FilesTable', backref='link', cascade='all, delete-orphan')
    # Связь с UserLinks
    user_links = relationship('UserLinks', backref='link', cascade='all, delete-orphan')

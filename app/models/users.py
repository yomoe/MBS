from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = 'users'

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, index=True, nullable=True)
    lastname = Column(String, nullable=True)
    firstname = Column(String, nullable=True)
    age_verified = Column(Boolean, default=False)
    links_requested = Column(Integer, default=0)
    language_code = Column(String, default='en')
    is_premium = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    is_bot = Column(Boolean, default=False)
    joined_date = Column(DateTime(timezone=True), server_default=func.current_timestamp())
    last_active = Column(DateTime(timezone=True), onupdate=func.current_timestamp())

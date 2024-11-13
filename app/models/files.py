from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, func, Index, String, UniqueConstraint

from app.database import Base


class FilesTable(Base):
    __tablename__ = 'files_table'

    link_id = Column(
        BigInteger,
        ForeignKey('links_table.link_id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        index=True
    )
    file_id = Column(String, primary_key=True, nullable=False)
    file_order = Column(BigInteger, nullable=False)
    file_type = Column(String, nullable=True)
    file_size = Column(BigInteger, nullable=True)
    date_added = Column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint('link_id', 'file_order', name='_link_id_file_order_uc'),
        Index('ix_files_table_link_id', 'link_id'),
    )

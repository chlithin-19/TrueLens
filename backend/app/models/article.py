import uuid
from sqlalchemy import Column, String, Text, DateTime, func, ForeignKey
from app.db.session import Base

class Article(Base):
    __tablename__ = "articles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(256), nullable=True)
    publication = Column(String(256), nullable=True)
    published_date = Column(String(128), nullable=True)
    url = Column(String(2048), nullable=True)
    filename = Column(String(512), nullable=True)
    
    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, JSON, DateTime, func, ForeignKey
from app.db.session import Base

from sqlalchemy.orm import relationship

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    url = Column(String(2048), nullable=True)
    filename = Column(String(512), nullable=True)
    
    title = Column(String(512), nullable=False)
    author = Column(String(256), nullable=False)
    publication = Column(String(256), nullable=False)
    published_date = Column(String(128), nullable=False)
    
    trust_score = Column(Integer, nullable=False)
    bias_rating = Column(String(64), nullable=False)
    sentiment_tone = Column(String(64), nullable=False)
    sentiment_score = Column(Float, nullable=False)
    
    is_clickbait = Column(Boolean, default=False)
    is_sensational = Column(Boolean, default=False)
    is_verified_author = Column(Boolean, default=False)
    
    emotion = Column(String(64), nullable=True)
    propaganda_score = Column(Integer, nullable=True)
    propaganda_techniques = Column(JSON, nullable=True)
    missing_perspectives = Column(JSON, nullable=True)
    embedding_id = Column(String(36), nullable=True)

    summary = Column(Text, nullable=False)
    claims = Column(JSON, nullable=False)  # Stores fact check claims list
    
    is_bookmarked = Column(Boolean, default=False)
    
    user_id = Column(String(128), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    article_id = Column(String(36), ForeignKey("articles.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    article = relationship("Article", lazy="selectin")

    @property
    def content(self) -> str:
        return self.article.content if self.article else None



from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl

class ClaimVerify(BaseModel):
    claim: str
    status: str
    details: str

class AnalysisCreate(BaseModel):
    url: Optional[str] = None

class SimilarArticle(BaseModel):
    id: str
    title: str
    author: Optional[str] = "Unknown"
    publication: Optional[str] = "Unknown"
    url: Optional[str] = None
    distance: Optional[float] = None

class AnalysisResponse(BaseModel):
    id: str
    url: Optional[str] = None
    filename: Optional[str] = None
    title: str
    author: str
    publication: str
    published_date: str
    trust_score: int
    bias_rating: str
    sentiment_tone: str
    sentiment_score: float
    is_clickbait: bool
    is_sensational: bool
    is_verified_author: bool
    summary: str
    content: Optional[str] = None
    claims: List[ClaimVerify]
    emotion: Optional[str] = "Neutral"
    propaganda_score: Optional[int] = 0
    propaganda_techniques: Optional[List[str]] = []
    missing_perspectives: Optional[List[str]] = []
    embedding_id: Optional[str] = None
    similar_articles: Optional[List[SimilarArticle]] = []
    created_at: datetime

    class Config:
        from_attributes = True

class DashboardStats(BaseModel):
    total_analyzed: int
    verified_facts: int
    avg_trust_score: int
    saved_reports: int

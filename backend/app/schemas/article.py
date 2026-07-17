from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ArticleBase(BaseModel):
    title: str
    content: str
    author: Optional[str] = None
    publication: Optional[str] = None
    published_date: Optional[str] = None
    url: Optional[str] = None
    filename: Optional[str] = None

class ArticleCreate(ArticleBase):
    pass

class ArticleResponse(ArticleBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

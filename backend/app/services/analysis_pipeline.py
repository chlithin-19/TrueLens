import logging
import asyncio
from dataclasses import dataclass
from typing import List, Optional

from app.services.nlp_preprocessor import NLPPreprocessor
from app.services.sentiment_service import SentimentAnalyzer
from app.services.gemini_analyzer import GeminiAnalyzer
from app.services.embedding_service import EmbeddingService
from app.services.fact_check_service import FactCheckService

logger = logging.getLogger("truelens.pipeline")

@dataclass
class AnalysisResult:
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
    claims: list
    emotion: str
    propaganda_score: int
    propaganda_techniques: list
    missing_perspectives: list
    embedding_id: Optional[str] = None

class AnalysisPipeline:
    def __init__(self, 
                 nlp: NLPPreprocessor, 
                 sentiment: SentimentAnalyzer, 
                 gemini: GeminiAnalyzer, 
                 embedding: EmbeddingService,
                 factcheck: FactCheckService = None):
        self.nlp = nlp
        self.sentiment = sentiment
        self.gemini = gemini
        self.embedding = embedding
        self.factcheck = factcheck

    async def analyze(self, article_data: dict, article_id: str) -> AnalysisResult:
        title = article_data.get("title", "")
        content = article_data.get("content", "")
        author = article_data.get("author", "Unknown")
        publication = article_data.get("publication", "Unknown")
        published_date = article_data.get("published_date", "Unknown")

        # 1. NLP Preprocessing (extract sentences for sentiment)
        sentences = self.nlp.extract_sentences(content)
        
        # 2. Sentiment Analysis
        sentiment_result = self.sentiment.analyze(sentences)
        
        # 3. Gemini Structured Analysis
        gemini_result = await self.gemini.analyze(title, content)
        
        # 4. Generate Embedding and Store in ChromaDB
        metadata = {
            "title": title,
            "author": author,
            "publication": publication,
            "url": article_data.get("url", "")
        }
        
        embedding_id = None
        try:
            embedding_id = self.embedding.store_article(article_id, content, metadata)
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")

        # 5. Fact Check claims
        claims = []
        if "claims" in gemini_result:
            for c in gemini_result["claims"]:
                if isinstance(c, dict):
                    claim_text = c.get("claim", "")
                    status = c.get("status", "Unverified")
                    details = c.get("details", "")
                    
                    if self.factcheck and claim_text:
                        fc_result = await self.factcheck.verify_claim(claim_text)
                        if fc_result["status"] != "Unverified":
                            status = fc_result["status"]
                            details = fc_result["details"]

                    claims.append({
                        "claim": claim_text,
                        "status": status,
                        "details": details
                    })

        # Combine results
        return AnalysisResult(
            title=title,
            author=author,
            publication=publication,
            published_date=published_date,
            trust_score=gemini_result.get("trust_score", 50),
            bias_rating=gemini_result.get("bias_rating", "Center"),
            sentiment_tone=sentiment_result.get("sentiment_tone", "Neutral"),
            sentiment_score=sentiment_result.get("sentiment_score", 0.0),
            is_clickbait=gemini_result.get("is_clickbait", False),
            is_sensational=gemini_result.get("is_sensational", False),
            is_verified_author=bool(author and author != "Unknown" and author != "Staff Reporter" and author != "Staff Writer"),
            summary=gemini_result.get("neutral_summary", content[:300] + "..."),
            claims=claims,
            emotion=gemini_result.get("emotion", "Neutral"),
            propaganda_score=gemini_result.get("propaganda_score", 0),
            propaganda_techniques=gemini_result.get("propaganda_techniques", []),
            missing_perspectives=gemini_result.get("missing_perspectives", []),
            embedding_id=embedding_id
        )

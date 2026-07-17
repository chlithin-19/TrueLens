from .nlp_preprocessor import NLPPreprocessor
from .sentiment_service import SentimentAnalyzer
from .gemini_analyzer import GeminiAnalyzer
from .embedding_service import EmbeddingService
from .fact_check_service import FactCheckService
from .analysis_pipeline import AnalysisPipeline

# Singletons
nlp_preprocessor = NLPPreprocessor()
sentiment_analyzer = SentimentAnalyzer()
gemini_analyzer = GeminiAnalyzer()
embedding_service = EmbeddingService()
fact_check_service = FactCheckService()

analysis_pipeline = AnalysisPipeline(
    nlp=nlp_preprocessor,
    sentiment=sentiment_analyzer,
    gemini=gemini_analyzer,
    embedding=embedding_service,
    factcheck=fact_check_service
)

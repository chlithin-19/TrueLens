import logging
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.core.config import settings

logger = logging.getLogger("truelens.gemini")

class ClaimVerify(BaseModel):
    claim: str = Field(description="The claim extracted from the article.")
    status: str = Field(description="Verification status: 'Verified', 'Misleading Context', 'Unverified', or 'False'.")
    details: str = Field(description="Details explaining the verification status.")

class AnalysisResultSchema(BaseModel):
    bias_rating: str = Field(description="Political bias: 'Left', 'Lean Left', 'Center', 'Lean Right', or 'Right'.")
    bias_explanation: str = Field(description="Brief explanation of why this bias rating was given.")
    is_clickbait: bool = Field(description="True if the title or content uses clickbait tactics.")
    is_sensational: bool = Field(description="True if the content is highly sensationalized.")
    propaganda_score: int = Field(description="Propaganda intensity score from 0 to 100.")
    propaganda_techniques: List[str] = Field(description="List of propaganda techniques identified (e.g., 'Appeal to Fear', 'Loaded Language').")
    missing_perspectives: List[str] = Field(description="List of viewpoints not represented in the article.")
    neutral_summary: str = Field(description="A balanced, fact-focused rewrite of the article summary.")
    claims: List[ClaimVerify] = Field(description="List of claims extracted and verified.")
    emotion: str = Field(description="Dominant emotion (e.g., 'Fear', 'Anger', 'Hope', 'Neutral').")
    trust_score: int = Field(description="Composite credibility rating from 0 to 100.")

class GeminiAnalyzer:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
            temperature=0.2,
            max_retries=3,
        )
        self.parser = JsonOutputParser(pydantic_object=AnalysisResultSchema)
        self.prompt = PromptTemplate(
            template="You are an expert AI journalist and fact-checker analyzing a news article.\n"
                     "Analyze the provided title and content according to the requested JSON format.\n\n"
                     "Title: {title}\n"
                     "Content: {content}\n\n"
                     "{format_instructions}\n",
            input_variables=["title", "content"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        self.chain = self.prompt | self.llm | self.parser

    async def analyze(self, title: str, content: str) -> dict:
        try:
            # We truncate content if it's too long to avoid token limits, though gemini-2.0-flash has a huge context
            # We'll limit to first ~30,000 characters just to be safe and fast.
            truncated_content = content[:30000]
            
            result = await self.chain.ainvoke({"title": title, "content": truncated_content})
            return result
        except Exception as e:
            logger.error(f"Gemini analysis failed: {e}")
            # Fallback to defaults
            return {
                "bias_rating": "Center",
                "bias_explanation": "Failed to analyze.",
                "is_clickbait": False,
                "is_sensational": False,
                "propaganda_score": 0,
                "propaganda_techniques": [],
                "missing_perspectives": [],
                "neutral_summary": "Analysis failed. Could not generate summary.",
                "claims": [],
                "emotion": "Neutral",
                "trust_score": 50
            }

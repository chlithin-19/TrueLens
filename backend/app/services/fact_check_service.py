import logging
import httpx
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger("truelens.factcheck")

class FactCheckService:
    def __init__(self):
        self.api_key = settings.GOOGLE_FACT_CHECK_API_KEY
        self.base_url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        self.client = httpx.AsyncClient()

    async def verify_claim(self, claim_text: str) -> Dict[str, Any]:
        """
        Queries the Google Fact Check API with the given claim text.
        Returns a dictionary with standard status and details.
        """
        if not self.api_key:
            logger.warning("Google Fact Check API key is missing. Returning Unverified.")
            return {
                "status": "Unverified",
                "details": "Fact-checking service is not configured."
            }

        try:
            response = await self.client.get(
                self.base_url,
                params={
                    "query": claim_text,
                    "key": self.api_key,
                    "languageCode": "en"
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            claims = data.get("claims", [])
            if not claims:
                return {
                    "status": "Unverified",
                    "details": "No relevant fact-check results found for this claim."
                }
                
            # Take the first most relevant claim
            top_claim = claims[0]
            claim_review = top_claim.get("claimReview", [])
            if not claim_review:
                return {
                    "status": "Unverified",
                    "details": "A related claim was found, but no rating was provided."
                }
                
            # Use the first review
            review = claim_review[0]
            textual_rating = review.get("textualRating", "").lower()
            publisher = review.get("publisher", {}).get("name", "Unknown Fact Checker")
            
            # Categorize the rating
            status = "Unverified"
            if any(word in textual_rating for word in ["false", "pants on fire", "mostly false", "incorrect"]):
                status = "False"
            elif any(word in textual_rating for word in ["true", "correct", "mostly true", "verified"]):
                status = "Verified"
            else:
                status = "Unverified" # E.g., half true, mixture, etc.

            details = f"Rated '{review.get('textualRating', 'Unknown')}' by {publisher}."
            
            return {
                "status": status,
                "details": details
            }

        except Exception as e:
            logger.error(f"Error querying Fact Check API: {e}")
            return {
                "status": "Unverified",
                "details": "Error occurred while contacting fact-checking services."
            }

    async def close(self):
        await self.client.aclose()

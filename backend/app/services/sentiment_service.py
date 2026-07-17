from nltk.sentiment.vader import SentimentIntensityAnalyzer
import numpy as np

class SentimentAnalyzer:
    def __init__(self):
        self.analyzer = None

    def _ensure_analyzer(self):
        if not self.analyzer:
            self.analyzer = SentimentIntensityAnalyzer()

    def analyze(self, sentences: list) -> dict:
        self._ensure_analyzer()
        if not sentences:
            return {"sentiment_tone": "Neutral", "sentiment_score": 0.0}

        scores = []
        for sentence in sentences:
            score = self.analyzer.polarity_scores(sentence)
            scores.append(score['compound'])

        avg_score = np.mean(scores)
        std_score = np.std(scores)

        # Determine tone based on mean and standard deviation
        if std_score > 0.5 and abs(avg_score) < 0.3:
            tone = "Mixed"
        elif avg_score >= 0.5:
            tone = "Optimistic" if avg_score > 0.7 else "Positive"
        elif avg_score <= -0.5:
            tone = "Critical" if avg_score < -0.7 else "Negative"
        elif 0.1 <= avg_score < 0.5:
            tone = "Cautious"
        elif -0.5 < avg_score <= -0.1:
            tone = "Skeptical"
        else:
            tone = "Neutral"

        return {
            "sentiment_tone": tone,
            "sentiment_score": round(float(avg_score), 2)
        }

import spacy
import nltk
import logging
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger("truelens.nlp")

class NLPPreprocessor:
    def __init__(self):
        self.nlp = None
        self._ensure_models_loaded()

    def _ensure_models_loaded(self):
        # Load spaCy model
        try:
            if not self.nlp:
                self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.warning("spaCy en_core_web_sm not found. Downloading...")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Download NLTK data
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon', quiet=True)
            
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)
            
        try:
            nltk.data.find('taggers/averaged_perceptron_tagger_eng')
        except LookupError:
            nltk.download('averaged_perceptron_tagger_eng', quiet=True)

    def preprocess(self, text: str) -> str:
        if not text:
            return ""
        doc = self.nlp(text)
        tokens = [token.lemma_.lower() for token in doc if not token.is_stop and not token.is_punct and token.is_alpha]
        return " ".join(tokens)

    def extract_entities(self, text: str) -> dict:
        if not text:
            return {}
        doc = self.nlp(text)
        entities = {}
        for ent in doc.ents:
            if ent.label_ not in entities:
                entities[ent.label_] = set()
            entities[ent.label_].add(ent.text)
        return {k: list(v) for k, v in entities.items()}

    def extract_sentences(self, text: str) -> list:
        if not text:
            return []
        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    def extract_keywords(self, text: str, top_n: int = 10) -> list:
        if not text:
            return []
        sentences = self.extract_sentences(text)
        if not sentences:
            return []
            
        try:
            vectorizer = TfidfVectorizer(stop_words='english', max_features=top_n)
            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            scores = tfidf_matrix.sum(axis=0).A1
            
            keywords = []
            for i in scores.argsort()[::-1][:top_n]:
                keywords.append(feature_names[i])
            return keywords
        except ValueError:
            return []

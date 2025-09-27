"""ML-based intent classification using Hugging Face models."""

from transformers import pipeline
from typing import Dict, Any, Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Types of query intents."""
    KPI = "kpi"
    ANALYTICAL = "analytical"
    UNKNOWN = "unknown"


class MLIntentClassifier:
    """Intent classifier using Hugging Face zero-shot classification."""

    def __init__(self, model_name: str = "facebook/bart-large-mnli"):
        """
        Initialize with a zero-shot classification model.

        Args:
            model_name: Hugging Face model for zero-shot classification
        """
        self.model_name = model_name
        self.classifier = None
        self.initialized = False

        # Define intent labels for zero-shot classification
        self.intent_labels = [
            "sales metrics query",
            "customer analytics query",
            "product inventory query",
            "order statistics query",
            "analytical why question",
            "trend analysis question",
            "general business question"
        ]

        # Map labels to intent types
        self.label_to_intent = {
            "sales metrics query": IntentType.KPI,
            "customer analytics query": IntentType.KPI,
            "product inventory query": IntentType.KPI,
            "order statistics query": IntentType.KPI,
            "analytical why question": IntentType.ANALYTICAL,
            "trend analysis question": IntentType.ANALYTICAL,
            "general business question": IntentType.UNKNOWN
        }

    def initialize(self):
        """Load the Hugging Face model."""
        try:
            logger.info(f"Loading Hugging Face model: {self.model_name}")
            self.classifier = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                device=-1  # Use CPU, set to 0 for GPU
            )
            self.initialized = True
            logger.info("ML Intent classifier initialized")
        except Exception as e:
            logger.error(f"Failed to load Hugging Face model: {e}")
            logger.info("Falling back to pattern-based classification")
            self.initialized = False

    def classify(self, question: str) -> Tuple[IntentType, float]:
        """
        Classify intent using zero-shot classification.

        Args:
            question: User's question

        Returns:
            Tuple of (IntentType, confidence_score)
        """
        if not self.initialized:
            # Fallback to simple keyword detection
            return self._simple_classify(question)

        try:
            # Run zero-shot classification
            result = self.classifier(
                question,
                candidate_labels=self.intent_labels,
                multi_label=False
            )

            # Get top prediction
            top_label = result['labels'][0]
            confidence = result['scores'][0]

            # Map to intent type
            intent_type = self.label_to_intent.get(
                top_label,
                IntentType.UNKNOWN
            )

            logger.info(f"ML Classification: {top_label} ({confidence:.2f}) -> {intent_type.value}")

            # If confidence is low, mark as unknown
            if confidence < 0.3:
                intent_type = IntentType.UNKNOWN

            return intent_type, confidence

        except Exception as e:
            logger.error(f"ML classification failed: {e}")
            return self._simple_classify(question)

    def _simple_classify(self, question: str) -> Tuple[IntentType, float]:
        """Simple keyword-based fallback classification."""
        question_lower = question.lower()

        # Analytical keywords
        analytical_keywords = ["why", "how", "explain", "analyze", "trend", "cause"]
        if any(keyword in question_lower for keyword in analytical_keywords):
            return IntentType.ANALYTICAL, 0.8

        # KPI keywords
        kpi_keywords = ["how many", "total", "count", "average", "top", "revenue", "sales"]
        if any(keyword in question_lower for keyword in kpi_keywords):
            return IntentType.KPI, 0.8

        return IntentType.UNKNOWN, 0.5


# Example usage for enhanced intent classification
class HybridIntentClassifier:
    """Combines ML and pattern-based classification for best results."""

    def __init__(self):
        self.ml_classifier = MLIntentClassifier()
        self.pattern_classifier = None  # Your existing pattern classifier

    def initialize(self):
        """Initialize both classifiers."""
        self.ml_classifier.initialize()

    def classify(self, question: str) -> Tuple[IntentType, Dict[str, Any]]:
        """
        Classify using both ML and patterns.

        Returns:
            Tuple of (IntentType, metadata)
        """
        # First try ML classification
        ml_intent, ml_confidence = self.ml_classifier.classify(question)

        # If high confidence ML result, use it
        if ml_confidence > 0.7:
            return ml_intent, {"method": "ml", "confidence": ml_confidence}

        # Otherwise fall back to patterns
        # This would call your existing pattern classifier
        return ml_intent, {"method": "fallback", "confidence": ml_confidence}
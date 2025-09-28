"""Hybrid intent classifier combining rule-based and ML approaches."""

import logging
from typing import Dict, Any, Tuple

from app.services.intent_router import intent_router, Intent
from app.services.ml_intent_classifier import ml_intent_classifier

logger = logging.getLogger(__name__)


class HybridIntentClassifier:
    """
    Hybrid classifier that uses:
    1. Rule-based patterns for common queries (fast, accurate)
    2. ML model for ambiguous/complex queries (flexible)
    """

    def __init__(self):
        self.rule_classifier = intent_router
        self.ml_classifier = ml_intent_classifier

        # Confidence threshold for rule-based classification
        self.rule_confidence_threshold = 0.9

    async def classify(
        self,
        question: str,
        use_ml: bool = True
    ) -> Tuple[Intent, Dict[str, Any], str]:
        """
        Classify intent using hybrid approach.

        Args:
            question: User's question
            use_ml: Whether to use ML fallback for UNKNOWN intents

        Returns:
            Tuple of (Intent, params, classification_method)
            where classification_method is "rule" or "ml"
        """
        # Step 1: Try rule-based first (fast path)
        rule_intent, rule_params = self.rule_classifier.classify(question)

        # If rule-based found a match (not UNKNOWN), use it
        if rule_intent != Intent.UNKNOWN:
            logger.info(f"Rule-based classification: {rule_intent.value}")
            return rule_intent, rule_params, "rule"

        # Step 2: If rule-based returns UNKNOWN and ML is enabled, try ML
        if use_ml:
            logger.info("Rule-based returned UNKNOWN, trying ML classifier...")
            ml_intent, ml_params = await self.ml_classifier.classify(question)

            if ml_intent != Intent.UNKNOWN:
                logger.info(f"ML classification: {ml_intent.value}")
                return ml_intent, ml_params, "ml"
            else:
                logger.info("Both classifiers returned UNKNOWN")
                return Intent.UNKNOWN, {}, "none"

        # Step 3: No ML fallback, return UNKNOWN
        return Intent.UNKNOWN, {}, "none"

    async def classify_with_confidence(
        self,
        question: str
    ) -> Dict[str, Any]:
        """
        Classify with detailed confidence information.

        Returns:
            Dict with intent, params, method, and confidence scores
        """
        # Get rule-based result
        rule_intent, rule_params = self.rule_classifier.classify(question)

        # Get ML result
        ml_intent, ml_params = await self.ml_classifier.classify(question)

        # Determine which to use
        if rule_intent != Intent.UNKNOWN:
            # Rule matched, prefer it
            final_intent = rule_intent
            final_params = rule_params
            method = "rule"
            confidence = 1.0  # Rules are deterministic
        elif ml_intent != Intent.UNKNOWN:
            # Only ML matched
            final_intent = ml_intent
            final_params = ml_params
            method = "ml"
            confidence = 0.8  # Lower confidence for ML
        else:
            # Neither matched
            final_intent = Intent.UNKNOWN
            final_params = {}
            method = "none"
            confidence = 0.0

        return {
            "intent": final_intent,
            "params": final_params,
            "method": method,
            "confidence": confidence,
            "rule_result": rule_intent.value,
            "ml_result": ml_intent.value
        }

    async def close(self):
        """Close ML classifier resources."""
        await self.ml_classifier.close()


# Global instance
hybrid_intent_classifier = HybridIntentClassifier()
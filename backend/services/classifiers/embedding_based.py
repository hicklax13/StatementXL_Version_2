"""
Embedding-based classifier for financial line items.

Uses SentenceTransformers (all-MiniLM-L6-v2) for semantic similarity matching.
"""
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import structlog

from backend.services.ontology_service import (
    ClassificationResult,
    OntologyItem,
    OntologyService,
    get_ontology_service,
)

logger = structlog.get_logger(__name__)

# Try to import sentence_transformers, gracefully handle if not installed
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not installed, embedding classifier disabled")


class EmbeddingClassifier:
    """
    Embedding-based classifier using semantic similarity.

    Uses all-MiniLM-L6-v2 (23M params, CPU-compatible) to encode
    line items and find nearest neighbors via cosine similarity.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"
    DEFAULT_EMBEDDINGS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "ontology_embeddings.pkl"
    SIMILARITY_THRESHOLD = 0.75

    def __init__(
        self,
        ontology_service: Optional[OntologyService] = None,
        embeddings_path: Optional[Path] = None,
        load_model: bool = True,
    ):
        """
        Initialize embedding classifier.

        Args:
            ontology_service: Ontology service instance.
            embeddings_path: Path to precomputed embeddings pickle.
            load_model: Whether to load the model (can be deferred).
        """
        self._ontology = ontology_service or get_ontology_service()
        self._embeddings_path = embeddings_path or self.DEFAULT_EMBEDDINGS_PATH
        self._model = None
        self._item_embeddings = None
        self._item_list: List[OntologyItem] = []
        self._text_list: List[str] = []

        if load_model and EMBEDDINGS_AVAILABLE:
            self._load_or_create_embeddings()

    def _load_or_create_embeddings(self) -> None:
        """Load precomputed embeddings or create them."""
        if self._embeddings_path.exists():
            self._load_embeddings()
        else:
            self._create_embeddings()

    def _load_embeddings(self) -> None:
        """Load precomputed embeddings from pickle file."""
        logger.info("Loading precomputed embeddings", path=str(self._embeddings_path))

        try:
            with open(self._embeddings_path, "rb") as f:
                data = pickle.load(f)

            self._item_embeddings = data["embeddings"]
            self._item_list = data["items"]
            self._text_list = data["texts"]

            logger.info(
                "Embeddings loaded",
                count=len(self._item_list),
            )
        except Exception as e:
            logger.error("Failed to load embeddings", error=str(e))
            self._create_embeddings()

    def _create_embeddings(self) -> None:
        """Create embeddings for all ontology items."""
        if not EMBEDDINGS_AVAILABLE:
            logger.warning("Cannot create embeddings, sentence-transformers not installed")
            return

        logger.info("Creating ontology embeddings", model=self.MODEL_NAME)

        # Load model
        self._model = SentenceTransformer(self.MODEL_NAME)

        # Collect all items and their text representations
        self._item_list = []
        self._text_list = []

        for item in self._ontology.get_all_items():
            # Create text representation combining label and aliases
            text = item.label
            self._item_list.append(item)
            self._text_list.append(text)

            # Also add each alias as a separate entry
            for alias in item.aliases:
                self._item_list.append(item)
                self._text_list.append(alias)

        # Generate embeddings
        logger.info("Encoding ontology items", count=len(self._text_list))
        self._item_embeddings = self._model.encode(
            self._text_list,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,  # For cosine similarity via dot product
        )

        # Save embeddings
        self._save_embeddings()

        logger.info("Embeddings created", count=len(self._item_list))

    def _save_embeddings(self) -> None:
        """Save embeddings to pickle file."""
        logger.info("Saving embeddings", path=str(self._embeddings_path))

        try:
            self._embeddings_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self._embeddings_path, "wb") as f:
                pickle.dump({
                    "embeddings": self._item_embeddings,
                    "items": self._item_list,
                    "texts": self._text_list,
                    "model": self.MODEL_NAME,
                }, f)

        except Exception as e:
            logger.error("Failed to save embeddings", error=str(e))

    def _get_model(self) -> Optional["SentenceTransformer"]:
        """Get or load the sentence transformer model."""
        if not EMBEDDINGS_AVAILABLE:
            return None

        if self._model is None:
            self._model = SentenceTransformer(self.MODEL_NAME)

        return self._model

    def classify(
        self, text: str, top_k: int = 5, threshold: float = None
    ) -> ClassificationResult:
        """
        Classify a line item using embedding similarity.

        Args:
            text: Line item text to classify.
            top_k: Number of top candidates to return.
            threshold: Minimum similarity threshold.

        Returns:
            ClassificationResult with best match.
        """
        if not EMBEDDINGS_AVAILABLE or self._item_embeddings is None:
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="embedding_unavailable",
            )

        if not text or not text.strip():
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="none",
            )

        threshold = threshold or self.SIMILARITY_THRESHOLD

        # Encode query
        model = self._get_model()
        if model is None:
            return ClassificationResult(
                item=None,
                confidence=0.0,
                match_type="embedding_unavailable",
            )

        query_embedding = model.encode(
            [text.strip()],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]

        # Compute similarities (dot product since normalized)
        similarities = np.dot(self._item_embeddings, query_embedding)

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        # Build candidates list (deduplicate by item ID)
        candidates = []
        seen_ids = set()

        for idx in top_indices:
            item = self._item_list[idx]
            score = float(similarities[idx])

            if item.id not in seen_ids:
                seen_ids.add(item.id)
                candidates.append((item, score))

        # Get best match
        if candidates and candidates[0][1] >= threshold:
            best_item, best_score = candidates[0]
            return ClassificationResult(
                item=best_item,
                confidence=best_score,
                match_type="embedding",
                candidates=candidates,
            )

        # Below threshold
        return ClassificationResult(
            item=candidates[0][0] if candidates else None,
            confidence=candidates[0][1] if candidates else 0.0,
            match_type="embedding_low_confidence",
            candidates=candidates,
        )

    def classify_batch(
        self, texts: List[str], top_k: int = 5
    ) -> List[ClassificationResult]:
        """
        Classify multiple line items.

        Args:
            texts: List of texts to classify.
            top_k: Number of top candidates per item.

        Returns:
            List of ClassificationResults.
        """
        return [self.classify(text, top_k) for text in texts]

    def regenerate_embeddings(self) -> None:
        """Force regeneration of embeddings."""
        if self._embeddings_path.exists():
            self._embeddings_path.unlink()
        self._create_embeddings()


# Singleton instance
_classifier_instance: Optional[EmbeddingClassifier] = None


def get_embedding_classifier() -> EmbeddingClassifier:
    """Get singleton EmbeddingClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = EmbeddingClassifier()
    return _classifier_instance

"""
Embeddings service for semantic similarity and knowledge graph enrichment.

Supports multiple providers:
- OpenAI: text-embedding-3-small (production)
- HuggingFace: sentence-transformers (open-source, on-device)

Features:
- Caching for cost/performance optimization
- Batch processing
- Similarity computation (cosine, euclidean)
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for texts."""
        pass

    @abstractmethod
    async def embed_single(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small."""

    def __init__(self, api_key: Optional[str] = None):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "text-embedding-3-small"
        self.dimension = 1536

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts."""
        try:
            response = await self.client.embeddings.create(
                input=texts, model=self.model
            )
            # Sort by index to maintain order
            embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in embeddings]
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            raise

    async def embed_single(self, text: str) -> List[float]:
        """Embed single text."""
        embeddings = await self.embed([text])
        return embeddings[0]


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """HuggingFace sentence-transformers provider (open-source)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Batch embed texts — always returns plain Python float lists."""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"HuggingFace embedding error: {e}")
            raise

    async def embed_single(self, text: str) -> List[float]:
        """Embed single text — always returns a plain Python float list."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


class EmbeddingCache:
    """Simple JSON-based embedding cache."""

    def __init__(self, cache_path: str = "data/embeddings_cache.json"):
        self.cache_path = cache_path
        self.cache: Dict[str, List[float]] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r") as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} cached embeddings")
            except Exception as e:
                logger.warning(f"Failed to load embedding cache: {e}")

    def save(self) -> None:
        """Save cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w") as f:
                json.dump(self.cache, f)
        except Exception as e:
            logger.warning(f"Failed to save embedding cache: {e}")

    def get(self, text: str) -> Optional[List[float]]:
        """Retrieve cached embedding."""
        # Use text hash as key to handle long texts
        key = hash_text(text)
        return self.cache.get(key)

    def set(self, text: str, embedding: List[float]) -> None:
        """Cache an embedding."""
        key = hash_text(text)
        self.cache[key] = embedding


class EmbeddingService:
    """Main service for embeddings with caching and similarity.

    Provider selection:
    - "openai"      → OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
    - "huggingface" → sentence-transformers all-MiniLM-L6-v2 (free, local)
    - "auto"        → tries OpenAI first, falls back to HuggingFace silently
    """

    def __init__(
        self,
        provider: str = "auto",
        cache_enabled: bool = True,
        cache_path: str = "data/embeddings_cache.json",
    ):
        """Initialize embedding service."""
        import os
        if provider == "openai":
            self.provider = OpenAIEmbeddingProvider()
        elif provider == "huggingface":
            self.provider = HuggingFaceEmbeddingProvider()
        elif provider == "auto":
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                try:
                    self.provider = OpenAIEmbeddingProvider(api_key=openai_key)
                    logger.info("EmbeddingService: using OpenAI provider")
                except Exception as e:
                    logger.warning("EmbeddingService: OpenAI init failed (%s), falling back to HuggingFace", e)
                    self.provider = HuggingFaceEmbeddingProvider()
            else:
                logger.info("EmbeddingService: OPENAI_API_KEY not set, using HuggingFace (all-MiniLM-L6-v2)")
                self.provider = HuggingFaceEmbeddingProvider()
        else:
            raise ValueError(f"Unknown provider: {provider}")

        self.cache = EmbeddingCache(cache_path) if cache_enabled else None

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts with caching."""
        embeddings = []
        texts_to_embed = []
        indices_to_embed = []

        # Check cache
        for i, text in enumerate(texts):
            if self.cache:
                cached = self.cache.get(text)
                if cached:
                    embeddings.append(cached)
                    continue

            texts_to_embed.append(text)
            indices_to_embed.append(i)

        # Embed uncached texts
        if texts_to_embed:
            new_embeddings = await self.provider.embed(texts_to_embed)

            # Cache and collect results
            for idx, text, embedding in zip(
                indices_to_embed, texts_to_embed, new_embeddings
            ):
                if self.cache:
                    self.cache.set(text, embedding)
                embeddings.append(embedding)

        if self.cache:
            self.cache.save()

        # Reorder to match input order
        result = [None] * len(texts)
        for i, text in enumerate(texts):
            result[i] = embeddings.pop(0)

        return result

    async def embed_single(self, text: str) -> List[float]:
        """Embed single text."""
        embeddings = await self.embed([text])
        return embeddings[0]

    @staticmethod
    def cosine_similarity(
        embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    @staticmethod
    def euclidean_distance(
        embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Compute Euclidean distance between two embeddings."""
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.linalg.norm(a - b))

    @staticmethod
    def batch_cosine_similarity(
        query_embedding: List[float], embeddings: List[List[float]]
    ) -> List[float]:
        """Compute cosine similarity between query and multiple embeddings."""
        query = np.array(query_embedding)
        similarities = []
        for emb in embeddings:
            target = np.array(emb)
            sim = float(np.dot(query, target) / (np.linalg.norm(query) * np.linalg.norm(target)))
            similarities.append(sim)
        return similarities


def hash_text(text: str) -> str:
    """Create consistent hash key for text."""
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()

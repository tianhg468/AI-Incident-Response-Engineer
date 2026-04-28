"""Incident searcher tool - semantic similarity search over past incidents."""

import logging
import json
from pathlib import Path
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class IncidentSearcher:
    """Search for similar past incidents using vector embeddings.

    Uses sentence-transformers for embeddings and FAISS for efficient
    similarity search. This enables finding historical incidents with
    similar symptoms even if they use different words.

    Example:
        Current: "Pods crashing with OOM errors, memory usage at 95%"
        Past: "Out of memory kills in production, heap exhausted"
        -> High similarity despite different wording

    The incident database is a JSON file containing:
    - incident_id: Unique identifier
    - service: Service name
    - symptoms: Description of what went wrong
    - root_cause: What actually caused the issue
    - resolution: How it was fixed
    - timestamp: When it occurred
    - metadata: Tags, severity, etc.
    """

    def __init__(self, incidents_dir: Path):
        """Initialize incident searcher.

        Args:
            incidents_dir: Directory containing past incidents data
        """
        self.incidents_dir = Path(incidents_dir)
        self.incidents_file = self.incidents_dir / "incidents.json"

        # Lazy-loaded components
        self._model = None
        self._index = None
        self._incidents = None

        logger.info(f"Initialized IncidentSearcher (dir: {incidents_dir})")

    def _load_model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer

            # Use a small, fast model
            # all-MiniLM-L6-v2: 384 dimensions, 80MB, very fast
            model_name = "all-MiniLM-L6-v2"
            logger.info(f"Loading embedding model: {model_name}")

            self._model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise RuntimeError(
                "Failed to load sentence-transformers model. "
                "Install with: pip install sentence-transformers"
            )

        return self._model

    def _load_incidents(self) -> list[dict]:
        """Load past incidents from JSON file.

        Returns:
            List of incident dicts
        """
        if self._incidents is not None:
            return self._incidents

        if not self.incidents_file.exists():
            logger.warning(f"Incidents file not found: {self.incidents_file}")
            self._incidents = []
            return []

        try:
            with open(self.incidents_file, 'r', encoding='utf-8') as f:
                incidents = json.load(f)

            logger.info(f"Loaded {len(incidents)} past incidents")
            self._incidents = incidents
            return incidents

        except Exception as e:
            logger.error(f"Failed to load incidents: {e}")
            self._incidents = []
            return []

    def _build_index(self, incidents: list[dict]):
        """Build FAISS index from incidents.

        Args:
            incidents: List of incident dicts
        """
        if self._index is not None:
            return

        if not incidents:
            logger.warning("No incidents to index")
            return

        try:
            import faiss
        except ImportError:
            logger.error("FAISS not installed. Install with: pip install faiss-cpu")
            raise RuntimeError("FAISS not installed")

        model = self._load_model()

        # Extract symptom text for embedding
        symptom_texts = [
            self._create_searchable_text(incident)
            for incident in incidents
        ]

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(symptom_texts)} incidents...")
        embeddings = model.encode(
            symptom_texts,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # Build FAISS index
        dimension = embeddings.shape[1]
        logger.info(f"Building FAISS index (dimension: {dimension})")

        # Use IndexFlatIP for cosine similarity (with normalized vectors)
        # For larger datasets, could use IndexIVFFlat for approximate search
        index = faiss.IndexFlatIP(dimension)

        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)

        # Add to index
        index.add(embeddings.astype('float32'))

        self._index = index
        logger.info(f"FAISS index built with {index.ntotal} vectors")

    def _create_searchable_text(self, incident: dict) -> str:
        """Create searchable text from incident data.

        Combines symptoms, error messages, and other relevant fields
        into a single text for embedding.

        Args:
            incident: Incident dict

        Returns:
            Combined searchable text
        """
        parts = []

        # Main symptoms
        if 'symptoms' in incident:
            parts.append(incident['symptoms'])

        # Service context
        if 'service' in incident:
            parts.append(f"Service: {incident['service']}")

        # Error messages
        if 'error_messages' in incident:
            errors = incident['error_messages']
            if isinstance(errors, list):
                parts.extend(errors[:3])  # Limit to first 3 errors
            else:
                parts.append(str(errors))

        # Tags/keywords
        if 'tags' in incident:
            tags = incident['tags']
            if isinstance(tags, list):
                parts.append(' '.join(tags))

        return ' '.join(parts)

    async def search_similar(
        self,
        symptom_text: str,
        service: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.6
    ) -> dict:
        """Search for similar past incidents.

        Args:
            symptom_text: Description of current incident symptoms
            service: Filter by service name (optional)
            limit: Maximum number of results
            min_similarity: Minimum similarity score (0.0-1.0)

        Returns:
            Dict with similar incidents
        """
        logger.info(f"Searching for similar incidents (service={service}, limit={limit})")

        # Load incidents
        incidents = self._load_incidents()

        if not incidents:
            return {
                'found': False,
                'message': 'No past incidents in database',
                'similar_incidents': []
            }

        # Build index if needed
        if self._index is None:
            self._build_index(incidents)

        if self._index is None:
            return {
                'found': False,
                'message': 'Failed to build search index',
                'similar_incidents': []
            }

        # Generate embedding for query
        model = self._load_model()
        query_embedding = model.encode(
            [symptom_text],
            show_progress_bar=False,
            convert_to_numpy=True
        )

        # Normalize for cosine similarity
        import faiss
        faiss.normalize_L2(query_embedding)

        # Search
        # Get more results than needed for filtering
        k = min(len(incidents), limit * 3)
        similarities, indices = self._index.search(
            query_embedding.astype('float32'),
            k
        )

        # Build results
        results = []
        for similarity, idx in zip(similarities[0], indices[0]):
            # Skip if below minimum similarity
            if similarity < min_similarity:
                continue

            incident = incidents[idx]

            # Filter by service if specified
            if service and incident.get('service', '').lower() != service.lower():
                continue

            results.append({
                'incident_id': incident.get('incident_id'),
                'service': incident.get('service'),
                'symptoms': incident.get('symptoms'),
                'root_cause': incident.get('root_cause'),
                'resolution': incident.get('resolution'),
                'timestamp': incident.get('timestamp'),
                'severity': incident.get('severity'),
                'tags': incident.get('tags', []),
                'similarity_score': round(float(similarity), 4),
                'metadata': incident.get('metadata', {})
            })

            # Stop if we have enough results
            if len(results) >= limit:
                break

        if not results:
            return {
                'found': False,
                'message': f'No similar incidents found (min_similarity={min_similarity})',
                'similar_incidents': [],
                'suggestions': [
                    'Try lowering min_similarity threshold',
                    'Remove service filter to search all services',
                    'Check if past incidents database is populated'
                ]
            }

        return {
            'found': True,
            'count': len(results),
            'query': symptom_text,
            'similar_incidents': results,
            'most_similar': results[0] if results else None
        }

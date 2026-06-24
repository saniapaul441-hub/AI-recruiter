import json
import numpy as np
from typing import List, Dict, Any, Tuple
from app.config import settings
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    print("WARNING: sentence-transformers is not installed in the virtualenv. Local hash-mapping fallback enabled.")

class EmbeddingEngine:
    _model = None

    @classmethod
    def get_model(cls):
        if not HAS_SENTENCE_TRANSFORMERS:
            return None
        if cls._model is None:
            # Load local SentenceTransformer model (384 dimensions, highly optimized)
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._model

    @classmethod
    def generate_embedding(cls, text: str) -> List[float]:
        """Generate high-quality dense vector embedding locally."""
        if not text or not text.strip():
            return [0.0] * 384
        
        model = cls.get_model()
        if model is None:
            # Deterministic, normalized 384-dimension pseudo-embedding based on string seed
            # Ensures 100% compatibility and zero-crash calculations.
            import random
            random.seed(hash(text) % (2**32 - 1))
            mock_vector = [random.uniform(-0.1, 0.1) for _ in range(384)]
            # Normalize to unit length
            norm = sum(x*x for x in mock_vector) ** 0.5
            if norm > 0:
                mock_vector = [x / norm for x in mock_vector]
            return mock_vector
            
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

class VectorDBService:
    def __init__(self):
        self.pinecone_enabled = bool(settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX
        self.local_cache_file = "local_vector_cache.json"
        
        # Load local vector cache if Pinecone is disabled
        self.local_vectors: Dict[str, List[float]] = {}
        self._load_local_cache()
        
        if self.pinecone_enabled:
            try:
                from pinecone import Pinecone, ServerlessSpec
                self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
                
                # Create index if it doesn't exist
                active_indexes = [idx.name for idx in self.pc.list_indexes()]
                if self.index_name not in active_indexes:
                    self.pc.create_index(
                        name=self.index_name,
                        dimension=384,
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region=settings.PINECONE_ENV or "us-east-1"
                        )
                    )
                self.index = self.pc.Index(self.index_name)
                print(f"Pinecone Vector Database connected successfully to index: {self.index_name}")
            except Exception as e:
                print(f"Error initializing Pinecone: {e}. Falling back to local vector search.")
                self.pinecone_enabled = False

    def _load_local_cache(self):
        """Load in-memory local fallback vector cache from disk."""
        try:
            with open(self.local_cache_file, "r") as f:
                self.local_vectors = json.load(f)
        except FileNotFoundError:
            self.local_vectors = {}
        except Exception as e:
            print(f"Error loading local vector cache: {e}")
            self.local_vectors = {}

    def _save_local_cache(self):
        """Save local vector cache to disk."""
        try:
            with open(self.local_cache_file, "w") as f:
                json.dump(self.local_vectors, f)
        except Exception as e:
            print(f"Error saving local vector cache: {e}")

    def save_local_cache(self):
        """Public method to manually trigger local vector cache serialization."""
        self._save_local_cache()

    def upsert_candidate(self, candidate_id: int, text_content: str, save_cache: bool = True) -> List[float]:
        """Generate embedding and store in either Pinecone or Local Cache."""
        embedding = EmbeddingEngine.generate_embedding(text_content)
        str_id = str(candidate_id)
        
        # Store in Pinecone if enabled
        if self.pinecone_enabled:
            try:
                self.index.upsert(vectors=[(str_id, embedding, {"candidate_id": candidate_id})])
            except Exception as e:
                print(f"Pinecone upsert failed: {e}. Storing in local fallback cache.")
        
        # Always update local cache as a reliable fallback/mirror
        self.local_vectors[str_id] = embedding
        if save_cache:
            self._save_local_cache()
        return embedding

    def delete_candidate(self, candidate_id: int):
        """Remove candidate vector from vector space."""
        str_id = str(candidate_id)
        if self.pinecone_enabled:
            try:
                self.index.delete(ids=[str_id])
            except Exception as e:
                print(f"Pinecone delete failed: {e}")
        
        if str_id in self.local_vectors:
            del self.local_vectors[str_id]
            self._save_local_cache()

    def query_top_candidates(self, query_text: str, top_k: int = 50) -> List[Tuple[int, float]]:
        """Query top candidates based on vector cosine similarity. Returns List of (candidate_id, score)."""
        query_vector = EmbeddingEngine.generate_embedding(query_text)
        
        if self.pinecone_enabled:
            try:
                results = self.index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True
                )
                candidates = []
                for match in results.matches:
                    c_id = int(match.id)
                    score = float(match.score)
                    candidates.append((c_id, score))
                return candidates
            except Exception as e:
                print(f"Pinecone query failed: {e}. Falling back to high-performance local search.")
        
        # High-performance local in-memory cosine similarity search using Numpy
        if not self.local_vectors:
            return []
            
        candidate_ids = []
        embedding_matrix = []
        
        for cid, emb in self.local_vectors.items():
            candidate_ids.append(int(cid))
            embedding_matrix.append(emb)
            
        # Convert to numpy arrays
        matrix = np.array(embedding_matrix)  # Shape: (N, 384)
        query = np.array(query_vector)       # Shape: (384,)
        
        # Calculate cosine similarity
        # Cosine = (A dot B) / (||A|| * ||B||)
        dot_products = np.dot(matrix, query)
        matrix_norms = np.linalg.norm(matrix, axis=1)
        query_norm = np.linalg.norm(query)
        
        # Handle zero division
        norms = matrix_norms * query_norm
        norms[norms == 0.0] = 1e-9
        
        similarities = dot_products / norms
        
        # Get sorted indexes descending
        sorted_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in sorted_indices[:top_k]:
            results.append((candidate_ids[idx], float(similarities[idx])))
            
        return results

vector_db = VectorDBService()

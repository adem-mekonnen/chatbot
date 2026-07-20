# app/rag/retriever.py
import os
import asyncio
import logging
import threading
import hashlib
import time
from functools import lru_cache
from typing import Tuple, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor
from app.config import settings
from app.logger import metrics_collector

logger = logging.getLogger("enterprise-agent")

# Thread-safe singleton for model loading
_embeddings_lock = threading.Lock()
_EMBEDDINGS_INSTANCE = None

# In-memory cache for query results with TTL
_query_cache: Dict[str, Dict[str, any]] = {}
_cache_lock = threading.Lock()
_MAX_CACHE_SIZE = 500 
_CACHE_TTL = 1800  # 30 minutes

# Thread pool executor for blocking vector search operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-worker")

def get_embeddings_singleton():
    """
    Returns a process-wide HuggingFaceEmbeddings instance.
    Loads the all-MiniLM-L6-v2 model used during ingestion.
    """
    global _EMBEDDINGS_INSTANCE
    if _EMBEDDINGS_INSTANCE is None:
        with _embeddings_lock:
            if _EMBEDDINGS_INSTANCE is None:
                try:
                    # Updated import for modern langchain
                    from langchain_huggingface import HuggingFaceEmbeddings
                    logger.info("Loading Embedding Model for Retrieval...")
                    _EMBEDDINGS_INSTANCE = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'},
                        encode_kwargs={'normalize_embeddings': True}
                    )
                    logger.info("Embedding model ready for search.")
                except Exception as e:
                    logger.error(f"Failed to load embeddings model: {e}")
                    _EMBEDDINGS_INSTANCE = None
    return _EMBEDDINGS_INSTANCE

def _get_query_hash(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode('utf-8')).hexdigest()

def _is_cache_valid(cache_entry: Dict[str, any]) -> bool:
    return time.time() - cache_entry.get('timestamp', 0) < _CACHE_TTL

def _cache_get(cache_key: str) -> Optional[Tuple[str, float]]:
    with _cache_lock:
        if cache_key in _query_cache and _is_cache_valid(_query_cache[cache_key]):
            return _query_cache[cache_key]['result']
    return None

def _cache_put(cache_key: str, result: Tuple[str, float]):
    with _cache_lock:
        if len(_query_cache) >= _MAX_CACHE_SIZE:
            oldest_key = min(_query_cache.keys(), key=lambda k: _query_cache[k]['timestamp'])
            del _query_cache[oldest_key]
        _query_cache[cache_key] = {'result': result, 'timestamp': time.time()}

class SecureRAGRetriever:
    _TOP_K = 5

    def __init__(self):
        # 1.1 is strict (Verified), 1.3 is loose (General)
        self.max_l2_distance_threshold = 1.1 
        
        try:
            # Connect to the ChromaDB created during build
            from langchain_chroma import Chroma
            embeddings = get_embeddings_singleton()
            
            if not os.path.exists(settings.chroma_persist_dir):
                logger.warning(f"Vectorstore directory {settings.chroma_persist_dir} not found!")

            self.vectorstore = Chroma(
                persist_directory=settings.chroma_persist_dir,
                embedding_function=embeddings,
                collection_name=settings.chroma_collection
            )
            logger.info(f"RAG system ACTIVE. Connected to collection: {settings.chroma_collection}")
        except Exception as e:
            logger.error(f"CRITICAL: RAG initialization failed: {e}")
            self.vectorstore = None

    async def retrieve_secure_context(self, query: str) -> Tuple[str, float]:
        """
        Main entry point for finding document context.
        """
        if not self.vectorstore:
            return "", 2.0
        
        start_time = time.time()
        cache_key = _get_query_hash(query)
        cached_result = _cache_get(cache_key)
        
        if cached_result:
            metrics_collector.increment("rag_cache_hits")
            return cached_result
        
        try:
            # Run the blocking search in the thread pool
            result = await asyncio.get_event_loop().run_in_executor(
                _executor, self._run_search, query
            )
            _cache_put(cache_key, result)
            
            elapsed = time.time() - start_time
            metrics_collector.histogram("rag_request_duration", elapsed)
            return result
        except Exception as e:
            logger.error(f"Search failure: {e}")
            return "", 2.0

    def _run_search(self, query: str) -> Tuple[str, float]:
        """
        Internal logic to perform similarity search across query variants.
        """
        variants = self._generate_query_variants(query)
        best_result = ("", 2.0)
        
        for variant in variants:
            try:
                # Search ChromaDB
                results = self.vectorstore.similarity_search_with_score(variant, k=self._TOP_K)
                if results:
                    doc, score = results[0]
                    # Lower score = better match in L2 distance
                    if score < best_result[1] and score <= self.max_l2_distance_threshold:
                        # Append metadata (source filename) for professional citations
                        source = doc.metadata.get('source', 'Unknown')
                        content_with_source = f"{doc.page_content}\n[Source: {source}]"
                        best_result = (content_with_source, score)
                    
                    if score < 0.7: break # Found a near-perfect match
            except Exception as e:
                continue
        
        return best_result
    
    def _generate_query_variants(self, query: str) -> List[str]:
        processed = self._preprocess_query(query)
        return [processed, f"{processed}?", query.strip()]
    
    def _preprocess_query(self, query: str) -> str:
        processed = query.lower().strip()
        # Expand common enterprise terms for better matching
        expansions = {
            "pto": "paid time off vacation",
            "hr": "human resources",
            "policy": "rule guideline procedure",
            "leave": "absence vacation time off"
        }
        for k, v in expansions.items():
            if k in processed:
                processed = processed.replace(k, v)
        return processed
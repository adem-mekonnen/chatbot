# app/rag/retriever.py
import os
import asyncio
import logging
import threading
import hashlib
import time
from typing import Tuple, Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor
from app.config import settings
from app.logger import metrics_collector

logger = logging.getLogger("enterprise-agent")

# Thread-safe singleton for cloud API connection
_embeddings_lock = threading.Lock()
_EMBEDDINGS_INSTANCE = None

# In-memory cache for query results
_query_cache: Dict[str, Dict[str, any]] = {}
_cache_lock = threading.Lock()
_MAX_CACHE_SIZE = 500 
_CACHE_TTL = 1800 

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-worker")

def get_embeddings_singleton():
    """
    Connects to Hugging Face Cloud API for embeddings.
    Saves ~450MB of RAM compared to local loading.
    """
    global _EMBEDDINGS_INSTANCE
    if _EMBEDDINGS_INSTANCE is None:
        with _embeddings_lock:
            if _EMBEDDINGS_INSTANCE is None:
                try:
                    # Switch from local model to Cloud API
                    from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
                    
                    hf_token = os.getenv("HF_TOKEN")
                    if not hf_token:
                        logger.error("HF_TOKEN is missing in Environment Variables!")

                    logger.info("Initializing RAM-efficient Cloud Embeddings...")
                    _EMBEDDINGS_INSTANCE = HuggingFaceInferenceAPIEmbeddings(
                        api_key=hf_token,
                        model_name="sentence-transformers/all-MiniLM-L6-v2"
                    )
                    logger.info("Cloud Embeddings Ready.")
                except Exception as e:
                    logger.error(f"Failed to connect to Cloud Embeddings: {e}")
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
        self.max_l2_distance_threshold = 1.1 
        try:
            from langchain_chroma import Chroma
            embeddings = get_embeddings_singleton()
            
            self.vectorstore = Chroma(
                persist_directory=settings.chroma_persist_dir,
                embedding_function=embeddings,
                collection_name=settings.chroma_collection
            )
            logger.info("RAG: Intelligent Cloud-Search Active.")
        except Exception as e:
            logger.error(f"RAG system failed: {e}")
            self.vectorstore = None

    async def retrieve_secure_context(self, query: str) -> Tuple[str, float]:
        if not self.vectorstore:
            return "", 2.0
        
        cache_key = _get_query_hash(query)
        cached_result = _cache_get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                _executor, self._run_search, query
            )
            _cache_put(cache_key, result)
            return result
        except Exception as e:
            logger.error(f"Search failure: {e}")
            return "", 2.0

    def _run_search(self, query: str) -> Tuple[str, float]:
        variants = [query.lower().strip(), f"{query}?", query.split()[-1]]
        best_result = ("", 2.0)
        
        for variant in variants:
            try:
                results = self.vectorstore.similarity_search_with_score(variant, k=self._TOP_K)
                if results:
                    doc, score = results[0]
                    if score < best_result[1] and score <= self.max_l2_distance_threshold:
                        source = doc.metadata.get('source', 'Company Policy')
                        content_with_source = f"{doc.page_content}\n\n[Reference: {source}]"
                        best_result = (content_with_source, score)
                    if score < 0.7: break 
            except Exception:
                continue
        return best_result
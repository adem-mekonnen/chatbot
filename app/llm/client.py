import json
import asyncio
import httpx
import time
from typing import AsyncGenerator, Optional
from app.config import settings
from app.logger import structured_logger
from app.logger import metrics_collector

class CircuitBreaker:
    """Simple circuit breaker to prevent cascade failures"""
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_proceed(self) -> bool:
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

class PluggableLLMClient:
    def __init__(self):
        self.max_http_retries = 3
        self.base_backoff_sec = 1.0
        self.ollama_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=30)
        self._health_check_interval = 60  # seconds
        self._last_health_check = 0
        self._ollama_healthy = True

    async def _check_ollama_health(self) -> bool:
        """Check if Ollama service is available"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
    
    async def _get_ollama_health_status(self) -> bool:
        """Get cached health status, refresh if needed"""
        now = time.time()
        if now - self._last_health_check > self._health_check_interval:
            self._ollama_healthy = await self._check_ollama_health()
            self._last_health_check = now
            structured_logger.info(f"Ollama health check: {'healthy' if self._ollama_healthy else 'unhealthy'}")
        return self._ollama_healthy

    async def _try_huggingface_fallback(self, prompt: str, system_context: str) -> str:
        """Fallback to HuggingFace API when Ollama is unavailable"""
        if not settings.hf_token:
            structured_logger.warning("No HuggingFace token available for fallback")
            return (
                "I apologize, but the AI service is temporarily unavailable. "
                "Please try again in a few moments or contact IT support."
            )
        
        try:
            headers = {"Authorization": f"Bearer {settings.hf_token}"}
            payload_hf = {
                "inputs": f"<|system|>\n{system_context}</s>\n<|user|>\n{prompt}</s>\n<|assistant|>",
                "parameters": {"temperature": 0.1, "max_new_tokens": 150}
            }
            
            metrics_collector.increment("llm_fallback_attempts")
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta",
                    json=payload_hf,
                    headers=headers
                )
                if res.status_code == 200:
                    output = res.json()
                    if isinstance(output, list) and len(output) > 0:
                        gen_text = output[0].get("generated_text", "")
                        if "<|assistant|>" in gen_text:
                            result = gen_text.split("<|assistant|>")[-1].strip()
                        else:
                            result = gen_text.strip()
                        
                        metrics_collector.increment("llm_fallback_successes")
                        structured_logger.info("HuggingFace fallback successful")
                        return result
                else:
                    structured_logger.error(f"HuggingFace API failed: {res.status_code}")
                    metrics_collector.increment("llm_fallback_failures")
        except Exception as e:
            structured_logger.error(f"HuggingFace fallback failed: {str(e)}")
            metrics_collector.increment("llm_fallback_failures")

        return (
            "I apologize, but I'm experiencing technical difficulties connecting to the AI service. "
            "Please try your question again in a few moments, or contact IT support if the issue persists. "
            f"(Error ID: {int(time.time())})"
        )

    async def generate(self, prompt: str, system_context: str = "You are an assistant.") -> str:
        """
        Generates text using local Ollama endpoints with circuit breaker and health checks.
        Falls back to HuggingFace if Ollama is unavailable.
        """
        start_time = time.time()
        
        # Check circuit breaker and health status first
        if not self.ollama_circuit_breaker.can_proceed():
            structured_logger.warning("Ollama circuit breaker is OPEN, using HuggingFace fallback")
            return await self._try_huggingface_fallback(prompt, system_context)
        
        # Quick health check if we haven't done one recently
        if not await self._get_ollama_health_status():
            structured_logger.warning("Ollama health check failed, using HuggingFace fallback")
            return await self._try_huggingface_fallback(prompt, system_context)

        payload = {
            "model": settings.ollama_model,
            "prompt": f"{system_context}\n\nUser Question:\n{prompt}",
            "stream": False,
            "options": {"temperature": 0.0, "num_ctx": 2048}  # Limit context window for faster processing
        }

        for attempt in range(self.max_http_retries):
            try:
                # Reduced timeout to 20 seconds for faster failure detection
                async with httpx.AsyncClient(timeout=20.0) as client:
                    metrics_collector.increment("llm_calls_total")
                    structured_logger.debug(f"LLM request attempt {attempt+1}: {settings.ollama_url}")
                    
                    res = await client.post(f"{settings.ollama_url}/api/generate", json=payload)
                    
                    # Retry on rate limits (429) or transient server errors (500, 502, 503, 504)
                    if res.status_code in [429, 500, 502, 503, 504]:
                        structured_logger.warning(f"LLM server error {res.status_code}, retrying...")
                        raise httpx.HTTPStatusError(
                            message=f"Transient server error: {res.status_code}",
                            request=res.request,
                            response=res
                        )
                        
                    if res.status_code == 200:
                        response_text = res.json().get("response", "").strip()
                        structured_logger.debug(f"LLM response length: {len(response_text)} characters")
                        
                        # Record success for circuit breaker
                        self.ollama_circuit_breaker.record_success()
                        
                        # Log performance metrics
                        elapsed = time.time() - start_time
                        metrics_collector.histogram("llm_request_duration", elapsed)
                        structured_logger.info(f"LLM request completed in {elapsed:.2f}s")
                        
                        return response_text
                        
                    else:
                        structured_logger.error(f"LLM request failed with status {res.status_code}: {res.text}")
                        
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                structured_logger.warning(f"LLM connection error on attempt {attempt+1}: {str(e)}")
                
                # Record failure for circuit breaker
                self.ollama_circuit_breaker.record_failure()
                
                if attempt == self.max_http_retries - 1:
                    structured_logger.error("All LLM connection attempts failed, trying HuggingFace fallback")
                    # Log failure metrics
                    elapsed = time.time() - start_time
                    metrics_collector.histogram("llm_request_failure_duration", elapsed)
                    metrics_collector.increment("llm_ollama_failures")
                    
                    # Try HuggingFace fallback if available
                    return await self._try_huggingface_fallback(prompt, system_context)
                else:
                    backoff = self.base_backoff_sec * (2 ** attempt)
                    structured_logger.debug(f"Backing off for {backoff} seconds")
                    await asyncio.sleep(backoff)

        # This should never be reached due to the fallback above
        return "Error: Unable to generate response after all retry attempts."

    async def generate_stream(self, prompt: str, system_context: str = "You are an assistant.") -> AsyncGenerator[str, None]:
        """Provides raw async token generation streaming for the portal interface."""
        
        # Check circuit breaker before attempting streaming
        if not self.ollama_circuit_breaker.can_proceed():
            structured_logger.warning("Ollama circuit breaker is OPEN, streaming not available")
            yield "I apologize, but the streaming service is temporarily unavailable. Please try a regular chat message."
            return
        
        # Quick health check
        if not await self._get_ollama_health_status():
            structured_logger.warning("Ollama health check failed, streaming not available")
            yield "I apologize, but the streaming service is temporarily unavailable. Please try a regular chat message."
            return
            
        payload = {
            "model": settings.ollama_model,
            "prompt": f"{system_context}\n\nUser Question:\n{prompt}",
            "stream": True,
            "options": {"temperature": 0.0, "num_ctx": 2048}  # Limit context for performance
        }
        
        for attempt in range(self.max_http_retries):
            try:
                # Reduced timeout to 25 seconds for streaming
                async with httpx.AsyncClient(timeout=25.0) as client:
                    structured_logger.debug(f"LLM stream attempt {attempt+1}: {settings.ollama_url}")
                    
                    async with client.stream("POST", f"{settings.ollama_url}/api/generate", json=payload) as response:
                        if response.status_code == 200:
                            self.ollama_circuit_breaker.record_success()
                            async for chunk in response.aiter_text():
                                if not chunk.strip():
                                    continue
                                try:
                                    data = json.loads(chunk)
                                    token = data.get("response", "")
                                    if token:
                                        yield token
                                except json.JSONDecodeError:
                                    continue
                            return  # Stream completed successfully
                        else:
                            structured_logger.warning(f"Stream failed with status {response.status_code}")
                            
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                structured_logger.warning(f"Stream connection error on attempt {attempt+1}: {str(e)}")
                self.ollama_circuit_breaker.record_failure()
                
                if attempt < self.max_http_retries - 1:
                    backoff = self.base_backoff_sec * (2 ** attempt)
                    structured_logger.debug(f"Stream backing off for {backoff} seconds")
                    await asyncio.sleep(backoff)
                else:
                    yield "Error: Unable to establish streaming connection. Please try a regular chat message."
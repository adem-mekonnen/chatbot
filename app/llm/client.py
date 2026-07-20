import json
import asyncio
import httpx
import time
import os
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
        else:
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
        self._health_check_interval = 60
        self._last_health_check = 0
        self._ollama_healthy = True

    async def _get_headers(self) -> dict:
        """Helper to get auth headers if using Groq/Cloud providers"""
        headers = {"Content-Type": "application/json"}
        # If we are using Groq, add the API key
        groq_key = os.getenv("GROQ_API_KEY")
        if "groq" in settings.ollama_url.lower() and groq_key:
            headers["Authorization"] = f"Bearer {groq_key}"
        return headers

    async def _check_ollama_health(self) -> bool:
        """Check if LLM service is available"""
        try:
            # If using Groq, health check is just a small token test
            if "groq" in settings.ollama_url.lower():
                return True 
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.ollama_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

    async def generate(self, prompt: str, system_context: str = "You are an assistant.") -> str:
        """
        Generates text using Groq (Cloud) or Ollama (Local).
        Automatically switches API format based on the URL.
        """
        if not self.ollama_circuit_breaker.can_proceed():
            return "AI Service temporarily paused due to frequent errors. Please try again in 1 minute."

        # Detect if we are using OpenAI/Groq format or Ollama format
        is_cloud_provider = any(x in settings.ollama_url.lower() for x in ["groq", "openai"])
        
        # 1. Prepare Payload
        if is_cloud_provider:
            # OpenAI / Groq Format
            endpoint = f"{settings.ollama_url}/chat/completions"
            payload = {
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": system_context},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1
            }
        else:
            # Local Ollama Format
            endpoint = f"{settings.ollama_url}/api/generate"
            payload = {
                "model": settings.ollama_model,
                "prompt": f"{system_context}\n\nUser: {prompt}",
                "stream": False,
                "options": {"temperature": 0.0}
            }

        # 2. Execute Request
        for attempt in range(self.max_http_retries):
            try:
                headers = await self._get_headers()
                async with httpx.AsyncClient(timeout=30.0) as client:
                    metrics_collector.increment("llm_calls_total")
                    res = await client.post(endpoint, json=payload, headers=headers)
                    
                    if res.status_code == 200:
                        data = res.json()
                        self.ollama_circuit_breaker.record_success()
                        
                        # Extract text based on provider
                        if is_cloud_provider:
                            return data["choices"][0]["message"]["content"].strip()
                        else:
                            return data.get("response", "").strip()
                    else:
                        structured_logger.error(f"LLM API Error {res.status_code}: {res.text}")
                        self.ollama_circuit_breaker.record_failure()
            
            except Exception as e:
                structured_logger.warning(f"LLM Connection Attempt {attempt+1} failed: {e}")
                if attempt == self.max_http_retries - 1:
                    self.ollama_circuit_breaker.record_failure()
                    return "I'm sorry, I'm having trouble connecting to my brain right now. Please try again."
                await asyncio.sleep(self.base_backoff_sec * (2 ** attempt))

    async def generate_stream(self, prompt: str, system_context: str = "You are an assistant.") -> AsyncGenerator[str, None]:
        """Provides async token generation for the UI."""
        is_cloud_provider = "groq" in settings.ollama_url.lower()
        endpoint = f"{settings.ollama_url}/chat/completions" if is_cloud_provider else f"{settings.ollama_url}/api/generate"
        
        # Prepare streaming payload
        if is_cloud_provider:
            payload = {
                "model": settings.ollama_model,
                "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}],
                "stream": True
            }
        else:
            payload = {
                "model": settings.ollama_model,
                "prompt": f"{system_context}\n\nUser: {prompt}",
                "stream": True
            }

        headers = await self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        yield "Connection Error. Please try again."
                        return

                    async for line in response.aiter_lines():
                        if not line: continue
                        
                        if is_cloud_provider:
                            # Parse Server-Sent Events (SSE) for Groq/OpenAI
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]": break
                                try:
                                    chunk = json.loads(data_str)
                                    token = chunk["choices"][0]["delta"].get("content", "")
                                    if token: yield token
                                except: continue
                        else:
                            # Parse raw JSON lines for Ollama
                            try:
                                chunk = json.loads(line)
                                yield chunk.get("response", "")
                            except: continue
        except Exception as e:
            yield f"Stream interrupted: {e}"
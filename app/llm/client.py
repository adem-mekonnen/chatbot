import json
import asyncio
import httpx
import time
import os
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from app.config import settings
from app.logger import structured_logger, metrics_collector

logger = logging.getLogger("enterprise-agent")

class CircuitBreaker:
    """Prevents system overload by pausing requests after multiple failures."""
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def can_proceed(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            structured_logger.error("CIRCUIT BREAKER: State changed to OPEN")

class PluggableLLMClient:
    def __init__(self):
        self.max_http_retries = 3
        self.base_backoff_sec = 1.5
        self.circuit_breaker = CircuitBreaker(failure_threshold=4, timeout=45)
        
    async def _get_headers(self) -> dict:
        """Determines headers based on the provider (Groq vs Ollama)."""
        headers = {"Content-Type": "application/json"}
        url = settings.ollama_url.lower()
        
        if "groq" in url:
            key = os.getenv("GROQ_API_KEY")
            if key: headers["Authorization"] = f"Bearer {key}"
        elif "huggingface" in url:
            key = os.getenv("HF_TOKEN")
            if key: headers["Authorization"] = f"Bearer {key}"
            
        return headers

    async def _try_huggingface_fallback(self, prompt: str, system_context: str) -> str:
        """Emergency fallback to HuggingFace Inference API if Groq fails."""
        hf_token = os.getenv("HF_TOKEN")
        if not hf_token:
            return "I'm having trouble connecting to my primary and secondary brains. Please contact support."

        structured_logger.warning("LLM: Primary provider failed. Attempting HuggingFace Fallback...")
        metrics_collector.increment("llm_fallback_attempts")

        payload = {
            "inputs": f"System: {system_context}\nUser: {prompt}\nAssistant:",
            "parameters": {"max_new_tokens": 500, "temperature": 0.7}
        }
        
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-beta",
                    json=payload,
                    headers={"Authorization": f"Bearer {hf_token}"}
                )
                if res.status_code == 200:
                    metrics_collector.increment("llm_fallback_success")
                    return res.json()[0].get("generated_text", "").split("Assistant:")[-1].strip()
        except Exception as e:
            structured_logger.error(f"LLM: Fallback also failed: {e}")
        
        return "Critical connection error. All AI providers are currently unreachable."

    async def generate(self, prompt: str, system_context: str = "You are an assistant.") -> str:
        """Main generation logic with Rate Limit (429) handling and Fallback."""
        if not self.circuit_breaker.can_proceed():
            return "The AI service is temporarily cooling down due to high traffic. Please try again in a minute."

        is_cloud = "groq" in settings.ollama_url.lower() or "openai" in settings.ollama_url.lower()
        endpoint = f"{settings.ollama_url}/chat/completions" if is_cloud else f"{settings.ollama_url}/api/generate"
        
        if is_cloud:
            payload = {
                "model": settings.ollama_model,
                "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}],
                "temperature": 0.2
            }
        else:
            payload = {
                "model": settings.ollama_model, 
                "prompt": f"{system_context}\n\nUser: {prompt}",
                "stream": False
            }

        for attempt in range(self.max_http_retries):
            try:
                start_time = time.time()
                headers = await self._get_headers()
                
                async with httpx.AsyncClient(timeout=40.0) as client:
                    metrics_collector.increment("llm_calls_total")
                    res = await client.post(endpoint, json=payload, headers=headers)
                    
                    # Handle Rate Limiting (Common on Groq Free Tier)
                    if res.status_code == 429:
                        wait_time = int(res.headers.get("retry-after", 5))
                        structured_logger.warning(f"LLM: Rate limited (429). Waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue

                    if res.status_code == 200:
                        self.circuit_breaker.record_success()
                        elapsed = time.time() - start_time
                        metrics_collector.record_latency(elapsed * 1000)
                        
                        data = res.json()
                        return data["choices"][0]["message"]["content"].strip() if is_cloud else data.get("response", "").strip()

                    else:
                        structured_logger.error(f"LLM Error {res.status_code}: {res.text}")
                        self.circuit_breaker.record_failure()

            except Exception as e:
                structured_logger.warning(f"LLM Attempt {attempt+1} failed: {e}")
                self.circuit_breaker.record_failure()
                await asyncio.sleep(self.base_backoff_sec * (2 ** attempt))

        # If all retries fail, try the HuggingFace Fallback
        return await self._try_huggingface_fallback(prompt, system_context)

    async def generate_stream(self, prompt: str, system_context: str = "You are an assistant.") -> AsyncGenerator[str, None]:
        """Provides token-by-token streaming for a better UI experience."""
        is_cloud = "groq" in settings.ollama_url.lower()
        endpoint = f"{settings.ollama_url}/chat/completions" if is_cloud else f"{settings.ollama_url}/api/generate"
        
        payload = {
            "model": settings.ollama_model,
            "stream": True
        }
        if is_cloud:
            payload["messages"] = [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}]
        else:
            payload["prompt"] = f"{system_context}\n\nUser: {prompt}"

        headers = await self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=40.0) as client:
                async with client.stream("POST", endpoint, json=payload, headers=headers) as response:
                    if response.status_code == 429:
                        yield "⚠️ Rate limit reached. Switching to standard chat..."
                        return

                    async for line in response.aiter_lines():
                        if not line or line.strip() == "": continue
                        
                        if is_cloud:
                            if line.startswith("data: "):
                                data_str = line[6:].strip()
                                if data_str == "[DONE]": break
                                try:
                                    chunk = json.loads(data_str)
                                    token = chunk["choices"][0]["delta"].get("content", "")
                                    if token: yield token
                                except: continue
                        else:
                            try:
                                chunk = json.loads(line)
                                yield chunk.get("response", "")
                                if chunk.get("done"): break
                            except: continue
        except Exception as e:
            structured_logger.error(f"Streaming failed: {e}")
            yield " [Connection lost, please try again] "
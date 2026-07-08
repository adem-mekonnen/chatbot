# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()


class AppSettings:
    """Loads and validates configuration variables. Enforces fail-fast constraints on boot."""

    def __init__(self):
        # Secrets: None when the env var is absent — caught explicitly in validate()
        self.jwt_secret: str | None = os.getenv("JWT_SECRET_KEY")
        self.hf_token: str | None = os.getenv("HF_INFERENCE_TOKEN")

        self.database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./enterprise_state.db")
        self.chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "./vectorstore")
        self.chroma_collection: str = os.getenv("CHROMA_COLLECTION", "enterprise_docs")
        self.ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.token_issuer: str = os.getenv("JWT_ISSUER", "enterprise_gateway")
        self.token_audience: str = os.getenv("JWT_AUDIENCE", "enterprise_clients")

        # Access token lifetime in minutes. Default 30 min; override per environment.
        # Use short values in production (15–30), longer ones in local dev (60–120).
        try:
            self.access_token_expire_minutes: int = int(
                os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
            )
        except ValueError:
            raise RuntimeError(
                "CRITICAL BOOT ERROR: ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer."
            )

    def validate(self) -> None:
        """
        Asserts presence and format of required configuration.
        Call this explicitly at application startup — not at import time —
        so tests can construct AppSettings without crashing during collection.
        """
        import re

        # JWT secret — must be present and long enough to resist brute-force
        if self.jwt_secret is None:
            raise RuntimeError(
                "CRITICAL BOOT ERROR: JWT_SECRET_KEY environment variable is not set."
            )
        if len(self.jwt_secret) < 32:
            raise RuntimeError(
                "CRITICAL BOOT ERROR: JWT_SECRET_KEY must be at least 32 characters long."
            )

        # Database dialect whitelist
        if not self.database_url.startswith(("sqlite+aiosqlite://", "postgresql+asyncpg://")):
            raise RuntimeError(
                f"CRITICAL BOOT ERROR: Unsupported database dialect '{self.database_url}'."
            )

        # OLLAMA_URL must be a reachable HTTP(S) endpoint
        if not re.match(r"^https?://", self.ollama_url):
            raise RuntimeError(
                f"CRITICAL BOOT ERROR: OLLAMA_URL '{self.ollama_url}' must be a valid HTTP/HTTPS endpoint."
            )

        # OLLAMA_MODEL must not be blank — a missing model name causes silent LLM failures
        if not self.ollama_model.strip():
            raise RuntimeError(
                "CRITICAL BOOT ERROR: OLLAMA_MODEL must not be blank."
            )

        # CHROMA_PERSIST_DIR must not be blank — an empty path causes silent vectorstore failures
        if not self.chroma_persist_dir.strip():
            raise RuntimeError(
                "CRITICAL BOOT ERROR: CHROMA_PERSIST_DIR must not be blank."
            )

        # Access token expiry must be a sensible positive integer
        if self.access_token_expire_minutes <= 0:
            raise RuntimeError(
                "CRITICAL BOOT ERROR: ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer."
            )


# Instantiated once at module import; validate() is NOT called here.
# Call settings.validate() explicitly at application startup (see app/main.py startup_event).
settings = AppSettings()

# app/security.py
import re
import uuid
import logging
import jwt
import nh3
import time
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from functools import lru_cache
from passlib.context import CryptContext
from sqlalchemy import select
from app.config import settings
from app.database import get_async_db_session, UserEntity, RefreshTokenEntity

ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger("enterprise-agent")

# Cache for authorization results and user lookups
_auth_cache: Dict[str, Dict[str, Any]] = {}
_auth_cache_max_size = 1000
_auth_cache_ttl = 300  # 5 minutes

def _get_cache_key(user_id: str, action: str, resource_id: Optional[str] = None) -> str:
    """Generate cache key for authorization results"""
    return f"auth:{user_id}:{action}:{resource_id or 'none'}"

def _is_cache_valid(cache_entry: Dict[str, Any]) -> bool:
    """Check if cache entry is still valid"""
    return time.time() - cache_entry.get('timestamp', 0) < _auth_cache_ttl

def _cache_get(key: str) -> Optional[bool]:
    """Get authorization result from cache"""
    if key in _auth_cache and _is_cache_valid(_auth_cache[key]):
        return _auth_cache[key]['result']
    return None

def _cache_set(key: str, result: bool) -> None:
    """Set authorization result in cache with TTL"""
    # Simple LRU eviction
    if len(_auth_cache) >= _auth_cache_max_size:
        # Remove oldest entries (simple approach)
        oldest_key = min(_auth_cache.keys(), key=lambda k: _auth_cache[k]['timestamp'])
        del _auth_cache[oldest_key]
    
    _auth_cache[key] = {
        'result': result,
        'timestamp': time.time()
    }

ROLE_PERMISSIONS = {
    "customer": ["VIEW_BALANCE_OWN", "TRANSFER_OWN", "VIEW_POLICY_DOCS"],
    "admin": ["VIEW_BALANCE_ANY", "VIEW_BALANCE_OWN", "TRANSFER_ANY", "TRANSFER_OWN", "AUDIT_READ", "SYSTEM_WRITE", "VIEW_POLICY_DOCS"]
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Async wrapper for password verification to avoid blocking the event loop"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, pwd_context.verify, plain_password, hashed_password)

async def authenticate_user_credentials(user_id: str, password_raw: str) -> Optional[Dict[str, str]]:
    """Validates user password hash against database records, returning user properties if valid."""
    start_time = time.time()
    
    async with get_async_db_session() as db:
        res = await db.execute(select(UserEntity).filter(UserEntity.user_id == user_id))
        user = res.scalars().first()
        if user:
            # Use async password verification to avoid blocking
            if await verify_password_async(password_raw, user.password_hash):
                elapsed = time.time() - start_time
                logger.info(f"Authentication successful for user {user_id} in {elapsed:.3f}s")
                return {"user_id": user_id, "role": user.role}
            else:
                logger.warning(f"Authentication failed for user {user_id}: invalid password")
        else:
            logger.warning(f"Authentication failed for user {user_id}: user not found")
    
    elapsed = time.time() - start_time
    logger.info(f"Authentication failed for user {user_id} in {elapsed:.3f}s")
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token.
    The canonical user identifier is stored in the standard 'sub' claim only.
    'user_id' and 'role' are also included as convenience claims for callers
    that need them without re-querying the database.
    """
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    user_id = str(data.get("user_id") or data.get("sub", ""))
    to_encode = {
        # Standard claims
        "sub": user_id,          # canonical — always use this as the identity key
        "exp": expire,
        "nbf": now - timedelta(seconds=10),
        "iat": now,
        "iss": settings.token_issuer,
        "aud": settings.token_audience,
        # Convenience claims
        "user_id": user_id,      # mirrors sub — kept so ABAC checks don't need sub parsing
        "role":    data.get("role", "customer"),
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)

async def create_and_persist_refresh_token(user_id: str) -> str:
    """Generates and persists an extended refresh token for lifecycle tracking."""
    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    payload = {
        "jti": token_id,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
        "iss": settings.token_issuer,
        "aud": settings.token_audience,
        "sub": user_id,
        "refresh": True
    }
    
    async with get_async_db_session() as db:
        db.add(RefreshTokenEntity(
            token_id=token_id,
            user_id=user_id,
            is_revoked=False,
            expires_at=expires_at
        ))
        await db.commit()
        
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)

async def revoke_refresh_token(token_id: str) -> bool:
    async with get_async_db_session() as db:
        res = await db.execute(select(RefreshTokenEntity).filter(RefreshTokenEntity.token_id == token_id))
        token = res.scalars().first()
        if token:
            token.is_revoked = True
            await db.commit()
            return True
    return False

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates a JWT.  Returns the payload dict on success.

    Returns None on failure and logs the specific failure reason so callers
    can distinguish security events (tampered/unknown) from routine expiry
    without leaking details to the client.

    Failure taxonomy:
      - jwt.ExpiredSignatureError  → token was valid but has expired (refresh candidate)
      - jwt.InvalidTokenError      → tampered, wrong audience/issuer, bad signature, etc.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            audience=settings.token_audience,
            issuer=settings.token_issuer,
        )
    except jwt.ExpiredSignatureError:
        logger.info("JWT rejected: token has expired.")
    except jwt.InvalidAudienceError:
        logger.warning("JWT rejected: audience mismatch — possible misconfiguration or replay attack.")
    except jwt.InvalidIssuerError:
        logger.warning("JWT rejected: issuer mismatch — possible misconfiguration or replay attack.")
    except jwt.DecodeError:
        logger.warning("JWT rejected: malformed token — possible tampering or wrong secret.")
    except jwt.PyJWTError as exc:
        logger.warning("JWT rejected: %s", type(exc).__name__)
    return None

def sanitize_user_input(text: str) -> str:
    """
    Strips all HTML tags and attributes using nh3 (the maintained Rust-backed
    replacement for bleach.clean, which was removed in bleach 6.0).
    Falls back to a simple regex strip if nh3 is unavailable.
    """
    try:
        # nh3.clean() with no allowed_tags strips every tag — identical to
        # bleach.clean(text, tags=[], strip=True) behaviour.
        return nh3.clean(text, tags=set()).strip()
    except Exception:
        # Last-resort regex fallback — should never be reached in production.
        return re.sub(r"<[^>]+>", "", text).strip()

def has_rbac_permission(role: str, action: str) -> bool:
    return action in ROLE_PERMISSIONS.get(role, [])

def has_abac_ownership(user_payload: dict, resource_owner_id: str) -> bool:
    """
    Enhanced ABAC ownership check that properly handles admin privileges.
    Admin users can access any resource regardless of ownership.
    """
    user_id = user_payload.get("user_id")
    role = user_payload.get("role", "customer")
    
    # Admin users have access to all resources
    if role in ["admin", "manager"]:
        logger.debug(f"ABAC: Admin user {user_id} granted access to resource {resource_owner_id}")
        return True
    
    # Regular users can only access their own resources
    has_access = str(user_id) == str(resource_owner_id)
    logger.debug(f"ABAC: User {user_id} {'granted' if has_access else 'denied'} access to resource {resource_owner_id}")
    return has_access

def check_authorization(user_payload: dict, required_action: str, target_resource_id: Optional[str] = None) -> bool:
    """
    Enhanced authorization check with caching and proper admin handling.
    """
    role = user_payload.get("role", "customer")
    user_id = user_payload.get("user_id")
    
    # Check cache first
    cache_key = _get_cache_key(str(user_id), required_action, target_resource_id)
    cached_result = _cache_get(cache_key)
    if cached_result is not None:
        logger.debug(f"Authorization cache hit: {cache_key} -> {cached_result}")
        return cached_result
    
    logger.debug(f"Authorization check: user={user_id}, role={role}, action={required_action}, resource={target_resource_id}")
    
    # First check RBAC permissions
    if not has_rbac_permission(role, required_action):
        logger.debug(f"RBAC denied: role {role} lacks permission for action {required_action}")
        result = False
    else:
        logger.debug(f"RBAC allowed: role {role} has permission for action {required_action}")
        
        # If no specific resource is targeted, RBAC permission is sufficient
        if target_resource_id is None:
            logger.debug("No target resource specified, RBAC permission sufficient")
            result = True
        else:
            # Check ABAC ownership for resource access
            result = has_abac_ownership(user_payload, target_resource_id)
    
    # Cache the result
    _cache_set(cache_key, result)
    
    logger.info(f"Authorization {'granted' if result else 'denied'}: user={user_id}, action={required_action}, resource={target_resource_id}")
    return result
    
    # For resource-specific actions, check ABAC ownership
    if not has_abac_ownership(user_payload, target_resource_id):
        logger.debug(f"ABAC denied: user {user_id} cannot access resource {target_resource_id}")
        return False
    
    logger.debug(f"Authorization granted: user {user_id} can perform {required_action} on resource {target_resource_id}")
    return True
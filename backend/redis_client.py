"""
RiskShield AI - Redis Cache & Client Interface
Handles high-performance in-memory caching, key-value storage, and connection telemetry.
Provides graceful fallback when Redis is offline.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = "redis://localhost:6379/0"

_redis_client = None
_redis_checked = False

def get_redis_client():
    """
    Lazy initialization of Redis client.
    Returns Redis instance if connected, or None if unavailable.
    """
    global _redis_client, _redis_checked
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        import redis
        client = redis.Redis.from_url(REDIS_URL, socket_timeout=1.5, socket_connect_timeout=1.5, protocol=2)
        if client.ping():
            _redis_client = client
            _redis_checked = True
            logger.info("Connected to Redis server at %s", REDIS_URL)
            return _redis_client
    except Exception as e:
        if not _redis_checked:
            logger.warning("Redis server unavailable (%s). Running in synchronous memory fallback mode.", str(e))
            _redis_checked = True
        _redis_client = None

    return None


def is_redis_available() -> bool:
    """Returns True if Redis is online and responding to ping."""
    client = get_redis_client()
    return client is not None


def cache_get(key: str) -> Optional[Any]:
    """Retrieve JSON-deserialized value from Redis cache."""
    client = get_redis_client()
    if not client:
        return None
    try:
        data = client.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
    except Exception as e:
        logger.error("Redis GET error for key %s: %s", key, str(e))
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Store JSON-serialized value in Redis cache with TTL."""
    client = get_redis_client()
    if not client:
        return False
    try:
        serialized = json.dumps(value)
        client.setex(key, ttl_seconds, serialized)
        return True
    except Exception as e:
        logger.error("Redis SET error for key %s: %s", key, str(e))
        return False


def cache_delete(key: str) -> bool:
    """Delete a key from Redis cache."""
    client = get_redis_client()
    if not client:
        return False
    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.error("Redis DELETE error for key %s: %s", key, str(e))
        return False


def cache_clear_pattern(pattern: str = "riskshield:*") -> int:
    """Delete all keys matching pattern."""
    client = get_redis_client()
    if not client:
        return 0
    try:
        keys = client.keys(pattern)
        if keys:
            return client.delete(*keys)
    except Exception as e:
        logger.error("Redis CLEAR pattern error: %s", str(e))
    return 0


def get_redis_telemetry() -> dict:
    """Returns telemetry information about Redis server connection."""
    client = get_redis_client()
    if not client:
        return {
            "status": "OFFLINE",
            "available": False,
            "mode": "Synchronous Fallback",
            "redis_url": REDIS_URL,
            "connected_clients": 0,
            "used_memory_human": "N/A"
        }
    try:
        info = client.info()
        return {
            "status": "ONLINE",
            "available": True,
            "mode": "Redis Distributed Cache & Broker",
            "redis_url": REDIS_URL,
            "redis_version": info.get("redis_version", "unknown"),
            "connected_clients": info.get("connected_clients", 1),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0)
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "available": False,
            "error": str(e),
            "mode": "Synchronous Fallback",
            "redis_url": REDIS_URL
        }

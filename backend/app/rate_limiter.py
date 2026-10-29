"""
P13: Rate limiter persistente con Redis y fallback de desarrollo en memoria.

Arquitectura:
- Cuando REDIS_URL está configurado: usa Redis con Sliding Window (sorted set por IP).
  Seguro para múltiples workers/instancias de uvicorn porque el estado es compartido.
- En desarrollo/test puede usar memoria si Redis no está disponible.
- En producción, Redis es obligatorio y sus fallas bloquean solicitudes protegidas.

Algoritmo: Sliding Window con Redis Sorted Set.
  - Clave: "rl:{ip}" con TTL = ventana de tiempo.
  - Miembros únicos y timestamps en microsegundos como score.
  - Operación atómica: MULTI/EXEC (pipeline) garantiza consistencia bajo carga.
"""
import time
import logging
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from app.config import settings

logger = logging.getLogger("theogen.rate_limiter")
_UNAVAILABLE_DETAIL = "Rate limiting no disponible; la operación fue bloqueada."

# ---------------------------------------------------------------------------
# Intentar conectar con Redis al importar
# ---------------------------------------------------------------------------
_redis_client = None
_redis_available = False


def _init_redis(redis_url: str) -> None:
    """Inicializa el cliente Redis. Llamado desde lifespan de la app."""
    global _redis_client, _redis_available
    if not redis_url:
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("REDIS_URL es obligatoria en producción para rate limiting.")
        logger.warning(
            "P13: REDIS_URL no configurado. El rate limiting usará memoria local — "
            "NO es efectivo con múltiples instancias o workers."
        )
        return
    try:
        import redis as redis_lib
        client = redis_lib.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        _redis_available = True
        logger.info("P13: Rate limiter conectado a Redis.")
    except Exception as exc:
        _redis_client = None
        _redis_available = False
        if settings.ENVIRONMENT == "production":
            raise RuntimeError("Redis no está disponible; inicio bloqueado en producción.") from None
        logger.warning(
            "P13: No se pudo conectar a Redis. Fallback local de desarrollo, sin garantías entre procesos."
        )


# ---------------------------------------------------------------------------
# Backend Redis: Sliding Window con Sorted Set
# ---------------------------------------------------------------------------

def _redis_check(client, ip: str, window: int, max_attempts: int) -> int:
    """
    Desliza la ventana y devuelve el número de intentos en el período actual.
    Usa pipeline para atomicidad. Retorna el conteo actual.
    """
    now_us = int(time.time() * 1_000_000)            # microsegundos
    cutoff_us = now_us - (window * 1_000_000)
    key = f"rl:{ip}"

    pipe = client.pipeline()
    pipe.zremrangebyscore(key, "-inf", cutoff_us)    # Eliminar entradas expiradas
    pipe.zadd(key, {uuid.uuid4().hex: now_us})       # Evitar colisiones de score concurrentes
    pipe.zcard(key)                                   # Contar intentos en ventana
    pipe.expire(key, window)                          # TTL = ventana
    results = pipe.execute()
    return results[2]  # zcard


def _redis_clear(client, ip: str) -> None:
    """Elimina todos los intentos de la IP (login exitoso)."""
    client.delete(f"rl:{ip}")


# ---------------------------------------------------------------------------
# Backend en Memoria: Fallback
# ---------------------------------------------------------------------------
_mem_attempts: dict[str, list[datetime]] = defaultdict(list)


def _mem_check(ip: str, window: int, max_attempts: int) -> int:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window)
    _mem_attempts[ip] = [t for t in _mem_attempts[ip] if t > cutoff]
    _mem_attempts[ip].append(now)
    return len(_mem_attempts[ip])


def _mem_clear(ip: str) -> None:
    _mem_attempts.pop(ip, None)


# ---------------------------------------------------------------------------
# API pública — misma firma que las funciones anteriores de auth.py
# ---------------------------------------------------------------------------

def check_rate_limit(
    client_ip: str,
    window: int = 300,
    max_attempts: int = 10,
) -> None:
    """
    Verifica que la IP no supere max_attempts en los últimos `window` segundos.
    Lanza HTTPException 429 si se supera el límite.
    Usa Redis si está disponible; solo desarrollo/test puede caer a memoria.
    """
    from fastapi import HTTPException

    if _redis_available and _redis_client is not None:
        try:
            count = _redis_check(_redis_client, client_ip, window, max_attempts)
            if count > max_attempts:
                raise HTTPException(
                    status_code=429,
                    detail=f"Demasiados intentos. Intente nuevamente en {window // 60} minutos.",
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("P13: Redis falló durante rate limiting: %s", exc)
            if settings.ENVIRONMENT == "production":
                raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from exc

    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL)

    count = _mem_check(client_ip, window, max_attempts)
    if count > max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intente nuevamente en {window // 60} minutos.",
        )


def record_failed_attempt(client_ip: str, window: int = 300) -> None:
    """
    Compatibilidad con los llamadores existentes.

    check_rate_limit ya cuenta cada solicitud de forma atómica; incrementar otra
    vez aquí duplicaría los fallos y alteraría el umbral según el resultado.
    """
    return None


def clear_failed_attempts(client_ip: str) -> None:
    """Limpia los intentos de la IP al autenticarse exitosamente."""
    if _redis_available and _redis_client is not None:
        try:
            _redis_clear(_redis_client, client_ip)
            return
        except Exception as exc:
            logger.error("P13: Error limpiando intentos en Redis: %s", exc)
            if settings.ENVIRONMENT == "production":
                from fastapi import HTTPException

                raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL) from exc
    if settings.ENVIRONMENT == "production":
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=_UNAVAILABLE_DETAIL)
    _mem_clear(client_ip)

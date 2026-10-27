"""
P13: Rate Limiter Persistente con backend Redis y fallback en memoria.

Arquitectura:
- Cuando REDIS_URL está configurado: usa Redis con Sliding Window (sorted set por IP).
  Seguro para múltiples workers/instancias de uvicorn porque el estado es compartido.
- Cuando Redis no está disponible (fallback): usa el dict en memoria original.
  Emite un WARNING en cada arranque para que el operador no ignore la degradación.

Algoritmo: Sliding Window con Redis Sorted Set.
  - Clave: "rl:{ip}" con TTL = ventana de tiempo.
  - Miembros: timestamps en microsegundos como score.
  - Operación atómica: MULTI/EXEC (pipeline) garantiza consistencia bajo carga.
"""
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

logger = logging.getLogger("theogen.rate_limiter")

# ---------------------------------------------------------------------------
# Intentar conectar con Redis al importar
# ---------------------------------------------------------------------------
_redis_client = None
_redis_available = False


def _init_redis(redis_url: str) -> None:
    """Inicializa el cliente Redis. Llamado desde lifespan de la app."""
    global _redis_client, _redis_available
    if not redis_url:
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
        logger.info("P13: Rate limiter conectado a Redis (%s).", redis_url)
    except Exception as exc:
        logger.warning(
            "P13: No se pudo conectar a Redis (%s): %s. "
            "Usando fallback en memoria — NOT safe for multi-instance deployments.",
            redis_url, exc
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
    pipe.zadd(key, {str(now_us): now_us})            # Añadir intento actual
    pipe.zcard(key)                                   # Contar intentos en ventana
    pipe.expire(key, window)                          # TTL = ventana
    results = pipe.execute()
    return results[2]  # zcard


def _redis_record_failed(client, ip: str, window: int) -> None:
    """Registra un intento fallido (la entrada ya fue añadida en check)."""
    # El intento ya se registró en _redis_check; nada más que hacer aquí.
    pass


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
    Usa Redis si está disponible; fallback a memoria si no.
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
            logger.warning("P13: Error leyendo Redis para rate limiting, usando memoria. %s", exc)

    # Fallback en memoria
    count = _mem_check(client_ip, window, max_attempts)
    if count > max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intente nuevamente en {window // 60} minutos.",
        )


def record_failed_attempt(client_ip: str, window: int = 300) -> None:
    """
    Registra un intento fallido adicional.
    Con Redis el intento ya fue registrado en check_rate_limit; en memoria se añade aquí.
    """
    if _redis_available and _redis_client is not None:
        try:
            # Añade un nuevo timestamp (contador independiente del de check)
            now_us = int(time.time() * 1_000_000)
            key = f"rl:{client_ip}"
            pipe = _redis_client.pipeline()
            pipe.zadd(key, {str(now_us) + "f": now_us})
            pipe.expire(key, window)
            pipe.execute()
            return
        except Exception as exc:
            logger.warning("P13: Error registrando intento fallido en Redis. %s", exc)

    # Fallback
    _mem_attempts[client_ip].append(datetime.now(timezone.utc))


def clear_failed_attempts(client_ip: str) -> None:
    """Limpia los intentos de la IP al autenticarse exitosamente."""
    if _redis_available and _redis_client is not None:
        try:
            _redis_clear(_redis_client, client_ip)
            return
        except Exception as exc:
            logger.warning("P13: Error limpiando intentos en Redis. %s", exc)
    _mem_clear(client_ip)

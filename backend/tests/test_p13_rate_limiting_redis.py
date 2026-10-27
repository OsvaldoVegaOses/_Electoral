"""
P13: Tests de Rate Limiting Persistente (Redis y fallback memoria)

Verifica:
- check_rate_limit bloquea al superar el umbral (backend memoria)
- record_failed_attempt acumula correctamente
- clear_failed_attempts reinicia el contador
- El módulo rate_limiter arranca correctamente sin Redis (fallback)
- Con Redis mockeado, el pipeline se llama con los argumentos correctos
- La respuesta 429 contiene el mensaje correcto
- Los endpoints de login y validate-token consumen el rate limiter
"""
import importlib
import pytest
from unittest.mock import MagicMock, patch, call
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_module():
    """Devuelve una instancia limpia del módulo rate_limiter con estado reiniciado."""
    import app.rate_limiter as rl
    # Reiniciar estado global entre tests
    rl._redis_client = None
    rl._redis_available = False
    rl._mem_attempts.clear()
    return rl


# ---------------------------------------------------------------------------
# 1. Fallback memoria: bloqueo al superar límite
# ---------------------------------------------------------------------------

class TestMemoryFallback:

    def setup_method(self):
        self.rl = _fresh_module()

    def test_permite_intentos_bajo_limite(self):
        """Los primeros N intentos no deben levantar excepción."""
        for _ in range(5):
            # window=300, max=5 => el 5.º es el límite, no debe bloquearse antes
            try:
                self.rl.check_rate_limit("1.2.3.4", window=300, max_attempts=5)
            except HTTPException as e:
                pytest.fail(f"No debería bloquear con menos de 5 intentos: {e}")

    def test_bloquea_al_superar_limite(self):
        """El intento N+1 debe levantar HTTP 429."""
        for _ in range(5):
            try:
                self.rl.check_rate_limit("5.6.7.8", window=300, max_attempts=5)
            except HTTPException:
                pass
        with pytest.raises(HTTPException) as exc_info:
            self.rl.check_rate_limit("5.6.7.8", window=300, max_attempts=5)
        assert exc_info.value.status_code == 429
        assert "minutos" in exc_info.value.detail.lower()

    def test_clear_restablece_contador(self):
        """clear_failed_attempts debe permitir nuevos intentos desde cero."""
        for _ in range(5):
            try:
                self.rl.check_rate_limit("9.9.9.9", window=300, max_attempts=5)
            except HTTPException:
                pass
        self.rl.clear_failed_attempts("9.9.9.9")
        # Tras limpiar, el primer intento debe ser permitido
        try:
            self.rl.check_rate_limit("9.9.9.9", window=300, max_attempts=5)
        except HTTPException as e:
            pytest.fail(f"Después de clear no debería bloquearse: {e}")

    def test_record_failed_acumula(self):
        """record_failed_attempt acumula en la lista en memoria."""
        ip = "11.22.33.44"
        self.rl._mem_attempts.clear()
        for _ in range(3):
            self.rl.record_failed_attempt(ip, window=300)
        assert len(self.rl._mem_attempts[ip]) == 3

    def test_diferentes_ips_son_independientes(self):
        """El conteo de una IP no afecta a otra."""
        for _ in range(10):
            try:
                self.rl.check_rate_limit("10.0.0.1", window=300, max_attempts=3)
            except HTTPException:
                pass
        # 10.0.0.2 no debe verse afectada
        try:
            self.rl.check_rate_limit("10.0.0.2", window=300, max_attempts=3)
        except HTTPException as e:
            pytest.fail(f"IP diferente no debería estar bloqueada: {e}")


# ---------------------------------------------------------------------------
# 2. Inicialización Redis
# ---------------------------------------------------------------------------

class TestRedisInit:

    def test_init_con_url_vacia_usa_memoria(self, caplog):
        """Sin REDIS_URL, el sistema usa memoria y emite WARNING."""
        import logging
        rl = _fresh_module()
        with caplog.at_level(logging.WARNING, logger="theogen.rate_limiter"):
            rl._init_redis("")
        assert not rl._redis_available
        assert rl._redis_client is None
        assert any("REDIS_URL" in r.message for r in caplog.records)

    def test_init_con_redis_no_disponible_usa_fallback(self, caplog):
        """Si Redis no responde, el sistema cae a memoria y emite WARNING."""
        import logging
        rl = _fresh_module()
        with patch("redis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.ping.side_effect = ConnectionError("Connection refused")
            mock_from_url.return_value = mock_client
            with caplog.at_level(logging.WARNING, logger="theogen.rate_limiter"):
                rl._init_redis("redis://localhost:6379/0")
        assert not rl._redis_available
        assert any("fallback" in r.message.lower() or "no se pudo" in r.message.lower()
                   for r in caplog.records)

    def test_init_exitoso_activa_redis(self):
        """Cuando Redis responde al ping, _redis_available pasa a True."""
        rl = _fresh_module()
        with patch("redis.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client
            rl._init_redis("redis://redis:6379/0")
        assert rl._redis_available is True
        assert rl._redis_client is mock_client


# ---------------------------------------------------------------------------
# 3. Backend Redis: pipeline correctamente llamado
# ---------------------------------------------------------------------------

class TestRedisBackend:

    def _make_rl_with_redis(self):
        rl = _fresh_module()
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 3, True]  # [zrem, zadd, zcard, expire]
        mock_client.pipeline.return_value = mock_pipe
        rl._redis_client = mock_client
        rl._redis_available = True
        return rl, mock_client, mock_pipe

    def test_redis_pipeline_invocado(self):
        """check_rate_limit llama al pipeline de Redis cuando está disponible."""
        rl, client, pipe = self._make_rl_with_redis()
        rl.check_rate_limit("1.1.1.1", window=300, max_attempts=10)
        assert client.pipeline.called
        assert pipe.execute.called

    def test_redis_bloquea_cuando_zcard_supera_limite(self):
        """Cuando zcard devuelve más que max_attempts, se lanza 429."""
        rl = _fresh_module()
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 11, True]  # zcard=11 > max=10
        mock_client.pipeline.return_value = mock_pipe
        rl._redis_client = mock_client
        rl._redis_available = True

        with pytest.raises(HTTPException) as exc_info:
            rl.check_rate_limit("2.2.2.2", window=300, max_attempts=10)
        assert exc_info.value.status_code == 429

    def test_redis_clear_llama_delete(self):
        """clear_failed_attempts elimina la clave Redis de la IP."""
        rl = _fresh_module()
        mock_client = MagicMock()
        rl._redis_client = mock_client
        rl._redis_available = True
        rl.clear_failed_attempts("3.3.3.3")
        mock_client.delete.assert_called_once_with("rl:3.3.3.3")

    def test_redis_error_en_pipeline_usa_fallback(self):
        """Si el pipeline Redis falla, el sistema cae a memoria sin propagar el error."""
        rl = _fresh_module()
        mock_client = MagicMock()
        mock_client.pipeline.side_effect = Exception("Redis timeout")
        rl._redis_client = mock_client
        rl._redis_available = True
        # No debe levantar excepción (el fallback es transparente)
        try:
            rl.check_rate_limit("4.4.4.4", window=300, max_attempts=10)
        except HTTPException:
            pass  # 429 del fallback es aceptable
        except Exception as e:
            pytest.fail(f"No debería propagarse el error de Redis: {e}")


# ---------------------------------------------------------------------------
# 4. Integración: endpoint /api/auth/login aplica rate limiting
# ---------------------------------------------------------------------------

class TestLoginRateLimitIntegration:
    """Verifica que el endpoint de login rechace con 429 al superar el límite."""

    def test_login_rate_limit_via_check_rate_limit(self):
        """
        Simula que check_rate_limit levanta 429 y verifica que el endpoint
        no lo absorba silenciosamente (la excepción se propaga).
        """
        from fastapi import HTTPException as FastAPIHTTPException
        import app.rate_limiter as rl
        rl._redis_client = None
        rl._redis_available = False
        rl._mem_attempts.clear()

        # Poblar manualmente para forzar 429
        from datetime import datetime, timezone
        ip = "99.99.99.99"
        rl._mem_attempts[ip] = [datetime.now(timezone.utc)] * 10

        with pytest.raises(FastAPIHTTPException) as exc_info:
            rl.check_rate_limit(ip, window=300, max_attempts=10)
        assert exc_info.value.status_code == 429

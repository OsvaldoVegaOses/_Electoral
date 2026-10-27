import sys
import os
import unittest
import hmac
import hashlib
from datetime import datetime, timezone

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.auth import (
    create_access_token, verify_password, get_password_hash,
    check_rate_limit, record_failed_attempt, clear_failed_attempts,
    _failed_attempts
)
from app.schemas import UserLogin, UserCreate
from app.routers.audit import _escape_like as audit_escape_like
from app.routers.voters import _escape_like as voters_escape_like, MAX_UPLOAD_SIZE_BYTES
from app.routers.elections import VALID_STATE_TRANSITIONS
from pydantic import ValidationError
from jose import jwt


class TestSecurityFixes(unittest.TestCase):

    def test_crit_02_rate_limiting(self):
        """CRIT-02: Rate limiter blocks client after 10 failed attempts and clears on success"""
        test_ip = "192.168.1.99"
        clear_failed_attempts(test_ip)
        
        # 9 failed attempts should not raise
        for _ in range(9):
            record_failed_attempt(test_ip)
        check_rate_limit(test_ip)
        
        # 10th failed attempt should trigger 429
        record_failed_attempt(test_ip)
        with self.assertRaises(Exception) as ctx:
            check_rate_limit(test_ip)
        self.assertEqual(ctx.exception.status_code, 429)
        
        # Clearing attempts resets the limit
        clear_failed_attempts(test_ip)
        check_rate_limit(test_ip)

    def test_crit_05_hmac_integrity_hash(self):
        """CRIT-05: HMAC-SHA256 calculation for vote integrity"""
        key = settings.VOTE_HMAC_KEY or "test_key"
        seed = "voter-1-cand-2-2026-10-27T08:00:00Z"
        computed_hmac = hmac.new(
            key.encode("utf-8"),
            seed.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        self.assertEqual(len(computed_hmac), 64)
        # Verify it cannot match plain sha256
        plain_sha256 = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        self.assertNotEqual(computed_hmac, plain_sha256)

    def test_high_01_timezone_awareness(self):
        """HIGH-01: Timezone-aware datetimes used across the system"""
        from app.models import _utcnow
        now = _utcnow()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_high_02_state_transitions(self):
        """HIGH-02: State machine validation for elections"""
        self.assertIn("Abierta", VALID_STATE_TRANSITIONS["Borrador"])
        self.assertNotIn("Cerrada", VALID_STATE_TRANSITIONS["Borrador"])
        self.assertIn("Cerrada", VALID_STATE_TRANSITIONS["Abierta"])
        self.assertNotIn("Borrador", VALID_STATE_TRANSITIONS["Abierta"])
        self.assertEqual(VALID_STATE_TRANSITIONS["Finalizada"], [])

    def test_high_04_password_validation(self):
        """HIGH-04: Password complexity enforced in schemas for user creation without locking login"""
        # Valid password (>=8 chars, with letter and digit)
        valid = UserCreate(nombre="Test User", email="user@test.cl", password="StrongPassword123")
        self.assertEqual(valid.email, "user@test.cl")

        # Invalid: too short
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="user@test.cl", password="short1")

        # Invalid: no numbers
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="user@test.cl", password="OnlyLettersHere")

        # Invalid: no letters
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="user@test.cl", password="1234567890")

        # UserLogin allows legacy credentials without artificial blocking
        login_compat = UserLogin(email="user@test.cl", password="legacy")
        self.assertEqual(login_compat.password, "legacy")

    def test_med_02_file_upload_limit(self):
        """MED-02: File upload limit set to 10MB"""
        self.assertEqual(MAX_UPLOAD_SIZE_BYTES, 10 * 1024 * 1024)

    def test_med_03_wildcard_escaping(self):
        """MED-03: SQL LIKE/ILIKE wildcards % and _ are escaped"""
        self.assertEqual(audit_escape_like("100%_safe"), r"100\%\_safe")
        self.assertEqual(voters_escape_like("test%user_name"), r"test\%user\_name")

    def test_low_01_jwt_jti_inclusion(self):
        """LOW-01: JWT access token includes jti claim for revocability"""
        token = create_access_token({"sub": "admin@theogen.cl", "rol": "Administrador"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        self.assertIn("jti", payload)
        self.assertIn("exp", payload)
        self.assertEqual(payload["sub"], "admin@theogen.cl")
        # Ensure separate tokens get distinct jti
        token2 = create_access_token({"sub": "admin@theogen.cl", "rol": "Administrador"})
        payload2 = jwt.decode(token2, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        self.assertNotEqual(payload["jti"], payload2["jti"])


if __name__ == "__main__":
    unittest.main()

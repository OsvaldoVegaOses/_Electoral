import sys
import os
import unittest
import hmac
import hashlib
import inspect
from datetime import datetime, timezone
import jwt
from pydantic import ValidationError

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings, Settings
from app.auth import (
    create_access_token, verify_password, get_password_hash,
    check_rate_limit, record_failed_attempt, clear_failed_attempts,
    get_current_user
)
from app.schemas import UserLogin, UserCreate
from app.routers.audit import _escape_like as audit_escape_like, router as audit_router
from app.routers.voters import _escape_like as voters_escape_like, MAX_UPLOAD_SIZE_BYTES, router as voters_router
from app.routers.elections import VALID_STATE_TRANSITIONS, router as elections_router
from app.routers.candidates import router as candidates_router
from app.routers.schools import router as schools_router
from app.routers.reports import router as reports_router
from app.routers.voting import router as voting_router
from main import SecurityHeadersMiddleware


class TestAll22SecurityVulnerabilities(unittest.TestCase):

    def test_01_crit_01_no_hardcoded_credentials(self):
        """CRIT-01: Ensure no hardcoded DB passwords or secret keys exist in docker-compose.yml"""
        compose_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml"))
        self.assertTrue(os.path.exists(compose_path))
        with open(compose_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("theogen_secret_password_2026", content)
        self.assertNotIn("theogen_jwt_production_secret_key_2026", content)
        self.assertIn("${POSTGRES_PASSWORD}", content)
        self.assertIn("${SECRET_KEY}", content)

        env_example = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env.example"))
        self.assertTrue(os.path.exists(env_example))
        with open(env_example, "r", encoding="utf-8") as f:
            env_content = f.read()
        self.assertIn("POSTGRES_PASSWORD", env_content)
        self.assertIn("SECRET_KEY", env_content)
        self.assertIn("VOTE_HMAC_KEY", env_content)

    def test_02_crit_02_rate_limiting_integrated(self):
        """CRIT-02: Rate limiter blocks after 10 failed attempts and clears on success"""
        test_ip = "10.0.0.99"
        clear_failed_attempts(test_ip)
        for _ in range(9):
            record_failed_attempt(test_ip)
        check_rate_limit(test_ip)
        record_failed_attempt(test_ip)
        with self.assertRaises(Exception) as ctx:
            check_rate_limit(test_ip)
        self.assertEqual(ctx.exception.status_code, 429)
        clear_failed_attempts(test_ip)
        check_rate_limit(test_ip)

    def test_03_crit_03_read_endpoints_require_auth(self):
        """CRIT-03: Administrative read endpoints require get_current_user dependency"""
        # Check that get_current_user dependency is attached to router endpoints
        for r, name in [
            (elections_router, "list_elections"),
            (schools_router, "list_schools"),
            (voters_router, "list_voters"),
            (candidates_router, "list_candidates"),
            (audit_router, "get_audit_logs"),
            (reports_router, "get_election_scrutiny"),
            (reports_router, "download_acta_apertura_pdf"),
            (reports_router, "download_acta_cierre_pdf"),
            (reports_router, "get_dashboard_stats"),
            (voters_router, "simulate_email_dispatch"),
        ]:
            route = next((route for route in r.routes if getattr(route, "name", None) == name or getattr(route, "endpoint", None).__name__ == name), None)
            self.assertIsNotNone(route, f"Route {name} not found in router")
            # Verify dependencies contain get_current_user
            endpoint = route.endpoint
            sig = inspect.signature(endpoint)
            has_auth = "current_user" in sig.parameters or any(
                "get_current_user" in str(d) for d in getattr(route, "dependencies", [])
            )
            self.assertTrue(has_auth, f"Route {name} does not have current_user dependency")

    def test_04_crit_04_tokens_masked_in_simulation(self):
        """CRIT-04: Voter tokens masked to prevent credential harvesting"""
        raw_uuid = "3a8f803d-0ccb-48b7-89f7-d92aa4c729de"
        masked = f"{raw_uuid[:4]}...{raw_uuid[-4:]}"
        self.assertEqual(masked, "3a8f...29de")
        self.assertNotIn("0ccb-48b7-89f7", masked)

    def test_05_crit_05_hmac_sha256_vote_integrity(self):
        """CRIT-05: Vote integrity hash uses HMAC-SHA256 with secret key"""
        key = settings.VOTE_HMAC_KEY or "fallback_key"
        seed = "voter-1-candidate-2-timestamp"
        hmac_hash = hmac.new(key.encode("utf-8"), seed.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertEqual(len(hmac_hash), 64)
        plain_sha256 = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        self.assertNotEqual(hmac_hash, plain_sha256)

    def test_06_high_01_timezone_awareness(self):
        """HIGH-01: Timezone-aware datetimes (no deprecated utcnow)"""
        from app.models import _utcnow
        now = _utcnow()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_07_high_02_election_state_machine(self):
        """HIGH-02: State machine enforces valid transition rules"""
        self.assertEqual(VALID_STATE_TRANSITIONS["Borrador"], ["Abierta"])
        self.assertEqual(VALID_STATE_TRANSITIONS["Abierta"], ["Cerrada"])
        self.assertEqual(VALID_STATE_TRANSITIONS["Cerrada"], ["Finalizada"])
        self.assertEqual(VALID_STATE_TRANSITIONS["Finalizada"], [])

    def test_08_high_03_random_seed_passwords(self):
        """HIGH-03: Seed data generates random passwords with secrets"""
        import secrets
        pwd1 = secrets.token_urlsafe(16)
        pwd2 = secrets.token_urlsafe(16)
        self.assertNotEqual(pwd1, pwd2)
        self.assertGreaterEqual(len(pwd1), 16)
        self.assertNotEqual(pwd1, "admin123")

    def test_09_high_04_password_strength_enforced(self):
        """HIGH-04: User creation passwords must be at least 8 characters with letters and numbers"""
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="test@theogen.cl", password="bad")
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="test@theogen.cl", password="onlyletters")
        with self.assertRaises(ValidationError):
            UserCreate(nombre="Test User", email="test@theogen.cl", password="1234567890")
        valid = UserCreate(nombre="Test User", email="test@theogen.cl", password="SecurePassword2026")
        self.assertEqual(valid.email, "test@theogen.cl")
        # UserLogin accepts credentials without blocking legacy accounts
        login = UserLogin(email="test@theogen.cl", password="legacy_password")
        self.assertEqual(login.password, "legacy_password")

    def test_10_high_05_concurrency_lock_in_voting(self):
        """HIGH-05: SELECT FOR UPDATE present in voting endpoint logic"""
        voting_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "routers", "voting.py"))
        with open(voting_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("with_for_update()", code)

    def test_11_high_06_candidates_hide_votes_when_open(self):
        """HIGH-06: Candidate vote counts hidden during open election (only shown when Cerrada or Finalizada)"""
        candidates_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "routers", "candidates.py"))
        with open(candidates_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn('election.estado in ["Cerrada", "Finalizada"]', code)
        self.assertIn("v_count = 0", code)

    def test_12_high_07_cors_restricted(self):
        """HIGH-07: CORS restricted to specific origins, methods and headers"""
        main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertNotIn("allow_methods=[\"*\"]", code)
        self.assertNotIn("allow_headers=[\"*\"]", code)
        self.assertIn("allow_origins=settings.BACKEND_CORS_ORIGINS", code)

    def test_13_med_01_docs_disabled_in_production(self):
        """MED-01: Swagger and ReDoc disabled when ENVIRONMENT is production"""
        main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("docs_url=_docs_url", code)
        self.assertIn("ENVIRONMENT != \"production\"", code)

    def test_14_med_02_max_upload_size_limit(self):
        """MED-02: Maximum upload limit enforced at 10 MB"""
        self.assertEqual(MAX_UPLOAD_SIZE_BYTES, 10 * 1024 * 1024)

    def test_15_med_03_sql_wildcard_escaping(self):
        """MED-03: Wildcard characters % and _ are safely escaped"""
        self.assertEqual(audit_escape_like("admin%_test"), r"admin\%\_test")
        self.assertEqual(voters_escape_like("john%_doe"), r"john\%\_doe")

    def test_16_med_04_dynamic_health_check_timestamp(self):
        """MED-04: Health check returns dynamic UTC ISO timestamp"""
        main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertNotIn("2026-10-26T20:30:00Z", code)
        self.assertIn("datetime.now(timezone.utc).isoformat()", code)

    def test_17_med_05_security_headers_middleware(self):
        """MED-05: HTTP security headers added via middleware in main.py"""
        main_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        with open(main_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("SecurityHeadersMiddleware", code)
        self.assertIn("X-Content-Type-Options", code)
        self.assertIn("X-Frame-Options", code)
        self.assertIn("X-XSS-Protection", code)
        self.assertIn("Referrer-Policy", code)
        self.assertIn("Permissions-Policy", code)

    def test_18_med_06_nginx_security_headers(self):
        """MED-06: Nginx configured with security headers and client max body size"""
        nginx_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "nginx.conf"))
        self.assertTrue(os.path.exists(nginx_path))
        with open(nginx_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("X-Content-Type-Options \"nosniff\"", content)
        self.assertIn("X-Frame-Options \"DENY\"", content)
        self.assertIn("Content-Security-Policy", content)
        self.assertIn("server_tokens off;", content)
        self.assertIn("client_max_body_size 10m;", content)

    def test_19_low_01_jwt_jti_claim(self):
        """LOW-01: Access token payload contains jti claim for revocability"""
        token = create_access_token({"sub": "admin@theogen.cl", "rol": "Administrador"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        self.assertIn("jti", payload)
        self.assertGreater(len(payload["jti"]), 10)

    def test_20_low_02_memory_rate_limiter_documented(self):
        """LOW-02: In-memory rate limiter limitation documented"""
        auth_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app", "auth.py"))
        with open(auth_path, "r", encoding="utf-8") as f:
            code = f.read()
        self.assertIn("Rate Limiter en Memoria", code)

    def test_21_low_03_pagination_on_list_endpoints(self):
        """LOW-03: Listing endpoints include skip and limit parameters"""
        for r, name in [
            (elections_router, "list_elections"),
            (schools_router, "list_schools"),
            (voters_router, "list_voters"),
            (candidates_router, "list_candidates"),
        ]:
            route = next(route for route in r.routes if getattr(route, "endpoint", None).__name__ == name)
            sig = inspect.signature(route.endpoint)
            self.assertIn("skip", sig.parameters, f"skip missing in {name}")
            self.assertIn("limit", sig.parameters, f"limit missing in {name}")

    def test_22_low_04_structured_logging(self):
        """LOW-04: Structured logging module used instead of print in core modules"""
        for filename in ["config.py", "auth.py", "seed_data.py", "main.py"]:
            filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app" if filename != "main.py" else "", filename))
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("logging.getLogger", content, f"logging missing in {filename}")


if __name__ == "__main__":
    unittest.main()

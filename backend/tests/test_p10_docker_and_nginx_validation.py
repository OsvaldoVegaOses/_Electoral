import os
import re
import subprocess
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestP10DockerComposeAndNginxValidation(unittest.TestCase):
    """
    Batería de pruebas automatizadas para P10:
    - Validación de sintaxis e interpolación de docker-compose.yml (desarrollo)
    - Validación de sintaxis e interpolación de docker-compose.prod.yml (producción)
    - Validación de sintaxis y directivas de seguridad de nginx-ssl.conf
    """

    def test_01_docker_compose_root_config_syntax(self):
        """Verifica que docker compose config compile sin errores en el archivo raíz"""
        res = subprocess.run(
            ["docker", "compose", "config"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True
        )
        self.assertEqual(
            res.returncode, 0,
            f"Error validando docker-compose.yml: {res.stderr}\n{res.stdout}"
        )
        self.assertIn("theogen-electoral", res.stdout)
        self.assertIn("theogen_backend", res.stdout)
        self.assertIn("theogen_db", res.stdout)
        self.assertIn("theogen_frontend", res.stdout)

    def test_02_docker_compose_prod_config_syntax(self):
        """Verifica que docker compose -f doc/templates/docker-compose.prod.yml config compile sin errores"""
        prod_compose_path = os.path.join(ROOT_DIR, "doc", "templates", "docker-compose.prod.yml")
        self.assertTrue(os.path.exists(prod_compose_path), "Falta archivo docker-compose.prod.yml")

        res = subprocess.run(
            ["docker", "compose", "-f", prod_compose_path, "config"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True,
            env={**os.environ,
                 "DATABASE_URL": "postgresql://synthetic_app:unused@db/synthetic",
                 "MIGRATION_DATABASE_URL": "postgresql://synthetic_migrator:unused@db/synthetic"},
        )
        self.assertEqual(
            res.returncode, 0,
            f"Error validando docker-compose.prod.yml: {res.stderr}\n{res.stdout}"
        )
        self.assertIn("theogen_backend", res.stdout)
        self.assertIn("theogen_db", res.stdout)
        self.assertIn("theogen_frontend", res.stdout)

    def test_03_nginx_ssl_conf_security_and_syntax(self):
        """Verifica que nginx-ssl.conf tenga sintaxis balanceada y todas las cabeceras de seguridad requeridas"""
        nginx_path = os.path.join(ROOT_DIR, "doc", "templates", "nginx-ssl.conf")
        self.assertTrue(os.path.exists(nginx_path), "Falta archivo nginx-ssl.conf")

        with open(nginx_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Comprobar balanceo de llaves {}
        open_braces = content.count("{")
        close_braces = content.count("}")
        self.assertEqual(open_braces, close_braces, f"Desbalance de llaves en Nginx: {open_braces} != {close_braces}")

        # 2. Rate limiting zones
        self.assertIn("zone=general_limit:10m", content)
        self.assertIn("zone=vote_limit:10m", content)
        self.assertIn("zone=auth_limit:10m", content)

        # 3. Redirección HTTP -> HTTPS
        self.assertIn("return 301 https://$host$request_uri;", content)

        # 4. Protocolos y cifrados TLS seguros
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3;", content)
        self.assertIn("server_tokens off;", content)

        # 5. Cabeceras de seguridad HTTP
        self.assertIn("Strict-Transport-Security", content)
        self.assertIn("X-Content-Type-Options \"nosniff\"", content)
        self.assertIn("X-Frame-Options \"DENY\"", content)
        self.assertIn("X-XSS-Protection \"1; mode=block\"", content)
        self.assertIn("Referrer-Policy \"strict-origin-when-cross-origin\"", content)
        self.assertIn("Content-Security-Policy", content)

        # 6. Proxy locations críticas
        self.assertIn("location /api/voting/submit", content)
        self.assertIn("location /api/voting/validate-token", content)
        self.assertIn("location /api/auth/login", content)
        self.assertIn("location /api/", content)
        self.assertIn("client_max_body_size 15M;", content)


if __name__ == "__main__":
    unittest.main()

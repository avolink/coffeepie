"""Authentication and authorisation guarantees of the root backend (coffeepie_backend/app).

Run from coffeepie_backend/:
  python3 -m unittest tests.test_security

No database or network needed: user lookup is replaced with an in-memory fake.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

STRONG_SECRET = "k8D2fQ9xLm4ZpV7sT1wB6nR3yH0cJ5aE8uG2dX4iO9qM"
os.environ.update({
    "JWT_SECRET_KEY": STRONG_SECRET,
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": "60",
    "DOCS_API_KEY": "a-long-random-docs-key-for-tests",
    "MONGO_URI": "mongodb://127.0.0.1:1",
    "MONGO_DB_NAME": "test",
    "ADMIN_EMAILS": "admin@example.com",
})

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.main import app  # noqa: E402
from app.core import ratelimit  # noqa: E402

USERS = {
    "u1": {"_id": "u1", "email": "user@example.com", "name": "U", "companyID": "c1"},
    "u2": {"_id": "u2", "email": "other@example.com", "name": "O", "companyID": "c2"},
    "adm": {"_id": "adm", "email": "admin@example.com", "name": "A", "companyID": None},
}


async def fake_get_user_by_id(uid):
    return USERS.get(uid)


def token_for(uid):
    return jwt.encode({"sub": uid}, STRONG_SECRET, algorithm="HS256")


FULL_UPDATE = {"name": None, "email": None, "type": None, "companyID": None,
               "age": None, "city": None, "occupation": None, "portions": None}


def update_body(**changes):
    return {**FULL_UPDATE, **changes}


def bearer(uid):
    return {"Authorization": f"Bearer {token_for(uid)}"}


class RootBackendSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._patch = mock.patch("app.core.security.get_user_by_id", fake_get_user_by_id)
        cls._patch.start()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()

    # ---- anonymous callers get nothing -------------------------------------
    def test_anonymous_requests_are_rejected(self):
        c = self.client
        for method, path in [
            ("get", "/nodes"), ("get", "/nodes/pve/vms"), ("post", "/clone-by-name"),
            ("delete", "/nodes/pve/vms/x"), ("get", "/nodes/pve/vms/x/vnc"),
            ("post", "/sunshine/send-pin"), ("get", "/console-url"),
            ("get", "/companies/"), ("get", "/companies/c1"), ("delete", "/companies/c1"),
            ("patch", "/companies/company/c1/portions?portions=100"),
            ("get", "/users/"), ("put", "/users/u1"), ("delete", "/users/u1"),
            ("get", "/snapshots/"), ("delete", "/snapshots/abc"),
            ("get", "/terminals/"),
        ]:
            with self.subTest(route=f"{method.upper()} {path}"):
                r = getattr(c, method)(path)
                self.assertIn(r.status_code, (401, 403, 422),
                              f"{method.upper()} {path} answered {r.status_code}")
                self.assertNotEqual(r.status_code, 200)

    def test_forged_token_is_rejected(self):
        forged = jwt.encode({"sub": "adm"}, "not-the-real-secret-not-the-real-secret", algorithm="HS256")
        r = self.client.get("/users/", headers={"Authorization": f"Bearer {forged}"})
        self.assertEqual(r.status_code, 401)

    def test_token_for_unknown_user_is_rejected(self):
        r = self.client.get("/users/me", headers=bearer("ghost"))
        self.assertEqual(r.status_code, 401)

    def test_legacy_query_token_still_authenticates(self):
        # the Qt terminal sends ?token=; it must not stop working
        r = self.client.get(f"/users/?token={token_for('u1')}")
        self.assertEqual(r.status_code, 403)  # authenticated, but not an admin

    # ---- ordinary users cannot reach admin or other people's data ---------
    def test_plain_user_cannot_use_admin_routes(self):
        h = bearer("u1")
        for method, path in [
            ("get", "/users/"), ("get", "/companies/"), ("delete", "/nodes/pve/vms/x"),
            ("post", "/sunshine/send-pin"), ("get", "/snapshots/"), ("get", "/terminals/"),
            ("patch", "/companies/company/c1/portions?portions=100"),
        ]:
            with self.subTest(route=f"{method.upper()} {path}"):
                r = getattr(self.client, method)(path, headers=h)
                self.assertEqual(r.status_code, 403, f"{method.upper()} {path} answered {r.status_code}")

    def test_user_cannot_modify_or_delete_someone_else(self):
        h = bearer("u1")
        self.assertEqual(self.client.put("/users/u2", json=update_body(name="x"), headers=h).status_code, 403)
        self.assertEqual(self.client.delete("/users/u2", headers=h).status_code, 403)

    def test_user_cannot_grant_themselves_credits_or_company(self):
        h = bearer("u1")
        for body in ({"portions": 999999}, {"companyID": "c2"}, {"type": "company"}, {"email": "x@y.co"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.put("/users/u1", json=update_body(**body), headers=h).status_code, 403)

    def test_user_cannot_read_another_company(self):
        h = bearer("u1")
        self.assertEqual(self.client.get("/companies/c2", headers=h).status_code, 403)
        self.assertEqual(self.client.get("/companies/c2/users", headers=h).status_code, 403)

    def test_admin_passes_the_admin_gate(self):
        # Reaches the handler (and fails later on the absent database), but is
        # not turned away at the door.
        async def fake_list():
            return []
        with mock.patch("app.api.users.crud_list_users", fake_list):
            r = self.client.get("/users/", headers=bearer("adm"))
        self.assertEqual(r.status_code, 200)

    # ---- throttling ---------------------------------------------------------
    def test_login_is_throttled(self):
        ratelimit.reset()
        async def no_user(email, password):
            return None
        with mock.patch("app.api.auth_routes.auth_service.authenticate_user", no_user):
            codes = [self.client.post("/auth/login", json={"email": "v@example.com", "password": str(i)}).status_code
                     for i in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5:], [429, 429])
        ratelimit.reset()

    # ---- password reset must not leak ------------------------------------
    def test_forgot_password_never_returns_a_link(self):
        ratelimit.reset()
        r = self.client.post("/auth/forgot-password", json={"email": "user@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("reset_link", r.text)
        r2 = self.client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
        self.assertEqual(r.json(), r2.json())

    # ---- docs key ---------------------------------------------------------
    def test_docs_need_the_configured_key(self):
        self.assertEqual(self.client.get("/openapi.json").status_code, 403)
        self.assertEqual(self.client.get("/openapi.json?key=your-docs-key").status_code, 403)


class StartupGuards(unittest.TestCase):
    def run_import(self, code, **env):
        e = {k: v for k, v in os.environ.items() if k not in ("JWT_SECRET_KEY", "DOCS_API_KEY")}
        e.update({"JWT_ALGORITHM": "HS256", "JWT_EXPIRE_MINUTES": "60", "MONGO_URI": "mongodb://127.0.0.1:1",
                  "MONGO_DB_NAME": "t", "PYTHONPATH": str(BACKEND)})
        e.update(env)
        return subprocess.run([sys.executable, "-c", code], env=e, cwd=BACKEND,
                              capture_output=True, text=True)

    def test_refuses_weak_jwt_secret(self):
        for weak in ("", "secret", "short", "your-super-secret-jwt-key-change-this-in-production"):
            with self.subTest(secret=weak):
                p = self.run_import("import app.core.security", JWT_SECRET_KEY=weak)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("JWT_SECRET_KEY", p.stderr)

    def test_accepts_strong_jwt_secret(self):
        p = self.run_import("import app.core.security", JWT_SECRET_KEY=STRONG_SECRET)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_refuses_default_docs_key(self):
        for weak in ("", "your-docs-key"):
            with self.subTest(key=weak):
                p = self.run_import("import app.main", JWT_SECRET_KEY=STRONG_SECRET, DOCS_API_KEY=weak)
                self.assertNotEqual(p.returncode, 0)
                self.assertIn("DOCS_API_KEY", p.stderr)


class SunshineTargetGuard(unittest.TestCase):
    def setUp(self):
        from app.services import net_guard
        self.g = net_guard
        self._env = mock.patch.dict(os.environ, {"SUNSHINE_ALLOWED_NETWORKS": "10.20.0.0/16"})
        self._env.start()

    def tearDown(self):
        self._env.stop()

    def test_vm_in_allowed_network_is_allowed(self):
        self.assertEqual(self.g.require_allowed_target("10.20.3.4"), "10.20.3.4")

    def test_dangerous_targets_are_refused(self):
        for bad in ("127.0.0.1", "localhost", "169.254.169.254", "0.0.0.0", "224.0.0.1",
                    "::1", "8.8.8.8", "10.21.0.1", "example.com", "10.20.3.4.evil.com", ""):
            with self.subTest(target=bad):
                with self.assertRaises(self.g.TargetNotAllowed):
                    self.g.require_allowed_target(bad)

    def test_fails_closed_without_configuration(self):
        with mock.patch.dict(os.environ, {"SUNSHINE_ALLOWED_NETWORKS": ""}):
            with self.assertRaises(self.g.TargetNotAllowed):
                self.g.require_allowed_target("10.20.3.4")

    def test_send_pin_refuses_before_any_network_call(self):
        from app.services import sunshine_service
        with mock.patch.object(sunshine_service.requests, "post") as post:
            with self.assertRaises(RuntimeError):
                sunshine_service.send_pin("https://169.254.169.254:47990/api/pin", "1234", "x")
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

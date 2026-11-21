"""Login, password reset and the Sunshine PIN route of the Proxmox backend.

Run from coffeepie_backend/proxmox_backend/:
  python3 -m unittest tests.test_auth_routes

Firebase and Proxmox are replaced with fakes; nothing touches the network.
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

os.environ.update({
    "FIREBASE_API_KEY": "fake-api-key",
    "FIREBASE_ADMIN_SDK_JSON": "unused.json",
    "SUNSHINE_USERNAME": "svc-user",
    "SUNSHINE_PASSWORD": "svc-pass",
    "SUNSHINE_ALLOWED_NETWORKS": "10.20.0.0/16",
})


class FirebaseError(Exception):
    pass


# Stand-in for firebase_admin so importing the service needs no key file.
fb = types.ModuleType("firebase_admin")
fb.credentials = types.SimpleNamespace(Certificate=lambda path: object())
fb.auth = mock.MagicMock(name="firebase_auth")
fb.exceptions = types.SimpleNamespace(FirebaseError=FirebaseError)
fb.initialize_app = lambda *a, **k: None
sys.modules.update({
    "firebase_admin": fb,
    "firebase_admin.credentials": fb.credentials,
    "firebase_admin.auth": fb.auth,
    "firebase_admin.exceptions": fb.exceptions,
})

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.dependencies import verify_bearer_token, get_proxmox_auth_headers  # noqa: E402
from app.services import auth_service  # noqa: E402
from app.services import ratelimit  # noqa: E402


def firebase_reply(status, body=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body or {}
    r.raise_for_status.side_effect = None if status < 400 else Exception(f"HTTP {status}")
    return r


class AuthRoutes(unittest.TestCase):
    def setUp(self):
        ratelimit.reset()
        self.client = TestClient(app)
        fb.auth.reset_mock()
        fb.auth.create_custom_token.return_value = b"custom-token-bytes"

    def test_wrong_password_gets_no_token(self):
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(400, {"error": {}})):
            r = self.client.post("/auth/login", json={"email": "victim@example.com", "password": "guess"})
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("custom_token", r.text)
        fb.auth.create_custom_token.assert_not_called()

    def test_login_never_looks_the_account_up_by_email_alone(self):
        # The old route called get_user_by_email and minted a token for whoever it found.
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(400)):
            self.client.post("/auth/login", json={"email": "victim@example.com", "password": "x"})
        fb.auth.get_user_by_email.assert_not_called()

    def test_correct_password_gets_a_token_for_that_account(self):
        with mock.patch.object(auth_service.requests, "post",
                               return_value=firebase_reply(200, {"localId": "uid-123"})) as post:
            r = self.client.post("/auth/login", json={"email": "me@example.com", "password": "right"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["custom_token"], "custom-token-bytes")
        fb.auth.create_custom_token.assert_called_once_with("uid-123")
        self.assertIn("signInWithPassword", post.call_args.args[0])

    def test_unknown_email_looks_the_same_as_wrong_password(self):
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(400)):
            a = self.client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})
            b = self.client.post("/auth/login", json={"email": "real@example.com", "password": "y"})
        self.assertEqual((a.status_code, a.json()), (b.status_code, b.json()))

    def test_outage_is_not_reported_as_wrong_password(self):
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(500)):
            r = self.client.post("/auth/login", json={"email": "me@example.com", "password": "x"})
        self.assertEqual(r.status_code, 503)

    def test_password_guessing_is_throttled(self):
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(400)):
            codes = [self.client.post("/auth/login", json={"email": "v@example.com", "password": str(i)}).status_code
                     for i in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5:], [429, 429])

    def test_reset_requests_are_throttled(self):
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(200)):
            codes = [self.client.post("/auth/forgot-password", json={"email": "v@example.com"}).status_code
                     for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_forgot_password_never_returns_the_link(self):
        for outcome in (firebase_reply(200), firebase_reply(400), Exception("boom")):
            ratelimit.reset()
            with self.subTest(outcome=str(outcome)):
                kw = {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
                with mock.patch.object(auth_service.requests, "post", **kw):
                    r = self.client.post("/auth/forgot-password", json={"email": "victim@example.com"})
                self.assertEqual(r.status_code, 200)
                self.assertNotIn("reset_link", r.text)
                self.assertNotIn("oobCode", r.text)
        fb.auth.generate_password_reset_link.assert_not_called()

    def test_forgot_password_answer_is_identical_for_every_address(self):
        ratelimit.reset()
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(200)):
            a = self.client.post("/auth/forgot-password", json={"email": "a@example.com"}).json()
        with mock.patch.object(auth_service.requests, "post", return_value=firebase_reply(400)):
            b = self.client.post("/auth/forgot-password", json={"email": "b@example.com"}).json()
        self.assertEqual(a, b)


class SunshinePin(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides[verify_bearer_token] = lambda: {"uid": "someone"}
        app.dependency_overrides[get_proxmox_auth_headers] = lambda: {"headers": {}, "cookies": {}}

    def tearDown(self):
        app.dependency_overrides.clear()

    def body(self, ip):
        return {"ip": ip, "pin": "1234", "client_name": "c"}

    def test_requires_a_token(self):
        app.dependency_overrides.clear()
        self.assertIn(self.client.post("/sunshine/send-pin", json=self.body("10.20.0.5")).status_code, (401, 403))

    def test_internal_and_foreign_targets_are_refused_without_a_request(self):
        from app.services import sunshine_service
        for ip in ("169.254.169.254", "127.0.0.1", "8.8.8.8", "internal.example", "10.99.0.1"):
            with self.subTest(ip=ip), mock.patch.object(sunshine_service.requests, "post") as post:
                r = self.client.post("/sunshine/send-pin", json=self.body(ip))
                self.assertEqual(r.status_code, 400)
                post.assert_not_called()

    def test_vm_in_the_allowed_network_goes_through(self):
        from app.services import sunshine_service
        ok = mock.Mock()
        ok.json.return_value = {"status": "ok"}
        ok.raise_for_status.return_value = None
        with mock.patch.object(sunshine_service.requests, "post", return_value=ok) as post:
            r = self.client.post("/sunshine/send-pin", json=self.body("10.20.0.5"))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        self.assertIn("timeout", post.call_args.kwargs)

    def test_refuses_to_call_sunshine_without_credentials(self):
        from app.services import sunshine_service
        with mock.patch.object(sunshine_service, "SUNSHINE_USERNAME", ""), \
             mock.patch.object(sunshine_service.requests, "post") as post:
            r = self.client.post("/sunshine/send-pin", json=self.body("10.20.0.5"))
        self.assertEqual(r.status_code, 400)
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()

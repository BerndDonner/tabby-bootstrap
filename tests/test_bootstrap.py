"""Offline tests for the SOPS-driven two-target bootstrap boundary."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bootstrap_payload
import seed


FAKE_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\ntest-key-only\n-----END OPENSSH PRIVATE KEY-----\n"


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.key = Path(self.temp.name) / "id_tabby_bootstrap"
        self.key.write_text(FAKE_KEY, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, target, env, debug=False):
        return bootstrap_payload.create_payload(
            target, "203.0.113.1", "feature/sops-target-shells", debug,
            str(self.key), environ=env,
        )

    def test_ollama_only_gets_cloudflare(self):
        payload = self.payload("ollama", {
            "CF_API_TOKEN": "cloudflare-test-token",
            "CF_ZONE_ID": "zone-test-id",
            "AWS_SECRET_ACCESS_KEY": "MUST_NOT_BE_FORWARDED",
        })
        self.assertEqual(payload["target"], "ollama")
        self.assertEqual(payload["env"], {
            "CF_API_TOKEN": "cloudflare-test-token",
            "CF_ZONE_ID": "zone-test-id",
        })
        self.assertEqual(payload["git_ssh_key"], FAKE_KEY)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", json.dumps(payload))

    def test_ollama_missing_secrets_fails_preflight(self):
        with self.assertRaisesRegex(ValueError, "CF_ZONE_ID"):
            self.payload("ollama", {"CF_API_TOKEN": "token"})

    def test_tabby_production_fails_until_reconfigured(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            self.payload("tabby", {}, debug=False)

    def test_tabby_debug_needs_no_fake_secrets(self):
        payload = self.payload("tabby", {}, debug=True)
        self.assertEqual(payload["env"], {})
        self.assertTrue(payload["debug"])

    def test_invalid_ip_rejected(self):
        with self.assertRaisesRegex(ValueError, "IP address"):
            bootstrap_payload.create_payload(
                "ollama", "not-an-ip", "master", False, str(self.key),
                environ={"CF_API_TOKEN": "x", "CF_ZONE_ID": "y"}
            )


class RemoteBootstrapTests(unittest.TestCase):
    def test_debug_dispatch_does_not_run_setup(self):
        payload = {
            "target": "ollama", "remote_ip": "203.0.113.1",
            "ref": "feature/sops-target-shells", "debug": True,
            "env": {"CF_API_TOKEN": "test", "CF_ZONE_ID": "test"},
            "git_ssh_key": FAKE_KEY,
        }
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             patch.object(seed, "setup_ssh") as ssh, \
             patch.object(seed, "clone_repo") as clone, \
             patch.object(seed, "run_setup") as run:
            seed.main()
            ssh.assert_called_once_with(FAKE_KEY)
            clone.assert_called_once_with("feature/sops-target-shells")
            run.assert_not_called()

    def test_ollama_dispatches_ollama_runner(self):
        payload = {
            "target": "ollama", "remote_ip": "203.0.113.1",
            "ref": "master", "debug": False,
            "env": {"CF_API_TOKEN": "test", "CF_ZONE_ID": "test"},
            "git_ssh_key": FAKE_KEY,
        }
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), \
             patch.object(seed, "setup_ssh"), \
             patch.object(seed, "clone_repo"), \
             patch.object(seed, "run_setup") as run:
            seed.main()
            run.assert_called_once_with("ollama")


if __name__ == "__main__":
    unittest.main()

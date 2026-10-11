"""Fast offline tests. No real SSH, Cloudflare, Nix, Lambda, or Ollama."""

import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import bootstrap_payload
import seed
import task_runner

COMMIT = "0123456789abcdef0123456789abcdef01234567"


class PayloadTests(unittest.TestCase):
    def payload(self, target="ollama", env=None, debug=False):
        return bootstrap_payload.create_payload(
            target, "203.0.113.7", debug, COMMIT, "feature/test",
            environ={"CF_API_TOKEN": "unit-token", "CF_ZONE_ID": "unit-zone", **(env or {})},
        )

    def test_ollama_only_declared_secrets(self):
        payload = self.payload(env={"AWS_SECRET_ACCESS_KEY": "NEVER_SEND"})
        self.assertEqual(payload["env"], {"CF_API_TOKEN": "unit-token", "CF_ZONE_ID": "unit-zone"})
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", json.dumps(payload))
        self.assertNotIn("git_ssh_key", payload)
        self.assertNotIn("ref", payload)
        self.assertEqual(payload["commit"], COMMIT)

    def test_missing_secret_fails_before_upload(self):
        with self.assertRaisesRegex(ValueError, "CF_ZONE_ID"):
            bootstrap_payload.create_payload("ollama", "203.0.113.7", False,
                                             COMMIT, "master", environ={"CF_API_TOKEN": "token"})

    def test_invalid_ip_and_sha_rejected(self):
        with self.assertRaisesRegex(ValueError, "IP address"):
            bootstrap_payload.create_payload("ollama", "bad", False, COMMIT, "master", environ={})
        with self.assertRaisesRegex(ValueError, "commit"):
            bootstrap_payload.create_payload("ollama", "203.0.113.7", False, "broken", "master", environ={})

    def test_tabby_debug_only(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            self.payload(target="tabby")
        self.assertEqual(self.payload(target="tabby", debug=True)["env"], {})


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("a", "b", "c"):
            (self.root / f"{name}.py").write_text("print('okay')\n")

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, tasks):
        m = self.root / "tasks.json"
        m.write_text(json.dumps({"version": 1, "tasks": tasks}))
        return task_runner.load_manifest(m, self.root)

    def task(self, name="a", after=None, secrets=None):
        return {"script": f"{name}.py", "after": after or [], "secrets": secrets or []}

    def test_reject_cycle(self):
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.manifest({"a": self.task("a", ["b"]), "b": self.task("b", ["a"])})

    def test_reject_unknown_task(self):
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            self.manifest({"a": self.task("a", ["missing"])})

    def test_reject_duplicate_dependencies(self):
        with self.assertRaisesRegex(ValueError, "invalid after"):
            self.manifest({"a": self.task("a"), "b": self.task("b", ["a", "a"])})

    def test_reject_secret_with_shell_syntax(self):
        with self.assertRaisesRegex(ValueError, "secret variable"):
            self.manifest({"a": self.task("a", secrets=["CF_TOKEN;echo evil"])})

    def test_reject_path_escaping_repo(self):
        with self.assertRaisesRegex(ValueError, "outside snapshot"):
            self.manifest({"a": {"script": "../evil.py", "after": [], "secrets": []}})

    def test_correct_graph(self):
        got = self.manifest({"a": self.task(), "b": self.task("b", ["a"])})
        self.assertEqual(list(got), ["a", "b"])


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ctx = {"remote_ip": "203.0.113.7"}

    def tearDown(self):
        self.tmp.cleanup()

    def script(self, name, source, after=(), secrets=()):
        (self.root / f"{name}.py").write_text(source)
        return {"script": f"{name}.py", "after": list(after), "secrets": list(secrets)}

    def test_parallel_and_dependencies(self):
        # Barrier: each independent task must see the other's start marker.
        # This verifies concurrency without relying on noisy subprocess startup timings.
        dns = self.root / "dns.started"
        install = self.root / "install.started"
        ready = self.root / "ready.done"
        def barrier(here, other):
            return ("import time,sys\nfrom pathlib import Path\n"
                    f"Path({str(here)!r}).touch()\n"
                    "for _ in range(200):\n"
                    f"    if Path({str(other)!r}).exists(): break\n"
                    "    time.sleep(.01)\n"
                    "else: sys.exit(7)\n")
        tasks = {
            "dns": self.script("dns", barrier(dns, install)),
            "install": self.script("install", barrier(install, dns)),
            "ready": self.script("ready", f"from pathlib import Path\nPath({str(ready)!r}).touch()\n", after=["dns", "install"]),
        }
        self.assertTrue(task_runner.TaskExecutor(tasks, {}, self.ctx, self.root).execute())
        self.assertTrue(dns.exists() and install.exists() and ready.exists())

    def test_env_isolation(self):
        outfile = self.root / "seen.json"
        script = """import os,json\nfrom pathlib import Path\nPath(%r).write_text(json.dumps({x: os.getenv(x) for x in ('CF_API_TOKEN', 'CF_ZONE_ID', 'REMOTE_IP')}))\n""" % str(outfile)
        tasks = {
            "safe": self.script("safe", script),
        }
        with patch.dict(os.environ, {"CF_API_TOKEN": "INHERITED", "CF_ZONE_ID": "INHERITED"}):
            runner = task_runner.TaskExecutor(tasks, {"CF_API_TOKEN": "new", "CF_ZONE_ID": "zone"}, self.ctx, self.root)
            self.assertTrue(runner.execute())
        env = json.loads(outfile.read_text())
        self.assertIsNone(env["CF_API_TOKEN"])
        self.assertIsNone(env["CF_ZONE_ID"])
        self.assertEqual(env["REMOTE_IP"], "203.0.113.7")

    def test_only_declared_secret_visible_to_dns(self):
        outfile = self.root / "seen.json"
        src = "import os,json\nfrom pathlib import Path\nPath(%r).write_text(json.dumps({x: os.getenv(x) for x in ('CF_API_TOKEN','CF_ZONE_ID')}))\n" % str(outfile)
        tasks = {"dns": self.script("dns", src, secrets=["CF_API_TOKEN"])}
        runner = task_runner.TaskExecutor(tasks, {"CF_API_TOKEN": "token", "CF_ZONE_ID": "zone"}, self.ctx, self.root)
        self.assertTrue(runner.execute())
        self.assertEqual(json.loads(outfile.read_text()), {"CF_API_TOKEN": "token", "CF_ZONE_ID": None})

    def test_failure_blocks_dependent_task(self):
        mark = self.root / "should_not_exist"
        tasks = {
            "bad": self.script("bad", "import sys\nsys.exit(9)\n"),
            "after": self.script("after", f"from pathlib import Path\nPath({str(mark)!r}).touch()\n", after=["bad"]),
        }
        self.assertFalse(task_runner.TaskExecutor(tasks, {}, self.ctx, self.root).execute())
        self.assertFalse(mark.exists())

    def test_single_task_skips_dependencies(self):
        a = self.root / "a-ran"
        tasks = {
            "a": self.script("a", f"from pathlib import Path\nPath({str(a)!r}).touch()\n"),
            "b": self.script("b", "print('b')\n", after=["a"]),
        }
        self.assertTrue(task_runner.TaskExecutor(tasks, {}, self.ctx, self.root).execute("b"))
        self.assertFalse(a.exists())

    def test_output_redaction(self):
        tasks = {"dns": self.script("dns", "import os\nprint(os.environ['CF_API_TOKEN'])\n", secrets=["CF_API_TOKEN"])}
        with patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(task_runner.TaskExecutor(tasks, {"CF_API_TOKEN": "SECRET123"}, self.ctx, self.root).execute())
        self.assertNotIn("SECRET123", output.getvalue())


class SeedTests(unittest.TestCase):
    def payload(self, debug=True):
        return {"target": "ollama", "remote_ip": "203.0.113.7", "commit": COMMIT,
                "branch": "master", "debug": debug,
                "env": {"CF_API_TOKEN": "token", "CF_ZONE_ID": "zone"}}

    def test_debug_never_runs_target_tasks(self):
        with patch.object(seed, "write_debug_context") as write, \
             patch.object(task_runner, "execute") as execute:
            self.assertEqual(seed.main(io.StringIO(json.dumps(self.payload()))), 0)
        write.assert_called_once()
        execute.assert_not_called()

    def test_debug_file_private(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "private" / "debug.json"
            seed.write_debug_context(self.payload(), file)
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(file.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(json.loads(file.read_text())["env"]["CF_API_TOKEN"], "token")

    def test_normal_executes_target_without_persisting_secrets(self):
        with tempfile.TemporaryDirectory() as td:
            dctx = Path(td) / "debug.json"
            dctx.write_text("OLD-SECRET")
            with patch.object(task_runner, "DEBUG_CONTEXT", dctx), \
                 patch.object(task_runner, "execute", return_value=True) as run:
                self.assertEqual(seed.main(io.StringIO(json.dumps(self.payload(False))), root=td), 0)
                run.assert_called_once()
                self.assertFalse(dctx.exists())


class ArchiveTests(unittest.TestCase):
    def test_git_archive_HEAD_captures_commit_not_unstaged(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            def git(*args):
                return subprocess.run(["git", *args], cwd=p, check=True, capture_output=True, text=True)
            git("init", "-q")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "test")
            (p / "script.py").write_text("committed\n")
            git("add", "script.py")
            git("commit", "-qm", "initial")
            (p / "script.py").write_text("uncommitted\n")
            self.assertTrue(git("status", "--porcelain").stdout)
            archive = p / "code.tar"
            with archive.open("wb") as out:
                subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=p, stdout=out, check=True)
            import tarfile
            with tarfile.open(archive) as f:
                self.assertEqual(f.extractfile("script.py").read(), b"committed\n")


if __name__ == "__main__":
    unittest.main()

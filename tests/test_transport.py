"""Full local->fake-SSH debug deployment without contacting a provider."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class TransportTests(unittest.TestCase):
    def test_snapshot_transport_debug_and_clean_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo = base / "repo"
            repo.mkdir()
            # Simulate a freshly committed local checkout (as deployment requires).
            for src in ROOT.rglob("*"):
                if not src.is_file() or ".git" in src.parts or "__pycache__" in src.parts:
                    continue
                target = repo / src.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            def git(*args):
                subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
            git("init", "-q")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            git("add", "-A")
            git("commit", "-qm", "transport test")
            fakebin = base / "fakebin"
            fakebin.mkdir()
            home = base / "gpu-home"
            home.mkdir()
            key = base / "local_ssh_key"
            key.write_text("fake-key, never transmitted")
            # The fake SSH/SCP tools deliberately execute the real remote
            # staging and seed scripts with HOME redirected into a temp dir.
            (fakebin / "scp").write_text('''#!/usr/bin/env python3
import os,shutil,sys
from pathlib import Path
shutil.copyfile(sys.argv[-2],Path(os.environ['FAKE_REMOTE_HOME'])/'tabby-bootstrap-source.tar')
''')
            (fakebin / "ssh").write_text('''#!/usr/bin/env python3
import os,sys,subprocess
from pathlib import Path
args=sys.argv[1:]
env=os.environ.copy()
env['HOME']=env['FAKE_REMOTE_HOME']
if 'bash' in args:
    result=subprocess.run(['bash','-s','--',args[-1]], env=env, input=sys.stdin.buffer.read())
else:
    result=subprocess.run(['python3','-u',str(Path(env['HOME'])/'tabby-bootstrap'/'seed.py')],env=env,input=sys.stdin.buffer.read())
sys.exit(result.returncode)
''')
            for name in ("scp", "ssh"):
                (fakebin / name).chmod(0o755)
            env = os.environ.copy()
            env.update(PATH=f"{fakebin}:{env['PATH']}", FAKE_REMOTE_HOME=str(home),
                       SSH_KEY_PATH=str(key), BOOTSTRAP_TARGET="ollama",
                       CF_API_TOKEN="fake-token", CF_ZONE_ID="fake-zone")
            def deploy(*extra):
                return subprocess.run(["bash", "deploy-seed.sh", "203.0.113.7", *extra],
                                      cwd=repo, env=env, capture_output=True, text=True)
            ok = deploy("--debug")
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            self.assertTrue((home / "tabby-bootstrap" / "ollama_setup" / "tasks.json").exists())
            self.assertFalse((home / "tabby-bootstrap" / ".git").exists())
            self.assertTrue((home / "tabby-bootstrap-source.tar").exists())
            debug = home / ".config" / "tabby-bootstrap" / "debug.json"
            self.assertEqual(debug.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(debug.read_text())["env"]["CF_API_TOKEN"], "fake-token")
            # Manual entrypoint must read the protected context after a new SSH login.
            manual_env = env.copy()
            manual_env["HOME"] = str(home)
            listed = subprocess.run(["python3", "task_runner.py", "--list"],
                                    cwd=home / "tabby-bootstrap", env=manual_env,
                                    capture_output=True, text=True)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn("dns", listed.stdout)
            self.assertIn("pull_chat", listed.stdout)
            invalid = deploy("--branch", "old")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("Unknown argument", invalid.stderr)
            (repo / "README.md").write_text("uncommitted")
            dirty = deploy("--debug")
            self.assertNotEqual(dirty.returncode, 0)
            self.assertIn("not clean", dirty.stderr)


if __name__ == "__main__":
    unittest.main()

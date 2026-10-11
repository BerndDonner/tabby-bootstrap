#!/usr/bin/env python3
"""Small stdlib DAG executor; separate subprocess + least-privilege env per task.

Automatic deployment calls execute() from seed.py with in-memory credentials.
In --debug, this CLI reads the protected debug context to run one task (without
its dependencies) or the complete graph (--all). It never prints credentials.
"""

import argparse
import codecs
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
DEBUG_CONTEXT = Path.home() / ".config" / "tabby-bootstrap" / "debug.json"
KNOWN_SECRET_NAMES = {"CF_API_TOKEN", "CF_ZONE_ID"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ENV_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Remove terminal controls from captured CLI output; never send cursor movement
# instructions from curl/ollama into the user's SSH session.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


class TaskOutput:
    """Turn LF lines and CR-overwritten progress into readable live log lines.

    Normal lines are never throttled. Carriage-return progress is sampled once
    every interval seconds, then its last state is printed before the next
    normal line / end of stream. Handles UTF-8 and CRLF across pipe chunks.
    """

    def __init__(self, emit, interval=2.0, clock=time.monotonic):
        self.emit = emit
        self.interval = interval
        self.clock = clock
        self.buffer = ""
        self.after_cr = False
        self.progress = None
        self.last_progress = None
        self.last_sample = None

    @staticmethod
    def clean(line):
        line = ANSI_ESCAPE.sub("", line)
        return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", line).rstrip()

    def flush_progress(self):
        if self.progress and self.progress != self.last_progress:
            self.emit(self.progress)
            self.last_progress = self.progress
        self.progress = None
        self.last_progress = None
        self.last_sample = None

    def _record(self, line, is_progress):
        line = self.clean(line)
        if not line.strip():
            return
        if is_progress:
            self.progress = line
            now = self.clock()
            if self.last_sample is None or now - self.last_sample >= self.interval:
                if line != self.last_progress:
                    self.emit(line)
                    self.last_progress = line
                self.last_sample = now
        else:
            self.flush_progress()
            self.emit(line)

    def feed(self, chunk, final=False):
        # The previous read may have ended exactly on CR. Treat it as a live
        # progress update immediately, and swallow a following LF if present.
        if self.after_cr:
            chunk = chunk.removeprefix("\n")
            self.after_cr = False
        self.buffer += chunk
        while True:
            sep = re.search(r"[\r\n]", self.buffer)
            if sep is None:
                break
            i = sep.start()
            char = self.buffer[i]
            if char == "\r" and i + 1 == len(self.buffer) and not final:
                self._record(self.buffer[:i], is_progress=True)
                self.buffer = ""
                self.after_cr = True
                break
            crlf = char == "\r" and self.buffer[i:i + 2] == "\r\n"
            self._record(self.buffer[:i], is_progress=char == "\r" and not crlf)
            self.buffer = self.buffer[i + (2 if crlf else 1):]
        if final:
            if self.buffer:
                self._record(self.buffer, is_progress=False)
                self.buffer = ""
            self.flush_progress()



def load_manifest(path, root=ROOT):
    """Validate a static, acyclic task graph before launching any task."""
    root = Path(root).resolve()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("tasks"), dict):
        raise ValueError("Manifest requires version=1 and a tasks object")
    tasks = raw["tasks"]
    if not tasks:
        raise ValueError("Task graph is empty")
    for name, task in tasks.items():
        if not isinstance(name, str) or not ID_PATTERN.fullmatch(name):
            raise ValueError(f"Invalid task ID: {name!r}")
        if not isinstance(task, dict) or set(task) != {"script", "after", "secrets"}:
            raise ValueError(f"Task {name}: requires exactly script, after, secrets")
        script = task["script"]
        if not isinstance(script, str) or not script.endswith(".py") or Path(script).is_absolute():
            raise ValueError(f"Task {name}: invalid script path")
        resolved = (root / script).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise ValueError(f"Task {name}: script missing or outside snapshot: {script}")
        for field in ("after", "secrets"):
            values = task[field]
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values) or len(values) != len(set(values)):
                raise ValueError(f"Task {name}: invalid {field}")
        if any(not ENV_PATTERN.fullmatch(s) for s in task["secrets"]):
            raise ValueError(f"Task {name}: invalid secret variable name")
    visited = set()
    visiting = set()

    def visit(name):
        if name in visiting:
            raise ValueError(f"Dependency cycle at {name}")
        if name in visited:
            return
        visiting.add(name)
        for dep in tasks[name]["after"]:
            if dep not in tasks:
                raise ValueError(f"Task {name} references unknown dependency {dep}")
            visit(dep)
        visiting.remove(name)
        visited.add(name)

    for name in tasks:
        visit(name)
    return tasks


class TaskExecutor:
    def __init__(self, tasks, secrets, context, root=ROOT, max_workers=4):
        self.tasks = tasks
        self.root = Path(root).resolve()
        if not isinstance(secrets, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in secrets.items()):
            raise ValueError("Invalid secrets")
        self.secrets = secrets
        self.context = context
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.cancel = threading.Event()
        self.active = {}
        self.secret_names = KNOWN_SECRET_NAMES | set(secrets) | {
            s for task in tasks.values() for s in task["secrets"]
        }
        missing = {s for task in tasks.values() for s in task["secrets"] if not secrets.get(s)}
        if missing:
            raise ValueError("Missing required secrets: " + ", ".join(sorted(missing)))

    def log(self, task, message):
        # Third-party commands may accidentally echo their environment.
        for value in self.secrets.values():
            if value:
                message = message.replace(value, "[REDACTED]")
        with self.lock:
            print(f"[{task}] {message}", flush=True)

    def stop_running(self):
        # Stop process groups (including child shell/installer processes), not
        # only the parent Python wrappers. Workers collect their exit statuses.
        self.cancel.set()
        with self.lock:
            procs = list(self.active.values())
        for proc in procs:
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        # Some installer subprocesses may ignore SIGTERM. Do not hang forever
        # on a billed GPU while waiting for worker processes to exit.
        for proc in procs:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def run_one(self, name):
        task = self.tasks[name]
        if self.cancel.is_set():
            return False
        # Inherit ordinary runtime env only; never blanket-forward CF secrets.
        env = {k: v for k, v in os.environ.items() if k not in self.secret_names}
        env.update({"REMOTE_IP": self.context["remote_ip"],
                    "CF_DNS_NAME": "ai.donner-lab.org", "PYTHONUNBUFFERED": "1"})
        env.update({s: self.secrets[s] for s in task["secrets"]})
        command = [sys.executable, "-u", str(self.root / task["script"])]
        with self.lock:
            if self.cancel.is_set():
                return False
            proc = subprocess.Popen(command, cwd=self.root, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    bufsize=0,
                                    start_new_session=True)
            self.active[name] = proc
        started = time.monotonic()
        self.log(name, "START")
        try:
            output = TaskOutput(lambda line: self.log(name, line))
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            with proc.stdout:
                while chunk := os.read(proc.stdout.fileno(), 8192):
                    output.feed(decoder.decode(chunk))
                output.feed(decoder.decode(b"", final=True), final=True)
            status = proc.wait()
        finally:
            with self.lock:
                self.active.pop(name, None)
        elapsed = time.monotonic() - started
        self.log(name, f"OK ({elapsed:.1f}s)" if status == 0
                 else f"FAILED (exit {status}, {elapsed:.1f}s)")
        return status == 0

    def execute(self, selected=None):
        if selected is not None:
            return self.run_one(selected)
        started = time.monotonic()
        pending = set(self.tasks)
        completed = set()
        running = {}
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                try:
                    while pending or running:
                        ready = sorted(n for n in pending if set(self.tasks[n]["after"]) <= completed)
                        for name in ready:
                            if len(running) >= self.max_workers:
                                break
                            pending.remove(name)
                            running[pool.submit(self.run_one, name)] = name
                        if not running:
                            raise RuntimeError("No executable tasks remain (invalid graph)")
                        done, _ = wait(running, return_when=FIRST_COMPLETED)
                        failed = False
                        for future in done:
                            name = running.pop(future)
                            if future.result():
                                completed.add(name)
                            else:
                                failed = True
                        if failed:
                            self.stop_running()
                            # All workers are joined by the executor context manager.
                            return False
                    return True
                except BaseException:
                    self.stop_running()
                    raise
        finally:
            elapsed = time.monotonic() - started
            self.log("bootstrap", f"TOTAL {elapsed:.1f}s | {len(completed)}/{len(self.tasks)} tasks completed")


def execute(target, secrets, context, root=ROOT):
    if target != "ollama":
        raise ValueError("Tabby normal setup is disabled; only --debug is available")
    tasks = load_manifest(Path(root) / "ollama_setup" / "tasks.json", root)
    runner = TaskExecutor(tasks, secrets, context, root)
    return runner.execute()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("task", nargs="?", help="Run exactly this task; dependencies are NOT automatically run")
    group.add_argument("--all", action="store_true", help="Run the whole DAG")
    group.add_argument("--list", action="store_true", help="List tasks")
    args = parser.parse_args(argv)
    try:
        # The CLI is intended only for manual use on a --debug instance.
        ctx = json.loads(DEBUG_CONTEXT.read_text(encoding="utf-8"))
        if not isinstance(ctx, dict) or ctx.get("target") != "ollama":
            raise ValueError("No runnable task graph for this target")
        tasks = load_manifest(ROOT / "ollama_setup" / "tasks.json", ROOT)
        if args.list:
            for name, task in tasks.items():
                print(f"{name:20s} after: {', '.join(task['after']) or '-'}")
            return 0
        if args.task and args.task not in tasks:
            raise ValueError(f"Unknown task {args.task!r}; run --list")
        runner = TaskExecutor(tasks, ctx["env"], ctx, ROOT)
        return 0 if runner.execute(None if args.all else args.task) else 1
    except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Task runner error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

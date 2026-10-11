"""Regression tests for real-time output from curl / Ollama CLI subprocesses."""

import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import task_runner


class TaskOutputTests(unittest.TestCase):
    def test_carriage_return_progress_is_sampled_and_last_update_kept(self):
        logs = []
        clock = [0.0]
        parser = task_runner.TaskOutput(logs.append, interval=2, clock=lambda: clock[0])
        parser.feed("Downloading: 1%\rDownloading: 2%\r")
        self.assertEqual(logs, ["Downloading: 1%"])
        clock[0] = 1.5
        parser.feed("Downloading: 50%\r")
        self.assertEqual(logs, ["Downloading: 1%"])
        clock[0] = 2.5
        parser.feed("Downloading: 75%\r")
        self.assertEqual(logs[-1], "Downloading: 75%")
        clock[0] = 2.6
        parser.feed("Downloading: 100%\rDone\n", final=True)
        self.assertEqual(logs, ["Downloading: 1%", "Downloading: 75%", "Downloading: 100%", "Done"])

    def test_crlf_split_between_chunks_and_colored_output(self):
        logs = []
        parser = task_runner.TaskOutput(logs.append)
        parser.feed("\x1b[32mReady\x1b[0m\r")
        parser.feed("\nnext \x1b[2Kmessage\n", final=True)
        self.assertEqual(logs, ["Ready", "next message"])

    def test_incomplete_final_line_and_empty_progress(self):
        logs = []
        parser = task_runner.TaskOutput(logs.append)
        parser.feed("one\n\r\npartial")
        parser.feed(" line", final=True)
        self.assertEqual(logs, ["one", "partial line"])


class RunnerLoggingTests(unittest.TestCase):
    def test_utf8_character_split_across_reads_and_stderr_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "utf8.py").write_text(r'''import sys, time
sys.stdout.buffer.write(b"Start \xe2")
sys.stdout.flush()
time.sleep(0.03)
sys.stdout.buffer.write(b"\x9c\x85\n")
sys.stdout.flush()
print("stderr warning", file=sys.stderr)
''')
            tasks = {"utf8": {"script": "utf8.py", "after": [], "secrets": []}}
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertTrue(task_runner.TaskExecutor(tasks, {},
                                {"remote_ip": "203.0.113.1"}, root).execute())
            log = output.getvalue()
            self.assertIn("[utf8] Start ✅", log)
            self.assertIn("[utf8] stderr warning", log)
            self.assertNotIn("�", log)

    def test_parallel_output_is_prefixed_and_total_follows_task_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("chat", "autocomplete"):
                (root / f"{name}.py").write_text('''import sys, time
for i in range(12):
    sys.stdout.write("\\r\\x1b[2KDownloading %02d%%" % (i * 9))
    sys.stdout.flush()
    time.sleep(0.01)
print("\\r\\x1b[32mFinished\\x1b[0m")
''')
            tasks = {name: {"script": f"{name}.py", "after": [], "secrets": []}
                     for name in ("chat", "autocomplete")}
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                self.assertTrue(task_runner.TaskExecutor(
                    tasks, {}, {"remote_ip": "203.0.113.1"}, root).execute())
            lines = output.getvalue().splitlines()
            self.assertTrue(all(re.match(r"^\[(chat|autocomplete|bootstrap)\] ", x) for x in lines), lines)
            for name in tasks:
                self.assertTrue(any(re.match(rf"^\[{name}\] OK \(\d+\.\ds\)$", x) for x in lines), lines)
                self.assertTrue(any(x.startswith(f"[{name}] Finished") for x in lines), lines)
                self.assertLessEqual(sum(f"[{name}] Downloading" in x for x in lines), 3)
            self.assertRegex(lines[-1], r"^\[bootstrap\] TOTAL \d+\.\ds \\| 2/2 tasks completed$")
            self.assertNotIn("\x1b", output.getvalue())
            self.assertNotIn("\r", output.getvalue())


if __name__ == "__main__":
    unittest.main()

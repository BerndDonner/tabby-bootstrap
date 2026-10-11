"""Offline tests for Ollama's NDJSON model-pull progress API."""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ollama_setup"))
import common


class FakeResponse:
    def __init__(self, events):
        self.events = [json.dumps(event).encode() + b"\n" for event in events]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def __iter__(self):
        return iter(self.events)


class ModelPullTests(unittest.TestCase):
    def test_json_progress_is_sampled_and_finishes_without_terminal_spam(self):
        events = [{"status": "pulling manifest"}]
        for i in range(101):
            events.append({"status": "pulling abcdef", "total": 100, "completed": i})
        events += [{"status": "verifying sha256 digest"}, {"status": "writing manifest"},
                   {"status": "success"}]
        seen = []

        def fake_open(request, timeout):
            seen.append((request, timeout))
            return FakeResponse(events)

        clock = [0]
        def monotonic():
            clock[0] += 0.06
            return clock[0]

        with patch.object(common, "run", return_value="NAME ID SIZE\n"), \
             patch.object(common.urllib.request, "urlopen", side_effect=fake_open), \
             patch.object(common.time, "monotonic", side_effect=monotonic), \
             patch.object(common, "log") as output:
            common.pull_model("qwen2.5-coder:7b")

        request, timeout = seen[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/pull")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {"model": "qwen2.5-coder:7b", "stream": True})
        self.assertEqual(timeout, 180)
        lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(lines.count("pulling manifest"), 1)
        self.assertIn("pulling abcdef: 100% (0.00/0.00 GB)", lines)
        self.assertIn("Pulled qwen2.5-coder:7b", lines)
        self.assertLess(len(lines), 15, lines)
        self.assertFalse(any("⠋" in line or "\r" in line for line in lines))

    def test_api_error_propagates(self):
        events = [{"status": "pulling manifest"}, {"error": "model unavailable"}]
        with patch.object(common, "run", return_value="NAME ID SIZE\n"), \
             patch.object(common.urllib.request, "urlopen", return_value=FakeResponse(events)):
            with self.assertRaisesRegex(RuntimeError, "model unavailable"):
                common.pull_model("deepseek-coder:6.7b")

    def test_truncated_stream_is_not_success(self):
        events = [{"status": "pulling abcdef", "total": 100, "completed": 100}]
        with patch.object(common, "run", return_value="NAME ID SIZE\n"), \
             patch.object(common.urllib.request, "urlopen", return_value=FakeResponse(events)):
            with self.assertRaisesRegex(RuntimeError, "without success"):
                common.pull_model("deepseek-coder:6.7b")

    def test_existing_model_skips_api(self):
        with patch.object(common, "run", return_value="NAME ID SIZE\nqwen2.5-coder:7b abc 4 GB\n"), \
             patch.object(common.urllib.request, "urlopen") as urlopen:
            common.pull_model("qwen2.5-coder:7b")
            urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()

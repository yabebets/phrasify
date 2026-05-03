from __future__ import annotations

import json
import os
import unittest
from importlib.util import find_spec
from unittest import mock

from phrasify.llm import _parse_items, extract_json_object, get_default_model


class LlmParsingTests(unittest.TestCase):
    def test_extract_json_object_from_fenced_response(self) -> None:
        payload = extract_json_object('```json\n{"expressions": []}\n```')
        self.assertEqual(json.loads(payload), {"expressions": []})

    def test_extract_json_object_from_wrapped_response(self) -> None:
        payload = extract_json_object('Here it is:\n{"expressions": [{"x": "{ok}"}]}\nDone')
        self.assertEqual(json.loads(payload)["expressions"][0]["x"], "{ok}")

    def test_parse_items_rejects_malformed_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "malformed expression item"):
            _parse_items('{"expressions": [{"expression": "ok"}, "bad"]}')

    def test_get_default_model_accepts_provider_env_override(self) -> None:
        with mock.patch.dict(os.environ, {"PHRASIFY_ANTHROPIC_MODEL": "claude-test"}, clear=False):
            self.assertEqual(get_default_model("anthropic"), "claude-test")

    @unittest.skipUnless(find_spec("anthropic"), "anthropic extra is not installed")
    def test_anthropic_extra_is_importable(self) -> None:
        import anthropic

        self.assertTrue(hasattr(anthropic, "Anthropic"))

    @unittest.skipUnless(find_spec("openai"), "openai extra is not installed")
    def test_openai_extra_is_importable(self) -> None:
        import openai

        self.assertTrue(hasattr(openai, "OpenAI"))


if __name__ == "__main__":
    unittest.main()

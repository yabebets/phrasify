from __future__ import annotations

import json
import unittest

from phrasify.llm import extract_json_object


class LlmParsingTests(unittest.TestCase):
    def test_extract_json_object_from_fenced_response(self) -> None:
        payload = extract_json_object('```json\n{"expressions": []}\n```')
        self.assertEqual(json.loads(payload), {"expressions": []})

    def test_extract_json_object_from_wrapped_response(self) -> None:
        payload = extract_json_object('Here it is:\n{"expressions": [{"x": "{ok}"}]}\nDone')
        self.assertEqual(json.loads(payload)["expressions"][0]["x"], "{ok}")


if __name__ == "__main__":
    unittest.main()


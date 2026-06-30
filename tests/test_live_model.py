import unittest

from tools.live_model import (
    LiveModelError,
    _extract_response_text,
    live_model_config_from_env,
)


class LiveModelTest(unittest.TestCase):
    def test_openai_config_requires_api_key_when_enabled(self):
        with self.assertRaisesRegex(LiveModelError, "OPENAI_API_KEY"):
            live_model_config_from_env({"OPENAI_MODEL": "gpt-example"})

    def test_openai_config_requires_model_when_enabled(self):
        with self.assertRaisesRegex(LiveModelError, "OPENAI_MODEL"):
            live_model_config_from_env({"OPENAI_API_KEY": "sk-test"})

    def test_openai_config_reads_expected_environment(self):
        config = live_model_config_from_env(
            {
                "OPENAI_API_KEY": "sk-test",
                "OPENAI_MODEL": "gpt-example",
                "OPENAI_RESPONSES_URL": "https://example.invalid/responses",
            }
        )

        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model, "gpt-example")
        self.assertEqual(config.api_key, "sk-test")
        self.assertEqual(config.endpoint, "https://example.invalid/responses")

    def test_openai_config_requires_https_endpoint_override(self):
        with self.assertRaisesRegex(LiveModelError, "must use https"):
            live_model_config_from_env(
                {
                    "OPENAI_API_KEY": "sk-test",
                    "OPENAI_MODEL": "gpt-example",
                    "OPENAI_RESPONSES_URL": "http://example.invalid/responses",
                }
            )

    def test_openai_response_text_extraction(self):
        payload = {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "First paragraph."},
                        {"type": "annotation", "text": "ignored"},
                    ]
                },
                {"content": [{"type": "output_text", "text": "Second paragraph."}]},
            ]
        }

        self.assertEqual(
            _extract_response_text(payload),
            "First paragraph.\nSecond paragraph.",
        )


if __name__ == "__main__":
    unittest.main()

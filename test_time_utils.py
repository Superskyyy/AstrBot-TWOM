import sys
import types
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

astrbot_module = types.ModuleType("astrbot")
astrbot_api_module = types.ModuleType("astrbot.api")
astrbot_api_module.logger = type(
    "LoggerStub",
    (),
    {
        "debug": lambda *args, **kwargs: None,
        "warning": lambda *args, **kwargs: None,
        "error": lambda *args, **kwargs: None,
    },
)()
sys.modules.setdefault("astrbot", astrbot_module)
sys.modules.setdefault("astrbot.api", astrbot_api_module)

utils_module = types.ModuleType("utils")
utils_module.__path__ = [str(Path(__file__).parent / "utils")]
sys.modules.setdefault("utils", utils_module)

import utils.time_utils as time_utils


class ParseDeathTimeTests(unittest.TestCase):
    def test_ignores_non_time_drop_note_after_death_marker(self):
        death_time = time_utils.parse_death_time("osos", ZoneInfo("UTC"))

        self.assertIsNotNone(death_time)

    def test_accepts_minute_with_drop_note_after_death_marker(self):
        death_time = time_utils.parse_death_time("22 爽死 mn", ZoneInfo("UTC"))

        self.assertEqual(death_time.minute, 22)
        self.assertEqual(death_time.second, 0)

    def test_accepts_clock_time_with_drop_note_after_death_marker(self):
        death_time = time_utils.parse_death_time("12:34 爽死 mn", ZoneInfo("UTC"))

        self.assertEqual(death_time.hour, 12)
        self.assertEqual(death_time.minute, 34)
        self.assertEqual(death_time.second, 0)

    def test_rejects_invalid_time_like_text_after_death_marker(self):
        with self.assertRaises(ValueError):
            time_utils.parse_death_time("99:99", ZoneInfo("UTC"))

        with self.assertRaises(ValueError):
            time_utils.parse_death_time("60", ZoneInfo("UTC"))


if __name__ == "__main__":
    unittest.main()

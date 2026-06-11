import unittest
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

astrbot_module = types.ModuleType("astrbot")
astrbot_api_module = types.ModuleType("astrbot.api")
astrbot_api_module.logger = type(
    "LoggerStub",
    (),
    {"debug": lambda *args, **kwargs: None, "error": lambda *args, **kwargs: None},
)()
sys.modules.setdefault("astrbot", astrbot_module)
sys.modules.setdefault("astrbot.api", astrbot_api_module)

utils_module = types.ModuleType("utils")
utils_module.__path__ = [str(Path(__file__).parent / "utils")]
sys.modules.setdefault("utils", utils_module)

import utils.formatter as formatter


class FormatTimerListTests(unittest.TestCase):
    def test_deduplicates_same_boss_visible_from_multiple_groups(self):
        timers = {
            "100_boss_a": {
                "boss": "boss_a",
                "spawn_time": "2026-06-11T15:30:00+00:00",
            },
            "200_boss_a": {
                "boss": "boss_a",
                "spawn_time": "2026-06-11T15:20:00+00:00",
            },
        }
        bosses = {
            "boss_a": {
                "display_name": "Boss A",
                "emoji": "",
            }
        }

        message = formatter.format_timer_list(
            timers,
            bosses,
            ZoneInfo("UTC"),
            show_secondary=False,
        )

        self.assertEqual(message.count("Boss A"), 1)
        self.assertIn("15:20", message)
        self.assertNotIn("15:30", message)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime
from pathlib import Path
import sys
import types
from zoneinfo import ZoneInfo

astrbot_module = types.ModuleType("astrbot")
astrbot_api_module = types.ModuleType("astrbot.api")
astrbot_api_module.logger = type(
    "LoggerStub",
    (),
    {"debug": lambda *args, **kwargs: None, "warning": lambda *args, **kwargs: None},
)()
sys.modules.setdefault("astrbot", astrbot_module)
sys.modules.setdefault("astrbot.api", astrbot_api_module)

utils_module = types.ModuleType("utils")
utils_module.__path__ = [str(Path(__file__).parent / "utils")]
sys.modules.setdefault("utils", utils_module)

import utils.lib_mini as lib_mini


class LibMiniReminderTests(unittest.TestCase):
    def test_matches_lib_mini_death_report_variants(self):
        matching_messages = [
            "lib d",
            "libd",
            "lib mini d",
            "libmini d",
            "libminid",
            "LIB MINI d",
            "图书馆 mini d",
            "图书馆mini d",
            "图书馆 d",
            "图书馆d",
            "图书馆mini d osos",
            "书库 d",
            "书库d",
            "书库 mini d",
            "书库mini d",
        ]

        for message in matching_messages:
            with self.subTest(message=message):
                self.assertTrue(lib_mini.is_lib_mini_death_report(message))

    def test_rejects_non_lib_mini_messages(self):
        non_matching_messages = [
            "mini d",
            "library mini",
            "图书馆 mini",
            "wdk d",
        ]

        for message in non_matching_messages:
            with self.subTest(message=message):
                self.assertFalse(lib_mini.is_lib_mini_death_report(message))

    def test_second_reminder_is_suppressed_after_death_report_in_same_window(self):
        tz = ZoneInfo("Asia/Shanghai")
        last_report = datetime(2026, 6, 11, 10, 15, tzinfo=tz)

        self.assertFalse(
            lib_mini.should_send_followup_reminder(
                datetime(2026, 6, 11, 10, 45, tzinfo=tz),
                last_report,
            )
        )

    def test_second_reminder_is_sent_without_report_in_same_window(self):
        tz = ZoneInfo("Asia/Shanghai")

        self.assertTrue(
            lib_mini.should_send_followup_reminder(
                datetime(2026, 6, 11, 10, 45, tzinfo=tz),
                None,
            )
        )
        self.assertTrue(
            lib_mini.should_send_followup_reminder(
                datetime(2026, 6, 11, 22, 45, tzinfo=tz),
                datetime(2026, 6, 11, 10, 15, tzinfo=tz),
            )
        )


if __name__ == "__main__":
    unittest.main()

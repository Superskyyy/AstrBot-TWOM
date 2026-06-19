import json
import unittest
from pathlib import Path
import sys
import types

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

import utils.boss_config as boss_config


class ParseBossDeathCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(
            Path(__file__).parent / "default_bosses.json", encoding="utf-8"
        ) as f:
            bosses = json.load(f)
        cls.alias_map = boss_config.build_alias_map(bosses)

    def parse(self, message):
        return boss_config.parse_boss_death_command(message, self.alias_map)

    def test_multiword_alias_with_space_keyword(self):
        # "red bee" must resolve to rb, NOT the Red boss.
        result = self.parse("red bee d")
        self.assertIsNotNone(result)
        self.assertEqual(result.boss_name, "rb")

    def test_multiword_alias_with_time(self):
        result = self.parse("red bee d 12:00")
        self.assertEqual(result.boss_name, "rb")
        self.assertEqual(result.time_part, "12:00")

    def test_red_still_works(self):
        self.assertEqual(self.parse("red d").boss_name, "red")
        self.assertEqual(self.parse("redd").boss_name, "red")

    def test_no_space_cjk(self):
        self.assertEqual(self.parse("大树d").boss_name, "大树")
        result = self.parse("大树d 12:00")
        self.assertEqual(result.boss_name, "大树")
        self.assertEqual(result.time_part, "12:00")

    def test_with_space_cjk(self):
        self.assertEqual(self.parse("大树 d").boss_name, "大树")

    def test_unknown_boss_with_space_reports(self):
        result = self.parse("mushland d")
        self.assertIsNone(result.boss_name)
        self.assertTrue(result.has_space_before_d)
        self.assertEqual(result.boss_input, "mushland")

    def test_not_a_death_report(self):
        self.assertIsNone(self.parse("hello world"))
        self.assertIsNone(self.parse("snake 12:00"))


if __name__ == "__main__":
    unittest.main()

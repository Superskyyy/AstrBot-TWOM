import sys
import types
import unittest
from pathlib import Path

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

import utils.map_config as map_config


class MapCommandParsingTests(unittest.TestCase):
    def test_parses_map_command_arguments(self):
        self.assertEqual(map_config.parse_map_command("/map 4"), "4")
        self.assertEqual(map_config.parse_map_command("/map 森林"), "森林")
        self.assertEqual(map_config.parse_map_command("/map   lh1"), "lh1")
        self.assertEqual(map_config.parse_map_command("/map"), "")

    def test_ignores_non_map_messages(self):
        self.assertIsNone(map_config.parse_map_command("map 4"))
        self.assertIsNone(map_config.parse_map_command("/boss list"))


if __name__ == "__main__":
    unittest.main()

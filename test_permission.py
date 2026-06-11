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

import utils.permission as permission


class FakeGroup:
    def __init__(self, owner=None, admins=None):
        self.group_owner = owner
        self.group_admins = admins or []


class FakeEvent:
    def __init__(self, sender_id, group=None, astrbot_admin=False):
        self.sender_id = sender_id
        self.group = group
        self.astrbot_admin = astrbot_admin

    def get_sender_id(self):
        return self.sender_id

    def is_admin(self):
        return self.astrbot_admin

    async def get_group(self):
        return self.group


class ResetPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_allows_group_admin_even_when_not_astrbot_admin(self):
        event = FakeEvent("123", FakeGroup(admins=["123"]), astrbot_admin=False)

        self.assertTrue(await permission.can_reset_timers(event))

    async def test_allows_group_owner_even_when_not_astrbot_admin(self):
        event = FakeEvent("123", FakeGroup(owner="123"), astrbot_admin=False)

        self.assertTrue(await permission.can_reset_timers(event))

    async def test_allows_astrbot_admin(self):
        event = FakeEvent("123", FakeGroup(admins=[]), astrbot_admin=True)

        self.assertTrue(await permission.can_reset_timers(event))

    async def test_rejects_regular_group_member(self):
        event = FakeEvent("123", FakeGroup(owner="999", admins=["456"]), astrbot_admin=False)

        self.assertFalse(await permission.can_reset_timers(event))


if __name__ == "__main__":
    unittest.main()

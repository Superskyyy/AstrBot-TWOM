"""
TWOM Boss Timer Plugin for AstrBot
Tracks boss respawn times and sends automatic reminders
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import zhconv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# Import utils modules
from .utils import boss_config, formatter, map_config, permission, scheduler, time_utils, timer_storage


@register(
    "astrbot_plugin_twom_boss_timer",
    "Superskyyy",
    "TWOM Boss timer with automatic reminders and map viewer",
    "v1.1.0",
    "https://github.com/Superskyyy/AstrBot-TWOM",
)
class BossTimer(Star):
    """TWOM游戏Boss刷新计时器，支持自动提醒和多群管理"""

    def __init__(self, context: Context, config: Optional[Dict] = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}

        # Initialize timezones (primary + secondary)
        tz_str = self.config.get("timezone", "Asia/Shanghai")
        self.timezone = time_utils.init_timezone(tz_str)

        secondary_tz_str = self.config.get("secondary_timezone", "America/Toronto")
        self.secondary_tz = time_utils.init_timezone(secondary_tz_str) if secondary_tz_str else None
        self.show_secondary = self.config.get("show_secondary_timezone", True)

        # Initialize scheduler
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)

        # Initialize paths
        self.data_dir = Path(get_astrbot_data_path()) / "boss_timer"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir = Path(__file__).parent / "assets"

        # Load configurations using utils
        default_bosses_path = Path(__file__).parent / "default_bosses.json"
        self.bosses = boss_config.load_bosses(default_bosses_path)
        self.boss_alias_map = boss_config.build_alias_map(self.bosses)

        self.timers = timer_storage.load_timers(self.data_dir)

        self.maps = map_config.load_maps(self.assets_dir)
        self.map_alias_map = map_config.build_map_alias_map(self.maps)

        # Start scheduler and restore timers
        self.scheduler.start()
        self._restore_timers()

        logger.info("TWOM Boss Timer plugin initialized successfully")

    @staticmethod
    def _get_user_id(unified_msg_origin: str) -> str:
        """Extract user ID from unified_msg_origin"""
        return unified_msg_origin.split("_")[-1] if "_" in unified_msg_origin else unified_msg_origin

    def _restore_timers(self):
        """Restore scheduled jobs from saved timers"""
        removed = scheduler.cleanup_expired_timers(self.timers, self.timezone)
        if removed > 0:
            timer_storage.save_timers(self.data_dir, self.timers)

        intervals = scheduler.get_reminder_intervals(self.config)
        restored = 0

        for timer_id, timer_data in self.timers.items():
            if not (spawn_time_str := timer_data.get("spawn_time")):
                continue

            try:
                spawn_time = datetime.fromisoformat(spawn_time_str).replace(tzinfo=self.timezone)
                if scheduler.schedule_reminders(
                    self.scheduler,
                    timer_id,
                    timer_data.get("boss"),
                    spawn_time,
                    timer_data.get("umo"),
                    self._send_reminder,
                    intervals,
                    self.timezone,
                ) > 0:
                    restored += 1
            except Exception as e:
                logger.error(f"Failed to restore timer {timer_id}: {e}")

        if restored > 0:
            logger.info(f"Restored {restored} active timers")

    async def _send_reminder(self, boss_name: str, spawn_time: datetime, umo: str, minutes_before: int):
        """Send reminder message (scheduled callback)"""
        display_name = boss_config.get_boss_display_name(boss_name, self.bosses)
        message = formatter.format_reminder_message(
            display_name,
            spawn_time,
            minutes_before,
            self.secondary_tz,
            self.show_secondary,
        )

        logger.info(f"Sending reminder: {boss_name} {minutes_before}min to {umo}")

        try:
            await self.context.send_message(umo, MessageEventResult().message(message))
        except Exception as e:
            logger.error(f"Failed to send reminder to {umo}: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL, priority=100)
    async def handle_boss_death(self, event: AstrMessageEvent):
        """Handle boss death recording. Pattern: <boss_name> d [time]"""
        msg = event.get_message_str().strip()
        # Convert Traditional Chinese to Simplified Chinese
        msg = zhconv.convert(msg, 'zh-cn')
        # Normalize spaces (replace full-width spaces and multiple spaces with single space)
        msg = re.sub(r'\s+', ' ', msg.replace('　', ' '))

        # Parse boss command (支持 "大树 d" 和 "大树d" 两种格式)
        msg_lower = msg.lower()
        boss_name = None
        time_part = None

        # 先尝试有空格的版本 "xxx d"
        has_space_before_d = False
        match_with_space = re.match(r"^(\S+)\s+d(?:\s+(.+))?$", msg_lower)
        if match_with_space:
            has_space_before_d = True
            boss_input = match_with_space.group(1)
            time_part = match_with_space.group(2)
            boss_name = boss_config.get_boss_by_alias(boss_input, self.boss_alias_map)
        else:
            # 尝试无空格版本 "xxxd"
            match_no_space = re.match(r"^(\S+)d(?:\s+(.+))?$", msg_lower)
            if match_no_space:
                prefix = match_no_space.group(1)
                time_part = match_no_space.group(2)

                # 先尝试完整名字（包括'd'）- 防止boss名本身以'd'结尾
                full_name = prefix + 'd'
                boss_name = boss_config.get_boss_by_alias(full_name, self.boss_alias_map)
                boss_input = full_name if boss_name else prefix

                # 如果完整名字找不到，再尝试去掉'd'的版本
                if not boss_name:
                    boss_name = boss_config.get_boss_by_alias(prefix, self.boss_alias_map)
                    boss_input = prefix
            else:
                logger.debug(f"Boss death pattern not matched: '{msg}'")
                return
        if not boss_name:
            # Boss not found - only show error message if there was a space before 'd'
            # e.g. "mushland d" should show error, but "mushland" (no space) should be silent
            if not has_space_before_d:
                return

            # Avoid matching common English phrases like "is day", "world", etc.
            common_words = {"is", "was", "has", "had", "world", "good", "bad", "old", "new", "should", "would", "could"}

            # Check if input contains Chinese characters (allow single Chinese chars)
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in boss_input)

            # Only show message if:
            # 1. Has Chinese character OR input is at least 2 characters (avoid single English letters)
            # 2. Not a common English word that might appear in phrases
            if (has_chinese or len(boss_input) >= 2) and boss_input not in common_words:
                yield MessageEventResult().message(
                    f"❌ 我还不知道什么是 {boss_input} 呢\n\n"
                    f"请输入 /boss bosses 来查看所有支持的boss名称"
                )
                event.stop_event()
            return

        try:
            death_time = time_utils.parse_death_time(time_part or "", self.timezone)
        except ValueError as e:
            logger.debug(f"Failed to parse death time for '{msg}': {e}")
            return

        # Check permissions
        group_id = event.get_group_id()
        if group_id:
            if not permission.is_group_enabled(group_id, self.config):
                logger.debug(f"Group {group_id} not enabled for boss timer")
                return
        else:
            user_id = self._get_user_id(event.unified_msg_origin)
            if not permission.is_user_enabled(user_id, self.config):
                logger.debug(f"User {user_id} not enabled for boss timer in private chat")
                return

        # Check group boss filter
        if group_id:
            allowed_bosses = permission.get_allowed_bosses_for_group(group_id, self.config)
            if allowed_bosses and boss_name not in allowed_bosses:
                logger.debug(f"Boss {boss_name} not allowed in group {group_id}. Allowed: {allowed_bosses}")
                return

        # Calculate spawn time and create timer
        spawn_time = boss_config.calculate_spawn_time(boss_name, death_time, self.bosses)

        # Create timer_id without timestamp (so same boss overwrites)
        if group_id:
            timer_id = f"{group_id}_{boss_name}"
            user_id = None
        else:
            user_id = self._get_user_id(event.unified_msg_origin)
            timer_id = f"private_{user_id}_{boss_name}"

        # Remove old timer and scheduled jobs if exists
        if timer_id in self.timers:
            # Cancel all scheduled reminder jobs for this timer
            for job in self.scheduler.get_jobs():
                if job.id.startswith(f"reminder_{timer_id}_"):
                    job.remove()

        # Save timer
        self.timers[timer_id] = {
            "boss": boss_name,
            "death_time": death_time.isoformat(),
            "spawn_time": spawn_time.isoformat(),
            "umo": event.unified_msg_origin,
            "group_id": group_id,
            "user_id": user_id,
            "created_at": datetime.now(self.timezone).isoformat(),
        }
        timer_storage.save_timers(self.data_dir, self.timers)

        # Schedule reminders
        intervals = scheduler.get_reminder_intervals(self.config)
        scheduler.schedule_reminders(
            self.scheduler,
            timer_id,
            boss_name,
            spawn_time,
            event.unified_msg_origin,
            self._send_reminder,
            intervals,
            self.timezone,
        )

        # Send confirmation
        display_name = boss_config.get_boss_display_name(boss_name, self.bosses)
        message = formatter.format_boss_spawn_message(
            display_name,
            spawn_time,
            self.secondary_tz,
            self.show_secondary,
        )

        yield MessageEventResult().message(message)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=100)
    async def handle_shortcut_commands(self, event: AstrMessageEvent):
        """Handle shortcut commands like 'bl', 'hz' for quick access"""
        msg = event.get_message_str().strip()
        msg = zhconv.convert(msg, 'zh-cn')
        msg = msg.lower()

        # Check if it's a list shortcut
        if msg in ["bl", "hz", "汇总", "匯總"]:
            # Call the list timers logic
            async for result in self.list_timers(event):
                yield result
            return

    @filter.command_group("boss")
    def boss_command_group(self):
        """Boss timer command group"""

    @boss_command_group.command("list", alias={"bl", "汇总", "hz", "匯總"})
    async def list_timers(self, event: AstrMessageEvent):
        """List all active boss timers (filtered by group/user)"""
        now = datetime.now(self.timezone)
        group_id = event.get_group_id()

        viewer_user_id = None if group_id else self._get_user_id(event.unified_msg_origin)

        # Collect visible timers
        visible_timers = {}
        for timer_id, timer_data in self.timers.items():
            spawn_time_str = timer_data.get("spawn_time")
            if not spawn_time_str:
                continue

            try:
                spawn_time = datetime.fromisoformat(spawn_time_str).replace(tzinfo=self.timezone)
                if spawn_time <= now:
                    continue  # Skip expired

                # Check if timer should be visible
                if not permission.should_show_timer(
                    timer_id,
                    timer_data,
                    group_id,
                    viewer_user_id,
                    self.config,
                ):
                    continue

                # Check group boss filter
                if group_id:
                    boss_name = timer_data.get("boss")
                    allowed_bosses = permission.get_allowed_bosses_for_group(group_id, self.config)
                    if allowed_bosses is not None and boss_name not in allowed_bosses:
                        continue

                visible_timers[timer_id] = timer_data
            except Exception:
                continue

        if not visible_timers:
            yield MessageEventResult().message("⏳ 当前没有活跃的boss计时器")
            return

        # Format and send
        message = formatter.format_timer_list(
            visible_timers,
            self.bosses,
            self.timezone,
            self.secondary_tz,
            self.show_secondary,
        )
        yield MessageEventResult().message(message)

    @boss_command_group.command("bosses", alias={"all", "可用", "支持", "名单"})
    async def list_all_bosses(self, event: AstrMessageEvent):
        """List all supported boss names and aliases"""
        if not self.bosses:
            yield MessageEventResult().message("❌ 没有加载任何boss配置")
            return

        lines = ["📋 所有支持的Boss列表：\n"]

        # Sort bosses by display name
        sorted_bosses = sorted(
            self.bosses.items(),
            key=lambda x: x[1].get("display_name", x[0])
        )

        for boss_key, boss_data in sorted_bosses:
            display_name = boss_data.get("display_name", boss_key)
            aliases = boss_data.get("aliases", [])
            emoji = boss_data.get("emoji", "")

            # Format: emoji + display_name + (aliases)
            alias_str = "、".join(aliases) if aliases else boss_key
            lines.append(f"{emoji} {display_name}")
            lines.append(f"   别名: {alias_str}")

        lines.append("\n使用方法：<boss名或别名> d")
        lines.append("例如：wdk d 或 维京海盗 d")

        yield MessageEventResult().message("\n".join(lines))

    @boss_command_group.command("cancel", alias={"取消", "remove", "rm", "del"})
    async def cancel_timer(self, event: AstrMessageEvent, boss_input: str):
        """Cancel a boss timer. Usage: /boss cancel wdk"""
        boss_input_lower = boss_input.lower()

        # Resolve boss name
        boss_name = boss_config.get_boss_by_alias(boss_input_lower, self.boss_alias_map)
        if not boss_name:
            yield MessageEventResult().message(
                f"❌ 未找到boss：{boss_input}\n使用 /boss bosses 查看所有支持的boss"
            )
            return

        group_id = event.get_group_id()
        current_user_id = None if group_id else self._get_user_id(event.unified_msg_origin)

        # Find and remove matching timers
        removed = []
        for timer_id, timer_data in list(self.timers.items()):
            if timer_data.get("boss") != boss_name:
                continue

            # Match location
            location_match = False
            if group_id:
                location_match = timer_data.get("group_id") == group_id
            else:
                location_match = timer_data.get("user_id") == current_user_id

            if location_match:
                # Cancel scheduled jobs
                scheduler.cancel_reminder_jobs(self.scheduler, timer_id)
                del self.timers[timer_id]
                removed.append(timer_id)

        if removed:
            timer_storage.save_timers(self.data_dir, self.timers)
            display_name = boss_config.get_boss_display_name(boss_name, self.bosses)
            yield MessageEventResult().message(
                f"✅ 已取消 {display_name} 的计时器\n使用 /boss list 查看剩余计时器"
            )
        else:
            yield MessageEventResult().message(
                f"❌ 未找到 {boss_input} 的活跃计时器\n使用 /boss list 查看所有计时器"
            )

    @boss_command_group.command("set", alias={"add", "添加", "补充"})
    async def cmd_set_boss_timer(self, event: AstrMessageEvent, boss_input: str, time_parts: tuple = ()):
        """
        Manually add a boss timer with specified spawn time.
        Usage: /boss set uk 15:30, /boss set uk 01-14 08:00
        """
        # Join time_parts to get spawn time string
        spawn_time_str = " ".join(str(p) for p in time_parts) if time_parts else ""

        if not boss_input or not spawn_time_str:
            yield MessageEventResult().message(
                f"❌ 请指定刷新时间\n\n用法：/boss add <boss名> <刷新时间>\n"
                f"示例：/boss add wdk 15:30\n"
                f"      /boss add bmm 01-11 08:00"
            )
            return

        # Check permissions
        group_id = event.get_group_id()
        if group_id:
            if not permission.is_group_enabled(group_id, self.config):
                return
        else:
            user_id = self._get_user_id(event.unified_msg_origin)
            if not permission.is_user_enabled(user_id, self.config):
                return

        # Resolve boss name
        boss_name = boss_config.get_boss_by_alias(boss_input.lower(), self.boss_alias_map)
        if not boss_name:
            yield MessageEventResult().message(
                f"❌ 未找到boss：{boss_input}\n使用 /boss help 查看所有支持的boss"
            )
            return

        # Check group boss filter
        if group_id:
            allowed_bosses = permission.get_allowed_bosses_for_group(group_id, self.config)
            if allowed_bosses is not None and boss_name not in allowed_bosses:
                logger.debug(f"Boss {boss_name} not allowed in group {group_id}")
                return

        # Parse spawn time
        try:
            spawn_time = time_utils.parse_spawn_time(spawn_time_str, self.timezone)
        except ValueError as e:
            yield MessageEventResult().message(
                f"❌ 时间格式错误：{e}\n\n支持的格式：\n"
                f"  15:30 或 15:30:45 (今天)\n"
                f"  01-11 15:30 或 01-11 15:30:45 (指定日期)"
            )
            return

        # Check if spawn time is in the future
        now = datetime.now(self.timezone)
        if spawn_time <= now:
            yield MessageEventResult().message(
                f"❌ 刷新时间必须在未来\n"
                f"指定时间：{time_utils.format_time(spawn_time, secondary_tz=self.secondary_tz, show_secondary=self.show_secondary)}\n"
                f"当前时间：{time_utils.format_time(now, secondary_tz=self.secondary_tz, show_secondary=self.show_secondary)}"
            )
            return

        current_user_id = None if group_id else self._get_user_id(event.unified_msg_origin)

        # Create timer_id without timestamp (so same boss overwrites)
        if group_id:
            timer_id = f"{group_id}_{boss_name}"
            umo = f"qq_group_{group_id}"
        else:
            timer_id = f"private_{current_user_id}_{boss_name}"
            umo = event.unified_msg_origin

        # Remove old timer and scheduled jobs if exists
        if timer_id in self.timers:
            scheduler.cancel_reminder_jobs(self.scheduler, timer_id)
            del self.timers[timer_id]

        self.timers[timer_id] = {
            "boss": boss_name,
            "spawn_time": spawn_time.isoformat(),
            "umo": umo,
            "group_id": group_id,
            "user_id": current_user_id,
        }

        # Schedule reminders
        intervals = scheduler.get_reminder_intervals(self.config)
        scheduler.schedule_reminders(
            self.scheduler,
            timer_id,
            boss_name,
            spawn_time,
            umo,
            self._send_reminder,
            intervals,
            self.timezone,
        )

        # Save timers
        timer_storage.save_timers(self.data_dir, self.timers)

        # Send confirmation
        display_name = boss_config.get_boss_display_name(boss_name, self.bosses)
        message = formatter.format_timer_added_message(
            display_name,
            spawn_time,
            self.secondary_tz,
            self.show_secondary,
        )
        yield MessageEventResult().message(message)

    @boss_command_group.command("reset", alias={"重置", "清空"})
    async def reset_timers(self, event: AstrMessageEvent):
        """Reset all boss timers. Only group admins and private chat users can use this."""
        group_id = event.get_group_id()

        # Permission check for group chat
        if group_id:
            # In group chat, only admins can reset
            if not event.is_admin():
                yield MessageEventResult().message("❌ 只有群管理员才能执行重置操作")
                return

            # Check if this group is enabled
            if not permission.is_group_enabled(group_id, self.config):
                return
        else:
            # In private chat, check if user is enabled
            user_id = self._get_user_id(event.unified_msg_origin)
            if not permission.is_user_enabled(user_id, self.config):
                return

        # Cancel all scheduled jobs
        cancelled_jobs = 0
        for job in self.scheduler.get_jobs():
            try:
                job.remove()
                cancelled_jobs += 1
            except Exception as e:
                logger.error(f"Failed to cancel job {job.id}: {e}")

        # Clear all timers
        timer_count = len(self.timers)
        self.timers.clear()

        # Save empty timers
        timer_storage.save_timers(self.data_dir, self.timers)

        # Send confirmation
        message = (
            f"✅ Boss计时器已重置\n\n"
            f"• 清除计时器：{timer_count} 个\n"
            f"• 取消定时任务：{cancelled_jobs} 个\n\n"
            f"所有boss记录已被清空"
        )
        yield MessageEventResult().message(message)

    @boss_command_group.command("help", alias={"帮助", "?"})
    async def show_help(self, event: AstrMessageEvent):
        """Show help message"""
        help_text = (
            "📖 TWOM Boss计时器使用说明\n\n"
            "━━━ 记录Boss死亡 ━━━\n格式：<boss名> d [时间]\n\n示例：\n"
            "  wdk d          → 现在\n  bmm d 23       → 当前时刻的23分\n"
            "  uk d 12:30     → 今天12:30\n  darl d 12:30:45 → 今天12:30:45\n\n"
            "支持的Boss别名：\n  wdk, bmm, uk, darl, faith, bill, 鹿, recluse 等\n"
            "  （详见 /boss list）\n\n"
            "━━━ 手动添加计时器 ━━━\n格式：/boss add <boss名> <刷新时间>\n\n示例：\n"
            "  /boss add wdk 15:30        → 今天15:30刷新\n"
            "  /boss add bmm 01-11 08:00  → 1月11日08:00刷新\n\n"
            "用途：补充之前漏记的boss死亡时间\n\n"
            "━━━ 查看计时器 ━━━\n"
            "/boss list  或  /boss bl  或  /boss hz\n"
            "快捷方式：直接输入 bl 或 hz 或 汇总\n\n"
            "━━━ 取消计时器 ━━━\n/boss cancel <boss名>\n示例：/boss cancel wdk\n\n"
            "━━━ 重置所有计时器 ━━━\n/boss reset\n清空所有boss记录（群管理员可用）\n\n"
            "━━━ 自动提醒 ━━━\n系统会在boss刷新前自动提醒：\n• 默认提前3分钟提醒\n\n"
            "提示：可在插件配置中自定义提醒时间点"
        )
        yield MessageEventResult().message(help_text)

    @filter.command_group("map")
    def map_command_group(self):
        """Map查看器命令组"""

    @map_command_group.command("list", alias={"ls", "map", "地图"})
    async def list_maps(self, event: AstrMessageEvent):
        """列出所有可用的地图"""
        if not self.maps:
            yield MessageEventResult().message("❌ 没有找到地图数据")
            return

        # Group maps by category
        maps_by_category = map_config.get_maps_by_category(self.maps)

        # Format output
        lines = ["🗺️ 可用地图列表：\n"]
        for category, map_list in sorted(maps_by_category.items()):
            lines.append(f"【{category}】")
            for map_data in map_list:
                map_id = map_data.get("id")
                name = map_data.get("name")
                aliases = map_data.get("aliases", [])
                alias_str = "、".join(aliases[:2]) if aliases else ""
                lines.append(f"  {map_id}. {name} ({alias_str})")
            lines.append("")

        lines.append("使用方法：/map <地图名或别名>")
        lines.append("例如：/map 森林 或 /map 1")

        yield MessageEventResult().message("\n".join(lines))

    @filter.regex(r"^/map\s+(.+)$")
    async def handle_map_query(self, event: AstrMessageEvent):
        """处理直接的地图查询（例如：/map 森林）"""
        message_str = event.get_message_str().strip()
        message_str = zhconv.convert(message_str, 'zh-cn')

        # Extract map input after /map
        match = re.match(r"^/map\s+(.+)$", message_str)
        if not match:
            return

        map_input = match.group(1).strip()

        # Skip if it's already a known subcommand
        if map_input.lower() in ["list", "ls", "列表", "地图", "help", "帮助"]:
            return

        # Try to show the map
        async for result in self._send_map(event, map_input):
            yield result

        # Stop event propagation to prevent LLM from responding
        event.stop_event()

    async def _send_map(self, event: AstrMessageEvent, map_input: str):
        """Internal method to send map image"""
        # Find map by ID or alias
        map_data = map_config.get_map_by_alias(map_input, self.map_alias_map)

        if not map_data:
            yield MessageEventResult().message(
                f"❌ 未找到地图：{map_input}\n使用 /map list 查看所有可用地图"
            )
            return

        # Get map file path
        map_file = map_data.get("file")
        map_path = self.assets_dir / "IMO地图查看器_files" / map_file

        if not map_path.exists():
            yield MessageEventResult().message(f"❌ 地图文件不存在：{map_file}")
            logger.error(f"Map file not found: {map_path}")
            return

        # Send the map image
        try:
            map_name = map_data.get("name")
            result = MessageEventResult()
            result.message(f"🗺️ {map_name}")
            result.image(str(map_path))
            yield result
        except Exception as e:
            logger.error(f"Failed to send map image: {e}")
            yield MessageEventResult().message(f"❌ 发送地图失败：{e}")

    async def terminate(self):
        """Cleanup on shutdown"""
        logger.info("Shutting down TWOM Boss Timer plugin")
        self.scheduler.shutdown(wait=True)
        timer_storage.save_timers(self.data_dir, self.timers)
        logger.info("TWOM Boss Timer plugin terminated")

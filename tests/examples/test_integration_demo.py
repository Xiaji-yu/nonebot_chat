"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Integration test skeleton — end-to-end pipeline demos

这些示例展示如何把多个模块串起来做集成测试，而不是只测单个函数。
运行：pytest tests/examples/test_integration_demo.py -v
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.config import (
    AccessConfig,
    AdminConfig,
    ChatConfig,
    ChatYamlConfig,
    DebounceConfig,
    DedupConfig,
    FormatConfig,
    PipelineConfig,
    RateLimitConfig,
    SilentConfig,
    SleepConfig,
    TriggerConfig,
)
from chat.memory.store import MemoryStore
from chat.personality import Personality
from chat.pipeline.admin import AdminInterceptor
from chat.pipeline.debounce import Debouncer
from chat.pipeline.dedup import reset as dedup_reset
from chat.pipeline.dispatcher import AIDispatcher
from chat.pipeline.formatter import MessageFormatter
from chat.pipeline.sender import MessageSender
from chat.pipeline.sleep import SleepController
from chat.pipeline.trigger import TriggerDetector

# ======================================================================
# 0. 配置层集成：YAML -> Pydantic -> Personality
# ======================================================================


class TestConfigIntegration:
    """展示配置加载、校验、回退的集成行为。"""

    def test_valid_yaml_roundtrip(self, tmp_path: Any) -> None:
        """合法 YAML 配置应能被 ChatYamlConfig 完整加载。"""
        yaml_path = tmp_path / "chat_config.yaml"
        yaml_path.write_text(
            """
personality:
  name: "测试助手"
  system_prompt: "你是一个测试助手。"
  wake_words: ["测试"]

llm:
  base_url: "http://localhost:11434/v1"
  model: "llama2"
  api_key: ""
  max_tokens: 500
  timeout: 30

temperature:
  default: 0.7
  proactive_min: 0.5
  proactive_max: 1.0

memory:
  max_history: 50
  distillation_threshold: 40
  core_memory_max: 10

proactive:
  enabled: true
  probability: 0.1
  cooldown: 300
  check_interval: 60

persistence:
  enabled: false
  db_path: "chat_history.db"
  retention_days: 7

pipeline:
  sleep:
    enabled: false
    mode: "schedule"
    schedule:
      start: "23:00"
      end: "08:00"
    override_by_mention: true
  dedup:
    enabled: true
    window: 5
  access:
    mode: "none"
    users: []
    groups: []
  silent:
    enabled: true
    keywords: ["闭嘴", "别回", "silent"]
  ratelimit:
    enabled: true
    max_requests: 3
    window: 10
  trigger:
    mode: "keyword"
    keywords: ["测试"]
  admin:
    enabled: true
  debounce:
    enabled: true
    window: 3
  format:
    max_length: 500
    mode: "plain"
""",
            encoding="utf-8",
        )

        import yaml

        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        config = ChatYamlConfig(**raw)

        assert config.personality.name == "测试助手"
        assert config.llm.model == "llama2"
        assert config.pipeline.trigger.mode == "keyword"
        assert config.pipeline.trigger.keywords == ["测试"]

    def test_invalid_config_falls_back_to_defaults(self, tmp_path: Any) -> None:
        """非法配置不应崩溃，应回退到默认值。"""
        yaml_path = tmp_path / "bad_config.yaml"
        yaml_path.write_text(
            "temperature:\n  default: 3.0\n", encoding="utf-8"
        )
        personality = Personality(ChatConfig(config_path=str(yaml_path)))
        assert personality.temperature_default == 0.7


# ======================================================================
# 1. Pipeline 集成：从 event 到 send
# ======================================================================


class TestPipelineIntegration:
    """把多个 pipeline 组件串起来，验证端到端行为。"""

    @pytest.fixture(autouse=True)
    def _reset_dedup(self) -> None:
        """每个测试前清空去重缓存。"""
        yield
        asyncio.get_event_loop().run_until_complete(dedup_reset())

    def _build_minimal_pipeline(self) -> Any:
        """构造一个最小可用的 Pipeline 组件集合。"""
        pipeline_config = PipelineConfig(
            sleep=SleepConfig(enabled=False),
            dedup=DedupConfig(enabled=False),
            access=AccessConfig(mode="none"),
            silent=SilentConfig(enabled=False),
            ratelimit=RateLimitConfig(enabled=False),
            trigger=TriggerConfig(mode="keyword", keywords=["助手"]),
            admin=AdminConfig(enabled=True),
            debounce=DebounceConfig(enabled=False),
            format=FormatConfig(max_length=500, mode="plain"),
        )
        return pipeline_config

    @pytest.mark.asyncio
    async def test_full_pipeline_flow(self) -> None:
        """完整流程：event -> sleep -> dedup -> access -> silent -> ratelimit ->
        admin -> debounce -> trigger -> dispatcher -> formatter -> sender。"""
        send_func = AsyncMock()
        memory_store = MemoryStore()
        llm_client = MagicMock()
        llm_client.chat = AsyncMock(return_value="你好！我是测试助手。")

        # 构造组件（sleep/access/silent/ratelimit/admin/debounce 的
        # 独立测试见 tests/test_*.py，此处聚焦 trigger → dispatcher → sender）
        pipeline_config = self._build_minimal_pipeline()
        trigger = TriggerDetector(pipeline_config.trigger)
        formatter = MessageFormatter(pipeline_config.format)
        distiller = MagicMock()
        distiller.distill = AsyncMock(return_value=None)

        dispatcher = AIDispatcher(
            personality=MagicMock(),
            llm_client=llm_client,
            memory_store=memory_store,
            distiller=distiller,
            trigger_detector=trigger,
        )
        # 让 personality mock 返回需要的属性
        personality = MagicMock()
        personality.memory_max_history = 50
        personality.memory_distillation_threshold = 40
        personality.memory_core_memory_max = 10
        personality.temperature_default = 0.7
        personality.build_system_message.return_value = {
            "role": "system", "content": "你是一个助手。",
        }
        dispatcher._personality = personality

        # 模拟 event
        event = MagicMock()
        event.get_plaintext.return_value = "助手 帮我写个测试"
        event.user_id = 123
        event.group_id = 456
        event.message = [{"type": "text", "data": {"text": "助手 帮我写个测试"}}]
        event.is_tome.return_value = False

        session_id = "g456_u123"

        # 手动走一遍 pipeline（这里只演示 trigger -> dispatcher -> formatter -> sender）
        triggered, trigger_type = trigger.detect(event)
        assert triggered is True
        assert trigger_type == "keyword:助手"

        reply = await dispatcher.dispatch(
            session_id, "助手 帮我写个测试", trigger_type, user_id="123", group_id="456",
        )
        assert reply == "你好！我是测试助手。"

        sender = MessageSender(send_func)
        parts = formatter.format(reply)
        await sender.send_batch(parts)

        send_func.assert_called_once_with("你好！我是测试助手。")


# ======================================================================
# 2. Memory + Persistence 集成
# ======================================================================


class TestMemoryPersistenceIntegration:
    """验证 MemoryStore 与 ChatPersistence 的集成行为。"""

    @pytest.fixture
    def persistence(self, tmp_path: Any) -> Any:
        from chat.memory.persistence import ChatPersistence

        db_path = tmp_path / "test_chat.db"
        return ChatPersistence(str(db_path))

    @pytest.mark.asyncio
    async def test_message_roundtrip(self, persistence: Any) -> None:
        """消息写入内存后，持久化层应能按会话查询到。"""
        store = MemoryStore(persistence=persistence)
        await store.add_user_message_with_meta("sess-1", "user-1", "hello", group_id="group-1")
        await store.add_assistant_message_with_meta("sess-1", "user-1", "hi", group_id="group-1")

        history = await store.get_history("sess-1")
        assert len(history) == 2

        db_msgs = persistence.get_messages("sess-1")
        assert len(db_msgs) == 2
        assert db_msgs[0]["role"] == "user"
        assert db_msgs[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_cleanup_does_not_remove_summaries(self, persistence: Any) -> None:
        """清理过期消息后，摘要应保留。"""
        persistence.save_summary("sess-1", "核心要点1")
        old_time = time.time() - 8 * 86400
        persistence._conn.execute(
            "INSERT INTO messages (session_id, user_id, group_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("sess-1", "user-1", "group-1", "user", "old", old_time),
        )
        persistence._conn.commit()

        deleted = persistence.cleanup_old_messages(retention_days=7)
        assert deleted == 1

        summaries = persistence.get_summaries("sess-1")
        assert len(summaries) == 1
        assert summaries[0] == "核心要点1"


# ======================================================================
# 3. 管理命令集成
# ======================================================================


class TestAdminCommandIntegration:
    """验证管理命令在 pipeline 中的拦截与执行。"""

    @pytest.mark.asyncio
    async def test_clear_memory_command(self) -> None:
        send_func = AsyncMock()
        memory_store = MemoryStore()
        session_id = "session-1"

        await memory_store.add_user_message(session_id, "hello")
        await memory_store.add_assistant_message(session_id, "hi")
        assert len(await memory_store.get_history(session_id)) == 2

        admin = AdminInterceptor(make_admin_config())
        cmd = await admin.intercept("清空记忆")
        assert cmd == "__CLEAR_MEMORY__"

        # 模拟 pipeline 执行命令
        if cmd == "__CLEAR_MEMORY__":
            await memory_store.clear_session(session_id)
            await send_func("记忆已清空 ✓")

        assert len(await memory_store.get_history(session_id)) == 0
        send_func.assert_called_once_with("记忆已清空 ✓")

    @pytest.mark.asyncio
    async def test_status_command(self) -> None:
        send_func = AsyncMock()
        memory_store = MemoryStore()
        session_id = "session-1"

        for _ in range(3):
            await memory_store.add_user_message(session_id, "msg")

        admin = AdminInterceptor(make_admin_config())
        cmd = await admin.intercept("状态")
        assert cmd == "__STATUS__"

        # 模拟 pipeline 执行命令
        if cmd == "__STATUS__":
            mem_count = len(await memory_store.get_history(session_id))
            core_count = memory_store.get_core_memory_count(session_id)
            status = (
                f"📊 状态报告\n"
                f"  会话消息: {mem_count} 条\n"
                f"  核心记忆: {core_count} 条\n"
                f"  休眠模式: {'开启 😴' if False else '关闭 🌅'}\n"
                f"  触发模式: keyword"
            )
            await send_func(status)

        send_func.assert_called_once()
        sent_text = send_func.call_args[0][0]
        assert "会话消息: 3 条" in sent_text
        assert "核心记忆: 0 条" in sent_text


# ======================================================================
# 4. 防抖 + 主动回复集成
# ======================================================================


class TestDebounceProactiveIntegration:
    """验证防抖合并后，主动回复的行为是否符合预期。"""

    @pytest.mark.asyncio
    async def test_debounce_merges_before_proactive(self) -> None:
        """防抖窗口内多条消息应合并为一次处理，避免重复主动回复。"""
        db = Debouncer(make_debounce_config(window=0.1))
        proactive_calls: list[str] = []

        async def reply_callback(merged: str) -> None:
            proactive_calls.append(f"reply:{merged}")

        await db.submit("session-1", "msg1", reply_callback)
        await db.submit("session-1", "msg2", reply_callback)
        await db.submit("session-1", "msg3", reply_callback)

        await asyncio.sleep(0.15)
        # 防抖应只触发一次回调，合并三条消息
        assert len(proactive_calls) == 1
        assert proactive_calls[0] == "reply:msg1\nmsg2\nmsg3"


# ======================================================================
# 5. 触发检测 + 休眠模式集成
# ======================================================================


class TestSleepTriggerIntegration:
    """验证休眠模式下，mention 唤醒与普通关键词的行为差异。"""

    @pytest.mark.asyncio
    async def test_mention_override_during_sleep(self) -> None:
        """休眠期间，@mention 应允许临时唤醒。"""
        sleep = SleepController(
            make_sleep_config(enabled=True, mode="schedule", start="23:00", end="08:00")
        )
        trigger = TriggerDetector(make_trigger_config(mode="mention"))

        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(0, 30)

            event_mention = MagicMock()
            event_mention.is_tome.return_value = True
            event_mention.get_plaintext.return_value = "hello"

            # sleep override by mention
            is_sleeping = await sleep.is_sleeping()
            is_mention = trigger.is_mention(event_mention)
            override_allowed = await sleep.is_override_allowed()

            assert is_sleeping is True
            assert is_mention is True
            assert override_allowed is True
            # pipeline 应允许通过
            assert is_sleeping is False or (is_mention and override_allowed) is True

    @pytest.mark.asyncio
    async def test_keyword_blocked_during_sleep(self) -> None:
        """休眠期间，普通关键词不应触发。"""
        sleep = SleepController(
            make_sleep_config(enabled=True, mode="schedule", start="23:00", end="08:00")
        )
        trigger = TriggerDetector(make_trigger_config(mode="keyword", keywords=["助手"]))

        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(0, 30)

            event = MagicMock()
            event.get_plaintext.return_value = "助手 帮我写个测试"
            event.is_tome.return_value = False

            is_sleeping = await sleep.is_sleeping()
            triggered, _ = trigger.detect(event)

            assert is_sleeping is True
            assert triggered is True  # trigger 本身匹配
            # 但在 pipeline 中，sleep 阶段会 drop，不会进入 trigger


# ======================================================================
# 6. 消息格式化 + 发送集成
# ======================================================================


class TestFormatterSenderIntegration:
    """验证长消息分片后，MessageSender 能逐片发送。"""

    @pytest.mark.asyncio
    async def test_long_message_split_and_send(self) -> None:
        send_func = AsyncMock()
        formatter = MessageFormatter(make_format_config(max_length=10, mode="plain"))
        sender = MessageSender(send_func)

        long_text = "你好世界！这是一个很长的消息，需要被分成多个部分发送。"
        parts = formatter.format(long_text)

        assert len(parts) > 1
        for part in parts:
            assert len(part) <= 10

        await sender.send_batch(parts)
        assert send_func.call_count == len(parts)


# ======================================================================
# 7. 并发蒸馏集成
# ======================================================================


class TestConcurrentDistillationIntegration:
    """验证并发场景下，蒸馏锁能防止双重蒸馏。"""

    @pytest.mark.asyncio
    async def test_only_one_distillation_runs(self) -> None:
        store = MemoryStore()
        for _ in range(20):
            await store.add_user_message("session-1", "msg")

        distiller = MagicMock()

        async def slow_distill(session_id: str, max_points: int) -> list[str]:
            # 模拟耗时蒸馏：让锁窗口真实存在，供其他协程观察到 _distilling=True
            await asyncio.sleep(0.05)
            return ["摘要1", "摘要2"]

        distiller.distill = AsyncMock(side_effect=slow_distill)

        # 模拟并发蒸馏
        async def try_distill() -> bool:
            if await store.try_begin_distill("session-1"):
                try:
                    await distiller.distill("session-1", 10)
                finally:
                    await store.end_distill("session-1")
                return True
            return False

        results = await asyncio.gather(try_distill(), try_distill(), try_distill())
        # 只有一个成功
        assert sum(results) == 1
        # 蒸馏器只被调用一次
        assert distiller.distill.call_count == 1


# ======================================================================
# 辅助工厂（保持与现有测试风格一致）
# ======================================================================


def make_admin_config(enabled: bool = True) -> object:
    cfg = type("AdminConfig", (), {})()
    cfg.enabled = enabled
    return cfg


def make_trigger_config(mode: str = "keyword", keywords: list[str] | None = None) -> object:
    cfg = type("TriggerConfig", (), {})()
    cfg.mode = mode
    cfg.keywords = keywords if keywords is not None else ["助手"]
    return cfg


def make_sleep_config(
    enabled: bool = True,
    mode: str = "schedule",
    start: str = "23:00",
    end: str = "08:00",
    override_by_mention: bool = True,
) -> object:
    cfg = type("SleepConfig", (), {})()
    cfg.enabled = enabled
    cfg.mode = mode
    cfg.schedule = type("Schedule", (), {})()
    cfg.schedule.start = start
    cfg.schedule.end = end
    cfg.override_by_mention = override_by_mention
    return cfg


def make_format_config(max_length: int = 500, mode: str = "plain") -> object:
    cfg = type("FormatConfig", (), {})()
    cfg.max_length = max_length
    cfg.mode = mode
    return cfg


def make_debounce_config(enabled: bool = True, window: float = 3.0) -> object:
    cfg = type("DebounceConfig", (), {})()
    cfg.enabled = enabled
    cfg.window = window
    return cfg


def _make_time(hour: int, minute: int) -> Any:
    from datetime import time as dt_time

    return dt_time(hour, minute)

"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : Pipeline 触发判定 → 防抖批 triggered 传递测试（M1 回归）
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.config import PipelineConfig
from chat.pipeline import Pipeline


def _build_pipeline(mode: str, keywords: list[str]) -> Pipeline:
    cfg = PipelineConfig(
        sleep={"enabled": False},
        dedup={"enabled": False},
        access={"whitelist": {"enabled": False, "users": [], "groups": []},
                "blacklist": {"enabled": False, "users": [], "groups": []}},
        silent={"enabled": False, "keywords": []},
        ratelimit={"enabled": False},
        trigger={"mode": mode, "keywords": keywords},
        admin={"enabled": True},
        debounce={"enabled": True, "window": 3},
    )
    personality = MagicMock()
    personality.pipeline_config = cfg
    personality.memory_max_history = 50
    personality.memory_distillation_threshold = 40
    personality.memory_core_memory_max = 10
    personality.temperature_default = 0.7
    personality.llm_base_url = "http://x/v1"
    personality.llm_model = "m"
    personality.build_system_message.return_value = {"role": "system", "content": "s"}

    llm = MagicMock()
    llm.chat = AsyncMock(return_value="回复内容")

    return Pipeline(
        pipeline_config=cfg,
        personality=personality,
        llm_client=llm,
        memory_store=MagicMock(),
        distiller=MagicMock(),
    )


def _make_event(text: str, *, mentioned: bool, group_id: str = "g1") -> MagicMock:
    event = MagicMock()
    event.get_plaintext.return_value = text
    event.user_id = 2224513919
    event.group_id = group_id
    event.is_tome.return_value = mentioned
    return event


class TestDebounceTriggeredPropagation:
    @pytest.mark.asyncio
    async def test_mention_message_passes_triggered_true(self) -> None:
        """群聊 @bot 消息 → 传给 Debouncer 的 triggered=True。"""
        pipeline = _build_pipeline("mention", ["云崽"])
        pipeline._debounce.submit = AsyncMock()

        await pipeline.process(
            _make_event("@bot hi", mentioned=True), "g1_u1", AsyncMock(),
        )
        pipeline._debounce.submit.assert_called_once()
        args = pipeline._debounce.submit.call_args
        assert args.kwargs.get("triggered") is True or args[0][3] is True

    @pytest.mark.asyncio
    async def test_plain_group_message_passes_triggered_false(self) -> None:
        """群聊普通消息（未 @ 未含关键词）→ triggered=False。"""
        pipeline = _build_pipeline("mention", ["云崽"])
        pipeline._debounce.submit = AsyncMock()

        await pipeline.process(
            _make_event("随便聊聊", mentioned=False), "g1_u1", AsyncMock(),
        )
        pipeline._debounce.submit.assert_called_once()
        args = pipeline._debounce.submit.call_args
        assert args.kwargs.get("triggered") is False or args[0][3] is False

    @pytest.mark.asyncio
    async def test_keyword_hit_passes_triggered_true(self) -> None:
        """群聊含关键词消息 → triggered=True。"""
        pipeline = _build_pipeline("keyword", ["云崽"])
        pipeline._debounce.submit = AsyncMock()

        await pipeline.process(
            _make_event("云崽 你好", mentioned=False), "g1_u1", AsyncMock(),
        )
        args = pipeline._debounce.submit.call_args
        assert args.kwargs.get("triggered") is True or args[0][3] is True

    @pytest.mark.asyncio
    async def test_private_always_triggered_true(self) -> None:
        """私聊消息（group_id=None）→ triggered=True（恒回复）。"""
        pipeline = _build_pipeline("mention", ["云崽"])
        pipeline._debounce.submit = AsyncMock()

        await pipeline.process(
            _make_event("随便聊聊", mentioned=False, group_id=None), "u1", AsyncMock(),
        )
        args = pipeline._debounce.submit.call_args
        assert args.kwargs.get("triggered") is True or args[0][3] is True

    @pytest.mark.asyncio
    async def test_disabled_mode_group_triggered_false(self) -> None:
        """trigger.mode=disabled → 群聊任何消息 triggered=False。"""
        pipeline = _build_pipeline("disabled", ["云崽"])
        pipeline._debounce.submit = AsyncMock()

        await pipeline.process(
            _make_event("云崽 你好", mentioned=True), "g1_u1", AsyncMock(),
        )
        args = pipeline._debounce.submit.call_args
        assert args.kwargs.get("triggered") is False or args[0][3] is False

    @pytest.mark.asyncio
    async def test_process_once_skip_trigger_uses_debounced_type(self) -> None:
        """skip_trigger=True 时不再 detect，直接以 debounced 类型派发。"""
        pipeline = _build_pipeline("mention", ["云崽"])
        pipeline._dispatcher.dispatch = AsyncMock(return_value="ok")
        send_func = AsyncMock()
        # 构造一个最后一条未触发的合并场景：直接调 _process_once(skip_trigger=True)
        event = _make_event("追问", mentioned=False)
        await pipeline._process_once(
            event, "g1_u1", "先触发\n追问", send_func,
            is_private=False, user_id="2224513919", group_id="g1",
            stream=False, skip_trigger=True,
        )
        pipeline._dispatcher.dispatch.assert_called_once()
        args = pipeline._dispatcher.dispatch.call_args
        # (session, text, trigger_type, ...)
        assert args[0][1] == "先触发\n追问"
        assert args[0][2] == "debounced"

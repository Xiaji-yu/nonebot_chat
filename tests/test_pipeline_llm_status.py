"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Pipeline 层的 LLM 连通性反馈测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.config import PipelineConfig
from chat.pipeline import Pipeline

# ── 构造辅助 ──────────────────────────────────────────────────────


def make_pipeline(llm_client: MagicMock) -> Pipeline:
    """构造最小可用的 Pipeline（各阶段用默认配置）。"""
    personality = MagicMock()
    personality.pipeline_config = PipelineConfig()
    personality.memory_max_history = 50
    personality.memory_distillation_threshold = 40
    personality.memory_core_memory_max = 10
    personality.temperature_default = 0.7
    personality.build_system_message.return_value = {
        "role": "system", "content": "你是助手。",
    }
    personality.llm_base_url = "http://localhost:11434/v1"
    personality.llm_model = "llama2"

    memory_store = MagicMock()
    memory_store.add_user_message_with_meta = AsyncMock()
    memory_store.add_user_message = AsyncMock()
    memory_store.needs_distillation = AsyncMock(return_value=False)
    distiller = MagicMock()

    return Pipeline(
        pipeline_config=PipelineConfig(),
        personality=personality,
        llm_client=llm_client,
        memory_store=memory_store,
        distiller=distiller,
    )


# ── 测试模型命令 ──────────────────────────────────────────────────


class TestTestModelCommand:
    @pytest.mark.asyncio
    async def test_test_model_success_sends_ok(self) -> None:
        llm = MagicMock()
        llm.health_check = AsyncMock(return_value=True)
        pipeline = make_pipeline(llm)
        send_func = AsyncMock()

        await pipeline._test_model(send_func)

        calls = [c.args[0] for c in send_func.call_args_list]
        assert calls[0].startswith("🔍")  # 先提示测试中
        assert any("✅" in c for c in calls)
        assert not any("❌" in c for c in calls)

    @pytest.mark.asyncio
    async def test_test_model_failure_sends_error(self) -> None:
        llm = MagicMock()
        llm.health_check = AsyncMock(return_value=False)
        pipeline = make_pipeline(llm)
        send_func = AsyncMock()

        await pipeline._test_model(send_func)

        calls = [c.args[0] for c in send_func.call_args_list]
        assert any("❌" in c for c in calls)
        assert "http://localhost:11434/v1" in next(c for c in calls if "❌" in c)

    @pytest.mark.asyncio
    async def test_test_model_without_llm_client(self) -> None:
        pipeline = make_pipeline(MagicMock())
        pipeline._llm_client = None
        send_func = AsyncMock()

        await pipeline._test_model(send_func)

        send_func.assert_called_once()
        assert "未配置" in send_func.call_args.args[0]


# ── LLM 回复失败时的区分提示 ──────────────────────────────────────


class TestLLMFailureFeedback:
    @pytest.mark.asyncio
    async def test_model_unreachable_message(self) -> None:
        """reply=None 且 health_check=False → 提示模型无法连通。"""
        llm = MagicMock()
        llm.health_check = AsyncMock(return_value=False)
        pipeline = make_pipeline(llm)
        send_func = AsyncMock()
        pipeline._dispatcher.dispatch = AsyncMock(return_value=None)

        await pipeline._process_once(
            event=MagicMock(),
            session_id="s1",
            text="hello",
            send_func=send_func,
            is_private=True,
            user_id="u1",
            group_id=None,
            stream=False,
        )

        send_func.assert_called_once()
        assert "模型无法连通" in send_func.call_args.args[0]

    @pytest.mark.asyncio
    async def test_model_ok_generic_message(self) -> None:
        """reply=None 但 health_check=True → 走通用错误文案。"""
        llm = MagicMock()
        llm.health_check = AsyncMock(return_value=True)
        pipeline = make_pipeline(llm)
        send_func = AsyncMock()
        pipeline._dispatcher.dispatch = AsyncMock(return_value=None)

        await pipeline._process_once(
            event=MagicMock(),
            session_id="s1",
            text="hello",
            send_func=send_func,
            is_private=True,
            user_id="u1",
            group_id=None,
            stream=False,
        )

        send_func.assert_called_once()
        assert "暂时无法回复" in send_func.call_args.args[0]

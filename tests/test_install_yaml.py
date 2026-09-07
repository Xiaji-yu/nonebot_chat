"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : install.py 配置向导 YAML 生成器测试
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from chat.config import ChatYamlConfig

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from install import generate_yaml


def _sample_config() -> dict:
    return {
        "personality": {
            "name": "云崽",
            "system_prompt": "你是云。\n很会编程。",
            "prompt_file": "SOUL.md",
        },
        "llm": {
            "base_url": "http://localhost:11434/v1",
            "model": "llama2",
            "api_key": "",
            "max_tokens": 1000,
            "timeout": 30,
        },
        "pipeline": {
            "access": {
                "whitelist": {"enabled": True, "users": ["2224513919"], "groups": []},
                "blacklist": {"enabled": False, "users": [], "groups": []},
            },
            "trigger": {"mode": "mention_keyword", "keywords": ["云崽", "小助手"]},
        },
    }


class TestGenerateYaml:
    def test_output_is_valid_yaml(self) -> None:
        out = generate_yaml(_sample_config())
        loaded = yaml.safe_load(out)
        assert isinstance(loaded, dict)
        assert loaded["personality"]["name"] == "云崽"

    def test_key_and_value_not_misquoted(self) -> None:
        """回归：旧 bug 把 'key: value' 整体加引号导致 YAML 非法。"""
        out = generate_yaml(_sample_config())
        assert '"name: 云崽"' not in out
        yaml.safe_load(out)  # 不应抛解析错误

    def test_multiline_prompt_keeps_newlines(self) -> None:
        out = generate_yaml(_sample_config())
        loaded = yaml.safe_load(out)
        assert "system_prompt: |" in out
        assert loaded["personality"]["system_prompt"].startswith("你是云。\n很会编程。")

    def test_roundtrip_into_chatyamlconfig(self) -> None:
        out = generate_yaml(_sample_config())
        cfg = ChatYamlConfig(**yaml.safe_load(out))
        assert cfg.personality.prompt_file == "SOUL.md"
        assert cfg.pipeline.access.whitelist.users == ["2224513919"]
        assert cfg.pipeline.trigger.mode == "mention_keyword"

    def test_scalar_quoting_for_url_and_empty(self) -> None:
        from install import _quote

        assert _quote("http://x/v1") == '"http://x/v1"'
        assert _quote("") == '""'
        assert _quote("plain") == "plain"

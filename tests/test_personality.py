"""
@Author         : Xiaji-yu
@Date           : 2026-09-07
@Description    : Personality 人格文件（SOUL.md）加载测试
"""

from __future__ import annotations

from pathlib import Path

from chat.config import ChatConfig
from chat.personality import Personality


def make_personality(tmp_path: Path, config_text: str | None = None) -> Personality:
    """在 tmp_path 构造配置目录并返回 Personality。"""
    yaml_path = tmp_path / "chat_config.yaml"
    if config_text is None:
        config_text = "personality:\n  name: 小助手\n  system_prompt: 内嵌提示\n"
    yaml_path.write_text(config_text, encoding="utf-8")
    return Personality(ChatConfig(config_path=str(yaml_path)))


class TestPersonalityPromptFile:
    def test_falls_back_to_embedded_prompt_when_no_soul(self, tmp_path: Path) -> None:
        p = make_personality(tmp_path)
        assert p.system_prompt == "内嵌提示"

    def test_auto_discovers_soul_md(self, tmp_path: Path) -> None:
        """未配置 prompt_file 时自动读取同目录 SOUL.md。"""
        (tmp_path / "SOUL.md").write_text(
            "你是云崽。一朵有脾气的小云。\n护短，嘴碎，认真帮得上忙。",
            encoding="utf-8",
        )
        p = make_personality(tmp_path)
        assert "云崽" in p.system_prompt
        assert "内嵌提示" not in p.system_prompt

    def test_prompt_file_overrides_embedded(self, tmp_path: Path) -> None:
        """显式 prompt_file 优先于内嵌 system_prompt。"""
        (tmp_path / "persona.md").write_text("显式人格文件内容", encoding="utf-8")
        cfg_text = (
            "personality:\n"
            "  name: 小助手\n"
            "  system_prompt: 内嵌提示\n"
            "  prompt_file: persona.md\n"
        )
        p = make_personality(tmp_path, cfg_text)
        assert p.system_prompt == "显式人格文件内容"

    def test_prompt_file_absolute_path(self, tmp_path: Path) -> None:
        """prompt_file 支持绝对路径。"""
        outer = tmp_path / "outer.md"
        outer.write_text("绝对路径人格", encoding="utf-8")
        cfg_text = (
            "personality:\n"
            "  name: 小助手\n"
            f"  prompt_file: {outer}\n"
        )
        p = make_personality(tmp_path, cfg_text)
        assert p.system_prompt == "绝对路径人格"

    def test_missing_prompt_file_falls_back(self, tmp_path: Path) -> None:
        """显式 prompt_file 不存在时回退内嵌 system_prompt。"""
        cfg_text = (
            "personality:\n"
            "  name: 小助手\n"
            "  system_prompt: 内嵌提示\n"
            "  prompt_file: missing.md\n"
        )
        p = make_personality(tmp_path, cfg_text)
        assert p.system_prompt == "内嵌提示"

    def test_soul_md_content_in_system_message(self, tmp_path: Path) -> None:
        """build_system_message 应使用文件内容。"""
        (tmp_path / "SOUL.md").write_text("SOUL 内容", encoding="utf-8")
        p = make_personality(tmp_path)
        msg = p.build_system_message()
        assert msg == {"role": "system", "content": "SOUL 内容"}


class TestPersonalityPromptFileRobustness:
    def test_non_utf8_soul_falls_back_without_crash(self, tmp_path: Path) -> None:
        """GBK 编码的 SOUL.md 不应崩溃，回退内嵌提示。"""
        (tmp_path / "SOUL.md").write_bytes("你是云崽。".encode("gbk"))
        p = make_personality(tmp_path)
        assert p.system_prompt == "内嵌提示"

    def test_empty_soul_falls_back(self, tmp_path: Path) -> None:
        """空 SOUL.md / 仅空白应回退内嵌提示。"""
        (tmp_path / "SOUL.md").write_text("   \n  ", encoding="utf-8")
        p = make_personality(tmp_path)
        assert p.system_prompt == "内嵌提示"

    def test_relative_prompt_file_ignores_cwd_same_name(self, tmp_path: Path, monkeypatch) -> None:
        """相对 prompt_file 应只按配置目录解析，不被进程 CWD 同名文件抢占。"""
        # 在 CWD 放置同名文件（不应被读取）
        cwd_file = Path("persona_dup.md")
        cwd_file.write_text("来自 CWD 的错误人格", encoding="utf-8")
        try:
            cfg_dir = tmp_path / "cfg"
            cfg_dir.mkdir()
            (cfg_dir / "persona_dup.md").write_text("来自配置目录的正确人格", encoding="utf-8")
            yaml_path = cfg_dir / "chat_config.yaml"
            yaml_path.write_text(
                "personality:\n"
                "  name: 小助手\n"
                "  system_prompt: 内嵌提示\n"
                "  prompt_file: persona_dup.md\n",
                encoding="utf-8",
            )
            # monkeypatch 当前工作目录到 tmp_path 之外，模拟 bot 从别处启动
            p = Personality(ChatConfig(config_path=str(yaml_path)))
            assert p.system_prompt == "来自配置目录的正确人格"
        finally:
            cwd_file.unlink(missing_ok=True)

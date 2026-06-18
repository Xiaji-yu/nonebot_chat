#!/usr/bin/env python3
"""
nonebot-chat 插件自动安装脚本

功能：
  1. 检查 Python 环境和 NoneBot2 依赖
  2. 从 GitHub 下载插件源码
  3. 安装 Python 依赖（aiohttp, pyyaml, pydantic）
  4. 交互式配置 chat_config.yaml（带默认值）
  5. 生成 NoneBot2 加载配置

用法：
  python install.py
"""

from __future__ import annotations

import os
import re
import sys
import subprocess
import tempfile
import shutil
import zipfile
from pathlib import Path
from typing import Any

# ── 常量 ──────────────────────────────────────────────────────────
GITHUB_REPO = "https://github.com/Xiaji-yu/nonebot_chat"
BRANCH = "main"
PLUGIN_DIR_NAME = "nonebot_plugin_status"  # 仓库名（作为插件包名）

REQUIRED_PYTHON = (3, 10)

# 插件依赖
PLUGIN_DEPS = {
    "aiohttp": ">=3.8",
    "pyyaml": ">=6.0",
    "pydantic": ">=2.0",
}

# NoneBot2 依赖（检查是否已安装）
NONEBOT_DEPS = {
    "nonebot2": ">=2.0.0",
    "nonebot-adapter-onebot": ">=2.0.0",
}

# ── 颜色 ──────────────────────────────────────────────────────────
class _C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def ok(cls, msg: str) -> str:
        return f"{cls.GREEN}✓{cls.RESET} {msg}"

    @classmethod
    def fail(cls, msg: str) -> str:
        return f"{cls.RED}✗{cls.RESET} {msg}"

    @classmethod
    def info(cls, msg: str) -> str:
        return f"{cls.CYAN}ℹ{cls.RESET} {msg}"

    @classmethod
    def warn(cls, msg: str) -> str:
        return f"{cls.YELLOW}⚠{cls.RESET} {msg}"

    @classmethod
    def header(cls, msg: str) -> str:
        return f"\n{cls.BOLD}{'=' * 50}\n  {msg}\n{'=' * 50}{cls.RESET}"


# ── 工具函数 ──────────────────────────────────────────────────────
def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """运行命令，返回 CompletedProcess。"""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        **kwargs,
    )


def pip_install(packages: dict[str, str]) -> bool:
    """pip install 一组包，返回是否全部成功。"""
    for pkg, spec in packages.items():
        print(f"  安装 {pkg}{spec} ...", end=" ", flush=True)
        result = run([sys.executable, "-m", "pip", "install", f"{pkg}{spec}"])
        if result.returncode == 0:
            print(_C.ok(""))
        else:
            print(_C.fail(result.stderr.strip()[:80]))
            return False
    return True


def is_package_installed(package: str) -> bool:
    """检查 pip 包是否已安装。"""
    result = run([sys.executable, "-m", "pip", "show", package])
    return result.returncode == 0


def download_zip(url: str, dest: Path) -> Path:
    """下载 GitHub zip 并解压到 dest。"""
    import urllib.request

    print(f"  下载 {url} ...", end=" ", flush=True)
    zip_path = dest / "repo.zip"
    try:
        urllib.request.urlretrieve(url, zip_path)
        print(_C.ok(""))
    except Exception as exc:
        print(_C.fail(str(exc)))
        sys.exit(1)

    print(f"  解压 ...", end=" ", flush=True)
    extract_dir = dest / "extracted"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        # GitHub zip 里有个顶层目录，需要跳过它
        for member in zf.namelist():
            # 跳过目录项和顶层目录名
            parts = Path(member).parts
            if len(parts) <= 1:
                continue
            target = extract_dir / Path(*parts[1:])
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))
    print(_C.ok(""))
    return extract_dir


# ── 交互式输入 ────────────────────────────────────────────────────
def ask(prompt: str, default: str, choices: list[str] | None = None) -> str:
    """交互式询问，带默认值。

    Args:
        prompt: 提示文本
        default: 默认值
        choices: 可选值列表（非 None 时验证输入）

    Returns:
        用户输入的字符串
    """
    while True:
        if choices:
            opts = "/".join(choices)
            raw = input(f"  {prompt} [{opts}] (默认: {default}): ").strip()
        else:
            raw = input(f"  {prompt} (默认: {default}): ").strip()
        if not raw:
            return default
        if choices and raw not in choices:
            print(f"    {_C.warn('请输入有效选项: ' + ', '.join(choices))}")
            continue
        return raw


def ask_int(prompt: str, default: int, min_val: int, max_val: int) -> int:
    """交互式询问整数。"""
    while True:
        raw = input(f"  {prompt} (默认: {default}, 范围 {min_val}-{max_val}): ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"    {_C.warn(f'请输入 {min_val}-{max_val} 之间的整数')}")


def ask_float(prompt: str, default: float, min_val: float, max_val: float) -> float:
    """交互式询问浮点数。"""
    while True:
        raw = input(f"  {prompt} (默认: {default}, 范围 {min_val}-{max_val}): ").strip()
        if not raw:
            return default
        try:
            val = float(raw)
            if min_val <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"    {_C.warn(f'请输入 {min_val}-{max_val} 之间的数值')}")


def ask_bool(prompt: str, default: bool) -> bool:
    """交互式询问是否。"""
    default_str = "Y" if default else "N"
    while True:
        raw = input(f"  {prompt} [Y/n] (默认: {default_str}): ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "true", "1"):
            return True
        if raw in ("n", "no", "false", "0"):
            return False
        print(f"    {_C.warn('请输入 Y 或 N')}")


def ask_list(prompt: str, default: list[str], item_label: str = "项目") -> list[str]:
    """交互式询问列表。

    每行输入一个值，空行结束。
    """
    print(f"  {prompt} (默认: {default})")
    print(f"    输入 {item_label}，每行一个，空行结束：")
    items: list[str] = []
    while True:
        raw = input(f"    [{len(items)+1}] ").strip()
        if not raw:
            if items:
                return items
            return default
        items.append(raw)


# ── 配置向导 ──────────────────────────────────────────────────────

class ConfigWizard:
    """交互式配置向导。"""

    # 每一步的 (说明, 默认值, 交互函数)
    STEPS: list[tuple[str, Any, Any]] = []

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}

    def run(self) -> dict[str, Any]:
        """运行交互式配置向导，返回配置字典。"""
        print(_C.header("交互式配置向导"))

        print(
            f"  所有选项都有默认值，直接回车即可使用默认。\n"
            f"  如果你不确定某项，建议保持默认。\n"
        )

        self._step_personality()
        self._step_llm()
        self._step_temperature()
        self._step_memory()
        self._step_proactive()
        self._step_sleep()
        self._step_dedup()
        self._step_access()
        self._step_silent()
        self._step_ratelimit()
        self._step_trigger()
        self._step_admin()
        self._step_debounce()
        self._step_format()

        print(f"\n{_C.ok('配置完成！')}")
        return self.config

    def _step_personality(self) -> None:
        print(f"\n{_C.CYAN}▸ 人格配置{_C.RESET}")
        self.config["personality"] = {
            "name": ask("人格名称", "小助手"),
            "system_prompt": self._ask_multiline(
                "系统提示词（System Prompt）",
                "你是一个友善、聪明的助手，名叫小助手。\n"
                "请用简洁、自然的语气回复，避免过于正式或机械的表达。\n"
                "适当使用 emoji，但不要过度。记住和用户的历史对话上下文。",
            ),
            "wake_words": ask_list(
                "唤醒词列表（子串匹配，不区分大小写）",
                ["小助手", "bot"],
                "唤醒词",
            ),
        }

    def _step_llm(self) -> None:
        print(f"\n{_C.CYAN}▸ LLM 配置{_C.RESET}")
        self.config["llm"] = {
            "base_url": ask(
                "API 基础地址",
                "http://localhost:11434/v1",
            ),
            "model": ask("模型名称", "llama2"),
            "api_key": ask("API 密钥（Ollama 等本地服务可留空）", ""),
            "max_tokens": ask_int("单次生成最大 token 数", 1000, 1, 8192),
            "timeout": ask_int("API 请求超时时间（秒）", 30, 5, 120),
        }

    def _step_temperature(self) -> None:
        print(f"\n{_C.CYAN}▸ 温度配置{_C.RESET}")
        print("  （温度越高回复越有创意，0.7 为平衡值）")
        default = 0.7
        default_min = 0.5
        default_max = 1.0
        t_default = ask_float("普通回复温度", default, 0.0, 2.0)
        t_min = ask_float("主动回复温度下限", default_min, 0.0, 2.0)
        t_max = ask_float("主动回复温度上限", default_max, 0.0, 2.0)
        # 确保 min <= max
        if t_min > t_max:
            t_min, t_max = t_max, t_min
            print(f"    {_C.warn('温度上下限已自动交换以确保 min <= max')}")
        self.config["temperature"] = {
            "default": t_default,
            "proactive_min": t_min,
            "proactive_max": t_max,
        }

    def _step_memory(self) -> None:
        print(f"\n{_C.CYAN}▸ 记忆系统配置{_C.RESET}")
        max_hist = ask_int("单会话最大消息条数", 50, 5, 500)
        threshold = ask_int("蒸馏触发阈值（必须 < 最大消息数）", 40, 10, 200)
        core_max = ask_int("蒸馏后保留的核心摘要条数", 10, 1, 50)
        # 交叉校验
        if threshold >= max_hist:
            print(f"    {_C.warn(f'阈值 {threshold} >= 最大消息数 {max_hist}，已自动调整')}")
            threshold = max(max_hist - 5, 10)
        if core_max > max_hist:
            core_max = max_hist
        self.config["memory"] = {
            "max_history": max_hist,
            "distillation_threshold": threshold,
            "core_memory_max": core_max,
        }

    def _step_proactive(self) -> None:
        print(f"\n{_C.CYAN}▸ 主动回复配置{_C.RESET}")
        self.config["proactive"] = {
            "enabled": ask_bool("是否启用主动回复", True),
            "probability": ask_float("主动回复概率（0.0-1.0）", 0.1, 0.0, 1.0),
            "cooldown": ask_int("主动回复冷却时间（秒）", 300, 30, 3600),
            "check_interval": ask_int("检查间隔（秒）", 60, 10, 600),
        }

    def _step_sleep(self) -> None:
        print(f"\n{_C.CYAN}▸ 休眠模式配置{_C.RESET}")
        enabled = ask_bool("是否启用休眠模式", False)
        mode = "schedule"
        schedule: dict[str, str] = {}
        override = True
        if enabled:
            mode = ask("休眠模式（schedule=定时 / manual=手动）", "schedule",
                        choices=["schedule", "manual"])
            if mode == "schedule":
                start = ask("休眠开始时间（HH:MM）", "23:00")
                end = ask("休眠结束时间（HH:MM）", "08:00")
                schedule = {"start": start, "end": end}
            override = ask_bool("@mention 是否可临时唤醒（休眠期间）", True)
        self.config["pipeline"] = {
            "sleep": {
                "enabled": enabled,
                "mode": mode,
                "schedule": schedule,
                "override_by_mention": override,
            },
        }

    def _step_dedup(self) -> None:
        print(f"\n{_C.CYAN}▸ 去重配置{_C.RESET}")
        self.config["pipeline"]["dedup"] = {
            "enabled": ask_bool("是否启用内容去重", True),
            "window": ask_int("去重时间窗口（秒）", 5, 1, 60),
        }

    def _step_access(self) -> None:
        print(f"\n{_C.CYAN}▸ 黑白名单配置{_C.RESET}")
        print("  mode=none 不过滤；whitelist 仅名单内可用；blacklist 拦截名单内")
        mode = ask("访问模式", "none", choices=["none", "whitelist", "blacklist"])
        users: list[str] = []
        groups: list[str] = []
        if mode != "none":
            if ask_bool("是否配置用户白名单/黑名单", False):
                users = ask_list("用户 ID 列表（QQ 号）", [], "QQ 号")
            if ask_bool("是否配置群组白名单/黑名单", False):
                groups = ask_list("群 ID 列表", [], "群 ID")
        self.config["pipeline"]["access"] = {
            "mode": mode,
            "users": users,
            "groups": groups,
        }

    def _step_silent(self) -> None:
        print(f"\n{_C.CYAN}▸ 静默关键词配置{_C.RESET}")
        enabled = ask_bool("是否启用静默关键词", True)
        keywords: list[str] = []
        if enabled:
            keywords = ask_list(
                "静默关键词列表（命中则跳过回复）",
                ["闭嘴", "别回", "silent"],
                "关键词",
            )
        self.config["pipeline"]["silent"] = {
            "enabled": enabled,
            "keywords": keywords,
        }

    def _step_ratelimit(self) -> None:
        print(f"\n{_C.CYAN}▸ 频控配置{_C.RESET}")
        self.config["pipeline"]["ratelimit"] = {
            "enabled": ask_bool("是否启用频控", True),
            "max_requests": ask_int("窗口内最大请求次数", 3, 1, 100),
            "window": ask_int("时间窗口（秒）", 10, 1, 300),
        }

    def _step_trigger(self) -> None:
        print(f"\n{_C.CYAN}▸ 触发检测配置{_C.RESET}")
        print("  mention=@机器人触发  keyword=关键词触发  spectator=所有消息")
        mode = ask("触发模式", "keyword", choices=["mention", "keyword", "spectator"])
        keywords: list[str] = []
        if mode == "keyword":
            keywords = ask_list(
                "触发关键词列表",
                ["小助手", "bot"],
                "关键词",
            )
        self.config["pipeline"]["trigger"] = {
            "mode": mode,
            "keywords": keywords,
        }

    def _step_admin(self) -> None:
        print(f"\n{_C.CYAN}▸ 管理命令配置{_C.RESET}")
        self.config["pipeline"]["admin"] = {
            "enabled": ask_bool("是否启用管理命令", True),
        }

    def _step_debounce(self) -> None:
        print(f"\n{_C.CYAN}▸ 防抖合并配置{_C.RESET}")
        self.config["pipeline"]["debounce"] = {
            "enabled": ask_bool("是否启用防抖合并", True),
            "window": ask_int("防抖窗口（秒）", 3, 1, 30),
        }

    def _step_format(self) -> None:
        print(f"\n{_C.CYAN}▸ 消息格式化配置{_C.RESET}")
        self.config["pipeline"]["format"] = {
            "max_length": ask_int("单条消息最大字符数", 500, 100, 2000),
            "mode": ask("格式化模式", "plain", choices=["plain", "markdown"]),
        }

    @staticmethod
    def _ask_multiline(prompt: str, default: str) -> str:
        """多行文本输入。空行结束。"""
        print(f"  {prompt}（空行结束，直接回车使用默认）：")
        if not default:
            print(f"    （默认值为空）")
        lines: list[str] = []
        use_default = True
        while True:
            raw = input("    ").rstrip()
            if not raw and not lines:
                return default
            if not raw:
                break
            use_default = False
            lines.append(raw)
        if use_default:
            return default
        return "\n".join(lines)


# ── 配置写入 ──────────────────────────────────────────────────────

def generate_yaml(config: dict[str, Any]) -> str:
    """将配置字典序列化为带注释的 YAML。"""
    lines: list[str] = [
        "# ============================================================",
        "#  nonebot_chat 配置文件",
        "#  由 install.py 自动生成，也可手动编辑",
        "# ============================================================",
        "",
    ]
    _write_section(config, lines, indent=0)
    return "\n".join(lines)


def _write_section(data: dict[str, Any], lines: list[str], indent: int) -> None:
    """递归写入配置段。"""
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            _write_section(value, lines, indent + 1)
        elif isinstance(value, list):
            if not value:
                lines.append(f"{prefix}{key}: []")
            elif all(isinstance(v, str) for v in value):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f'{prefix}  - "{item}"')
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, str):
            if "\n" in value:
                lines.append(f"{prefix}{key}: |")
                for line in value.split("\n"):
                    lines.append(f"{prefix}  {line}")
            else:
                lines.append(f'{prefix}{key}: "{value}"')
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{prefix}{key}: {value}")


# ── NoneBot2 集成指引 ─────────────────────────────────────────────

def print_setup_guide(plugin_install_dir: Path, config_path: Path) -> None:
    """打印 NoneBot2 集成指引。"""
    print(_C.header("安装完成！"))

    print(f"\n  插件目录: {plugin_install_dir}")
    print(f"  配置文件: {config_path}")

    print(f"\n{_C.CYAN}▸ 在 bot.py 中加载插件：{_C.RESET}")
    print()
    print("    import nonebot")
    print("    from nonebot.adapters.onebot import Bot, Event")
    print()
    print("    nonebot.init()")
    print("    nonebot.load_plugin('nonebot_plugin_status.chat')")
    print()
    print("    if __name__ == '__main__':")
    print("        nonebot.run()")
    print()

    print(f"{_C.CYAN}▸ 确保 bot.py 所在目录存在 .env 文件：{_C.RESET}")
    print()
    print("    # .env 示例")
    print("    DRIVER=~nonebot + nonebot.drivers.httpx")
    print("    ADAPTERS=~nonebot + nonebot.adapters.onebot")
    print()

    print(f"{_C.CYAN}▸ 如果使用 nb-cli 创建的项目：{_C.RESET}")
    print()
    print("    1. 将插件目录复制到 bot 项目的 plugins/ 目录下")
    print(f"       复制: {plugin_install_dir}")
    print("       到:   <你的bot项目>/plugins/nonebot_plugin_status/")
    print()
    print("    2. 或者在 bot.py 中按上述方式加载")
    print()
    print(f"{_C.CYAN}▸ 管理命令（在对话中发送）：{_C.RESET}")
    print()
    print("    清空记忆 / clear  — 清空当前会话记忆")
    print("    状态   / status   — 查看会话状态")
    print("    休眠   / sleep    — 切换休眠模式")
    print("    唤醒   / wake     — 强制唤醒")
    print()


# ── 主流程 ────────────────────────────────────────────────────────

def check_python() -> bool:
    """检查 Python 版本。"""
    version = sys.version_info[:2]
    if version >= REQUIRED_PYTHON:
        print(_C.ok(f"Python {version[0]}.{version[1]}"))
        return True
    print(_C.fail(
        f"Python {version[0]}.{version[1]}，需要 >= {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}"
    ))
    return False


def check_nonebot() -> tuple[bool, bool]:
    """检查 NoneBot2 依赖。

    Returns:
        (has_nonebot, has_adapter)
    """
    has_nb = is_package_installed("nonebot2")
    has_adapter = is_package_installed("nonebot_adapter_onebot")

    if has_nb:
        print(_C.ok("nonebot2 已安装"))
    else:
        print(_C.warn("nonebot2 未安装"))

    if has_adapter:
        print(_C.ok("nonebot-adapter-onebot 已安装"))
    else:
        print(_C.warn("nonebot-adapter-onebot 未安装"))

    return has_nb, has_adapter


def install_plugin_deps() -> bool:
    """安装插件依赖。"""
    print(f"\n{_C.header('安装插件依赖')}")
    return pip_install(PLUGIN_DEPS)


def install_nonebot_deps() -> bool:
    """安装 NoneBot2 依赖（如需要）。"""
    print(f"\n{_C.header('检查 NoneBot2 依赖')}")
    has_nb, has_adapter = check_nonebot()

    if has_nb and has_adapter:
        print(_C.ok("NoneBot2 依赖完整"))
        return True

    missing = {}
    if not has_nb:
        missing.update(NONEBOT_DEPS)
    if not has_adapter:
        missing["nonebot-adapter-onebot"] = ">=2.0.0"

    print(f"\n  需要安装缺失的依赖：")
    for pkg in missing:
        print(f"    - {pkg}")

    if not ask_bool("\n是否自动安装？", True):
        print(f"  {_C.warn('请手动安装后重新运行此脚本')}")
        return False

    return pip_install(missing)


def download_plugin(dest: Path) -> Path:
    """下载插件源码。"""
    print(f"\n{_C.header('下载插件')}")
    print(f"  仓库: {GITHUB_REPO}")
    print(f"  分支: {BRANCH}")

    zip_url = f"{GITHUB_REPO}/archive/refs/heads/{BRANCH}.zip"
    extracted = download_zip(zip_url, dest)
    return extracted


def locate_plugin_dir(extracted: Path) -> Path | None:
    """从解压目录中找到插件包目录。"""
    for child in extracted.iterdir():
        if child.is_dir() and (child / "chat").is_dir():
            return child
    return None


def interactive_config() -> dict[str, Any]:
    """运行交互式配置向导。"""
    wizard = ConfigWizard()
    return wizard.run()


def write_config(config: dict[str, Any], dest: Path) -> Path:
    """写入配置文件。"""
    yaml_content = generate_yaml(config)
    config_path = dest / "chat_config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")
    print(_C.ok(f"配置文件已写入: {config_path}"))
    return config_path


def main() -> None:
    """主流程。"""
    print(f"\n{_C.BOLD}{_C.CYAN}{'=' * 50}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}  nonebot_chat 插件自动安装脚本{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}{'=' * 50}{_C.RESET}")

    # 1. 检查 Python
    print(f"\n{_C.header('检查 Python 环境')}")
    if not check_python():
        sys.exit(1)

    # 2. 检查 NoneBot2
    install_nonebot_deps()

    # 3. 安装插件依赖
    install_plugin_deps()

    # 4. 下载插件
    tmp = Path(tempfile.mkdtemp(prefix="nonebot_chat_install_"))
    try:
        extracted = download_plugin(tmp)
        plugin_src = locate_plugin_dir(extracted)
        if plugin_src is None:
            print(_C.fail("无法在下载的仓库中找到 chat/ 目录"))
            sys.exit(1)

        # 5. 确定安装位置
        print(f"\n{_C.header('选择安装位置')}")
        print(f"  源码位置: {plugin_src}")
        print()
        print("  安装选项：")
        print("    1. 当前目录下的 plugins/ 文件夹（推荐用于 nb-cli 项目）")
        print("    2. 自定义路径")
        print("    3. 仅生成配置文件（手动复制源码）")

        choice = ask("选择安装方式", "1", choices=["1", "2", "3"])

        if choice == "1":
            install_dir = Path.cwd() / "plugins" / "nonebot_plugin_status"
            install_dir.parent.mkdir(parents=True, exist_ok=True)
            if install_dir.exists():
                if not ask_bool(f"目录已存在 {install_dir}，是否覆盖？", False):
                    print("  已取消")
                    sys.exit(0)
                shutil.rmtree(install_dir)
            shutil.copytree(plugin_src, install_dir)
            print(_C.ok(f"插件已安装到: {install_dir}"))

        elif choice == "2":
            custom = input("  请输入安装路径: ").strip()
            install_dir = Path(custom).expanduser().resolve()
            install_dir.parent.mkdir(parents=True, exist_ok=True)
            if install_dir.exists():
                if not ask_bool(f"目录已存在 {install_dir}，是否覆盖？", False):
                    print("  已取消")
                    sys.exit(0)
                shutil.rmtree(install_dir)
            shutil.copytree(plugin_src, install_dir)
            print(_C.ok(f"插件已安装到: {install_dir}"))

        else:
            install_dir = plugin_src
            print(f"  将使用源码目录: {install_dir}")

        # 6. 交互式配置
        config = interactive_config()
        config_path = write_config(config, install_dir)

        # 7. 输出指引
        print_setup_guide(install_dir, config_path)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{_C.warn('安装已取消')}")
        sys.exit(0)

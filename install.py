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
PLUGIN_DIR_NAME = "nonebot_chat"

REQUIRED_PYTHON = (3, 10)

PLUGIN_DEPS = {
    "aiohttp": ">=3.8",
    "pyyaml": ">=6.0",
    "pydantic": ">=2.0",
}

NONEBOT_DEPS = {
    "nonebot2": ">=2.0.0",
    "nonebot-adapter-onebot": ">=2.0.0",
}

# YAML 需要转义的特殊字符
_YAML_SPECIAL = re.compile(r'[\\"\n\r\t#:{}[\]&*?|>!%`@]')

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
    """检查 pip 包是否已安装（通过 argv 传递，避免代码注入）。"""
    result = run(
        [sys.executable, "-c",
         "import importlib.metadata, sys; "
         "print(importlib.metadata.version(sys.argv[1]))",
         "--", package]
    )
    return result.returncode == 0


# ── YAML 安全转义 ─────────────────────────────────────────────────

def _yaml_escape(value: str) -> str:
    """对 YAML 双引号字符串内的特殊字符做完整转义。"""
    # 先处理反斜杠（必须在处理引号之前）
    value = value.replace("\\", "\\\\")
    # 处理双引号
    value = value.replace('"', '\\"')
    # 处理控制字符
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    # 换行在字面量块标量中天然安全，但在双引号中需转义
    value = value.replace("\n", "\\n")
    return value


def _yaml_escape_literal_block(value: str) -> str:
    """对 YAML 字面量块标量（|）中的每行做安全处理。

    防止行首的 --- 和 ... 被解析为 YAML 文档标记。
    """
    lines = value.split("\n")
    escaped = []
    for line in lines:
        # 行首空白缩进保留，内容部分转义文档标记
        stripped = line.lstrip(" ")
        if stripped in ("---", "...") or stripped.startswith("--- ") or stripped.startswith("... "):
            indent = line[:len(line) - len(stripped)]
            escaped.append(f"{indent}# {stripped.lstrip('#').strip()}")
        else:
            escaped.append(line)
    return "\n".join(escaped)


# ── 下载与解压 ────────────────────────────────────────────────────

def download_zip(url: str, dest: Path) -> Path:
    """下载 GitHub zip 并解压到 dest（带路径遍历防护）。"""
    import urllib.request

    print(f"  下载 {url} ...", end=" ", flush=True)
    zip_path = dest / "repo.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "nonebot-chat-installer"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        zip_path.write_bytes(data)
        print(_C.ok(""))
    except Exception as exc:
        print(_C.fail(str(exc)))
        sys.exit(1)

    print(f"  解压 ...", end=" ", flush=True)
    extract_dir = dest / "extracted"
    extract_dir.mkdir(exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            _safe_extract(zf, extract_dir)
        print(_C.ok(""))
    except zipfile.BadZipFile as exc:
        print(_C.fail(f"损坏的 ZIP 文件: {exc}"))
        sys.exit(1)
    except Exception as exc:
        print(_C.fail(f"解压失败: {exc}"))
        sys.exit(1)

    return extract_dir


def _safe_extract(zf: zipfile.ZipFile, extract_dir: Path) -> None:
    """安全解压 ZIP，防止路径遍历攻击。

    校验每个成员的解析路径是否在 extract_dir 内。
    """
    extract_resolved = extract_dir.resolve()

    for member in zf.namelist():
        # 跳过目录项和顶层目录名
        parts = Path(member).parts
        if len(parts) <= 1:
            continue

        target = extract_dir / Path(*parts[1:])
        target_resolved = target.resolve()

        # 路径遍历防护：确保目标在提取目录内
        try:
            target_resolved.relative_to(extract_resolved)
        except ValueError:
            print(f"\n  {_C.warn(f'跳过可疑路径: {member}')}")
            continue

        if member.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(member))


# ── 交互式输入 ────────────────────────────────────────────────────

def ask(prompt: str, default: str, choices: list[str] | None = None) -> str:
    """交互式询问，带默认值。"""
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
    """交互式询问列表。每行输入一个值，空行结束。"""
    print(f"  {prompt} (直接回车使用默认)")
    print(f"    输入 {item_label}，每行一个，空行结束：")
    items: list[str] = []
    while True:
        raw = input(f"    [{len(items) + 1}] ").strip()
        if not raw:
            if items:
                return items
            return list(default)
        items.append(raw)


def ask_time(prompt: str, default: str) -> str:
    """交互式询问时间（HH:MM 格式）。"""
    while True:
        raw = input(f"  {prompt} (默认: {default}): ").strip()
        if not raw:
            return default
        if re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", raw):
            return raw
        print(f"    {_C.warn('请输入有效时间，格式 HH:MM（如 23:30）')}")


# ── 配置向导 ──────────────────────────────────────────────────────

class ConfigWizard:
    """交互式配置向导。"""

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
                "系统提示词（System Prompt，空行使用默认）",
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
            "base_url": ask("API 基础地址", "http://localhost:11434/v1"),
            "model": ask("模型名称", "llama2"),
            "api_key": ask("API 密钥（Ollama 等本地服务可留空）", ""),
            "max_tokens": ask_int("单次生成最大 token 数", 1000, 1, 8192),
            "timeout": ask_int("API 请求超时时间（秒）", 30, 5, 120),
        }

    def _step_temperature(self) -> None:
        print(f"\n{_C.CYAN}▸ 温度配置{_C.RESET}")
        print("  （温度越高回复越有创意，0.7 为平衡值）")
        t_default = ask_float("普通回复温度", 0.7, 0.0, 2.0)
        t_min = ask_float("主动回复温度下限", 0.5, 0.0, 2.0)
        t_max = ask_float("主动回复温度上限", 1.0, 0.0, 2.0)
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
            mode = ask("休眠模式", "schedule", choices=["schedule", "manual"])
            if mode == "schedule":
                start = ask_time("休眠开始时间（HH:MM）", "23:00")
                end = ask_time("休眠结束时间（HH:MM）", "08:00")
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
            if ask_bool("是否配置用户名单", False):
                users = ask_list("用户 ID 列表（QQ 号）", [], "QQ 号")
            if ask_bool("是否配置群组名单", False):
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
        print("  mention=@机器人  keyword=关键词  spectator=所有消息")
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
            "enabled": ask_bool("是否启用防抖", True),
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
        """多行文本输入。空行结束，直接回车使用默认。"""
        print(f"  {prompt}：")
        lines: list[str] = []
        while True:
            raw = input("    ").rstrip()
            if not raw and not lines:
                return default
            if not raw:
                break
            lines.append(raw)
        return "\n".join(lines)


# ── 配置写入（安全 YAML 序列化） ─────────────────────────────────

def _yaml_scalar(value: str, indent: int, literal_block: bool = False) -> str:
    """安全地序列化一个 YAML 标量值。

    Args:
        value: 原始字符串值
        indent: 缩进层级
        literal_block: 是否使用字面量块标量（|）

    Returns:
        安全的 YAML 标量行
    """
    prefix = "  " * indent

    if literal_block and "\n" in value:
        # 字面量块标量：处理文档标记注入
        safe_value = _yaml_escape_literal_block(value)
        lines = safe_value.split("\n")
        result = [f"{prefix}|"]
        for line in lines:
            result.append(f"{prefix}  {line}")
        return "\n".join(result)

    # 检测是否需要引号包裹
    if _YAML_SPECIAL.search(value):
        # 需要转义的双引号字符串
        escaped = _yaml_escape(value)
        return f'{prefix}"{escaped}"'

    return f"{prefix}{value}"


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
                    safe_item = _yaml_escape(item)
                    lines.append(f'{prefix}  - "{safe_item}"')
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, str):
            lines.append(_yaml_scalar(f"{key}: {value}", indent))
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{prefix}{key}: {value}")


# ── 路径安全 ──────────────────────────────────────────────────────

def _validate_install_path(install_dir: Path) -> tuple[bool, str]:
    """验证安装路径是否安全。

    Returns:
        (safe, reason)
    """
    try:
        resolved = install_dir.resolve()
    except (OSError, RuntimeError) as exc:
        return False, f"无法解析路径: {exc}"

    # 检查是否在系统敏感目录下
    system_paths = [
        Path("/etc"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/System"),
        Path("/Windows"),
        Path("/Program Files"),
    ]
    for sp in system_paths:
        try:
            resolved.relative_to(sp.resolve())
            return False, f"不能安装到系统目录: {sp}"
        except ValueError:
            pass

    return True, ""


# ── NoneBot2 集成指引 ─────────────────────────────────────────────

def print_setup_guide(plugin_install_dir: Path, config_path: Path) -> None:
    """打印 NoneBot2 集成指引。"""
    print(_C.header("安装完成！"))

    print(f"\n  插件目录: {plugin_install_dir}")
    print(f"  配置文件: {config_path}")

    print(f"\n{_C.CYAN}▸ 在 bot.py 中加载插件：{_C.RESET}")
    print()
    print("    import nonebot")
    print()
    print("    nonebot.init()")
    print("    nonebot.load_plugin('nonebot_chat.chat')")
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
    print("       到:   <你的bot项目>/plugins/nonebot_chat/")
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
    """检查 NoneBot2 依赖。"""
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
    """写入配置文件（含 chat_enabled 和 only_superusers）。"""
    config_path = dest / "chat_config.yaml"

    # 如果已存在则备份
    if config_path.exists():
        backup = config_path.with_suffix(".yaml.bak")
        shutil.copy2(config_path, backup)
        print(f"  {_C.info(f'已有配置已备份到: {backup}')}")

    # 补充运行时配置
    if "chat_enabled" not in config:
        config["chat_enabled"] = ask_bool("是否启用聊天功能", True)
    if "only_superusers" not in config:
        config["only_superusers"] = ask_bool("是否仅允许超级用户使用", True)

    yaml_content = generate_yaml(config)
    config_path.write_text(yaml_content, encoding="utf-8")

    # 设置 restrictive 文件权限（仅 owner 可读写）
    try:
        os.chmod(config_path, 0o600)
    except OSError:
        pass  # Windows 等不支持 chmod 的平台静默跳过

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
    if not install_nonebot_deps():
        print(_C.fail("NoneBot2 依赖安装失败"))
        sys.exit(1)

    # 3. 安装插件依赖
    if not install_plugin_deps():
        print(_C.fail("插件依赖安装失败"))
        sys.exit(1)

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
            install_dir = Path.cwd() / "plugins" / PLUGIN_DIR_NAME
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
            if not custom:
                print("  " + _C.warn("路径不能为空"))
                sys.exit(1)

            install_dir = Path(custom).expanduser().resolve()

            # 路径安全检查
            safe, reason = _validate_install_path(install_dir)
            if not safe:
                print(f"  {_C.fail(reason)}")
                sys.exit(1)

            print(f"  将安装到: {install_dir}")
            if not ask_bool("确认此路径？", True):
                print("  已取消")
                sys.exit(0)

            install_dir.parent.mkdir(parents=True, exist_ok=True)
            if install_dir.exists():
                if not ask_bool(f"目录已存在，是否覆盖？", False):
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

        # 7. 完成指引
        print_setup_guide(install_dir, config_path)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{_C.warn('安装已取消')}")
        sys.exit(0)
    except Exception as exc:
        print(f"\n{_C.fail(f'安装出错: {exc}')}")
        sys.exit(1)

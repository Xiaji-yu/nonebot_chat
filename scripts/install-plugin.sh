#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Xiaji-yu/nonebot_chat.git"
PLUGIN_DIR="plugins/nonebot_chat"
LOAD_LINE='nonebot.load_plugin("plugins.nonebot_chat.chat")'
PYPROJECT_FILE="pyproject.toml"

# ------------------------------------------------------------------
# 0. 项目形态检测
#    legacy : 传统项目（有 bot.py），通过修改 bot.py 注册
#    nbcli  : nb-cli 脚手架项目（无 bot.py，pyproject.toml 含 [tool.nonebot]）
# ------------------------------------------------------------------
MODE="unknown"
if [[ -f "bot.py" ]]; then
    MODE="legacy"
elif [[ -f "$PYPROJECT_FILE" ]] && grep -q '^\[tool\.nonebot\]' "$PYPROJECT_FILE"; then
    MODE="nbcli"
fi

if [[ "$MODE" == "unknown" ]]; then
    echo "错误: 未检测到可用的项目形态。"
    echo "  - 传统项目需要存在 bot.py"
    echo "  - nb-cli 脚手架项目需要 pyproject.toml 且含 [tool.nonebot]"
    echo "请切换到 bot 项目根目录后重试。"
    exit 1
fi

echo "检测到项目形态: ${MODE}"

# ------------------------------------------------------------------
# 1. 获取插件源码（两种形态都克隆到 plugins/，方便本地查看/修改）
# ------------------------------------------------------------------
mkdir -p plugins
if [[ -d "$PLUGIN_DIR" ]]; then
    echo "提示: $PLUGIN_DIR 已存在，跳过 git clone。"
else
    echo "正在克隆 nonebot_chat -> $PLUGIN_DIR ..."
    git clone "$REPO_URL" "$PLUGIN_DIR"
fi

# ------------------------------------------------------------------
# 2a. legacy：修改 bot.py 注册插件
# ------------------------------------------------------------------
install_legacy() {
    if grep -qF "$LOAD_LINE" bot.py; then
        echo "提示: bot.py 已包含插件加载行，跳过修改。"
    else
        echo "正在修改 bot.py ..."
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        cp "bot.py" "bot.py.bak.$TIMESTAMP"

        if grep -q "nonebot.init()" bot.py; then
            sed -i "/nonebot.init()/a $LOAD_LINE" bot.py
        else
            {
                echo ""
                echo "# Auto-loaded by nonebot_chat installer"
                echo "$LOAD_LINE"
            } >> bot.py
        fi
        echo "已修改 bot.py，原文件备份为 bot.py.bak.$TIMESTAMP"
    fi
}

# ------------------------------------------------------------------
# 2b. nbcli：安装依赖并在 pyproject.toml 注册插件
# ------------------------------------------------------------------
install_plugin_deps() {
    # 可编辑安装本地源码，使 `import chat` 可用（nb-cli 靠模块名加载）
    # 注意: uv 只用长选项 --editable（-e 会被解析为未知参数）
    if command -v uv >/dev/null 2>&1 && [[ -f "uv.lock" ]]; then
        uv add --editable "$PLUGIN_DIR"
    elif [[ -n "${VIRTUAL_ENV:-}" ]] && command -v pip >/dev/null 2>&1; then
        pip install -e "$PLUGIN_DIR"
    elif [[ -x ".venv/bin/pip" ]]; then
        .venv/bin/pip install -e "$PLUGIN_DIR"
    else
        echo "警告: 未检测到 uv 或虚拟环境，请手动安装插件:"
        echo "      uv add --editable $PLUGIN_DIR   # 或激活 venv 后 pip install -e $PLUGIN_DIR"
    fi
}

register_pyproject() {
    cp "$PYPROJECT_FILE" "$PYPROJECT_FILE.bak.$(date +%Y%m%d%H%M%S)"

    python3 - "$PYPROJECT_FILE" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    text = f.read()

# 已注册则跳过
if re.search(r'^"?nonebot-chat"?\s*=', text, re.M):
    print("pyproject.toml 已声明 nonebot-chat，跳过注册。")
    sys.exit(0)

# 情形 A: [tool.nonebot.plugins] 段已存在 → 在段内追加一行
m = re.search(r'^\[tool\.nonebot\.plugins\]\s*$', text, re.M)
if m:
    head = text[:m.end()]
    tail = text[m.end():]
    nxt = re.search(r'^\s*\[', tail, re.M)
    if nxt:
        seg_body, seg_rest = tail[:nxt.start()], tail[nxt.start():]
    else:
        seg_body, seg_rest = tail, ""
    seg_body = seg_body.rstrip("\n")
    if seg_body.strip():
        new = head + seg_body + '\n"nonebot-chat" = ["chat"]\n' + seg_rest.lstrip("\n")
    else:
        new = head + '\n"nonebot-chat" = ["chat"]\n' + seg_rest.lstrip("\n")
    text = new
    print('已在 [tool.nonebot.plugins] 追加: "nonebot-chat" = ["chat"]')

# 情形 B: 尚无该段 → 追加到文件末尾（不破坏已有 [tool.nonebot.*] 结构）
elif re.search(r'^\[tool\.nonebot\]\s*$', text, re.M):
    text = text.rstrip("\n") + '\n\n[tool.nonebot.plugins]\n"nonebot-chat" = ["chat"]\n'
    print('已追加 [tool.nonebot.plugins]: "nonebot-chat" = ["chat"]')

else:
    print("错误: pyproject.toml 缺少 [tool.nonebot]。", file=sys.stderr)
    sys.exit(1)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
PY
}

install_nbcli() {
    echo "正在注册到 $PYPROJECT_FILE ..."
    register_pyproject
    install_plugin_deps
}

# ------------------------------------------------------------------
# 3. 汇总
# ------------------------------------------------------------------
if [[ "$MODE" == "legacy" ]]; then
    install_legacy
else
    install_nbcli
fi

# ------------------------------------------------------------------
# 4. 配置模板放到项目根目录（与插件仓库解耦，pull 不会覆盖）
# ------------------------------------------------------------------
CONFIG_SRC="$PLUGIN_DIR/chat_config.yaml"
if [[ -f "$CONFIG_SRC" ]]; then
    if [[ -f "chat_config.yaml" ]]; then
        echo "提示: 项目根目录已有 chat_config.yaml，保留现有配置。"
    else
        cp "$CONFIG_SRC" "chat_config.yaml"
        echo "已复制配置模板到项目根目录: chat_config.yaml"
    fi
fi

echo ""
echo "=== 安装完成 ==="
echo "1. 插件源码已克隆到: $PLUGIN_DIR"
if [[ "$MODE" == "legacy" ]]; then
    echo "2. bot.py 已更新"
else
    echo "2. pyproject.toml 已注册 [tool.nonebot.plugins]"
    echo "3. 启动方式: nb run"
fi
echo ""
echo "=== 下一步：配置 ==="
echo "插件从项目根目录的 chat_config.yaml 读取配置（已与插件仓库解耦，git pull 不会覆盖）。"
echo "请在 .env（或 .env.prod）中添加："
echo "  CHAT_CONFIG_PATH=chat_config.yaml"
echo "然后编辑 chat_config.yaml 填入你的 LLM 配置（base_url / model / api_key）。"
echo "更新插件代码时直接 cd $PLUGIN_DIR && git pull 即可，不影响你的配置。"

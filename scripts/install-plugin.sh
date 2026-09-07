#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Xiaji-yu/nonebot_chat.git"
PLUGIN_DIR="plugins/nonebot_chat"
LOAD_LINE='nonebot.load_plugin("plugins.nonebot_chat.chat")'

# 确保在 bot.py 目录下执行
if [[ ! -f "bot.py" ]]; then
    echo "错误: 当前目录未找到 bot.py，请切换到 bot.py 所在目录后再运行此脚本。"
    exit 1
fi

# 克隆插件源码
if [[ -d "$PLUGIN_DIR" ]]; then
    echo "提示: $PLUGIN_DIR 已存在，跳过 git clone。"
else
    echo "正在克隆 nonebot_chat -> $PLUGIN_DIR ..."
    git clone "$REPO_URL" "$PLUGIN_DIR"
fi

# 修改 bot.py（如尚未加载）
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

echo ""
echo "=== 安装完成 ==="
echo "1. 插件源码已克隆到: $PLUGIN_DIR"
echo "2. bot.py 已更新"
echo "3. 请将 chat_config.yaml 放到 $PLUGIN_DIR/ 目录下（或设置 CHAT_CONFIG_PATH 环境变量）"
echo "4. 重启 bot 即可"

#!/usr/bin/env bash
# ============================================================
#  nonebot_chat 插件安装脚本（Bash 入口）
#  实际逻辑由 install.py 处理，此脚本仅作入口兼容。
# ============================================================
#  用法: bash install.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PY="${SCRIPT_DIR}/install.py"

# 检查 install.py 是否存在
if [ ! -f "$INSTALL_PY" ]; then
    echo "错误: 找不到 install.py (期望位置: ${INSTALL_PY})" >&2
    exit 1
fi

# 查找可用的 Python 解释器
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null || echo "0.0")
        major="${ver%%.*}"
        minor="${ver#*.}"
        if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "错误: 需要 Python >= 3.10，请先安装 Python" >&2
    exit 1
fi

# 委托给 install.py
exec "$PYTHON" "$INSTALL_PY" "$@"

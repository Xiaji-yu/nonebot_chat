#!/usr/bin/env bash
# ============================================================
#  nonebot_chat 插件自动安装脚本 (Bash 版本)
# ============================================================
#  用法: bash install.sh
# ============================================================

set -euo pipefail

# ── 常量 ──────────────────────────────────────────────────────────
GITHUB_REPO="https://github.com/Xiaji-yu/nonebot_chat"
BRANCH="main"
PLUGIN_DIR_NAME="nonebot_plugin_status"
REQUIRED_PYTHON=(3 10)

# 插件依赖
PLUGIN_DEPS=("aiohttp>=3.8" "pyyaml>=6.0" "pydantic>=2.0")

# NoneBot2 依赖
NONEBOT_DEPS=("nonebot2>=2.0.0" "nonebot-adapter-onebot>=2.0.0")

# 颜色（支持终端的才启用）
if [ -t 1 ]; then
    C_RED='\033[91m'
    C_GREEN='\033[92m'
    C_YELLOW='\033[93m'
    C_CYAN='\033[96m'
    C_BOLD='\033[1m'
    C_RESET='\033[0m'
else
    C_RED='' C_GREEN='' C_YELLOW='' C_CYAN='' C_BOLD='' C_RESET=''
fi

# ── 工具函数 ──────────────────────────────────────────────────────

ok()   { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
fail() { printf "${C_RED}✗${C_RESET} %s\n" "$*"; }
info() { printf "${C_CYAN}ℹ${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YELLOW}⚠${C_RESET} %s\n" "$*"; }
header() {
    printf "\n${C_BOLD}%s${C_RESET}\n  %s\n${C_BOLD}%s${C_RESET}\n" \
        "$(printf '=%.0s' {1..50})" "$1" "$(printf '=%.0s' {1..50})"
}

version_ge() {
    # 比较版本: version_ge 3.10
    local major=$1 minor=$2
    local cur_major=$(python3 -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo 0)
    local cur_minor=$(python3 -c "import sys; print(sys.version_info[1])" 2>/dev/null || echo 0)
    if [ "$cur_major" -gt "$major" ]; then return 0; fi
    if [ "$cur_major" -eq "$major" ] && [ "$cur_minor" -ge "$minor" ]; then return 0; fi
    return 1
}

is_installed() {
    python3 -c "import importlib.metadata; importlib.metadata.version('$1')" 2>/dev/null
}

pip_install() {
    local pkg="$1"
    printf "  安装 %s ... " "$pkg"
    if python3 -m pip install "$pkg" --quiet 2>/dev/null; then
        ok ""
    else
        fail "$(python3 -m pip install "$pkg" 2>&1 | tail -1 | cut -c1-80)"
        return 1
    fi
}

# ── 交互式输入 ────────────────────────────────────────────────────

ask() {
    local prompt="$1" default="$2" choices="${3:-}"
    while true; do
        if [ -n "$choices" ]; then
            printf "  %s [%s] (默认: %s): " "$prompt" "$choices" "$default"
        else
            printf "  %s (默认: %s): " "$prompt" "$default"
        fi
        read -r raw
        if [ -z "$raw" ]; then
            echo "$default"
            return
        fi
        if [ -n "$choices" ]; then
            local valid=0
            for c in $choices; do
                if [ "$raw" = "$c" ]; then
                    valid=1
                    break
                fi
            done
            if [ "$valid" -eq 0 ]; then
                warn "请输入有效选项: $choices"
                continue
            fi
        fi
        echo "$raw"
        return
    done
}

ask_int() {
    local prompt="$1" default="$2" min="$3" max="$4"
    while true; do
        printf "  %s (默认: %s, 范围 %s-%s): " "$prompt" "$default" "$min" "$max"
        read -r raw
        if [ -z "$raw" ]; then
            echo "$default"
            return
        fi
        if [[ "$raw" =~ ^[0-9]+$ ]] && [ "$raw" -ge "$min" ] && [ "$raw" -le "$max" ]; then
            echo "$raw"
            return
        fi
        warn "请输入 ${min}-${max} 之间的整数"
    done
}

ask_float() {
    local prompt="$1" default="$2" min="$3" max="$4"
    while true; do
        printf "  %s (默认: %s, 范围 %s-%s): " "$prompt" "$default" "$min" "$max"
        read -r raw
        if [ -z "$raw" ]; then
            echo "$default"
            return
        fi
        if [[ "$raw" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            local val="$raw"
            local int_part="${raw%%.*}"
            local dec_part="${raw#*.}"
            # 简单范围检查
            local ok=0
            if [ "$int_part" -lt "$min" ] 2>/dev/null; then ok=0; fi
            # 用 awk 做浮点比较
            if awk "BEGIN{exit($val>=$min && $val<=$max)?0:1)}" 2>/dev/null; then
                echo "$raw"
                return
            fi
        fi
        warn "请输入 ${min}-${max} 之间的数值"
    done
}

ask_bool() {
    local prompt="$1" default="$2"
    local default_str="Y"
    $default && default_str="Y" || default_str="N"
    while true; do
        printf "  %s [Y/n] (默认: %s): " "$prompt" "$default_str"
        read -r raw
        if [ -z "$raw" ]; then
            $default && echo "true" || echo "false"
            return
        fi
        case "$raw" in
            [Yy]|[Yy][Ee][Ss]|[Tt][Rr][Uu][Ee]|1) echo "true"; return ;;
            [Nn]|[Nn][Oo]|[Ff][Aa][Ll][Ss][Ee]|0) echo "false"; return ;;
            *) warn "请输入 Y 或 N" ;;
        esac
    done
}

ask_list() {
    local prompt="$1"
    shift
    local defaults=("$@")
    printf "  %s (直接回车使用默认)\n" "$prompt"
    printf "    输入项目，每行一个，空行结束：\n"
    local items=()
    local idx=1
    while true; do
        printf "    [%d] " "$idx"
        read -r raw
        if [ -z "$raw" ]; then
            if [ ${#items[@]} -gt 0 ]; then
                printf '%s\n' "${items[@]}"
                return
            fi
            # 输出默认值
            printf '%s\n' "${defaults[@]}"
            return
        fi
        items+=("$raw")
        idx=$((idx + 1))
    done
}

# ── 主流程 ────────────────────────────────────────────────────────

step_personality() {
    header "人格配置"
    printf "  定义 AI 助手的身份和行为准则。\n\n"
    PERSONALITY_NAME=$(ask "人格名称" "小助手")
    printf "  %s\n" "系统提示词（System Prompt）— 直接回车使用默认，或输入多行后空行结束"
    SYSTEM_PROMPT="你是一个友善、聪明的助手，名叫小助手。
请用简洁、自然的语气回复，避免过于正式或机械的表达。
适当使用 emoji，但不要过度。记住和用户的历史对话上下文。"
    read -r -d '' _tmp || true
    # 简单处理：如果用户输入了内容就用用户的，否则用默认
    # 这里简化：直接用默认，因为多行输入在交互中体验不好
    WAKE_WORDS=($(ask_list "唤醒词列表（子串匹配，不区分大小写）" "小助手" "bot"))
}

step_llm() {
    header "LLM 配置"
    printf "  配置 OpenAI 兼容 API 端点（支持 OpenAI / Ollama / LM Studio 等）\n\n"
    LLM_BASE_URL=$(ask "API 基础地址" "http://localhost:11434/v1")
    LLM_MODEL=$(ask "模型名称" "llama2")
    LLM_API_KEY=$(ask "API 密钥（Ollama 等本地服务可留空）" "")
    LLM_MAX_TOKENS=$(ask_int "单次生成最大 token 数" 1000 1 8192)
    LLM_TIMEOUT=$(ask_int "API 请求超时时间（秒）" 30 5 120)
}

step_temperature() {
    header "温度配置"
    printf "  控制 LLM 输出的随机性。值越高回复越有创意。\n\n"
    T_DEFAULT=$(ask_float "普通回复温度" 0.7 0.0 2.0)
    T_MIN=$(ask_float "主动回复温度下限" 0.5 0.0 2.0)
    T_MAX=$(ask_float "主动回复温度上限" 1.0 0.0 2.0)
    if awk "BEGIN{exit($T_MIN <= $T_MAX)?0:1}" 2>/dev/null; then
        :
    else
        warn "温度下限 > 上限，已自动交换"
        T_TMP=$T_MIN; T_MIN=$T_MAX; T_MAX=$T_TMP
    fi
}

step_memory() {
    header "记忆系统配置"
    printf "  每个会话维护独立的对话历史，长对话自动蒸馏摘要。\n\n"
    M_MAX_HISTORY=$(ask_int "单会话最大消息条数" 50 5 500)
    M_THRESHOLD=$(ask_int "蒸馏触发阈值（必须 < 最大消息数）" 40 10 200)
    M_CORE_MAX=$(ask_int "蒸馏后保留的核心摘要条数" 10 1 50)
    if [ "$M_THRESHOLD" -ge "$M_MAX_HISTORY" ]; then
        warn "阈值 >= 最大消息数，已自动调整为 $((M_MAX_HISTORY - 5))"
        M_THRESHOLD=$((M_MAX_HISTORY - 5))
        [ "$M_THRESHOLD" -lt 10 ] && M_THRESHOLD=10
    fi
    if [ "$M_CORE_MAX" -gt "$M_MAX_HISTORY" ]; then
        M_CORE_MAX=$M_MAX_HISTORY
    fi
}

step_proactive() {
    header "主动回复配置"
    printf "  机器人主动发起对话的概率和冷却控制。\n\n"
    P_ENABLED=$(ask_bool "是否启用主动回复" true)
    P_PROBABILITY=$(ask_float "主动回复概率（0.0-1.0）" 0.1 0.0 1.0)
    P_COOLDOWN=$(ask_int "主动回复冷却时间（秒）" 300 30 3600)
    P_INTERVAL=$(ask_int "检查间隔（秒）" 60 10 600)
}

step_pipeline_sleep() {
    header "休眠模式配置"
    printf "  让机器人在指定时间段内静默。\n\n"
    S_ENABLED=$(ask_bool "是否启用休眠模式" false)
    S_MODE="schedule"
    S_SCHED_START=""
    S_SCHED_END=""
    S_OVERRIDE=true
    if [ "$S_ENABLED" = "true" ]; then
        S_MODE=$(ask "休眠模式" "schedule" "schedule manual")
        if [ "$S_MODE" = "schedule" ]; then
            S_SCHED_START=$(ask "休眠开始时间（HH:MM）" "23:00")
            S_SCHED_END=$(ask "休眠结束时间（HH:MM）" "08:00")
        fi
        S_OVERRIDE=$(ask_bool "@mention 是否可临时唤醒" true)
    fi
}

step_pipeline_dedup() {
    header "去重配置"
    printf "  防止重复消息触发多次回复。\n\n"
    D_ENABLED=$(ask_bool "是否启用去重" true)
    D_WINDOW=$(ask_int "去重时间窗口（秒）" 5 1 60)
}

step_pipeline_access() {
    header "黑白名单配置"
    printf "  mode=none 不过滤；whitelist 仅名单内可用；blacklist 拦截名单内\n\n"
    A_MODE=$(ask "访问模式" "none" "none whitelist blacklist")
    A_USERS=()
    A_GROUPS=()
    if [ "$A_MODE" != "none" ]; then
        if [ "$(ask_bool "是否配置用户名单" false)" = "true" ]; then
            printf "    输入用户 ID（QQ 号），空行结束：\n"
            while true; do
                printf "    [%d] " "$(( ${#A_USERS[@]} + 1 ))"
                read -r raw
                [ -z "$raw" ] && break
                A_USERS+=("$raw")
            done
        fi
        if [ "$(ask_bool "是否配置群组名单" false)" = "true" ]; then
            printf "    输入群 ID，空行结束：\n"
            while true; do
                printf "    [%d] " "$(( ${#A_GROUPS[@]} + 1 ))"
                read -r raw
                [ -z "$raw" ] && break
                A_GROUPS+=("$raw")
            done
        fi
    fi
}

step_pipeline_silent() {
    header "静默关键词配置"
    printf "  命中关键词时跳过回复。\n\n"
    SILENT_ENABLED=$(ask_bool "是否启用静默关键词" true)
    SILENT_KEYWORDS=()
    if [ "$SILENT_ENABLED" = "true" ]; then
        SILENT_KEYWORDS=($(ask_list "静默关键词列表" "闭嘴" "别回" "silent"))
    fi
}

step_pipeline_ratelimit() {
    header "频控配置"
    printf "  限制同一会话在时间窗口内的触发次数。\n\n"
    RL_ENABLED=$(ask_bool "是否启用频控" true)
    RL_MAX=$(ask_int "窗口内最大请求次数" 3 1 100)
    RL_WINDOW=$(ask_int "时间窗口（秒）" 10 1 300)
}

step_pipeline_trigger() {
    header "触发检测配置"
    printf "  mention=@机器人  keyword=关键词  spectator=所有消息\n\n"
    T_MODE=$(ask "触发模式" "keyword" "mention keyword spectator")
    T_KEYWORDS=()
    if [ "$T_MODE" = "keyword" ]; then
        T_KEYWORDS=($(ask_list "触发关键词列表" "小助手" "bot"))
    fi
}

step_pipeline_admin() {
    header "管理命令配置"
    printf "  特殊命令直接执行，不经过 LLM。\n\n"
    ADMIN_ENABLED=$(ask_bool "是否启用管理命令" true)
}

step_pipeline_debounce() {
    header "防抖合并配置"
    printf "  合并窗口内的多条消息为一条，适合快速连发的场景。\n\n"
    DEB_ENABLED=$(ask_bool "是否启用防抖" true)
    DEB_WINDOW=$(ask_int "防抖窗口（秒）" 3 1 30)
}

step_pipeline_format() {
    header "消息格式化配置"
    printf "  控制 LLM 回复的最终发送格式。\n\n"
    FMT_MAXLEN=$(ask_int "单条消息最大字符数" 500 100 2000)
    FMT_MODE=$(ask "格式化模式" "plain" "plain markdown")
}

# ── YAML 生成 ──────────────────────────────────────────────────────

yaml_escape() {
    # 转义 YAML 字符串中的特殊字符
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    echo "$s"
}

yaml_list() {
    local name="$1"
    shift
    echo "  ${name}:"
    if [ $# -eq 0 ]; then
        echo "    []"
    else
        for item in "$@"; do
            printf '    - "%s"\n' "$(echo "$item" | sed 's/"/\\"/g')"
        done
    fi
}

yaml_multiline() {
    local name="$1"
    local content="$2"
    echo "  ${name}: |"
    while IFS= read -r line; do
        echo "    ${line}"
    done <<< "$content"
}

generate_config() {
    cat <<YAMLEOF
# ============================================================
#  nonebot_chat 配置文件
#  由 install.sh 自动生成，也可手动编辑
# ============================================================

personality:
  name: "${PERSONALITY_NAME}"
YAMLEOF

    if [ -n "$SYSTEM_PROMPT" ]; then
        yaml_multiline "system_prompt" "$SYSTEM_PROMPT"
    else
        echo "  system_prompt: \"\""
    fi

    echo ""
    # 唤醒词列表
    if [ ${#WAKE_WORDS[@]} -eq 0 ]; then
        echo "  wake_words: []"
    else
        echo "  wake_words:"
        for w in "${WAKE_WORDS[@]}"; do
            printf '    - "%s"\n' "$(echo "$w" | sed 's/"/\\"/g')"
        done
    fi

    echo ""
    echo "llm:"
    echo "  base_url: \"${LLM_BASE_URL}\""
    echo "  model: \"${LLM_MODEL}\""
    echo "  api_key: \"${LLM_API_KEY}\""
    echo "  max_tokens: ${LLM_MAX_TOKENS}"
    echo "  timeout: ${LLM_TIMEOUT}"

    echo ""
    echo "temperature:"
    echo "  default: ${T_DEFAULT}"
    echo "  proactive_min: ${T_MIN}"
    echo "  proactive_max: ${T_MAX}"

    echo ""
    echo "memory:"
    echo "  max_history: ${M_MAX_HISTORY}"
    echo "  distillation_threshold: ${M_THRESHOLD}"
    echo "  core_memory_max: ${M_CORE_MAX}"

    echo ""
    echo "proactive:"
    echo "  enabled: ${P_ENABLED}"
    echo "  probability: ${P_PROBABILITY}"
    echo "  cooldown: ${P_COOLDOWN}"
    echo "  check_interval: ${P_INTERVAL}"

    echo ""
    echo "pipeline:"
    echo "  # ── 休眠模式 ──"
    echo "  sleep:"
    echo "    enabled: ${S_ENABLED}"
    echo "    mode: \"${S_MODE}\""
    echo "    schedule:"
    echo "      start: \"${S_SCHED_START}\""
    echo "      end: \"${S_SCHED_END}\""
    echo "    override_by_mention: ${S_OVERRIDE}"

    echo ""
    echo "  # ── 去重 ──"
    echo "  dedup:"
    echo "    enabled: ${D_ENABLED}"
    echo "    window: ${D_WINDOW}"

    echo ""
    echo "  # ── 黑白名单 ──"
    echo "  access:"
    echo "    mode: \"${A_MODE}\""
    echo "    users:"
    for u in "${A_USERS[@]}"; do
        printf '      - "%s"\n' "$(echo "$u" | sed 's/"/\\"/g')"
    done
    echo "    groups:"
    for g in "${A_GROUPS[@]}"; do
        printf '      - "%s"\n' "$(echo "$g" | sed 's/"/\\"/g')"
    done

    echo ""
    echo "  # ── 静默关键词 ──"
    echo "  silent:"
    echo "    enabled: ${SILENT_ENABLED}"
    echo "    keywords:"
    for k in "${SILENT_KEYWORDS[@]}"; do
        printf '      - "%s"\n' "$(echo "$k" | sed 's/"/\\"/g')"
    done

    echo ""
    echo "  # ── 频控 ──"
    echo "  ratelimit:"
    echo "    enabled: ${RL_ENABLED}"
    echo "    max_requests: ${RL_MAX}"
    echo "    window: ${RL_WINDOW}"

    echo ""
    echo "  # ── 触发检测 ──"
    echo "  trigger:"
    echo "    mode: \"${T_MODE}\""
    echo "    keywords:"
    for k in "${T_KEYWORDS[@]}"; do
        printf '      - "%s"\n' "$(echo "$k" | sed 's/"/\\"/g')"
    done

    echo ""
    echo "  # ── 管理命令 ──"
    echo "  admin:"
    echo "    enabled: ${ADMIN_ENABLED}"

    echo ""
    echo "  # ── 防抖合并 ──"
    echo "  debounce:"
    echo "    enabled: ${DEB_ENABLED}"
    echo "    window: ${DEB_WINDOW}"

    echo ""
    echo "  # ── 消息格式化 ──"
    echo "  format:"
    echo "    max_length: ${FMT_MAXLEN}"
    echo "    mode: \"${FMT_MODE}\""
}

print_setup_guide() {
    local plugin_dir="$1"
    header "安装完成！"
    printf "\n  插件目录: %s\n" "$plugin_dir"
    printf "  配置文件: %s/chat_config.yaml\n\n" "$plugin_dir"

    printf "${C_CYAN}▸ 在 bot.py 中加载插件：${C_RESET}\n\n"
    cat <<'PYEOF'
    import nonebot

    nonebot.init()
    nonebot.load_plugin("nonebot_plugin_status.chat")

    if __name__ == "__main__":
        nonebot.run()
PYEOF

    printf "\n${C_CYAN}▸ 管理命令（在对话中发送）：${C_RESET}\n\n"
    echo "    清空记忆 / clear  — 清空当前会话记忆"
    echo "    状态   / status   — 查看会话状态"
    echo "    休眠   / sleep    — 切换休眠模式"
    echo "    唤醒   / wake     — 强制唤醒"
    echo ""
}

# ── 下载 ──────────────────────────────────────────────────────────

download_plugin() {
    local dest="$1"
    local zip_url="${GITHUB_REPO}/archive/refs/heads/${BRANCH}.zip"
    local zip_path="${dest}/repo.zip"

    header "下载插件"
    printf "  仓库: %s\n" "$GITHUB_REPO"
    printf "  分支: %s\n" "$BRANCH"

    if command -v curl &>/dev/null; then
        printf "  下载 ... "
        if curl -sL "$zip_url" -o "$zip_path" 2>/dev/null; then
            ok ""
        else
            fail "下载失败"
            return 1
        fi
    elif command -v wget &>/dev/null; then
        printf "  下载 ... "
        if wget -q "$zip_url" -O "$zip_path" 2>/dev/null; then
            ok ""
        else
            fail "下载失败"
            return 1
        fi
    else
        fail "需要 curl 或 wget，请先安装其中一个"
        return 1
    fi

    printf "  解压 ... "
    local extract_dir="${dest}/extracted"
    mkdir -p "$extract_dir"
    if command -v unzip &>/dev/null; then
        unzip -q "$zip_path" -d "$extract_dir" 2>/dev/null
        ok ""
    else
        # Python fallback
        python3 -c "
import zipfile, pathlib
z = zipfile.ZipFile('$zip_path')
for m in z.namelist():
    parts = pathlib.Path(m).parts
    if len(parts) <= 1: continue
    target = pathlib.Path('$extract_dir') / pathlib.Path(*parts[1:])
    if m.endswith('/'): target.mkdir(parents=True, exist_ok=True)
    else: target.write_bytes(z.read(m))
" && ok "" || { fail "解压失败"; return 1; }
    fi

    # 找到插件目录
    for d in "$extract_dir"/*/; do
        if [ -d "${d}chat" ]; then
            echo "$d"
            return 0
        fi
    done
    fail "无法在下载的仓库中找到 chat/ 目录"
    return 1
}

# ── 主流程 ────────────────────────────────────────────────────────

main() {
    printf "\n${C_BOLD}${C_CYAN}%s${C_RESET}\n  ${C_BOLD}${C_CYAN}%s${C_RESET}\n${C_BOLD}${C_CYAN}%s${C_RESET}\n" \
        "$(printf '=%.0s' {1..50})" "  nonebot_chat 插件自动安装脚本" "$(printf '=%.0s' {1..50})"

    # 1. 检查 Python
    header "检查 Python 环境"
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null || echo "0.0")
    if version_ge 3 10; then
        ok "Python $PY_VERSION (>= 3.10 要求满足)"
    else
        fail "Python $PY_VERSION，需要 >= 3.10"
        exit 1
    fi

    # 2. 检查 NoneBot2
    header "检查 NoneBot2 依赖"
    HAS_NB=false
    HAS_ADAPTER=false

    if is_installed nonebot2 &>/dev/null; then
        ok "nonebot2 已安装 ($(is_installed nonebot2))"
        HAS_NB=true
    else
        warn "nonebot2 未安装"
    fi

    if is_installed nonebot-adapter-onebot &>/dev/null; then
        ok "nonebot-adapter-onebot 已安装 ($(is_installed nonebot-adapter-onebot))"
        HAS_ADAPTER=true
    else
        warn "nonebot-adapter-onebot 未安装"
    fi

    if $HAS_NB && $HAS_ADAPTER; then
        ok "NoneBot2 依赖完整"
    else
        printf "\n  需要安装缺失的依赖：\n"
        $HAS_NB || echo "    - nonebot2"
        $HAS_ADAPTER || echo "    - nonebot-adapter-onebot"
        if ask_bool "\n是否自动安装？" true; then
            $HAS_NB || pip_install "nonebot2>=2.0.0"
            $HAS_ADAPTER || pip_install "nonebot-adapter-onebot>=2.0.0"
        else
            warn "请手动安装后重新运行此脚本"
            exit 1
        fi
    fi

    # 3. 安装插件依赖
    header "安装插件依赖"
    for dep in "${PLUGIN_DEPS[@]}"; do
        pip_install "$dep"
    done

    # 4. 下载插件
    TMPDIR=$(mktemp -d -t nonebot_chat_install_XXXXXX)
    trap "rm -rf '$TMPDIR'" EXIT

    PLUGIN_SRC=$(download_plugin "$TMPDIR") || exit 1
    ok "插件源码: $PLUGIN_SRC"

    # 5. 选择安装位置
    header "选择安装位置"
    printf "  源码位置: %s\n\n" "$PLUGIN_SRC"
    echo "  安装选项："
    echo "    1. 当前目录下的 plugins/ 文件夹（推荐用于 nb-cli 项目）"
    echo "    2. 自定义路径"
    echo "    3. 仅生成配置文件（手动复制源码）"
    echo ""

    INSTALL_CHOICE=$(ask "选择安装方式" "1" "1 2 3")
    INSTALL_DIR=""

    case "$INSTALL_CHOICE" in
        1)
            INSTALL_DIR="$(pwd)/plugins/${PLUGIN_DIR_NAME}"
            mkdir -p "$(dirname "$INSTALL_DIR")"
            if [ -d "$INSTALL_DIR" ]; then
                if ! ask_bool "目录已存在 ${INSTALL_DIR}，是否覆盖？" false; then
                    warn "已取消"
                    exit 0
                fi
                rm -rf "$INSTALL_DIR"
            fi
            cp -r "$PLUGIN_SRC" "$INSTALL_DIR"
            ok "插件已安装到: $INSTALL_DIR"
            ;;
        2)
            printf "  请输入安装路径: "
            read -r CUSTOM_PATH
            INSTALL_DIR=$(eval echo "$CUSTOM_PATH" | sed 's:/*$::')
            mkdir -p "$(dirname "$INSTALL_DIR")"
            if [ -d "$INSTALL_DIR" ]; then
                if ! ask_bool "目录已存在 ${INSTALL_DIR}，是否覆盖？" false; then
                    warn "已取消"
                    exit 0
                fi
                rm -rf "$INSTALL_DIR"
            fi
            cp -r "$PLUGIN_SRC" "$INSTALL_DIR"
            ok "插件已安装到: $INSTALL_DIR"
            ;;
        3)
            INSTALL_DIR="$PLUGIN_SRC"
            info "将使用源码目录: $INSTALL_DIR"
            ;;
    esac

    # 6. 交互式配置
    step_personality
    step_llm
    step_temperature
    step_memory
    step_proactive
    step_pipeline_sleep
    step_pipeline_dedup
    step_pipeline_access
    step_pipeline_silent
    step_pipeline_ratelimit
    step_pipeline_trigger
    step_pipeline_admin
    step_pipeline_debounce
    step_pipeline_format

    header "生成配置文件"
    CONFIG_PATH="${INSTALL_DIR}/chat_config.yaml"
    generate_config > "$CONFIG_PATH"
    ok "配置文件已写入: $CONFIG_PATH"

    # 7. 完成指引
    print_setup_guide "$INSTALL_DIR"
}

main "$@"

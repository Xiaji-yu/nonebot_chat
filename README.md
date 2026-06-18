# nonebot_chat

NoneBot2 智能聊天插件 — 人格驱动对话、记忆系统、主动回复。

## 功能

- **人格系统**：通过 `chat_config.yaml` 配置 AI 人格名称、系统提示词、唤醒词
- **记忆系统**：会话级对话历史管理，支持长对话自动蒸馏摘要
- **主动回复**：概率触发的 spontaneous 回复，带冷却时间
- **Pipeline 架构**：可配置的消息处理流水线
  - 去重、黑白名单、静默关键词、频控
  - 休眠模式（定时/手动，@mention 可唤醒）
  - 触发检测（@提及/关键词/旁观模式）
  - 管理命令（清空记忆、状态查询、休眠/唤醒）
  - 回复防抖合并、消息分片、Markdown 处理
- **OpenAI 兼容 API**：通过 `aiohttp` 直连，支持 OpenAI / Ollama / 任何兼容端点

## Pipeline 流程

```
入站消息 → 休眠检测 → 去重 → 黑白名单 → 静默关键词 → 频控
         → 管理命令 → 防抖合并 → 触发检测 → AI 派发
         → 消息格式化 → 发送
```

## 安装

```bash
pip install nonebot-chat
```

或在 `bot.py` 中直接加载本地插件：

```python
nonebot.load_plugin("nonebot_plugin_status.chat")
```

## 配置

编辑项目目录下的 `chat_config.yaml`。完整配置见下方「配置详解」章节。

## 管理命令

| 命令 | 效果 |
|---|---|
| `/chat` / `聊天` | 开始对话 |
| `清空记忆` / `clear` | 清空当前会话记忆 |
| `状态` / `status` | 查看会话状态（消息数、休眠状态、触发模式） |
| `休眠` / `sleep` | 切换休眠模式（仅 manual 模式有效） |
| `唤醒` / `wake` | 强制唤醒（仅 manual 模式有效） |

## 依赖

- Python >= 3.10
- nonebot2 >= 2.0.0
- nonebot-adapter-onebot >= 2.0.0
- aiohttp >= 3.8
- pydantic >= 2.0
- pyyaml >= 6.0

## License

MIT

---

## 配置详解

### personality — 人格

```yaml
personality:
  name: "小助手"               # 人格名称
  system_prompt: |             # 系统提示词（多行）
    你是一个友善的助手...
  wake_words: ["小助手", "bot"] # 唤醒词（子串匹配，不区分大小写）
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `name` | string | `"小助手"` | 人格名称，出现在主动回复和系统提示中 |
| `system_prompt` | string | 见上方 | 系统提示词，定义 AI 的行为准则、语气、风格。支持多行 |
| `wake_words` | list[string] | `["小助手", "bot"]` | 唤醒词列表。用户消息命中任意词才触发回复（主动回复除外）。子串匹配，注意避免短词误匹配 |

### llm — 大语言模型

```yaml
llm:
  base_url: "http://localhost:11434/v1"  # API 端点（不含 /chat/completions）
  model: "llama2"                         # 模型名称
  api_key: ""                             # API 密钥，Ollama 可留空
  max_tokens: 1000                        # 单次生成最大 token 数
  timeout: 30                             # 请求超时（秒）
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `base_url` | string | `"http://localhost:11434/v1"` | OpenAI 兼容 API 基础 URL。Ollama 本地用 `http://localhost:11434/v1`，OpenAI 用 `https://api.openai.com/v1` |
| `model` | string | `"llama2"` | 模型名称，需与服务端实际加载的模型一致 |
| `api_key` | string | `""` | API 密钥。不需要认证的服务（如本地 Ollama）留空即可 |
| `max_tokens` | int | `1000` | 单次生成最大 token 数。中文约 1.5-2 字符/token |
| `timeout` | int | `30` | 单次 API 请求超时时间（秒），范围 5-120 |

### temperature — 温度

```yaml
temperature:
  default: 0.7        # 普通回复温度
  proactive_min: 0.5  # 主动回复温度下限
  proactive_max: 1.0  # 主动回复温度上限
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `default` | float | `0.7` | 普通回复温度。0.0=确定性，2.0=随机。0.7 是平衡创意和一致性的常用值 |
| `proactive_min` | float | `0.5` | 主动回复温度下限。主动回复通常更短更随意，建议低于 default |
| `proactive_max` | float | `1.0` | 主动回复温度上限。必须 `>= proactive_min`，否则启动报错 |

**温度参考：**
- `0.0 - 0.3`：高度确定，适合 factual 回复
- `0.4 - 0.7`：平衡创意和一致性（推荐日常使用）
- `0.8 - 1.2`：更有创意，适合闲聊
- `1.3 - 2.0`：高度随机，可能产生意外输出

### memory — 记忆系统

```yaml
memory:
  max_history: 50              # 单会话最大消息数
  distillation_threshold: 40   # 触发蒸馏的消息数阈值
  core_memory_max: 10          # 蒸馏后保留的核心摘要条数
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `max_history` | int | `50` | 单会话最多保留的消息条数（含核心记忆）。范围 5-500 |
| `distillation_threshold` | int | `40` | 消息数达到此值时触发蒸馏。必须 `< max_history`，否则启动报错。推荐设为 `max_history` 的 75%-80% |
| `core_memory_max` | int | `10` | 蒸馏后保留的核心摘要条数。这些摘要以 system 角色注入，帮助 AI 记住重要信息（偏好、决定、待办等） |

**蒸馏机制：** 当消息数达到 `distillation_threshold` 时，调用 LLM 将旧对话浓缩为若干条核心要点，替换为 system 角色消息，释放上下文窗口。当前用户消息不受影响。

**会话标识：** 群聊用 `groupId_userId`，私聊用 `userId`，不同会话独立记忆。

### proactive — 主动回复

```yaml
proactive:
  enabled: true          # 是否启用
  probability: 0.1       # 触发概率（10%）
  cooldown: 300          # 冷却时间 5 分钟
  check_interval: 60     # 检查间隔（秒）
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用主动回复 |
| `probability` | float | `0.1` | 每条消息的主动回复概率。0.1 = 约 10% 的消息会触发 |
| `cooldown` | int | `300` | 同一会话内两次主动回复的最小间隔（秒）。防止刷屏 |
| `check_interval` | int | `60` | 主动回复检查间隔（秒），当前为配置保留接口 |

**注意：** 主动回复同样经过休眠检测、黑白名单、频控等 Pipeline 检查。

### pipeline — 消息处理流水线

```
入站消息 → 休眠检测 → 去重 → 黑白名单 → 静默关键词 → 频控
         → 管理命令 → 防抖合并 → 触发检测 → AI 派发
         → 消息格式化 → 发送
```

任一阶段决定 drop 消息，后续阶段不再执行。

#### pipeline.sleep — 休眠模式

```yaml
pipeline:
  sleep:
    enabled: false
    mode: "schedule"         # "schedule" | "manual"
    schedule:
      start: "23:00"         # 休眠开始（HH:MM）
      end: "08:00"           # 休眠结束（HH:MM）
    override_by_mention: true # @mention 可唤醒
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `false` | 是否启用休眠模式 |
| `mode` | string | `"schedule"` | `"schedule"` = 按时间段休眠；`"manual"` = 通过 `/sleep`/`/wake` 手动控制 |
| `schedule.start` | string | `"23:00"` | 休眠开始时间（HH:MM，24小时制） |
| `schedule.end` | string | `"08:00"` | 休眠结束时间（HH:MM） |
| `override_by_mention` | bool | `true` | 休眠期间 @mention 是否允许临时唤醒 |

**休眠期间规则：**
- `@mention` → 正常响应（`override_by_mention: true` 时）
- 其他触发方式 → 全部静默（drop）

**跨天设置：** `start: "23:00", end: "08:00"` 表示从 23:00 到次日 08:00。

#### pipeline.dedup — 去重

```yaml
  dedup:
    enabled: true
    window: 5
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用去重 |
| `window` | int | `5` | 时间窗口（秒），相同内容在此窗口内只处理一次 |

基于内容 MD5 哈希 + 时间窗口实现。适合防止误触发的重复消息。

#### pipeline.access — 黑白名单

```yaml
  access:
    mode: "none"        # "none" | "whitelist" | "blacklist"
    users: []           # 用户 ID 列表
    groups: []          # 群 ID 列表
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `mode` | string | `"none"` | `"none"` = 不过滤；`"whitelist"` = 仅名单内可用；`"blacklist"` = 名单内拦截 |
| `users` | list[string] | `[]` | 用户 ID 列表（QQ 号等） |
| `groups` | list[string] | `[]` | 群 ID 列表 |

**安全设计：** 非法 mode 值会触发启动报错（fail-closed），不会静默放行。

#### pipeline.silent — 静默关键词

```yaml
  silent:
    enabled: true
    keywords: ["闭嘴", "别回", "silent"]
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用静默关键词 |
| `keywords` | list[string] | `["闭嘴", "别回", "silent"]` | 静默关键词列表，子串匹配（不区分大小写）。命中则跳过回复 |

#### pipeline.ratelimit — 频控

```yaml
  ratelimit:
    enabled: true
    max_requests: 3      # 窗口内最大请求次数
    window: 10           # 时间窗口（秒）
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用频控 |
| `max_requests` | int | `3` | 时间窗口内最大允许触发次数 |
| `window` | int | `10` | 滑动窗口长度（秒） |

**示例：** `max_requests: 3, window: 10` 表示 10 秒内最多触发 3 次，第 4 次被拦截并等待窗口重置。

#### pipeline.trigger — 触发检测

```yaml
  trigger:
    mode: "keyword"      # "mention" | "keyword" | "spectator"
    keywords: ["小助手", "bot"]
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `mode` | string | `"keyword"` | `"mention"` = 必须 @；`"keyword"` = 命中关键词；`"spectator"` = 所有消息 |
| `keywords` | list[string] | `["小助手", "bot"]` | 触发关键词（keyword 模式下生效）。子串匹配 |

**注意：** keyword 模式下 keywords 不能为空，否则启动报错。

#### pipeline.admin — 管理命令

```yaml
  admin:
    enabled: true
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用管理命令 |

**内置命令（不经过 LLM，直接执行）：**

| 命令 | 别名 | 效果 |
|---|---|---|
| `清空记忆` | `clear` | 清空当前会话的对话历史和核心记忆 |
| `状态` | `status` | 查看当前会话状态（消息数、核心记忆数、休眠状态、触发模式） |
| `休眠` | `sleep` | 切换休眠模式（manual 模式下生效） |
| `唤醒` | `wake` | 强制唤醒（manual 模式下生效） |

#### pipeline.debounce — 防抖合并

```yaml
  debounce:
    enabled: true
    window: 3            # 防抖窗口（秒）
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 是否启用防抖合并 |
| `window` | int | `3` | 防抖窗口（秒）。用户停止输入后等待这么久再统一发送合并后的内容给 LLM |

适合用户快速连发的场景（如复制粘贴多条消息），合并后上下文更连贯。

#### pipeline.format — 消息格式化

```yaml
  format:
    max_length: 500      # 单条消息最大字符数
    mode: "plain"        # "plain" | "markdown"
```

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `max_length` | int | `500` | 单条消息最大字符数。超过时自动分片发送。建议 `<= llm.max_tokens * 1.5` |
| `mode` | string | `"plain"` | `"plain"` = 纯文本；`"markdown"` = 基础 Markdown 转 OneBot CQ 码 |

**Markdown 支持：** `**粗体**`、`*斜体*`、`` `行内代码` ``、`` ```代码块``` `` → 自动转为 CQ 码。

## 使用方式

### 群聊

发送 `小助手 今天天气怎么样` — 唤醒词 + 消息内容

### 私聊

直接发送消息（私聊无唤醒词要求）

### 命令

在任意对话中发送 `/chat` 开始对话，`状态` 查看会话信息

## 常见问题

**Q: 机器人没有回复？**
- 检查是否命中唤醒词（keyword 模式）或 @了机器人（mention 模式）
- 检查是否在黑名单中
- 检查频控是否被限制
- 查看启动日志确认 LLM 连通性

**Q: 如何限制只有特定用户可用？**
- 设置 `pipeline.access.mode: "whitelist"` 并填写 `users` 列表

**Q: 如何让机器人在指定时间段静默？**
- 设置 `pipeline.sleep.enabled: true`，配置 `schedule.start` 和 `schedule.end`

**Q: 记忆会占用多少内存？**
- 默认最多 50 条消息/会话，每条约 100-500 字节。50 个活跃会话约占用 1-2 MB。

## 开发

```bash
# 安装依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check chat/
```

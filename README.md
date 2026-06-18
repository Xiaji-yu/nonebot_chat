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

编辑项目目录下的 `chat_config.yaml`：

```yaml
personality:
  name: "小助手"
  system_prompt: |
    你是一个友善的助手...
  wake_words: ["小助手", "bot"]

llm:
  base_url: "http://localhost:11434/v1"
  model: "llama2"
  api_key: ""
  max_tokens: 1000
  timeout: 30

temperature:
  default: 0.7
  proactive_min: 0.5
  proactive_max: 1.0

memory:
  max_history: 50
  distillation_threshold: 40
  core_memory_max: 10

proactive:
  enabled: true
  probability: 0.1
  cooldown: 300

pipeline:
  sleep:
    enabled: false
    mode: "schedule"
    schedule:
      start: "23:00"
      end: "08:00"
    override_by_mention: true

  dedup:
    enabled: true
    window: 5

  access:
    mode: "none"
    users: []
    groups: []

  silent:
    enabled: true
    keywords: ["闭嘴", "别回", "silent"]

  ratelimit:
    enabled: true
    per_session: 3
    window: 10

  trigger:
    mode: "keyword"
    keywords: ["小助手", "bot"]

  admin:
    enabled: true

  debounce:
    enabled: true
    window: 3

  format:
    max_length: 500
    mode: "plain"
```

## 管理命令

| 命令 | 效果 |
|---|---|
| `/chat` / `聊天` | 开始对话 |
| `清空记忆` / `clear` | 清空当前会话记忆 |
| `状态` / `status` | 查看会话状态 |
| `休眠` / `sleep` | 切换休眠模式 |
| `唤醒` / `wake` | 强制唤醒 |

## 依赖

- Python >= 3.10
- nonebot2 >= 2.0.0
- nonebot-adapter-onebot >= 2.0.0
- aiohttp >= 3.8
- pydantic >= 2.0
- pyyaml >= 6.0

## License

MIT

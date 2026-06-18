# nonebat-chat

NoneBot2 智能聊天插件 — 人格驱动对话、记忆系统、主动回复。

## 功能

- **人格系统**：通过 `chat_config.yaml` 配置 AI 人格名称、系统提示词、唤醒词
- **记忆系统**：会话级对话历史管理，支持长对话自动蒸馏摘要
- **主动回复**：概率触发的 spontaneous 回复，带冷却时间
- **温度控制**：普通回复和主动回复独立温度配置
- **OpenAI 兼容 API**：通过 `aiohttp` 直连，支持 OpenAI / Ollama / 任何兼容端点

## 安装

```bash
pip install nonebat-chat
```

或在 `bot.py` 中直接加载本地插件：

```python
nonebot.load_plugin("nonebot_plugin_status.chat")
```

## 配置

编辑项目目录下的 `chat_config.yaml`：

```yaml
# 人格
personality:
  name: "小助手"
  system_prompt: |
    你是一个友善的助手...
  wake_words: ["小助手", "bot"]

# LLM（OpenAI 兼容）
llm:
  base_url: "http://localhost:11434/v1"
  model: "llama2"
  api_key: ""
  max_tokens: 1000
  timeout: 30

# 温度
temperature:
  default: 0.7
  proactive_min: 0.5
  proactive_max: 1.0

# 记忆
memory:
  max_history: 50
  distillation_threshold: 40
  core_memory_max: 10

# 主动回复
proactive:
  enabled: true
  probability: 0.1
  cooldown: 300
  check_interval: 60
```

## 使用

- 发送 `小助手 你好` 触发对话（唤醒词 + 消息）
- 或发送 `/chat 你好` 直接开始对话

## 依赖

- Python >= 3.10
- nonebot2 >= 2.0.0
- nonebot-adapter-onebot >= 2.0.0
- aiohttp >= 3.8
- pydantic >= 2.0
- pyyaml >= 6.0

## License

MIT

# CONTRIBUTING.md

> 最后更新：2026-06-19

感谢你愿意为 nonebot_chat 贡献代码。请先花 2 分钟阅读本文件，
确保你的改动方向和项目规范一致，减少返工。

---

## 目录

- [行为准则](#行为准则)
- [开发环境](#开发环境)
- [分支策略](#分支策略)
- [提交规范](#提交规范)
- [PR 流程](#pr-流程)
- [测试要求](#测试要求)
- [代码审查标准](#代码审查标准)
- [常见问题](#常见问题)

---

## 行为准则

- 只提交你自己编写或拥有明确授权的代码。
- 不提交 API Key、Token、密码或含真实用户 ID 的配置文件。
- 发现安全相关问题，请通过私有渠道报告，不要直接开公开 Issue。

---

## 开发环境

### 前置要求

- Python >= 3.10
- `pip` 或 `pdm` / `poetry`（任选一个即可）
- 虚拟环境（推荐 `venv` 或 `conda`）

### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/Xiaji-yu/nonebot_chat.git
cd nonebot_chat

# 2. 创建虚拟环境（示例）
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖（含开发依赖）
pip install -e ".[dev]"

# 4. 复制环境变量示例
cp .env.example .env

# 5. 运行测试
pytest
```

### 本地检查清单

提交前请确认以下命令通过：

```bash
# 类型/语法检查
python3 -m compileall chat tests

# 运行测试
pytest

# 代码格式检查（可选，逐步迁移）
ruff check chat/ tests/
```

---

## 分支策略

| 分支类型 | 命名规则 | 说明 |
|---------|---------|------|
| 主分支 | `main` | 受保护，只能通过 PR 合并 |
| 功能分支 | `feature/<short-name>` | 新功能，从 `main` 切出 |
| 热修复 | `hotfix/<issue-number>` | 线上问题，从 `main` 切出 |
| 实验分支 | `experiment/<name>` | 验证性改动，合并后删除 |

示例：
```bash
git checkout -b feature/add-session-timeout
git checkout -b hotfix/42-llm-timeout-handling
git checkout -b experiment/new-cache-strategy
```

---

## 提交规范

采用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>

[可选 body：说明为什么，不是说明做了什么]

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Type

| type | 用途 |
|-----|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 仅文档 |
| `test` | 测试相关 |
| `refactor` | 重构（不改功能） |
| `perf` | 性能优化 |
| `chore` | 构建、依赖、配置 |

### Scope

- 单模块改动使用模块名，如 `config`、`pipeline`、`memory`
- 多模块改动使用顶层目录，如 `chat`、`tests`
- 全局改动 scope 留空

### 示例

```bash
# 好的提交
feat(pipeline): add proactive reply deduplication
fix(memory): prevent double distillation under concurrency
docs: update README with markdown formatting examples

# 不好的提交
fix: update code
update
misc changes
```

### 提交前检查

项目使用本地 `pre-commit` 钩子。请确保：

```bash
pre-commit run --all-files
```

如果还没有安装 pre-commit：

```bash
pip install pre-commit
pre-commit install
```

---

## PR 流程

1. 从 `main` 切出功能分支
2. 完成开发并自测通过
3. 确保提交信息符合规范
4. 运行 `pre-commit run --all-files` 全绿
5. 推送到远程并创建 PR

### PR 描述必须包含

- **变更摘要**：1-3 句话说明改了什么、为什么改
- **关联 Issue**：`Closes #123` 或 `Relates #123`
- **测试说明**：改了哪些功能，如何验证
- ** Checklist **：

  - [ ] `pre-commit run --all-files` 通过
  - [ ] `pytest` 全量通过
  - [ ] 已补充/更新测试
  - [ ] 已更新文档（如需要）

### 合并策略

- 功能分支 → `squash and merge`（保持 main 线性历史）
- 热修复 → `merge commit`（保留完整时间线）
- 实验分支 → 合并后删除

---

## 测试要求

### 测试文件组织

```
tests/
├── conftest.py          # 共享 fixtures
├── test_<module>.py     # 业务测试
└── examples/
    └── test_<demo>.py   # 用法示例
```

### 测试命名规范

格式：`test_<被测行为>_<条件>`

```python
# 好
async def test_rate_limiter_blocks_when_exceeds_limit() -> None:
async def test_debouncer_merges_messages_within_window() -> None:

# 不好
async def test_rate_limiter() -> None:
async def test_debounce() -> None:
```

### 测试覆盖要求

每个模块的测试应覆盖：

- [ ] 正常路径（happy path）
- [ ] 边界条件（空输入、最大值、特殊字符）
- [ ] 错误路径（API 失败、网络超时、非法参数）
- [ ] 状态机转换（如有状态）
- [ ] 并发/竞争条件（涉及共享状态时）

### Mock 原则

- 优先使用 `unittest.mock` 标准库
- 不引入重型 mock 框架
- Mock 层级不超过 3 层
- 测试不依赖网络、数据库、外部服务

---

## 代码审查标准

审查沿两个独立维度进行：

### Axis 1 — Standards（规范）

- [ ] 类型注解完整（参数 + 返回值）
- [ ] 公共函数/类有 Google 风格 Docstring
- [ ] 无魔法数字/字符串，常量已提取
- [ ] 异常处理具体，无裸 `except Exception: pass`
- [ ] 导入顺序符合 ruff/isort 约定
- [ ] 提交信息符合 Conventional Commits

### Axis 2 — Spec（需求）

- [ ] 行为与 PRD/Issue 描述一致
- [ ] 无 gold plating（多余功能）
- [ ] 无遗漏边界（少做）
- [ ] 接口签名与约定匹配

### 完成后自检清单

- [ ] **死代码**：无赋值后未使用的变量
- [ ] **缺失类型注解**：参数有默认值但未标注类型
- [ ] **静默丢弃**：无 `else: pass` 或低级别日志掩盖重要信息
- [ ] **幂等性**：重复执行安全
- [ ] **接口最小化**：对外暴露的函数/属性不超出实际需要
- [ ] **并发安全**：共享状态有锁，锁粒度合理
- [ ] **函数签名稳定性**：新增参数有默认值

---

## 常见问题

### Q: 为什么不用 GitHub Actions？

项目偏好本地 `pre-commit` 钩子，保持轻量，无外部 CI 依赖。

### Q: 如何运行单个测试文件？

```bash
pytest tests/test_ratelimit.py -v
```

### Q: 如何查看测试覆盖率？

```bash
pip install pytest-cov
pytest --cov=chat --cov-report=term-missing
```

### Q: 发现 Bug 怎么办？

请先参考 `CLAUDE.md` 的调试协议：

1. 写一个最小复现测试
2. 确认稳定复现
3. 列出 3-5 个假设
4. 逐个验证
5. 修复 + 回归测试

---

## 提问

遇到实现不确定时：

1. 先搜索现有代码和文档
2. 查看 `CLAUDE.md` 是否有相关约定
3. 仍然不确定？在 Issue 或 PR 中标注 `[提问]`，维护者会尽快回复

---

再次感谢你的贡献！

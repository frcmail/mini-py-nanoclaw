# mini-py-nanoclaw

纯 Python 版本的 NanoClaw 实现。

英文主文档请看 [README.md](README.md)。

## 当前状态

- 运行时为纯 Python（`nanoclaw`）。
- setup 链路为纯 Python（`python -m nanoclaw.setup --step ...`）。
- 容器内 agent runner 为纯 Python（`nanoclaw.agent_runner`）。
- 主执行路径中的 Node/TypeScript 运行代码已移除。

## 质量门禁

- CI 在 `push` 与 `pull_request` 上执行。
- Lint：`ruff`
- 测试：`pytest` 多版本矩阵（`3.9`、`3.11`、`3.12`）
- 打包校验：构建 wheel/sdist 并执行 `twine check`

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
.venv/bin/python -m nanoclaw
```

默认运行数据目录为 `~/.nanoclaw`（`NANOCLAW_HOME`），可按需覆盖：

```bash
export NANOCLAW_HOME=/path/to/nanoclaw-home
```

分组记忆文件位于 `$NANOCLAW_HOME/groups/<folder>/CLAUDE.md`（运行时目录，不纳入仓库版本管理）。

需要环境变量时先复制模板：

```bash
cp .env.example .env
```

## Setup 步骤

```bash
python3 -m nanoclaw.setup --step environment
python3 -m nanoclaw.setup --step container
python3 -m nanoclaw.setup --step groups
python3 -m nanoclaw.setup --step register
python3 -m nanoclaw.setup --step mounts
python3 -m nanoclaw.setup --step service
python3 -m nanoclaw.setup --step verify
```

也可使用脚本：

```bash
./setup.sh environment
```

或使用新的脚本路径：

```bash
./scripts/setup.sh environment
```

## Channel 配置

使用 `NANOCLAW_CHANNELS` 指定启用频道：

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

Webhook 相关环境变量：

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=your-bearer-token
NANOCLAW_WEBHOOK_OUTBOUND_URL=https://example.com/outbound  # 可选
```

Webhook 入站接口（`POST /inbound`）字段：

- 必填：`chat_jid`、`sender`、`sender_name`、`content`
- 可选：`timestamp`、`chat_name`、`is_group`

## 测试

```bash
.venv/bin/python -m pytest
```

## Lint

```bash
.venv/bin/python -m ruff check nanoclaw tests
```

## 统一命令

```bash
make lint
make test
make build
make check
```

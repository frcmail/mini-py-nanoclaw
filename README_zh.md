# mini-py-nanoclaw

纯 Python 版本的 NanoClaw 实现。

英文主文档请看 [README.md](README.md)。

## 当前状态

- 运行时为纯 Python（`mini_py_nanoclaw`）。
- setup 链路为纯 Python（`python -m mini_py_nanoclaw.setup --step ...`）。
- 容器内 agent runner 为纯 Python（`mini_py_nanoclaw.agent_runner`）。
- 主执行路径中的 Node/TypeScript 运行代码已移除。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/pip install croniter==2.0.7 pytest==7.4.4 pytest-asyncio==0.23.8
.venv/bin/python -m mini_py_nanoclaw
```

## Setup 步骤

```bash
python3 -m mini_py_nanoclaw.setup --step environment
python3 -m mini_py_nanoclaw.setup --step container
python3 -m mini_py_nanoclaw.setup --step groups
python3 -m mini_py_nanoclaw.setup --step register
python3 -m mini_py_nanoclaw.setup --step mounts
python3 -m mini_py_nanoclaw.setup --step service
python3 -m mini_py_nanoclaw.setup --step verify
```

也可使用脚本：

```bash
./setup.sh environment
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
.venv/bin/python -m pytest tests_py
```

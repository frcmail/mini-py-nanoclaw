# mini-py-nanoclaw

NanoClaw 的纯 Python 运行时实现。

英文文档请看 [README.md](README.md)。

## 仓库提供了什么

- 单一 Python 运行包：`nanoclaw`
- Python setup 流程：`python -m nanoclaw.setup --step <name>`
- Python 容器 agent runner：`python -m nanoclaw.agent_runner`
- 多频道支持：`local-file`、`cli-stdio`、`webhook-http`

## 3 分钟快速上手

1. 创建虚拟环境并安装依赖。
```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
```

2. （可选）复制环境变量模板。
```bash
cp .env.example .env
```

3. 启动服务。
```bash
.venv/bin/python -m nanoclaw
```

## 运行时目录约定

默认运行目录为 `~/.nanoclaw`（可通过 `NANOCLAW_HOME` 覆盖）：

```bash
export NANOCLAW_HOME=/path/to/nanoclaw-home
```

关键目录：

- `$NANOCLAW_HOME/groups/<folder>/CLAUDE.md`：分组记忆文件
- `$NANOCLAW_HOME/store/messages.db`：SQLite 状态库
- `$NANOCLAW_HOME/data/`：频道与 IPC 运行数据

## Setup 流程

逐步执行：

```bash
python3 -m nanoclaw.setup --step environment
python3 -m nanoclaw.setup --step container
python3 -m nanoclaw.setup --step groups
python3 -m nanoclaw.setup --step register
python3 -m nanoclaw.setup --step mounts
python3 -m nanoclaw.setup --step service
python3 -m nanoclaw.setup --step verify
```

脚本入口（行为一致）：

```bash
./scripts/setup.sh verify
```

## 频道配置

使用 `NANOCLAW_CHANNELS`（逗号分隔）启用频道：

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

`local-file` 频道：

- 入站目录：`$NANOCLAW_HOME/data/channels/local-file/inbound`
- 出站目录：`$NANOCLAW_HOME/data/channels/local-file/outbound`

入站文件示例（`*.json`）：
```json
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello"}
```

`cli-stdio` 频道：

- 从 `stdin` 每行读取一条入站消息
- 向 `stdout` 输出 JSON 行格式的出站消息

`webhook-http` 频道：

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=your-bearer-token
NANOCLAW_WEBHOOK_OUTBOUND_URL=https://example.com/outbound  # 可选
```

入站接口：`POST /inbound`，请求头必须包含 `Authorization: Bearer <token>`

必填字段：`chat_jid`、`sender`、`sender_name`、`content`  
可选字段：`timestamp`、`chat_name`、`is_group`

## 开发命令

```bash
make lint        # ruff check nanoclaw tests
make test        # pytest
make build       # 构建 sdist + wheel
make check       # lint + test + build
```

也可直接执行：

```bash
.venv/bin/python -m ruff check nanoclaw tests
.venv/bin/python -m pytest
.venv/bin/python -m build
```

## 容器镜像构建

```bash
cd container
./build.sh
```

## CI 说明

- Lint：`ruff`
- 测试：`pytest`（`3.9`、`3.11`、`3.12`）
- 打包：`build` + `twine check`

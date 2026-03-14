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

可选（非运行时必需）目录：

- `assets/`：品牌与展示素材
- `deploy/`：部署模板（如 launchd）
- `config-examples/`：配置示例

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

兼容入口（行为一致，可选）：`./scripts/setup.sh`、`./setup.sh`

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

## 推荐命令

```bash
make lint        # ruff check nanoclaw tests
make test        # pytest
make build       # 构建 sdist + wheel
make check       # lint + test + build
```

## Docker 化运行

主服务容器（推荐流程）：

```bash
make docker-build
make docker-up
docker compose logs -f nanoclaw
make docker-down
```

前置条件：已安装 Docker Engine 与 Docker Compose 插件。

执行 Docker smoke 测试：

```bash
make docker-smoke
```

Smoke 覆盖内容：

- 构建主服务与 agent 镜像
- 在容器内执行 setup 关键步骤（`environment/container/groups/register/verify`）
- 启动 `docker compose` 并验证 `nanoclaw` 服务处于运行状态

docker.sock 安全说明：

- Compose 默认把宿主机 `/var/run/docker.sock` 挂载到服务容器，确保 NanoClaw 仍可拉起 agent 容器。
- 该能力等价于较高宿主机权限，只建议在可信本机/受控环境中使用。

### 容器职责划分

- 根目录 `Dockerfile`：主服务镜像（`python -m nanoclaw`）
- `container/Dockerfile`：agent runner 镜像（`nanoclaw-agent`），用于任务/容器执行链路

构建 agent 镜像：

```bash
cd container
./build.sh
```

兼容方式：

- 仍可直接使用 `docker compose ...` 与 `./scripts/docker-smoke.sh`。

## CI 说明

- Lint：`ruff`
- 测试：`pytest`（`3.9`、`3.11`、`3.12`）
- 打包：`build` + `twine check`
- Docker smoke：`./scripts/docker-smoke.sh`

# mini-py-nanoclaw

NanoClaw 的纯 Python 运行时实现（主服务链路不依赖 Node）。

英文版本请看 [README.md](README.md)。

## 项目说明

本仓库提供：

- 运行入口：`python -m nanoclaw`
- Setup 入口：`python -m nanoclaw.setup --step <name>`
- Agent 运行入口：`python -m nanoclaw.agent_runner`
- 频道：`local-file`、`cli-stdio`、`webhook-http`

运行时数据统一位于 `NANOCLAW_HOME`（默认 `~/.nanoclaw`）。

## 快速开始

1. 安装依赖

```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
cp .env.example .env  # 可选
```

2. 执行 setup 基础步骤

```bash
./setup.sh environment
./setup.sh groups
./setup.sh register
./setup.sh verify
```

3. 启动服务

```bash
.venv/bin/python -m nanoclaw
```

4. 通过 `local-file` 注入一条测试消息

```bash
mkdir -p ~/.nanoclaw/data/channels/local-file/inbound
cat > ~/.nanoclaw/data/channels/local-file/inbound/hello.json <<'JSON'
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello"}
JSON
```

然后查看出站目录：

- `~/.nanoclaw/data/channels/local-file/outbound/`

## 运行时目录

默认 `NANOCLAW_HOME=~/.nanoclaw`。

关键路径：

- `$NANOCLAW_HOME/groups/<folder>/CLAUDE.md`：分组记忆文件
- `$NANOCLAW_HOME/store/messages.db`：SQLite 状态
- `$NANOCLAW_HOME/data/channels/`：频道运行时文件
- `$NANOCLAW_HOME/data/ipc/`：IPC 运行时文件

以下目录不是运行必需：

- `assets/`（品牌素材）
- `deploy/`（部署模板）
- `config-examples/`（配置示例）

## Setup 步骤

可以直接调用 `python -m nanoclaw.setup --step <name>`，也可以用 `./setup.sh <step>` 包装入口。

步骤说明：

1. `environment`：检查 Python 版本与平台
2. `container`：检查容器运行时可用性
3. `groups`：创建默认分组记忆文件
4. `register`：注册本地主分组
5. `mounts`：按需生成 mount allowlist 配置
6. `service`：输出服务模式提示
7. `verify`：检查运行目录完整性

完整执行序列：

```bash
python -m nanoclaw.setup --step environment
python -m nanoclaw.setup --step container
python -m nanoclaw.setup --step groups
python -m nanoclaw.setup --step register
python -m nanoclaw.setup --step mounts
python -m nanoclaw.setup --step service
python -m nanoclaw.setup --step verify
```

兼容入口：

- `./setup.sh`
- `./scripts/setup.sh`

## 配置项

核心环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `NANOCLAW_HOME` | `~/.nanoclaw` | 运行目录（groups/store/data） |
| `ASSISTANT_NAME` | `Andy` | 助手名称/触发名 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `NANOCLAW_CHANNELS` | `local-file` | 频道列表（逗号分隔） |
| `NANOCLAW_WEBHOOK_HOST` | `127.0.0.1` | Webhook 监听地址 |
| `NANOCLAW_WEBHOOK_PORT` | `8787` | Webhook 监听端口 |
| `NANOCLAW_WEBHOOK_TOKEN` | 空 | 启用 webhook 时必填 |
| `NANOCLAW_WEBHOOK_OUTBOUND_URL` | 空 | 可选 webhook 出站回调地址 |
| `CONTAINER_TIMEOUT` | `1800000` | Agent 执行超时（毫秒） |
| `MAX_CONCURRENT_CONTAINERS` | `5` | 分组队列并发上限 |
| `NANOCLAW_REQUIRE_CONTAINER_RUNTIME` | `0` | `1`=运行时不可用即失败；`0`=降级启动 |

## 频道使用

启用多频道：

```bash
export NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

### local-file

- 入站：`$NANOCLAW_HOME/data/channels/local-file/inbound/*.json`
- 出站：`$NANOCLAW_HOME/data/channels/local-file/outbound/*.json`

入站示例：

```json
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello","is_group":true}
```

### cli-stdio

- 入站：从 `stdin` 按行读取（纯文本或 JSON）
- 出站：向 `stdout` 输出 JSON 行

示例：

```bash
echo '{"chat_jid":"cli:main","sender":"cli:user","sender_name":"CLI","content":"hello"}' | \
  NANOCLAW_CHANNELS=cli-stdio .venv/bin/python -m nanoclaw
```

### webhook-http

启用时至少需要：

```bash
export NANOCLAW_CHANNELS=webhook-http
export NANOCLAW_WEBHOOK_TOKEN=your-token
```

入站接口：

- `POST /inbound`
- Header：`Authorization: Bearer <token>`
- 必填字段：`chat_jid`、`sender`、`sender_name`、`content`
- 可选字段：`timestamp`、`chat_name`、`is_group`

出站行为：

- 一定会写入 `$NANOCLAW_HOME/data/channels/webhook/outbound/`
- 可选再 POST 到 `NANOCLAW_WEBHOOK_OUTBOUND_URL`

## 开发命令

```bash
make install-dev
make lint
make test
make build
make check
make run
make setup-verify
```

## Docker

### 主服务

```bash
make docker-build
make docker-up
docker compose logs -f nanoclaw
make docker-down
```

### Smoke 测试

```bash
make docker-smoke
```

Smoke 覆盖：

- 构建主服务镜像
- 构建 agent 镜像
- 校验 agent 入口 marker 输出
- 执行 setup smoke（`environment/container/groups/register/verify`）
- 启动 compose 并确认服务存活

### 容器职责

- 根目录 `Dockerfile`：主服务镜像（`python -m nanoclaw`）
- `container/Dockerfile`：agent 镜像（`nanoclaw-agent`）

直接构建 agent：

```bash
./container/build.sh local
```

### docker.sock 安全说明

Compose 会把 `/var/run/docker.sock` 挂载进服务容器，以保留容器调度能力。
这等价于较高主机权限，仅建议在可信环境中使用。

## CI

当前 CI 包含：

- Ruff lint
- Pytest 矩阵（`3.9`、`3.11`、`3.12`）
- 打包构建 + `twine check`
- Docker smoke 脚本

## 常见问题

1. `./setup.sh` 提示模块导入失败

- 确保在仓库根目录执行
- 确保 `.venv` 存在，或 `python3` 已安装 `nanoclaw`

2. Webhook 返回 `401 unauthorized`

- 检查 `NANOCLAW_WEBHOOK_TOKEN`
- 检查请求头格式 `Authorization: Bearer <token>`

3. 服务启动但不回消息

- 检查 `NANOCLAW_CHANNELS`
- 检查入站 payload 的 `content` 非空
- 运行 `python -m nanoclaw.setup --step verify`

4. Docker 不可用但希望服务继续运行

- 保持 `NANOCLAW_REQUIRE_CONTAINER_RUNTIME=0`（默认）
- 只有需要 fail-fast 时再设为 `1`

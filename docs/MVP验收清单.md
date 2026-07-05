# QQ 群机器人 MVP 验收清单

本清单用于在 Linux 云服务器上验证 MVP 是否达到 `docs/MVP规格.md` 的完成定义。每项要求对应的证据类型见 `docs/MVP验收证据矩阵.md`。

## 1. 部署前检查

- 已安装 Docker 和 Docker Compose。
- 已复制 `.env.production.example` 为 `.env`。
- 已修改 `ADMIN_PASSWORD`、`APP_SECRET_KEY`、`POSTGRES_PASSWORD`。
- 已配置 `ALLOWED_GROUPS` 为目标 QQ 群号。
- 已配置 `BOT_QQ` 为机器人 QQ 号。
- 已配置 `ONEBOT_ACCESS_TOKEN`，并确保 Lagrange.OneBot 与 Bot Core 使用同一个 token。
- 如需验收 `/warn`、`/banword` 等群管命令，已配置 `ADMIN_QQ_IDS` 为管理员 QQ 号。
- 已按实际模型服务配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。
- 已准备 Lagrange.OneBot 配置和登录态目录 `data/onebot`。

生成 Lagrange.OneBot 配置：

```bash
python scripts/prepare_lagrange_config.py --env-file .env
```

执行生产配置自检：

```bash
python scripts/preflight_check.py --env-file .env
```

该检查会验证默认密码、数据库连接、群号、管理员 QQ、命令前缀、OneBot 反向 WebSocket 地址、模型 Base URL、模型参数和限流参数。若 `COMMAND_PREFIX` 为空，或 `ONEBOT_REVERSE_WS_URL` 不是 `ws://`/`wss://` 地址，或 `LLM_BASE_URL` 不是 `http://`/`https://` 地址，应先修正再启动服务。

正式上线前建议使用严格模式：

```bash
python scripts/preflight_check.py --env-file .env --strict
```

## 2. 启动服务

```bash
docker compose up -d --build
docker compose ps
```

也可以使用部署脚本完成配置自检、启动和 Bot Core 冒烟检查：

```bash
sh scripts/deploy_mvp.sh
```

正式上线前建议启用严格预检，让推荐项缺失也直接失败：

```bash
STRICT_PREFLIGHT=1 sh scripts/deploy_mvp.sh
```

真实 OneBot 登录后，可以让部署脚本同时强校验 OneBot 在线状态：

```bash
STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ONLINE=1 sh scripts/deploy_mvp.sh
```

真实 QQ 群完成收发测试和群管命令测试后，可以让部署脚本进一步强校验最近活动和 admin-lite 审计记录：

```bash
STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ACTIVITY=1 REQUIRE_MVP_CORE_LOGS=1 REQUIRE_ADMIN_LITE_AUDIT=1 sh scripts/deploy_mvp.sh
```

预期：

- `postgres` 为 healthy。
- `redis` 为 healthy。
- `bot-app` 为 healthy。
- `web-admin` 为 healthy。
- `onebot` 正常运行，或进入等待扫码/登录流程。
- `bot-app` 的宿主机 `8000` 端口只绑定 `127.0.0.1`，不要直接对公网开放。

完成 OneBot 登录后，可以先执行在线状态验收。真实 Lagrange.OneBot 已在线时，建议跳过模拟 OneBot 连接，避免模拟 WebSocket 临时占用 Bot Core 的当前 OneBot 连接状态：

```bash
python scripts/mvp_acceptance.py \
  --env-file .env \
  --strict-preflight \
  --require-onebot-online \
  --skip-onebot-simulation
```

该脚本会依次执行生产配置自检和 HTTP smoke，并强校验 OneBot 在线状态。真实 QQ 群完成 `/ping`、`/help`、`/dice`、`/ai` 或 @ 回复测试后，再追加 `--require-onebot-activity`，强校验后台已经记录最近入站事件和出站动作。模拟 OneBot 核心命令和 admin-lite 场景适合在真实 OneBot 登录前、或临时停止 `onebot` 容器后单独执行；真实 QQ 群里的群管命令按后文“权限和群管验收”手动验证。

## 3. Bot Core 冒烟检查

```bash
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis
```

预期：

- `/api/system/health` 返回 ok。
- `/api/system/ready` 可在浏览器或 curl 中返回 ok。
- `/api/system/ready` 中 cache backend 为 `redis`。
- 后台认证接口可用。
- 群、模型、日志、LLM 调用日志接口可访问。

后台群管理页可在目标群第一次发言前手动添加群号，设置启用状态和回复模式。群号必须使用数字 QQ 群号。

## 4. 模拟 OneBot 检查

```bash
python scripts/onebot_simulate.py \
  --ws-url ws://127.0.0.1:8000/onebot/ws \
  --group-id <ALLOWED_GROUPS中的一个群号> \
  --access-token "$ONEBOT_ACCESS_TOKEN"
```

预期：

- 输出多条 `send_group_msg` 动作。
- `/ping` 的 `params.message` 为 `pong`。
- `/help`、`/dice 2d6`、`/ai hello` 均有符合预期的回复；未配置 API Key 时，`/ai` 会返回明确配置提示。
- 后台消息日志能看到这些模拟消息。

如果只想检查最小反向 WebSocket 连通性，可以执行：

```bash
python scripts/onebot_simulate.py \
  --ws-url ws://127.0.0.1:8000/onebot/ws \
  --group-id <ALLOWED_GROUPS中的一个群号> \
  --access-token "$ONEBOT_ACCESS_TOKEN" \
  --scenario ping
```

如果要单独检查群管最小闭环，可以确保 `ADMIN_QQ_IDS` 已配置后执行：

```bash
python scripts/onebot_simulate.py \
  --ws-url ws://127.0.0.1:8000/onebot/ws \
  --group-id <ALLOWED_GROUPS中的一个群号> \
  --user-id <ADMIN_QQ_IDS中的一个QQ号> \
  --access-token "$ONEBOT_ACCESS_TOKEN" \
  --scenario admin-lite
```

预期：

- `/warn` 返回已记录警告。
- `/banword add` 返回已添加关键词。
- 随后的关键词命中消息返回配置的拦截提示。
- 后台审计日志能看到 `warn` 和 `banword_add`。

如果要单独检查 `active` 回复模式，可以先在后台把测试群回复模式改为 active，再执行：

```bash
python scripts/onebot_simulate.py \
  --ws-url ws://127.0.0.1:8000/onebot/ws \
  --group-id <ALLOWED_GROUPS中的一个群号> \
  --access-token "$ONEBOT_ACCESS_TOKEN" \
  --scenario active-question
```

预期：

- 普通疑问句会触发一次大模型回复；未配置 API Key 时会返回明确配置提示。
- 后台消息日志能看到 `active_chat`。

## 5. 真实 QQ 群验收

Lagrange.OneBot 登录完成后，先执行在线状态强校验：

```bash
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis \
  --require-onebot-online
```

预期：

- 后台 OneBot 状态为在线。
- Redis 缓存后端为 `redis`。

在目标 QQ 群中发送：

```text
/ping
```

预期：

- 机器人回复 `pong`。
- 后台 OneBot 状态显示在线。
- 后台消息日志出现该消息和处理状态。

发送：

```text
/help
```

预期：

- 机器人回复命令列表。

发送：

```text
/dice 2d6
```

预期：

- 机器人回复骰子结果。
- LLM 调用日志不新增。

发送：

```text
/ai 你好，请简单介绍你自己
```

预期：

- 配置了模型 API Key 时，机器人回复大模型结果。
- 未配置 API Key 时，机器人明确提示需要配置 API Key。
- 后台 LLM 调用日志有记录。

@机器人并提问：

```text
@机器人 你能做什么？
```

预期：

- 机器人调用大模型回复。
- 消息日志和 LLM 调用日志均可查询。

真实群完成上述收发测试后，再执行活动强校验：

```bash
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis \
  --require-onebot-online \
  --require-onebot-activity \
  --require-mvp-core-logs
```

预期：

- 后台 OneBot 状态仍为在线。
- 后台 OneBot 状态有最近事件和最近动作时间。
- `/api/system/logs` 中存在 `/ping`、`/help`、`/dice`、`/ai` 对应的处理记录。

## 6. 权限和群管验收

普通用户发送：

```text
/warn @某人 测试
```

预期：

- 机器人回复权限不足。

管理员 QQ 号加入 `ADMIN_QQ_IDS` 后发送：

```text
/warn @某人 测试管理警告
```

预期：

- 机器人回复已记录警告。
- 审计日志记录 `warn`。

继续发送：

```text
/banword add 测试广告 请不要发广告
```

随后发送包含 `测试广告` 的消息。

预期：

- 机器人回复配置的拦截提示。
- 审计日志记录 `banword_add`。

完成真实群管命令后，可以自动校验 admin-lite 审计记录：

```bash
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis \
  --require-admin-lite-audit
```

预期：

- `/api/audit-logs` 中存在 `warn` 和 `banword_add`。

## 7. 故障恢复验收

重启 Bot Core：

```bash
docker compose restart bot-app
```

预期：

- `bot-app` 恢复 healthy。
- 群配置仍存在。
- `/ping` 仍可回复。

断开或重启 OneBot：

```bash
docker compose restart onebot
```

预期：

- OneBot 重新连接 Bot Core。
- 后台 OneBot 状态恢复在线。

## 8. 备份验收

```bash
sh scripts/backup.sh
ls data/backups
```

预期：

- 生成 PostgreSQL SQL 备份文件。

如需演练恢复流程，先确认当前环境允许覆盖数据库，再执行：

```bash
FORCE=1 sh scripts/restore_postgres.sh ./data/backups/<备份文件名>.sql
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --expect-cache-backend redis
```

预期：

- PostgreSQL 可从 SQL 备份恢复。
- 恢复后 Bot Core 健康检查和后台 API 仍可访问。
- 群配置、消息日志等数据库持久数据符合备份时状态。

## 9. MVP 完成判定

以下全部满足时，MVP 可判定完成：

- Docker Compose 可启动核心服务。
- Bot Core ready 健康检查通过。
- 模拟 OneBot WebSocket 可收到 `pong` 动作。
- 真实 QQ 群 `/ping`、`/help`、`/dice` 可用。
- `/ai` 和 @机器人可按模型配置返回结果或明确错误。
- 后台可登录、配置模型、查看群开关和日志。
- PostgreSQL 数据持久化，重启后配置不丢失。
- OneBot 登录恢复流程和常见故障处理文档已确认。

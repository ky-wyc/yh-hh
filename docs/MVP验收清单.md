# QQ 群机器人 MVP 验收清单

本清单用于在 Linux 云服务器上验证 MVP 是否达到 `docs/MVP规格.md` 的完成定义。

## 1. 部署前检查

- 已安装 Docker 和 Docker Compose。
- 已复制 `.env.production.example` 为 `.env`。
- 已修改 `ADMIN_PASSWORD`、`APP_SECRET_KEY`、`POSTGRES_PASSWORD`。
- 已配置 `ALLOWED_GROUPS` 为目标 QQ 群号。
- 已配置 `BOT_QQ` 为机器人 QQ 号。
- 已按实际模型服务配置 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。
- 已准备 Lagrange.OneBot 配置和登录态目录 `data/onebot`。

执行生产配置自检：

```bash
python scripts/preflight_check.py --env-file .env
```

正式上线前建议使用严格模式：

```bash
python scripts/preflight_check.py --env-file .env --strict
```

## 2. 启动服务

```bash
docker compose up -d --build
docker compose ps
```

预期：

- `postgres` 为 healthy。
- `redis` 为 healthy。
- `bot-app` 为 healthy。
- `web-admin` 为 healthy。
- `onebot` 正常运行，或进入等待扫码/登录流程。

## 3. Bot Core 冒烟检查

```bash
python scripts/smoke_check.py \
  --base-url http://127.0.0.1:8000 \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD"
```

预期：

- `/api/system/health` 返回 ok。
- `/api/system/ready` 可在浏览器或 curl 中返回 ok。
- 后台认证接口可用。
- 群、模型、日志、LLM 调用日志接口可访问。

## 4. 模拟 OneBot 检查

```bash
python scripts/onebot_simulate.py \
  --ws-url ws://127.0.0.1:8000/onebot/ws \
  --group-id <ALLOWED_GROUPS中的一个群号>
```

预期：

- 输出 `send_group_msg` 动作。
- `params.message` 为 `pong`。
- 后台消息日志能看到该模拟消息。

## 5. 真实 QQ 群验收

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

## 6. 权限和群管验收

普通用户发送：

```text
/warn @某人 测试
```

预期：

- 机器人回复权限不足。

管理员 QQ 号加入 `ADMIN_QQ_IDS` 后发送：

```text
/banword add 测试广告 请不要发广告
```

随后发送包含 `测试广告` 的消息。

预期：

- 机器人回复配置的拦截提示。
- 审计日志记录关键词配置操作。

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

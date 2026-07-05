# 机器人

本仓库实现 `docs/MVP规格.md` 描述的 MVP 版本：QQ 小号通过 OneBot v11 反向 WebSocket 接入，Bot Core 负责消息路由、基础 Skill、大模型调用、后台 API 和 Docker 部署。

## MVP 能力

- OneBot v11 反向 WebSocket：`/onebot/ws`
- 群消息接收、消息去重、群白名单
- `/help`、`/ping`、`/ai`、`/dice`
- `@机器人` 调用大模型
- `admin-lite`：`/warn`、`/banword add/remove/list`
- PostgreSQL/SQLite 兼容的数据模型
- Redis 限流状态，开发环境可降级为内存实现
- 后台 API：登录、状态、群设置、系统设置、日志
- Vue 3 管理端源码骨架
- Docker Compose 部署文件

## 本地开发

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
pytest
uvicorn app.main:create_app --factory --reload
```

开发默认使用 SQLite 和内存缓存。生产部署请使用 Docker Compose 中的 PostgreSQL 和 Redis。

## 一键检查

```bash
python scripts/check_all.py --pnpm pnpm
```

也可以连同本地运行态 smoke 一起跑：

```bash
python scripts/check_all.py --pnpm pnpm --with-smoke
```

## Docker Compose

```bash
cp .env.production.example .env
# 编辑 .env，替换所有默认密码、token、群号和模型配置
python scripts/preflight_check.py --env-file .env
docker compose up -d --build
```

Linux 服务器上也可以使用部署脚本完成 preflight、启动和 smoke：

```bash
sh scripts/deploy_mvp.sh
```

正式上线前可以启用严格预检，让推荐项缺失也直接失败：

```bash
STRICT_PREFLIGHT=1 sh scripts/deploy_mvp.sh
```

真实 OneBot 登录后，可以要求部署脚本同时校验在线状态：

```bash
STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ONLINE=1 sh scripts/deploy_mvp.sh
```

真实 QQ 群完成收发测试和群管命令测试后，可以进一步启用活动与审计强校验：

```bash
STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ACTIVITY=1 REQUIRE_MVP_CORE_LOGS=1 REQUIRE_ADMIN_LITE_AUDIT=1 sh scripts/deploy_mvp.sh
```

`preflight_check.py` 会检查生产密码、数据库连接、群号、管理员 QQ、命令前缀、OneBot 反向 WebSocket 地址、模型 Base URL、模型参数和限流参数，正式上线前建议先修完所有 error 和 strict warning。

部署脚本会根据 `.env` 自动生成：

```text
data/onebot/appsettings.json
```

OneBot 容器默认使用 `ghcr.io/lagrangedev/lagrange.onebot:edge`。可以参考 `deploy/lagrange/appsettings.example.json` 配置反向 WebSocket，使其连接：

```text
ws://bot-app:8000/onebot/ws
```

`bot-app` 的宿主机端口默认只绑定 `127.0.0.1:8000`，供服务器本机 smoke 和排障使用；对外访问后台请使用 `web-admin` 暴露的端口。生产环境建议再通过 HTTPS 反向代理、服务器防火墙或访问控制保护后台入口。

备份和恢复：

```bash
sh scripts/backup.sh
FORCE=1 sh scripts/restore_postgres.sh ./data/backups/<备份文件名>.sql
```

## MVP Smoke Check

服务启动后可以先跑 HTTP 检查。生产环境建议使用 `.env` 中的后台账号：

```bash
python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis
```

如需保存机器可读的 smoke 结果，可以追加报告文件路径：

```bash
python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis --report-file data/smoke-report.json
```

如果 OneBot 已完成登录，可以追加 `--require-onebot-online` 做上线强校验。真实 QQ 群完成收发测试后，还可以追加 `--require-onebot-activity`，要求后台已经记录最近入站事件和出站动作。
真实核心命令完成后，还可以追加 `--require-mvp-core-logs`，要求消息日志中已经记录 `/ping`、`/help`、`/dice`、`/ai` 的处理结果。
真实群管命令完成后，还可以追加 `--require-admin-lite-audit`，要求审计日志中已经记录 `warn` 和 `banword_add`。

也可以把生产自检和 HTTP smoke 串起来执行。若真实 Lagrange.OneBot 已在线，追加 `--skip-onebot-simulation`，只做在线状态强校验，避免模拟连接临时占用当前 OneBot 连接状态：

```bash
python scripts/mvp_acceptance.py --env-file .env --strict-preflight --require-onebot-online --skip-onebot-simulation
```

真实 QQ 群完成收发测试和群管命令测试后，再追加 `--require-onebot-activity --require-mvp-core-logs --require-admin-lite-audit` 执行最终活动、核心命令日志与审计校验。

真实 OneBot 登录前，或临时停止 `onebot` 容器后，可以用模拟 OneBot 连接验证反向 WebSocket：

```bash
python scripts/onebot_simulate.py --ws-url ws://127.0.0.1:8000/onebot/ws --group-id 10001 --access-token "$ONEBOT_ACCESS_TOKEN"
```

默认会模拟 `/ping`、`/help`、`/dice 2d6`、`/ai hello`。如果只想检查最小连通性，可以追加 `--scenario ping`；如果要单独检查群管最小闭环，可以在设置 `ADMIN_QQ_IDS` 后使用 `--scenario admin-lite`；如果已把测试群回复模式设为 `active`，可以使用 `--scenario active-question` 检查普通疑问句主动回答。

如果配置了 `ALLOWED_GROUPS`，模拟脚本的 `--group-id` 必须在白名单里。

本地开发也可以一条命令完成 HTTP、反向 WebSocket、基础命令和 admin-lite 检查：

```bash
python scripts/local_smoke.py --port 8765 --allowed-groups 10001
```

## 后台

默认账号来自 `.env`：

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

API Key 不会在后台接口明文返回，只返回 `api_key_configured`。后台可以写入新 Key，也可以清空已有 Key；清空后模型调用会返回明确配置提示。

运行期主要配置优先在后台完成，`.env` 作为首次启动和兜底默认值。后台“系统设置”已覆盖：

- 大模型 Provider、Base URL、API Key、模型名、温度、Token、超时和连通性测试。
- 机器人 QQ、机器人昵称、管理员 QQ、群白名单。
- 默认新群启用状态、默认回复模式、命令前缀。
- 用户/群每分钟限流。

## 文档

- `docs/QQ机器人系统设计方案.md`
- `docs/MVP规格.md`
- `docs/MVP验收清单.md`
- `docs/MVP验收证据矩阵.md`
- `docs/MVP本地完成状态.md`
- `docs/一期产品蓝图.md`
- `docs/二期能力池.md`
- `docs/运维说明.md`

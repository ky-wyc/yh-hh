# 新一代 QQ 群机器人 MVP

本仓库实现 `docs/MVP规格.md` 描述的 MVP 版本：QQ 小号通过 OneBot v11 反向 WebSocket 接入，Bot Core 负责消息路由、基础 Skill、大模型调用、后台 API 和 Docker 部署。

## MVP 能力

- OneBot v11 反向 WebSocket：`/onebot/ws`
- 群消息接收、消息去重、群白名单
- `/help`、`/ping`、`/ai`、`/dice`
- `@机器人` 调用大模型
- `admin-lite`：`/warn`、`/banword add/remove/list`
- PostgreSQL/SQLite 兼容的数据模型
- Redis 限流状态，开发环境可降级为内存实现
- 后台 API：登录、状态、群设置、模型设置、日志
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

## Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

OneBot 容器默认使用 `ghcr.io/lagrangedev/lagrange.onebot:edge`。可以参考 `deploy/lagrange/appsettings.example.json` 配置反向 WebSocket，使其连接：

```text
ws://bot-app:8000/onebot/ws
```

## MVP Smoke Check

服务启动后可以先跑 HTTP 检查：

```bash
python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username admin --password change-me
```

再用模拟 OneBot 连接验证反向 WebSocket：

```bash
python scripts/onebot_simulate.py --ws-url ws://127.0.0.1:8000/onebot/ws --group-id 10001
```

如果配置了 `ALLOWED_GROUPS`，模拟脚本的 `--group-id` 必须在白名单里。

本地开发也可以一条命令完成 HTTP 和反向 WebSocket 检查：

```bash
python scripts/local_smoke.py --port 8765 --allowed-groups 10001
```

## 后台

默认账号来自 `.env`：

```text
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me
```

API Key 不会在后台接口明文返回，只返回 `api_key_configured`。

## 文档

- `docs/QQ机器人系统设计方案.md`
- `docs/MVP规格.md`
- `docs/一期产品蓝图.md`
- `docs/二期能力池.md`

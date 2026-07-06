# QQ 群机器人 MVP 本地完成状态

本文用于记录当前 MVP 在“真实 QQ 群验收暂不考虑”口径下的完成状态。真实 Linux 云服务器、OneBot 接入层登录、真实 QQ 群收发、备份恢复演练仍保留在 `MVP验收清单.md` 和 `MVP验收证据矩阵.md` 中，后续上线时再执行。

## 1. 当前结论

在本地和 CI 可验证范围内，MVP 已完成：

- OneBot v11 反向 WebSocket 接入路径。
- 群文本消息标准化、去重、后台可配置白名单和回复模式。
- `/help`、`/ping`、`/ai`、`/dice`。
- `admin-lite`：`/warn`、`/banword add/remove/list` 和关键词命中回复。
- OpenAI-compatible 大模型配置、缺 Key 明确提示、调用日志。
- 后台登录、仪表盘、群设置、系统设置、日志、审计日志。
- 后台可配置大模型 API、机器人 QQ/昵称、管理员 QQ、群白名单、默认回复模式、命令前缀和限流参数。
- SQLite 开发模式、PostgreSQL/Redis 生产部署配置。
- Docker Compose、NapCat 接入、预检、备份、恢复脚本。
- 本地 smoke、模拟 OneBot、生产 smoke、机器可读 smoke 报告。

## 2. 当前证明命令

本地最终检查命令：

```powershell
& 'C:\Users\WYC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/check_all.py --python 'C:\Users\WYC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' --pnpm 'C:\Users\WYC\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\pnpm.cmd' --with-smoke
```

当前通过内容：

- `compileall app scripts`
- `ruff check .`
- `pytest`
- `web-admin` 生产构建
- `scripts/local_smoke.py`

当前测试结果：

```text
97 passed
All MVP checks passed.
```

## 3. MVP 规格对应状态

| MVP 规格项 | 本地状态 | 证据 |
| --- | --- | --- |
| OneBot v11 反向 WebSocket | 已完成 | `/onebot/ws`、`onebot_simulate.py`、OneBot 相关测试 |
| 接收群文本消息 | 已完成 | `events` 测试、`local_smoke.py` |
| 忽略非文本消息 | 已完成 | `tests/test_events.py` |
| 发送群文本消息 | 已完成 | `onebot_simulate.py` 返回 `send_group_msg` |
| 断线状态记录 | 已完成 | OneBot 状态接口和测试 |
| 事件标准化和去重 | 已完成 | `tests/test_events.py`、`tests/test_router.py` |
| 群白名单 | 已完成 | 后台系统设置、`tests/test_router.py`、`preflight_check.py` |
| `/help`、`/ping`、`/ai`、`/dice` | 已完成 | `local_smoke.py`、`tests/test_router.py` |
| `active` 疑问句保守回复 | 已完成 | `local_smoke.py`、`tests/test_router.py` |
| OpenAI-compatible LLM | 已完成 | `app/llm.py`、后台系统设置、测试 |
| 大模型错误处理和日志 | 已完成 | `tests/test_admin_api.py`、`local_smoke.py` |
| admin-lite | 已完成 | `tests/test_router.py`、`local_smoke.py` |
| 数据持久模型 | 已完成 | SQLAlchemy 模型、SQLite/PostgreSQL 配置、测试 |
| Redis/内存缓存 | 已完成 | `app/cache.py`、`tests/test_cache.py` |
| Web 后台 MVP | 已完成 | Vue 构建、后台 API 测试、系统设置页 |
| Docker Compose 部署文件 | 已完成 | `docker-compose.yml`、`tests/test_deployment_config.py` |
| 健康检查和 smoke | 已完成 | `/api/system/health`、`/api/system/ready`、`smoke_check.py` |
| 备份和恢复脚本 | 已完成 | `scripts/backup.sh`、`scripts/restore_postgres.sh`、部署配置测试 |
| 运维说明 | 已完成 | `docs/运维说明.md` |

## 4. 暂不计入完成条件

以下项目不是当前本地完成口径的一部分：

- 真实 Linux 云服务器部署。
- 真实 QQ 小号登录。
- 真实 QQ 群收发。
- 真实 OneBot 重连恢复。
- 真实 PostgreSQL 备份恢复演练。

这些项目的执行步骤已经保留在：

- `docs/MVP验收清单.md`
- `docs/MVP验收证据矩阵.md`
- `docs/运维说明.md`

## 5. 后续进入真实验收时的入口

真实环境准备好后，建议从以下命令开始：

```bash
STRICT_PREFLIGHT=1 sh scripts/deploy_mvp.sh
```

真实群完成基础命令、AI 和群管测试后，可以运行：

```bash
STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ACTIVITY=1 REQUIRE_MVP_CORE_LOGS=1 REQUIRE_ADMIN_LITE_AUDIT=1 sh scripts/deploy_mvp.sh
```

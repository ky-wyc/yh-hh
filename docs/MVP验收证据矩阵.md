# QQ 群机器人 MVP 验收证据矩阵

本矩阵用于把 `MVP规格.md` 的交付范围映射到可执行证据。它不替代 `MVP验收清单.md`，而是帮助判断哪些能力可以在本地或 CI 中证明，哪些必须在 Linux 云服务器和真实 QQ 群中证明。

## 1. 使用原则

- 本地测试、CI 和模拟 OneBot 只能证明 Bot Core、后台 API、前端构建和协议处理逻辑。
- MVP 完成必须有真实 Linux 云服务器、真实 Lagrange.OneBot 登录态、真实 QQ 群收发证据。
- `--require-onebot-online` 只证明 OneBot 当前在线。
- `--require-onebot-activity` 需要真实或模拟消息已经产生最近入站事件和出站动作；真实上线验收时，应在真实 QQ 群完成收发测试后再执行。
- 模拟 OneBot 检查适合在真实 OneBot 登录前、或临时停止 `onebot` 容器后执行，避免干扰当前在线状态。

## 2. 本地和 CI 证据

| 要求 | 证据命令 | 证明内容 | 不能证明 |
| --- | --- | --- | --- |
| Python 代码可导入、语法有效 | `python scripts/check_all.py --pnpm pnpm` | `app` 和 `scripts` 可编译，ruff 和 pytest 通过 | Linux 容器真实运行 |
| 后端单元和集成逻辑 | `python -m pytest` | 路由、权限、后台运行期配置、缓存、OneBot 事件、admin-lite 等测试通过 | 真实 QQ 协议兼容性 |
| 前端可构建 | `cd web-admin && pnpm run build` | Vue 管理端生产构建成功 | 服务器公网访问和 HTTPS |
| 本地运行态闭环 | `python scripts/check_all.py --pnpm pnpm --with-smoke` | 本地启动、HTTP smoke、模拟 OneBot 核心命令、admin-lite 基本闭环 | 真实 Lagrange 登录和真实 QQ 群收发 |
| Smoke 机器可读报告 | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --report-file data/smoke-report.json` | 生成 JSON 报告，记录 health、ready、OneBot 状态、接口检查和缺失项 | 不替代端到端业务验收 |
| 模拟 OneBot 反向 WebSocket | `python scripts/onebot_simulate.py --ws-url ws://127.0.0.1:8000/onebot/ws --group-id 10001 --access-token "$ONEBOT_ACCESS_TOKEN"` | Bot Core 能接收模拟群消息并返回 `send_group_msg` 动作 | QQ 小号风控、登录态、真实群权限 |

## 3. 生产部署证据

| MVP 要求 | 必要证据 | 推荐命令或操作 | 通过标准 |
| --- | --- | --- | --- |
| 生产配置完整 | 严格预检输出成功 | `python scripts/preflight_check.py --env-file .env --strict` | 无 error，strict warning 已处理 |
| Docker Compose 可启动核心服务 | 容器状态 | `docker compose up -d --build && docker compose ps` | `postgres`、`redis`、`bot-app`、`web-admin` healthy，`onebot` 运行或进入登录流程 |
| 部署脚本完整强校验 | 部署脚本输出成功 | `STRICT_PREFLIGHT=1 REQUIRE_ONEBOT_ACTIVITY=1 REQUIRE_MVP_CORE_LOGS=1 REQUIRE_ADMIN_LITE_AUDIT=1 sh scripts/deploy_mvp.sh` | 严格预检、启动、HTTP smoke、OneBot 在线、最近活动、核心命令日志和 admin-lite 审计均通过 |
| Bot Core ready | HTTP smoke | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis` | health、ready、后台 API、日志 API 可访问，cache backend 为 `redis` |
| OneBot 在线 | OneBot 状态 API | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis --require-onebot-online` | `/api/system/onebot-status` 返回 online |
| OneBot 活动记录 | 真实群收发后的状态 API | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis --require-onebot-online --require-onebot-activity` | 存在 `last_event_at` 和 `last_action_at` |
| 核心命令消息日志 | 真实核心命令后的消息日志 | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis --require-mvp-core-logs` | `/api/system/logs` 中存在 `command:ping`、`command:help`、`command:dice`、`command:ai` |
| admin-lite 审计记录 | 真实群管命令后的审计日志 | `python scripts/smoke_check.py --base-url http://127.0.0.1:8000 --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --expect-cache-backend redis --require-admin-lite-audit` | `/api/audit-logs` 中存在 `warn` 和 `banword_add` |
| 一键生产验收在线状态 | 验收脚本输出成功 | `python scripts/mvp_acceptance.py --env-file .env --strict-preflight --require-onebot-online --skip-onebot-simulation` | 预检、HTTP smoke、OneBot 在线均通过 |
| 一键生产验收活动和群管状态 | 真实核心命令、真实群管命令后验收脚本输出成功 | `python scripts/mvp_acceptance.py --env-file .env --strict-preflight --require-onebot-online --require-onebot-activity --require-mvp-core-logs --require-admin-lite-audit --skip-onebot-simulation` | 预检、HTTP smoke、OneBot 在线、活动、核心命令日志和 admin-lite 审计均通过 |

## 4. 真实 QQ 群功能证据

| MVP 要求 | 群内操作 | 后台或日志证据 | 通过标准 |
| --- | --- | --- | --- |
| 接收并回复群文本消息 | 在白名单目标群发送 `/ping` | 消息日志出现该消息，OneBot 状态有最近事件和动作 | 群内回复 `pong` |
| `/help` 可用 | 发送 `/help` | 消息日志记录处理状态 | 群内回复命令列表 |
| `/dice` 可用且不调用模型 | 发送 `/dice 2d6` | 消息日志有回复，LLM 调用日志不新增 | 群内回复骰子结果 |
| `/ai` 可用 | 发送 `/ai 你好，请简单介绍你自己` | LLM 调用日志有记录 | 配置 API Key 时返回模型结果；未配置时返回明确配置提示 |
| @机器人可用 | @机器人并提问 | 消息日志和 LLM 调用日志均可查询 | 群内返回模型回复或明确配置提示 |
| 普通用户不能执行群管 | 普通用户发送 `/warn @某人 测试` | 消息日志记录权限不足 | 群内回复权限不足 |
| 管理员群管可用 | 后台系统设置中的管理员发送 `/warn @某人 测试管理警告` 和 `/banword add 测试广告 请不要发广告` | 审计日志记录 `warn` 和 `banword_add` | 命令返回成功，后续命中关键词时返回拦截提示 |
| 白名单外群不响应 | 在非后台群白名单群发送命令 | 日志记录丢弃原因 | 群内无回复，后台不会自动新增该群配置 |
| 后台运行期设置生效 | 在后台修改 API、机器人 QQ/昵称、管理员 QQ、群白名单、限流或命令前缀后，不重启服务直接发消息验证 | 消息日志、审计日志或 LLM 日志体现新配置 | 新配置立即影响路由、权限、触发和限流 |

## 5. 持久化和恢复证据

| 要求 | 操作 | 通过标准 |
| --- | --- | --- |
| 群配置持久化 | 后台添加或修改群配置后执行 `docker compose restart bot-app` | 重启后群配置仍存在，`/ping` 仍可回复 |
| OneBot 可恢复连接 | 执行 `docker compose restart onebot` | OneBot 重新连接，后台状态恢复在线 |
| PostgreSQL 备份可生成 | 执行 `sh scripts/backup.sh` | `data/backups` 下生成 SQL 备份文件 |
| PostgreSQL 可恢复 | 执行 `FORCE=1 sh scripts/restore_postgres.sh ./data/backups/<备份文件名>.sql` 后跑 smoke | Bot Core 健康检查和后台 API 仍可访问，持久数据符合备份状态 |
| 登录态可迁移 | 备份并恢复 `.env` 和 `data/onebot` 后启动服务 | OneBot 能重新上线，真实群可继续收发 |

## 6. MVP 完成判定证据包

MVP 最终完成时，建议保存以下证据：

- `python scripts/check_all.py --pnpm pnpm --with-smoke` 的本地通过输出。
- Linux 服务器上 `python scripts/preflight_check.py --env-file .env --strict` 的通过输出。
- Linux 服务器上 `docker compose ps` 的服务状态。
- Linux 服务器上 `python scripts/mvp_acceptance.py --env-file .env --strict-preflight --require-onebot-online --require-onebot-activity --require-mvp-core-logs --require-admin-lite-audit --skip-onebot-simulation` 的通过输出。
- 真实 QQ 群中 `/ping`、`/help`、`/dice`、`/ai`、@机器人、群管命令的测试记录。
- 后台消息日志、LLM 调用日志、审计日志能查询到对应记录。
- `sh scripts/backup.sh` 和一次恢复演练后的 smoke 通过输出。

只有上述证据同时成立，才可判定 `MVP规格.md` 中的完成定义已经满足。

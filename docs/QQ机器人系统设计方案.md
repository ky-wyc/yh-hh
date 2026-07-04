# 新一代 QQ 群机器人项目参考文档

| 项目 | 内容 |
| --- | --- |
| 文档名称 | 新一代 QQ 群机器人项目参考文档 |
| 文档状态 | 设计基线，已按 MVP、一期、二期拆分 |
| 适用阶段 | 需求确认、架构设计、MVP 开发、部署运维 |
| 目标平台 | Linux 云服务器 |
| 接入方式 | QQ 小号 + OneBot v11 |
| 核心定位 | 聊天、群管、AI、娱乐一体的新一代 QQ 群机器人 |
| 后台 UI 参考 | Daymychen/art-design-pro |
| 阶段文档 | [MVP 规格](MVP规格.md)、[一期产品蓝图](一期产品蓝图.md)、[二期能力池](二期能力池.md) |
| 最后更新 | 2026-07-05 |

## 目录

- [1. 产品定位](#1-产品定位)
- [2. 建设目标](#2-建设目标)
- [3. 范围边界](#3-范围边界)
- [4. 术语定义](#4-术语定义)
- [5. 设计原则](#5-设计原则)
- [6. 总体架构](#6-总体架构)
- [7. 技术选型](#7-技术选型)
- [8. 核心模块设计](#8-核心模块设计)
- [9. Web 管理后台设计](#9-web-管理后台设计)
- [10. 数据模型设计](#10-数据模型设计)
- [11. API 设计](#11-api-设计)
- [12. 消息处理流水线](#12-消息处理流水线)
- [13. Prompt 与人格配置](#13-prompt-与人格配置)
- [14. 主动发言策略](#14-主动发言策略)
- [15. 记忆与知识库策略](#15-记忆与知识库策略)
- [16. 群管安全策略](#16-群管安全策略)
- [17. 权限、审计与风控](#17-权限审计与风控)
- [18. 成本控制与用量统计](#18-成本控制与用量统计)
- [19. 部署与运维](#19-部署与运维)
- [20. 备份与恢复](#20-备份与恢复)
- [21. MVP 范围](#21-mvp-范围)
- [22. MVP 后续规划](#22-mvp-后续规划)
- [23. 风险与约束](#23-风险与约束)
- [24. 验收标准](#24-验收标准)
- [25. 推荐实施顺序](#25-推荐实施顺序)
- [26. 最终推荐方案](#26-最终推荐方案)

## 1. 产品定位

本项目定位为“聊天、群管、AI、娱乐一体的新一代 QQ 群机器人”。

它不是单纯的命令机器人，也不是只会调用大模型的聊天机器人。它是一个面向 QQ 群长期运行的群内智能体，需要同时承担群聊陪伴、秩序维护、知识问答、群活动组织、文字娱乐、消息分析和后台管理等职责。

核心方向：

```text
聊天：自然对话、上下文理解、群内陪伴、问题回答。
群管：规则维护、广告拦截、警告禁言、成员管理、审计记录。
AI：自定义大模型、长期记忆、知识库、群聊总结、智能分析。
娱乐：文字游戏、抽签骰子、接龙、群活动、轻量互动玩法。
后台：可视化配置、权限管理、日志查看、模型和知识库管理。
```

产品目标是让机器人既能“聊得起来”，也能“管得住群”，还能“记得住事”，并且可以通过后台持续配置、扩展和演进。

## 2. 建设目标

本项目目标是构建一个可部署在 Linux 云服务器上、24 小时运行的第三方 QQ 群机器人系统。

机器人使用 QQ 小号通过 OneBot 协议接入 QQ 群消息，支持自定义大模型、群聊问答、群管、文字游戏、长期记忆、知识库、定时任务、群聊分析，并提供网页版后台管理能力。

本方案不采用 QQ 官方机器人接口。当前目标场景要求以 QQ 小号身份接入普通 QQ 群，并接收、分析、回复群内消息。

### 2.1 业务目标

- 降低群管理成本。
- 提高群内问答和信息检索效率。
- 增强群内娱乐和互动能力。
- 支持群聊数据沉淀、总结和分析。
- 支持通过后台进行持续运营和配置。

### 2.2 技术目标

- Linux 云服务器 24 小时运行。
- OneBot 接入实现可替换。
- 大模型服务可自定义。
- 核心能力插件化。
- 数据持久化、可备份、可恢复。
- 后台可视化管理。
- 支持灰度扩展和分阶段上线。

## 3. 范围边界

### 3.1 必须支持

本节描述完整产品目标范围，不等同于 MVP 范围。各阶段实际交付以 [MVP 规格](MVP规格.md)、[一期产品蓝图](一期产品蓝图.md)、[二期能力池](二期能力池.md) 为准。

- QQ 小号接入群聊消息。
- 接收 QQ 群内文本消息。
- 根据命令、@机器人、关键词触发回复。
- 接入可自定义的大模型服务。
- 群内智能聊天问答。
- 群管功能，例如禁言、踢人、警告、关键词拦截。
- 文字游戏，例如猜数字、掷骰子、词语接龙、接龙故事。
- 长期记忆，例如用户偏好、群设定、重要群事件。
- 知识库问答，例如群规、项目文档、FAQ、游戏设定。
- 定时任务，例如每日总结、定时提醒、周期公告。
- 群聊消息分析，例如热门话题、活跃成员、风险消息、每日总结。
- Web 后台管理。
- Docker Compose 部署。

### 3.2 能力分层

```text
基础层：QQ 接入、消息收发、权限、配置、日志、部署。
聊天层：命令问答、@回复、上下文、多轮对话、主动发言。
AI 层：模型适配、Prompt、人设、长期记忆、知识库、总结分析。
群管层：规则、警告、禁言、踢人、广告识别、审计。
娱乐层：骰子、猜数字、词语接龙、故事接龙、文字活动。
后台层：仪表盘、群设置、模型设置、Skill 设置、知识库、日志。
```

### 3.3 第一版暂不覆盖

- 多平台同时接入，例如微信、Telegram、Discord。
- 复杂图像、语音、视频理解。
- 大规模多租户商业 SaaS。
- 完整移动端 App。
- 万人群级别的高并发分布式架构。
- 自动拉人、广告群发、绕过平台限制等高风险行为。

## 4. 术语定义

| 术语 | 定义 |
| --- | --- |
| QQ 小号 | 用于运行机器人的 QQ 账号，加入目标 QQ 群并接收群消息。 |
| OneBot | QQ 机器人生态中的通用协议，用于统一事件接收和 API 调用。 |
| OneBot 实现 | 具体接入程序，例如 Lagrange.OneBot 或 NapCat。 |
| Bot Core | 机器人核心服务，负责消息路由、权限、AI、Skill、后台 API。 |
| Skill | 可插拔能力模块，例如 AI 问答、骰子、知识库、群管。 |
| RAG | Retrieval-Augmented Generation，检索增强生成，用于知识库问答。 |
| 长期记忆 | 机器人沉淀的用户偏好、群设定、稳定事实和重要事件。 |
| 短期上下文 | 当前群聊最近一段消息，用于多轮对话和临时理解。 |
| 主动发言 | 机器人在未被命令或 @ 的情况下，根据群聊上下文主动回复。 |
| 审计日志 | 对后台操作、群管操作、配置变更的不可忽略记录。 |

## 5. 设计原则

### 5.1 协议边界清晰

业务系统只依赖 OneBot 抽象接口，不直接依赖 NapCat 或 Lagrange 的私有能力。

### 5.2 默认保守

机器人默认只响应命令和 @。主动发言、自动群管、长期记忆写入等能力必须可配置、可关闭、可审计。

### 5.3 模块插件化

聊天、群管、游戏、知识库、定时任务都应以 Skill 或独立服务模块组织，避免形成一个难维护的大处理函数。

### 5.4 模型不直接执行高风险操作

大模型可以参与判断和建议，但不能绕过权限系统直接执行踢人、长时间禁言、删除大量数据等操作。

### 5.5 数据可治理

消息、记忆、知识库、日志、任务都应可查询、可删除、可备份、可恢复。敏感信息必须最小化保存。

### 5.6 云端可运维

系统必须具备自动重启、健康检查、日志查看、配置管理、备份恢复和故障排查能力。

### 5.7 MVP 优先闭环

第一版优先验证 QQ 接入、消息收发、基础路由、AI 回复、后台最小配置和 Docker 部署闭环。长期记忆、知识库、群聊分析、复杂群管、完整后台图表等能力可以保留设计，但不得阻塞 MVP 验收。

## 6. 总体架构

```text
QQ 小号
  ↓
OneBot 实现层
Lagrange.OneBot / NapCat
  ↓ WebSocket
Bot Core 服务
  ├─ OneBot 事件接收
  ├─ 消息路由
  ├─ 权限与风控
  ├─ 大模型适配器
  ├─ Skill 插件系统
  ├─ 群管模块
  ├─ 文字游戏模块
  ├─ 长期记忆模块
  ├─ 知识库 RAG 模块
  ├─ 定时任务模块
  ├─ 群聊分析模块
  └─ Web 管理 API
        ↓
      Web 管理后台
```

### 6.1 服务组成

```text
onebot-adapter：QQ 小号协议接入。
bot-app：机器人核心服务和管理 API。
web-admin：后台前端，可独立部署或由 bot-app 托管。
postgres：核心业务数据库。
redis：缓存、限流、短期上下文、任务锁。
vector-store：知识库向量检索，优先 pgvector，后续可切 Qdrant。
nginx：可选，用于 HTTPS、反向代理和静态资源服务。
```

### 6.2 OneBot 接入边界

Bot Core 必须通过内部适配器调用 OneBot 能力。MVP 阶段固定采用 OneBot 反向 WebSocket：Bot Core 暴露 `/onebot/ws`，OneBot 实现主动连接 Bot Core。正向 WebSocket 可作为后续兼容模式，但第一版不同时支持两种连接模式，避免部署和重连逻辑复杂化。

```text
OneBotAdapter
  ├─ start()
  ├─ stop()
  ├─ accept_connection()
  ├─ normalize_event(raw_event) -> BotEvent
  ├─ build_dedup_key(event) -> string
  ├─ send_action(action, params) -> ActionResult
  ├─ send_group_message(group_id, message)
  ├─ send_private_message(user_id, message)
  ├─ mute_user(group_id, user_id, duration)
  ├─ kick_user(group_id, user_id)
  ├─ get_group_list()
  ├─ get_group_member_info(group_id, user_id)
  ├─ get_capabilities()
  └─ health_check()
```

内部标准事件 `BotEvent` 至少包含：

```text
event_id
self_id
platform
event_type
message_type
onebot_message_id
group_id
user_id
nickname
raw_text
segments
raw_event_json
received_at
```

运行时实现预案：

- `Lagrange.OneBot`：优先用于 Linux 服务端部署。
- `NapCat`：作为兼容实现和备选方案。
- `MockAdapter`：用于本地测试和自动化测试。

要求：

- 业务模块不能直接调用 NapCat/Lagrange 特有 API。
- OneBot 实现差异、事件字段差异、错误码差异由 Adapter 层消化。
- 所有发送动作必须返回结构化结果，包含成功状态、OneBot 返回码、错误信息和重试建议。
- 后台展示当前接入实现、连接状态、最近断线时间。
- 切换 OneBot 实现时，不影响大模型、Skill、记忆、知识库和后台配置。

### 6.3 推荐架构定案

MVP 阶段采用“模块化单体”架构，不在第一版拆分微服务。

推荐定案：

```text
QQ 接入：Lagrange.OneBot 优先，NapCat 备用。
协议边界：OneBot v11。
连接方式：MVP 固定反向 WebSocket。
后端：Python + FastAPI + asyncio。
后台：Vue 3 + Vite + TypeScript + Element Plus + Tailwind CSS。
后台风格：参考 Daymychen/art-design-pro。
数据库：PostgreSQL。
缓存：Redis。
向量检索：一期知识库使用 pgvector，后续可切 Qdrant。
部署：Docker Compose。
```

模块化单体内部结构建议：

```text
app/
  adapters/onebot/
  core/router/
  core/permissions/
  llm/
  skills/
  games/
  memory/
  knowledge/
  scheduler/
  analytics/
  admin_api/
```

选择该方案的原因：

- 第一版优先保证稳定接消息、稳定发消息、稳定配置、稳定部署。
- 模块化单体比微服务更容易开发、调试和部署。
- 内部模块边界清晰，后续可按压力和复杂度拆分服务。
- OneBot、LLM、知识库和后台 UI 都保留替换空间。

## 7. 技术选型

### 7.1 QQ 接入层

统一使用 OneBot v11 协议作为业务系统边界。

候选实现：

- `Lagrange.OneBot`：适合 Linux 服务端部署，偏服务化。
- `NapCat`：生态活跃，OneBot 兼容性较好。

### 7.2 后端服务

推荐技术：

- Python 3.11+
- FastAPI
- asyncio
- SQLAlchemy 2.x
- Alembic
- Pydantic Settings
- APScheduler 或 Celery Beat

选择理由：

- Python 对大模型、RAG、任务调度、数据处理生态成熟。
- FastAPI 可同时承载 Bot Core API 和 Web 后台 API。
- asyncio 适合 OneBot WebSocket 长连接和异步大模型调用。

### 7.3 Web 后台

推荐技术：

- Vue 3
- Vite
- TypeScript
- Element Plus
- Tailwind CSS
- Pinia
- TanStack Query
- ECharts

后台 UI 风格参考 `Daymychen/art-design-pro`。该项目采用 Vue 3、Vite、TypeScript、Element Plus 和 Tailwind CSS，适合作为本项目后台管理端的视觉、布局和交互参考。

后台属于管理工具，优先追求清晰、稳定、信息密度和表单能力。若开发周期允许，建议直接基于该类管理模板搭建后台骨架，而不是从零搭建导航、布局、主题和通用表格表单。

### 7.4 数据层

推荐组合：

- PostgreSQL：核心业务数据、配置、长期记忆、日志、任务。
- Redis：短期上下文、限流、锁、在线状态、临时游戏状态。
- pgvector：一期知识库阶段向量检索。
- Qdrant：后续知识库规模扩大后的独立向量库选项。

### 7.5 大模型接入

采用 OpenAI-compatible 接口抽象。

配置项：

```text
LLM_PROVIDER
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_TEMPERATURE
LLM_MAX_TOKENS
LLM_TIMEOUT_SECONDS
```

可接入：

- OpenAI-compatible 云模型。
- DeepSeek。
- 通义千问兼容接口。
- 智谱兼容接口。
- 硅基流动。
- 本地 vLLM。
- 本地 Ollama 代理。

## 8. 核心模块设计

### 8.1 OneBot 接入模块

职责：

- 建立 OneBot WebSocket 连接。
- 接收群消息、私聊消息、通知事件。
- 调用 OneBot API 发送消息、禁言、踢人。
- 断线自动重连。
- 记录连接状态。

关键接口：

```text
connect()
send_group_message(group_id, message)
send_private_message(user_id, message)
mute_user(group_id, user_id, duration)
kick_user(group_id, user_id)
get_group_list()
get_group_member_info(group_id, user_id)
```

### 8.2 消息路由模块

职责：

- 解析群消息。
- 判断是否需要响应。
- 分发到命令、Skill、大模型、群管、游戏模块。
- 维护最近上下文。

触发方式：

以下为完整产品可支持的触发方式。MVP 实际启用范围以 [MVP 规格](MVP规格.md) 为准。

```text
/ai 问题
@机器人 问题
/help
/dice 2d6
/guess start
关键词触发
后台配置的自动回复规则
```

回复模式：

```text
disabled：禁用本群机器人。
command_only：只响应命令。
mention_only：响应命令和 @。
active：允许根据上下文主动插话。
admin_only：仅管理员可使用。
```

### 8.3 大模型模块

职责：

- 统一调用不同大模型。
- 维护系统提示词。
- 组装短期上下文、长期记忆和知识库检索结果。
- 处理超时、重试、错误降级。
- 统计 token、成本和响应时间。

MVP 阶段只接入短期上下文和基础模型调用，不启用长期记忆和知识库检索。长期记忆和知识库接口可以预留，但不阻塞 MVP 验收。

回答流程：

```text
用户消息
  ↓
权限与限流检查
  ↓
获取短期上下文
  ↓
检索长期记忆
  ↓
检索知识库
  ↓
构造 Prompt
  ↓
调用大模型
  ↓
输出过滤与长度控制
  ↓
发送群回复
```

### 8.4 Skill 插件系统

Skill 是机器人能力扩展的基本单位。

每个 Skill 包含：

```text
name：技能名。
description：说明。
permissions：权限要求。
enabled_by_default：是否默认启用。
config_schema：配置项。
handle(ctx, args)：处理函数。
```

Skill 分期：

```text
MVP：
- help：展示可用命令。
- ping：健康响应。
- ai：大模型问答。
- dice：掷骰子。
- admin-lite：管理员手动警告和关键词拦截。

一期：
- guess：猜数字。
- kb：知识库问答。
- remind：提醒。
- summary：群聊总结。
- admin：基础群管增强。

二期：
- wordchain：词语接龙。
- story：故事接龙。
- activity：群活动。
- advanced-admin：群管规则引擎。
```

启用策略：

- 全局启用或禁用。
- 按群启用或禁用。
- 按角色限制。
- 后台可配置。

### 8.5 群管模块

命令示例：

```text
/warn @用户 原因
/mute @用户 10m 原因
/unmute @用户
/kick @用户 原因
/banword add 关键词
/banword remove 关键词
/rule
/setrule 群规内容
```

自动群管策略：

- 广告关键词检测。
- 链接检测。
- 重复刷屏检测。
- 敏感词检测。
- 新人欢迎。
- 警告累计后自动禁言。

### 8.6 文字游戏模块

游戏分期：

```text
MVP：
- 掷骰子。

一期：
- 猜数字。
- 持久游戏状态。

二期：
- 词语接龙。
- 群内故事接龙。
- 文字战斗。
- 群活动报名。
```

游戏状态按群隔离：

```text
group_id
game_type
state_json
started_by
status
created_at
updated_at
```

规则：

- 一个群同一时间默认只开一个主要游戏。
- 游戏命令不能触发大模型长回复。
- 游戏状态定期清理。

### 8.7 长期记忆模块

长期记忆分三类：

```text
user_memory：用户记忆。
group_memory：群记忆。
event_memory：事件记忆。
```

记忆写入来源：

- 用户明确说“记住”。
- 管理员后台手动新增。
- 每日总结提取稳定事实。
- 群配置变化自动写入。

删除方式：

- `/forget` 命令。
- 后台删除。
- 过期时间自动清理。
- 管理员批量清理。

### 8.8 知识库模块

知识库用于回答固定资料类问题。

资料来源：

- 后台手动新增文本。
- 上传 Markdown、TXT、PDF、Word。
- 导入网页内容。
- 导入群规、FAQ、项目文档。

处理流程：

```text
文档上传
  ↓
文本抽取
  ↓
分块
  ↓
生成 embedding
  ↓
存储向量
  ↓
用户提问时检索
  ↓
结合大模型回答
```

### 8.9 定时任务模块

任务类型：

- 一次性提醒。
- 每日提醒。
- 每周提醒。
- Cron 表达式任务。
- 系统维护任务。

命令示例：

```text
/remind 20:00 记得打卡
/schedule daily 09:00 早安
/tasks
/task cancel 123
```

系统内置任务：

- 每日群聊总结。
- 每日记忆压缩。
- 清理过期上下文。
- 清理过期游戏状态。
- 数据库备份。
- 健康检查。

### 8.10 群聊分析模块

分析维度：

- 今日消息数。
- 活跃成员。
- 热门关键词。
- 主要话题。
- 情绪倾向。
- 广告或争吵风险。
- 机器人回复次数。
- 大模型调用次数。
- 未回答问题。

命令：

```text
/summary today
/summary week
/analyze today
/hot
```

## 9. Web 管理后台设计

### 9.1 UI 风格基线

后台管理端参考 `Daymychen/art-design-pro` 的现代管理后台风格。

风格要求：

- 整体采用清爽、现代、信息密度适中的后台布局。
- 支持侧边栏导航、顶部状态栏、面包屑、标签页或多页签。
- 支持亮色和暗色主题。
- 首页仪表盘突出运行状态、消息量、模型调用量和异常信息。
- 表格、筛选、表单、弹窗、抽屉和详情页保持统一交互。
- 配置类页面以表单为主，日志和分析类页面以表格、图表为主。
- 高风险操作使用确认弹窗，并展示操作后果。
- 移动端只需基础可用，优先保证桌面端管理体验。

设计参考：

```text
项目：Daymychen/art-design-pro
定位：现代化后台管理模板
技术：Vue 3 + Vite + TypeScript + Element Plus + Tailwind CSS
用途：后台布局、主题、表格、表单、图表和交互风格参考
```

### 9.2 页面结构

```text
登录页
仪表盘
群管理
大模型设置
Skill 管理
群管设置
知识库管理
长期记忆管理
定时任务
群聊分析
日志中心
系统设置
```

### 9.3 仪表盘

展示：

- Bot 在线状态。
- OneBot 连接状态。
- 今日接收消息数。
- 今日发送消息数。
- 今日大模型调用次数。
- 当前启用群数量。
- 最近错误日志。
- 最近 24 小时消息趋势。

### 9.4 群管理

能力：

- 查看群列表。
- 启用或禁用群。
- 设置回复模式。
- 设置群管理员。
- 设置群命令前缀。
- 设置群限流。
- 查看群成员摘要。
- 查看群最近分析。

### 9.5 大模型设置

能力：

- 修改 Base URL。
- 修改 API Key。
- 修改模型名。
- 修改温度。
- 修改最大输出长度。
- 修改系统提示词。
- 测试模型调用。
- 查看模型调用日志。

API Key 只能写入和重置，不在后台明文展示。

### 9.6 Skill 管理

能力：

- 查看 Skill 列表。
- 全局启用或禁用 Skill。
- 按群启用或禁用 Skill。
- 修改 Skill 配置。
- 查看 Skill 调用统计。

### 9.7 群管设置

能力：

- 管理敏感词。
- 管理广告关键词。
- 配置刷屏阈值。
- 配置自动禁言规则。
- 配置新人欢迎语。
- 查看群管审计日志。

### 9.8 知识库管理

能力：

- 新增知识库。
- 上传文档。
- 编辑文档。
- 删除文档。
- 重新向量化。
- 检索测试。
- 设置知识库适用群。

### 9.9 长期记忆管理

能力：

- 查看用户记忆。
- 查看群记忆。
- 新增记忆。
- 修改记忆。
- 删除记忆。
- 查看记忆来源。
- 审核待确认记忆。
- 执行记忆压缩。

### 9.10 定时任务

能力：

- 新建任务。
- 暂停任务。
- 恢复任务。
- 删除任务。
- 查看执行历史。
- 查看失败原因。

### 9.11 日志中心

日志类型：

- 消息日志。
- 大模型调用日志。
- 群管审计日志。
- 系统错误日志。
- 定时任务日志。
- 登录日志。

## 10. 数据模型设计

### 10.1 核心表

```text
users
- id
- qq_id
- nickname
- status
- created_at
- updated_at

groups
- id
- qq_group_id
- name
- enabled
- reply_mode
- config_json
- created_at
- updated_at

group_admins
- id
- group_id
- user_id
- role

group_members
- id
- group_id
- user_id
- card_name
- nickname
- role
- joined_at
- last_seen_at

messages
- id
- event_id
- self_id
- platform
- onebot_message_id
- group_id
- user_id
- message_type
- content
- segments_json
- raw_event_json
- raw_event_hash
- dedup_key
- discard_reason
- created_at

bot_replies
- id
- group_id
- user_id
- trigger_type
- input_message_id
- content
- skill_name
- llm_model
- send_status
- onebot_result_json
- created_at

skills
- id
- name
- enabled
- config_json

group_skills
- id
- group_id
- skill_name
- enabled
- config_json

memories
- id
- scope_type
- scope_id
- memory_type
- content
- importance
- confidence
- source
- source_message_id
- review_status
- expires_at
- last_used_at
- usage_count
- created_at
- updated_at

knowledge_documents
- id
- title
- content
- source_type
- scope_type
- scope_id
- status
- created_at
- updated_at

knowledge_chunks
- id
- document_id
- chunk_text
- embedding
- embedding_model
- embedding_dim
- metadata_json
- created_at

scheduled_tasks
- id
- task_type
- scope_type
- scope_id
- cron_expr
- payload_json
- enabled
- next_run_at
- created_at
- updated_at

task_runs
- id
- task_id
- status
- started_at
- finished_at
- error_message
- result_json

game_sessions
- id
- group_id
- game_type
- state_json
- status
- started_by
- created_at
- updated_at

audit_logs
- id
- actor_user_id
- actor_role
- target_user_id
- group_id
- action
- target_type
- target_id
- before_json
- after_json
- detail_json
- result
- ip_address
- user_agent
- created_at

llm_usage_logs
- id
- group_id
- user_id
- skill_name
- provider
- model
- prompt_tokens
- completion_tokens
- estimated_cost
- latency_ms
- status
- created_at

admin_users
- id
- username
- password_hash
- role
- status
- last_login_at
- created_at
- updated_at

admin_sessions
- id
- admin_user_id
- token_hash
- expires_at
- ip_address
- user_agent
- created_at
```

### 10.2 数据保存原则

- 原始消息按配置保存，支持关闭或缩短保留周期。
- 长期记忆只保存稳定事实，不保存所有聊天。
- 知识库保存原文和分块结果。
- 审计日志不可由普通管理员删除。
- 敏感字段不明文写入日志。
- `messages.dedup_key` 必须有唯一约束，防止 OneBot 重连或重放导致重复响应。
- `users.qq_id`、`groups.qq_group_id`、`skills.name` 应建立唯一约束。
- 使用 pgvector 时，`knowledge_chunks.embedding` 直接保存向量；切换 Qdrant 时，该字段可替换为外部向量 ID。

## 11. API 设计

### 11.1 认证

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

认证要求：

- 后台账户必须保存密码哈希，不保存明文密码。
- 登录接口必须有 IP 和用户名维度限流。
- 推荐使用 HttpOnly、Secure、SameSite Cookie 保存会话；如使用 JWT，必须支持过期和服务端撤销。
- 所有写接口必须校验管理员角色和 CSRF 或同等防护。
- API Key、访问令牌、登录态等敏感字段只能写入、重置和脱敏展示。

### 11.2 仪表盘

```text
GET /api/dashboard/overview
GET /api/dashboard/metrics
GET /api/dashboard/recent-errors
```

### 11.3 群管理

```text
GET    /api/groups
GET    /api/groups/{group_id}
PATCH  /api/groups/{group_id}
GET    /api/groups/{group_id}/admins
POST   /api/groups/{group_id}/admins
DELETE /api/groups/{group_id}/admins/{user_id}
```

### 11.4 大模型配置

```text
GET   /api/settings/llm
PATCH /api/settings/llm
POST  /api/settings/llm/test
```

### 11.5 Skill 管理

```text
GET   /api/skills
PATCH /api/skills/{skill_name}
GET   /api/groups/{group_id}/skills
PATCH /api/groups/{group_id}/skills/{skill_name}
```

### 11.6 知识库

```text
GET    /api/kb/documents
POST   /api/kb/documents
POST   /api/kb/documents/upload
GET    /api/kb/documents/{document_id}
PATCH  /api/kb/documents/{document_id}
DELETE /api/kb/documents/{document_id}
POST   /api/kb/search
POST   /api/kb/reindex
```

### 11.7 记忆

```text
GET    /api/memories
POST   /api/memories
PATCH  /api/memories/{memory_id}
DELETE /api/memories/{memory_id}
POST   /api/memories/{memory_id}/approve
POST   /api/memories/{memory_id}/reject
```

### 11.8 定时任务

```text
GET    /api/tasks
POST   /api/tasks
PATCH  /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
GET    /api/tasks/{task_id}/runs
```

### 11.9 群聊分析

```text
GET /api/analytics/groups/{group_id}/summary
GET /api/analytics/groups/{group_id}/topics
GET /api/analytics/groups/{group_id}/members
GET /api/analytics/groups/{group_id}/risk-messages
```

### 11.10 系统与审计

```text
GET /api/system/health
GET /api/system/onebot-status
GET /api/system/logs
GET /api/audit-logs
GET /api/usage/llm
```

## 12. 消息处理流水线

所有群消息统一进入消息处理流水线，避免功能之间互相抢消息或重复回复。流水线分为公共前置阶段和按意图执行阶段，不能把所有消息都固定送入记忆、知识库和大模型。

```text
接收 OneBot 事件
  ↓
事件标准化
  ↓
消息去重
  ↓
群白名单检查
  ↓
用户权限检查
  ↓
限流检查
  ↓
群策略检查
  ↓
意图识别
  ↓
生成执行计划
  ├─ command：直接执行命令 Skill
  ├─ game_action：进入游戏状态机
  ├─ admin_action：权限校验后执行群管动作
  ├─ kb_question：检索知识库后按需调用大模型
  ├─ mention_chat：检索上下文、记忆、知识库后调用大模型
  ├─ keyword_trigger：命中规则后直接回复或转 Skill
  └─ passive_observe：仅记录和分析，不公开回复
  ↓
输出安全检查
  ↓
发送回复或记录不回复原因
  ↓
记录日志和统计
```

意图类型：

```text
command：显式命令。
mention_chat：@机器人聊天。
keyword_trigger：关键词触发。
admin_action：群管操作。
game_action：文字游戏操作。
kb_question：知识库问题。
passive_observe：只记录和分析，不回复。
active_reply_candidate：主动发言候选。
```

约束：

- 一条消息默认最多触发一次公开群回复。
- 高风险操作必须经过权限模块。
- 大模型不是所有消息的默认入口，只有需要时才调用。
- 所有被丢弃的消息应记录丢弃原因，方便排查。
- `/dice`、`/guess`、`/ping`、`/help` 等确定性命令不得调用大模型。
- 执行计划必须可测试，MockAdapter 应能覆盖路由、限流、去重和发送失败场景。

## 13. Prompt 与人格配置

机器人需要支持多层 Prompt，而不是只有一个全局系统提示词。

Prompt 层级：

```text
global_persona：全局人格。
group_persona：群级人格。
skill_prompt：Skill 专用提示词。
kb_prompt：知识库问答提示词。
moderation_prompt：群管分析提示词。
summary_prompt：群聊总结提示词。
game_prompt：文字游戏主持提示词。
```

优先级：

```text
系统安全约束
  > 全局人格
  > 群级人格
  > Skill 专用 Prompt
  > 当前消息上下文
```

后台需要支持：

- 修改全局人格。
- 为不同群配置不同人格。
- 预览最终组合 Prompt。
- 恢复默认 Prompt。
- 查看 Prompt 修改历史。

设计原则：

- 群管 Prompt 与聊天 Prompt 分离。
- 知识库问答要求优先引用资料，不确定时说明不知道。
- 娱乐 Skill 可以更活泼，但不能绕过安全约束。
- Prompt 修改必须写入审计日志。

## 14. 主动发言策略

主动发言用于增强群聊存在感，但默认必须保守开启。

触发条件：

```text
群回复模式为 active。
机器人最近没有频繁发言。
当前话题与机器人能力相关。
模型判断有明确帮助价值。
群内没有正在进行的高优先级游戏或群管事件。
```

限制项：

```text
每群主动发言冷却时间。
每群每日主动发言上限。
每用户连续触发上限。
置信度阈值。
夜间静默时段。
管理员一键暂停。
```

默认策略：

- 新群默认不开启主动发言。
- MVP 只支持命令和 @ 回复。
- 主动发言需要后台按群开启。
- 主动发言结果必须记录触发原因。

后台配置：

- 是否开启主动发言。
- 冷却时间。
- 每日上限。
- 触发关键词。
- 静默时间段。
- 最近主动发言记录。

## 15. 记忆与知识库策略

### 15.1 长期记忆可信度

长期记忆必须有来源、可信度和审核状态。

建议字段：

```text
confidence：可信度，0 到 1。
source_type：来源类型，用户声明/管理员录入/模型提取/系统生成。
source_message_id：来源消息。
created_by：创建者。
review_status：pending/approved/rejected。
last_used_at：最近使用时间。
usage_count：被使用次数。
```

写入规则：

- 管理员后台录入的记忆可直接 approved。
- 用户明确要求“记住”的内容可直接写入，但仍保留来源。
- 模型自动提取的记忆默认 pending 或低可信度。
- 涉及个人隐私、敏感身份、攻击性标签的内容不得自动写入。

使用规则：

- 默认只使用 approved 记忆。
- 低可信度记忆只作为弱参考。
- 回答中不能暴露私密记忆的来源细节。
- 用户和管理员可以删除相关记忆。

### 15.2 知识库作用域

知识库必须按作用域隔离，避免 A 群资料影响 B 群回答。

作用域：

```text
global：全局知识库。
group：群知识库。
user：用户私有知识库。
game：游戏设定知识库。
admin：群管规则知识库。
```

检索优先级：

```text
当前群知识库
  > 当前游戏/活动知识库
  > 用户私有知识库
  > 全局知识库
  > 大模型常识
```

回答要求：

- 能从知识库回答时，优先基于知识库。
- 知识库没有依据时，必须说明资料中没有找到。
- 后台可配置是否允许模型使用常识补充。
- 重要回答应附带知识来源标题或片段编号。

## 16. 群管安全策略

群管功能必须遵循“规则执行，模型建议”的原则。

可直接执行：

- 明确关键词命中的拦截规则。
- 明确刷屏阈值命中的临时禁言。
- 管理员手动命令。
- 黑名单命中。

需要确认或只建议：

- 模型判断的广告嫌疑。
- 模型判断的争吵风险。
- 模型建议踢人。
- 长时间禁言。
- 涉及多个用户的大规模处理。

高风险操作：

```text
kick：踢人。
mute_long：长时间禁言。
blacklist：加入黑名单。
delete_memory：删除大量记忆。
change_group_policy：修改群策略。
```

高风险操作要求：

- 只有 `super_admin` 或 `group_admin` 可执行。
- 必须记录审计日志。
- 必须包含原因。
- 可配置二次确认。
- 模型不能绕过权限直接执行。

## 17. 权限、审计与风控

### 17.1 角色模型

```text
super_admin：系统超级管理员。
group_admin：群级机器人管理员。
trusted_user：可信用户。
normal_user：普通用户。
blocked_user：黑名单用户。
```

### 17.2 风控能力

- 群白名单。
- 用户黑名单。
- 命令级权限控制。
- 每群每分钟回复上限。
- 每用户每分钟调用上限。
- 大模型调用限流。
- 敏感操作二次确认。
- 自动群管操作审计。

### 17.3 后台操作审计

审计范围：

```text
登录和登出。
修改大模型配置。
修改 Prompt。
启用或关闭主动发言。
修改群回复模式。
修改群管规则。
新增、修改、删除知识库。
新增、修改、删除长期记忆。
新增、暂停、删除定时任务。
手动执行禁言、踢人、警告。
导出或恢复数据。
```

审计字段：

```text
actor_id：操作者。
actor_role：操作者角色。
action：操作类型。
target_type：目标类型。
target_id：目标 ID。
before_json：修改前。
after_json：修改后。
ip_address：来源 IP。
user_agent：客户端信息。
created_at：操作时间。
```

要求：

- API Key 等敏感字段不能明文进入审计日志。
- 审计日志普通管理员不可删除。
- 后台需要按时间、操作者、操作类型筛选。

## 18. 成本控制与用量统计

限制维度：

```text
全局每日 token 上限。
每群每日 token 上限。
每用户每日 token 上限。
每 Skill 调用上限。
主动发言 token 上限。
高成本模型权限限制。
```

统计指标：

```text
请求次数。
输入 token。
输出 token。
估算费用。
平均响应时间。
失败次数。
超时次数。
按群统计。
按用户统计。
按 Skill 统计。
```

降级策略：

- 达到用户额度时，提示稍后再试。
- 达到群额度时，仅允许管理员继续调用。
- 达到全局额度时，关闭非必要 AI 功能。
- 模型失败时，返回简短错误，不重复刷屏。
- 可配置备用模型。

后台需要提供：

- 今日用量。
- 本月用量。
- 各群排行。
- 各 Skill 用量。
- 成本估算。
- 额度配置。

## 19. 部署与运维

### 19.1 Docker Compose 服务

```text
services:
  bot-app:
    image: qqbot-app
    restart: always
    env_file: .env
    depends_on:
      - postgres
      - redis

  onebot:
    image: lagrange-onebot-or-napcat
    restart: always
    depends_on:
      - bot-app
    volumes:
      - ./data/onebot:/app/data

  postgres:
    image: postgres:16
    restart: always
    volumes:
      - ./data/postgres:/var/lib/postgresql/data

  redis:
    image: redis:7
    restart: always

  nginx:
    image: nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
```

### 19.2 服务器要求

- Linux 云服务器。
- 2 核 CPU 起步。
- 2 GB 内存起步，推荐 4 GB。
- 20 GB 磁盘起步。
- 固定公网 IP。
- Docker 和 Docker Compose。

### 19.3 运行保障

- 容器 `restart: always`。
- OneBot 自动重连 Bot Core，Bot Core 记录连接状态和最近断线原因。
- OneBot 登录态持久化。
- 日志按天滚动。
- 数据库定时备份。
- 健康检查接口。
- 后台显示连接状态。
- MVP 使用 PostgreSQL + pgvector，不启动 Qdrant；二期需要独立向量库时再加入 qdrant 服务。
- OneBot 容器需要配置反向 WebSocket 地址，指向 `ws://bot-app:8000/onebot/ws`。

### 19.4 配置示例

```text
APP_ENV=production
APP_SECRET_KEY=change-me
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-me

ONEBOT_CONNECTION_MODE=reverse_ws
ONEBOT_REVERSE_WS_PATH=/onebot/ws
ONEBOT_REVERSE_WS_URL=ws://bot-app:8000/onebot/ws
ONEBOT_ACCESS_TOKEN=

DATABASE_URL=postgresql+asyncpg://qqbot:password@postgres:5432/qqbot
REDIS_URL=redis://redis:6379/0
VECTOR_BACKEND=pgvector

LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=change-me
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=1000

DEFAULT_REPLY_MODE=mention_only
DEFAULT_COMMAND_PREFIX=/
```

## 20. 备份与恢复

备份对象：

```text
PostgreSQL 数据库。
Redis 关键持久状态。
知识库原文。
向量库数据。
.env 配置模板。
OneBot 登录态。
上传文件。
后台配置。
```

备份策略：

- PostgreSQL 每日自动备份。
- 知识库文档和上传文件每日增量备份。
- 配置变更后生成配置快照。
- OneBot 登录态定期备份，但需要限制访问权限。
- 备份文件保留最近 7 天和每月快照。

恢复流程：

```text
停止 bot-app。
恢复 PostgreSQL。
恢复知识库文件和向量数据。
恢复 OneBot 登录态。
启动 onebot。
启动 bot-app。
执行健康检查。
后台确认连接状态和消息收发。
```

要求：

- 后台展示最近一次备份时间。
- 备份失败需要通知管理员。
- 恢复流程要有文档。
- 敏感备份文件不能放在公开目录。

## 21. MVP 范围

第一阶段目标是跑通完整闭环，而不是一次性做完所有高级能力。详细范围以 [MVP 规格](MVP规格.md) 为准。

### 21.1 MVP 功能

- OneBot 反向 WebSocket 接入。
- QQ 群消息接收。
- 群白名单。
- `/help`、`/ping`。
- `@机器人` 和 `/ai` 调用自定义大模型。
- `/dice` 掷骰子。
- 基础群管最小集：管理员手动警告、关键词拦截。
- PostgreSQL 保存群、用户、消息摘要、配置。
- Redis 保存短期上下文和限流状态。
- Web 后台最小集：登录、连接状态、群开关、模型设置、日志查看。
- Docker Compose 部署。

### 21.2 MVP 不做

- 长期记忆：一期实现，见 [一期产品蓝图](一期产品蓝图.md)。
- 知识库问答：一期实现，见 [一期产品蓝图](一期产品蓝图.md)。
- 每日群聊总结：一期实现，见 [一期产品蓝图](一期产品蓝图.md)。
- `/guess` 等需要持久游戏状态的玩法：一期实现，见 [一期产品蓝图](一期产品蓝图.md)。
- 自动禁言、踢人和模型判定群管：一期后段或二期实现，见 [一期产品蓝图](一期产品蓝图.md) 与 [二期能力池](二期能力池.md)。
- 文件知识库、PDF/Word 解析、Qdrant、复杂分析、多模型路由、插件市场：二期能力池，见 [二期能力池](二期能力池.md)。

## 22. MVP 后续规划

MVP 后续分为一期和二期，不再把所有非 MVP 能力笼统称为“以后做”。

### 22.1 一期：长期运营能力

详见 [一期产品蓝图](一期产品蓝图.md)。

一期目标是把机器人从“能跑通闭环”推进到“可长期运营”，主要包括：

- 长期记忆最小版本。
- 知识库最小版本。
- 每日总结和定时任务。
- `/guess` 和持久游戏状态。
- 后台一期增强。
- 基础群管增强。
- 审计、权限和日志补齐。

### 22.2 二期：增强和规模化能力

详见 [二期能力池](二期能力池.md)。

二期能力按实际使用反馈排序，不要求一次性全部实现，主要包括：

- 文件知识库上传和 PDF、Word、Markdown 解析。
- pgvector 和 Qdrant 可切换。
- 自动记忆提取和记忆压缩。
- 群聊情绪、风险分析和后台图表。
- 更完整的群管规则引擎和操作回滚。
- 词语接龙、故事接龙、文字战斗等复杂玩法。
- 多模型路由、模型调用成本统计和额度治理。
- 插件市场式 Skill 管理。

## 23. 风险与约束

### 23.1 QQ 小号风险

使用第三方小号接入可能存在：

- 登录态失效。
- 协议变化导致不可用。
- 账号风控。
- 账号封禁。
- OneBot 实现兼容差异。

缓解：

- 业务代码只依赖 OneBot。
- OneBot 实现可替换。
- 限制回复频率。
- 避免刷屏。
- 避免自动拉人、广告、骚扰行为。
- 保留人工接管能力。

### 23.2 大模型风险

风险：

- 幻觉。
- 敏感内容。
- 成本失控。
- 长上下文导致响应慢。

缓解：

- 系统提示词约束。
- 输出长度限制。
- 按群和用户限流。
- 知识库引用优先。
- 高风险群管操作不由模型直接执行。

### 23.3 数据隐私风险

群聊消息、用户记忆、知识库可能包含敏感信息。

缓解：

- 后台登录保护。
- API Key 不明文展示。
- 数据库定期备份和访问限制。
- 记忆可删除。
- 只保存必要数据。

## 24. 验收标准

本节是完整产品验收清单。MVP 的验收以 [MVP 规格](MVP规格.md) 为准；一期和二期能力分别以阶段文档中的验收项为准。

### 24.1 接入验收

- Bot 可在 Linux 云服务器运行。
- OneBot 反向 WebSocket 连接断开后可自动重连。
- 可接收指定 QQ 群文本消息。
- 可向指定 QQ 群发送消息。
- 后台能看到 OneBot 在线状态。

### 24.2 聊天与 AI 验收

- `/ai` 可调用自定义大模型。
- `@机器人` 可触发回答。
- 未配置 API Key 时有明确错误提示。
- 单群和单用户限流生效。
- 大模型调用日志可查询。

### 24.3 群管验收

- 管理员可执行警告、禁言等操作。
- 普通用户不能执行管理命令。
- 群管操作写入审计日志。
- 高风险操作不能由模型直接执行。

### 24.4 娱乐验收

- `/dice` 可掷骰子。
- `/guess start` 可启动猜数字。
- 游戏状态按群隔离。
- 游戏状态可过期清理。

### 24.5 记忆与知识库验收

- 可新增、查看、删除长期记忆。
- 待审核记忆不会默认参与回答。
- 可在后台新增知识库文本。
- 知识库问答能返回基于资料的回答。
- 群知识库不会污染其他群。

### 24.6 后台验收

- 后台需要登录。
- 可查看仪表盘。
- 可配置群开关和回复模式。
- 可配置大模型参数。
- 可启用或禁用 Skill。
- 可查看日志和审计记录。

### 24.7 部署验收

- Docker Compose 可一键启动核心服务。
- 容器异常退出后可自动重启。
- 数据库存储目录持久化。
- 备份任务可执行。
- 健康检查接口可访问。

## 25. 推荐实施顺序

```text
第 1 步：确定 OneBot 实现，跑通 Linux 服务器登录和反向 WebSocket 连接。
第 2 步：实现 Bot Core 的 OneBot 事件标准化、去重和消息发送。
第 3 步：实现消息路由、群白名单、/help、/ping。
第 4 步：接入 OpenAI-compatible 大模型，实现 @ 和 /ai。
第 5 步：接入 PostgreSQL、Redis，保存群、用户、消息摘要、限流状态。
第 6 步：实现基础 Skill 系统、/dice 和最小群管能力。
第 7 步：实现 Web 后台 MVP：登录、连接状态、群开关、模型设置、日志。
第 8 步：Docker Compose 部署、健康检查和最小备份。
第 9 步：补齐审计、权限细化和后台体验。
第 10 步：实现长期记忆。
第 11 步：实现知识库最小版本。
第 12 步：增加群聊总结、分析、复杂游戏和定时任务。
```

## 26. 最终推荐方案

最终推荐采用：

```text
Lagrange.OneBot 或 NapCat
+ OneBot v11
+ Python FastAPI Bot Core
+ Vue 3 Web Admin，参考 Daymychen/art-design-pro 风格
+ PostgreSQL
+ Redis
+ pgvector 或 Qdrant
+ Docker Compose
+ OpenAI-compatible LLM Adapter
```

该方案满足当前目标：

- 不依赖官方 QQ Bot。
- 使用 QQ 小号接入普通群聊。
- 可云端 24 小时运行。
- 支持自定义大模型。
- 支持聊天、群管、文字游戏。
- 支持长期记忆和知识库。
- 支持定时任务和群聊分析。
- 支持 Web 后台管理配置。

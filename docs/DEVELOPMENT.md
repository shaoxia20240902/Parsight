# XLSX-to-BI 开发文档

> 本文档描述当前代码库的**真实实现**。修改功能后请同步更新本文档与 `docs/README.md` 索引。

---

## 1. 产品能力概览

| 模块 | 路由 | 说明 |
|------|------|------|
| XLSX 管理 | `/data` | 上传、表浏览、单表 **AI 六维理解**（Markdown） |
| XLSX 关联 | `/data/relations` | 空间级 **跨表关联分析**（Markdown） |
| BI 看板 | `/bi` | 进入页仅查状态；在 `BIDashboard` 内手动触发生成 |
| Chat | `/chat` | 快速问答 |
| 管理 | `/admin` | 用户管理（管理员） |

**已移除（勿再引用）**：`/api/analysis/*`、文件级 `global_summary` / `relationships` JSON、旧 RelationsView 关系图、Mock 兜底。

---

## 2. 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3、FastAPI、SQLAlchemy（async）、MySQL |
| 前端 | Vue 3、Vite、Pinia、Element Plus、marked、ECharts |
| LLM | 管理端启用的 OpenAI 兼容 API（`AGENT_BACKEND=local`） |
| 数据导入 | 全列 `TEXT`，避免类型推断错误 |

---

## 3. 目录结构

```
xlsx-to-bi/
├── backend/
│   ├── app/
│   │   ├── agents/          # LLM Agent（understanding、relations、bi、chat…）
│   │   ├── models/          # ORM + migrate_db
│   │   ├── routers/         # API 路由
│   │   ├── services/        # db_service、llm_client、*_verification
│   │   └── utils/           # data_sampler、sql_validator
│   ├── data/                # MySQL、上传文件
│   └── run.py
├── frontend/src/
│   ├── api/                 # data.ts（数据/理解/关联）、index.ts（BI/Chat）、space.ts
│   ├── views/               # DataView、RelationsView、BIView、ChatView…
│   └── components/          # BIDashboard、ChartCard、UploadProgress…
└── docs/                    # 本文档目录
```

---

## 4. 核心数据流

### 4.1 动态表命名

上传时动态表名格式：

```
{用户名}_{空间seq_id}_{Sheet名}
```

- `用户名`：登录用户 `username`，经 `sanitize_name` 处理
- `空间seq_id`：`spaces.seq_id` 全局自增整数（非 UUID）
- `Sheet名`：Excel 工作表名，经 `sanitize_name` 处理

示例：`zhangsan_3_销售明细`

实现：`app/services/xlsx_parser.py` → `build_table_name()`。上传前必须选择空间。

### 4.2 上传 → 入库 → 轻量分析

```
POST /api/upload/stream
  → XlsxParser（全 TEXT 建表）
  → run_post_upload_analysis（异步任务）
       ├── LocalSheetSummaryAgent → sheet_meta.summary 等
       ├── TableUnderstandingAgent → sheet_meta.understanding_content
       └── 文件状态 → understanding_ready（不再自动生成 BI）

POST /api/bi/generate/{file_id}
  → 门禁：各表 understanding 就绪，否则 409
  → BIBusinessGenerator v3 → file_records.bi_config
```

跨表关联**不在上传时生成**，由用户在「XLSX 关联」页触发。

> **BI v3**（见 `docs/BI_ADVANCED_OPTIMIZATION.md`）：上传后异步六维理解（`understanding_ready`）；`POST /api/bi/generate` 需理解就绪否则 409；生成路径为总览→角色→场景→问题→审视→SQL，失败单图修复一次后丢弃。

### 4.3 单表理解（六维 Markdown）

```
GET /api/data/table/{table}/understanding?regenerate=
  → 无缓存：TableUnderstandingAgent（前10+随机90行+表头）
  → save_understanding_draft（初稿 = 终稿展示）
  → BackgroundTasks: run_understanding_verification
       ├── 提取异议字段 → SELECT DISTINCT
       └── 修订后 save_understanding_verified（保留 content_initial）
```

前端 `DataView`：单卡片 Markdown、核对 badge、3s 轮询、`核对前/核对后` 切换。

### 4.4 空间跨表关联

```
GET /api/data/relations?space_id=&regenerate=
  → 前置：各 Sheet 已有 understanding_content
  → build_space_relations_context（每表随机20行 + 单表理解）
  → RelationsAnalysisAgent → save_space_relations_draft
  → BackgroundTasks: run_relations_verification（JOIN SQL 核对）
```

前端 `RelationsView`：与理解页同风格，支持初稿/终稿对比。

---

## 5. 数据模型

### 5.1 `spaces`

| 字段 | 说明 |
|------|------|
| `id` | UUID，API 与外键使用 |
| `seq_id` | 自增整数，用于短表名（全局唯一） |
| `relations_content` | 跨表关联终稿（Markdown） |
| `relations_content_initial` | 核对前初稿 |
| `relations_verification_status` | `idle` \| `verifying` \| `completed` \| `failed` |
| `relations_updated_at` | 更新时间 |

### 5.2 `sheet_meta`

| 字段 | 说明 |
|------|------|
| `summary`, `key_dimensions`, `key_metrics`… | 上传后 Sheet 短总结（Chat/BI/关联上下文） |
| `understanding_content` | 六维理解终稿（Markdown） |
| `understanding_content_initial` | 核对前初稿 |
| `understanding_verification_status` | 核对状态 |
| `understanding_updated_at` | 更新时间 |

### 5.3 `file_records`

| 字段 | 说明 |
|------|------|
| `status` | `uploaded` / `analyzing` / `analyzed` / `error` |
| `bi_config` | BI 看板 JSON 配置 |
| `bi_thinking_journal` | BI 生成思考过程（自然语言条目数组，供前端搜索展示） |
| `space_id` | 所属空间 |

> 历史库可能仍存在已废弃列 `global_summary`、`relationships` 等，ORM 不再映射。

### 5.4 迁移

`backend/app/models/database.py` → `migrate_db()` 在启动时 `ALTER TABLE` 补列。

---

## 6. API 一览

### 6.1 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录，返回 JWT |

### 6.2 空间

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/spaces` | 空间列表 |
| POST | `/api/spaces` | 创建空间 |
| DELETE | `/api/spaces/{id}` | 删除 |
| PUT | `/api/spaces/{id}/active` | 切换当前空间 |

### 6.3 上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 同步上传（测试用） |
| POST | `/api/upload/stream` | **推荐** SSE 进度上传 |
| POST | `/api/upload/validate-reimport` | 更新前校验 Sheet/字段名（form: `file`, `space_id`） |
| POST | `/api/upload/reimport/stream` | **更新导入** SSE（form: `file`, `space_id`, `mode=overwrite\|insert`） |
| GET | `/api/files` | 文件列表 |

### 6.4 数据表

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data/tables?space_id=` | 空间下动态表 |
| GET | `/api/data/table/{name}/columns` | 列信息 |
| GET | `/api/data/table/{name}/rows` | 分页 + 搜索 |
| GET | `/api/data/export?space_id=` | 导出空间全部 Sheet 为 XLSX |

### 6.5 单表理解

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data/table/{name}/understanding?regenerate=` | 获取/生成理解 |
| PUT | `/api/data/table/{name}/understanding` | 保存用户编辑 |

**GET 响应**：

```json
{
  "content": "终稿 Markdown",
  "content_initial": "初稿或 null",
  "is_cached": true,
  "updated_at": "ISO8601",
  "verification_status": "idle|verifying|completed|failed"
}
```

### 6.6 空间关联

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/data/relations?space_id=&regenerate=` | 跨表关联 Markdown |

响应字段同理解接口（`content` / `content_initial` / `verification_status`）。

### 6.7 BI

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/bi/status/{file_id}` | 查询 BI 生成状态（只读）：`completed` / `none` / `blocked` |
| GET | `/api/bi/thinking/{file_id}?q=` | BI 生成思考过程（自然语言，可搜索） |
| POST | `/api/bi/generate/{file_id}` | 手动生成 BI 配置（SSE，需六维理解就绪，否则 409） |
| GET | `/api/bi/config/{file_id}` | 获取已生成配置（404 表示尚未生成） |
| POST | `/api/bi/chart-data` | 图表数据 |
| GET | `/api/bi/filter-options/{file_id}` | 筛选选项 |
| POST | `/api/bi/categories` | 新增自定义分类 |
| PATCH | `/api/bi/categories/{category_id}` | 修改自定义分类名称 |
| DELETE | `/api/bi/categories/{category_id}` | 删除自定义分类 |
| PATCH | `/api/bi/charts/{chart_id}` | 修改图表元数据（`title` / `description` / `category_id`），不调用 LLM |
| POST | `/api/bi/regenerate-chart` | 单图重生成 |

### 6.8 管理（管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/users` | 用户列表 |
| POST | `/api/admin/users` | 创建用户（自动创建默认空间） |
| DELETE | `/api/admin/users/{user_id}` | 删除用户及其空间、文件、动态表（不可删自己或其他管理员） |

### 6.9 Chat

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/quick-qa` | 快速问答；LLM 不可用（如余额不足 HTTP 402）时返回 **503**，`detail` 为可读错误文案 |
| POST | `/api/chat/deep-research` | 深度调研（SSE） |
| GET | `/api/chat/history` | 历史 |
| POST | `/api/chat/confirm-keyword` | 关键词确认 |
| POST | `/api/chat/dashboard-build` | 看板构建 |
| POST | `/api/chat/dashboard-layout` | 看板布局 |

---

## 7. Agent 清单（当前）

| 标识 | 类 | 用途 |
|------|-----|------|
| `sheet_summary` | `LocalSheetSummaryAgent` | 上传后 Sheet 短总结 |
| `keyword_confirm` | `LocalKeywordConfirmAgent` | Chat 关键词 |
| `role_decomposition` | `LocalRoleDecompositionAgent` | 深度调研角色 |
| `sub_question_selector` | `LocalSubQuestionSelectorAgent` | 子问题筛选 |
| `sql_generator` | `LocalSQLGeneratorAgent` | SQL 生成 |
| `chart_generator` | `LocalChartGeneratorAgent` | 图表配置 |
| `report_generator` | `LocalReportGeneratorAgent` | 报告 |
| `quick_qa` | `LocalQuickQAAgent` | 快速问答 |
| `dashboard_builder` | `LocalDashboardBuilderAgent` | 看板构建 |
| `dashboard_layout` | `LocalDashboardLayoutAgent` | 看板布局 |
| — | `TableUnderstandingAgent` | 单表六维理解 |
| — | `RelationsAnalysisAgent` | 空间跨表关联 |
| — | `BIClassificationAgent` | BI 图表分类 |

**已删除**：`LocalGlobalAnalysisAgent`（原 Agent B 文件级 JSON 关联）。

工厂：`agent_factory.py`，仅 `AGENT_BACKEND=local`；`shenzhou` 未对接。

---

## 8. 前端页面与 API 映射

| 页面 | 主要 API |
|------|----------|
| `DataView.vue` | `uploadFileStream`, `validateReimport`, `reimportFileStream`, `exportSpaceData`, `getTables`, `getTableRows`, `getTableUnderstanding`, `saveTableUnderstanding` |
| `RelationsView.vue` | `getRelations(spaceId, regenerate)` |
| `BIView.vue` | `listFiles`, `getBIStatus`；有文件则渲染 `BIDashboard`（不自动 `generate`） |
| `ChatView.vue` | `quickQA`, `getChatHistory` |
| `AdminView.vue` | `listUsers`, `createUser`, `deleteUser`（`api/admin.ts`） |

**localStorage**：`xlsx-bi-active-space`、`xlsx-bi-token`。

---

## 9. 环境变量

见 `backend/.env.example`。关键项：

| 变量 | 说明 |
|------|------|
| `AGENT_BACKEND` | `local`（唯一可用） |
| **LLM API / 模型** | **不在 `.env` 配置**；在管理后台「LLM 配置」创建并启用（`api_base`、`api_key`、`primary_model`、`alt_model` 均必填）。启动时加载 `is_active=true` 的记录到进程内存，无启用项时 AI 调用直接失败 |
| `LLM_MAX_TOKENS` / `LLM_TEMPERATURE` | 可选，控制单次调用 token 与温度 |
| `SAMPLE_FIRST_N` / `SAMPLE_RANDOM_N` | 理解采样（config.py） |
| `RELATIONS_RANDOM_SAMPLE_N` | 关联采样每表行数（默认 20） |

---

## 10. 开发规范

1. **禁止 Mock/兜底**：见 `.cursor/rules/no-fallback.mdc`
2. **前端 UI**：见项目根 `CLAUDE.md`（Apple 极简风格）
3. **导入数据**：一律 TEXT，见 `data_sampler._infer_type`
4. **文档同步**：见 `.cursor/rules/sync-docs.mdc`
5. **BI 排查日志**（开发阶段）：
   - `backend/logs/bi_pipeline.log` — 流水线步骤与错误（`step=`、`run_id`、`table_name`、角色/场景/问题 ID）
   - `backend/logs/ai_calls.log` — LLM 请求/响应全文
   - 单次生成在 `generation_report.pipeline_run_id` 与日志 `run_id` 对齐，便于 `grep run_id` 串联

---

## 11. 本地启动

```bash
# 后端
cd backend && pip install -r requirements.txt
cp .env.example .env   # 配置 DASHSCOPE_API_KEY
python run.py

# 前端
cd frontend && npm install && npm run dev
```

或使用 `./start.sh`。

---

## 12. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-15 | 初版：Markdown 理解/关联 + 核对流水线；移除旧 analysis 路由与文件级 JSON 关联；整理本文档 |
| 2026-05-15 | 动态表名改为 `{username}_{space.seq_id}_{sheet}`；`spaces` 新增 `seq_id` |
| 2026-05-15 | 管理页用户删除 API；AdminView 暖色 UI 与析见品牌统一 |
| 2026-05-15 | Data 页导出/更新文件：字段校验、覆盖/插入、更新后可选重新生成表理解 |
| 2026-05-16 | 新增 `docs/INSIGHT_MODULE.md`：洞察/深度洞察/BI 的 Agent 调用链、提示词与并发设计 |
| 2026-05-16 | BI 仓库图表支持编辑标题/说明/分类；新增 `PATCH /api/bi/charts/{chart_id}` |
| 2026-05-16 | 新增 `docs/BI_ADVANCED_OPTIMIZATION.md`：BI 现状梳理、多视角/KPI 优化方案（待实施） |
| 2026-05-16 | 新增 `docs/BI_VISION.md`；重写 `BI_ADVANCED_OPTIMIZATION.md`：六维理解门禁、角色→问题→图、LLM 定视角、自定义宽表 1～3（待实施） |
| 2026-05-16 | BI 方案补充：Sheet 总览 KPI、角色→场景→问题→问题审视→SQL（见 `BI_VISION.md` / `BI_ADVANCED_OPTIMIZATION.md`） |
| 2026-05-16 | BI 方案补充：单图 SQL/空结果修复智能体，仅重试 1 次，失败丢弃该图（待实施） |
| 2026-05-16 | **落地 BI v3**：`bi_pipeline_agents`、`bi_sql_builder`、理解门禁、上传解耦 BI、`BIChartRepairAgent` |
| 2026-05-16 | BI LLM 输入改为完整 `understanding_content` + 全量 `fields`（不截断）；提高各 Agent `max_tokens` |
| 2026-05-16 | BI 蓝图改为分步流水线（选角→场景→问题→审视）；`analysis_type` 业务自由命名，SQL 用 `sql_template_hint` 映射 |
| 2026-05-16 | BI 流水线专用日志 `backend/logs/bi_pipeline.log`（`bi_pipeline_logger`）；`generation_report.pipeline_run_id` 关联单次生成 |
| 2026-05-16 | 修复 `MetricSpecCompiler._resolve_fields` 缺失；新增 `GET /api/bi/status`；BI 页进入仅查状态、手动生成 |
| 2026-05-16 | BI 生成 UI（Claude 风格）：图表轮播 + 思考文案；`bi_thinking_journal` 入库；`GET /api/bi/thinking` |
| 2026-05-25 | 快速问答：移除 LLM 失败静默兜底；402/401/403 不重试；失败返回 HTTP 503 |
| 2026-05-25 | LLM 运行时仅使用管理端已启用配置（地址/Key/主备模型），移除 `.env` 与 `model_override` 兜底 |
| 2026-05-25 | 修复 `LLMClient` 构造时读取配置导致后端无法启动（登录代理 ETIMEDOUT）；改为每次调用前解析管理端配置 |
| 2026-05-25 | BI 生成体验：`categories_ready` 后进入分阶段看板（`BIStagedGeneratingBoard`）；分析文案最多 3 行滚动；Sheet 图表规划与分类执行改为 `asyncio.gather` 并发 |
| 2026-05-25 | 修复推荐问题生成误写 `file_records.status=generating_recommendations`（超长）：改用 `recommended_questions_status`；`GET /api/files` 返回该字段 |

<!-- 新增变更请在上方表格追加一行，格式：| YYYY-MM-DD | 简要说明 | -->

# XLSX-to-BI 文档索引

> **维护约定**：任何功能、API、数据模型、Agent 或前端页面有改动时，必须同步更新下表对应文档。详见仓库根目录 `.cursor/rules/sync-docs.mdc`。

| 文档 | 用途 | 何时更新 |
|------|------|----------|
| [DEVELOPMENT.md](./DEVELOPMENT.md) | **主文档**：架构、数据模型、API、AI 流水线、前端路由 | 改后端/前端功能时 **必更** |
| [BI_DASHBOARD_MODULE.md](./BI_DASHBOARD_MODULE.md) | **BI 看板专项**：前端状态模型、公共筛选、Sheet/自定义分类、多 Agent 生成流水线、提示词设计 | 改 BI 看板、BI Agent、图表 SQL、筛选或仓库逻辑时 |
| [BI_VISION.md](./BI_VISION.md) | **BI 产品愿景**（自然语言）：角色→问题→图表、理解门禁、自定义宽表 | 产品/业务对齐「要什么」 |
| [BI_ADVANCED_OPTIMIZATION.md](./BI_ADVANCED_OPTIMIZATION.md) | **BI 深度优化**（开发版）：流水线、Agent、模板、分期实施 | 开发 BI 生成逻辑时 |
| [INSIGHT_MODULE.md](./INSIGHT_MODULE.md) | **洞察模块**：Chat 洞察/深度洞察、Agent 调用链与实施切片 | 改 Chat 洞察/深度洞察或对接逻辑时 |
| [PROJECT_VALUE.md](./PROJECT_VALUE.md) | **项目价值说明**：开源意义、工程范围、后续方向 | 申请开源支持、更新项目定位或维护路线时 |
| [SECURITY_AND_API_USAGE.md](./SECURITY_AND_API_USAGE.md) | **安全与 API 使用计划**：Codex Security 需求、API 额度用途 | 更新安全边界、模型调用或申请材料时 |
| [OPEN_SOURCE_GRANT_NOTES.md](./OPEN_SOURCE_GRANT_NOTES.md) | **开源支持申请补充说明**：面向 grant / credits / maintainer support 的简明说明 | 申请开源开发者支持时 |
| [../README.md](../README.md) | 快速开始、技术栈概览 | 启动方式或技术栈变化时 |
| [../backend/.env.example](../backend/.env.example) | 环境变量说明 | 新增/删除/重命名 env 时 |
| [../../.cursor/rules/no-fallback.mdc](../../.cursor/rules/no-fallback.mdc) | 禁止 Mock/兜底 | 仅当错误处理策略变化时 |
| [../../CLAUDE.md](../../CLAUDE.md) | 前端 UI 设计规范 | 仅当视觉/组件规范变化时 |

**文档版本**：与代码同步维护，以 `DEVELOPMENT.md` 文末「变更记录」为准。

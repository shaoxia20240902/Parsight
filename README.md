# Parsight / 析见

<p align="center">
  <img src="./frontend/public/logo-full.svg" alt="Parsight" width="120" />
</p>

<p align="center">
  面向 XLSX 数据分析的智能 BI 应用。上传 Excel 后，AI 自动完成单表理解、跨表关联、看板生成与自然语言问答。
</p>

<p align="center">
  <a href="https://github.com/shaoxia20240902/Parsight">GitHub</a> ·
  <a href="https://shaoxia20240902.github.io/Parsight/">官网</a> ·
  <a href="./docs/README.md">文档</a>
</p>

---

## 核心能力

- **XLSX 上传与解析**：自动识别 Sheet 结构、字段类型并写入 MySQL。
- **AI 单表理解**：六维业务理解，输出 Markdown 报告并支持异议核对。
- **跨表关联分析**：空间级多表关系发现，生成可核对的 SQL。
- **自动 BI 看板**：自动推荐指标、维度与图表，生成可交互看板。
- **自然语言问答**：快速洞察、深度研究、BI Builder 三种对话模式。
- **空间与后台管理**：多空间隔离、LLM 配置、用户与日志管理。

## 技术栈

- **后端**：FastAPI、SQLAlchemy、MySQL、Pandas、OpenPyXL
- **前端**：Vue 3、Vite、Element Plus、Pinia、ECharts
- **AI**：本地 Agent 编排，支持 DeepSeek / DashScope 等 LLM

## 快速开始

需要：MySQL、Python 3.10+、Node.js 18+。

```bash
git clone https://github.com/shaoxia20240902/Parsight.git
cd Parsight/backend && cp .env.example .env
# 编辑 backend/.env：配置 DATABASE_URL 与 JWT_SECRET_KEY
cd .. && ./start.sh
```

启动后：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8007`
- API 文档：`http://localhost:8007/docs`

默认管理员账号为 `admin`，首次启动密码见后端日志（或在 `.env` 中设置 `ADMIN_INITIAL_PASSWORD`）。登录后请在 **管理后台 → LLM 配置** 启用一条模型配置，AI 功能方可正常使用。

## 配置摘要

| 变量 | 必需 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | MySQL 连接串，例如 `mysql+aiomysql://root:密码@127.0.0.1:3306/xlsx_to_bi?charset=utf8mb4` |
| `JWT_SECRET_KEY` | 是 | 长度 ≥ 32 位的随机字符串，用于登录 Token 签名 |
| `ADMIN_INITIAL_PASSWORD` | 否 | 管理员初始密码；不设置时系统会生成一次性随机密码 |
| `CORS_ALLOW_ORIGINS` | 否 | 多来源用英文逗号分隔，生产环境必须显式配置 |
| `OSS_*` | 否 | 可选的阿里云 OSS 配置 |

完整环境变量说明见 [`backend/.env.example`](./backend/.env.example)。

## 项目结构

```text
Parsight/
├── backend/     # FastAPI 后端、Agent、数据服务
├── frontend/    # Vue 3 前端
├── docs/        # 架构文档与官网落地页
├── mock_data/   # 示例 XLSX 数据
└── start.sh     # 一键启动脚本
```

## 文档

- [docs/README.md](./docs/README.md) — 文档索引
- [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md) — 架构、API 与开发规范
- [docs/PROJECT_VALUE.md](./docs/PROJECT_VALUE.md) — 项目价值与开源方向

## 贡献

欢迎 Fork 并提交 Pull Request。提交信息建议遵循 [Conventional Commits](https://www.conventionalcommits.org/)，前端代码遵循 [`CLAUDE.md`](./CLAUDE.md) 设计规范。

Built by [shaoxia20240902](https://github.com/shaoxia20240902).

## License

[MIT License](./LICENSE)

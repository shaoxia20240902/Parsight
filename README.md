# Parsight

Parsight 是一个面向 XLSX 数据分析的智能 BI 应用。用户上传 Excel 文件后，系统会自动解析入库，并通过 AI 完成单表理解、跨表关联分析、看板生成和自然语言问答。

## 功能

- XLSX 文件上传、结构解析与数据入库
- 单表六维理解，支持 Markdown 结果与异议核对
- 空间级多表关联分析，支持 SQL 核对
- 自动生成 BI 图表看板
- 基于业务数据的自然语言问答
- 管理后台、空间切换与数据浏览

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL、Pandas、OpenPyXL
- 前端：Vue 3、Vite、Element Plus、Pinia、ECharts、marked
- AI：DashScope / 阿里云百炼，本地 Agent 编排模式

## 项目结构

```text
Parsight/
├── backend/              # FastAPI API、Agent、数据服务
│   ├── app/
│   ├── tests/
│   └── requirements.txt
├── frontend/             # Vue 3 前端应用
│   ├── src/
│   ├── public/
│   └── package.json
├── docs/                 # 架构、BI、Agent、开发文档
├── mock_data/            # 示例 XLSX 数据
├── start.sh              # 一键启动脚本
├── start-backend.sh      # 后端启动脚本
└── start-frontend.sh     # 前端启动脚本
```

## 快速开始

### 1. 准备后端配置

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`，至少配置以下内容：

```bash
DASHSCOPE_API_KEY=你的 DashScope API Key
DATABASE_URL=mysql+aiomysql://root:your-password@127.0.0.1:3306/xlsx_to_bi?charset=utf8mb4
JWT_SECRET_KEY=change-this-to-a-random-string
```

### 2. 启动服务

推荐使用一键启动脚本：

```bash
./start.sh
```

也可以分别启动前后端：

```bash
./start-backend.sh   # http://localhost:8000
./start-frontend.sh  # http://localhost:3000
```

启动后访问：

- 前端：http://localhost:3000
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

默认管理员账号为 `admin` / `123456`，首次启动时自动创建。

## 页面

| 页面 | 路径 | 能力 |
|------|------|------|
| XLSX 管理 | `/data` | 上传、表数据、单表六维理解（Markdown + 异议核对） |
| XLSX 关联 | `/data/relations` | 空间级跨表关联（Markdown + SQL 核对） |
| BI | `/bi` | 自动图表看板 |
| Chat | `/chat` | 快速问答 |
| 管理后台 | `/admin` | 用户、空间与系统管理 |

## 测试

后端完整流程测试：

```bash
cd backend
python tests/test_full_flow.py
```

前端构建检查：

```bash
cd frontend
npm install
npm run build
```

## 文档

| 文档 | 说明 |
|------|------|
| [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md) | 主开发文档：架构、API、数据模型、Agent |
| [docs/BI_DASHBOARD_MODULE.md](./docs/BI_DASHBOARD_MODULE.md) | BI 看板专项：公共筛选、分类模型、并发生成流水线、提示词设计 |
| [docs/INSIGHT_MODULE.md](./docs/INSIGHT_MODULE.md) | Chat 洞察/深度洞察：调用链、实施切片、待确认问题 |
| [docs/README.md](./docs/README.md) | 文档索引与维护约定 |

代码变更时请同步更新对应文档。

## 开源声明 / Open Source

Parsight 基于 **MIT License** 开源，欢迎自由使用、修改、分发和商业应用。

我们采用**共创协作**模式：

- 任何人都可以 Fork 本项目并提交 Pull Request
- 核心维护者负责 Code Review 和合并决策
- 贡献者将在 CONTRIBUTORS 中得到署名认可
- 欢迎通过 Issue 提交功能建议、Bug 报告和使用反馈

### 如何贡献 / Contributing

1. **Fork** 本仓库到你的 GitHub 账号
2. 创建特性分支：`git checkout -b feature/your-feature-name`
3. 提交你的修改：`git commit -m "feat: add your feature"`
4. 推送到你的 Fork：`git push origin feature/your-feature-name`
5. 向本仓库提交 **Pull Request**，描述修改内容和目的
6. 核心维护者将 Review 并合并你的贡献

### 协作规范

- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式
- 代码变更需同步更新对应文档（`docs/` 目录）
- 前端需遵循 `CLAUDE.md` 中的 Apple 极简设计规范
- PR 描述中请附上测试说明或截图

## License

本项目基于 [MIT License](./LICENSE) 开源。


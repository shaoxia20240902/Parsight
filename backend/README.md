# Parsight Backend

FastAPI 后端，负责 XLSX 解析、数据入库、AI Agent 编排、BI 生成与 API 服务。

## 环境

- Python 3.10+
- MySQL 5.7+

## 启动

```bash
cd backend
cp .env.example .env
# 编辑 .env，至少配置 DATABASE_URL 与 JWT_SECRET_KEY
pip install -r requirements.txt
python run.py
```

服务默认运行在 `http://localhost:8007`，API 文档见 `/docs`。

## 测试

```bash
python -c "from app.main import app"
```

完整项目说明见 [../README.md](../README.md)。

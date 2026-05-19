#!/bin/bash

# 后端服务启动脚本
# 功能：杀掉占用端口的进程，启动 FastAPI 服务，支持热重载

set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;31m'
NC='\033[0m'

# 配置
PORT=${SERVER_PORT:-8007}
HOST="0.0.0.0"
BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)/backend"

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  后端服务启动脚本${NC}"
echo -e "${GREEN}================================${NC}"

# 进入后端目录
cd "$BACKEND_DIR"

# 杀掉占用端口的进程
echo -e "${GREEN}[1/4] 检查端口 $PORT...${NC}"
PID=$(lsof -ti:$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo -e "${YELLOW}端口 $PORT 被进程 $PID 占用，正在终止...${NC}"
    kill -9 $PID 2>/dev/null || true
    sleep 1
    echo -e "${GREEN}进程已终止${NC}"
else
    echo -e "${GREEN}端口 $PORT 可用${NC}"
fi

# 激活虚拟环境（如果存在）
echo -e "${GREEN}[2/4] 检查虚拟环境...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}虚拟环境已激活${NC}"
else
    echo -e "${YELLOW}未找到虚拟环境，使用系统 Python${NC}"
fi

# 安装依赖
echo -e "${GREEN}[3/4] 检查依赖...${NC}"
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
    echo -e "${GREEN}依赖已安装${NC}"
fi

# 启动服务
echo -e "${GREEN}[4/4] 启动 FastAPI 服务...${NC}"
echo ""
echo -e "${GREEN}服务地址: http://$HOST:$PORT${NC}"
echo -e "${GREEN}API 文档: http://$HOST:$PORT/docs${NC}"
echo -e "${GREEN}按 Ctrl+C 停止服务${NC}"
echo ""

# 使用 uvicorn 启动，reload=True 支持文件更改自动重启
python -m uvicorn app.main:app \
    --host $HOST \
    --port $PORT \
    --reload \
    --reload-dir app

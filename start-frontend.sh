#!/bin/bash

# 前端服务启动脚本
# 功能：安装依赖并启动 Vite 开发服务器

set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;31m'
NC='\033[0m'

# 配置
PORT=3000
FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)/frontend"

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  前端服务启动脚本${NC}"
echo -e "${GREEN}================================${NC}"

# 进入前端目录
cd "$FRONTEND_DIR"

# 检查 package.json
if [ ! -f "package.json" ]; then
    echo -e "${YELLOW}错误：未找到 package.json${NC}"
    exit 1
fi

# 检查 node 和 npm
echo -e "${GREEN}[1/3] 检查 Node.js 环境...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${YELLOW}错误：未安装 Node.js${NC}"
    exit 1
fi

echo -e "${GREEN}Node.js 版本: $(node -v)${NC}"
echo -e "${GREEN}npm 版本: $(npm -v)${NC}"

# 安装依赖
echo -e "${GREEN}[2/3] 检查并安装依赖...${NC}"
if [ ! -d "node_modules" ]; then
    echo -e "${GREEN}安装依赖中...${NC}"
    npm install
else
    echo -e "${GREEN}依赖已安装${NC}"
fi

# 启动开发服务器
echo -e "${GREEN}[3/3] 启动 Vite 开发服务器...${NC}"
echo ""
echo -e "${GREEN}前端地址: http://localhost:$PORT${NC}"
echo -e "${GREEN}按 Ctrl+C 停止服务${NC}"
echo ""

npm run dev

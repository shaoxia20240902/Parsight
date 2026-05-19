#!/bin/bash

# XLSX to BI 项目启动脚本
# 功能：自动杀掉占用端口的进程，启动后端服务，支持文件更改自动重启

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 后端配置
BACKEND_PORT=${SERVER_PORT:-8007}
BACKEND_HOST="0.0.0.0"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 杀掉占用指定端口的进程
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)

    if [ -n "$pid" ]; then
        log_warn "端口 $port 被进程 $pid 占用，正在终止..."
        kill -9 $pid 2>/dev/null || true
        sleep 1
        log_info "进程 $pid 已终止"
    else
        log_info "端口 $port 未被占用"
    fi
}

# 启动后端服务
start_backend() {
    log_info "启动后端服务..."

    cd "$BACKEND_DIR"

    # 杀掉占用端口的进程
    kill_port $BACKEND_PORT

    # 检查 Python 虚拟环境
    if [ -d "venv" ]; then
        log_info "激活虚拟环境..."
        source venv/bin/activate
    fi

    # 检查依赖
    if [ -f "requirements.txt" ]; then
        log_info "检查并安装依赖..."
        pip install -q -r requirements.txt
    fi

    # 启动服务（uvicorn 已配置 reload=True，会自动监听文件变化）
    log_info "后端服务启动中... http://$BACKEND_HOST:$BACKEND_PORT"
    python run.py &
    BACKEND_PID=$!

    # 等待服务启动
    sleep 2

    # 检查服务是否成功启动
    if kill -0 $BACKEND_PID 2>/dev/null; then
        log_info "后端服务启动成功 (PID: $BACKEND_PID)"
    else
        log_error "后端服务启动失败"
        exit 1
    fi
}

# 启动前端服务
start_frontend() {
    log_info "检查前端项目..."

    cd "$FRONTEND_DIR"

    # 检查是否有 package.json
    if [ -f "package.json" ]; then
        log_info "启动前端服务..."

        # 检查 node_modules
        if [ ! -d "node_modules" ]; then
            log_info "安装前端依赖..."
            npm install
        fi

        npm run dev &
        FRONTEND_PID=$!

        sleep 3

        if kill -0 $FRONTEND_PID 2>/dev/null; then
            log_info "前端服务启动成功 (PID: $FRONTEND_PID)"
            log_info "前端地址: http://localhost:3000"
        else
            log_warn "前端服务启动失败"
        fi
    else
        log_warn "前端项目未初始化（缺少 package.json）"
    fi
}

# 清理函数
cleanup() {
    log_info "正在停止服务..."

    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
        log_info "后端服务已停止"
    fi

    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
        log_info "前端服务已停止"
    fi

    exit 0
}

# 注册清理函数
trap cleanup SIGINT SIGTERM

# 主函数
main() {
    echo "=========================================="
    echo "  XLSX to BI 智能看板 - 启动脚本"
    echo "=========================================="
    echo ""

    # 启动后端
    start_backend

    # 启动前端
    start_frontend

    echo ""
    echo "=========================================="
    log_info "所有服务已启动"
    log_info "后端: http://localhost:$BACKEND_PORT"
    log_info "按 Ctrl+C 停止所有服务"
    echo "=========================================="

    # 等待子进程
    wait
}

# 执行主函数
main "$@"

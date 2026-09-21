#!/bin/bash
set -e

echo "🚀 MuYiMusic 环境初始化脚本"
echo "================================"

# 检查 Node.js 版本
echo "📦 检查 Node.js 版本..."
NODE_VERSION=$(node --version)
echo "当前 Node.js 版本: $NODE_VERSION"

# 检查 Python 版本
echo "🐍 检查 Python 环境..."
if command -v conda &> /dev/null; then
    echo "Conda 已安装"
    if conda env list | grep -q "muyimusic"; then
        echo "✅ muyimusic conda 环境已存在"
    else
        echo "❌ 请先创建 muyimusic conda 环境"
        echo "   conda create -n muyimusic python=3.12"
        exit 1
    fi
else
    echo "❌ 未检测到 Conda"
    exit 1
fi

# 启用 Corepack 并安装依赖
echo "📦 安装前端依赖..."
corepack enable
pnpm install

# 后端依赖检查
echo "🔧 检查后端依赖..."
cd services/api
conda run --no-capture-output -n muyimusic uv sync
cd ../..

# 复制环境变量模板
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件并填入实际配置"
else
    echo "✅ .env 文件已存在"
fi

# 初始化数据库（如果 Docker 已运行）
if docker ps | grep -q postgres; then
    echo "🗄️  数据库容器运行中，执行迁移..."
    cd services/api
    conda run --no-capture-output -n muyimusic alembic upgrade head
    cd ../..
else
    echo "ℹ️  数据库容器未运行，跳过迁移"
fi

echo ""
echo "✅ 环境初始化完成！"
echo ""
echo "下一步："
echo "  1. 编辑 .env 文件（如尚未配置）"
echo "  2. 启动本地环境: pnpm deploy:local"
echo "  3. 前端开发: pnpm dev:admin 或 pnpm dev:weapp"
echo "  4. 后端开发: cd services/api && conda run -n muyimusic python -m uvicorn app.main:app --reload --port 8001"

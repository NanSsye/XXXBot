#!/bin/bash
set -e

# 启动Redis服务
echo "启动Redis服务..."
redis-server /etc/redis/redis.conf --daemonize yes

# 等待Redis服务启动
echo "等待Redis服务可用..."
sleep 2

# 检查并确保3000端口可用
echo "检查终端服务端口..."
if nc -z localhost 3000; then
    echo "警告：端口3000已被占用，尝试终止占用进程..."
    kill -9 $(lsof -t -i:3000) 2>/dev/null || true
    sleep 1
fi

# 启动WeTTy终端服务 - 使用/wetty作为基础路径
echo "启动WeTTy终端服务..."
wetty --port 3000 --host 0.0.0.0 --allow-iframe --base /wetty --command /bin/bash &

# 等待WeTTy服务启动
echo "等待WeTTy服务可用..."
sleep 3

# 注释: 不再单独启动管理后台服务器，由main.py统一管理
# 管理后台将由main.py自动启动，使用main_config.toml中配置的端口

# 启动主应用
echo "启动XXXBot主应用..."
exec python main.py

# 保持容器运行
wait
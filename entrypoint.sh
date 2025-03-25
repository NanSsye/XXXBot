#!/bin/bash
# 启动Redis服务
redis-server /etc/redis/redis.conf --daemonize yes
# 启动管理后台服务器
python admin/run_server.py --host 0.0.0.0 --port 8080 &
# 执行主程序
exec python main.py
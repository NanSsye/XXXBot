"""
Docker环境下的启动脚本

此脚本用于在Docker环境中启动微信API服务器、代理服务器和机器人
"""

import os
import sys
import asyncio
import threading
import time
import subprocess
from loguru import logger

# 导入必要的模块
from WechatAPI.Extensions.proxy_server import start_proxy_server
import bot_core

# 配置日志
logger.add("logs/docker_start.log", rotation="10 MB", level="INFO")

async def start_proxy():
    """启动代理服务器"""
    logger.info("启动微信API代理服务器")
    
    # 从环境变量或配置文件获取端口
    target_port = int(os.environ.get("WECHAT_API_PORT", 9000))
    proxy_port = int(os.environ.get("WECHAT_API_PROXY_PORT", 9001))
    
    logger.info(f"目标服务器: 127.0.0.1:{target_port}")
    logger.info(f"代理端口: {proxy_port}")
    
    # 启动代理服务器
    await start_proxy_server("127.0.0.1", target_port, proxy_port)

def run_proxy_server():
    """在单独的线程中运行代理服务器"""
    asyncio.run(start_proxy())

async def main():
    """主函数"""
    try:
        # 在单独的线程中启动代理服务器
        proxy_thread = threading.Thread(target=run_proxy_server, daemon=True)
        proxy_thread.start()
        
        # 等待代理服务器启动
        logger.info("等待代理服务器启动...")
        await asyncio.sleep(2)
        
        # 启动机器人
        logger.info("启动机器人...")
        await bot_core.main()
        
    except KeyboardInterrupt:
        logger.info("用户中断，停止服务")
    except Exception as e:
        logger.exception(f"启动异常: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

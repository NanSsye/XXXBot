"""
启动微信API代理服务器

此脚本用于启动微信API代理服务器，添加对分块下载大文件的支持
"""

import os
import sys
import argparse
from loguru import logger

from WechatAPI.Extensions.proxy_server import run_proxy_server

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='启动微信API代理服务器')
    parser.add_argument('--target-host', type=str, default='127.0.0.1',
                        help='目标微信API服务器主机 (默认: 127.0.0.1)')
    parser.add_argument('--target-port', type=int, default=9000,
                        help='目标微信API服务器端口 (默认: 9000)')
    parser.add_argument('--proxy-port', type=int, default=9001,
                        help='代理服务器端口 (默认: 9001)')
    
    args = parser.parse_args()
    
    # 配置日志
    logger.add("logs/proxy_server.log", rotation="10 MB", level="INFO")
    
    # 打印启动信息
    logger.info("启动微信API代理服务器")
    logger.info(f"目标服务器: {args.target_host}:{args.target_port}")
    logger.info(f"代理端口: {args.proxy_port}")
    
    # 启动代理服务器
    try:
        run_proxy_server(args.target_host, args.target_port, args.proxy_port)
    except KeyboardInterrupt:
        logger.info("用户中断，停止代理服务器")
    except Exception as e:
        logger.exception(f"代理服务器异常: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

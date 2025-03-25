#!/usr/bin/env python
"""
XYBotV2 管理后台启动脚本
此脚本用于单独启动管理后台服务器
"""

import os
import sys
import argparse
import uvicorn
import logging
from pathlib import Path

# 设置日志级别
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("admin_server")

# 确保当前目录在sys.path中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
    logger.debug(f"添加路径到sys.path: {current_dir}")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="XYBotV2管理后台服务器")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务器监听地址")
    parser.add_argument("--port", type=int, default=8080, help="服务器监听端口")
    parser.add_argument("--username", type=str, default="admin", help="管理员用户名")
    parser.add_argument("--password", type=str, default="admin", help="管理员密码")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    # 记录启动参数
    logger.info(f"=== 启动XYBotV2管理后台服务器 ===")
    logger.info(f"主机: {args.host}")
    logger.info(f"端口: {args.port}")
    logger.info(f"用户名: {args.username}")
    logger.info(f"调试模式: {args.debug}")
    logger.info(f"工作目录: {os.getcwd()}")
    logger.info(f"Python版本: {sys.version}")
    logger.info(f"===========================")
    
    # 导入server模块并设置配置
    try:
        logger.debug(f"尝试导入server模块...")
        from server import load_config, config
        logger.debug(f"成功导入server.load_config")
        
        # 更新配置
        load_config()
        logger.debug(f"原始配置: {config}")
        
        config["host"] = args.host
        config["port"] = args.port
        config["username"] = args.username
        config["password"] = args.password
        config["debug"] = args.debug
        
        logger.info(f"更新后配置: {config}")
        
        # 初始化应用
        logger.debug(f"初始化FastAPI应用...")
        from server import init_app, app
        init_app()
        logger.debug(f"FastAPI应用初始化完成")
        
        # 启动uvicorn服务器
        logger.info(f"正在启动XYBotV2管理后台服务器: {args.host}:{args.port}")
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="debug" if args.debug else "info"
        )
    except ImportError as e:
        logger.error(f"导入server模块失败: {e}")
        # 尝试列出当前目录中的文件
        try:
            logger.debug(f"当前目录文件列表:")
            for f in os.listdir(current_dir):
                logger.debug(f"  - {f}")
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        logger.error(f"启动服务器时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1) 
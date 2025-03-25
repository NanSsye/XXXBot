import asyncio
import os
import sys
import time
import tomllib
import traceback
import threading
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# 修改导入语句，确保导入正确的bot_core模块
try:
    # 先尝试使用相对导入（当前目录）
    from .bot_core import bot_core
except ImportError:
    # 如果相对导入失败，尝试使用绝对导入（当前目录）
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    from bot_core import bot_core, set_bot_instance, update_bot_status

# 管理后台启动函数
def start_admin_server(config):
    """启动管理后台服务器"""
    try:
        # 导入需要的模块
        from admin.server import start_server
        
        admin_config = config.get("Admin", {})
        admin_enabled = admin_config.get("enabled", True)
        
        if not admin_enabled:
            logger.info("管理后台功能已禁用")
            return None
            
        admin_host = admin_config.get("host", "0.0.0.0")
        admin_port = admin_config.get("port", 9090)
        admin_username = admin_config.get("username", "admin")
        admin_password = admin_config.get("password", "admin123")
        admin_debug = admin_config.get("debug", False)
        
        # 提前启动管理后台服务
        logger.info(f"启动管理后台，地址: {admin_host}:{admin_port}")
        
        server_thread = start_server(
            host_arg=admin_host,
            port_arg=admin_port,
            username_arg=admin_username,
            password_arg=admin_password,
            debug_arg=admin_debug,
            bot=None  # 暂时没有bot实例
        )
        
        logger.success(f"管理后台已启动: http://{admin_host}:{admin_port}")
        return server_thread
    except Exception as e:
        logger.error(f"启动管理后台时出错: {e}")
        logger.error(traceback.format_exc())
        return None

def is_api_message(record):
    return record["level"].name == "API"


class ConfigChangeHandler(FileSystemEventHandler):
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_triggered = 0
        self.cooldown = 2  # 冷却时间(秒)
        self.waiting_for_change = False  # 是否在等待文件改变

    def on_modified(self, event):
        if not event.is_directory:
            current_time = time.time()
            if current_time - self.last_triggered < self.cooldown:
                return

            file_path = Path(event.src_path).resolve()
            if (file_path.name == "main_config.toml" or
                    "plugins" in str(file_path) and file_path.suffix in ['.py', '.toml']):
                logger.info(f"检测到文件变化: {file_path}")
                self.last_triggered = current_time
                if self.waiting_for_change:
                    logger.info("检测到文件改变，正在重启...")
                    self.waiting_for_change = False
                self.restart_callback()


async def main():
    # 设置工作目录为脚本所在目录
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)
    
    # 更新初始化状态
    update_bot_status("initializing", "系统初始化中")
    
    # 读取配置文件
    config_path = script_dir / "main_config.toml"
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        logger.success("读取主设置成功")
    except Exception as e:
        logger.error(f"读取主设置失败: {e}")
        return
    
    # 启动管理后台（提前启动）
    admin_server_thread = start_admin_server(config)

    # 检查是否启用自动重启
    auto_restart = config.get("XYBot", {}).get("auto-restart", False)

    if auto_restart:
        # 设置监控
        observer = Observer()
        plugins_path = script_dir / "plugins"

        handler = ConfigChangeHandler(None)

        def restart_program():
            logger.info("正在重启程序...")
            # 清理资源
            observer.stop()
            try:
                import multiprocessing.resource_tracker
                multiprocessing.resource_tracker._resource_tracker.clear()
            except Exception as e:
                logger.warning(f"清理资源时出错: {e}")
            # 重启程序
            os.execv(sys.executable, [sys.executable] + sys.argv)

        handler.restart_callback = restart_program
        observer.schedule(handler, str(config_path.parent), recursive=False)
        observer.schedule(handler, str(plugins_path), recursive=True)
        observer.start()

        try:
            # 运行机器人核心
            bot = await bot_core()
            
            # 保持程序运行
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到终止信号，正在关闭...")
            observer.stop()
            observer.join()
        except Exception as e:
            logger.error(f"程序发生错误: {e}")
            logger.error(traceback.format_exc())
            logger.info("等待文件改变后自动重启...")
            handler.waiting_for_change = True

            while handler.waiting_for_change:
                await asyncio.sleep(1)
    else:
        # 直接运行主程序，不启用监控
        try:
            # 运行机器人核心
            bot = await bot_core()
            
            # 保持程序运行
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到终止信号，正在关闭...")
        except Exception as e:
            logger.error(f"发生错误: {e}")
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    # 防止低版本Python运行
    if sys.version_info.major != 3 and sys.version_info.minor != 11:
        print("请使用Python3.11")
        sys.exit(1)
    print(
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░ ░▒▓██████▓▒░▒▓████████▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░  \n"
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░          ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ \n"
        "░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░           ░▒▓█▓▒▒▓█▓▒░       ░▒▓█▓▒░ \n"
        " ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░           ░▒▓█▓▒▒▓█▓▒░ ░▒▓██████▓▒░  \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░            ░▒▓█▓▓█▓▒░ ░▒▓█▓▒░        \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░            ░▒▓█▓▓█▓▒░ ░▒▓█▓▒░        \n"
        "░▒▓█▓▒░░▒▓█▓▒░  ░▒▓█▓▒░   ░▒▓███████▓▒░ ░▒▓██████▓▒░  ░▒▓█▓▒░             ░▒▓██▓▒░  ░▒▓████████▓▒░\n" )


    logger.remove()

    logger.level("API", no=1, color="<cyan>")

    logger.add(
        "logs/XYBot_{time}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        encoding="utf-8",
        enqueue=True,
        retention="2 weeks",
        rotation="00:01",
        backtrace=True,
        diagnose=True,
        level="DEBUG",
    )
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
        level="TRACE",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    asyncio.run(main())
